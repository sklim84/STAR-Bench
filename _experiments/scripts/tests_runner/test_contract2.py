"""A single-turn run end to end against the mock server, asserting Contract 2."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from _experiments.scripts import benchmark
from _experiments.scripts.runner import records
from _experiments.scripts.tests_runner.conftest import base_argv
from _experiments.scripts.tests_runner.mock_server import malformed, raw_content, status, text, tool_call


def _run(server, benchmark_dir: Path, out: Path, executor, extra=()) -> list[dict]:
    argv = base_argv(server, out) + ["--cases-dir", str(benchmark_dir)] + list(extra)
    benchmark.main(argv, executor=executor)
    files = sorted(out.glob("*.jsonl"))
    assert files, f"no run records under {out}"
    return [rec for f in files for rec in records.read_records(f)]


def test_every_case_gets_a_record_with_provenance_and_config(server, single_benchmark, tmp_path,
                                                             fake_tools):
    server.always(text("정상 거래만 확인됩니다."))
    out = tmp_path / "records"
    recs = _run(server, single_benchmark, out, fake_tools)

    assert sorted(r["case_id"] for r in recs) == ["st_001", "st_002", "st_003"]
    for rec in recs:
        assert rec["setting"] == "single"
        assert rec["tools_lang"] == "kr"
        assert rec["query_lang"] == "kr"
        assert rec["run_id"]
        assert rec["config"]["model"] == "mock-model"
        assert rec["config"]["temperature"] == 0.0
        assert rec["config"]["seed"]
        assert rec["config"]["concurrency"] == 1
        prov = rec["provenance"]
        assert "star_bench_commit" in prov and "started_at" in prov
        assert prov["tools_sha256"] and prov["system_prompt_sha256"]
        assert "streamlit_stubbed" in prov
        assert rec["final_text"] == "정상 거래만 확인됩니다."
        assert rec["stop_reason"] == "no_tool_call"
        assert rec["rounds"][0]["finish_reason"] == "stop"
        assert rec["rounds"][0]["usage"]["total_tokens"] == 15
        assert rec["rounds"][0]["attempts"] == 1


def test_a_tool_call_is_recorded_with_its_raw_arguments_result_and_source(
        server, single_benchmark, tmp_path, fake_tools):
    server.push(tool_call("get_statistics", {}, reasoning="먼저 통계를 본다"),
                text("총 4,732,130건입니다."))
    server.always(text("추가 정보가 필요합니다."))
    out = tmp_path / "records"
    recs = {r["case_id"]: r for r in _run(server, single_benchmark, out, fake_tools)}

    rec = recs["st_001"]
    assert len(rec["rounds"]) == 2
    first = rec["rounds"][0]
    call = first["tool_calls"][0]
    assert call["name"] == "get_statistics"
    assert call["source"] == "native"
    assert call["valid_json"] is True
    assert call["args_is_object"] is True
    assert call["arguments_raw"] == "{}"
    assert first["reasoning_chars"] == len("먼저 통계를 본다")
    executed = first["executed"][0]
    assert executed["tool_call_id"] == call["id"]
    assert executed["error"] is None
    assert json.loads(executed["result"])["tool"] == "get_statistics"
    assert rec["final_text"] == "총 4,732,130건입니다."
    assert rec["stop_reason"] == "no_tool_call"


def test_the_reasoning_goes_back_into_the_history(server, single_benchmark, tmp_path, fake_tools):
    server.push(tool_call("get_statistics", {}, reasoning="계획"), text("끝"))
    server.always(text("끝"))
    _run(server, single_benchmark, tmp_path / "r", fake_tools)

    second = server.requests[1]["messages"]
    assistant = [m for m in second if m["role"] == "assistant"][0]
    assert assistant.get("reasoning_content") == "계획"
    assert [m["role"] for m in second][-1] == "tool"


def test_assistant_text_alongside_a_call_stays_in_the_history(server, single_benchmark, tmp_path,
                                                              fake_tools):
    server.push(tool_call("get_statistics", {}, content="통계를 먼저 봅니다"), text("끝"))
    server.always(text("끝"))
    _run(server, single_benchmark, tmp_path / "r", fake_tools)
    assistant = [m for m in server.requests[1]["messages"] if m["role"] == "assistant"][0]
    assert assistant["content"] == "통계를 먼저 봅니다"


def test_an_error_stops_the_case_but_keeps_the_calls_made_before_it(
        server, single_benchmark, tmp_path, fake_tools):
    server.push(tool_call("get_statistics", {}), status(400, "template rejected the request"))
    server.always(text("끝"))
    recs = {r["case_id"]: r for r in _run(server, single_benchmark, tmp_path / "r", fake_tools)}
    rec = recs["st_001"]
    assert rec["stop_reason"] == "error"
    assert rec["error"]["status"] == 400
    assert rec["error"]["round"] == 1
    assert rec["rounds"][0]["tool_calls"][0]["name"] == "get_statistics"
    assert rec["rounds"][0]["executed"][0]["result"]


def test_a_gateway_reply_without_choices_is_an_error_and_not_a_silent_zero(
        server, single_benchmark, tmp_path, fake_tools):
    server.always(malformed("no_choices"))
    recs = _run(server, single_benchmark, tmp_path / "r", fake_tools)
    assert all(r["stop_reason"] == "error" for r in recs)
    assert all(r["error"]["type"] == "gateway_error" for r in recs)


def test_an_empty_reply_is_an_error_type_of_its_own(server, single_benchmark, tmp_path,
                                                    fake_tools):
    server.always(malformed("empty"))
    recs = _run(server, single_benchmark, tmp_path / "r", fake_tools)
    assert all(r["error"]["type"] == "empty_reply" for r in recs)


def test_a_length_stop_is_distinguishable_from_a_model_that_stopped(
        server, single_benchmark, tmp_path, fake_tools):
    server.always(text("잘린 응답", finish_reason="length"))
    recs = _run(server, single_benchmark, tmp_path / "r", fake_tools)
    assert all(r["stop_reason"] == "length" for r in recs)
    assert all(r["rounds"][-1]["finish_reason"] == "length" for r in recs)


def test_arguments_that_are_not_an_object_are_flagged_and_not_executed(
        server, single_benchmark, tmp_path, fake_tools):
    server.push(tool_call(("get_statistics", "[1, 2, 3]")), text("끝"))
    server.always(text("끝"))
    recs = {r["case_id"]: r for r in _run(server, single_benchmark, tmp_path / "r", fake_tools)}
    call = recs["st_001"]["rounds"][0]["tool_calls"][0]
    assert call["args_is_object"] is False
    assert call["arguments_raw"] == "[1, 2, 3]"
    executed = recs["st_001"]["rounds"][0]["executed"][0]
    assert executed["error"]["type"] == "arguments_not_object"
    assert ("get_statistics", {}) not in fake_tools.calls


def test_unparsable_arguments_keep_the_raw_string(server, single_benchmark, tmp_path, fake_tools):
    server.push(tool_call(("get_statistics", "{not json")), text("끝"))
    server.always(text("끝"))
    recs = {r["case_id"]: r for r in _run(server, single_benchmark, tmp_path / "r", fake_tools)}
    call = recs["st_001"]["rounds"][0]["tool_calls"][0]
    assert call["valid_json"] is False
    assert call["arguments_raw"] == "{not json"


def test_a_tool_that_raises_is_recorded_as_an_executed_error(server, single_benchmark, tmp_path,
                                                             fake_tools):
    server.push(tool_call("explodes", {}), text("끝"))
    server.always(text("끝"))
    recs = {r["case_id"]: r for r in _run(server, single_benchmark, tmp_path / "r", fake_tools)}
    executed = recs["st_001"]["rounds"][0]["executed"][0]
    assert executed["error"]["type"] == "RuntimeError"
    assert recs["st_001"]["stop_reason"] != "error"


def test_the_round_ceiling_stops_the_loop_and_says_so(server, single_benchmark, tmp_path,
                                                      fake_tools):
    server.always(tool_call("get_statistics", {}))
    recs = _run(server, single_benchmark, tmp_path / "r", fake_tools, extra=["--max-rounds", "3"])
    for rec in recs:
        assert len(rec["rounds"]) == 3
        assert rec["stop_reason"] == "max_rounds"


def test_a_retryable_status_is_retried_and_the_attempts_are_recorded(
        server, single_benchmark, tmp_path, fake_tools):
    server.push(status(503, "warming up"), text("이제 됩니다"))
    server.always(text("끝"))
    argv = base_argv(server, tmp_path / "r") + ["--cases-dir", str(single_benchmark),
                                                "--max-retries", "2"]
    benchmark.main(argv, executor=fake_tools)
    recs = {r["case_id"]: r for r in
            (rec for f in sorted((tmp_path / "r").glob("*.jsonl"))
             for rec in records.read_records(f))}
    assert recs["st_001"]["rounds"][0]["attempts"] == 2
    assert recs["st_001"]["final_text"] == "이제 됩니다"


def test_a_deterministic_4xx_is_not_retried(server, single_benchmark, tmp_path, fake_tools):
    server.always(status(400, "bad request"))
    argv = base_argv(server, tmp_path / "r") + ["--cases-dir", str(single_benchmark),
                                                "--max-retries", "3"]
    benchmark.main(argv, executor=fake_tools)
    recs = [rec for f in sorted((tmp_path / "r").glob("*.jsonl"))
            for rec in records.read_records(f)]
    assert all(r["rounds"][0]["attempts"] == 1 for r in recs)


def test_the_run_manifest_records_the_command_and_the_configuration(
        server, single_benchmark, tmp_path, fake_tools):
    server.always(text("끝"))
    out = tmp_path / "r"
    _run(server, single_benchmark, out, fake_tools)
    manifest = json.loads(next(out.glob("*.manifest.json")).read_text(encoding="utf-8"))
    assert manifest["setting"] == "single"
    assert manifest["tools_lang"] == "kr"
    assert manifest["n_cases_benchmark"] == 3
    assert manifest["config"]["model"] == "mock-model"
    assert manifest["provenance"]["preflight"]["ok"] is True


def test_cases_are_collected_from_every_file_of_the_directory(server, split_benchmark, tmp_path,
                                                              fake_tools):
    server.always(text("끝"))
    recs = _run(server, split_benchmark, tmp_path / "r", fake_tools)
    assert sorted(r["case_id"] for r in recs) == ["st_001", "st_002", "st_003"]


def test_a_long_tool_result_is_truncated_for_the_model_but_kept_whole_in_the_record(
        server, single_benchmark, tmp_path):
    payload = json.dumps([{"date": 20240101, "amount": 5000000}] * 4000, ensure_ascii=False)

    def big_tool(name, arguments):
        return payload

    server.push(tool_call("query_transactions", {"sql": "SELECT 1"}), text("끝"))
    server.always(text("끝"))
    recs = {r["case_id"]: r for r in _run(server, single_benchmark, tmp_path / "r", big_tool)}
    executed = recs["st_001"]["rounds"][0]["executed"][0]
    assert executed["result"] == payload
    assert executed["error"]["type"] == "result_truncated"
    sent = [m for m in server.requests[1]["messages"] if m["role"] == "tool"][0]["content"]
    assert len(sent) < len(payload)
    assert "truncated by the benchmark runner" in sent
