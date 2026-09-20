# STAR-Bench scoring

This package turns run records and gold annotations into eval files. Runners do not score: they
record what the model did, and scoring happens afterwards, so a scoring rule can change without
re-running a model.

```
python -m _experiments.scripts.scoring.score_runs \
    --runs   <dir of *.jsonl run records> \
    --benchmark benchmarks \
    --out    <dir for eval files>
```

The metric definitions below are the implementation, and they are the definitions the paper uses.

## Notation

For one case, `C` is the list of tool calls the model made, in the order it made them, across all
rounds of that case. `G` is the gold tool set (`expected.tools_must_include`, plus
`expected.primary_tool` when it is not already in that list). A case whose gold tool set is empty is
an abstention case; a case with `expected.expect_clarification` is a clarification case.

## Per-case metrics

**h (tool selection).** `h = 1` when every tool in `G` appears among the names in `C`, otherwise 0.
Extra tools do not change h; they are visible in `f1_tools`, in `p` and in the `over_call` error
type. For an abstention or clarification case, `h = 1` when the model made no tool call and its final
text is non-empty and is not an unparsed tool call.

**r (tool recall).** Fraction of `G` that appears in `C`. Undefined (null) for abstention and
clarification cases.

**p (precision).** Per case, the fraction of calls in `C` whose name is in `G`; null when the model
made no call. The aggregate `p_micro` is the total number of gold-tool calls divided by the total
number of calls over the run, reported with `n_calls`. A model that never calls a tool has no
precision rather than a perfect one.

**f1_tools.** F1 between the SET of called tool names and `G`. For an abstention case it is 1 when
no tool was called and 0 otherwise. A policy that calls all 23 tools on every case reaches h = 1 with
f1_tools below 0.1.

**a (parameter accuracy).** Mean score of the parameter checks of the case, null when the case has no
checks. The aggregate averages only over cases with checks and reports that n. A check that concerns
a tool the model never called counts as failed, so a = 0 rather than null for a case that has checks
and no matching call.

**o (order).** Null unless `expected.tool_order` is present and every tool in it was called. When it
is defined, o = 1 when the first occurrences of the ordered tools are in strictly increasing call
position, and 0 otherwise. Reordered duplicates and reversed orders score 0.

**abstain_ok / clarification_ok.** True when the model made no tool call and the final text is
non-empty and not an unparsed tool call. Empty text, or text that is a tool call the runner failed to
parse, is a `parse_fail`, not a success. Text is recognised as an unparsed tool call when it carries
tool-call markup (`<tool_call>`, `[TOOL_CALLS]`, `<|python_tag|>`, `<function=`, `to=functions.`) or
contains a JSON object with a `name` and an `arguments` or `parameters` field.

**error_flag.** True when the run record carries an error or stopped with `error`. Calls the model
made before the error are still scored.

**hallucinated_param_count.** Number of argument keys, over all calls, that are not properties of
that tool's schema. A valid optional argument such as `hops` is not hallucinated.

**error_type.** One label per case, in this order of precedence:

| label | meaning |
|---|---|
| `correct` | h = 1, a is null or 1, o is null or 1, and no tool outside `G` was called |
| `length_stop` | the run stopped because the output budget ran out |
| `system_error` | the run record carries an error (transport, gateway, template, missing record) |
| `parse_fail` | no call was made and the final text is empty or is an unparsed tool call |
| `no_call` | tool case, no call at all |
| `wrong_tool` | calls were made, none of them is in `G` |
| `missing_tool` | some but not all of `G` was called |
| `param_error` | every gold tool was called, a check failed |
| `order_error` | tools and parameters right, `tool_order` violated |
| `over_call` | tools and parameters right, tools outside `G` were also called |

Each label names the failure it describes. An older label set conflated them: `missing_param` meant a
missing tool, `other` meant over-calling, and both no-call and wrong-tool were `wrong_func`.

## Parameter checks

Every check of one gold call spec is evaluated against the SAME model call, and the call that
satisfies the most checks is the one that counts. Two gold specs for one tool never take the same
model call. A model cannot pass one check with a first call and another check with a second call.

Before comparison, arguments the model omitted are filled from the tool schema defaults, so a call
that relies on `dormant_days = 180` or `unit = "monthly"` is judged the same as one that writes the
default out.

| check | rule |
|---|---|
| plain argument | typed equality, see below |
| `sql_conditions` | every `{column, op, value}` must appear as a restricting predicate of the model SQL |
| `sql_valid` | the model SQL executes on HOFINET without an error |
| `hops_min`, `hops_max` | the `hops` argument must be an integer within the bound |
| `result_row_count_min/max`, `result_contains` | read the executed tool result, English keys (`result`, `total_count`) |
| `keyword` (FIU), `term` (glossary) | compared by the catalog rows the value selects |

**Typed equality.** Values are compared against the tool schema type. Numbers compare numerically and
exactly, so 3.9 is not 3 and 20240101.9 is not 20240101. Booleans compare only with booleans, so True
is not 1. Strings compare after stripping, and case-insensitively when the schema declares an enum,
so `"Monthly"` matches `"monthly"`. A numeric string matches a numeric gold value (`"78432"` matches
78432), while a formatted one (`"78,432"`) or a differently formatted date (`"2024-01-01"` against
20240101) does not. A list-valued gold argument is compared as set recall of the gold items, so an
extra item does not cost anything and a missing one costs proportionally. An object argument is
compared key by key. A list or object sent as a JSON string is parsed first, because the tool layer
accepts it that way.

**SQL conditions.** Predicates are read with sqlglot (pinned, see `requirements.txt`) from every
WHERE and HAVING clause of the statement, including subqueries and CTEs, but only along AND-only
paths: a comparison under OR, or under NOT other than `NOT col = v`, does not restrict the result and
never satisfies a condition. `=` is also satisfied by `IN (v)` with one value, `>=` and `<=` by the
matching side of a BETWEEN, and a BETWEEN condition by the pair of `>=` and `<=` predicates. When
sqlglot cannot parse the text, or is not installed, a regex fallback reads `col op literal` terms
from every WHERE and HAVING clause, subqueries included: it delimits each clause by parenthesis
depth, splits on AND at depth 0, unwraps `CAST(col AS t)` and `col::t`, and gives up on a clause
whose OR is at the clause's own level. It drops the single terms it cannot read rather than the
clause, and reports them: a condition check that fails while such a term was dropped says so and
names the sqlglot pin, so a failure caused by the environment cannot be read as a data defect. Both
parsers read the same atoms from every reference statement in the benchmark, which is a test. This
replaces the substring test, under which `sql_contains: ["4"]` was satisfied by the year 2024 or by
`LIMIT 10`, and a keyword inside a comment or a string literal counted as a condition. The same rule
is used for single-turn and multi-turn.

**sql_valid.** Taken from the executed result recorded in the run when there is one, and otherwise by
executing the model SQL read-only through the platform's own `query_transactions` tool. The check
passes when the tool returns no `error`.

**Free-string reference arguments.** `lookup_fiu_reference_types(keyword)` and
`get_aml_glossary(term)` are pure functions of a static catalog, so the check compares the rows the
model's value selects with the rows the gold value selects, using the platform catalog functions.
`non-face-to-face` therefore passes against `Non-face-to-face`, and `virtual assets`, which selects
nothing, fails against `virtual asset`. When the gold value itself selects no row, the check falls
back to case-insensitive string equality and the case is flagged for the data owners.

**Arguments that are not compared.** `generate_str.summary` (free narrative) and
`generate_str.fraud_probability` (a number the tools do not produce) are excluded from a.

**Malformed calls.** Arguments that are not a JSON object (a list, an unparsable string) make every
check of that call fail; they never raise. A tool name carrying a serving artefact, such as the
Harmony suffix in `query_transactions<|channel|>commentary` or a `functions.` recipient prefix, is
normalised to the tool name for h, r, p and a, and the raw name is reported in `parser_artifacts` so
the parser problem is counted as a parser problem and not as a separate tool.

**Alternatives.** `expected.alternatives` holds further acceptable behaviours, either
`{"abstain": true}` or a `{tools_must_include, param_checks}` block. The case is scored against the
primary gold and against each alternative, and the best result is kept; `matched` names the winner.

## Multi-turn

Turns are scored with the same comparison module. Per turn: h, r, p, a, f1_tools, context_hit,
clarification_ok, error_type, turn_error. Per scenario:

**c (scenario completion).** `c = 1` when every turn of the scenario has h = 1. One definition, in
the code and in the paper. A turn with no run record counts as a failed turn and is listed in
`missing_turns`.

**context_hit.** Defined only for turns with a `context_ref`. The referenced value is looked for in
the call to the EXPECTED tool; the same argument in some other tool's call does not count. In the
oracle setting the expected value is read from the gold `tool_result` of the source turn. In
the end-to-end setting it is read from the run's OWN executed result for that source turn, so a model
that correctly carried forward the value its own call produced is credited, and the parameter check
for that argument uses the same value. When the source turn executed nothing usable, the reference is
not applicable: context_hit is null and the affected check is left out of a. When the reference
points at an argument in a SQL call, the value must appear as a whole token in the model's SQL, and
gold conditions carrying the source value are rewritten to the value the run produced.

**context_accuracy** is the mean of context_hit over the turns where it is defined, with n.

## Aggregates

Every aggregate carries the n it was computed over: `{"mean": ..., "n": ...}` for means,
`{"mean": ..., "n_calls": ..., "n_cases_with_calls": ...}` for `p_micro`. Aggregates are also
reported by category and by difficulty (single-turn) and by sub-category (multi-turn). The eval file
records coverage: how many gold cases had no record (`missing_case_ids`), records with no gold case
(`unknown_case_ids`), and whether the run is complete.

## Which benchmark a run was scored against

Every record carries `provenance.benchmark_sha256`, the digest of the `cases_*.json` files the run
was asked about. `score_runs.py` compares it with the directory it was given and refuses the whole
command when they differ, naming both: scoring the Korean arm against `benchmarks_en` would otherwise
succeed silently and write an eval whose provenance hash and whose gold came from different data. The
result of that comparison is in every eval file as `meta.scorer.benchmark_check`
(`match`, `mismatch`, or `not_recorded` for records written before the digest existed, which are
scored with a warning). `--allow-benchmark-mismatch` scores a mismatch anyway and records the
override, the status and both hashes in the eval file.

## Gold self-test

```
python -m _experiments.scripts.scoring.gold_selftest --benchmark benchmarks --out report.json
```

Renders every gold annotation as a run record and scores it. Gold that is internally consistent
scores perfectly; anything else is a data defect and is listed in the report, separating blocking
defects (a check the gold call cannot pass, a gold key that is not a schema property) from advisories
(a gold call that is not executable because a required argument is not pinned, a gold catalog value
that selects nothing). It takes any benchmark directory, so the same command checks the rebuilt data.

## Legacy checkpoints

`legacy.py` converts checkpoints written by the earlier runner into run records, for regression
comparison only. Single-turn checkpoints stored neither arguments nor final text, so converted
single-turn records mark every parameter check not applicable (a is null) and fall back to judging
abstention by "no tool call" alone. Multi-turn checkpoints kept the model's arguments, and the
end-to-end ones kept executed results, so those convert fully.

## Requirements

`sqlglot` (pinned in `requirements.txt` next to this file) and the companion platform checkout for
the tool schema, the catalog and the query database. `score_runs.py --no-sql-exec` scores without a
database, using only results recorded in the run; `--no-catalog` falls back to string comparison for
the two reference arguments. The scorer never calls a model or a network service.
