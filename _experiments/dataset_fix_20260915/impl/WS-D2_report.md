# WS-D2 report: the closeout findings and the domain review (2026-09-16)

Branch `audit-fixes`, repository `STAR-Bench`. Two rounds landed here: the seven
findings the closeout verification left open
(`closeout/closeout_data.md`) and the four asks of the domain review of the 143
new cases (`impl/USER_REVIEW_2026-09-16.md`). Every change to `benchmarks/`,
`benchmarks_en/`, `benchmarks_multiturn/` and `benchmarks_multiturn_en/` was
produced by a committed pass; the data files carry no hand edits.

```bash
python -m _experiments.scripts.data_fixes.run_all --from 574c077 --skip-checks
python -m _experiments.scripts.data_fixes.multiturn.build
```

The first command replays the whole single-turn round from the pre-audit snapshot,
including `new_cases.author`, and **reproduces both committed directories byte for
byte** (checked on 2026-09-16 with `diff -rq`). The second rebuilds the multi-turn
files from the scenario specs by executing every gold call on the platform.

Commits: `c519a77` (closeout, single-turn), `dd32921` (closeout, multi-turn),
`86564ea` (domain review, data), `6377bad` (domain review, passes and pipeline).

---

## Part 1 - the closeout findings

### 1. C1-003 - 49 questions asked for a fraud probability

`predict_fraud` and `rank_risky_transactions` return `fraud_risk_score`, described
as an "uncalibrated XGBoost score in [0, 1]; not a probability of fraud", and
`score_account_risk` returns a 0-100 behavioural risk score. The closeout counted
40 single-turn questions asking for a 확률 / probability; the sweep for the same
framing found 49 (it also caught `가능성` / "likelihood" / "how likely", which is
the same claim in other words).

`p14_risk_score.py` rewords all 49 in both arms and changes no gold: the Korean
now says 위험 점수, which is the wording the multi-turn data already used when
L2-012 removed the framing there, and the English says "fraud risk score". The
pass ends with a residue check: no question whose gold names one of the three
scoring tools may contain 확률, 가능성, "probabilit", "likelihood" or "how likely".

| | before | after |
|---|---|---|
| KR questions naming a probability | 49 | 0 |
| EN questions naming a probability or a likelihood | 49 | 0 |
| gold blocks changed | - | 0 |

### 2. L1-003 - 대포통장 / "mule account" mapped to three different golds

Five cases used the word while their golds differed: `detect_aml_patterns(funnel)`
(st_mtool_013, st_mtool_019, st_mtool_059), `get_receiving_account_profile`
(st_grap_039) and an abstention (st_grap_irr_002). `p15_tool_cues.py` gives each
question the one cue its own gold answers (D11), adds no alternatives, and checks
that the word is gone from both arms.

| case | gold | the cue it now carries |
|---|---|---|
| st_mtool_013 | `detect_aml_patterns(funnel)` | 입금 상대는 많고 출금 상대는 소수인 funnel 계좌 패턴 |
| st_mtool_019 | `detect_aml_patterns(funnel)` | the same, as the first clause |
| st_mtool_059 | `detect_aml_patterns(funnel)` | the same, as the second clause |
| st_grap_039 | `get_receiving_account_profile` | 들어온 거래 건수와 송금 계좌·송금 기관 수, 이상거래 비율 - the fields only that tool returns |
| st_grap_irr_002 | (no tool call) | asks for the criteria for judging a receiving account, before the account information exists |

### 3. L1-010 - splitting language on two different golds

`st_ctr_029` and `st_ctr_033` now name the CTR reporting threshold, which is what
`detect_ctr_candidates(mode=structuring)` is defined by, and `st_gfs_041` names
the HOFINET label its gold summarises instead of describing CTR structuring:

* st_ctr_029: "CTR 보고 기준 미만으로 나눈 거래 분할 패턴을 탐지해줘"
* st_ctr_033: "대금을 CTR 보고 기준 미만으로 여러 번에 나눠서 입금하는 거래를 찾아줘"
* st_gfs_041: "이상거래 유형 가운데 분할 거래(유형3)로 분류된 건의 건수와 금액 요약을 보여줘"

### 4. L1-016 - the one gold call that could not be executed

`st_mtool_084`'s gold called `analyze_network` with no `account_id`, so executing
it returned `{'error': 'account_id is required.'}`. It was the one self-test
advisory and the one call the platform harness skipped.

`rank_risky_transactions` scores a random sample, so the account in first place
cannot be pinned, which is why `p10_executable_gold` left the advisory. Dropping
the second call would have turned the case into a plain `rank_risky_transactions`
question, of which the benchmark already holds 55, so `p16_executable_gold2.py`
names the account in the question instead: the case stays a two-tool case and both
calls execute. The `skipped` entry left `preflight/allow_empty.json` with it.

* KR: "고위험 거래 20건을 랭킹하고, 계좌 9000000000034076의 네트워크도 분석해줘"
* gold-call execution: 1,129 -> **1,130 calls, 0 skipped**; self-test advisories 1 -> **0**

### 5. L1-025 - the same boundary, two different meanings

The closeout named seven pairs where Korean 이상 (>=) became "over" / "more than"
(>). `p17_boundary_parity.py` fixes those and what a sweep over all 1,258 pairs
added. The sweep (numbers, comparison words, negation, units) is described in
[the sweep section](#the-krem-sweep-over-all-1258-pairs) below.

**English brought back to the Korean boundary (12 cases).** st_ctr_008, st_ctr_013,
st_ctr_030, st_dorm_022, st_dorm_028, st_dorm_035, st_dorm_038 (twice), st_dorm_041,
st_qt_004, st_qt_045, st_qt_050 (twice), st_an_017. Five of these were the ones the
closeout flagged as carrying the gold's own value. st_qt_050's Korean bands also
overlapped at 1000만원; the reference SQL puts that value in the large band and the
question now says so. st_an_017 said "up to level 2" where the Korean counts hops.

**Both arms moved onto the threshold the tool applies (7 cases).**
`detect_dormant_reactivation` filters `>= dormant_days` and
`>= min_reactivation_amount`, `detect_smurfing_network` `>= min_counterparts`, and
`detect_ctr_candidates(structuring)` sums "to it or above", but st_ctr_019,
st_dorm_026, st_dorm_032, st_dorm_042, st_dorm_044, st_dorm_046 and st_smurf_049
said 넘는 / "more than" in both languages, so both arms asked for something the
gold does not check. st_dorm_046 and st_smurf_049 are 2026-09 expansion cases and
were corrected in `new_cases/g4_single_tool.py`, which authors them.

### 6. st_strv_001 / 002 / 003 - drafts that describe nothing

The three pre-existing `validate_str_fields` drafts stated a `TransactionPeriod`,
a `TransactionCount` and a `TotalAmount_KRW` for account pairs with no transactions
between them, at a `WithdrawalInstitutionCode` that is not the sender's bank.
`p18_str_drafts.py` rebuilds them with `new_cases/g1_validate_str.base_draft`, the
same code that built the 22 drafts WS-G added, on rows 10, 15 and 19 of
`new_cases/grounding.json`, and keeps the defect each case exists to test. The pass
refuses to run if a rebuilt draft equals any other case's draft.

| case | grounding row | the required field it still misses |
|---|---|---|
| st_strv_001 | 9000000000041188 -> 9000000003707223, 159, Internet Banking, 20240715-20240723, 7 transfers, 28,000,000 | `VII_Narrative.SuspicionJudgmentReason` |
| st_strv_002 | 9000000000021942 -> 9000000002264298, 147, 20221013-20221021, 28 transfers, 1,940,000,000 | `III_TransactionDetails.TransactionChannel` |
| st_strv_003 | 9000000004387158 -> 9000000004415397, 159, Internet Banking, 20221010-20221020, 2 transfers, 120,000,000 | `VI_TransactionType.PrimarySuspicionType` |

### 7. The sweep findings

`p19_sweep_fixes.py`:

* **st_acr_042** asked to compare the 2023 and the 2024 channel ratios and name the
  channels whose risk rose, while its gold is one
  `analyze_channel_risk(20230101-20241231)` call, which returns a single aggregate.
  `param_checks` holds one entry per tool, so two calls of the same tool cannot both
  be pinned; the question now asks for the aggregate the gold produces.
* **st_cp_025** asserted that 2021 Q4 is when the data was first collected. HOFINET
  starts on 2021-09-01, so 2021 Q4 is the first *complete* quarter. **st_cp_040**
  made the same claim in English and is corrected with it.

### 8-10. Multi-turn (commit `dd32921`)

* **mt_str_023 turn 4 (L3-018).** The draft handed over as "the STR draft I am
  working on" named withdrawal account 9000000000041932 and receiving account
  9000000002364786, while turns 3 and 5 investigate 9000000004387158. `DRAFT_023`
  is now the real 2024 same-day-withdrawal (type 5) aggregate of the scenario's own
  account to its busiest type-5 counterparty that year (9000000004416541,
  20240123-20240501, 2 transfers, 120,000,000 KRW, Internet Banking) and still
  leaves §VI and §VII out, so `validate_str_fields` reports the same two missing
  fields and turn 5 quotes the same result.
* **33 of the 38 reference SQL statements (L2-009).** Commit 5f45ee5 appended the
  tie-break columns without de-duplicating them, so `receiver_acc`, `date` and
  `amount` each appeared twice. `order_by()` now appends only the tie-break columns
  the caller does not already sort on. The statement is still a total order over all
  seven columns, so every executed result is unchanged; **0 of 38 repeat a column**.
* **8 gold STR summaries (L2-012)** spliced raw English catalog, glossary and
  "nothing found" sentences into Korean narrative (mt_str_006, 015, 020, 023, 040,
  048, 049, 050). `spec.KO_SOURCE` records the Korean that each of those nine values
  stands for and `{name:ko}` renders it, so the summary is still bound to the
  executed result and the build fails on a value the table does not hold.
* **The English arm's `generate_str` summary was Korean in all 45 scenarios.** D13
  says the answer follows the language of the question, so each scenario now carries
  a summary in each language (`Bi` in `spec.py`) and the call is executed once per
  arm, because `generate_str` echoes the summary into
  `VII_Narrative.SuspicionJudgmentReason`. `fraud_type` stays Korean in both arms:
  the platform's §VI enum has no English form. Exactly two fields differ between the
  arms; `verify.py` blanks those two and still requires every other byte of the gold
  call and of the injected result to be identical, and a new
  `check_summary_language` fails if a Korean summary carries no Korean or an English
  one carries any.

---

## Part 2 - the domain review

### A. One spelling per pattern term

**The convention.** Each pattern is written one way, in both arms, with no
cross-language gloss in brackets:

| pattern | Korean question | English question |
|---|---|---|
| `ring` | 순환거래 | circular transaction |
| `layering` | 레이어링 | layering |
| `funnel` | funnel | funnel |
| `structuring` | structuring | structuring |
| smurfing | 스머핑 | smurfing |

The Korean word is used where Korean AML practice has one that states the condition
itself. The English token is used for the two patterns where the Korean word would
be a second name for something the data already names: 구조화 reads as a synonym of
분할 거래, which is HOFINET fraud type 3 and a *different* gold tool - the exact
ambiguity L1-010 was opened for - and every Korean word for funnel (깔때기, 집금,
집금책, 퍼널) collides with the 집금/집결 wording `detect_smurfing_network` uses.
One exception: a question that asks for an AML glossary entry or an FIU catalog row
names it by its key, which the catalog holds in English ("Structuring 항목"); that is
the entry's name, not the pattern term.

`p20_terminology.py` applies it to 26 cases (31 question edits) and refuses to
finish while a second spelling is left. Single-turn Korean questions before -> after:
구조화 alone 12 -> 0, 구조화(structuring) 6 -> 0, 깔때기 1 -> 0, 집금 2 -> 0, bare
`ring` 1 -> 0, bare `layering` 2 -> 0. st_ctr_009 and st_ctr_036 also change verb: with one
spelling they would otherwise sit at 0.76 and 0.80 character-3-gram Jaccard from
st_ctr_004 and st_ctr_021, and the Korean benchmark carries no pair above 0.72.

The multi-turn specs follow it too: mt_str_020 turn 1 and mt_str_049 turn 4 name the
glossary entry by its key, mt_str_021 turn 2 drops 분할거래 for `structuring`, and the
`KO_SOURCE` rendering of the FIU structuring row ends "(structuring)".

**Mirrored in the tool prose.** `_experiments/scripts/tools_kr_text.json` said 퍼널
for funnel in two parameter descriptions and 분할거래 for structuring in the
`detect_ctr_candidates` description; both now use the convention, and `tools_kr.py`
is regenerated (`gen_tools_kr --check` passes).

**For the platform repository (not edited here), three strings to decide on:**

1. `src/features/agent.py:1182` - the §VI mapping table has
   `(("ring", "cycle", "순환", "환거래"), "Structured transactions")`, so *ring* maps
   to a §VI label whose name is the *structuring* term, while
   `(("structuring", "smurfing", "분할", "스머핑"), ...)` on line 1185 maps structuring
   somewhere else. Two different patterns, one word in the label.
2. `src/features/agent.py:1184` - `(("funnel", "mule", "대포통장", "집금"), ...)` still
   carries 대포통장, the crime name L1-003 removed from the benchmark data.
3. Everything else in the platform (the `detect_aml_patterns` and
   `detect_ctr_candidates` descriptions, the enum values, the English system prompt)
   already uses the bare terms and matches the convention; the Korean system prompt
   does not name the patterns at all.

### B. Every clarification case re-derived against D19

`p22_clarification_audit.py` carries the derivation for all 40
`expect_clarification` cases - the tool the question points at and the argument it
leaves unresolved - and checks each argument against the tool's own schema, so the
table cannot drift from the platform. It changes no data. **All 40 hold: 0 of them
could have been answered by calling the tool on its defaults.** The pass fails if
a named argument is not required.

| id | tool | unresolved | kind |
|---|---|---|---|
| st_gir_irr_002 | `get_institution_report` | bank_id | schema-required |
| st_mp_001 | `get_aml_glossary` | term | schema-required |
| st_mp_002 | `analyze_network` | account_id | schema-required |
| st_mp_003 | `get_institution_report` | bank_id | schema-required |
| st_mp_004 | `lookup_fiu_reference_types` | keyword | schema-required |
| st_mp_005 | `score_account_risk` | account_id | schema-required |
| st_mp_006 | `get_account_profile` | account_id | schema-required |
| st_mp_007 | `compare_periods` | the four period bounds | schema-required |
| st_mp_008 | `get_institution_report` | bank_id | schema-required |
| st_mp_009 | `detect_smurfing_network` | direction | schema-required |
| st_mp_010 | `get_fraud_type_summary` | fraud_type | schema-required |
| st_mp_011 | `detect_aml_patterns` | account_a, account_b | required for pattern_type=shortest_path |
| st_mp_014 | `detect_monitoring_alerts` | rule_id | schema-required |
| st_mp_015 | `validate_str_fields` | str_draft | schema-required |
| st_mp_016 | `compare_periods` | the four period bounds | schema-required |
| st_mp_017 | `predict_fraud` | all six features | schema-required |
| st_mp_018 | `detect_aml_patterns` | account_a, account_b | required for pattern_type=shortest_path |
| st_mp_020 | `get_receiving_account_profile` | account_id | schema-required |
| st_mp_022 | `detect_aml_patterns` | pattern_type | schema-required |
| st_mp_024 | `detect_smurfing_network` | direction | schema-required |
| st_mp_025 | `get_institution_report` | bank_id | schema-required |
| st_mp_026 | `detect_ctr_candidates` | mode | schema-required |
| st_mp_027 | `score_account_risk` | account_id | schema-required |
| st_mp_028 | `predict_fraud` | all six features | schema-required |
| st_mp_029 | `query_transactions` | sql | schema-required |
| st_mp_030 | `get_fraud_type_summary` | fraud_type | schema-required |
| st_mp_031 | `compare_periods` | the four period bounds | schema-required |
| st_mp_032 | `get_institution_report` | bank_id | schema-required |
| st_mp_033 | `detect_aml_patterns` | account_b | required for pattern_type=shortest_path |
| st_mp_034 | `get_aml_glossary` | term | schema-required |
| st_mp_035 | `lookup_fiu_reference_types` | keyword | schema-required |
| st_mp_036 | `validate_str_fields` | str_draft | schema-required |
| st_mp_037 | `analyze_network` | account_id | schema-required |
| st_mp_038 | `get_account_profile` | account_id | schema-required |
| st_mp_039 | `get_receiving_account_profile` | account_id | schema-required |
| st_mp_040 | `detect_smurfing_network` | direction | schema-required |
| st_mp_041 | `detect_monitoring_alerts` | rule_id | schema-required |
| st_mp_042 | `detect_aml_patterns` | pattern_type | schema-required |
| st_mp_043 | `predict_fraud` | sender_bank, receiver_bank, fund_type | schema-required |
| st_mp_044 | `query_transactions` | sql | schema-required |

Three cases (st_mp_011, st_mp_018, st_mp_033) rest on `account_a` / `account_b`,
which JSON Schema cannot mark required for `pattern_type=shortest_path` alone: the
`required` list holds `pattern_type` and the property descriptions say "required for
shortest_path". The pass executes
`detect_aml_patterns(pattern_type="shortest_path")` and records the platform's
answer, `'shortest_path requires account_a and account_b.'`, so the claim is a test
and not a reading of the schema.

Three of the 19 cases the reviewer asked about also changed wording under ask C
(st_mp_030, st_mp_032, st_mp_044); none of them changed kind. **st_mp_026 is the
one worth a second opinion**: the mode is genuinely unresolved ("앞에서 말한 조회
모드로"), but "CTR 대상 거래" may read to a model as `mode=high_value`. The reviewer
marked it ok-with-note and it is left as it is.

### C. Phrasings that read like a translated column name

`p21_phrasing.py`, six cases:

| case | before | after |
|---|---|---|
| st_mp_030 | 상위 관련 기관 | 그 유형에서 건수가 가장 많은 금융회사 |
| st_gfs_016 | 상위 관련 기관 | 이 유형이 가장 많이 발생한 금융회사 |
| st_gfs_036 | 상위 관련 금융회사 | 이 유형에서 건수가 가장 많은 금융회사 |
| st_mp_032 | 입출금 양방향 현황 리포트 | 입출금 자금흐름 현황 리포트 |
| st_mtool_113 | 입출금 양방향 현황 리포트 | 입출금 자금흐름 현황 리포트 |
| st_mp_044 | 결과 건수와 상위 행 | 결과 건수와 상위 거래 내역 |

The sweep behind them looked for 양방향, 상위 행, 상위 관련, 컬럼/행/레코드/필드 as
nouns, and raw schema parameter names. It found the three the reviewer named, two
more of the same shape (st_gfs_016, st_gfs_036, st_mtool_113) and the `bank_id`
cases below. 분포 ("distribution") was checked and left: it is what an analyst says,
not a column name.

### D. When a raw parameter value may appear in the question

**The rule.** A parameter never appears in a question in its schema spelling. That
covers a value in brackets after a Korean phrase ("모이는(inbound)"), an identifier
with an underscore ("고액거래(high_value)"), a parameter name ("bank_id 156") and a
phrase that names the slot rather than the condition ("structuring 모드로", "inbound
방향의"). The question states the condition and the model maps it to the schema.

Three things stay, because they are names rather than hints: the two pattern terms
ask A fixed (`funnel`, `structuring`); an AML glossary term or FIU keyword, which
the tool matches literally against an English catalog; and the HOFINET code tables
(자금구분 3, 매체구분 2, 거래시간대 9, 유형 7, institution numbers), which are the
values the data itself carries. An ordinary English word that coincides with an enum
value ("inbound", "high-value") is normal English and stays in the English arm.

16 cases changed: st_ctr_045 ("structuring 모드로"), st_ctr_048 ("(high_value)", the
one the reviewer asked about), st_mtool_034, st_mtool_039, st_mtool_042, st_mtool_045,
st_mtool_052, st_mtool_061, st_mtool_071, st_mtool_077, st_smurf_036 ("(inbound)" /
"(outbound)"), st_smurf_005, st_smurf_006, st_smurf_046 ("inbound 방향의"), st_gir_007
and st_gir_037 ("bank_id"). Every one of them still states the condition the gold
value follows from, so `direction`, `mode` and `bank_id` stay derivable; the
difficulty rule (D23) counts them as derived now, which is why the distribution moves.

**st_mtool_061 was rewritten, not only de-bracketed.** It asked for the collection
*and* the dispersion direction while its gold pins one `detect_smurfing_network`
call, and `param_checks` holds one entry per tool, so the second half could never be
scored - the same shape as st_acr_042. It now asks for the one direction and says
why: "스머핑 네트워크에서 자금이 한 계좌로 모이는 방향만 탐지해줘. 분산 방향은 지금
볼 필요 없어."

---

## The KR/EN sweep over all 1,258 pairs

Four automated screens over every pair, each reviewed case by case:

| screen | candidates | real defects | what the rest were |
|---|---|---|---|
| boundary claims (a number, its unit and the comparison word attached to it, in both languages) | 32 | 12 | English numerals written out (five, ten), "이내" -> "within", 이상거래 matching as 이상 |
| numeric drift (every number in one language present in the other, after month names, ordinals, quarters and Korean numerals are normalised) | 44 | 0 | 하반기 -> "second half", "two-factor", rule ids R00N |
| negation (제외/아닌/없는/않은 against not/no/excluding/without) | 20 | 0 | 없던 계좌 -> "accounts that had no transactions" and the like |
| units (the unit attached to each Korean number against the English wording) | 13 | 1 | 일 inside 일반, institution codes; the one was st_an_017's "level" for 홉 |
| stiff constructions and schema spellings (ask C and ask D) | 28 | 22 | 분포 ("distribution"), which is what an analyst says, in six cases |

The boundary screen also found the seven cases where both arms agree with each other
but not with the tool, which is finding 5's second group.

---

## Final composition

1,258 cases in each language, the same ids, the same gold, the same difficulty and
the same note in both.

| | value |
|---|---|
| single-turn cases per language | 1,258 |
| difficulty easy / medium / hard | 736 / 283 / 239 |
| single-tool / multi-tool / abstention / clarification | 987 / 112 / 119 / 40 |
| multi-turn scenarios / turns | 50 / 219 |
| STR narrative coverage | 0.9328 |
| Korean near-duplicate pairs above 0.72 Jaccard | 0 (was 1) |
| logged changes over the whole round | 6,095 |

Difficulty moved from 739/282/237 to 736/283/239: naming the pattern explicitly
(st_gfs_041, st_mtool_013, st_mtool_059) removes a derivation step, and taking the
raw enum values out of the questions (ask D) adds one, which is the rule working as
D23 defines it.

## Gate results

| gate | command | result |
|---|---|---|
| single-turn linter | `python -m _experiments.scripts.data_fixes.lint_benchmarks` | **1,258 cases, 0 violations**, exit 0 |
| gold self-test, `benchmarks` | `… .scoring.gold_selftest --benchmark benchmarks` | **1258/1258 perfect, 0 defects, 0 advisories** |
| gold self-test, `benchmarks_en` | same | **1258/1258 perfect, 0 defects, 0 advisories** |
| gold self-test, `benchmarks_multiturn` | same | **oracle 50/50, e2e 50/50 perfect** |
| gold self-test, `benchmarks_multiturn_en` | same | **oracle 50/50, e2e 50/50 perfect** |
| gold-call execution | `… .data_fixes.verify_gold_calls --benchmark <dir> --gate` | **1,130 calls, 28 empty, 0 blocking, 0 skipped**, exit 0, both arms |
| multi-turn verify | `python -m _experiments.scripts.data_fixes.multiturn.verify` | **no problems**; 4-6 turns, 219 turns, STR coverage 0.9328 |
| new cases | `… .data_fixes.new_cases.verify --gate` | **143 cases, 151 gold calls, 0 problems**, exit 0 |
| platform harness | `pytest -m gold` with all four directories | benchmarks and benchmarks_en **ok 1220 / empty 28 / error 0 / skipped 0**; multiturn and multiturn_en **ok 199 / empty 1 / error 0** |
| pre-flight | `python -m _experiments.scripts.preflight.run --all` | gate 2 code tests **PASS**, gate 3 benchmark data **9/9 PASS**, gate 4 gold answers **10/10 PASS**, gate 5 **PASS**, gate 6 skipped, gate 1 **FAIL** |
| pipeline replay | `… .data_fixes.run_all --from 574c077 --skip-checks` | both directories reproduced **byte for byte** |

The 28 empty gold calls are the `detect_aml_patterns` ring and layering scans, which
HOFINET cannot answer by construction (D06); they are listed case by case in
`preflight/allow_empty.json`. Gate 1 fails on the evaluation dependency pins
(matplotlib, numpy, openai, pandas, scipy differ from `requirements-eval.txt`) and on
26 of 28 model revisions that are still unpinned; both are outside the data and were
already failing before this round.

## What was deliberately left

* **st_mp_026** keeps its clarification gold. The mode is genuinely unresolved, but
  "CTR 대상 거래" may read as `mode=high_value`; the reviewer marked it
  ok-with-note. Flagged above rather than changed.
* **The platform's §VI mapping table** (three strings, listed under ask A) is
  reported rather than edited: the instruction was to report platform wording.
* **The English arm's near-duplicate pairs** (81 above 0.72 Jaccard) are unchanged
  and pre-date this round; the Korean arm, which the closeout measured, is at 0.
* **`fraud_type` in the multi-turn gold stays Korean in both arms.** The platform's
  §VI enum has no English value, so the English arm cannot call the tool otherwise.
  Only `summary` follows the question's language.
* **Gate 1 of the pre-flight** is left failing: dependency pins and model revisions
  belong to the serving work stream.
