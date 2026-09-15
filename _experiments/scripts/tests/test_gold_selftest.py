"""The gold self-test must pass consistent gold and name the inconsistent gold."""

from __future__ import annotations

import json

from _experiments.scripts.scoring.gold import load_benchmark
from _experiments.scripts.scoring.gold_selftest import run_multiturn, run_single

GOOD = {"id": "good", "question": "q", "difficulty": "easy", "expected": {
    "primary_tool": "analyze_network", "tools_must_include": ["analyze_network"],
    "param_checks": {"analyze_network": {"account_id": 78432, "hops_min": 2}}}}

GOOD_SQL = {"id": "good_sql", "question": "q", "difficulty": "easy", "expected": {
    "primary_tool": "query_transactions", "tools_must_include": ["query_transactions"],
    "param_checks": {"query_transactions": {
        "sql_conditions": [{"column": "fraud_type", "op": "=", "value": 4}], "sql_valid": True}},
    "reference_calls": {"query_transactions": {"sql": "SELECT COUNT(*) AS n FROM hofinet WHERE fraud_type = 4"}}}}

NO_REFERENCE_SQL = {"id": "no_sql", "question": "q", "difficulty": "easy", "expected": {
    "primary_tool": "query_transactions", "tools_must_include": ["query_transactions"],
    "param_checks": {"query_transactions": {"sql_contains": ["134"], "sql_valid": True}}}}

BAD_KEY = {"id": "bad_key", "question": "q", "difficulty": "easy", "expected": {
    "primary_tool": "compare_periods", "tools_must_include": ["compare_periods"],
    "param_checks": {"compare_periods": {"period_a_start": 20240101}}}}

ABSTAIN = {"id": "abstain", "question": "q", "difficulty": "easy",
           "expected": {"primary_tool": "", "tools_must_include": []}}


def _benchmark(tmp_path, cases, name="cases_selftest.json"):
    (tmp_path / name).write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    return load_benchmark(tmp_path)


def test_consistent_gold_scores_perfect(ctx, tmp_path, sql_execution):
    cases = [GOOD, ABSTAIN] + ([GOOD_SQL] if sql_execution else [])
    report = run_single(_benchmark(tmp_path, cases), ctx)
    assert report["n_perfect"] == report["n"] == len(cases), report["defects"]


def test_gold_without_reference_sql_is_reported(ctx, tmp_path):
    report = run_single(_benchmark(tmp_path, [NO_REFERENCE_SQL]), ctx)
    assert report["n_perfect"] == 0
    kinds = {p["kind"] for p in report["defects"][0]["render_problems"]}
    assert "needs_reference_sql" in kinds


def test_gold_key_outside_the_schema_is_reported(ctx, tmp_path):
    report = run_single(_benchmark(tmp_path, [BAD_KEY]), ctx)
    assert {p["kind"] for p in report["defects"][0]["render_problems"]} >= {"not_a_schema_property"}


def test_multiturn_context_reference_consistency_is_checked(ctx, tmp_path):
    consistent = {"id": "mt_ok", "sub_category": "long_context", "turns": [
        {"turn": 1, "content": "u", "tool_calls": [{"name": "detect_monitoring_alerts", "arguments": {"rule_id": "R001"}}],
         "tool_result": {"alerts": [{"account_id": 4242}]}},
        {"turn": 2, "content": "u", "tool_calls": [{"name": "analyze_network", "arguments": {"account_id": 4242}}],
         "context_ref": {"from_turn": 1, "key": "alerts[0].account_id", "to_param": "account_id"},
         "tool_result": {"connected_account_count": 2}}]}
    broken = json.loads(json.dumps(consistent))
    broken["id"] = "mt_broken"
    broken["turns"][1]["tool_calls"][0]["arguments"]["account_id"] = 9999  # not the value turn 1 produced
    report = run_multiturn(_benchmark(tmp_path, [consistent, broken]), ctx, "oracle")
    assert [r["case_id"] for r in report["defects"]] == ["mt_broken"]
