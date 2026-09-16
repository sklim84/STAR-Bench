# Audit fixes: the multi-turn rebuild (WS-E)

Branch `audit-fixes` in `STAR-Bench`. Scope: register step 9 (L6-034, L3-018, L3-004,
L2-004 … L2-018, C2-008, C1-010) and decision D03, on the platform as WS-A fixed it.

Files owned by this stream: `benchmarks_multiturn/`, `benchmarks_multiturn_en/`,
`_experiments/scripts/data_fixes/multiturn/`, `_experiments/scripts/build_multiturn_en.py`.

## Commits

| commit | content |
|---|---|
| `1ba3a32` (data) | the 50 scenarios rebuilt on real HOFINET entities, generated from a scenario spec, with every injected result the output of executing that turn's gold call |
| `1ba3a32` (prose) | the narratives read their figures out of the tool results; Korean particles, dates and money rendered by the builder; `verify.py` |
| `304f365` | READMEs, `build_multiturn_en.py` retired, refreshed gold self-test reports |
| `5f45ee5` | total ordering in the listing queries so the build is reproducible; `verify.py` re-executes every gold call |

(The first two are one commit each in the log; the table splits them by subject.)

## What the file is now

50 scenarios, 219 turns, the same counts as before. Nothing in it is written by
hand: `_experiments/scripts/data_fixes/multiturn/scenarios*.py` holds the specs and
`build.py` executes them. Running the build again reproduces both files byte for
byte (checked over three runs).

```bash
python -m _experiments.scripts.data_fixes.multiturn.build
python -m _experiments.scripts.data_fixes.multiturn.verify
```

## Register ids

| id | fix | verification |
|---|---|---|
| L3-018, D03 | Every account, institution, date, amount and channel exists in HOFINET and carries the story its scenario tells. 36 distinct gold accounts, 9 institutions, all real. A `predict_fraud` turn takes the six features of a transaction that is really in the data, read from the previous turn's own result, so the amount, the time slot and the fund type are a combination HOFINET contains. | `verify.py` checks every 16-digit id against the HOFINET account set and every institution against the sender and receiver sets |
| L3-004, D03 | Every `tool_result` is the output of executing that turn's gold call on the fixed platform, with the platform's English result keys. | `verify.py::check_results_are_live` re-executes all 200 gold calls and compares them with what is stored |
| L2-004, L2-005, L2-006, L2-011 | The injected evidence cannot contradict HOFINET, because it is HOFINET: no fraud type 6, no type-7 row outside time slot 21, no amount outside the 48 values, no old crime name, no argument that is not a schema property. A scenario's `fraud_type` is the type its own evidence carries. | `verify.py` (schema properties, old names), the gold self-test, the gold-call harness |
| L2-007 | Channel names come from `analyze_channel_risk`, so `media_type` and `channel_name` always agree. | tool output |
| L2-008 | Institution ids are taken from the tool results or pinned to the HOFINET ranges. | `verify.py` |
| L2-009, Contract 1 | `sql_contains` is gone. Every `query_transactions` turn carries `sql_conditions` (`{column, op, value}` on English column names) plus `sql_valid`, and an executable `reference_sql`. | gold self-test: the 36 turns that carried no executable SQL now carry one, and the 72 blocking problems they raised are 0 |
| L2-010 | The user turns are new prose. Korean particles are chosen by the builder from the sound the value ends on (`{acc:은는}`, `{w:으로로}`), so the class of error the 4/28 bulk substitution left behind cannot recur. | reading; the particle table is in `build.py` |
| L2-012, M14-2 | `generate_str` gold carries `summary`, `fraud_type` (the §VI enum the tool accepts) and `tools_used`. `fraud_probability` is gone from every gold and from every `context_ref`: the tools return an uncalibrated risk score, not a probability. The summaries state only figures their own turns produced. | gold self-test: the 12 references into `generate_str.fraud_probability` are gone |
| L2-013 | 46 `context_ref`s (21 onto `account_id`, 15 onto `amount`, 6 onto the SQL, 4 onto `bank_id`), each resolved against the source turn's real result at build time, each pointing at an argument the gold call of its own turn takes. SQL references use `to_param: "sql"`, which the scorer reads as "this value has to appear as a token in the model's SQL". | build fails on an unresolvable reference; `verify.py` re-checks; gold self-test reports no `context_reason` |
| L2-014 | No `tool_calls_alt` anywhere. Every turn has exactly one gold tool (D11). | absence |
| L2-015, D19 | 14 clarification turns, one per `missing_parameter` scenario, each because a schema-required argument (or an unresolved reference to one) is missing: `summary`, `account_id`, `bank_id`, `direction`, `pattern_type`, `mode`, `fraud_type`, `keyword`, `time_slot`, the four `compare_periods` dates, and a bare "that account". No turn asks back for something an earlier result already settled. | reading, per-turn `note` |
| L2-016 | FIU lookups use English keywords that select catalog rows (`night`, `split`, `balance certificate`, `bulk`, `third party`); the glossary uses `Layering` and `Structuring`. The scorer compares the rows a value selects, so case and wording variants pass. | gold self-test: the 7 "gold value returns no catalog rows" advisories are gone |
| L2-017, L2-018, M12, M13 | English type names are the platform's own (`Sudden Change in Transaction Pattern` and the rest). `fraud_type_name` is the HOFINET name of the code, so no scenario is labelled "기타". | `spec.py` tables |
| C2-008 (data half) | Every `query_transactions` turn stores its executable statement twice over: `tool_calls[0].reference_sql`, which the scorer's gold renderer reads, and `reference_calls.query_transactions.sql`, the shape the platform's gold-call harness reads. **The runner half is not done; see below.** | gold-call harness executes all 38 |
| C1-010 | `build_multiturn_en.py` is retired. Both files come out of one pass over one spec, keyed by scenario id and turn number. | `verify.py::check_parity`: same ids in the same order, same turn counts, byte-identical tool interface, and no turn left untranslated |
| L6-034 | The M1 … M15 draft is subsumed: the rebuild removes the defects at their source rather than patching the 362 rows. The three semantic items the rebuild does not settle by construction (the §VI classification of the STR gold, the FIU and glossary values, the removal of alternatives) are applied above. | the checks in this table |

## Verification

| check | result |
|---|---|
| `gold_selftest --benchmark benchmarks_multiturn` | oracle **50/50 perfect**, e2e **50/50 perfect**, 0 defects, 0 advisories (was 10/50, 40 defects) |
| `gold_selftest --benchmark benchmarks_multiturn_en` | oracle **50/50**, e2e **50/50**, 0 defects, 0 advisories |
| `scripts/gold_calls.py` (platform, `STAR_BENCH_GOLD_DIRS`) | 200 gold calls per directory: **199 ok, 1 empty, 0 error, 0 skipped**, both languages |
| `data_fixes.multiturn.verify` | no problems: parity, schema properties, required arguments pinned, reference SQL present, every context reference resolved, every entity real, every stored result still live, no result large enough to be truncated |
| build reproducibility | three consecutive builds, identical sha256 |

The one empty result is `detect_aml_patterns(pattern_type="layering")` in
`mt_str_020`, and it is the point of that turn: HOFINET's transfer graph is
acyclic and its longest chain of consecutive fraud transfers is two, so the tool
answers with that fact. The scenario's STR then rests on the account's own
transactions. It is the only place in the file where a tool returns no rows.

## Turn and type distribution, for the paper

The manuscript says 3 to 6 turns. The data is **4 to 6**: 4 turns in 32
scenarios, 5 in 17, 6 in 1, 219 turns over 50 scenarios (mean 4.38).

| block | value |
|---|---|
| sub-category | `base` 14, `missing_parameter` 14, `long_context` 22 |
| turn kind | 200 tool-call turns, 14 clarification turns, 5 no-tool answers |
| `context_ref` turns | 46 |
| HOFINET fraud type | 1: 14, 2: 10, 3: 10, 4: 8, 5: 3, 7: 5 |
| tools | all 23 appear; `generate_str` 45, `query_transactions` 38, `predict_fraud` 17, `score_account_risk` 12, `get_account_profile` 10, `analyze_network` 8, `get_institution_report` 8, `detect_ctr_candidates` 7, `detect_monitoring_alerts` 6, `detect_smurfing_network` 6, `lookup_fiu_reference_types` 6, `detect_aml_patterns` 5, `get_fraud_type_summary` 5, `get_receiving_account_profile` 5, `compare_periods` 4, `get_statistics` 4, `analyze_channel_risk` 3, `analyze_cross_institution_flow` 2, `detect_dormant_reactivation` 2, `get_aml_glossary` 2, `get_trend_analysis` 2, `validate_str_fields` 2, `rank_risky_transactions` 1 |

STR narrative coverage of the gold summaries, recomputed with the patterns
`RQ_str_generation_quality.py` uses, over the 45 scenarios that end in a report:
**0.932** overall (was 0.704). Subjects 0.978, date 0.889, place 0.867,
instrument 1.000, method 1.000, grounds 1.000, 5W1H summary 0.789. Date and place
are below 1.0 in the scenarios whose tools carry neither a date range nor an
institution (`get_receiving_account_profile`, `detect_smurfing_network`,
`detect_dormant_reactivation`, `get_fraud_type_summary`), which is a property of
the tool set, not of the writing.

## What the manuscript has to state

1. **The turn range is 4 to 6**, not 3 to 6, and the mean is 4.38.
2. **The oracle results are real tool outputs**, not expert-written mocks. The
   earlier text described them as ground-truth tool output while 82% of them
   shared no key with what the tool returns; that sentence is now true and can be
   said plainly, with the build script as the evidence.
3. **The entities are real HOFINET entities**, so the end-to-end setting is a
   fair comparison: a model that calls the tools itself gets the same values the
   oracle setting injects.
4. **`fraud_probability` is not part of any gold.** Anything in the paper that
   reports a context-carry of a probability into `generate_str` has to go; the
   46 context references carry account ids, institution ids, media types and
   amounts.
5. **The example table** (the `detect_ctr_candidates.account_id` example among
   others) has to be redrawn from the new file; no gold argument outside a tool
   schema survives.
6. **STR narrative coverage is 0.932**, computed over gold summaries that state
   only figures their own tool results carry.
7. **HOFINET limits the type mix.** Type 4 exists in 5 accounts and type 7 in 3,
   so a few scenarios share an account with another scenario that approaches it
   through different tools. The type distribution above follows the data rather
   than a design target, and the paper should say so.
8. **One scenario ends on an empty tool result on purpose** (`mt_str_020`,
   layering), because HOFINET's transfer graph is acyclic. That is worth a
   sentence next to D06.

## Not done here, and why

| id | reason |
|---|---|
| C2-008 (runner half) | `runner/loop.py::_oracle_turns` still injects the gold `arguments` block verbatim, so the 38 SQL turns show the assistant calling `query_transactions` with `sql_conditions` and `sql_valid` instead of a statement. The data carries the statement; the runner has to prefer it. WS-C owns that file. The change is in "What the other streams must do" below. |
| D04, D22 | The STR quality checker and the blind evaluation come after the rerun. The gold summaries are the reference text they will use. |
| the rerun | Step 11. Nothing here needs a GPU. |

## What the other streams must do

- **WS-C (runners).** One change in `runner/loop.py::_oracle_turns`: when a gold
  call carries `reference_sql`, inject `{"sql": <that statement>}` as the
  assistant's arguments, and otherwise drop the evaluator-only keys
  (`sql_conditions`, `sql_valid`, `hops_min`, `hops_max`, `result_contains`,
  `result_row_count_min`, `result_row_count_max`) before injecting. Without it
  C2-008 is only half fixed: the oracle history keeps showing a tool call made
  out of evaluator meta keys, which is the shape Hermes-3-8B and gpt-oss-20B
  copied in the 2026 run. Nothing else in the runner has to change; the largest
  injected result is 7,830 characters, well inside the 4,000-token budget, so no
  multi-turn result is truncated.
- **WS-B (scoring).** The multi-turn gold now matches what the README asked for:
  `reference_sql` per query turn, schema-property gold keys, context references
  that resolve. `to_param` is `"sql"` on the 6 SQL references, which
  `_spec_index_for` already maps onto the SQL checks.
- **WS-F (pre-flight).** `python -m _experiments.scripts.data_fixes.multiturn.verify`
  belongs in the suite: it fails on a stale injected result, a broken reference,
  an invented entity or a KR/EN drift, and it prints the distribution the paper
  reports.
- **WS-D (single-turn).** Nothing shared. The two data streams touch different
  directories and different scripts.

## Scenario by scenario

`sub` is the sub-category, `ctx` the number of context references, and the last
column is why those entities carry that story. The same table, with the gold
arguments and the result keys per turn, is in
`_experiments/scripts/data_fixes/multiturn/rebuild_log.json`.

| id | sub | HOFINET type | turns | ctx | tools | entities and why |
|---|---|---|---|---|---|---|
| `mt_str_001` | base | 1 sudden pattern change | 4 | 1 | query_transactions -> predict_fraud -> analyze_network -> generate_str | 9000000000037352 carries 161 type-1 (sudden pattern change) transactions, the most of any account in HOFINET, and is a sender at institution 157. |
| `mt_str_002` | missing_parameter | 4 concurrent multiple | 5 | 1 | clarify -> query_transactions -> predict_fraud -> detect_ctr_candidates -> generate_str | 9000000004236284 has 431 type-4 (concurrent multiple transactions) rows, the most in HOFINET, and its 2024 activity is large enough for a CTR high-value check. |
| `mt_str_003` | long_context | 3 split | 4 | 2 | query_transactions -> get_account_profile -> score_account_risk -> generate_str | Institution 159 is the top sender bank for type-3 (split) transactions (1,464 of 2,073); the grouped query really returns 9000000004390593 first. |
| `mt_str_004` | base | 3 split | 4 | 0 | query_transactions -> detect_smurfing_network -> analyze_network -> generate_str | 9000000000039222 sends to 856 distinct accounts with 83 type-3 rows, so the outbound smurfing scan really returns it. |
| `mt_str_005` | base | 5 same-day withdrawal | 4 | 1 | get_fraud_type_summary -> query_transactions -> predict_fraud -> generate_str | Type 5 has only 243 rows in HOFINET; 9000000000041932 holds 75 of them, the most of any account. |
| `mt_str_006` | base | 7 night bulk | 4 | 0 | lookup_fiu_reference_types -> query_transactions -> score_account_risk -> generate_str | 9000000000038845 holds 23 of the 35 type-7 rows in HOFINET; every one of them is in time slot 21. |
| `mt_str_007` | base | 1 sudden pattern change | 4 | 1 | analyze_channel_risk -> query_transactions -> predict_fraud -> generate_str | PC Banking (media_type 1) is the highest-fraud-ratio channel in 2024; the largest type-1 PC-banking transaction is account 9000000000020857's 300,000,000 KRW transfer. |
| `mt_str_008` | base | 2 new counterparty | 4 | 1 | get_statistics -> rank_risky_transactions -> predict_fraud -> generate_str | The deterministic ranking puts account 9000000004241908's 6,000,000 KRW transfer first; that account's labelled fraud is dominated by type 2 (21 of 41 rows). |
| `mt_str_009` | base | 2 new counterparty | 4 | 1 | analyze_cross_institution_flow -> query_transactions -> predict_fraud -> generate_str | In 2024Q4 the 151 to 149 leg has the highest fraud ratio (14.29%) among legs with at least ten transactions; its 2024 fraud rows are all type 2. |
| `mt_str_010` | base | 2 new counterparty | 4 | 0 | detect_dormant_reactivation -> get_account_profile -> detect_ctr_candidates -> generate_str | With the default thresholds the reactivation scan really returns 9000000000023022 first (978 dormant days, a 5,000,000 KRW reactivation); its one labelled transaction is type 2. |
| `mt_str_011` | base | 3 split | 4 | 0 | detect_monitoring_alerts -> query_transactions -> score_account_risk -> generate_str | R003 (repeated identical amounts) really flags 9000000000041188 first in 2024Q4: 202 transfers of exactly 4,000,000 KRW; the account's labelled fraud is type 3. |
| `mt_str_012` | base | 7 night bulk | 4 | 0 | get_trend_analysis -> compare_periods -> query_transactions -> generate_str | 9000000004242392 holds 7 type-7 rows and 2,626 of its transactions are in the 21 slot, so a night-time reading of this account is grounded. |
| `mt_str_013` | base | 1 sudden pattern change | 4 | 0 | get_receiving_account_profile -> detect_smurfing_network -> detect_aml_patterns -> generate_str | 9000000004371903 receives from 123 distinct senders with 103 flagged inbound transactions, the highest fraud count among receiving accounts. |
| `mt_str_014` | missing_parameter | 1 sudden pattern change | 4 | 1 | clarify -> query_transactions -> predict_fraud -> generate_str | 9000000000019720 carries 20 type-1 rows at institution 134, enough for a listing and a prediction without being one of the very large accounts. |
| `mt_str_015` | missing_parameter | 4 concurrent multiple | 5 | 1 | clarify -> query_transactions -> predict_fraud -> lookup_fiu_reference_types -> generate_str | 9000000004242077 has 91 type-4 rows, 62 of them in 2024, so the 2024 listing is not empty. |
| `mt_str_016` | missing_parameter | 2 new counterparty | 5 | 0 | get_institution_report -> clarify -> compare_periods -> query_transactions -> generate_str | Institution 151 sends the type-2 accounts 9000000000027664 and 9000000004239253, so its report and a 2024 second-half listing both carry new-counterparty fraud. |
| `mt_str_017` | missing_parameter | 3 split | 4 | 0 | clarify -> detect_smurfing_network -> detect_aml_patterns -> generate_str | 9000000004424162 receives 361 transfers from six senders, 44 of them labelled type 3, which is the split-transaction collection pattern the scenario describes. |
| `mt_str_018` | missing_parameter | 1 sudden pattern change | 4 | 0 | clarify -> get_institution_report -> query_transactions -> generate_str | Institution 134 has 86 type-1 rows in 2024, so its report and the 2024 listing both support the sudden-pattern-change reading. |
| `mt_str_019` | missing_parameter | 4 concurrent multiple | 5 | 0 | get_statistics -> clarify -> get_fraud_type_summary -> query_transactions -> generate_str | Institution 147 holds 812 of the 929 type-4 rows, so the type summary really points at it. |
| `mt_str_020` | missing_parameter | 1 sudden pattern change | 5 | 0 | get_aml_glossary -> clarify -> detect_aml_patterns -> query_transactions -> generate_str | 9000000004235447 has 19 type-1 rows at institution 134. The layering scan is kept because its documented empty answer is the point of the turn: HOFINET's transfer graph is acyclic and its longest fraud chain is two transfers. |
| `mt_str_021` | missing_parameter | 3 split | 4 | 1 | clarify -> detect_ctr_candidates -> score_account_risk -> generate_str | The 2023 structuring scan really returns 9000000004243626 first: 93 same-day transfers totalling 103,870,000 KRW with a 5,000,000 KRW maximum, which is the structuring shape. |
| `mt_str_022` | missing_parameter | 2 new counterparty | 4 | 0 | clarify -> compare_periods -> query_transactions -> generate_str | 2024 has 1,424 type-2 rows in the second half alone, so the year comparison and the listing are both grounded. |
| `mt_str_023` | missing_parameter | 5 same-day withdrawal | 5 | 0 | clarify -> lookup_fiu_reference_types -> query_transactions -> validate_str_fields -> generate_str | 9000000004387158 holds 66 of the 243 type-5 rows, and the balance-certificate entry is the FIU reference type for the same-day withdrawal pattern. |
| `mt_str_024` | missing_parameter | 3 split | 5 | 1 | clarify -> get_account_profile -> get_receiving_account_profile -> analyze_network -> generate_str | 9000000000042369 has 40 type-3 rows and 806 distinct receivers, so its profile really names a top counterparty to follow. |
| `mt_str_025` | missing_parameter | 2 new counterparty | 5 | 1 | clarify -> query_transactions -> predict_fraud -> score_account_risk -> no tool | 9000000000019227 has 40 transactions, none labelled, a maximum of 300,000 KRW and a model score of 0.0, so the correct conclusion is that no STR is warranted. |
| `mt_str_026` | missing_parameter | 4 concurrent multiple | 5 | 1 | clarify -> predict_fraud -> query_transactions -> get_account_profile -> generate_str | The six features are those of a real transaction: 9000000004390593's 90,000,000 KRW type-4 transfer on 2022-07-22 from institution 159 to 155 over internet banking. |
| `mt_str_027` | long_context | 1 sudden pattern change | 4 | 1 | get_institution_report -> query_transactions -> get_account_profile -> generate_str | Institution 157's 2024 type-1 rows really group to 9000000004242077 first (53 rows). |
| `mt_str_028` | long_context | 3 split | 4 | 2 | query_transactions -> get_receiving_account_profile -> detect_smurfing_network -> generate_str | 9000000004234041 has 47 type-3 rows and its busiest receiver is 9000000004289938 with 91 transfers, so the reference resolves inside the real result. |
| `mt_str_029` | long_context | 2 new counterparty | 4 | 1 | detect_monitoring_alerts -> query_transactions -> compare_periods -> generate_str | R005 really flags 9000000004236923 first (12 to 264 transactions between quarters); its labelled fraud is dominated by type 2. |
| `mt_str_030` | long_context | 1 sudden pattern change | 4 | 2 | detect_ctr_candidates -> analyze_network -> detect_aml_patterns -> generate_str | The 2024 high-value CTR scan really returns 9000000004242077's 500,000,000 KRW transfer first; that account carries 151 type-1 rows. |
| `mt_str_031` | long_context | 4 concurrent multiple | 4 | 2 | get_fraud_type_summary -> query_transactions -> score_account_risk -> generate_str | The type-4 summary really names institution 147 first (812 of 929 rows), and that institution's 2024 rows group to 9000000004236284 first. |
| `mt_str_032` | long_context | 1 sudden pattern change | 5 | 2 | get_trend_analysis -> analyze_channel_risk -> query_transactions -> predict_fraud -> generate_str | In December 2024 the riskiest channel is media type 6 (Other) and that month really has 17 type-1 rows on that channel. |
| `mt_str_033` | long_context | 3 split | 4 | 1 | get_statistics -> get_fraud_type_summary -> get_institution_report -> generate_str | Institution 159 sends 1,464 of the 2,073 type-3 rows, so the summary's top institution is the one whose report matters. |
| `mt_str_034` | long_context | 1 sudden pattern change | 4 | 1 | detect_dormant_reactivation -> get_account_profile -> detect_ctr_candidates -> generate_str | With a 100,000,000 KRW reactivation threshold the scan returns 9000000000028288 first (648 dormant days); the account carries a type-1 row. |
| `mt_str_035` | base | 7 night bulk | 4 | 1 | query_transactions -> predict_fraud -> score_account_risk -> no tool | 9000000000007575 has 40 transactions, none labelled, a maximum of 300,000 KRW and no night-slot activity, so the night-time bulk suspicion does not hold. |
| `mt_str_036` | long_context | 4 concurrent multiple | 4 | 1 | analyze_cross_institution_flow -> get_institution_report -> query_transactions -> generate_str | Over 2024 the 147 to 154 leg has the highest fraud ratio (30.57% of 157 transactions) among legs with 50 or more transactions, and its fraud is dominated by type 4. |
| `mt_str_037` | long_context | 2 new counterparty | 5 | 3 | analyze_channel_risk -> query_transactions -> get_account_profile -> analyze_network -> generate_str | PC Banking is the riskiest channel in 2024Q4 (1.495%) and its Q4 fraud is eight type-2 rows, so the chain resolves on real data. |
| `mt_str_038` | long_context | 2 new counterparty | 4 | 1 | get_institution_report -> query_transactions -> score_account_risk -> no tool | Institution 145's busiest 2024Q4 sender, 9000000000020983, has 69 transactions and no labelled fraud, so the correct conclusion is that no STR is warranted. |
| `mt_str_039` | long_context | 1 sudden pattern change | 4 | 1 | detect_monitoring_alerts -> query_transactions -> detect_ctr_candidates -> generate_str | R002 really flags 9000000000044046 first in 2024Q4 (164 transfers on 31 December); the account's labelled fraud is type 1. |
| `mt_str_040` | long_context | 5 same-day withdrawal | 5 | 1 | get_statistics -> get_fraud_type_summary -> query_transactions -> lookup_fiu_reference_types -> generate_str | Institution 159 sends 148 of the 243 type-5 rows and 59 of them fall in 2024, so the reference from the summary to the query lands on real rows. |
| `mt_str_041` | long_context | 4 concurrent multiple | 5 | 3 | query_transactions -> predict_fraud -> get_receiving_account_profile -> detect_smurfing_network -> generate_str | 9000000004236284 has 244 type-4 rows in 2024 and its busiest receiver is 9000000004376103 with 952 transfers. |
| `mt_str_042` | long_context | 2 new counterparty | 4 | 1 | detect_monitoring_alerts -> get_institution_report -> query_transactions -> generate_str | R004 flags 9000000004237509 first in 2024 with 84.62% of its transfers going to institution 156, and institution 156 receives 354 type-2 rows in 2024. |
| `mt_str_043` | long_context | 1 sudden pattern change | 5 | 1 | query_transactions -> predict_fraud -> analyze_network -> detect_aml_patterns -> generate_str | 9000000000038694 has 18 type-1 rows in 2024 and a real two-hop path to 9000000001279469 through 9000000000036484. |
| `mt_str_044` | base | 7 night bulk | 4 | 0 | get_account_profile -> predict_fraud -> detect_smurfing_network -> no tool | 9000000004232727 has 40 transactions of at most 100,000 KRW, no labelled fraud and a model score of 0.0, so the suspicion does not hold. |
| `mt_str_045` | long_context | 1 sudden pattern change | 5 | 3 | detect_monitoring_alerts -> get_account_profile -> score_account_risk -> get_institution_report -> generate_str | R001 as redefined (slots 21/0/3, 5,000,000 KRW and above) really flags 9000000004234408's 200,000,000 KRW transfer at slot 21 on 2024-12-10 first; the account carries 21 type-1 rows. |
| `mt_str_046` | long_context | 3 split | 4 | 1 | query_transactions -> predict_fraud -> validate_str_fields -> generate_str | 9000000004242511 has 43 type-3 rows in 2024, which is what the draft in the turn text reports. |
| `mt_str_047` | base | 4 concurrent multiple | 4 | 0 | query_transactions -> score_account_risk -> analyze_network -> no tool | 9000000000027378 has 40 transactions of at most 100,000 KRW spread over 24 counterparties with no labelled fraud, so the suspicion does not hold. |
| `mt_str_048` | long_context | 7 night bulk | 5 | 1 | lookup_fiu_reference_types -> query_transactions -> get_receiving_account_profile -> score_account_risk -> generate_str | 9000000004242392 holds 7 type-7 rows and 2,626 transactions in the 21 slot, and its type-7 rows all go to 9000000004421588. |
| `mt_str_049` | long_context | 3 split | 5 | 1 | detect_monitoring_alerts -> get_account_profile -> detect_ctr_candidates -> get_aml_glossary -> generate_str | R003 as redefined (the same amount of 2,000,000 KRW or more, three times or more) flags 9000000004390593 first: 2,126 transfers of exactly 4,000,000 KRW; the account carries 616 type-3 rows. |
| `mt_str_050` | long_context | 1 sudden pattern change | 6 | 1 | query_transactions -> predict_fraud -> analyze_network -> score_account_risk -> lookup_fiu_reference_types -> generate_str | 9000000000017766 has 24 type-1 rows at institution 134 and 288 counterparties, so every one of the five analysis turns returns data. |
