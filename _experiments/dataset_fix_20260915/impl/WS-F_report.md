# Audit fixes: the pre-flight gate suite (WS-F)

Branch `audit-fixes` in `STAR-Bench`. Scope: register step 10, issue L5-003, and the final
integration check across the other streams' work.

Files owned by this stream: `_experiments/scripts/preflight/` and
`_experiments/scripts/tests_preflight/`, plus one section in the repository `README.md`.
Nothing else was touched: where a gate found a problem it is reported below, not patched.

## Commits

| commit | content |
|---|---|
| `66a3821` | gate framework, gates 1 to 3 (environment, code tests, benchmark data) |
| `51857ea` | gates 4 and 5 (gold answers, serving readiness) and the empty-result allow-list |
| `14676ed` | gate 6 (the canary) and its anomaly thresholds |
| `b4965ed` | the `run` command, the written report, 41 tests |
| `bccb6a6` | package README, the repository README section, two reporting fixes |
| `b81ddfe` | top-level `--help` lists both subcommands |
| `764eb35` | the canary record count in the threshold sources, this report and the generated `impl/preflight_report.md` |

## The command

```bash
python -m _experiments.scripts.preflight.run --all --report
```

Gates run in order, every gate runs even when an earlier one fails, each prints one pass/fail
line, and the exit status is non-zero if any of them failed. `--report` writes
`impl/preflight_report.md` and `impl/preflight_report.json`. The whole suite takes about two
minutes and touches no GPU.

| | Gate | Checks |
|---|---|---|
| 1 | environment | `_experiments.env.check_env`; the platform tool layer imports and exposes 23 tools; the platform commit is recorded and its tree is clean; the parquet, database, model, prompt and tools sha256 are readable; the `hofinet` columns are the released English ones; `streamlit_stubbed` is true; every configuration to be run has a pinned model revision |
| 2 | code tests | the platform suite (`pytest -q` in `STAR-Bench-Web`, optionally under `--platform-python`), `_experiments/scripts/tests`, `tests_runner`, `tests_preflight`, and `gen_tools_kr --check` for schema-arm parity |
| 3 | benchmark data | the single-turn linter, `data_fixes.multiturn.verify`, `new_cases.verify --gate`, KR/EN parity (same ids in the same order, same gold, same difficulty, same note), the case counts against `expected_counts.json`, and a duplicate-question check |
| 4 | gold answers | `scoring.gold_selftest` on all four benchmark directories with zero defects required, and every gold call executed through the platform harness (`scripts/gold_calls.py` functions, `STAR_BENCH_GOLD_DIRS`) with a per-tool table |
| 5 | serving readiness | the registry against `run_plan.json` in both directions, registry completeness, published template hashes, tensor-parallel size against the hosts the rerun has, and the Korean prompt budget per configuration |
| 6 | canary | a fixed sample through the real runners against a served model, then the anomaly gates; a subcommand, because it needs a server |

## Result of the run

`python -m _experiments.scripts.preflight.run --all --report`, 2026-09-16, on
`STAR-Bench@764eb35` and `STAR-Bench-Web@1309117`:

```
[FAIL] gate 1 environment            7/8 checks     2.8s
[PASS] gate 2 code tests             5/5 checks    65.6s
[PASS] gate 3 benchmark data         9/9 checks    11.3s
[PASS] gate 4 gold answers           9/9 checks    47.9s
[PASS] gate 5 serving readiness      5/5 checks     0.1s
[SKIP] gate 6 canary run             0/0 checks     0.0s

FAILED: gate 1 environment
```

Two minutes and eight seconds, 36 checks, one failure. Provenance of that run:
platform `1309117`, parquet `88a393845b4f`, database `a93ebc65ac33`, model
`96c9c16e632d`, platform prompt `ad90f2e7bc74`, platform tools `06bc60620eb3`,
`streamlit_stubbed` true, both working trees clean.

The full output, with every check, the hashes and the exact commands, is
`impl/preflight_report.md`.

### The one failure

**Gate 1, model revisions are pinned.** 26 of the 28 configurations have `null` in
`_experiments/scripts/model_revisions.json`; only `DragonLLM/Llama-Open-Finance-8B` and
`DragonLLM/Qwen-Open-Finance-R-8B` carry a snapshot sha (they were already in the local cache
when WS-C wrote the file). This is not a defect another stream left behind: WS-C recorded it as
"the rest are filled by whoever downloads them", the runner refuses to emit serving arguments
without a revision (`UnpinnedRevision`, R2C-003), and only the person who downloads a model can
supply its sha. The gate stays red on purpose until they do, and
`--configs <ids>` narrows it to the configurations one host is about to serve, so a co-author
who has downloaded two models gets a green gate for those two.

Filling one entry:

```bash
huggingface-cli download Qwen/Qwen3.5-4B --revision main   # prints the snapshot sha
# put that sha in _experiments/scripts/model_revisions.json under the model id
python -m _experiments.scripts.preflight.run --only env --configs qwen35-4b-nt,qwen35-4b-t
```

### Everything else the run found

Nothing. Gates 2 to 5 pass on the state the other four streams left:

* platform suite 495 passed / 15 skipped / 2 deselected, scoring 112 passed, runners 115 passed
  / 1 skipped, pre-flight 41 passed, and `tools_kr.py` up to date against `agent.TOOLS`.
* the single-turn linter reports 1,258 cases and 0 violations; `multiturn.verify` reports no
  problems; `new_cases.verify --gate` reports 143 cases, 151 gold calls, 0 problems.
* the two languages carry the same 1,258 ids in the same order with byte-identical gold,
  difficulty and notes, and the same 50 scenarios with the same turn counts.
* the gold self-test is 1258/1258 on both single-turn directories and 50/50 oracle and 50/50
  end-to-end on both multi-turn directories, with zero defects.
* 2,896 gold calls execute across the four directories with **zero errors**: 1,219 ok / 28 empty
  / 1 skipped per single-turn directory, 199 ok / 1 empty per multi-turn directory.

## The empty-result allow-list

Gate 4 fails on any gold-call error, and on any empty or unexecutable call that
`preflight/allow_empty.json` does not name. The list has 30 entries and covers exactly three
things, which a test enforces:

| n | what | why it answers nothing |
|---|---|---|
| 17 | `detect_aml_patterns` ring scans, single-turn (`st_ap_*`, `st_mtool_*`) | D06: a ring needs a cycle of 3 to 6 fraud transfers and HOFINET's transfer graph is acyclic |
| 11 | `detect_aml_patterns` layering scans, single-turn | D06: layering needs a chain of 3 or more consecutive fraud transfers and the longest fraud chain in HOFINET is 2 |
| 1 | `detect_aml_patterns` layering, `mt_str_020` | the same fact, in the one multi-turn turn that scans for it |
| 1 | `analyze_network` in `st_mtool_084` | the account comes from the first call's own result, so there is no gold argument to execute; WS-D documented it as the single self-test advisory |

Entries are keyed `single` or `multiturn` rather than per language, because the two languages
carry the same gold. An entry that stops being empty is reported as stale and can be removed;
it does not fail the gate. `--update-allow-list` rewrites the file from a run, marking every new
entry `TO BE EXPLAINED`, which the test then rejects until somebody writes the reason.

## The canary

```bash
python -m _experiments.scripts.preflight.run canary --config <id> \
    --base-url http://127.0.0.1:11434/v1
python -m _experiments.scripts.preflight.run canary --mock          # no GPU, for testing
```

**The sample** (`preflight/canary_sample.json`, rebuildable with `--rebuild-sample`): 40
single-turn cases plus 3 multi-turn scenarios, chosen by a rule rather than by hand. One case
per gold tool first, because a parser that drops one tool's calls is what this is for; then the
three case shapes whose failure mode differs (3 clarification, 3 no-tool, 5 multi-tool); then
the lowest-id hard cases up to 40. The scenarios are the lowest-id one of each sub-category
(`mt_str_001` base, `mt_str_002` missing_parameter, `mt_str_003` long_context). Together they
cover all 23 tools, `generate_str` through the scenarios. The sample is fixed so two
configurations are compared on the same cases.

It runs through the real runners as a `--partial` run into a fresh directory, at concurrency 1,
on the Korean arm, and then reads the Contract 2 records.

**The gates** (`preflight/thresholds.json`, every number with its source):

| gate | limit | where the number comes from |
|---|---|---|
| no-tool-call rate | 0.40 of the cases whose gold expects a tool | 2026 Korean arm: median configuration 11.1%, worst three 75.0% (xLAM-2-1b), 52.6% (A.X-4.0-Light), 31.2% (Phi-4-mini, later traced to C2-001) |
| system-error rate | 0.01 | the spec's number; Llama-3.2-3B hit 16.1% in 2026 and every one was scored as a zero (L5-019) |
| `finish_reason: length` | 0.02 | the spec's number; one of the canary's 53 records passes, two do not |
| fallback-parser share | 0.20 of the tool calls | the spec's number; the finance Qwen's calls all came through the fallback parser on the wrong tool parser (L5-010) |
| empty tool-result share | the sample's own gold empty share + 0.10, floor 0.15 | the baseline is computed from `allow_empty.json` at run time, so ring and layering do not count against the model |
| prompt headroom | at least 2,000 tokens | the spec's number, measured from the server's own `usage.prompt_tokens` rather than from an estimate |
| per-case latency ceiling | 600 s | 2026: per-configuration medians 0.2 s to 190 s, slowest single case 1,431 s; 600 s is above every configuration median and twice the 300 s client timeout |
| per-case latency spread | slowest / median <= 12, and only above 30 s | 2026 p95/median was 2.4 at the median configuration and 8.5 at the worst |

`--mock` runs the same code path against `tests_runner/mock_server.py`, which is how the
subcommand is tested without a GPU. On the mock the run is 53 records in about 10 s and every
gate is clean.

## Tests

`python -m pytest _experiments/scripts/tests_preflight -q`: **41 passed**.

Each anomaly gate is tested against records written for the 2026 failure it exists to catch (an
error scored as a zero, a length stop, fallback calls, empty results, an 11k prompt in a 12,288
context, a 900-second case among 5-second cases), and against the case that must *not* trip it
(a case whose gold expects no tool, a uniformly slow reasoning run, a baseline that is already
high). The data gate is tested on a benchmark written to drift (a case missing on the English
side, gold that differs between the languages, two cases asking the same question, a user turn
legitimately repeated across scenarios). The serving gate is tested against registries built to
be wrong (the same model in the same mode twice, a 12,288 context, a reasoning configuration
with an 8k budget, a template not in the repository, a configuration that fits no host). The
canary runs end to end against the mock server. The allow-list is tested to cover only ring,
layering and the one chained call, and the thresholds file to carry a source for every number.

## What the rerun still has to do on the serving host

1. **Fill `model_revisions.json`** as each model is downloaded. This is the one red gate.
2. **Re-run gate 5 there.** On this machine no tokenizer could be loaded offline, so the prompt
   budget is the calibrated byte estimate: 9,496 tokens for the Korean arm, the tightest
   headroom 6,888 tokens (the reasoning configurations, 32,768 context minus a 16,384 output
   budget). WS-C measured the estimate as conservative by about 20% against the real Qwen
   tokenizer, so nothing is at risk, but with `transformers` installed and the snapshot present
   the check uses the real tokenizer per model and the number becomes a measurement.
3. **Run the canary per configuration** against the served model before the column runs. It is
   the only gate that can see a wrong tool-call parser, a reasoning mode that is not applied or
   a template that eats calls, and it is 53 records (40 cases plus 13 turns).
4. **`--serving-stack`** on that host, so the vLLM and torch pins are checked too. On this
   machine the serving stack is deliberately absent and the flag is off by default.

## Not covered by this stream

| id | reason |
|---|---|
| the GPU smoke items in WS-C's list (repaired templates, Kanana-2-Think, the Mistral vendor format, gpt-oss reasoning effort, per-model position embeddings) | they need a server. The canary is the gate that runs them; the eight items are the per-configuration reading of its output |
| L5-001, L5-004, L5-023, R1-R1 | the rerun itself, step 11 |
| D04, D22, and the manuscript work | after the rerun |
