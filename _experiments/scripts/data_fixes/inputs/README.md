# Build inputs

The inputs a build step reads but does not derive. They are tracked here so that a clean
clone can rebuild `benchmarks/` and `benchmarks_en/` without reaching outside the
repository.

| file | what it is |
|---|---|
| `fix_table_data.json` | The per-case table of the question and gold values that are pinned by hand rather than derived from HOFINET (296 cases). Each entry records both the value the data is expected to carry and the value the table pins, so a build step that applies it stops when the tree in front of it is not the tree the table was written for, instead of rewriting a value that is already correct. |

Nothing else here reads outside the repository. `account_map.json`,
`new_cases/new_cases.json` and `new_cases/grounding.json` sit next to the code that reads
them, and the multi-turn data is derived from `multiturn/scenarios*.py` and the HOFINET
database.
