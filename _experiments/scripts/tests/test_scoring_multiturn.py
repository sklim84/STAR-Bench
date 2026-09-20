"""Multi-turn counterexamples: shared comparison, context references, scenario completion."""

from __future__ import annotations

import json

import pytest
from conftest import call, record, turn

from _experiments.scripts.scoring import aggregate_multiturn, score_scenario


def scenario(turns, *, case_id="mt_x", sub_category="base"):
    return {"id": case_id, "scenario": "s", "sub_category": sub_category, "turns": turns}


def turn_record(number, calls=(), **kw):
    return record(calls, case_id="mt_x", turn=number, setting=kw.pop("setting", "oracle"), **kw)


NET_TURN = turn(1, [{"name": "analyze_network", "arguments": {"account_id": 78432}}],
                tool_result={"account_id": 78432, "connected_account_count": 8})


# --- one comparison module for both settings ------------------------

def test_best_call_wins_in_multi_turn_too(ctx):
    calls = [call("analyze_network", {"account_id": 1}), call("analyze_network", {"account_id": 78432})]
    res = score_scenario(scenario([NET_TURN]), {1: turn_record(1, calls)}, ctx)
    assert res["turns"][0]["a"] == 1.0, "multi-turn used to score only the first matching call"


def test_float_tolerance_is_gone(ctx):
    calls = [call("analyze_network", {"account_id": 78432.009})]
    res = score_scenario(scenario([NET_TURN]), {1: turn_record(1, calls)}, ctx)
    assert res["turns"][0]["a"] == 0.0


def test_multi_turn_sql_valid_is_evaluated(ctx):
    gold = turn(1, [{"name": "query_transactions",
                     "arguments": {"sql_conditions": [{"column": "sender_acc", "op": "=", "value": 78432}],
                                   "sql_valid": True}}], tool_result={"total_count": 3})
    bad = call("query_transactions", {"sql": "78432"}, result={"error": "Only SELECT queries are allowed."})
    res = score_scenario(scenario([gold]), {1: turn_record(1, [bad])}, ctx)
    assert res["turns"][0]["a"] == 0.0, "a non-SQL string containing the number used to score 1.0"


def test_over_calling_shows_up_in_precision_and_f1(ctx):
    calls = [call(n, {"account_id": 78432}) for n in
             ["query_transactions", "predict_fraud", "analyze_network", "generate_str", "detect_aml_patterns"]]
    t = score_scenario(scenario([NET_TURN]), {1: turn_record(1, calls)}, ctx)["turns"][0]
    assert t["h"] == 1 and t["p"] == 0.2 and t["f1_tools"] < 0.4 and t["error_type"] == "over_call"


# --- / generate_str narrative and probability are not scored --

STR_TURN = turn(4, [{"name": "generate_str", "arguments": {
    "summary": "Account 78432 moved 49.5m KRW at night to three accounts.",
    "fraud_type": "분할거래",
    "fraud_probability": 0.91,
    "aml_patterns": ["분할거래"],
    "tools_used": ["query_transactions", "predict_fraud", "analyze_network"]}}],
    tool_result={"status": "created"})


def test_paraphrased_summary_and_reordered_tool_list_score_full(ctx):
    model = call("generate_str", {
        "summary": "A different but faithful narrative.",
        "fraud_type": "분할거래",
        "fraud_probability": 0.42,
        "aml_patterns": ["분할거래"],
        "tools_used": ["analyze_network", "query_transactions", "predict_fraud", "get_statistics"]})
    t = score_scenario(scenario([STR_TURN]), {4: turn_record(4, [model])}, ctx)["turns"][0]
    assert t["a"] == 1.0
    checked = {c["check"] for c in t["checks"][0]["results"]}
    assert "summary" not in checked and "fraud_probability" not in checked


def test_list_arguments_score_as_set_recall(ctx):
    gold = turn(4, [{"name": "generate_str", "arguments": {"aml_patterns": ["분할거래", "심야거래"]}}],
                tool_result={"status": "created"})
    model = call("generate_str", {"aml_patterns": ["분할거래"]})
    t = score_scenario(scenario([gold]), {4: turn_record(4, [model])}, ctx)["turns"][0]
    assert t["a"] == 0.5


# --- context_hit only from the expected tool's call -----------------

CTX_SCENARIO = scenario([
    turn(1, [{"name": "detect_monitoring_alerts", "arguments": {"rule_id": "R001"}}],
         tool_result={"alerts": [{"account_id": 33567, "rule": "R001"}]}),
    turn(2, [{"name": "analyze_network", "arguments": {"account_id": 33567}}],
         context_ref={"from_turn": 1, "key": "alerts[0].account_id", "to_param": "account_id"},
         tool_result={"connected_account_count": 4}),
], sub_category="long_context")


def test_context_hit_requires_the_expected_tool(ctx):
    right = {1: turn_record(1, [call("detect_monitoring_alerts", {"rule_id": "R001"})]),
             2: turn_record(2, [call("analyze_network", {"account_id": 33567})])}
    wrong_tool = {1: right[1], 2: turn_record(2, [call("score_account_risk", {"account_id": 33567})])}
    assert score_scenario(CTX_SCENARIO, right, ctx)["turns"][1]["context_hit"] is True
    assert score_scenario(CTX_SCENARIO, wrong_tool, ctx)["turns"][1]["context_hit"] is False


# --- end-to-end references come from the run's own results ----------

def _e2e_records(own_account, *, executed=True):
    result = {"alerts": [{"account_id": own_account, "rule": "R001"}]} if executed else None
    first = turn_record(1, [call("detect_monitoring_alerts", {"rule_id": "R001"},
                                 result=result if executed else None)], setting="e2e")
    second = turn_record(2, [call("analyze_network", {"account_id": own_account})], setting="e2e")
    return {1: first, 2: second}


def test_e2e_context_is_scored_against_the_runs_own_result(ctx):
    records = _e2e_records(99999)
    e2e = score_scenario(CTX_SCENARIO, records, ctx, setting="e2e")["turns"][1]
    oracle = score_scenario(CTX_SCENARIO, records, ctx, setting="oracle")["turns"][1]
    assert e2e["context_hit"] is True and e2e["a"] == 1.0, "carrying its own value forward is correct in E2E"
    assert oracle["context_hit"] is False and oracle["a"] == 0.0


def test_e2e_context_is_not_applicable_when_the_source_turn_produced_nothing(ctx):
    records = _e2e_records(99999, executed=False)
    t = score_scenario(CTX_SCENARIO, records, ctx, setting="e2e")["turns"][1]
    assert t["context_hit"] is None and t["a"] is None and t["context_reason"]


def test_e2e_sql_condition_value_follows_the_own_result(ctx):
    gold = scenario([
        turn(1, [{"name": "detect_monitoring_alerts", "arguments": {"rule_id": "R001"}}],
             tool_result={"alerts": [{"account_id": 33567}]}),
        turn(2, [{"name": "query_transactions", "arguments": {
            "sql_conditions": [{"column": "sender_acc", "op": "=", "value": 33567}], "sql_valid": True}}],
             context_ref={"from_turn": 1, "key": "alerts[0].account_id", "to_param": "sql"},
             tool_result={"total_count": 1}),
    ], sub_category="long_context")
    records = {
        1: turn_record(1, [call("detect_monitoring_alerts", {"rule_id": "R001"},
                                result={"alerts": [{"account_id": 41205}]})], setting="e2e"),
        2: turn_record(2, [call("query_transactions", {"sql": "SELECT * FROM hofinet WHERE sender_acc = 41205"},
                                result=[{"amount": 1}])], setting="e2e"),
    }
    t = score_scenario(gold, records, ctx, setting="e2e")["turns"][1]
    assert t["a"] == 1.0 and t["context_hit"] is True


# --- and : c is "every turn has h = 1" ----------------------------

def test_scenario_complete_needs_every_turn_to_hit(ctx):
    gold = scenario([NET_TURN, STR_TURN])
    all_hit = {1: turn_record(1, [call("analyze_network", {"account_id": 1})]),
               4: turn_record(4, [call("generate_str", {"fraud_type": "X"})])}
    one_missed = {1: turn_record(1, []), 4: all_hit[4]}
    assert score_scenario(gold, all_hit, ctx)["c"] == 1, "c is defined by h, not by a weighted score"
    assert score_scenario(gold, one_missed, ctx)["c"] == 0


def test_clarification_turn_that_errored_is_not_a_success(ctx):
    gold = scenario([turn(1, [], clarification=True)])
    errored = turn_record(1, [], final_text="", error={"type": "api_error", "message": "400"}, stop_reason="error")
    t = score_scenario(gold, {1: errored}, ctx)["turns"][0]
    assert t["clarification_ok"] is False and t["h"] == 0 and t["error_type"] == "system_error"


def test_clarification_turn_with_a_question_passes(ctx):
    gold = scenario([turn(1, [], clarification=True)])
    asked = turn_record(1, [], final_text="Which account should I analyse?")
    t = score_scenario(gold, {1: asked}, ctx)["turns"][0]
    assert t["clarification_ok"] is True and t["h"] == 1


def test_missing_turn_record_is_reported(ctx):
    gold = scenario([NET_TURN, STR_TURN])
    res = score_scenario(gold, {1: turn_record(1, [call("analyze_network", {"account_id": 78432})])}, ctx)
    assert res["missing_turns"] == [4] and res["c"] == 0
    assert res["turns"][1]["missing_record"] is True


def test_two_gold_calls_of_one_tool_take_two_model_calls(ctx):
    gold = turn(1, [{"name": "get_account_profile", "arguments": {"account_id": 1}},
                    {"name": "get_account_profile", "arguments": {"account_id": 2}}],
                tool_result={"ok": True})
    one_call = {1: turn_record(1, [call("get_account_profile", {"account_id": 1})])}
    two_calls = {1: turn_record(1, [call("get_account_profile", {"account_id": 1}),
                                    call("get_account_profile", {"account_id": 2})])}
    assert score_scenario(scenario([gold]), one_call, ctx)["turns"][0]["a"] == 0.5
    assert score_scenario(scenario([gold]), two_calls, ctx)["turns"][0]["a"] == 1.0


def test_alternative_gold_calls_are_accepted(ctx):
    gold = turn(1, [{"name": "get_institution_report", "arguments": {"bank_id": 134}}],
                alt=[{"name": "get_fraud_type_summary", "arguments": {"bank_id": 134, "fraud_type": 4}}],
                tool_result={"ok": True})
    rec = {1: turn_record(1, [call("get_fraud_type_summary", {"bank_id": 134, "fraud_type": 4})])}
    t = score_scenario(scenario([gold]), rec, ctx)["turns"][0]
    assert t["h"] == 1 and t["a"] == 1.0 and t["matched"] == "alternative:0"


def test_aggregate_carries_n_for_every_metric(ctx):
    gold = scenario([NET_TURN, STR_TURN])
    res = score_scenario(gold, {1: turn_record(1, [call("analyze_network", {"account_id": 78432})]),
                                4: turn_record(4, [call("generate_str", {"fraud_type": "분할거래",
                                                                          "aml_patterns": ["분할거래"],
                                                                          "tools_used": ["query_transactions"]})])}, ctx)
    agg = aggregate_multiturn([res])
    assert agg["n_scenarios"] == 1 and agg["n_turns"] == 2
    assert agg["c"] == {"mean": 1.0, "n": 1}
    assert agg["h"]["n"] == 2 and agg["a"]["n"] == 2
    assert agg["context_accuracy"] == {"mean": None, "n": 0}
    assert "base" in agg["by_sub_category"]
