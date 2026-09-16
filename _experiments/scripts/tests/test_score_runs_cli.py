"""End to end: run records in, eval files out."""

from __future__ import annotations

import json
from pathlib import Path

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


# ---------------------------------------------------------------------------
# The records say which benchmark they were run on; the scorer checks it (V-04)
#
# Scoring the Korean run against benchmarks_en succeeded silently and wrote an
# eval whose provenance hash and whose gold came from different data.
# ---------------------------------------------------------------------------

from _experiments.scripts.scoring.gold import load_benchmark  # noqa: E402


def _bench(tmp_path, name="bench", cases=None):
    path = tmp_path / name
    path.mkdir()
    (path / "cases_x.json").write_text(json.dumps(cases or CASES, ensure_ascii=False),
                                       encoding="utf-8")
    return path


def _run_dir(tmp_path, rows, name="runs"):
    runs = tmp_path / name
    runs.mkdir()
    _write(runs / "model_a.jsonl", rows)
    return runs


def _records(bench_dir, *, sha=None, case_ids=("c1", "c2")):
    """Records carrying the Contract 2 benchmark digest, as the runner writes it."""
    digest = sha if sha is not None else load_benchmark(bench_dir).sha256
    rows = []
    for case_id in case_ids:
        rec = record([call("analyze_network", {"account_id": 78432})], case_id=case_id,
                     run_id="model_a")
        rec["provenance"] = {"benchmark_dir": Path(bench_dir).name, "benchmark_sha256": digest,
                             "benchmark_files": 1}
        rows.append(rec)
    return rows


def test_records_that_name_this_benchmark_are_scored_and_the_check_is_recorded(tmp_path):
    bench = _bench(tmp_path)
    runs = _run_dir(tmp_path, _records(bench))
    out = tmp_path / "eval"
    assert main(["--runs", str(runs), "--benchmark", str(bench), "--out", str(out),
                 "--no-sql-exec"]) == 0
    check = json.loads((out / "eval_model_a.json").read_text(encoding="utf-8"))["meta"]["scorer"]
    assert check["benchmark_check"]["status"] == "match"
    assert check["benchmark_check"]["benchmark_sha256"] == load_benchmark(bench).sha256
    assert "benchmark_mismatch_override" not in check


def test_records_from_another_benchmark_are_refused(tmp_path, capsys):
    """The reported hole: a Korean run scored against benchmarks_en."""
    kr = _bench(tmp_path, "benchmarks")
    en = _bench(tmp_path, "benchmarks_en",
                [dict(c, question="in English") for c in CASES])
    runs = _run_dir(tmp_path, _records(kr))
    out = tmp_path / "eval"
    assert main(["--runs", str(runs), "--benchmark", str(en), "--out", str(out),
                 "--no-sql-exec"]) == 2
    err = capsys.readouterr().err
    assert "refusing to score" in err and "benchmarks" in err
    assert not list(out.glob("eval_*.json")), "nothing is written when the scorer refuses"


def test_a_mixed_record_directory_is_refused(tmp_path):
    """A directory holding records from two arms is not one run."""
    kr = _bench(tmp_path, "benchmarks")
    en = _bench(tmp_path, "benchmarks_en", [dict(c, question="in English") for c in CASES])
    runs = _run_dir(tmp_path, _records(kr, case_ids=["c1"]) + _records(en, case_ids=["c2"]))
    assert main(["--runs", str(runs), "--benchmark", str(kr), "--out", str(tmp_path / "eval"),
                 "--no-sql-exec"]) == 2


def test_the_override_flag_scores_and_records_both_hashes(tmp_path):
    kr = _bench(tmp_path, "benchmarks")
    en = _bench(tmp_path, "benchmarks_en", [dict(c, question="in English") for c in CASES])
    runs = _run_dir(tmp_path, _records(kr))
    out = tmp_path / "eval"
    assert main(["--runs", str(runs), "--benchmark", str(en), "--out", str(out),
                 "--no-sql-exec", "--allow-benchmark-mismatch"]) == 0
    scorer = json.loads((out / "eval_model_a.json").read_text(encoding="utf-8"))["meta"]["scorer"]
    assert scorer["benchmark_mismatch_override"]["flag"] == "--allow-benchmark-mismatch"
    assert scorer["benchmark_check"]["status"] == "mismatch"
    assert scorer["benchmark_check"]["benchmark_sha256"] == load_benchmark(en).sha256
    recorded = scorer["benchmark_check"]["records"]
    assert [r["benchmark_dir"] for r in recorded] == ["benchmarks"]
    assert recorded[0]["benchmark_sha256"] == load_benchmark(kr).sha256


def test_records_without_the_digest_are_scored_with_a_warning(tmp_path, capsys):
    """Records from before C1-012 carry no hash; there is nothing to compare."""
    bench = _bench(tmp_path)
    runs = _run_dir(tmp_path, [record([], case_id="c1", run_id="model_a"),
                               record([], case_id="c2", run_id="model_a")])
    out = tmp_path / "eval"
    assert main(["--runs", str(runs), "--benchmark", str(bench), "--out", str(out),
                 "--no-sql-exec"]) == 0
    assert "cannot be verified" in capsys.readouterr().err
    scorer = json.loads((out / "eval_model_a.json").read_text(encoding="utf-8"))["meta"]["scorer"]
    assert scorer["benchmark_check"]["status"] == "not_recorded"
