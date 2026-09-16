# Pre-flight gates

Register step 10, issue L5-003. Everything that has to be true before the rerun
starts, in one command:

```bash
python -m _experiments.scripts.preflight.run --all --report
```

Gates run in order, all of them run even when an early one fails, and the exit
status is non-zero if any of them failed. Nothing here repairs anything: a gate
that fails names the file and the id, and the stream that owns it fixes it.

| | Gate | What it reads |
|---|---|---|
| 1 | environment | `_experiments.env.check_env`, the platform import, the platform commit and cleanliness, the parquet and database sha256, the `hofinet` column names, the Streamlit stub flag, the model revision pins |
| 2 | code tests | the platform suite, `_experiments/scripts/tests`, `tests_runner`, `tests_preflight`, and `gen_tools_kr --check` |
| 3 | benchmark data | the single-turn linter, `data_fixes.multiturn.verify`, `new_cases.verify --gate`, KR/EN parity, the case counts, duplicate questions |
| 4 | gold answers | `scoring.gold_selftest` on all four directories, and every gold call executed through the platform harness |
| 5 | serving readiness | the registry against the run plan, registry completeness, published template hashes, tensor-parallel size against the hosts, the Korean prompt budget per configuration |
| 6 | canary | a fixed sample through the runners against a served model, then the anomaly gates |

## Options

```bash
--only env,tests,data,gold,serving   run a subset
--configs qwen35-4b-nt,phi-4-mini    check the revision pins of these configurations only
--serving-stack                      also check the serving dependency pins (on the serving host)
--platform-python /path/to/python    when the platform stack has its own interpreter
--report                             write reports/preflight_report.md and .json
--update-allow-list                  rewrite allow_empty.json from this run, for review
--update-gold-expected               rewrite gold_selftest_expected.json from this run
```

## The canary

```bash
python -m _experiments.scripts.preflight.run canary --config <id> \
  --base-url http://127.0.0.1:11434/v1
python -m _experiments.scripts.preflight.run canary --mock          # no GPU
```

It runs `canary_sample.json` (40 single-turn cases covering all 23 tools, plus one
scenario per multi-turn sub-category) through `benchmark.py` and
`benchmark_multiturn.py` as a `--partial` run into a fresh directory, then reads
the shape of the output rather than the score. `--rebuild-sample` regenerates the
sample by its documented rule.

## Files

| File | What it is |
|---|---|
| `run.py` | the command; `gates` is the default subcommand, `canary` the other one |
| `gate.py` | the gate framework: a check carries the exact command it ran |
| `environment.py`, `code_tests.py`, `data.py`, `gold.py`, `serving.py`, `canary.py` | one gate each |
| `report.py` | the markdown and JSON reports |
| `_probe.py`, `_gold_driver.py`, `_budget_driver.py` | the three things that run in their own process, so a platform import error is a failed check rather than a traceback |
| `expected_counts.json` | the case counts the write-up reports; a stream that adds cases updates it |
| `gold_selftest_expected.json` | what a fresh gold self-test must produce per directory, with the benchmark sha256 it was produced from; gate 4 regenerates and compares |
| `reports/` | the last `--report` run: `preflight_report.md` and `.json`, tracked |
| `allow_empty.json` | the gold calls that answer nothing, case by case with the reason |
| `run_plan.json` | the configurations and columns the rerun covers, and the hosts it has |
| `thresholds.json` | the canary's anomaly thresholds, each with the measurement it came from |
| `canary_sample.json` | the fixed sample |

Everything a gate reads is inside this package, so `--all` runs in a clean clone
of the branch. A data change that moves the gold self-test counts refreshes
`gold_selftest_expected.json` in the same commit:

```bash
python -m _experiments.scripts.preflight.run --only gold --update-gold-expected
```

Regenerating the report with `--report` modifies two tracked files; commit or
discard them, because gate 1 reads a modified tracked file as a dirty tree (it
says when the only modified files are the report itself).

Tests: `_experiments/scripts/tests_preflight`.
