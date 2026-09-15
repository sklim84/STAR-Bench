"""End to end: run records in, eval files out."""

from __future__ import annotations

import json

from conftest import call, record

from _experiments.scripts.scoring.score_runs import main

CASES = [
    {"id": "c1", "question": "q", "difficulty": "easy", "expected": {
        "primary_tool": "analyze_network", "tools_must_include": ["analyze_network"],
        "param_checks": {"analyze_network": {"account_id": 78432}}}},
    {"id": "c2", "question": "q", "difficulty": "medium", "expected": {
        "primary_tool": "", "tools_must_include": []}},
]

SCENARIO = [{"id": "mt1", "sub_category": "base", "turns": [
    {"turn": 1, "content": "u", "tool_calls": [{"name": "get_statistics", "arguments": {}}],
     "tool_result": {"total_count": 1}},
    {"turn": 2, "content": "u", "tool_calls": [{"name": "analyze_network", "arguments": {"account_id": 7}}],
     "tool_result": {"connected_account_count": 1}}]}]


def _write(path, rows):
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")


def test_single_turn_run_produces_an_eval_file(tmp_path):
    bench = tmp_path / "bench"
    bench.mkdir()
    (bench / "cases_x.json").write_text(json.dumps(CASES, ensure_ascii=False), encoding="utf-8")
    runs = tmp_path / "runs"
    runs.mkdir()
    _write(runs / "model_a.jsonl", [
        record([call("analyze_network", {"account_id": 78432})], case_id="c1", run_id="model_a"),
        record([], case_id="c2", run_id="model_a", final_text="Out of scope."),
    ])
    out = tmp_path / "eval"
    assert main(["--runs", str(runs), "--benchmark", str(bench), "--out", str(out), "--no-sql-exec"]) == 0

    report = json.loads((out / "eval_model_a.json").read_text(encoding="utf-8"))
    assert report["meta"]["coverage"]["complete"] is True
    assert report["meta"]["scorer"]["benchmark_sha256"] and report["meta"]["scorer"]["tool_schema_sha256"]
    assert report["aggregate"]["h"] == {"mean": 1.0, "n": 2}
    assert report["aggregate"]["a"]["n"] == 1
    assert {r["case_id"] for r in report["results"]} == {"c1", "c2"}
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary[0]["run_id"] == "model_a"


def test_missing_case_is_reported_in_coverage(tmp_path):
    bench = tmp_path / "bench"
    bench.mkdir()
    (bench / "cases_x.json").write_text(json.dumps(CASES, ensure_ascii=False), encoding="utf-8")
    runs = tmp_path / "runs"
    runs.mkdir()
    _write(runs / "model_b.jsonl", [record([], case_id="c2", run_id="model_b", final_text="No.")])
    out = tmp_path / "eval"
    main(["--runs", str(runs), "--benchmark", str(bench), "--out", str(out), "--no-sql-exec"])
    report = json.loads((out / "eval_model_b.json").read_text(encoding="utf-8"))
    assert report["meta"]["coverage"]["missing_case_ids"] == ["c1"]
    assert report["aggregate"]["error_types"]["system_error"] == 1


def test_multiturn_records_are_grouped_by_scenario_and_turn(tmp_path):
    bench = tmp_path / "bench"
    bench.mkdir()
    (bench / "cases_mt.json").write_text(json.dumps(SCENARIO, ensure_ascii=False), encoding="utf-8")
    runs = tmp_path / "runs"
    runs.mkdir()
    _write(runs / "model_c.jsonl", [
        record([call("get_statistics", {})], case_id="mt1", run_id="model_c", turn=1, setting="oracle"),
        record([call("analyze_network", {"account_id": 7})], case_id="mt1", run_id="model_c", turn=2, setting="oracle"),
    ])
    out = tmp_path / "eval"
    main(["--runs", str(runs), "--benchmark", str(bench), "--out", str(out), "--no-sql-exec"])
    report = json.loads((out / "eval_model_c.json").read_text(encoding="utf-8"))
    assert report["aggregate"]["n_turns"] == 2 and report["aggregate"]["c"] == {"mean": 1.0, "n": 1}
    assert report["results"][0]["setting"] == "oracle"
