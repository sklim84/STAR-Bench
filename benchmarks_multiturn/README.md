# Multi-turn STR Workflow Benchmark

Multi-turn benchmark built around the Suspicious Transaction Report (STR) drafting
workflow. It uses the same 23 AML tools as the single-turn set and evaluates the
investigation process up to STR drafting as a multi-turn dialogue.

- `cases_str_workflow.json` — 50 scenarios / 219 turns.
- English counterpart: [`../benchmarks_multiturn_en/`](../benchmarks_multiturn_en/)
  (only the natural-language fields are translated; the tool interface is kept
  identical — see *English version* below).

## Scenario categories (`sub_category`)

| `sub_category`     | Definition                                                                 | Turns |
|--------------------|----------------------------------------------------------------------------|-------|
| `base`             | All information is given; tools are called sequentially.                    | 3–5   |
| `missing_parameter`| A required parameter is missing → the agent must ask back → retry.          | 4–6   |
| `long_context`     | A value from a prior turn's `tool_result` must be carried into a later call.| 4–6   |

Distribution: `base` 14, `missing_parameter` 14, `long_context` 22.

## JSON schema

```jsonc
{
  "id": "mt_str_{nnn}",
  "scenario": "one-line scenario description",
  "sub_category": "base | missing_parameter | long_context",
  "fraud_type": 1,                       // anomaly-type code (1–7)
  "fraud_type_name": "string",
  "turns": [
    {
      "turn": 1,                          // 1-based
      "content": "user utterance",
      "tool_calls": [
        { "name": "tool name", "arguments": { "key": "expected value (param check)" } }
      ],
      "tool_calls_alt": [ ... ],          // optional: alternative acceptable call(s)
      "tool_result": { ... },             // object | null — mock result injected into history
      "context_ref": {                    // long_context turns only
        "from_turn": 1,                   // earlier turn that produced the value
        "key": "key inside that turn's tool_result",
        "to_param": "argument key of THIS turn that must receive the value"
      },
      "expect_clarification": false,      // true → asking back (no tool call) is correct
      "note": "evaluation point (optional)"
    }
  ]
}
```

### Field notes
- **`tool_calls`** — the tool(s) and expected parameters for the turn. An empty array
  `[]` means *not* calling a tool is correct (the ask-back turn of `missing_parameter`).
  Multiple entries mean several tools must be called in one turn.
- **`tool_result`** — a realistic HOFINET-based mock response the evaluator injects into
  the conversation history; it is the source data referenced by the next turn's
  `context_ref`. `null` on turns with no tool call.
- **`context_ref`** — used only in `long_context`; checks that a specific value from a
  prior turn's `tool_result` was carried correctly into this turn's arguments.
- **`expect_clarification`** — `true` when the correct behavior is to ask the user back
  instead of calling a tool (first turn of `missing_parameter`).

## Evaluation metrics

Per turn (same formulas as the single-turn set):
- `h` — tool selection accuracy (`tool_calls[].name` match)
- `a` — parameter accuracy (`tool_calls[].arguments` match)
- `s` — composite score (weighted sum)

Per scenario (multi-turn specific):
- `avg_s` — mean of per-turn `s` (directly comparable to single-turn `s`)
- `context_accuracy` — accuracy of the carried value on `context_ref` turns
- `scenario_complete` — `true` iff every turn has `s > 0.5`

## Scripted execution

1. Send the system prompt + 23 tool definitions.
2. Send turn 1 `content`; receive the model response → score `tool_calls`.
3. Inject the ground-truth `tool_result` into the conversation history.
4. Send the next turn's `content` (with prior history) and repeat.

Tool results are pre-injected each turn so tool-calling ability is measured
independently of upstream errors.

```bash
PYTHONPATH=. python -m _experiments.scripts.benchmark_multiturn \
  --models <MODEL> --output _experiments/results_mt/
```

## STR narrative coverage

Each ground-truth `generate_str.summary` follows the Korean FIU STR §VII narrative
form (seven sub-sections based on the 5W1H principle). Over the 45 scenarios that
include a `generate_str` turn, keyword-matching coverage of the mandatory narrative
sections averages **0.704**: the four core sections (subjects, methods, grounds,
5W1H summary) all exceed 80%, while *date* and *instrument* (60%) and *branch & place*
(17.8%) are lower because HOFINET anonymizes institutions/branches to serial numbers.
Full per-section figures are reported in the paper (Appendix: *STR Narrative Coverage*,
`tab:str_section_coverage`).

## English version

[`../benchmarks_multiturn_en/cases_str_workflow.json`](../benchmarks_multiturn_en/)
mirrors this set with the natural-language fields (`content`, `scenario`,
`fraud_type_name`, `note`) translated to English, while the tool interface
(`tool_calls`, `tool_result`, `context_ref`, including Korean parameter/result keys)
is byte-identical — the "English query + Korean tool interface" setting, consistent
with the single-turn `benchmarks_en/`. It is regenerated deterministically by
`_experiments/scripts/build_multiturn_en.py`. Run it with `--cases-dir`:

```bash
PYTHONPATH=. python -m _experiments.scripts.benchmark_multiturn \
  --models <MODEL> --cases-dir benchmarks_multiturn_en --output _experiments/results_mt_en/
```
