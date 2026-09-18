# Porting an analysis step to the scored rerun

Every step reads `_experiments/scripts/analysis/load.py` and nothing else from the
results trees. Read `load.py` first: its docstring says why the pre-audit keys are
not coming back.

## The reader

```python
from _experiments.scripts.analysis import load

cases              = load.single()                    # 1 row per (config, case)
cases              = load.single(column="entools_krq")   # 2x2 arms: entools_krq | krtools_enq | entools_enq
scenarios, turns   = load.multiturn("oracle")         # or "e2e"
calls              = load.calls("single")             # 1 row per tool call, with arguments and tool output
agg                = load.aggregates("single")        # {config_id: the scorer's own aggregate}
todo               = load.missing()                   # which of the 28 are not scored yet
cfgs               = load.configs()                   # the serving registry as a table
```

`load.single()` columns include `config_id label group model reasoning_mode
is_reasoning case_id category difficulty h r p a o f1_tools abstain_ok
clarification_ok error_type error_flag stop_reason matched n_calls n_gold_calls
n_checks called_tools gold_tools extra_tools hallucinated_param_count`.

`load.multiturn()` gives scenarios with `c h_mean a_mean context_accuracy
sub_category n_turns` and turns with `turn h a context_hit clarification_ok
called_tools gold_tools`.

## What each old name becomes

| old | new | note |
|---|---|---|
| `primary_tool_hit` | `h` | 0/1, already the paper's primary metric |
| `tool_recall` / `tool_precision` | `r` / `p` | `p` is null when the model called nothing, not 1.0 |
| `param_accuracy` | `a` | null when the case has no parameter checks, not 1.0 |
| `order_score` | `o` | null when order does not apply |
| `param_check_details` | `checks` | |
| `id` | `case_id` | |
| `score` (weighted) | **gone** | see below |
| per-turn `tool_hit` | `h` | |
| `scenario_complete` | `c` | |
| `avg_tool_hit` / `avg_param_accuracy` | `h_mean` / `a_mean` | |
| `overall.primary_tool_hit_rate` | `cases["h"].mean()` or `agg[cfg]["h"]["mean"]` | the two agree; a test checks it |
| `by_category[t].aggregated.primary_tool_hit_rate` | `cases.groupby("category")["h"].mean()` | |
| `think` (bool) | `reasoning_mode` | T and NT are separate `config_id`s |

## Five rules

1. **`score >= 0.9` becomes `h == 1`.** The weighted score has no definition in
   the paper (D02) and is not reproducible. Every step that thresholded it wanted
   "did this case come out right", and that is `h`. Say so in the step's header.
2. **Null is not zero and not one.** Take means over the non-null rows and report
   the count: `a.dropna().mean()` with `a.notna().sum()`. Contract 3 asks every
   aggregate to carry its n, so write the n into the output next to the number.
3. **The cohort is the registry, not a list in the file.** Delete every
   `EXCLUDE_MODELS` / `COHORT` / `_CANONICAL_NAMES` / `GROUPS` / `ROWS` literal.
   Rows come from `load.single()`; display names from `label`; grouping from
   `group`; ordering from the metric unless the step needs the registry order.
   A step that needs a subset selects it by `group` or by an explicit,
   commented reason, never by a list of names that drifts from the registry.
4. **Say when the cohort is incomplete.** 18 of 28 configurations are scored
   today. Every output carries `n_configs` and the ids that were missing, taken
   from `load.missing()`. A figure that silently draws 18 rows under a caption
   that says 28 is the failure this rule exists to prevent.
5. **The error taxonomy changed.** Old `{correct, wrong_func, hallucinated_call,
   api_error, wrong_value, missing_param, other}` is now `{correct, no_call,
   wrong_tool, missing_tool, over_call, param_error, order_error, length_stop,
   system_error}`. There is no mapping; use the new names. `wrong_func` is
   `wrong_tool`.

## Keep

- The output file names and formats. A manuscript object reads them by name.
- The statistics: bootstrap iterations and seeds, Wilson intervals, McNemar.
- The figure style. Only the input section changes.

## Paths

Resolve every path from the repository root, which is
`Path(__file__).resolve().parents[3]`, never from the working directory.
`_figure_out.install()` stays where it is already used.
