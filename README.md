# STAR-Bench: Evaluating Anti-Money Laundering Agents for Regulatory Reporting Workflows

## Overview

STAR-Bench is a domain-specific function-calling benchmark for evaluating LLMs as
anti-money laundering (AML) agents. Unlike general-purpose tool-use benchmarks,
STAR-Bench targets **23 AML-specific tools** derived from a real AML agent platform,
adds **regulation-grounded parameter constraints** (STR field schema, reporting
thresholds, fraud-type codes), a controlled **Korean–English bilingual** setting, and
a **multi-turn suspicious transaction report (STR) writing** workflow on top of
single-turn tool calling.

## Key features

- **1,258 expert-authored, cross-validated single-turn cases** over 23 tools and 3
  difficulty levels (Easy 737 / Medium 283 / Hard 238).
- **4 AML subdomains** derived from the reference platform (see below).
- **50 multi-turn STR scenarios**, evaluated under both an **oracle** setting
  (ground-truth tool results injected each turn) and an **end-to-end (E2E)** setting
  (the model's own tool outputs propagate across turns).
- **Controlled bilingual evaluation**: query language (KR/EN) × tool-definition
  language (KR/EN), enabling a 2×2 decomposition of language effects.
- **24 open-weight models (28 thinking/non-thinking configurations)** across families,
  evaluated with native function calling. Each configuration is served alone from a
  pinned registry entry that fixes the model revision, chat template, tool-call
  parser, reasoning mode, context window and output budget. 18 are vLLM on local NVIDIA
  L40S 48 GB and H100 80 GB hosts; 10 are served through a commercial gateway in every
  setting, where the provider serves its own copy of the weights, so the registry fixes
  the request but not the revision. The run records say which.
- **Deterministic decoding** (temperature 0); case-level bootstrap (10,000 resamples)
  confirms stable rankings (Kendall τ = 0.962, 95% CI [0.935, 0.985]).

## Benchmark structure

| Subdomain | Tools | Coverage |
|-----------|:-----:|----------|
| Transaction Inquiry & Statistics | 7 | Summary statistics, raw queries, account/receiver profiles, period comparison, fraud-type breakdown, institution report |
| Suspicious Activity Detection | 4 | Fraud-probability prediction, risky-transaction ranking, account risk scoring, rule-based monitoring |
| Money Flow & Network Analysis | 7 | Network analysis, AML pattern (ring/layering/funnel) detection, smurfing, dormant reactivation, cross-institution flow, trend, channel risk |
| Regulatory Reporting | 5 | CTR-candidate detection, FIU reference lookup, STR field validation, AML glossary, STR generation† |

† `generate_STR` is evaluated only in the multi-turn STR workflow (no single-turn cases).

### Case composition (single-turn, 1,258 cases)

| Difficulty | Call type | Category |
|---|---|---|
| Easy: 737 | Tool-required: 1,099 | Single-tool: 1,089 |
| Medium: 283 | No gold tool: 159 (out of scope 119, missing argument 40) | Multi-tool: 125 |
| Hard: 238 | | Missing-parameter: 44 |

Difficulty reflects two independent factors: semantic ambiguity between
similar-function tools, and information completeness of the query (missing-parameter
follow-ups and abstention on irrelevant queries).

## Repository structure

```
benchmarks/               — Single-turn cases, Korean (24 JSON files, 1,258 cases)
benchmarks_en/            — English-translated single-turn cases (1,258)
benchmarks_multiturn/     — Multi-turn STR scenarios, Korean (50)
benchmarks_multiturn_en/  — English multi-turn STR scenarios
_experiments/
  scripts/
    runner/               — Serving registry, request layer, run records (Contract 2)
    scoring/              — Scorer: metric definitions, gold comparison, aggregates
    analysis/             — One reader over the scored runs, and the manuscript tables
    preflight/            — Six gates that must pass before a run
    data_fixes/           — Benchmark linters and the regulatory terminology table
    benchmark.py, benchmark_multiturn.py, run_master.sh — the runners
    regenerate_analysis.py — rebuilds every table, figure and in-text figure from the scored runs
  runs/
    single/ mt_oracle/ mt_e2e/        — run records, one JSON line per case or turn
    single_entools_krq/ single_krtools_enq/ single_entools_enq/ — the 2x2 arms
    baselines/                        — the two un-specialised bases, outside the cohort
    eval/                             — scores, one directory per column and configuration
  results_RQ1 … results_RQ5/ — Per-research-question analysis outputs and figures
  paper_tables/       — The paper's data tables, generated
  human_eval/round2/  — Blind STR drafts, the code-to-model key and the two raters' scores (Appendix F)
  bfcl_results/             — BFCL scores for the general-vs-domain comparison
  figures/                  — Generated figures
```

Every number in the paper is rebuilt from `runs/` by
`python -m _experiments.scripts.regenerate_analysis --all`: the tables into
`paper_tables/`, the figures stated in prose into `results_RQ1/text_figures.json`, and the
expert agreement from the released ratings in `human_eval/round2/`. The run records are the
primary artefact: each holds the raw response per round, the parsed calls with their
arguments and whether the server or the text fallback produced them, the tool output,
and the stop reason, so the scoring can be repeated without serving a model again.

> The **executable AML tools** live in the companion platform repository,
> `STAR-Bench-Web`, which is released alongside this one — this repository holds
> the cases, the evaluator and the runners, and calls into that one rather than
> keeping a second copy of the tool layer. See *Installation* below.
>
> The benchmark transaction environment is **synthetic** and is released
> with the platform (`_datasets/transactions.parquet`). What is not released is the real
> transaction data that synthesis was derived from.

### Case format

```json
[{"question": "...", "expected_tool_call": {"name": "...", "arguments": {...}}}]
```

## Installation

Running the benchmark executes real AML tools against the transaction environment, and
both live in the companion platform repository. Clone the two side by side:

```bash
git clone <STAR-Bench URL>      STAR-Bench
git clone <STAR-Bench-Web URL>  STAR-Bench-Web    # executable tools + data

pip install -r STAR-Bench/requirements.txt                # evaluation engine
pip install -r STAR-Bench-Web/requirements-tools.txt      # tool layer (DuckDB, XGBoost, …)
```

The runners locate the platform automatically when the two repositories are
siblings. If they are not, point at it explicitly:

```bash
export STAR_BENCH_WEB=/path/to/STAR-Bench-Web
```

Either way the resolution is handled by `_experiments/scripts/_platform.py`, which
fails with setup instructions rather than a bare `ModuleNotFoundError`.

`requirements-tools.txt` is the tool layer without the platform's Streamlit UI;
use the platform's full `requirements.txt` only if you also want to run its app.

No further setup is needed: the DuckDB view is built from the released Parquet on
first run, and the trained fraud detector used by `predict_fraud` ships with the
platform (regenerate it with `python -m scripts.train_detector` if you prefer).

Hosted-provider evaluation (OpenAI / Anthropic) needs only the analysis and client
packages; reproducing the open-weight runs additionally requires the vLLM serving
stack pinned in `_experiments/env/requirements-serving.txt`.

## Running

Run from the repository root with `PYTHONPATH=.`:

A run names a registry configuration rather than a model string, so the revision,
template, parser, reasoning mode, context and budget come from one place and land in
the record.

```bash
# Serve one configuration and run one column against it
bash _experiments/scripts/run_benchmark.sh --config qwen35-27b-nt --gpu 0,1 \
  --mode single --tools-lang kr --query-lang kr \
  --out-root _experiments/runs

# The 2x2 arms differ only in --tools-lang and --query-lang
# The multi-turn columns are --mode oracle and --mode e2e

# Every configuration this host can serve
python -m _experiments.scripts.runner.plan --host-gpus 2

# Score afterwards, from the records
python _experiments/scripts/scoring/score_runs.py \
  --runs _experiments/runs/single/qwen35-27b-nt \
  --benchmark benchmarks --out _experiments/runs/eval/single/qwen35-27b-nt

# Rebuild every table and figure
python -m _experiments.scripts.regenerate_analysis --all
```

**Providers.** Native function calling against a vLLM server, with a per-configuration
tool-call parser and a custom plugin for Kanana. `benchmark_openrouter.py` runs the same
column through a gateway for a model the host cannot serve, pinning the provider and the
quantisation so the gateway cannot silently reroute; a gateway run is a different serving
stack and the record says so. Thinking models are two configurations, not one.

### Before a run: the pre-flight gates

```bash
python -m _experiments.scripts.preflight.run --all --report
```

Six gates, one pass/fail line each, non-zero exit on any failure: the environment
(platform commit, parquet and database hashes, `hofinet` columns, Streamlit stub,
model revision pins), the four test suites and the schema-arm parity check, the
benchmark data (linters, KR/EN parity, case counts, duplicate questions), the gold
answers (self-test on all four directories and every gold call executed on the
platform), serving readiness (registry against the run plan, template hashes,
tensor-parallel size against the hosts, prompt budget per configuration), and a
canary run.

The canary needs a served model and is its own subcommand:

```bash
python -m _experiments.scripts.preflight.run canary --config <id> \
  --base-url http://127.0.0.1:11434/v1
```

It sends a fixed sample of 40 single-turn cases covering all 23 tools plus three
multi-turn scenarios through the runners, then trips on a no-tool-call rate, an
error rate, a `finish_reason: length` share, a fallback-parser share, an empty
tool-result share, a prompt headroom or a latency band outside what
`_experiments/scripts/preflight/thresholds.json` allows. `--mock` runs the same
path against the mock server, without a GPU. `--report` writes the full report to
`_experiments/scripts/preflight/reports/preflight_report.md` and `.json`.

## Headline findings

Every figure below is rebuilt by `regenerate_analysis --all` and carries the number
of configurations it covers: 28 for the single-turn and oracle results, 25 for
end-to-end, 7 for the language 2x2 and 10 for the BFCL comparison; the per-research-question outputs sit under
`results_RQ1`–`results_RQ5`.

| Model | Single-turn `h` | Multi-turn `h̄` | Completion `c` |
|---|:---:|:---:|:---:|
| Gemma-4-31B | .966 | .904 | .66 |
| Qwen3.6-27B | .943 | .840 | .40 |
| Kanana-2-Think | .897 | .922 | .68 |
| Mistral-Small-24B | .814 | .922 | .72 |
| Llama-3.3-70B | .779 | .900 | .60 |
| xLAM-2-70B | .695 | .849 | .46 |

- **Single-turn accuracy does not predict workflow completion.** Configurations
  within six points of one another on single-turn tool hit, from .904 to .966,
  complete between 36% and 66% of STR scenarios. The configuration that completes the
  most, Mistral-Small-24B at .72, is 17th of 28 on single-turn tool hit. Turn-level
  hit and completion agree almost exactly (ρ = 0.99), so the workflow axis is one
  coherent thing that single-turn tool use does not reach.

- **The workflow breaks at the reporting turn.** Under the oracle setting, which
  injects the ground-truth call and its executed output after every turn, hit climbs
  through the investigation turns (.739, .819, .871) and falls to .694 at the fourth,
  where 28 of the 50 scenarios ask for the report. The drop survives a setting that
  erases every earlier mistake.

- **Reporting fails in a shape of its own, not at a higher rate.** Averaged over the
  cohort the four Regulatory Reporting tools sit within a point and a half of the
  analysis tools, and 13 of 28 configurations are worse on reporting. What differs is
  the failure: across analysis tools 44% of failures are wrong-tool substitutions and
  23% are no-calls, while STR-field validation fails by never calling the tool in 75% of
  its failures and the AML glossary in 66%. CTR-candidate detection falls back to a
  generic transaction query in 40% of its failures. FIU reference lookup is selected correctly 87.6% of the time
  and grounded correctly 53.0%, the widest such gap in the suite: the model reaches the
  right tool and cannot convert Korean regulatory terminology into its argument.

- **End-to-end execution costs parameter grounding, not tool selection.** Feeding the
  agent its own tool outputs lowers mean turn-level hit by 4.2 points and completion by
  2.2, while parameter accuracy falls by 8.9, over the 25 configurations run in both
  settings. Tool executions returned an error for
  2.3% of calls, and every attributed one was caused by the model rather than by the
  platform or the data.

- **Some models cannot emit a callable form.** Four configurations name the correct
  tool in their answer text far more often than they produce a parseable call.
  Phi-4-mini reports h = .120 while naming the gold tool in 639 of its 1,258 cases, and
  the shapes it emits are not any vendor's call format, so no parser accepts them.
  `unparsed_calls.py` reports this gap per configuration.

- **General function-calling rank does not predict AML tool use.** Over the ten
  configurations that overlap with BFCL and whose BFCL runs elicited tool calls at
  all, the rank correlation is moderate and not significant (Spearman ρ = 0.47,
  p = 0.17). xLAM-2-70B is second under BFCL and seventh here; EXAONE-4.0-32B moves
  the other way, ninth to fourth.

- **Language alignment is a per-model question.** In the 2×2 over query language and
  tool-definition language, the average effects are small, and the exceptions belong to
  particular models: A.X-4.0 loses 4.5 points on English queries, while Llama-3.3-70B
  is best when query and schema are both English.

## Evaluation metrics

**Single-turn.** Tool hit `h` (every gold tool is among the calls; the primary
metric), required-tool recall `r`, precision `p`, parameter accuracy `a` (key-value
constraints on correctly selected tools) and order score `o` (1 when the tools the gold
orders first appear in that order, for multi-tool cases). `p`, `a` and `o` are undefined rather than perfect
where they do not apply: `p` for a case with no calls, `a` for a case with no
parameter check, `o` for a case whose order is unconstrained. Every aggregate carries
the count it was taken over. Parser failures score zero; a correct abstention on an
irrelevant or underspecified query counts as a successful refusal, and requires an
answer rather than merely the absence of a call.

**Multi-turn STR.** Per-turn tool hit `h̄` and parameter accuracy `ā` (means over
turns), and scenario completion rate `c` (fraction of scenarios in which every turn
achieves `h = 1`). Context carry-over accuracy is reported as a state-tracking
diagnostic.

**STR generation quality.** Over scenarios whose ground truth includes a `generate_STR`
turn, we report the production rate (fraction that actually invoke `generate_STR`) and,
for produced drafts, a deterministic evidence check over required-field completeness,
evidence grounding (factual slots supported by prior tool outputs) and regulatory
terminology use, with their mean as the overall score. Under the penalized setting, a
scenario without an STR scores zero on every axis, and a report that states no figure
scores zero on grounding. Workflow completion `c` counts tool selection only; arguments
and the report are scored separately, so a completed workflow can still end in a weak
report.

## Citation

A citation block is added at camera-ready. It is withheld here because the
review copy of this repository is anonymous.

## License

Released for research purposes.
