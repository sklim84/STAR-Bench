# New single-turn cases, 2026-09 expansion (WS-G)

The 143 cases deleted as duplicates are replaced here by 143 newly authored cases, and
the same pass enlarges the categories that were too small to support the paper's claims.
Every case carries `"source": "2026-09 expansion"`, so the composition can be described
honestly and the round can be undone by dropping that tag.

```bash
python -m _experiments.scripts.data_fixes.new_cases.build_grounding   # needs the database
python -m _experiments.scripts.data_fixes.new_cases.author            # writes the cases
python -m _experiments.scripts.data_fixes.new_cases.verify --gate     # needs the platform
```

`author.py` is idempotent: it drops every case with that source tag before it adds them
again, so re-running it reproduces the committed files. It never touches an existing case,
and it refuses to run if a new id collides with an existing one.

## The files

| file | what it holds |
|---|---|
| `build_grounding.py` | Reads HOFINET and the platform catalog read-only and writes `grounding.json`. It must run before the authoring modules change, not before every authoring run. |
| `grounding.json` | The facts the questions are written against: 22 real transfer aggregates for the STR drafts, accounts per role, the accounts each monitoring rule still alerts on under an account filter, the funnel accounts the tool defaults find, the FIU keyword row counts, and the fraud-type/institution pairs that carry data. |
| `g1_validate_str.py` | 22 `validate_str_fields` cases. Each question carries a full STR draft built from one grounding row, with a different defect: complete drafts, one missing required field per required field, a missing section, a placeholder, an empty string, two fields at once, the legacy section names, snake_case field names, and drafts with no sections. |
| `g2_reference.py` | 17 `get_aml_glossary` and 17 `lookup_fiu_reference_types` cases. Only terms the 13-entry glossary holds; only keywords that select catalog rows, checked against `grounding.json`. |
| `g3_clarification.py` | 19 clarification cases. Each entry names the tool and the schema-required argument the question leaves unresolved. |
| `g4_single_tool.py` | 43 single-tool cases for the thinnest tools, including the first cases for `get_fraud_type_summary.bank_id` and `detect_monitoring_alerts.account_id`. |
| `g5_multi_tool.py` | 25 multi-tool cases, 14 of which reach a regulatory-reporting tool; no existing multi-tool case did. |
| `author.py` | Assembles the groups, derives `difficulty` from `p11_difficulty` and `note` from `p12_notes`, writes both languages and `new_cases.json`. |
| `verify.py` | Executes every new gold call, runs the near-duplicate check, checks KR/EN parity, and writes `impl/WS-G_review_sheet.json`. |
| `new_cases.json` | The manifest: every new case with its question in both languages, its gold, its difficulty points and its rationale. |

## Rules the cases follow

* Exactly one gold tool set per case, or a deliberate clarification.
* Every value in the gold appears in the question or follows from it, and every entity is
  one HOFINET holds: real 16-digit accounts in a role they actually play, bank codes from
  the sender and receiver lists, dates inside 20210901-20241231, amounts among the 48, code
  values from the official tables, and no fraud question on fund type 4.
* Glossary and FIU questions ask for catalog content, not for a concept explanation.
* `query_transactions` cases carry `sql_conditions` and an executable
  `expected.reference_calls.query_transactions.sql` (Contract 1).
* Difficulty comes from the rule and notes from the final gold, by calling the WS-D
  passes rather than reimplementing them.
