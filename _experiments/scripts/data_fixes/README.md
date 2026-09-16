# Single-turn data fixes (WS-D)

Every change to `benchmarks/` and `benchmarks_en/` since the 2026-09 audit was produced by a
pass in this package. The data files carry no hand edits: restoring the two directories from
the pre-audit commit and running `run_all.py` reproduces the committed files byte for byte.

```bash
python -m _experiments.scripts.data_fixes.run_all --from 574c077  # replay from the snapshot
```

`--from` is how the round is replayed and how the claim above is checked. Without it the
sequence stops at `p01_apply_v3`, which refuses to run once the data no longer carries the
fix table's as-is values, which is the whole point of that guard. Use the individual
verifiers to re-check a finished tree: `lint_benchmarks`, `verify_gold_calls`,
`scoring.gold_selftest`, `new_cases.verify --gate`.

`--from` writes the snapshot into the working tree only and resets the index straight back to
HEAD. `git checkout <commit> -- <path>` also stages what it restores, and on a shared branch
the next `git commit -a` from another work stream then commits the snapshot over the fixed
data; that is what happened in d2a4000 and was undone in f790db3.

Each pass writes `changelog/<pass>.json`: one entry per change, with the case id, the language,
the field, the register issue, the reason, and the value before and after. The paper appendix
cites those entries.

## The passes, in order

`p11_difficulty` and `p12_notes` derive their values from the question and the gold, so
`run_all.py` puts them last. In the first round they ran before `p13_lint_fixes`, which
left eight notes naming a value their own gold no longer carried.

| pass | register issue | what it does |
|---|---|---|
| `p01_apply_v3` | K4 | Applies the approved fix table v3 (`inputs/fix_table_data.json`): 170 KR questions, 220 EN questions, 105 gold blocks. Refuses to run if an as-is value no longer matches the table. |
| `p02_dedupe` | L1-023, D09 | Deletes the 143 `*_ex01..08` cases, which repeated the question and the gold of the `*_001` case of the same file. 1,258 to 1,115 cases. Writes `changelog/p02_composition.json`. |
| `p03_followups` | L1-012, L1-013, L1-025, L1-027, L1-028 | `period_a_*` gold keys that are not schema properties, sample sizes over the schema maximum, EN questions that changed a tool or a parameter, the stale `question_ko` copies, requests HOFINET cannot answer, conditions the gold tool cannot apply. |
| `p04_accounts` | L3-007, D03 | Replays `account_map.json`: every invented account id becomes a real HOFINET account that plays the same role. |
| `p05_predict_fraud` | C1-003, D12 | Re-applies the R3 and R7 mappings of commit 868fd28: 30 amounts onto the 48 HOFINET values, 34 golds off fund type 4. |
| `p06_relevance` | L1-001, L6-009, L3-011, D10 | 14 mislabelled abstention cases become tool cases, 8 defensible-either-way cases gain an alternative, the glossary and FIU questions ask for catalog content, `st_gl_008` uses a term the catalog holds. |
| `p07_boundaries` | L1-002 … L1-011, D11 | A discriminating cue in each of the 66 questions where two tools overlapped. |
| `p08_clarification` | L1-014, L1-015, L1-016, L1-018, D19 | One rule for what a clarification case is; STR drafts; required enum values; parameters the question left open. |
| `p09_contract1` | C1-011, L4-015 | `sql_contains` becomes `sql_conditions`, and every case that expects `query_transactions` gains an executable `expected.reference_calls.query_transactions.sql`. |
| `p10_executable_gold` | L1-016, D19 | Pins the required arguments eight gold calls still omitted, so they can be executed. |
| `p14_risk_score` | C1-003, D12 | 49 questions that asked for a fraud probability now ask for the risk score the tools return. |
| `p15_tool_cues` | L1-003, L1-010, D11 | The last eight questions whose wording fitted two gold tools. |
| `p16_executable_gold2` | L1-016, D19 | `st_mtool_084`, the one gold call that could not be executed. |
| `p17_boundary_parity` | L1-025 | Comparison words that mean the threshold the gold checks, in both languages. |
| `p18_str_drafts` | L1-014 | The three pre-existing STR drafts rebuilt from real HOFINET aggregates. |
| `p19_sweep_fixes` | L1-009, L1-013 | The three questions the closeout case sweep found. |
| `p20_terminology` | review ask A | One spelling per pattern term (ring, layering, funnel, structuring, smurfing) in both arms. |
| `p21_phrasing` | review asks C, D | Schema spellings out of the questions, and the phrasings the domain review flagged. |
| `p22_clarification_audit` | review ask B | Re-derives every `expect_clarification` case against D19 and checks it against the tool schema. Changes no data. |
| `p23_terminology_residue` | L1-010 | The terminology collision `p20` left in `st_fiu_001` and `st_mtool_106`, and one residue screen (`terminology.py`) over all four benchmark directories. |
| `p24_risk_score_tails` | C1-003 | The five English questions `p14` left ungrammatical. |
| `p25_catalog_gold` | L1-019 | Every FIU keyword and glossary term the gold pins, checked against the platform catalog: it selects rows, and the same rows however it is capitalised. Changes no data. |
| `p26_closeout_nits` | L1-016, L1-023, L2-015 | Five English near-duplicate pairs the round created, `st_acif_034`'s over-pinned `min_transactions`, two English fluency nits. |
| `p13_lint_fixes` | C1-011 | Whatever the linter reported after all the other passes had run. |
| `p11_difficulty` | L1-022, D23 | Relabels difficulty by an explicit rule. Writes `changelog/p11_difficulty_scores.json` with the points per case. |
| `p12_notes` | L1-026 | Regenerates every note from the final gold. |

## Tools that are not passes

* `build_account_map.py` — builds `account_map.json` from HOFINET and the platform's own graph
  code. It needs the database, and it must run on the **pre-p04** data, because it reads the
  invented ids out of the questions. It refuses to run once the data holds real ids. Re-run it
  only to change the mapping rule; `p04_accounts.py` replays the committed map without a database.
* `lint_benchmarks.py` — the pre-flight gate (`check_hofinet_compliance.py` delegates to it).
  Exits non-zero on any violation. `--no-db` skips the account existence check.
* `verify_gold_calls.py` — executes every gold call through the platform's own tool layer and
  reports the ones that answer nothing. Needs the platform and the database.

## Environment

The passes are plain Python and need nothing but the standard library. `build_account_map.py`,
`lint_benchmarks.py` (without `--no-db`) and `verify_gold_calls.py` need `duckdb`, `pandas`,
`networkx` and the companion platform checkout (`STAR_BENCH_WEB`, or a sibling directory).
`p25_catalog_gold` reads the platform's catalog module but no database, and it reports
itself skipped when the platform is not importable.

Every input a pass reads but does not derive is tracked in `inputs/`, so a clean clone can
replay the round; see `inputs/README.md`. `TERMINOLOGY.md` is the pattern-term convention
the questions follow and `terminology.py` is its executable copy.
