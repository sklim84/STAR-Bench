"""The legacy checkpoint adapter, and the limits it must make visible."""

from __future__ import annotations

from conftest import case

from _experiments.scripts.scoring import score_case, score_scenario
from _experiments.scripts.scoring.legacy import multiturn_records, single_turn_record

NET = case("analyze_network", checks={"analyze_network": {"account_id": 78432}}, case_id="net")
ABSTAIN = case("", case_id="irr")

LEGACY_ROW = {"model": "google/gemma-4-31B-it", "category": "analyze_network", "case_id": "net",
              "id": "net", "difficulty": "easy", "primary_tool_hit": True, "tool_recall": 1.0,
              "tool_precision": 0.5, "param_accuracy": 1.0, "order_score": 1.0, "score": 0.95,
              "error_type": "other", "called_tools": ["analyze_network", "get_statistics"],
              "elapsed_sec": 11.11}


def test_single_turn_legacy_keeps_tool_selection(ctx):
    rec = single_turn_record(LEGACY_ROW, run_id="legacy")
    r = score_case(NET, rec, ctx)
    assert r["h"] == 1 and r["called_tools"] == ["analyze_network", "get_statistics"]
    assert r["p"] == 0.5 and r["extra_tools"] == ["get_statistics"]


def test_single_turn_legacy_cannot_score_parameters(ctx):
    r = score_case(NET, single_turn_record(LEGACY_ROW, run_id="legacy"), ctx)
    assert r["a"] is None and r["n_checks"] == 0, "legacy checkpoints stored no arguments"
    assert r["checks"][0]["results"][0]["applicable"] is False


def test_single_turn_legacy_scores_a_zero_when_the_tool_was_not_called(ctx):
    row = dict(LEGACY_ROW, called_tools=["get_statistics"])
    r = score_case(NET, single_turn_record(row, run_id="legacy"), ctx)
    assert r["a"] == 0.0 and r["error_type"] == "wrong_tool"


def test_single_turn_legacy_abstention_uses_the_pre_d19_rule(ctx):
    row = dict(LEGACY_ROW, case_id="irr", called_tools=[], error_type="correct")
    r = score_case(ABSTAIN, single_turn_record(row, run_id="legacy"), ctx)
    assert r["abstain_ok"] is True, "no final text was stored, so only 'no tool call' can be checked"


def test_legacy_system_error_becomes_a_run_error(ctx):
    row = dict(LEGACY_ROW, called_tools=[], error_type="connection_error")
    r = score_case(NET, single_turn_record(row, run_id="legacy"), ctx)
    assert r["error_flag"] is True and r["error_type"] == "system_error"


LEGACY_MT = {
    "id": "mt_x", "scenario": "s", "sub_category": "base", "setting": "real", "num_turns": 1,
    "turns": [{"turn": 1, "tool_hit": 1.0, "param_accuracy": 1.0, "score": 1.0,
               "actual_tool_calls": [{"name": "analyze_network", "arguments": {"account_id": 78432},
                                      "_id": "chatcmpl-tool-1"}],
               "executed_results": [{"name": "analyze_network", "arguments": {"account_id": 78432},
                                     "result": "{\"connected_account_count\": 8}"}]}],
}


def test_multiturn_legacy_keeps_arguments_and_results(ctx):
    records = multiturn_records(LEGACY_MT, run_id="legacy")
    assert len(records) == 1 and records[0]["setting"] == "e2e"
    scenario = {"id": "mt_x", "sub_category": "base", "turns": [
        {"turn": 1, "content": "u", "tool_calls": [{"name": "analyze_network", "arguments": {"account_id": 78432}}],
         "tool_result": {"connected_account_count": 8}}]}
    res = score_scenario(scenario, {1: records[0]}, ctx, setting="e2e")
    assert res["turns"][0]["a"] == 1.0 and res["c"] == 1
