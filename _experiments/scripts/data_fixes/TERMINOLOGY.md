# Pattern terminology in the benchmark questions

One spelling per AML pattern, in both arms. The 2026-09 domain review (ask A) found
구조화(structuring), 구조화 and structuring used for the same thing, and 깔때기(funnel),
funnel(집금), 집금책 funnel and funnel for another, so a model could not tell from the
wording which tool a question wanted.

`terminology.py` next to this file is the executable copy of everything below.
`p20_terminology` applied the convention, `p23_terminology_residue` screens for it, and
`multiturn.verify` runs the same screen over the two multi-turn arms.

## The convention

| pattern | Korean question | English question |
|---|---|---|
| `ring` | 순환거래 | circular transaction |
| `layering` | 레이어링 | layering |
| `funnel` | funnel | funnel |
| `structuring` | structuring | structuring |
| smurfing | 스머핑 | smurfing |
| HOFINET fraud type 3 | 분할 거래 | split transaction |

The Korean term is used where Korean AML practice has a word that states the condition
itself (순환거래, 레이어링, 스머핑). The English token is used for the two patterns whose
Korean word would be a second name for something the data already names:

* 구조화 reads as a synonym of 분할 거래, which is HOFINET fraud type 3 and a different
  gold tool (L1-010, see below);
* every Korean word for funnel (깔때기, 집금, 집금책) collides with the 집금/집결 wording
  `detect_smurfing_network` uses.

Neither arm ever writes one language's term with the other in brackets: not
`구조화(structuring)`, not `funnel(집금)`, not `깔때기(funnel)`.

**One exception.** A question that asks for an AML glossary entry or an FIU catalog row
names it by its key, which the catalog holds in English: "AML 용어집에서 Structuring
항목", "the Structuring entry". That is the entry's name, not the pattern term.

## structuring is not HOFINET fraud type 3 (L1-010)

They are different things answered by different tools, so a question whose gold selects
one must not name the other.

| | what it is | gold that selects it | how the question names it |
|---|---|---|---|
| HOFINET fraud type 3 | a `fraud_type` value in the transaction data | `get_fraud_type_summary(fraud_type=3)`, `generate_str(fraud_type='분할거래')`, a `fraud_type = 3` SQL predicate | 분할 거래 / split transaction |
| the structuring pattern | a detection mode and a catalog and glossary entry | `detect_ctr_candidates(mode='structuring')`, `detect_aml_patterns(pattern='structuring')`, `lookup_fiu_reference_types(keyword='structuring')`, `get_aml_glossary(term='Structuring')` | structuring |

`lookup_fiu_reference_types(keyword='split')` is on neither side: that gold *is* the
catalog's split-transaction rows (`Deposits-Split`, and the securities In/Out row), so
`st_fiu_007` and `mt_str_015#t4` name 분할 거래 / split transfers and are right to.

A question whose gold carries values from both sides may name both.

## Catalog-valued gold

A gold string that has to reach a catalog is spelled in the form the tool itself
canonicalises to, because the scorer compares non-enum strings case-sensitively
(`scoring/compare.py`) while the tools do not.

| gold | rule | why |
|---|---|---|
| `lookup_fiu_reference_types.keyword` | lower case | the tool lower-cases the keyword before matching, and its own description lists its examples in lower case ("structuring, cash, non-face-to-face, virtual asset, dormancy, gambling, balance certificate") |
| `get_aml_glossary.term` | the catalog key as spelled (`CDD`, `STR`, `Structuring`, `Layering`) | the tool compares against the key |

A model that copies a spelling out of the tool description therefore scores what the
gold expects. The residual risk is on the scoring side and is recorded in
`AUDIT_FIXES_scoring.md`: a model that writes `ATM` where the gold says `atm` still
scores 0, because `_scalar_equal` case-folds enum values only.

## What the screen does not read

The screen reads the text a model sees as the user's message, with any JSON payload
removed, because that is what the convention governs. Two things are deliberately out
of scope:

* **Gold argument values.** `generate_str(fraud_type='분할거래')` is a §VI enum the
  platform only accepts in Korean.
* **STR narratives.** Four Korean `generate_str.summary` golds say "CTR 분할거래 조회"
  for a `mode='structuring'` query (`mt_str_010#t4`, `mt_str_021#t4`, `mt_str_039#t4`,
  `mt_str_049#t5`). They are left alone: `RQ_str_generation_quality.py` keys its §VII.5
  "method" and 6-W "how" patterns on 분할 and not on `structuring`, so rewording them
  would move a reported coverage number for a wording point.

## Where else the convention is stated

`STAR-Bench-Web src/features/agent.py` (`_AML_PATTERN_ITEMS`) and its `CHANGES.md`
describe the Korean recognition aliases the platform keeps for *funnel*. Both said the
benchmark questions use `깔때기(funnel)`, which is the spelling `p20_terminology`
removed, and pointed at this file under a path it never had. The platform reference
should read `_experiments/scripts/data_fixes/TERMINOLOGY.md` and say that the questions
use `funnel`.
