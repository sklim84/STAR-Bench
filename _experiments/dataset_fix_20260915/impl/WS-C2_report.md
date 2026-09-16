# WS-C2: the defects the closeout verification found in the code half

Scope: the ten new defects and the six still-open code issues in
`closeout/closeout_code.md`, plus the `sql_valid` scoring defect in the last
paragraph of `closeout/closeout_data.md`. Branch `audit-fixes` in both
repositories, 2026-09-16. Nothing under `benchmarks*/` or
`_experiments/scripts/data_fixes/` was touched: that is the other stream's.

## Finding -> commit -> verification

| # | finding | what it was | commit | verification |
|---|---|---|---|---|
| 1 | defect 1 (high), R1-R4 | `check_env` read `requirements-evaluation.txt`; the file is `requirements-eval.txt`, so no evaluation pin was ever checked and the cross-file numpy loop was dead. It reported "12 of 12 match" on an environment missing jinja2, matplotlib and openpyxl | `72fe3c6` | `tests_preflight/test_env_pins.py`, 8 tests: the named file exists and pins the six packages, a missing package is reported by name, a wrong version is reported, a cross-file conflict is named, a pin file that is not there is exit 2. Live: `check_env` now reads 16 pins (was 0) |
| 2 | closeout_data last paragraph | without sqlglot the fallback stripped the parentheses off the whole WHERE clause, so `IN (...)` never matched: st_qt_013 and st_qt_037 failed their own self-test (1256/1258) and any model SQL using IN scored unmet. A clause containing NOT was dropped whole | `005d98d` | `tests/test_scoring_sql.py`, 44 tests. IN / NOT IN / BETWEEN run through both parsers (`parser` fixture), and `test_both_parsers_read_the_same_atoms_from_the_same_statements` compares the atoms the two read from seven statements. Gate 1 check "the scorer parses SQL with sqlglot" reports the parser and the pinned version |
| 3 | defect 2 (medium) | `test_templates.py` skipped without jinja2 and gate 2 read only the exit status, so the D21/C2-007/C2-018 template repairs were never exercised by the committed report | `1b911d6` | gate 2 runs every suite with `-rs` and fails on a skip whose reason is not in `preflight/skips_allowed.json` (five release reasons: neo4j, app-only packages, the unreleased table and CSV, `_docs`). 5 tests in `test_report_and_allow_list.py`, including a suite that exits 0 with a jinja2 skip and now fails the check. jinja2, matplotlib and openpyxl were already in `requirements-eval.txt`; with them installed `test_templates.py` runs its 7 tests against `llama3_tools.jinja` and `phi4_mini_tools.jinja` and checks the published hashes |
| 4 | defect 3 (medium), R1-R3 | the registry runs concurrency 8 and D07 says 1; the justifying measurement existed only as prose in `WS-C_report.md` | `729138f` | `IMPLEMENTATION_SPEC.md` records the deviation under D07 with the reason and what stays unchanged; `preflight/run_plan.json` carries the batching-agreement run (`qwen35-4b-nt`, full single-turn, twice at 8 and once at 1, three output directories); `run_master.sh --agreement` runs it; gate 5 check "the concurrency deviation is declared and measured" fails while the registry default differs from the decision and the plan holds no such run. 6 tests in `test_serving_gate.py`. The agreement number is measured after the rerun |
| 5 | defect 4 (low) | `impl/gold_selftest_benchmarks{,_en}.json` said 1176/1258 with 82 defects while the data is 1258/1258 with none, and `AUDIT_FIXES_scoring.md` quoted them as current | `2c04c58`, `fb741e8` | the four reports are regenerated; `AUDIT_FIXES_scoring.md` carries the current table and says what the old defects were; gate 4 check "the committed gold self-test reports match a fresh run" compares each report's benchmark hash and headline counts with the self-test it already runs. It caught the data moving under `c519a77`/`dd32921` during this work, which is what it is for |
| 6 | defect 5 (low), C2-016 | `provenance.database.origin` and `.build_info` were always null: `collect()` read `connection_info()` before anything opened the connection | `f3492f1` | `test_guards.py::test_the_record_says_which_database_object_answered` asserts origin, both paths and a build_info with a parquet hash and a row count; `::test_a_run_whose_database_never_opened_is_refused` asserts `check_pin` refuses such a run |
| 7 | defect 6 (low), L5-024 | the multi-turn loop truncated a round to 8 calls with no error flag, unlike the single-turn loop | `aed836d` | `test_multiturn.py::test_a_turn_over_the_call_ceiling_is_recorded_as_one`: the round carries `call_limit` with the real call count, the record carries the error and `stop_reason` is `max_calls`; a turn within the ceiling carries none of it |
| 8 | defect 7 (low) | `--limit N` applied the limit after the expected key list was built, so every smoke run ended INCOMPLETE with exit 1 | `2629998` | `test_resume.py`: a limited run is `records: 2/2 (complete, limited to 2 of 3)` and exit 0, the manifest carries `limit`, `n_cases_run` and `n_cases_benchmark`, `--limit` with `--case-ids` is refused, and a run that really lost a record still exits 1. A resumed run is verified against its output directory, which reported INCOMPLETE for the same reason |
| 9 | defect 8 (low) | `loop.CLARIFICATION_REPLY` was a Korean sentence injected into every history, English arm included | `aed836d` | `CLARIFICATION_REPLIES` keyed by language, chosen by the run's query language falling back to the schema arm; three tests, including an end-to-end English run whose injected history carries the English reply and no Korean one |
| 10 | defect 9 (low) | `sql_valid` passed on an executed entry with `result=None, error=None`, the shape `scoring/legacy.py` produces | `66cc836` | `test_scoring_single.py`: that shape fails with evidence `unavailable`, a recorded result still passes, a recorded error still fails, and the legacy adapter no longer emits an executed entry for a checkpoint row with no result |
| 11 | C1-012 | a run record carried no hash of the benchmark case files; only the eval file did | `f3492f1` | the record carries `benchmark_dir`, `benchmark_sha256` and the file count, and the manifest the per-file hashes. `test_the_record_carries_the_hash_of_the_benchmark_files_it_read` asserts it equals `scoring.gold.load_benchmark(...).sha256`, so a record and an eval file compare |
| 12 | L5-021, defect 10 (partly) | the three OpenRouter drivers began with `cd /home/recordame/...` and ran a Python from a scratchpad; the guard read its log and pid from the same place; two e2e scripts pointed at another machine's checkout | `b9bca41` | all of them take the repository root from their own location, the way `run_benchmark.sh` does, with `$BENCH_PYTHON`, `$BENCH_CONCURRENCY`, `$OR_RUN_DIR`/`$OR_LOG`/`$OR_PIDFILE` and `$STAR_BENCH_ROOT`. `test_no_tracked_script_embeds_a_checkout_path` walks every tracked `.py` and `.sh` |
| 13a | R2C-005 | no analysis regeneration entry script | `9e6bbcd` | `regenerate_analysis.py`: 23 steps in the order of the paper, each naming what it produces and which manuscript object reads it, `--list`, `--only`, `--all`, `--results-root`, `--dry-run`, `--report`, and the one explicit `--copy-to-manuscript`. `--list` and `--all --dry-run` print all 23 |
| 13b | R2C-005 | `RQ4_query_tool_language_ablation.py` read `results_kr`/`results_en` as the Korean-tool cells while the table came from `results_or_kr_tools_kr`; no Korean-tools 2x2 path | `9e6bbcd` | cells are KR tools = `results_or_{kr,en}_tools_kr`, EN tools = `results_{kr,en}`; the retired `results_*_tools_en` arms are refused by name (D16); model ids matched on a normalised key across the gateway's lower-cased slugs. The table is 10 full 2x2 rows (KR-KR .855, EN-KR .843, KR-EN .857, EN-EN .804) where it was 0, with EXAONE-32B and A.X-4.0 waiting for their runs. Every cell and the output directory are options |
| 13c | L6-048 | `generate_reg_vs_analysis.py` fixed `ylim` at 0.95 and cut the highest marker (analysis h .955) in half | `09e4cb8` | the limits come from the data with a pad; the figure is regenerated (n=28, reg .559, ana .812, gap 25.3pp) |
| 13d | L3-001 | the appendix caption's "5,550 calls, 30 errors (0.5%)" came from a reader that never looked inside the JSON string the tool layer returns | `2ec0794` | `e2e_error_rates.py` reads the same 5,550 calls: 1,324 errors (23.9%) and 1,179 empty (21.2%), attributed by cause to platform 15.5%, data (no history for the account) 5.1%, model 3.2%, 0 unattributed. It reads both Contract 2 records and the old eval files, and writes JSON plus a markdown table |
| 13e | R2C-007 | four superseded scripts overwrote manuscript figures under the names the paper builds from, two of them writing outside the repository | `9cdd2c8` | `_figure_out.py` replaces the copied dual-save header: a live figure script writes into `_experiments/figures` only, and the manuscript copy is one explicit step. The four move to `archive/` with a README naming what replaced each, and write into `_experiments/figures/archive/`. Checked by running `generate_reg_vs_analysis.py` and confirming the manuscript copy was untouched |
| 14a | L6-042 | the platform README said the raw dataset is not included while the parquet and the model are tracked, and that timestamps are quantized | `69a5fc9` (Web) | the section says what is in the repository (parquet, detector, schema document), what is not (the pre-release CSV), and what the DuckDB copy is |
| 14b | C1-008 | `HOFINET.MD` section 1 described the old CSV and section 2 the Korean column names; the code-table source was not cited | `69a5fc9` (Web) | section 1 describes the released parquet with its sha256, size, codec and row count, measured from the file; section 2 is the released English schema with the original CSV name beside each column; sections 6.2 and 6.3 cite the KFTC D-testbed code table (2022-09) and say it is not distributed |

## Final verification

| check | result |
|---|---|
| STAR-Bench suites (`tests`, `tests_runner`, `tests_preflight`) | 333 passed, 0 skipped |
| platform suite (`STAR-Bench-Web`) | 495 passed, 15 skipped, 2 deselected; every skip is one of the five release reasons in `skips_allowed.json` |
| `gen_tools_kr --check` | `tools_kr.py` is up to date (23 tools) |
| `preflight.run --all --report` | gate 1 FAIL 8/9 (the 26 unpinned model revisions, the intended red gate), gate 2 PASS 5/5, gate 3 PASS 9/9, gate 4 PASS 10/10, gate 5 PASS 6/6, gate 6 SKIP |

The run above was made while the data stream was editing `benchmarks*/` in the
same checkout, so two further checks failed on that and not on anything here:
gate 1's "the tree is clean" (their uncommitted files) and gate 4's new
freshness check (the benchmark hash moved after the reports were written; the
counts it compares were identical, 1258/1258 and 50/50 with 0 defects). The
committed `impl/preflight_report.md` is therefore left as WS-F wrote it on a
clean tree; it predates the three checks added here (the SQL parser check in
gate 1, the report-freshness check in gate 4, the concurrency-deviation check in
gate 5). Regenerate it, and the four self-test reports, once the data stream's
last commit has landed:

```
for b in benchmarks benchmarks_en benchmarks_multiturn benchmarks_multiturn_en; do
  python -m _experiments.scripts.scoring.gold_selftest --benchmark $b \
      --out _experiments/dataset_fix_20260915/impl/gold_selftest_$b.json
done
python -m _experiments.scripts.preflight.run --all --report
```

Gate 1's one failure is the same one the closeout recorded; the pin check inside
it now passes on 16 evaluation pins where it used to check none, and the new SQL
parser check passes on the pinned sqlglot. Gate 4 gained the report-freshness
check and gate 5 the concurrency-deviation check.

## Left undone, and why

* **`data_fixes/account_map.json` and `new_cases/grounding.json`** still embed
  absolute paths (defect 10). They are data files under
  `_experiments/scripts/data_fixes/`, which another stream was editing
  throughout this work; the path guard test is scoped to tracked `.py` and `.sh`
  so it does not fail on them. Whoever owns that directory should strip the two
  paths.
* **The batching-agreement number** is not measured: it needs a served model,
  and no GPU was in scope. The run is in the plan, `run_master.sh --agreement`
  runs it, and gate 5 fails if it leaves the plan.
* **The 26 unpinned model revisions** are serving-host work (R2C-003): whoever
  downloads a model fills `model_revisions.json`, and the runner refuses to
  serve without it.
* **`RQ4`'s EXAONE-32B and A.X-4.0 rows** stay empty until those two
  configurations are run on the Korean tool arm; the script reports which cells
  have no eval files rather than silently averaging over what it has.
* **The remote-machine scripts** under `e2e_rerun/` and `goldfix_remote/` still
  carry `/home/mlp/...` and `/home/work/...` paths. Those are the record of what
  ran on co-authors' machines and are documented as such in their READMEs; only
  the two that are analysis readers (`e2e_analyze.py`, `check_lock.py`) were
  changed to resolve the root from their own location.
