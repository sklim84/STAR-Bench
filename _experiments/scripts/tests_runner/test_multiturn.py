"""The multi-turn runner: one record per turn, oracle and end-to-end."""

from __future__ import annotations

import json
from pathlib import Path

from _experiments.scripts import benchmark_multiturn as mt
from _experiments.scripts.runner import records
from _experiments.scripts.runner.loop import CLARIFICATION_REPLY
from _experiments.scripts.tests_runner.conftest import base_argv
from _experiments.scripts.tests_runner.mock_server import text, tool_call


def _run(server, bench: Path, out: Path, executor, extra=()) -> list[dict]:
    argv = base_argv(server, out) + ["--cases-dir", str(bench)] + list(extra)
    mt.main(argv, executor=executor)
    return [rec for f in sorted(out.glob("*.jsonl")) for rec in records.read_records(f)]


def test_one_record_per_turn_with_the_turn_number(server, multiturn_benchmark, tmp_path,
                                                  fake_tools):
    server.always(text("추가 정보가 필요합니다."))
    recs = _run(server, multiturn_benchmark, tmp_path / "r", fake_tools)
    assert [r["turn"] for r in recs] == [1, 2, 3]
    assert {r["case_id"] for r in recs} == {"mt_001"}
    assert all(r["setting"] == "oracle" for r in recs)
    assert all(r["final_text"] for r in recs)


def test_the_multi_turn_runner_sends_the_reasoning_mode_and_the_budget(
        server, multiturn_benchmark, tmp_path, fake_tools):
    server.always(text("네"))
    _run(server, multiturn_benchmark, tmp_path / "r", fake_tools)
    request = server.requests[0]
    assert request["max_completion_tokens"] == 1024
    assert request["temperature"] == 0
    assert request["seed"]
    assert request["tools"], "the multi-turn runner must send the schema arm"


def test_the_oracle_setting_injects_the_gold_call_and_result(server, multiturn_benchmark,
                                                             tmp_path, fake_tools):
    server.always(text("네"))
    _run(server, multiturn_benchmark, tmp_path / "r", fake_tools)
    second = server.requests[1]["messages"]
    assistant = [m for m in second if m.get("tool_calls")][0]
    assert assistant["tool_calls"][0]["function"]["name"] == "query_transactions"
    tool_msg = [m for m in second if m["role"] == "tool"][0]
    assert json.loads(tool_msg["content"])["total_count"] == 2
    assert not fake_tools.calls, "the oracle setting must not execute the model's calls"


def test_an_oracle_clarification_turn_gets_a_neutral_reply_not_the_gold_note(
        server, multiturn_benchmark, tmp_path, fake_tools):
    server.always(text("네"))
    _run(server, multiturn_benchmark, tmp_path / "r", fake_tools)
    # Turn 3 is the clarification turn; the history before it must not carry an
    # annotation. Only the assistant replies injected by the runner are checked.
    injected = [m["content"] for r in server.requests for m in r["messages"]
                if m["role"] == "assistant" and not m.get("tool_calls")]
    assert "되묻기" not in " ".join(injected)


def test_the_e2e_setting_executes_the_models_own_calls_and_feeds_them_forward(
        server, multiturn_benchmark, tmp_path, fake_tools):
    server.push(tool_call("query_transactions", {"sql": "SELECT 1"}),
                tool_call("score_account_risk", {"account_id": 9000000000000002}))
    server.always(text("추가 정보가 필요합니다."))
    recs = _run(server, multiturn_benchmark, tmp_path / "r", fake_tools,
                extra=["--setting", "e2e"])
    assert [name for name, _ in fake_tools.calls] == ["query_transactions", "score_account_risk"]
    assert recs[0]["rounds"][0]["executed"][0]["result"]
    second = server.requests[1]["messages"]
    tool_msg = [m for m in second if m["role"] == "tool"][0]
    assert json.loads(tool_msg["content"])["tool"] == "query_transactions"


def test_an_e2e_turn_without_a_call_keeps_the_models_own_text_in_the_history(
        server, multiturn_benchmark, tmp_path, fake_tools):
    server.always(text("어느 계좌를 말씀하시는지요?"))
    _run(server, multiturn_benchmark, tmp_path / "r", fake_tools, extra=["--setting", "e2e"])
    injected = [m["content"] for m in server.requests[1]["messages"] if m["role"] == "assistant"]
    assert injected == ["어느 계좌를 말씀하시는지요?"]
    assert CLARIFICATION_REPLY not in injected


def test_a_turn_that_errors_is_recorded_as_an_error_and_not_as_no_call(
        server, multiturn_benchmark, tmp_path, fake_tools):
    from _experiments.scripts.tests_runner.mock_server import status
    server.always(status(500, "server exploded"))
    recs = _run(server, multiturn_benchmark, tmp_path / "r", fake_tools)
    assert all(r["stop_reason"] == "error" for r in recs)
    assert all(r["error"]["status"] == 500 for r in recs)


def test_the_run_is_verified_against_the_expected_turn_count(server, multiturn_benchmark,
                                                             tmp_path, fake_tools, capsys):
    server.always(text("네"))
    _run(server, multiturn_benchmark, tmp_path / "r", fake_tools)
    assert "3/3 (complete)" in capsys.readouterr().out


def test_an_oracle_sql_turn_shows_the_query_and_never_the_checks(server, multiturn_benchmark,
                                                                 tmp_path, fake_tools):
    """C2-008: the evaluator's keys are checks, not a call the model could make."""
    server.always(text("네"))
    _run(server, multiturn_benchmark, tmp_path / "r", fake_tools)

    injected = [m for request in server.requests for m in request["messages"]
                if m.get("tool_calls")]
    assert injected, "the oracle setting must inject the gold call"
    arguments = [json.loads(call["function"]["arguments"])
                 for m in injected for call in m["tool_calls"]
                 if call["function"]["name"] == "query_transactions"]
    assert arguments
    for args in arguments:
        assert args["sql"].lstrip().upper().startswith("SELECT")
        for key in ("sql_conditions", "sql_valid", "sql_contains"):
            assert key not in args

    whole = json.dumps(server.requests, ensure_ascii=False)
    for key in ("sql_conditions", "sql_valid", "sql_contains"):
        assert key not in whole, f"{key} reached the model"


def test_evaluator_only_keys_are_stripped_even_without_a_reference_query():
    from _experiments.scripts.runner.loop import oracle_arguments

    call = {"name": "analyze_network",
            "arguments": {"account_id": 9000000000000002, "hops": 2,
                          "hops_min": 1, "hops_max": 3, "result_row_count_min": 1}}
    assert oracle_arguments(call, {}) == {"account_id": 9000000000000002, "hops": 2}


def test_a_turn_level_reference_call_is_used_when_the_call_carries_none():
    from _experiments.scripts.runner.loop import oracle_arguments

    call = {"name": "query_transactions", "arguments": {"sql_conditions": [], "sql_valid": True}}
    turn = {"reference_calls": {"query_transactions": {"sql": "SELECT 1 FROM hofinet"}}}
    assert oracle_arguments(call, turn) == {"sql": "SELECT 1 FROM hofinet"}


def test_the_real_multi_turn_gold_renders_a_query_for_every_sql_turn():
    """The rebuilt benchmark, not a fixture: no SQL turn injects a check."""
    from pathlib import Path as _Path

    from _experiments.scripts.runner.loop import EVALUATOR_ONLY_ARGS, oracle_arguments

    root = _Path(__file__).resolve().parents[3]
    scenarios = json.loads(
        (root / "benchmarks_multiturn" / "cases_str_workflow.json").read_text(encoding="utf-8"))
    sql_turns = 0
    for scenario in scenarios:
        for turn in scenario.get("turns", []):
            for call in turn.get("tool_calls") or []:
                args = oracle_arguments(call, turn)
                assert not (set(args) & EVALUATOR_ONLY_ARGS), (scenario["id"], turn["turn"])
                if call["name"] == "query_transactions":
                    sql_turns += 1
                    assert args.get("sql", "").lstrip().upper().startswith(("SELECT", "WITH")), \
                        (scenario["id"], turn["turn"])
    assert sql_turns > 0


# ---------------------------------------------------------------------------
# The round ceiling, and the language of the injected clarification reply
# ---------------------------------------------------------------------------

def test_a_turn_over_the_call_ceiling_is_recorded_as_one(server, multiturn_benchmark,
                                                         tmp_path, fake_tools):
    """L5-024: the single-turn loop reports the ceiling; this one truncated silently."""
    from _experiments.scripts.runner.loop import MAX_CALLS_PER_ROUND

    many = tool_call("get_statistics", {})
    many["choices"][0]["message"]["tool_calls"] = [
        {"id": f"c{i}", "type": "function",
         "function": {"name": "get_statistics", "arguments": "{}"}}
        for i in range(MAX_CALLS_PER_ROUND + 4)]
    server.always(many)
    recs = _run(server, multiturn_benchmark, tmp_path / "r", fake_tools,
                extra=["--setting", "e2e"])

    first = recs[0]
    assert len(first["rounds"][0]["tool_calls"]) == MAX_CALLS_PER_ROUND
    assert first["rounds"][0]["error"]["type"] == "call_limit"
    assert str(MAX_CALLS_PER_ROUND + 4) in first["rounds"][0]["error"]["message"]
    assert first["error"]["type"] == "call_limit"
    assert first["stop_reason"] == "max_calls"


def test_a_turn_within_the_ceiling_carries_no_call_limit_error(server, multiturn_benchmark,
                                                               tmp_path, fake_tools):
    server.always(tool_call("get_statistics", {}))
    recs = _run(server, multiturn_benchmark, tmp_path / "r", fake_tools,
                extra=["--setting", "e2e"])
    assert recs[0]["rounds"][0]["error"] is None
    assert recs[0]["error"] is None
    assert recs[0]["stop_reason"] == "tool_call"


def test_the_injected_clarification_reply_follows_the_language_of_the_arm():
    """A Korean sentence used to be injected into every English-arm history."""
    from _experiments.scripts.runner import loop

    assert loop.clarification_reply("en") == loop.CLARIFICATION_REPLIES["en"]
    assert loop.clarification_reply("kr") == loop.CLARIFICATION_REPLIES["kr"]
    assert loop.clarification_reply(None) == loop.CLARIFICATION_REPLIES["kr"]

    turn = {"turn": 3, "content": "which account?"}
    english = loop._oracle_turns(turn, 3, loop.clarification_reply("en"))
    assert english == [{"role": "assistant", "content": loop.CLARIFICATION_REPLIES["en"]}]
    korean = loop._oracle_turns(turn, 3, loop.clarification_reply("kr"))
    assert korean == [{"role": "assistant", "content": loop.CLARIFICATION_REPLIES["kr"]}]


def test_an_english_run_never_puts_a_korean_reply_in_the_history(
        server, multiturn_benchmark, tmp_path, fake_tools):
    from _experiments.scripts.runner.loop import CLARIFICATION_REPLIES

    server.always(text(""))
    # --query-lang now has to agree with the cases directory, so the English arm reads
    # a directory named for it; the fixture scenarios are copied under that name.
    import shutil
    en_bench = tmp_path / "scenarios_en"
    shutil.copytree(multiturn_benchmark, en_bench)
    _run(server, en_bench, tmp_path / "en", fake_tools,
         extra=["--query-lang", "en", "--setting", "e2e"])
    injected = [m["content"] for r in server.requests for m in r["messages"]
                if m["role"] == "assistant" and not m.get("tool_calls")]
    assert CLARIFICATION_REPLIES["en"] in injected
    assert CLARIFICATION_REPLIES["kr"] not in injected


def test_a_korean_run_keeps_the_korean_reply(server, multiturn_benchmark, tmp_path, fake_tools):
    from _experiments.scripts.runner.loop import CLARIFICATION_REPLIES

    server.always(text(""))
    _run(server, multiturn_benchmark, tmp_path / "kr", fake_tools,
         extra=["--query-lang", "kr", "--setting", "e2e"])
    injected = [m["content"] for r in server.requests for m in r["messages"]
                if m["role"] == "assistant" and not m.get("tool_calls")]
    assert CLARIFICATION_REPLIES["kr"] in injected
    assert CLARIFICATION_REPLIES["en"] not in injected
