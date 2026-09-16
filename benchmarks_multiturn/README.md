# Multi-turn STR Workflow Benchmark

Multi-turn benchmark built around the Suspicious Transaction Report (STR) drafting
workflow. It uses the same 23 AML tools as the single-turn set and evaluates the
investigation process up to STR drafting as a multi-turn dialogue.

- `cases_str_workflow.json` — 50 scenarios / 219 turns.
- English counterpart: [`../benchmarks_multiturn_en/`](../benchmarks_multiturn_en/).

Every account, institution, date, amount and channel in this file exists in
HOFINET, and every `tool_result` is the output of executing that turn's gold call
on the platform. The file is generated, not edited:

```bash
python -m _experiments.scripts.data_fixes.multiturn.build     # rebuild both languages
python -m _experiments.scripts.data_fixes.multiturn.verify    # checks and distribution
```

`_experiments/scripts/data_fixes/multiturn/scenarios*.py` holds the scenario
specs, and `rebuild_log.json` records, per scenario, the entities chosen and why.

## Scenario categories (`sub_category`)

| `sub_category`     | Definition                                                                 | Count |
|--------------------|----------------------------------------------------------------------------|-------|
| `base`             | All information is given; tools are called in sequence.                     | 14 |
| `missing_parameter`| A schema-required argument (or an unresolved reference to one) is missing, so the agent has to ask back before it can continue (D19). | 14 |
| `long_context`     | A value from an earlier turn's `tool_result` has to be carried into a later call. | 22 |

Turns per scenario: **4** in 32 scenarios, **5** in 17, **6** in 1 — 219 turns in
total. Of those, 200 expect a tool call, 14 expect the agent to ask back, and 5
expect an answer with no tool call (the scenarios where the evidence does not
support a report). 46 turns carry a `context_ref`. All 23 tools appear.

HOFINET fraud types across the 50 scenarios: type 1 (sudden change in
transaction pattern) 14, type 2 (transaction with new counterparty) 10, type 3
(split transaction) 10, type 4 (concurrent multiple transactions) 8, type 5
(same-day withdrawal after large deposit) 3, type 7 (late-night/early-morning
bulk transactions) 5.

## JSON schema

```jsonc
{
  "id": "mt_str_{nnn}",
  "scenario": "one-line scenario description",
  "sub_category": "base | missing_parameter | long_context",
  "fraud_type": 1,                       // HOFINET fraud type (1-5, 7; code 6 unused)
  "fraud_type_name": "string",
  "turns": [
    {
      "turn": 1,                          // 1-based
      "content": "user utterance",
      "tool_calls": [
        { "name": "tool name",
          "arguments": { "key": "expected value (parameter check)" },
          "reference_sql": "executable SQL, query_transactions only" }
      ],
      "reference_calls": {                // query_transactions only; the same SQL,
        "query_transactions": { "sql": "..." }   // in the shape the platform's
      },                                         // gold-call harness reads
      "tool_result": { ... },             // object | null — the real output of the gold call
      "context_ref": {                    // the value a later turn has to carry
        "from_turn": 1,                   // the turn whose result holds it
        "key": "result[0].sender_acc",    // a path inside that turn's tool_result
        "to_param": "account_id"          // the argument of THIS turn that receives it
      },
      "expect_clarification": false,      // true → asking back is correct
      "note": "what the turn tests"
    }
  ]
}
```

### Field notes

- **`tool_calls`** — the gold tool and the parameter checks for the turn. An empty
  array means no tool call is the correct behaviour: either a clarification turn
  (`expect_clarification`) or a turn where the analysis does not support a report.
  There are no alternative gold calls: every question has exactly one gold tool
  (D11).
- **`arguments`** — platform parameter names in both language files (Contract 1).
  For `query_transactions` the checks are `sql_conditions` (a list of
  `{column, op, value}` predicates the model's SQL must restrict on) and
  `sql_valid`; the executable statement is `reference_sql`.
- **`tool_result`** — what the platform really returns for the gold call, with the
  platform's English result keys. `null` on turns with no tool call.
- **`context_ref`** — `key` resolves inside the source turn's real result and
  `to_param` is an argument the gold call of this turn really takes.
- **`generate_str`** — the gold carries `summary`, `fraud_type` (the STR form §VI
  classification the tool's enum accepts) and `tools_used`. It carries no
  `fraud_probability`: the tools return an uncalibrated risk score, not a
  probability, and the scorer excludes both `summary` and `fraud_probability`
  from parameter accuracy.

## Evaluation

Scoring is `_experiments/scripts/scoring/`; the metric definitions are in that
package's `README.md`. Per turn: h, r, p, a, f1_tools, `context_hit`,
`clarification_ok`, `error_type`. Per scenario: **c** (every turn has h = 1) and
`context_accuracy`.

```bash
PYTHONPATH=. python -m _experiments.scripts.benchmark_multiturn \
  --models <MODEL> --output _experiments/results_mt/
python -m _experiments.scripts.scoring.gold_selftest --benchmark benchmarks_multiturn
```

The gold self-test renders each gold annotation as a run record and scores it;
this file scores 50/50 perfect in both the oracle and the end-to-end setting.

## Scripted execution

1. Send the system prompt and the 23 tool definitions.
2. Send turn 1 `content`; score the model's call.
3. Inject the turn's `tool_result` into the conversation history.
4. Send the next turn's `content` with the prior history, and repeat.

In the oracle setting the results are injected from this file, so tool-calling
ability is measured independently of upstream errors. In the end-to-end setting
the runner executes the model's own calls and `context_hit` is judged against
what those calls returned.

## STR narrative coverage

Each gold `generate_str.summary` follows the Korean FIU STR §VII narrative form
(seven sub-sections on the 5W1H principle) and states only figures that the
scenario's own tool results carry. Over the 45 scenarios that end in an STR,
keyword coverage of the mandatory sections averages **0.932**: subjects 0.978,
date 0.889, place 0.867, instrument 1.000, method 1.000, grounds 1.000, 5W1H
summary 0.789. Date and place are below 1.0 in the scenarios whose tools are not
date-scoped or carry no institution (`get_receiving_account_profile`,
`detect_smurfing_network`, `detect_dormant_reactivation`). The figures are
recomputed by `verify.py` with the same patterns the analysis script uses.

## English version

[`../benchmarks_multiturn_en/cases_str_workflow.json`](../benchmarks_multiturn_en/)
carries the same 50 scenarios with `content`, `scenario`, `fraud_type_name` and
`note` in English; `tool_calls`, `reference_calls`, `tool_result` and
`context_ref` are identical to this file, so the two differ only in the language
of the conversation. Both files are written by the same build pass, keyed by
scenario id and turn number.
