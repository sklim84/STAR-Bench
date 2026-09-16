# Replay inputs

The inputs a pass reads but does not derive. They live here, tracked, so that a clean
clone can replay the whole correction round with

```bash
python -m _experiments.scripts.data_fixes.run_all --from 574c077
```

and reproduce `benchmarks/` and `benchmarks_en/` byte for byte. Before 2026-09-16 the
fix table sat in `_experiments/dataset_fix_20260915/`, which is internal audit material
and is gitignored, so the replay only worked on a machine that happened to still carry
that directory.

| file | read by | what it is |
|---|---|---|
| `fix_table_data.json` | `p01_apply_v3` | the approved single-turn fix table v3: per case the as-is question and gold and the approved to-be values (296 cases). The pass refuses to run when an as-is value no longer matches the data. |

Nothing else in `data_fixes/` reads outside the repository. `account_map.json`,
`new_cases/new_cases.json` and `new_cases/grounding.json` are next to the passes that
replay them, and the multi-turn build derives everything from `multiturn/scenarios*.py`
and the HOFINET database.
