# WS-G report: new single-turn cases (2026-09 expansion)

Branch `audit-fixes`, repository `STAR-Bench`. 143 new cases were authored in both
languages, replacing the 143 `*_ex01..08` duplicates D09 deleted and enlarging the
categories that were too small to support the paper's claims. **1,115 -> 1,258 cases per
language.** Every new case is produced by a committed module under
`_experiments/scripts/data_fixes/new_cases/` and carries `"source": "2026-09 expansion"`.
`benchmarks/` and `benchmarks_en/` are append-only in this stream: a check in the commit
confirmed that no existing case was deleted, modified or reordered.

The review sheet a domain expert reads is `impl/WS-G_review_sheet.json`: one entry per new
case with the Korean question, the English question, the gold call, the executed result
summary, the difficulty points, a one-line rationale and the nearest existing question,
grouped by gold tool set.

## What was added, and why

| group | cases | the gap it closes |
|---|---|---|
| `validate_str_fields` | 22 (3 -> 25) | Three cases could not support any claim about the STR form. Each new question carries a full STR draft (D19) with a different defect. |
| `get_aml_glossary` | 17 (8 -> 25) | The glossary holds 13 entries and only 8 were ever asked for. Nine questions write the term out, eight name the concept the term abbreviates. |
| `lookup_fiu_reference_types` | 17 (8 -> 25) | Eight cases over a 31-row catalog. Seven of the new ones also pin an industry, which needs the catalog excerpt rather than model knowledge. |
| clarification | 19 (21 -> 40) | Each names one tool whose schema-required argument the question leaves unresolved (D19). |
| multi-tool | 25 (87 -> 112 cases with more than one gold tool) | No existing multi-tool case reached a regulatory-reporting tool; 14 of the new ones do. The rest pair the thinnest analysis tools. |
| single-tool, thinnest tools | 43 | Six for `get_fraud_type_summary.bank_id` and five for `detect_monitoring_alerts.account_id` -- two schema arguments with no case at all -- and 32 that widen parameter ranges (CTR thresholds and windows, period pairs, sample sizes, dormancy windows, counterparty thresholds). |

## Composition before and after

| category (file) | before | after | easy | medium | hard |
|---|---|---|---|---|---|
| `analyze_channel_risk` | 50 | 55 | 31 | 0 | 24 |
| `analyze_cross_institution_flow` | 50 | 50 | 38 | 12 | 0 |
| `analyze_network` | 50 | 50 | 50 | 0 | 0 |
| `compare_periods` | 50 | 56 | 9 | 0 | 47 |
| `detect_aml_patterns` | 50 | 50 | 15 | 35 | 0 |
| `detect_ctr_candidates` | 50 | 56 | 11 | 27 | 18 |
| `detect_dormant_reactivation` | 50 | 55 | 53 | 2 | 0 |
| `detect_monitoring_alerts` | 50 | 55 | 16 | 31 | 8 |
| `detect_smurfing_network` | 50 | 55 | 11 | 36 | 8 |
| `get_account_profile` | 50 | 50 | 50 | 0 | 0 |
| `get_aml_glossary` | 8 | 25 | 17 | 8 | 0 |
| `get_fraud_type_summary` | 50 | 56 | 35 | 21 | 0 |
| `get_institution_report` | 50 | 50 | 48 | 1 | 1 |
| `get_receiving_account_profile` | 50 | 50 | 50 | 0 | 0 |
| `get_statistics` | 55 | 55 | 54 | 1 | 0 |
| `get_trend_analysis` | 50 | 50 | 6 | 26 | 18 |
| `lookup_fiu_reference_types` | 8 | 25 | 1 | 15 | 9 |
| `missing_parameters` | 25 | 44 | 44 | 0 | 0 |
| `multi_tool` | 100 | 125 | 11 | 35 | 79 |
| `predict_fraud` | 55 | 55 | 52 | 3 | 0 |
| `query_transactions` | 61 | 61 | 8 | 28 | 25 |
| `rank_risky_transactions` | 50 | 55 | 54 | 1 | 0 |
| `score_account_risk` | 50 | 50 | 50 | 0 | 0 |
| `validate_str_fields` | 3 | 25 | 25 | 0 | 0 |
| **total** | **1,115** | **1,258** | **739** | **282** | **237** |

Difficulty moves from 667/247/201 to 739/282/237. The new cases are 72 easy, 35 medium and
36 hard; the share of easy cases is unchanged (59.8% -> 58.7%).

| gold tool | before | after | new | gold tool | before | after | new |
|---|---|---|---|---|---|---|---|
| (no tool call) | 140 | 159 | +19 | `analyze_channel_risk` | 52 | 58 | +6 |
| `query_transactions` | 75 | 77 | +2 | `compare_periods` | 48 | 58 | +10 |
| `get_statistics` | 68 | 68 | +0 | `detect_dormant_reactivation` | 52 | 58 | +6 |
| `detect_ctr_candidates` | 54 | 64 | +10 | `get_trend_analysis` | 57 | 58 | +1 |
| `analyze_network` | 63 | 63 | +0 | `rank_risky_transactions` | 51 | 58 | +7 |
| `detect_aml_patterns` | 61 | 62 | +1 | `get_account_profile` | 53 | 57 | +4 |
| `detect_monitoring_alerts` | 51 | 61 | +10 | `score_account_risk` | 56 | 57 | +1 |
| `get_fraud_type_summary` | 50 | 60 | +10 | `predict_fraud` | 55 | 56 | +1 |
| `detect_smurfing_network` | 52 | 59 | +7 | `analyze_cross_institution_flow` | 53 | 55 | +2 |
| `get_aml_glossary` | 12 | 33 | +21 | `get_institution_report` | 53 | 55 | +2 |
| `lookup_fiu_reference_types` | 8 | 30 | +22 | `get_receiving_account_profile` | 53 | 54 | +1 |
| `validate_str_fields` | 3 | 30 | +27 | | | | |

A multi-tool case counts once per gold tool, so the tool column sums to more than 1,258.
The analysis tools now sit in a 54-77 band instead of 48-75, and the three catalog tools
move from 3/8/12 to 30/30/33.

| case kind | before | after |
|---|---|---|
| single-tool | 888 | 987 |
| multi-tool | 87 | 112 |
| abstention (no tool call) | 119 | 119 |
| clarification (`expect_clarification`) | 21 | 40 |

By the four AML subdomains the paper uses (`generate_subdomain_radar.py`), counted as gold
tool occurrences:

| subdomain | before | after |
|---|---|---|
| Transaction Inquiry | 400 | 429 |
| Suspicious Detection | 213 | 232 |
| Money Flow & Network | 390 | 413 |
| Regulatory Reporting | 77 | 157 |

Regulatory Reporting was the reason for this round: it was a quarter the size of the other
three and three of its four tools had single-digit or barely double-digit coverage.

## How each quality rule was enforced

**1. Answerable from the question alone, exactly one gold tool.** Every new case names its
tool through a cue the tool description carries and no other tool's does: glossary
questions say `AML 용어집`, FIU questions say `FIU ... 참고유형`, monitoring questions name
the rule or its wording, smurfing questions name the direction or a counterparty count,
CTR questions name the mode or the threshold. The 19 clarification cases are the deliberate
exception: each names one tool whose schema-required argument the question leaves
unresolved, and `g3_clarification.py` records which tool and which argument that is, so the
D19 rule is checkable per case. Tools whose arguments are all optional are absent from that
group, because a default call is the correct answer for them.

**2. Every value exists in HOFINET.** No value was typed from memory.
`build_grounding.py` reads HOFINET and the platform catalog read-only and writes
`grounding.json`; the authoring modules read only that file and fail loudly when a value is
not in it (`fraud_bank` raises for a fraud-type/institution pair with no rows, `monitor`
raises when a rule has no account whose alert survives the account filter, `g2_reference`
raises for a glossary term the catalog does not define or an FIU keyword that selects
nothing). The accounts are 16-digit HOFINET ids picked for the role they play, following
the `account_map.json` convention. The four role pools exclude every account an existing
case already pins; the monitoring, funnel and STR-draft accounts are instead chosen by what
the tool actually returns, and one of the 14 new account references (`st_mon_047`) lands on
the account `st_gap_042` already profiles, because only three accounts keep an R004 alert
once the account filter is applied. The two questions ask different tools for different
things. The STR drafts are built from 22 real
transfer aggregates: the two account numbers, the withdrawal institution code, the channel,
the window, the transaction count and the total amount are what that pair actually has in
that window. The linter checks the rest independently: bank ids, time slots, fund and media
types, fraud types, dates inside 20210901-20241231, the 48 amounts, no `predict_fraud` gold
on fund type 4, and account existence against the database.

**3. Executable, with a sensible result.** `verify.py` runs all 151 gold calls of the new
cases through the platform's own tool layer and fails the gate on an error, an exception or
an empty result. **All 151 execute, none errors, none answers nothing.** The two
`query_transactions` cases carry `sql_conditions` and an executable
`expected.reference_calls.query_transactions.sql`, and the reference SQL is executed as
part of that run. The parameter values were chosen against the data rather than by guess:
`detect_dormant_reactivation` at 800 days returns 6 rows and at
`min_reactivation_amount = 300,000,000` returns none, so 800 is used and 300,000,000 is not;
`get_fraud_type_summary(fraud_type=7, bank_id=159)` returns all 35 rows of that type because
they all sit at one institution; the funnel case names one of the three accounts the scan
finds at the tool's new defaults.

**4. Not a near-duplicate, natural Korean.** Each new question is compared with all 1,258
questions of the same language by character 3-gram Jaccard, with any JSON payload removed
first, and the STR drafts are compared separately as an exact-match check over the drafts.
Four questions came back at or above 0.75 (`st_ctr_045` 0.844, `st_gl_009` 0.851,
`st_gl_010` 0.795, `st_cp_049` 0.772) and were rewritten; the highest remaining similarity
is 0.59 (`st_mp_034`). The gold tool sets of the 25 multi-tool cases are all new: none of
the 87 existing multi-tool cases uses the same set. The English question is a translation of
the Korean one and carries the same id, gold, difficulty and note, which `verify.py` checks
and the linter's parity check checks again.

**5. Difficulty and notes by the documented rule.** `author.py` imports
`p11_difficulty.points` and `p12_notes.note_for`, the same code that labelled the 1,115
existing cases, rather than reimplementing either. The per-case points and their four
components are in the review sheet, so a reviewer can see why a case is labelled as it is.

**6. Marked as this round's work.** Every new case carries `"source": "2026-09 expansion"`.
The runner's own bookkeeping field is `_source`, so there is no collision.

## Gate results

| gate | command | result |
|---|---|---|
| data linter | `python -m _experiments.scripts.data_fixes.lint_benchmarks` | **1,258 cases, 0 violations**, exit 0 |
| gold self-test (KR) | `python -m _experiments.scripts.scoring.gold_selftest --benchmark benchmarks` | **1258/1258 perfect**, 0 defects, 1 advisory |
| gold self-test (EN) | same, `--benchmark benchmarks_en` | **1258/1258 perfect**, 0 defects, 1 advisory |
| gold-call execution | `python -m _experiments.scripts.data_fixes.verify_gold_calls --benchmark benchmarks --gate` | 1,129 calls, 28 empty, **0 blocking**, exit 0 |
| new-case verification | `python -m _experiments.scripts.data_fixes.new_cases.verify --gate` | 143 cases, 151 gold calls, **0 problems**, exit 0 |
| platform gold-call harness | `pytest tests/test_gold_calls.py -m gold` on `STAR-Bench-Web@audit-fixes`, `STAR_BENCH_GOLD_DIRS` pointing at both directories | **ok 1,219, empty 28, error 0, skipped 1** per directory, 2 passed |

The one self-test advisory and the one skipped call are the same pre-existing case,
`st_mtool_084`, whose second call takes the account of the top row of a
`rank_risky_transactions` sample; WS-D documented it. The 28 empty results are the
pre-existing `ring` and `layering` scans, which HOFINET's acyclic transfer graph cannot
answer (D06). Both numbers are unchanged by this round, and the 12 funnel scans that were
empty before WS-A lowered the defaults now return rows, so the empty count fell from 40
to 28.

## Judgement calls worth a reviewer's attention

* **The D23 rule reads "is this value written in the question" as a substring test.** For
  `get_fraud_type_summary(fraud_type=1, bank_id=159)` the digit `1` occurs inside `159`, so
  the rule scores the fraud type as not derived and labels the case easy. Four of the six
  new institution-filtered cases are easy for that reason. The rule is D23's and it already
  labels the 1,115 existing cases the same way; changing it would relabel the whole
  benchmark, which is not this stream's call.
* **The two catalog tools stay at 30-33 cases while the analysis tools sit at 54-77.** The
  glossary has 13 entries and the FIU catalog 31 rows, so 25 questions per tool is already
  close to asking for the same row twice. Going further would mean either near-duplicate
  questions or enlarging the catalogs, which changes the platform.
* **FIU keywords select a row set, not a single row.** The scorer compares the rows the
  model's keyword selects with the rows the gold keyword selects, so a question whose
  natural keyword has a near neighbour in the catalog is genuinely hard. `st_mtool_116`
  ("wire transfer", 2 rows) is the clearest example. That is the behaviour
  `RQ2_lookup_fiu_keyword_analysis.py` studies, and the existing cases already work this
  way, but a domain expert should confirm the keyword is the one an analyst would reach for.
* **`tool_order` is set on 10 of the 25 multi-tool cases** -- the ones where the second call
  takes an input or a frame from the first. The other 15 ask for two independent things and
  are not ordered, which is how the existing multi-tool cases treat that situation.
* **Two new cases name an account that a third new case also names.** `st_mtool_110` and
  `st_mtool_125` both touch accounts with an R003 alert, from a pool of three; the questions
  and the gold tool sets differ, and the similarity check passes, but the pool is small
  because only a few accounts keep an alert under the account filter.

## Still open

1. **Domain review.** `impl/WS-G_review_sheet.json` has not been read by a domain expert
   yet. The items above are the ones most worth their time.
2. **Multi-turn.** `benchmarks_multiturn*` is another stream's; nothing here touched it.
   The naming rules the new cases follow are the ones WS-D listed for that stream.
3. **The paper's composition table** has to be regenerated from the 1,258 cases, and the
   appendix should say that 143 of them were authored in this round and are marked with
   `source`. The per-subdomain table above is the one the Regulatory Reporting claim rests on.
4. **`grounding.json` is tied to one database build.** It records the platform path but not
   the database sha256; if HOFINET is ever rebuilt, `build_grounding.py` has to be re-run and
   the authoring modules re-checked. The linter and the gold-call harness would catch a
   mismatch, so this is a convenience rather than a correctness gap.
