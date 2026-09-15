"""Counterexamples from the 2026-09 audit, pinned as single-turn scoring tests.

Each test names the register id it fixes. A failure here means the scorer went
back to a behaviour an auditor already showed to be wrong.
"""

from __future__ import annotations

import json

import pytest
from conftest import call, case, record

from _experiments.scripts.scoring import aggregate_single, load_benchmark, score_case

NET = case("analyze_network", checks={"analyze_network": {"account_id": 78432}}, case_id="net")
PF = case("predict_fraud", checks={"predict_fraud": {"time_slot": 0, "amount": 20000000, "fund_type": 4}}, case_id="pf")
NOCHECK = case("get_statistics", case_id="stats")
ABSTAIN = case("", case_id="irr")
CLARIFY = case("", case_id="clar", clarification=True)
CHAIN = case("query_transactions", tools=["query_transactions", "analyze_network"],
             order=["query_transactions", "analyze_network"],
             checks={"analyze_network": {"account_id": 5}}, case_id="chain")
QT = case("query_transactions", checks={"query_transactions": {
    "sql_conditions": [{"column": "fraud_type", "op": "=", "value": 4}], "sql_valid": True}}, case_id="qt")


# --- L4-004, L1-021: a trivial no-call policy must not win p, o or a ----------

def test_null_model_gets_no_precision_or_order_credit(ctx):
    r = score_case(NET, record([]), ctx)
    assert r["h"] == 0 and r["p"] is None and r["o"] is None
    assert r["a"] == 0.0 and r["error_type"] == "no_call"


def test_null_model_case_without_checks_has_a_not_applicable(ctx):
    r = score_case(NOCHECK, record([]), ctx)
    assert r["h"] == 0 and r["a"] is None, "a must stay undefined, never 1.0 for a model that called nothing"


def test_null_model_aggregate_over_the_real_benchmark(ctx):
    bench = load_benchmark("benchmarks")
    results = [score_case(c, record([], final_text=""), ctx, category=bench.category_of(cid))
               for cid, c in bench.cases.items()]
    agg = aggregate_single(results)
    assert agg["p_micro"]["mean"] is None and agg["p_micro"]["n_calls"] == 0
    assert agg["o"]["n"] == 0, "o is undefined when the ordered tools were never called"
    assert agg["h"]["mean"] == 0.0, "empty answers fail the abstention cases too (D19)"
    assert agg["a"]["n"] < agg["n_cases"], "a is averaged only over cases that have checks"


# --- L4-005, D01: over-calling is visible in the tool-set F1 ------------------

def test_call_every_tool_policy_keeps_h_but_loses_f1(ctx):
    calls = [call(name, {}) for name in sorted(ctx.schemas.names())]
    r = score_case(NET, record(calls), ctx)
    assert r["h"] == 1
    assert r["f1_tools"] < 0.1
    assert r["p"] < 0.05
    assert r["error_type"] == "param_error"


def test_extra_tool_call_is_labelled_over_call(ctx):
    calls = [call("analyze_network", {"account_id": 78432}), call("get_statistics", {})]
    r = score_case(NET, record(calls), ctx)
    assert r["h"] == 1 and r["a"] == 1.0
    assert r["extra_tools"] == ["get_statistics"] and r["error_type"] == "over_call"


# --- L4-008: every check of one tool is evaluated on the same call -----------

def test_checks_are_not_split_across_calls(ctx):
    calls = [call("predict_fraud", {"time_slot": 0, "amount": 1, "fund_type": 1}),
             call("predict_fraud", {"time_slot": 9, "amount": 20000000, "fund_type": 1}),
             call("predict_fraud", {"time_slot": 9, "amount": 1, "fund_type": 4})]
    r = score_case(PF, record(calls), ctx)
    assert r["a"] == pytest.approx(1 / 3), "no single call is right; the best call scores 1 of 3 checks"


def test_best_call_is_picked(ctx):
    calls = [call("predict_fraud", {"time_slot": 9}),
             call("predict_fraud", {"time_slot": 0, "amount": 20000000, "fund_type": 4})]
    assert score_case(PF, record(calls), ctx)["a"] == 1.0


# --- L4-015: SQL conditions, not substrings ---------------------------------

def test_select_1_plus_unrelated_valid_sql_does_not_pass(ctx):
    calls = [call("query_transactions", {"sql": "SELECT * FROM nowhere WHERE fraud_type = 4"},
                  result={"error": "Table or column not found."}),
             call("query_transactions", {"sql": "SELECT 1"}, result=[{"1": 1}])]
    r = score_case(QT, record(calls), ctx)
    assert r["a"] == 0.5, "conditions and validity must hold for the SAME call"


def test_single_digit_keyword_in_unrelated_sql_does_not_pass(ctx):
    sql = "SELECT * FROM hofinet WHERE date >= 20240101 AND fraud_type = 1 LIMIT 4"
    r = score_case(QT, record([call("query_transactions", {"sql": sql}, result=[])]), ctx)
    assert r["a"] == 0.5 and r["checks"][0]["results"][0]["passed"] is False


def test_matching_sql_passes_both_checks(ctx):
    sql = "SELECT COUNT(*) AS n FROM hofinet WHERE fraud_type = 4"
    r = score_case(QT, record([call("query_transactions", {"sql": sql}, result=[{"n": 3}])]), ctx)
    assert r["a"] == 1.0 and r["error_type"] == "correct"


def test_sql_valid_is_executed_when_the_run_did_not_record_a_result(ctx, sql_execution):
    if not sql_execution:
        pytest.skip("platform query database is not built here (set HOFINET_DUCKDB_PATH)")
    sql = "SELECT COUNT(*) AS n FROM hofinet WHERE fraud_type = 4"
    r = score_case(QT, record([call("query_transactions", {"sql": sql})]), ctx)
    assert r["a"] == 1.0
    broken = score_case(QT, record([call("query_transactions", {"sql": "SELECT * FROM missing WHERE fraud_type = 4"})]), ctx)
    assert broken["a"] == 0.5


def test_legacy_sql_contains_needs_whole_tokens_outside_comments(ctx):
    legacy = case("query_transactions", checks={"query_transactions": {"sql_contains": ["4"]}}, case_id="legacy")
    year_only = score_case(legacy, record([call("query_transactions", {"sql": "SELECT * FROM hofinet WHERE date >= 20240101"})]), ctx)
    in_comment = score_case(legacy, record([call("query_transactions", {"sql": "SELECT 1 -- fraud_type 4"})]), ctx)
    real = score_case(legacy, record([call("query_transactions", {"sql": "SELECT * FROM hofinet WHERE fraud_type = 4"})]), ctx)
    assert year_only["a"] == 0.0 and in_comment["a"] == 0.0 and real["a"] == 1.0


# --- L4-019: typed value comparison -----------------------------------------

@pytest.mark.parametrize("value,expected_score", [
    (78432, 1.0), ("78432", 1.0), (78432.0, 1.0), (78432.9, 0.0), ("78,432", 0.0), (None, 0.0),
])
def test_account_id_comparison(ctx, value, expected_score):
    assert score_case(NET, record([call("analyze_network", {"account_id": value})]), ctx)["a"] == expected_score


def test_true_is_not_one(ctx):
    c = case("predict_fraud", checks={"predict_fraud": {"fund_type": 1}}, case_id="bool")
    assert score_case(c, record([call("predict_fraud", {"fund_type": True})]), ctx)["a"] == 0.0


def test_enum_string_case_is_normalised(ctx):
    c = case("get_trend_analysis", checks={"get_trend_analysis": {"unit": "monthly"}}, case_id="enum")
    assert score_case(c, record([call("get_trend_analysis", {"unit": "Monthly"})]), ctx)["a"] == 1.0


def test_date_string_is_not_an_integer_date(ctx):
    c = case("compare_periods", checks={"compare_periods": {"period1_start": 20240101}}, case_id="date")
    assert score_case(c, record([call("compare_periods", {"period1_start": "2024-01-01"})]), ctx)["a"] == 0.0


# --- L1-017: schema defaults are filled before comparison --------------------

def test_omitted_argument_that_equals_the_schema_default_passes(ctx):
    c = case("detect_dormant_reactivation", checks={"detect_dormant_reactivation": {"dormant_days": 180}}, case_id="dorm")
    assert score_case(c, record([call("detect_dormant_reactivation", {})]), ctx)["a"] == 1.0
    assert score_case(c, record([call("detect_dormant_reactivation", {"dormant_days": 200})]), ctx)["a"] == 0.0


def test_non_default_gold_value_still_needs_the_argument(ctx):
    c = case("detect_dormant_reactivation", checks={"detect_dormant_reactivation": {"dormant_days": 365}}, case_id="dorm2")
    assert score_case(c, record([call("detect_dormant_reactivation", {})]), ctx)["a"] == 0.0


# --- L1-019: free-string catalog arguments compared by their result set ------

@pytest.mark.parametrize("gold,model,passes", [
    ("Non-face-to-face", "non-face-to-face", True),
    ("Non-face-to-face", " NON-FACE-TO-FACE ", True),
    ("others' names", "Others' Names", True),
    ("virtual asset", "virtual assets", False),
    ("structuring", "split", False),
])
def test_fiu_keyword_uses_the_catalog_rows(ctx, gold, model, passes):
    c = case("lookup_fiu_reference_types", checks={"lookup_fiu_reference_types": {"keyword": gold}}, case_id="fiu")
    r = score_case(c, record([call("lookup_fiu_reference_types", {"keyword": model})]), ctx)
    assert (r["a"] == 1.0) is passes


def test_glossary_term_uses_the_catalog_entry(ctx):
    c = case("get_aml_glossary", checks={"get_aml_glossary": {"term": "EDD"}}, case_id="gl")
    assert score_case(c, record([call("get_aml_glossary", {"term": "edd"})]), ctx)["a"] == 1.0
    assert score_case(c, record([call("get_aml_glossary", {"term": "SDD"})]), ctx)["a"] == 0.0


def test_gold_value_without_catalog_rows_falls_back_to_string_equality(ctx):
    c = case("get_aml_glossary", checks={"get_aml_glossary": {"term": "구조화"}}, case_id="gl_kr")
    r = score_case(c, record([call("get_aml_glossary", {"term": "구조화"})]), ctx)
    flags = r["checks"][0]["results"][0]
    assert r["a"] == 1.0 and flags.get("gold_empty_result") is True


# --- L4-020: malformed arguments never crash the scorer ---------------------

def test_list_arguments_are_a_failed_check_not_an_exception(ctx):
    r = score_case(NET, record([call("analyze_network", [{"account_id": 78432}])]), ctx)
    assert r["h"] == 1 and r["a"] == 0.0 and r["malformed_arg_calls"] == 1


def test_unparsable_argument_string_is_a_failed_check(ctx):
    tc, _ = call("analyze_network", None, raw="{account_id: 78432")
    tc["arguments"] = None
    tc["valid_json"] = False
    r = score_case(NET, record([(tc, None)]), ctx)
    assert r["a"] == 0.0 and r["malformed_arg_calls"] == 1


def test_non_numeric_hops_is_a_failed_check(ctx):
    c = case("analyze_network", checks={"analyze_network": {"account_id": 1, "hops_min": 2}}, case_id="hops")
    r = score_case(c, record([call("analyze_network", {"account_id": 1, "hops": "three"})]), ctx)
    assert r["a"] == 0.5


# --- L4-021: hallucinated parameters are judged against the schema -----------

def test_valid_optional_argument_is_not_hallucinated(ctx):
    r = score_case(NET, record([call("analyze_network", {"account_id": 78432, "hops": 2})]), ctx)
    assert r["hallucinated_param_count"] == 0 and r["error_type"] == "correct"


def test_argument_outside_the_schema_counts_as_hallucinated(ctx):
    r = score_case(NET, record([call("analyze_network", {"account_id": 78432, "depth": 9})]), ctx)
    assert r["hallucinated_param_count"] == 1


# --- L4-028: order by first occurrence, strict subsequence ------------------

def test_reordered_duplicates_do_not_score_full_order(ctx):
    calls = [call("analyze_network", {"account_id": 5}),
             call("query_transactions", {"sql": "SELECT 1"}),
             call("analyze_network", {"account_id": 5})]
    assert score_case(CHAIN, record(calls), ctx)["o"] == 0


def test_reversed_order_scores_zero_not_half(ctx):
    calls = [call("analyze_network", {"account_id": 5}), call("query_transactions", {"sql": "SELECT 1"})]
    r = score_case(CHAIN, record(calls), ctx)
    assert r["o"] == 0 and r["error_type"] == "order_error"


def test_correct_order_scores_one(ctx):
    calls = [call("query_transactions", {"sql": "SELECT 1"}), call("analyze_network", {"account_id": 5})]
    assert score_case(CHAIN, record(calls), ctx)["o"] == 1


def test_order_is_undefined_when_an_ordered_tool_is_missing(ctx):
    r = score_case(CHAIN, record([call("query_transactions", {"sql": "SELECT 1"})]), ctx)
    assert r["o"] is None and r["h"] == 0 and r["error_type"] == "missing_tool"


# --- L4-029: Harmony channel suffix is a parser artefact, not a tool ---------

def test_harmony_channel_suffix_is_stripped_and_flagged(ctx):
    calls = [call("analyze_network<|channel|>commentary", {"account_id": 78432})]
    r = score_case(NET, record(calls), ctx)
    assert r["h"] == 1 and r["p"] == 1.0 and r["a"] == 1.0
    assert r["called_tools"] == ["analyze_network"]
    assert r["parser_artifacts"] == ["analyze_network<|channel|>commentary"]


def test_recipient_prefix_is_stripped(ctx):
    r = score_case(NET, record([call("functions.analyze_network", {"account_id": 78432})]), ctx)
    assert r["h"] == 1 and r["parser_artifacts"]


# --- L4-009 and D19: abstention and clarification need an answer -------------

def test_abstention_needs_a_non_empty_answer(ctx):
    answered = score_case(ABSTAIN, record([], final_text="This is out of scope."), ctx)
    assert answered["abstain_ok"] is True and answered["h"] == 1
    empty = score_case(ABSTAIN, record([], final_text="   "), ctx)
    assert empty["abstain_ok"] is False and empty["h"] == 0 and empty["error_type"] == "parse_fail"


def test_clarification_with_empty_text_fails(ctx):
    ok = score_case(CLARIFY, record([], final_text="Which account should I look at?"), ctx)
    bad = score_case(CLARIFY, record([], final_text=""), ctx)
    assert ok["clarification_ok"] is True and ok["h"] == 1
    assert bad["clarification_ok"] is False and bad["error_type"] == "parse_fail"


@pytest.mark.parametrize("text", [
    '{"name": "analyze_network", "arguments": {"account_id": 1}}',
    '```json\n{"name": "get_statistics", "parameters": {}}\n```',
    '<tool_call>{"name": "get_statistics"}</tool_call>',
    'I will call [TOOL_CALLS] get_statistics',
])
def test_unparsed_tool_call_text_is_not_an_abstention(ctx, text):
    r = score_case(ABSTAIN, record([], final_text=text), ctx)
    assert r["abstain_ok"] is False and r["error_type"] == "parse_fail"


def test_calling_a_tool_on_an_abstention_case_is_over_call(ctx):
    r = score_case(ABSTAIN, record([call("get_statistics", {})]), ctx)
    assert r["h"] == 0 and r["p"] == 0.0 and r["f1_tools"] == 0.0 and r["error_type"] == "over_call"


# --- L4-022: error types name the actual failure ----------------------------

def test_error_type_labels(ctx):
    assert score_case(NET, record([]), ctx)["error_type"] == "no_call"
    assert score_case(NET, record([call("get_statistics", {})]), ctx)["error_type"] == "wrong_tool"
    assert score_case(CHAIN, record([call("query_transactions", {"sql": "SELECT 1"})]), ctx)["error_type"] == "missing_tool"
    assert score_case(NET, record([call("analyze_network", {"account_id": 1})]), ctx)["error_type"] == "param_error"
    assert score_case(NET, record([call("analyze_network", {"account_id": 78432})]), ctx)["error_type"] == "correct"


def test_system_error_and_length_stop(ctx):
    err = record([], error={"type": "connection_error", "message": "refused", "round": 0}, stop_reason="error")
    assert score_case(NET, err, ctx)["error_type"] == "system_error"
    long = record([], final_text="", stop_reason="length")
    assert score_case(NET, long, ctx)["error_type"] == "length_stop"


# --- D21: calls made before an error are still scored -----------------------

def test_calls_before_an_error_are_scored_with_the_error_flag(ctx):
    rec = record([[call("query_transactions", {"sql": "SELECT 1"})], []],
                 error={"type": "api_error", "message": "400 at round 2", "round": 1}, stop_reason="error")
    r = score_case(CHAIN, rec, ctx)
    assert r["r"] == 0.5 and r["error_flag"] is True and r["error_type"] == "system_error"


def test_a_complete_case_that_errored_afterwards_stays_correct(ctx):
    rec = record([[call("query_transactions", {"sql": "SELECT 1"}), call("analyze_network", {"account_id": 5})]],
                 error={"type": "api_error", "message": "400 on the summary round", "round": 1}, stop_reason="error")
    r = score_case(CHAIN, rec, ctx)
    assert r["h"] == 1 and r["error_flag"] is True and r["error_type"] == "correct"


# --- Contract 1 alternatives ------------------------------------------------

def test_alternative_tool_set_is_accepted(ctx):
    c = case("get_institution_report", checks={"get_institution_report": {"bank_id": 134}},
             alternatives=[{"tools_must_include": ["get_fraud_type_summary"],
                            "param_checks": {"get_fraud_type_summary": {"bank_id": 134, "fraud_type": 4}}}],
             case_id="alt")
    r = score_case(c, record([call("get_fraud_type_summary", {"bank_id": 134, "fraud_type": 4})]), ctx)
    assert r["h"] == 1 and r["a"] == 1.0 and r["matched"] == "alternative:0"


def test_abstain_alternative_is_accepted(ctx):
    c = case("get_aml_glossary", checks={"get_aml_glossary": {"term": "CDD"}},
             alternatives=[{"abstain": True}], case_id="amb")
    r = score_case(c, record([], final_text="CDD means customer due diligence."), ctx)
    assert r["h"] == 1 and r["matched"] == "alternative:0" and r["abstain_ok"] is True


# --- Contract 3 shape and aggregates ---------------------------------------

def test_aggregate_reports_n_for_every_metric(ctx):
    results = [
        score_case(NET, record([call("analyze_network", {"account_id": 78432})]), ctx),
        score_case(NOCHECK, record([call("get_statistics", {})]), ctx),
        score_case(ABSTAIN, record([], final_text="Out of scope."), ctx),
    ]
    agg = aggregate_single(results)
    assert agg["h"] == {"mean": 1.0, "n": 3}
    assert agg["a"]["n"] == 1, "only one of the three cases has parameter checks"
    assert agg["p_micro"] == {"mean": 1.0, "n_calls": 2, "n_cases_with_calls": 2}
    assert agg["abstain_ok"] == {"mean": 1.0, "n": 1}
    assert agg["error_types"]["correct"] == 3


def test_missing_record_is_visible(ctx):
    r = score_case(NET, None, ctx)
    assert r["missing_record"] is True and r["error_type"] == "system_error" and r["h"] == 0


def test_result_checks_read_english_keys(ctx):
    c = case("query_transactions", checks={"query_transactions": {"result_row_count_min": 2}}, case_id="rows")
    ok = score_case(c, record([call("query_transactions", {"sql": "SELECT 1"},
                                    result={"result": [1, 2, 3], "total_count": 3})]), ctx)
    korean = score_case(c, record([call("query_transactions", {"sql": "SELECT 1"},
                                        result=json.dumps({"결과": [1, 2, 3]}))]), ctx)
    assert ok["a"] == 1.0 and korean["a"] == 0.0


def test_a_retried_round_error_is_flagged_but_does_not_hide_the_real_failure(ctx):
    rec = record([call("analyze_network", {"account_id": 1})])
    rec["rounds"][0]["error"] = {"type": "api_error", "message": "400, retried", "round": 0}
    rec["rounds"][0]["attempts"] = 2
    r = score_case(NET, rec, ctx)
    assert r["error_flag"] is True and r["round_errors"] == 1 and r["error_type"] == "param_error"


def test_length_finish_reason_on_the_last_round_is_a_length_stop(ctx):
    rec = record([])
    rec["rounds"][0]["finish_reason"] = "length"
    assert score_case(NET, rec, ctx)["error_type"] == "length_stop"


def test_serialised_list_argument_is_accepted(ctx):
    c = case("generate_str", checks={"generate_str": {"aml_patterns": ["분할거래"]}}, case_id="str_list")
    r = score_case(c, record([call("generate_str", {"summary": "x", "aml_patterns": '["분할거래"]'})]), ctx)
    assert r["a"] == 1.0, "the tool layer parses a serialised array, so scoring does too"
