# WS-D report: single-turn benchmark data (register step 8)

Branch `audit-fixes`, repository `STAR-Bench`. Every change to `benchmarks/` and
`benchmarks_en/` was produced by a committed pass in `_experiments/scripts/data_fixes/`;
`run_all.py --from 574c077` replays the whole sequence from the pre-audit snapshot and
reproduces the committed files byte for byte. The passes wrote 5,831 logged changes over
1,258 distinct case ids, each with the case id, language, field, register issue, reason and
the value before and after (`_experiments/scripts/data_fixes/changelog/`).

Data hashes after the fixes (sha256 over the `cases_*.json` files, name then bytes, in
sorted order): `benchmarks` `d801b350b5bbf66a…`, `benchmarks_en` `a5530d8c6afb9789…`.

## What changed, by decision

| decision / issue | cases | what was done |
|---|---|---|
| K4 (fix table v3) | 296 | 170 KR questions, 220 EN questions and 105 gold blocks replaced with the approved to-be values. The pass refuses to run unless the as-is value still matches the table. |
| D09 / L1-023 | 143 | The `*_ex01..08` duplicates deleted: 19 questions had 6-9 copies each. **1,258 to 1,115 cases.** |
| D03 / L3-007 | 243 | 76 invented 10-digit account numbers, none of which exists in HOFINET, replaced by real 16-digit accounts that play the same role. |
| D12 / C1-003 | 47 + 3 | 30 `predict_fraud` amounts mapped onto the 48 values HOFINET holds and 34 golds moved off fund type 4 (868fd28 R3/R7); three SQL questions moved off fund type 4 as well. |
| D10 / L1-001, L6-009, L3-011 | 34 | 14 mislabelled abstention cases became tool cases, 8 more accept the tool answer beside the abstention, 12 glossary and FIU questions ask for catalog content, `st_gl_008` uses a term the catalog holds. |
| D11 / L1-002 … L1-011 | 66 | A discriminating cue added so exactly one gold tool remains. |
| D19 / L1-014, L1-015, L1-016, L1-018 | 52 | One rule for what a clarification case is; STR drafts in the three `validate_str_fields` questions; required enum values in the question; parameters the question left open or stated backwards. |
| D23 / L1-022 | 557 | Difficulty recomputed from an explicit rule. |
| Contract 1 / C1-011, L4-015 | 75 | `sql_contains` replaced by `sql_conditions` plus an executable `expected.reference_calls.query_transactions.sql`. |
| L1-012, L1-013, L1-025, L1-026, L1-027, L1-028 | 1,115 | Gold keys that are not schema properties, sample sizes over the schema maximum, EN questions that changed a tool or a parameter, the stale `question_ko` copies, requests HOFINET cannot answer, conditions the gold tool cannot apply, and every note regenerated from the final gold. |

## Final composition

1,115 cases in each language, the same ids, the same gold, the same difficulty and the same
notes in both.

| category (file) | n | easy | medium | hard |
|---|---|---|---|---|
| `analyze_channel_risk` | 50 | 30 | 0 | 20 |
| `analyze_cross_institution_flow` | 50 | 38 | 12 | 0 |
| `analyze_network` | 50 | 50 | 0 | 0 |
| `compare_periods` | 50 | 7 | 0 | 43 |
| `detect_aml_patterns` | 50 | 15 | 35 | 0 |
| `detect_ctr_candidates` | 50 | 10 | 26 | 14 |
| `detect_dormant_reactivation` | 50 | 48 | 2 | 0 |
| `detect_monitoring_alerts` | 50 | 13 | 29 | 8 |
| `detect_smurfing_network` | 50 | 10 | 33 | 7 |
| `get_account_profile` | 50 | 50 | 0 | 0 |
| `get_aml_glossary` | 8 | 8 | 0 | 0 |
| `get_fraud_type_summary` | 50 | 31 | 19 | 0 |
| `get_institution_report` | 50 | 48 | 1 | 1 |
| `get_receiving_account_profile` | 50 | 50 | 0 | 0 |
| `get_statistics` | 55 | 54 | 1 | 0 |
| `get_trend_analysis` | 50 | 6 | 26 | 18 |
| `lookup_fiu_reference_types` | 8 | 0 | 6 | 2 |
| `missing_parameters` | 25 | 25 | 0 | 0 |
| `multi_tool` | 100 | 11 | 26 | 63 |
| `predict_fraud` | 55 | 52 | 3 | 0 |
| `query_transactions` | 61 | 8 | 28 | 25 |
| `rank_risky_transactions` | 50 | 50 | 0 | 0 |
| `score_account_risk` | 50 | 50 | 0 | 0 |
| `validate_str_fields` | 3 | 3 | 0 | 0 |
| **total** | **1,115** | **667** | **247** | **201** |

| case kind | n |
|---|---|
| single-tool | 888 |
| multi-tool | 87 |
| abstention (no tool call) | 119 |
| clarification (`expect_clarification`) | 21 |

| gold tool | cases | gold tool | cases |
|---|---|---|---|
| (no tool call) | 140 | `analyze_channel_risk` | 52 |
| `query_transactions` | 75 | `detect_dormant_reactivation` | 52 |
| `get_statistics` | 68 | `detect_smurfing_network` | 52 |
| `analyze_network` | 63 | `detect_monitoring_alerts` | 51 |
| `detect_aml_patterns` | 61 | `rank_risky_transactions` | 51 |
| `get_trend_analysis` | 57 | `get_fraud_type_summary` | 50 |
| `score_account_risk` | 56 | `compare_periods` | 48 |
| `predict_fraud` | 55 | `get_aml_glossary` | 12 |
| `detect_ctr_candidates` | 54 | `lookup_fiu_reference_types` | 8 |
| `analyze_cross_institution_flow` | 53 | `validate_str_fields` | 3 |
| `get_account_profile` | 53 | | |
| `get_institution_report` | 53 | | |
| `get_receiving_account_profile` | 53 | | |

A multi-tool case counts once per gold tool, so the tool column sums to more than 1,115.
12 cases carry `expected.alternatives`, 75 carry `expected.reference_calls`, 21 carry
`expected.expect_clarification`.

## The difficulty rule (D23)

```
points = tool_count + argument_derivation + tool_overlap + information_gap
```

* `tool_count` — 0 for one gold tool, 1 for two, 2 for three or more.
* `argument_derivation` — how many gold values the question does not write out and the model
  has to derive (a fraud type from its name, a date range from "the first half of 2024", a SQL
  predicate from a phrase): 0 for none, 1 for one, 2 for two or more.
* `tool_overlap` — 0 when no other tool answers anything like this one, 1 when one to three do,
  2 when four or more do. The overlap map is the one D11 fixed, listed tool by tool in
  `p11_difficulty.py`.
* `information_gap` — 1 when the case expects no tool call at all.

0-1 points is easy, 2 is medium, 3 or more is hard. `changelog/p11_difficulty_scores.json`
carries the points and every component per case. The distribution moves from 530/412/173 to
667/247/201. The old labels did not track observed difficulty: over the 28 pre-audit
configurations, hard cases had a higher mean h (.808) than medium ones (.778), and the rank
correlation between a case's h and its difficulty was -0.17.

## Gate results

| gate | command | result |
|---|---|---|
| data linter | `python -m _experiments.scripts.data_fixes.lint_benchmarks` | **1,115 cases, 0 violations**, exit 0 |
| linter, negative control | same, on a copy with 12 defects planted | **21 violations**, exit 1 |
| gold-call execution | `… .verify_gold_calls --benchmark benchmarks --gate` | 978 gold calls executed, **0 blocking**, exit 0 |
| gold self-test (KR) | `python -m _experiments.scripts.scoring.gold_selftest --benchmark benchmarks` | **1115/1115 perfect**, 0 defects, 1 advisory |
| gold self-test (EN) | same, `--benchmark benchmarks_en` | **1115/1115 perfect**, 0 defects, 1 advisory |

The linter checks schema keys, English keys, tool names, enum values, schema bounds, HOFINET
values (bank ids, time slots, fund and media types, fraud types, dates, the 48 amounts, and
fund type 4 in a fraud question), account existence against the database, `sql_conditions`
columns, the reference SQL, the clarification and alternatives shapes, fraud-type naming,
duplicate questions and KR/EN parity. It exits non-zero on any violation, so it can gate the
re-run. `check_hofinet_compliance.py` now delegates to it; its old "0 violations" must not be
quoted, because it read Korean parameter keys the data had not used since April and reported
0 both for the real data and for a copy with the keys put back in Korean.

## What still answers nothing, and why

40 of the 978 gold calls return an empty result: 17 `ring`, 11 `layering` and 12 `funnel`
scans. Rings and layering do not occur in HOFINET's transfer graph at all, which D06 already
documents. **Funnel is new**: only 414 accounts both send and receive, none of them forwards
to three or fewer counterparties, and the largest inflow among accounts with six or fewer
outgoing counterparties is five, so the default `min_inflow=10, max_outflow=3` can never
match. WS-D did not pin funnel parameters into the gold because D06 rebuilds that tool;
`impl/WS-D_tool_description_requests.md` item 9 asks WS-A to lower the defaults or state the
emptiness in the description. h is unaffected either way, because the gold is the call.

One advisory remains in the self-test: `st_mtool_084`'s second call takes the account of the
top row of a `rank_risky_transactions` sample, which is not stable enough to pin.

`predict_fraud` inputs are in the data distribution field by field, which is what D12 scopes;
none of the 55 six-field combinations occurs as a row in HOFINET, and making them occur would
mean rewriting the time slot, both institutions and the channel of 47 of the 55 questions.

## Departures from the register text, and why

* **L1-006 `st_gfs_036`** — the register suggests adding `get_statistics` to `tools_must_include`
  so the question can compare one type's average amount with the others. `get_statistics`
  returns counts per type but no amounts, so that would not answer the question either; the
  question was narrowed to what one `get_fraud_type_summary` call returns, which L1-006 also
  offers for `st_gfs_038` and `st_gfs_009`.
* **L1-015 and the blind review** — the register lists five mislabelled missing-parameter cases
  (`st_mp_012/013/019/021/023`), and the round-2 blind review calls three of them (013, 019,
  023) defensible either way. D19's rule settles it: their tool has no required argument, so a
  default call is the only correct behaviour and they became tool cases. They therefore do not
  carry an alternative. Of the 14 defensible-either-way cases, 11 carry `alternatives`
  (8 abstention cases, `st_gl_006`, `st_mp_005`, and `st_mon_025` with two) and 3 are settled
  by the D19 rewrite.
* **The 16 clear mislabels** — 14 are abstention cases and were fixed in the relevance pass;
  the other two (`st_mp_012`, `st_mp_021`) are missing-parameter cases and were fixed in the
  clarification pass.
* **`st_mtool_087`** names three accounts but the gold can hold only one `score_account_risk`
  spec, because `param_checks` is keyed by tool. All three accounts are real; the gold checks
  the first. Contract 1 cannot express "the same tool with three different arguments".

## What other streams have to mirror

See `impl/WS-D_tool_description_requests.md` for the full list. In short:

1. **WS-C (`tools_kr.py`)** — the Korean schema must carry the platform's R003 wording
   (`동일 금액 반복 송금`, not `정액거래패턴`) and the other four rule labels from `RULE_NAMES`.
2. **WS-A (system prompt, D08)** — state the D10 rule once: a definition or comparison of a term
   the glossary holds is answered with `get_aml_glossary`; any other conceptual explanation is
   answered without a tool.
3. **WS-A (`detect_aml_patterns`)** — decide what to do about the empty funnel scan.
4. **WS-B (scoring)** — `expected.alternatives` is now used by 12 single-turn cases and
   `expected.reference_calls` by 75; both are already supported.
5. **WS-E (multi-turn)** — the naming rules the single-turn data now follows: CTR cases say
   `구조화(structuring)` and fraud type 3 is always `분할 거래(유형3)`; funnel questions state the
   few outgoing counterparties and smurfing questions a counterparty threshold; monitoring-rule
   questions name the rule; SQL questions say so; account ids are the real 16-digit HOFINET ids;
   fund type 4 never appears in a fraud question; amounts are among the 48 HOFINET holds.
   `_experiments/scripts/data_fixes/account_map.json` is the account mapping to reuse.
