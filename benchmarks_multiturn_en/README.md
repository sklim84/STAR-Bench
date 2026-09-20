# Multi-turn STR Workflow Benchmark (English)

English version of [`../benchmarks_multiturn/`](../benchmarks_multiturn/). The
same 50 scenarios and 219 turns, with `content`, `scenario`, `fraud_type_name`
and `note` in English. The tool interface (`tool_calls`, `reference_calls`,
`tool_result`, `context_ref`) is identical to the Korean file, so the two differ
only in the language of the conversation, and the gold `generate_str.fraud_type`
keeps the platform's own Korean §VI enum value in both.

Both files are written by one build pass, keyed by scenario id and turn number:

```bash
python -m _experiments.scripts.data_fixes.multiturn.build
python -m _experiments.scripts.data_fixes.multiturn.verify   # asserts the parity
```

See the Korean directory's `README.md` for the schema and the evaluation.

```bash
PYTHONPATH=. python -m _experiments.scripts.benchmark_multiturn \
  --config <CONFIG_ID> --tools-lang en --query-lang en --setting oracle \
  --out _experiments/runs/mt_oracle_en/<CONFIG_ID>
```
