# Benchmark build and validation tooling

The four benchmark directories (`benchmarks/`, `benchmarks_en/`,
`benchmarks_multiturn/`, `benchmarks_multiturn_en/`) are built and checked from this
package. The data files carry no hand edits, so every value in them can be traced back to
HOFINET, to the platform tool schema or to the platform catalog, and the composition the
paper reports can be re-derived instead of taken on trust.

The name of the directory is historical; what lives here is the benchmark's build and
validation tooling, not a set of one-off edits.

## The tools

| tool | what it does |
|---|---|
| `lint_benchmarks.py` | The gate the single-turn data has to clear: gold keys against the tool schema, argument values against HOFINET, the two languages against each other, and the wording convention. Exits non-zero on any violation, so it can block a run. `--no-db` skips the account existence check. `check_hofinet_compliance.py` at the top of `scripts/` is an alias for it. |
| `verify_gold_calls.py` | Executes every gold call through the platform's own tool layer and reports the ones that answer nothing, because a call that returns an error or an empty result cannot be the reference answer to the question that asks for it. Needs the platform and the database. |
| `terminology.py` | One spelling per AML pattern term, and the screen that enforces it over all four benchmark directories. `TERMINOLOGY.md` states the same convention in prose. |
| `build_account_map.py` | Derives `account_map.json`: one real HOFINET account per account id a question names, chosen to satisfy every role that id plays across the cases that use it. Needs the database. |
| `account_map.json` | The committed map, so the account assignment can be read and re-checked without a database. |
| `common.py` | Benchmark IO shared by everything here: the `Bench` container, which keeps cases file by file so their order survives a round trip, and the change-log format. |
| `new_cases/` | The single-turn cases as code: the questions, the gold, the HOFINET facts they are written against, and the checks that every gold executes and that no two cases ask the same question. |
| `multiturn/` | The multi-turn benchmark as code: the scenario specs, the builder that executes every gold call against the platform, and the verifier. |
| `inputs/` | Inputs a build step reads but does not derive, tracked so a clean clone can reproduce the data. |

## Checking a tree

```bash
python -m _experiments.scripts.data_fixes.lint_benchmarks
python -m _experiments.scripts.data_fixes.verify_gold_calls
python -m _experiments.scripts.data_fixes.new_cases.verify --gate
python -m _experiments.scripts.data_fixes.multiturn.verify
python -m _experiments.scripts.scoring.gold_selftest
```

Each check is independent of how the data was produced: it reads the committed files and
reports what does not hold. `lint_benchmarks` is the one that gates, so it is the one the
pre-flight run calls.

## Environment

Reading and linting the data needs nothing but the standard library. `build_account_map.py`,
`lint_benchmarks.py` (without `--no-db`), `verify_gold_calls.py`, the multi-turn build and
the new-case verification need `duckdb`, `pandas`, `networkx` and the companion platform
checkout (`STAR_BENCH_WEB`, or a sibling directory). The catalog checks read the platform's
catalog module but no database, and they report themselves skipped when the platform is not
importable, so the linter still runs on a machine that carries only this repository.
