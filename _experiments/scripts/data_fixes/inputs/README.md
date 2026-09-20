# Build inputs

The inputs a build step reads but does not derive, tracked so that a clean clone can
rebuild `benchmarks/` and `benchmarks_en/` without reaching outside the repository.

| file | what it is |
|---|---|

Nothing else here reads outside the repository. `account_map.json`,
`new_cases/new_cases.json` and `new_cases/grounding.json` sit next to the code that reads
them, and the multi-turn data is derived from `multiturn/scenarios*.py` and the HOFINET
database.
