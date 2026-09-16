"""The canary sample, the thresholds and the anomaly gates.

The gates are tested on records written for the test, one per failure the 2026
run actually had, so a threshold that stops working is a red test rather than a
quiet pass.
"""

from __future__ import annotations

import json

import pytest

from _experiments.scripts.preflight import canary
from _experiments.scripts.preflight.gate import Context, STAR_BENCH_ROOT

THRESHOLDS = canary.load_thresholds()


def record(case_id="st_a_001", *, calls=1, source="native", finish_reason="tool_calls",
           error=None, stop_reason="no_tool_call", results=("{\"total_count\": 3}",),
           prompt_tokens=1000, elapsed=1.0, turn=None, max_model_len=32768,
           max_tokens=8192) -> dict:
    rounds = [{
        "idx": 0, "finish_reason": finish_reason, "content": "",
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": 10},
        "tool_calls": [{"id": f"c{i}", "name": "get_statistics", "arguments_raw": "{}",
                        "arguments": {}, "source": source, "valid_json": True,
                        "args_is_object": True} for i in range(calls)],
        "executed": [{"tool_call_id": f"c{i}", "name": "get_statistics", "arguments": {},
                      "result": results[i % len(results)], "error": None}
                     for i in range(calls)],
        "error": None, "attempts": 1,
    }]
    return {"run_id": "r", "case_id": case_id, "turn": turn, "setting": "single",
            "tools_lang": "kr", "query_lang": "kr",
            "config": {"max_model_len": max_model_len, "max_tokens": max_tokens},
            "provenance": {}, "rounds": rounds, "final_text": "", "stop_reason": stop_reason,
            "error": error, "elapsed_s": elapsed}


def metrics(records, *, baseline=0.0, gold=None):
    gold = gold or {r["case_id"]: {"expects_tool": True} for r in records}
    return {m.name: m for m in canary.evaluate(records, gold=gold, thresholds=THRESHOLDS,
                                               baseline_empty_share=baseline)}


# -- the sample -------------------------------------------------------------

def test_the_sample_covers_every_tool_the_platform_offers():
    sample = canary.load_sample()
    from _experiments.scripts._platform import ensure_platform_on_path
    ensure_platform_on_path()
    from src.features.agent import TOOLS

    assert set(sample["tools_covered"]) == {t["function"]["name"] for t in TOOLS}


def test_every_sampled_id_is_in_the_benchmark():
    from _experiments.scripts.preflight.data import load_cases

    sample = canary.load_sample()
    cases, _ = load_cases(STAR_BENCH_ROOT / "benchmarks")
    scenarios, _ = load_cases(STAR_BENCH_ROOT / "benchmarks_multiturn")
    known = {c["id"] for c in cases}
    assert set(sample["cases"]) <= known
    assert set(sample["scenarios"]) <= {s["id"] for s in scenarios}
    assert len(sample["cases"]) == 40


def test_every_threshold_says_where_its_number_came_from():
    doc = json.loads(canary.THRESHOLDS_PATH.read_text(encoding="utf-8"))
    for name, entry in doc["thresholds"].items():
        assert entry["why"].strip(), f"{name} has no source"
        assert isinstance(entry["value"], (int, float))


# -- the anomaly gates ------------------------------------------------------

def test_a_healthy_run_trips_nothing():
    for metric in canary.evaluate([record(f"st_{i}") for i in range(20)],
                                  gold={f"st_{i}": {"expects_tool": True} for i in range(20)},
                                  thresholds=THRESHOLDS, baseline_empty_share=0.0):
        assert metric.ok, f"{metric.name}: {metric.value}"


def test_a_model_that_stops_calling_tools_trips_the_no_call_gate():
    records = [record(f"st_{i}", calls=0) for i in range(10)] + [record("st_x")]
    metric = metrics(records)["no-tool-call rate"]
    assert not metric.ok
    assert "st_0" in metric.offenders


def test_a_case_whose_gold_expects_no_tool_is_not_counted_as_a_miss():
    records = [record(f"st_{i}", calls=0) for i in range(10)]
    gold = {f"st_{i}": {"expects_tool": False} for i in range(10)}
    assert metrics(records, gold=gold)["no-tool-call rate"].ok


def test_one_http_error_in_forty_cases_trips_the_error_gate():
    """Llama-3.2-3B answered 16.1% of its 2026 cases with an error scored as zero."""
    records = [record(f"st_{i}") for i in range(40)]
    records.append(record("st_boom", error={"type": "APIStatusError", "message": "503"},
                          stop_reason="error"))
    metric = metrics(records)["system-error rate"]
    assert not metric.ok
    assert "st_boom" in metric.offenders[0]


def test_records_that_stop_on_length_trip_the_budget_gate():
    records = [record(f"st_{i}") for i in range(40)]
    records += [record("st_long1", finish_reason="length"),
                record("st_long2", finish_reason="length")]
    assert not metrics(records)["finish_reason length share"].ok


def test_calls_arriving_through_the_fallback_parser_trip_the_parser_gate():
    """The finance Qwen was served with a parser that never matched (L5-010)."""
    records = [record(f"st_{i}", source="fallback") for i in range(5)]
    records += [record(f"st_n{i}") for i in range(10)]
    metric = metrics(records)["fallback-parser share"]
    assert not metric.ok
    assert metric.value == pytest.approx(5 / 15)


def test_tool_results_that_answer_nothing_trip_against_the_recorded_baseline():
    empty = "{\"notice\": \"No transaction history\"}"
    records = [record(f"st_{i}", results=(empty,)) for i in range(5)]
    records += [record(f"st_n{i}") for i in range(10)]
    metric = metrics(records, baseline=0.04)["empty tool-result share"]
    assert not metric.ok
    # A low baseline keeps the floor, so one legitimately empty result is not a trip.
    assert metric.limit == pytest.approx(THRESHOLDS["empty_result_share_floor"])
    assert metric.value == pytest.approx(5 / 15)


def test_a_baseline_that_is_already_high_raises_the_limit_with_it():
    empty = "{\"notice\": \"No ring pattern\"}"
    records = [record(f"st_{i}", results=(empty,)) for i in range(2)]
    records += [record(f"st_n{i}") for i in range(18)]
    metric = metrics(records, baseline=0.30)["empty tool-result share"]
    assert metric.ok
    assert metric.limit == pytest.approx(0.40)


def test_a_prompt_that_leaves_no_room_for_a_tool_result_trips_the_headroom_gate():
    """Phi-4-mini was registered at 12,288 tokens against a 9k prompt (C2-001)."""
    records = [record("st_a", prompt_tokens=11000, max_model_len=12288, max_tokens=1000)]
    metric = metrics(records)["prompt headroom (tokens)"]
    assert not metric.ok
    assert metric.value == 288


def test_a_case_far_slower_than_the_rest_is_reported():
    records = [record(f"st_{i}", elapsed=5.0) for i in range(20)]
    records.append(record("st_slow", elapsed=900.0))
    found = metrics(records)
    assert not found["per-case latency ceiling"].ok
    assert "st_slow" in found["per-case latency ceiling"].offenders[0]
    assert not found["per-case latency spread"].ok


def test_a_uniformly_slow_reasoning_run_is_not_an_outlier():
    records = [record(f"st_{i}", elapsed=180.0) for i in range(20)]
    found = metrics(records)
    assert found["per-case latency ceiling"].ok
    assert found["per-case latency spread"].ok


# -- end to end against the mock server -------------------------------------

def test_the_canary_runs_against_the_mock_server(tmp_path):
    from _experiments.scripts.tests_runner.mock_server import MockOpenAIServer, text, tool_call

    def respond(request):
        messages = request.get("messages") or []
        if messages and messages[-1].get("role") == "tool":
            return text("answered")
        return tool_call("get_statistics", {})

    ctx = Context()
    with MockOpenAIServer() as server:
        server.respond_with(respond)
        result = canary.run(ctx, base_url=server.url, out_dir=tmp_path / "canary",
                            model="mock", allow_unpinned=True, no_env_check=True)
    assert result.ok, [c.detail for c in result.failures]
    assert any(c.name == "prompt headroom (tokens)" for c in result.checks)
    assert (tmp_path / "canary" / "case_ids.txt").is_file()
