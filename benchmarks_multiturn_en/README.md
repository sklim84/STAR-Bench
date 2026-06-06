# Multi-turn STR Workflow Benchmark (English)

English version of [`../benchmarks_multiturn/`](../benchmarks_multiturn/). Only the
natural-language fields (`content`, `scenario`, `fraud_type_name`, `note`) are
translated to English; the tool interface (`tool_calls`, `tool_result`,
`context_ref`, including Korean parameter/result keys) is byte-identical to the
Korean set — the "English query + Korean tool interface" setting, consistent with
the single-turn `benchmarks_en/`.

Regenerated deterministically by `_experiments/scripts/build_multiturn_en.py`.
See the Korean directory's `README.md` for the schema and evaluation metrics.

```bash
PYTHONPATH=. python -m _experiments.scripts.benchmark_multiturn \
  --models <MODEL> --cases-dir benchmarks_multiturn_en --output _experiments/results_mt_en/
```
