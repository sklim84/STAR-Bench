# Audit fixes: scoring (WS-B)

Branch `audit-fixes`. Scope: register step 7 plus the scoring parts of D01, D02, D19 and D21, and
contracts 1 to 3 as defined in `_experiments/dataset_fix_20260915/impl/IMPLEMENTATION_SPEC.md`.

Files owned by this stream: `_experiments/scripts/evaluator.py`,
`_experiments/scripts/scoring/`, `_experiments/scripts/tests/`.

Metric definitions as implemented: `_experiments/scripts/scoring/README.md` (written to be copied
into the paper).

## Commits

| commit | content |
|---|---|
| `01044e9` | scoring library: records, schema, comparison, SQL, catalog, metrics, aggregates, `score_runs.py` |
| `09b71b2` | gold self-test |
| `9384005` | counterexample tests (single-turn, multi-turn, SQL) |
| `9f263af` | `evaluator.py` delegates to the library; legacy checkpoint adapter |
| `6f88ba6` | README with the metric definitions, sqlglot pin |
| `0699ead` | this file, gold self-test reports, CLI and self-test tests |
| `28d8551` | a retried round error no longer hides the real failure; `finish_reason` read |
| `53bdba7` | a list or object argument sent as a JSON string is parsed before comparison |
| `d4c693c` | warning when sqlglot is missing |
| `1423afe` | malformed gold is a failed check, not an exception |

## Register ids

| id | fix | where | verification |
|---|---|---|---|
| L4-020 | non-dict arguments and non-numeric values are failed checks, never exceptions | `scoring/compare.py` (`score_call`), `scoring/records.py` | `test_scoring_single.py::test_list_arguments_are_a_failed_check_not_an_exception`, `::test_unparsable_argument_string_is_a_failed_check`, `::test_non_numeric_hops_is_a_failed_check` |
| L4-029 | Harmony channel suffix and `functions.` prefix stripped for scoring, raw name reported as a parser artefact | `scoring/records.py` (`normalize_tool_name`) | `::test_harmony_channel_suffix_is_stripped_and_flagged`, `::test_recipient_prefix_is_stripped` |
| L1-019 | FIU `keyword` and glossary `term` compared by the catalog rows they select, imported from the platform through `_platform.py` | `scoring/catalog.py` | `::test_fiu_keyword_variants_that_select_the_same_rows_pass`, `::test_fiu_keyword_that_selects_other_rows_fails`, `::test_glossary_term_uses_the_catalog_entry`, `::test_gold_value_without_catalog_rows_falls_back_to_string_equality`. The tests read the catalog rather than hard-coding its content, so a catalog change in WS-A does not break them. Case and spacing variants pass; a value that selects different rows (a plural such as `virtual assets`, which the catalog's substring matching does not find) fails. |
| L1-017 | schema defaults filled before comparison, defaults read from the tool schema | `scoring/compare.py` (`fill_defaults`), `scoring/schema.py` | `::test_omitted_argument_that_equals_the_schema_default_passes`, `::test_non_default_gold_value_still_needs_the_argument` |
| L4-015 | `sql_conditions` matched against the WHERE and HAVING predicates with sqlglot 30.18.0 plus a conservative regex fallback; `sql_valid` from the recorded executed result or by read-only execution through the platform tool; one rule for single-turn and multi-turn | `scoring/sql.py` | `test_scoring_sql.py` (23 tests), `test_scoring_single.py::test_single_digit_keyword_in_unrelated_sql_does_not_pass`, `::test_select_1_plus_unrelated_valid_sql_does_not_pass`, `::test_sql_valid_is_executed_when_the_run_did_not_record_a_result` |
| L4-008 | all checks of one tool on the same call, best call chosen, two gold specs never share a call | `scoring/compare.py` (`match_specs`) | `::test_checks_are_not_split_across_calls`, `::test_best_call_is_picked`, `test_scoring_multiturn.py::test_two_gold_calls_of_one_tool_take_two_model_calls` |
| L4-018 | single-turn and multi-turn share one comparison module | `scoring/compare.py` used by `single.py` and `multiturn.py` | `test_scoring_multiturn.py::test_best_call_wins_in_multi_turn_too`, `::test_float_tolerance_is_gone` |
| L4-019 | typed comparison: no int truncation, booleans are not numbers, enum strings case-normalised | `scoring/compare.py` (`_scalar_equal`) | `::test_account_id_comparison` (6 cases), `::test_true_is_not_one`, `::test_enum_string_case_is_normalised`, `::test_date_string_is_not_an_integer_date` |
| L4-021 | hallucinated parameters counted against the tool schema properties | `scoring/compare.py` (`hallucinated_params`) | `::test_valid_optional_argument_is_not_hallucinated`, `::test_argument_outside_the_schema_counts_as_hallucinated` |
| L4-022 | error types `no_call`, `wrong_tool`, `missing_tool`, `over_call`, `param_error`, `order_error`, `parse_fail`, `system_error`, `length_stop`, `correct` | `scoring/single.py` (`_error_type`) | `::test_error_type_labels`, `::test_system_error_and_length_stop`, `::test_extra_tool_call_is_labelled_over_call`, `::test_calling_a_tool_on_an_abstention_case_is_over_call` |
| L4-027 | `context_hit` read only from the expected tool's call | `scoring/multiturn.py` (`_context_hit`) | `test_scoring_multiturn.py::test_context_hit_requires_the_expected_tool` |
| L4-028 | order judged by first occurrence, strict increase, undefined unless every ordered tool was called | `scoring/metrics.py` (`order_metric`) | `::test_reordered_duplicates_do_not_score_full_order`, `::test_reversed_order_scores_zero_not_half`, `::test_correct_order_scores_one`, `::test_order_is_undefined_when_an_ordered_tool_is_missing` |
| L3-022 | `result_*` checks read the English result keys (`result`, `total_count`); multi-turn `sql_valid` is evaluated | `scoring/compare.py` (`_check`, `_row_count`) | `::test_result_checks_read_english_keys`, `test_scoring_multiturn.py::test_multi_turn_sql_valid_is_evaluated` |
| L4-009, D19 | abstention and clarification succeed only with no tool call and a non-empty final text that is not an unparsed tool call | `scoring/records.py` (`answer_text_ok`, `is_unparsed_tool_call`), `scoring/single.py` | `::test_abstention_needs_a_non_empty_answer`, `::test_clarification_with_empty_text_fails`, `::test_unparsed_tool_call_text_is_not_an_abstention` (4 cases), `test_scoring_multiturn.py::test_clarification_turn_that_errored_is_not_a_success` |
| L1-021, L4-004, D02 | a averaged over cases with checks, p micro over calls with n, o only where an order is given and every ordered tool was called | `scoring/metrics.py`, `scoring/aggregate.py` | `::test_null_model_gets_no_precision_or_order_credit`, `::test_null_model_case_without_checks_has_a_not_applicable`, `::test_null_model_aggregate_over_the_real_benchmark`, `::test_aggregate_reports_n_for_every_metric` |
| L4-005, D01 | h is "every gold tool was called"; tool-set F1 stored next to it | `scoring/metrics.py` (`tool_metrics`) | `::test_call_every_tool_policy_keeps_h_but_loses_f1` |
| L4-001, D02 | c is "every turn has h = 1", one definition everywhere | `scoring/multiturn.py` (`score_scenario`) | `test_scoring_multiturn.py::test_scenario_complete_needs_every_turn_to_hit` |
| L4-007, D03 | end-to-end context references resolved from the run's own executed results; not applicable when the source turn produced nothing | `scoring/multiturn.py` (`_context_plan`) | `::test_e2e_context_is_scored_against_the_runs_own_result`, `::test_e2e_context_is_not_applicable_when_the_source_turn_produced_nothing`, `::test_e2e_sql_condition_value_follows_the_own_result` |
| D21 | calls made before an error are scored, `error_flag` set | `scoring/single.py`, `scoring/records.py` | `::test_calls_before_an_error_are_scored_with_the_error_flag`, `::test_a_complete_case_that_errored_afterwards_stays_correct` |
| L2-012, L4-011 | `generate_str.summary` and `fraud_probability` excluded from a; list arguments compared as set recall | `scoring/compare.py` (`EXCLUDED_ARGS`, `compare_value`) | `test_scoring_multiturn.py::test_paraphrased_summary_and_reordered_tool_list_score_full`, `::test_list_arguments_score_as_set_recall` |
| L4-016 | scores are not stored in run records; every eval is recomputed from records plus gold, and the eval file records which benchmark and tool schema it used | `scoring/score_runs.py` | `test_score_runs_cli.py::test_single_turn_run_produces_an_eval_file` (runner-side part belongs to WS-C) |
| Contract 1 | alternatives (tool set or abstain) scored as best of primary and alternatives; `expect_clarification`; `reference_calls.<tool>.sql` | `scoring/single.py` (`candidates`), `scoring/gold_selftest.py` | `::test_alternative_tool_set_is_accepted`, `::test_abstain_alternative_is_accepted`, `test_scoring_multiturn.py::test_alternative_gold_calls_are_accepted` |
| Contract 3 | every aggregate carries n; coverage of the run is part of the eval file | `scoring/aggregate.py`, `scoring/score_runs.py` | `test_score_runs_cli.py` (3 tests) |

### Not fixed here, and why

| id | reason |
|---|---|
| L4-002, L4-003, L6-010, L6-025, L6-050 | STR quality scoring is D04, a phase after the rerun, and needs the stored drafts. No STR work in this stream. |
| R1-S3, L4-026, D20 | Case-weighted reporting with per-tool n and bootstrap CIs is the analysis step. The scorer now stores per-case results and per-category n, which is what that step needs. |
| L4-025, L6-057 | Bootstrap ranking stability on h is the analysis step (step 11). |
| L4-012, L1-023, L1-012 and the other data ids | Data fixes (WS-D). The gold self-test names the cases; see below. |
| L4-016 (runner half), L4-017, L5-018, L5-019 | Runner work (WS-C): fresh output directories, run records with arguments, results, final text and errors. |

## Gold self-test on the current data

Run against the four benchmark directories; reports in
`_experiments/dataset_fix_20260915/impl/gold_selftest_*.json`, regenerated 2026-09-16 on the
rebuilt data. Pre-flight gate 4 runs the same self-test and fails when a committed report and a
fresh run disagree, so these numbers cannot go stale unnoticed again.

| benchmark | perfect | defects | advisories |
|---|---|---|---|
| `benchmarks` | 1258 / 1258 | 0 | 1 |
| `benchmarks_en` | 1258 / 1258 | 0 | 1 |
| `benchmarks_multiturn` (oracle and e2e) | 50 / 50 | 0 | 0 |
| `benchmarks_multiturn_en` (oracle and e2e) | 50 / 50 | 0 | 0 |

Every gold call renders and scores 1 against itself. The one advisory is `st_mtool_084`, whose gold
`analyze_network` call pins no `account_id`: the annotation is consistent, but the call cannot be
executed as written, so it is also the one call the platform gold-call harness skips (L1-016, open
in the data workstream).

The defects this table used to report (82 single-turn, 40 multi-turn) were the pre-rebuild data:
cases expecting `query_transactions` without `expected.reference_calls.query_transactions.sql`,
`period_a_*` arguments that are not `compare_periods` properties (L1-012), and context references
pointing at `generate_str.fraud_probability` (L2-013). WS-D and WS-E fixed all of them; the
requirements they came from are listed under "What the other streams must provide" below.

The same command re-runs against the data in the tree:

```
python -m _experiments.scripts.scoring.gold_selftest --benchmark benchmarks \
    --out _experiments/dataset_fix_20260915/impl/gold_selftest_benchmarks.json
```

## What the other streams must provide

WS-C (runners), so that the scorer can do its work:

- One JSONL record per case, and per turn for multi-turn, with `run_id`, `case_id`, `turn`,
  `setting`, `config` and `provenance` as Contract 2 spells them. The scorer copies `config` and
  `provenance` from the first record of a run into the eval file.
- Per round: `tool_calls` with `id`, `name`, `arguments_raw`, `arguments`, `source`, `valid_json`,
  and `executed` entries carrying `tool_call_id`, `name`, `arguments`, `result`, `error`. The
  `tool_call_id` link is what lets a check read the result of the call it is scoring; without ids the
  scorer falls back to position within the round.
- `final_text` on every record. D19 scoring of abstention and clarification needs it, and a run
  without it scores every such case as a failure.
- `finish_reason` per round and `stop_reason` per record, so `length_stop` is distinguishable from a
  model that simply stopped, and `error` with a type when the run failed, so calls made before the
  error keep their credit (D21).
- The tool names as the server returned them. The scorer strips serving artefacts itself and reports
  them; it cannot report what the runner has already rewritten.
- Fresh output directories. The scorer never reads old checkpoints, and `legacy.py` exists only for
  regression comparison.

WS-D and WS-E (data):

- `expected.reference_calls.<tool>.sql` for every case that expects `query_transactions`, and
  `sql_conditions` instead of `sql_contains`. Without it no gold call can be rendered and the gold
  self-test cannot clear the case.
- Gold argument keys must be schema properties (`period1_start` and not `period_a_start`), and a gold
  call should pin every required argument so it can be executed.
- Multi-turn `context_ref` must point at an argument the gold call of that turn actually takes, and
  its `key` must resolve inside the source turn's `tool_result`; `key` may be a path such as
  `alerts[0].account_id`. References to `generate_str.fraud_probability` are not scored.
- Free-string catalog values must select at least one catalog row, otherwise the check degrades to
  string equality.
- Alternatives go in `expected.alternatives`, either `{"abstain": true}` or a
  `{tools_must_include, param_checks}` block.

## Running the tests

```
python -m pytest _experiments/scripts/tests -q     # 112 tests
```

They need `sqlglot` and the platform checkout. The one test that executes SQL skips itself when the
platform query database is not built; point `HOFINET_DUCKDB_PATH` at a writable path to build a
private copy from the released Parquet.
