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
