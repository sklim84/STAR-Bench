# AML-Bench: A Function Calling Benchmark for Anti-Money Laundering Agents

## Overview

AML-Bench is a domain-specific function calling benchmark for evaluating LLMs as anti-money laundering (AML) agents. Unlike existing tool-use benchmarks targeting general-purpose APIs, AML-Bench evaluates 23 AML-specific tools extracted from a real operational AML agent platform.

## Key Features

- **1,258 expert-curated test cases** across 24 evaluation categories and 3 difficulty levels
- **51 models** from 14 families evaluated (largest model comparison in tool-calling benchmarks)
- **Korean–English prompt ablation**: controlled single-variable experiment isolating query language effect
- **5-round reproducibility**: mean ± standard deviation reported for all metrics

## Main Findings

1. Tool-calling accuracy does not scale with model size — 4B models outperform 70B counterparts
2. Korean prompts yield higher accuracy than English for 75% of models
3. Thinking mode degrades Korean tool-calling while improving English, revealing a language–reasoning interaction

## Benchmark Structure

| Subdomain | Tools | Description |
|-----------|-------|-------------|
| Transaction Stats & Inquiry | 6 | Summary statistics, raw queries, account profiles, period comparison |
| AML Detection & Reporting | 5 | Network analysis, pattern detection, fraud prediction, STR generation |
| CTR, Risk & Monitoring | 3 | High-value transaction detection, risk scoring, rule-based monitoring |
| Flow, Trend & Channel | 6 | Dormant reactivation, smurfing, trend analysis, cross-institution flow |
| AML Reference | 3 | FIU reference lookup, STR validation, AML glossary |

## Repository Structure

```
_manuscript/          — Paper source (LaTeX, ACL/EMNLP format)
benchmarks/           — Benchmark cases (24 JSON files, 1,258 cases)
benchmarks_en/        — English-translated cases (for KR-EN ablation)
figures/              — Paper figures (PNG/PDF)
tables/               — Comparison results (Excel)
```

## Evaluation Metrics

- **Composite Score** ($s \in [0, 1]$): weighted combination of tool selection and parameter accuracy
- **Tool Selection Accuracy**: fraction of cases with correct primary tool
- **Parameter Accuracy**: key-value match accuracy for correctly selected tools
- **Error Distribution**: wrong_func, wrong_params, parse_fail, api_error

## Citation

```bibtex
@inproceedings{lim2026amlbench,
  title={AML-Bench: A Function Calling Benchmark for Anti-Money Laundering Agents},
  author={Lim, Seonkyu and Hong, Gwangui and Lim, KyungTae},
  booktitle={Proceedings of the Conference on Empirical Methods in Natural Language Processing (EMNLP)},
  year={2026}
}
```

## License

This benchmark is released for research purposes.
