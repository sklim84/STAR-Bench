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
  difficulty levels (Easy 673 / Medium 412 / Hard 173).
- **4 AML subdomains** derived from the reference platform (see below).
- **50 multi-turn STR scenarios**, evaluated under both an **oracle** setting
  (ground-truth tool results injected each turn) and an **end-to-end (E2E)** setting
  (the model's own tool outputs propagate across turns).
- **Controlled bilingual evaluation**: query language (KR/EN) × tool-definition
  language (KR/EN), enabling a 2×2 decomposition of language effects.
- **24 open-weight models (28 thinking/non-thinking configurations)** across families,
  evaluated with native function calling, vLLM-served on 2× NVIDIA H100 80GB GPUs
  (OpenAI/Anthropic providers also supported).
- **Deterministic decoding** (temperature 0); case-level bootstrap (10,000 resamples)
  confirms stable rankings (Kendall τ = 0.936, 95% CI [0.900, 0.968]).

## Benchmark structure

| Subdomain | Tools | Coverage |
|-----------|:-----:|----------|
| Transaction Inquiry & Statistics | 7 | Summary statistics, raw queries, account/receiver profiles, period comparison, fraud-type breakdown, institution report |
| Suspicious Activity Detection | 4 | Fraud-probability prediction, risky-transaction ranking, account risk scoring, rule-based monitoring |
| Money Flow & Network Analysis | 7 | Network analysis, AML pattern (ring/layering/funnel) detection, smurfing, dormant reactivation, cross-institution flow, trend, channel risk |
| Regulatory Reporting | 5 | CTR-candidate detection, FIU reference lookup, STR field validation, AML glossary, STR generation† |

† `generate_STR` is evaluated only in the multi-turn STR workflow (no single-turn cases).

### Case composition (single-turn, 1,258 cases)

| Difficulty | Call type | Intent |
|---|---|---|
| Easy: 673 | Single-tool (22 tools): 1,133 | Tool-required: 1,099 |
| Medium: 412 | Multi-tool (1): 100 | Abstain (irrelevant query): 159 |
| Hard: 173 | Missing-parameter (1): 25 | |

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
  scripts/                — Evaluation engine (benchmark.py, benchmark_multiturn.py, run_master.sh)
  results_kr/             — Single-turn results: KR queries, KR tool definitions (primary)
  results_en/             — Single-turn results: EN queries, KR tool definitions
  results_kr_tools_en/    — 2×2 ablation arm: KR queries, EN tool definitions
  results_en_tools_en/    — 2×2 ablation arm: EN queries, EN tool definitions
  results_mt_oracle/      — Multi-turn STR results: oracle tool-result injection (main setting)
  results_mt_real/        — Multi-turn STR results: end-to-end execution (errors propagate)
  results_RQ1 … results_RQ5/ — Per-research-question analysis outputs and figures
  bfcl_results/           — BFCL runs for the general-vs-domain comparison (RQ5)
  figures/                — Generated figures
  MODELS.md               — Evaluated-model registry
```

> The paper manuscript lives in a separate repository (`STAR-Bench-paper`); the
> reference AML agent platform from which the tools are derived lives in
> `STAR-Bench-Web`. Raw HOFINET transaction records are not released.

### Case format

```json
[{"question": "...", "expected_tool_call": {"name": "...", "arguments": {...}}}]
```

## Installation

```bash
pip install -r requirements.txt
```

Hosted-provider evaluation (OpenAI / Anthropic) needs only the analysis and client
packages; reproducing the open-weight runs additionally requires the vLLM serving
stack pinned in `requirements.txt`.

## Running

Run from the repository root with `PYTHONPATH=.`:

```bash
# Single-turn, Korean (primary)
PYTHONPATH=. python -m _experiments.scripts.benchmark \
  --models Qwen/Qwen3-8B --output _experiments/results_kr/ --checkpoint --resume

# Single-turn, English queries
PYTHONPATH=. python -m _experiments.scripts.benchmark \
  --models Qwen/Qwen3-8B --output _experiments/results_en/ \
  --cases-dir benchmarks_en/ --checkpoint --resume

# Multi-turn STR — oracle setting (main): ground-truth tool results injected each turn
PYTHONPATH=. python -m _experiments.scripts.benchmark_multiturn \
  --models Qwen/Qwen3-8B --setting oracle --output _experiments/results_mt_oracle/

# Multi-turn STR — end-to-end setting: the model's own tool outputs propagate
PYTHONPATH=. python -m _experiments.scripts.benchmark_multiturn \
  --models Qwen/Qwen3-8B --setting real --output _experiments/results_mt_real/

# Full automation across modes (vLLM)
bash _experiments/scripts/run_master.sh --server 1 --modes kr,en,mt
```

**Providers.** Native function calling for OpenAI (gpt-4o/5-mini family), Anthropic
(Claude Haiku/Sonnet), and vLLM-served open-weight models. vLLM uses per-model
tool-call parsers (with a custom plugin for Kanana); thinking models are split into
`think` / `nothink` entries.

## Research questions and headline findings

The benchmark is organized around five research questions; full per-model tables,
metrics, and statistics are in the paper and under `_experiments/results_*`.

- **RQ1 — Tool discrimination.** Tool-hit accuracy does **not** scale monotonically
  with model size: mid- and small-sized models (e.g., Mistral-Small-24B,
  Ministral-3-3B) outperform larger ones (e.g., Llama-3.3-70B). Wrong-tool errors are
  structured — concentrated on near-duplicate tools (e.g., account-profile vs
  receiving-account-profile) — rather than random.
- **RQ2 — Regulatory reporting.** The Regulatory Reporting subdomain is the **weakest**
  (mean tool hit ≈ 0.58 vs. 0.79–0.83 for the other subdomains; an average gap of about
  24.7 percentage points against ordinary analysis tools). Its failures stem from **not
  engaging the regulatory tool**: STR-field validation fails almost entirely by no-call,
  CTR-candidate detection by wrong-tool fallback to a generic transaction query, and FIU
  reference lookup by keyword-mapping errors (correct tool, wrong search keyword).
- **RQ3 — Multi-turn STR.** Single-turn skill does not transfer to multi-turn STR
  completion, and multi-turn rankings differ substantially from single-turn rankings.
  Even under the favorable **oracle** setting, the per-turn hit rate collapses by roughly
  27 percentage points at the STR-writing/reporting turn; **end-to-end** execution
  amplifies the errors further (mean scenario completion drops from .173 to .062).
  Multi-turn completion correlates with context carry-over accuracy (Spearman ρ = 0.73).
- **RQ4 — Bilingual robustness.** With tool definitions fixed in Korean, Korean queries
  are generally stronger than English queries, but the magnitude varies substantially
  across model families; switching tool definitions from Korean to English does not
  consistently close the gap. Query-language and tool-definition-language effects are of
  similar magnitude with weak interaction.
- **RQ5 — Generalization gap.** General function-calling rank does **not** predict AML
  tool use: among the 10 overlapping (BFCL top-ranked) models, the rank correlation is
  weak and not significant (Spearman ρ = 0.333, p = 0.347). Model size and specialization
  labels are likewise unreliable predictors; finance-oriented fine-tuning helps most in
  the regulation- and detection-heavy subdomains.

## Evaluation metrics

**Single-turn.** Tool hit `h` (correct primary tool selected; the primary metric),
required-tool recall `r`, precision `p` (false-positive control), parameter accuracy
`a` (key–value constraints on correctly selected tools), and order score `o` (LCS-based
call-order consistency for multi-tool cases). Parser failures score zero; a correct
abstention on an irrelevant or underspecified query counts as a successful refusal.

**Multi-turn STR.** Per-turn tool hit `h̄` and parameter accuracy `ā` (scenario-level
means), and scenario completion rate `c` (fraction of scenarios in which every turn
achieves `h = 1`). Context carry-over accuracy is reported as a state-tracking
diagnostic.

**STR generation quality.** Over scenarios whose ground truth includes a `generate_STR`
turn, we report the production rate (fraction that actually invoke `generate_STR`) and,
for produced drafts, a deterministic evidence check over required-field completeness,
evidence grounding (factual slots supported by prior tool outputs), regulatory
terminology use, and unsupported-fact rate, combined into an overall score. Under the
penalized setting, a scenario without an STR scores zero on every quality axis.

## Citation

```bibtex
@misc{lim2026starbench,
  title  = {STAR-Bench: Evaluating Anti-Money Laundering Agents for Regulatory Reporting Workflows},
  author = {Lim, Seonkyu and Hong, Gwangui and Tae, Inwoo and Hwang, Inje and
            Baek, Jonghyuk and Kim, Jingu and Choi, Jeongwhan and Lee, Jaehoon and
            Yoo, Hangyeol and Cheong, Jaeyoung and Lee, Yongjae and Kim, Min-Soo and
            Lim, KyungTae},
  year   = {2026},
  note   = {Preprint}
}
```

## License

Released for research purposes.
