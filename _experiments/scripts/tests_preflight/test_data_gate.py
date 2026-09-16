"""Gate 3 finds the drift it exists to find, on a benchmark written for the test."""

from __future__ import annotations

import json

from _experiments.scripts.preflight import data
from _experiments.scripts.preflight.gate import Context

from .conftest import write_benchmark


def _ctx(root):
    return Context(root=root)


def test_a_clean_benchmark_passes_parity_and_the_duplicate_check(benchmark):
    ctx = _ctx(benchmark)
    assert data._parity(ctx).ok
    assert all(check.ok for check in data._duplicates(ctx))


def test_a_case_missing_from_the_english_side_is_named(benchmark, case_factory):
    path = benchmark / "benchmarks_en" / "cases_demo.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(cases[:1], ensure_ascii=False), encoding="utf-8")
    check = data._parity(_ctx(benchmark))
    assert not check.ok
    assert "case ids differ" in check.detail


def test_gold_that_differs_between_the_languages_is_named_by_id(benchmark):
    path = benchmark / "benchmarks_en" / "cases_demo.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    cases[1]["expected"]["tools_must_include"] = ["get_statistics"]
    path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    check = data._parity(_ctx(benchmark))
    assert not check.ok
    assert "st_a_002.expected" in check.detail


def test_two_cases_asking_the_same_question_fail_the_duplicate_check(benchmark, case_factory):
    for name in ("benchmarks", "benchmarks_en"):
        path = benchmark / name / "cases_demo.json"
        cases = json.loads(path.read_text(encoding="utf-8"))
        cases.append(case_factory("st_a_003", cases[0]["question"], "get_statistics"))
        path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    checks = {c.name: c for c in data._duplicates(_ctx(benchmark))}
    failed = checks["no duplicate question in benchmarks"]
    assert not failed.ok
    assert "st_a_001" in failed.detail and "st_a_003" in failed.detail


def test_a_user_turn_repeated_across_scenarios_is_not_a_duplicate(benchmark, scenario_factory):
    """"Score the first transaction in that result" means a different one each time."""
    for name in ("benchmarks_multiturn", "benchmarks_multiturn_en"):
        path = benchmark / name / "cases_str_workflow.json"
        scenarios = json.loads(path.read_text(encoding="utf-8"))
        repeated = scenario_factory("mt_str_002", [scenarios[0]["turns"][0]["content"], "another"])
        scenarios.append(repeated)
        path.write_text(json.dumps(scenarios, ensure_ascii=False), encoding="utf-8")
    checks = {c.name: c for c in data._duplicates(_ctx(benchmark))}
    assert checks["no duplicate scenario in benchmarks_multiturn"].ok


def test_two_identical_scenarios_do_fail(benchmark, scenario_factory):
    for name in ("benchmarks_multiturn", "benchmarks_multiturn_en"):
        path = benchmark / name / "cases_str_workflow.json"
        scenarios = json.loads(path.read_text(encoding="utf-8"))
        clone = dict(scenarios[0], id="mt_str_002")
        scenarios.append(clone)
        path.write_text(json.dumps(scenarios, ensure_ascii=False), encoding="utf-8")
    checks = {c.name: c for c in data._duplicates(_ctx(benchmark))}
    failed = checks["no duplicate scenario in benchmarks_multiturn"]
    assert not failed.ok
    assert "mt_str_002" in failed.detail


def test_the_counts_check_reads_the_pinned_file(benchmark, monkeypatch, tmp_path):
    counts = tmp_path / "counts.json"
    counts.write_text(json.dumps({"counts": {"benchmarks": {"cases": 2},
                                             "benchmarks_multiturn": {"cases": 1, "turns": 2}}}),
                      encoding="utf-8")
    monkeypatch.setattr(data, "COUNTS_PATH", counts)
    assert data._counts(_ctx(benchmark)).ok

    counts.write_text(json.dumps({"counts": {"benchmarks": {"cases": 3}}}), encoding="utf-8")
    check = data._counts(_ctx(benchmark))
    assert not check.ok
    assert "2 cases, expected 3" in check.detail


def test_the_real_counts_file_matches_the_real_benchmark():
    """The pinned counts are the ones on disk, so gate 3 means something."""
    ctx = Context()
    assert data._counts(ctx).ok, data._counts(ctx).detail
