# Rerun assignment (2026-09-16)

Frozen point: tag `rerun-freeze-20260916` on branch `audit-fixes` in both repositories.
Procedure: `COAUTHOR_QUICKSTART.md` in this directory. This file says only who runs what.

Scope per configuration: single-turn 1,258 cases, multi-turn 50 scenarios (219 turns) in oracle and end-to-end. Concurrency 8, temperature 0, seed 20260925.
Seven configurations also run the three extra 2x2 arms (marked 2x2): ax-4.0, llama-3.3-70b, exaone-32b, gemma-4-31b, qwen36-27b, qwen35-27b-t, qwen35-27b-nt.

Estimated hours assume concurrency 8 and include server start and model load. They are estimates, not targets.

## Lead, via OpenRouter  (10 configurations, about $135 in API cost)

| config id | OpenRouter model | mode | output | 2x2 |
|---|---|---|---|---|
| `llama-3.3-70b` | `meta-llama/llama-3.3-70b-instruct` | none | 8k | yes |
| `gpt-oss-120b-t` | `openai/gpt-oss-120b` | effort_high | 16k |  |
| `gpt-oss-120b-nt` | `openai/gpt-oss-120b` | effort_low | 16k |  |
| `gpt-oss-20b-t` | `openai/gpt-oss-20b` | effort_high | 16k |  |
| `gpt-oss-20b-nt` | `openai/gpt-oss-20b` | effort_low | 16k |  |
| `qwen36-27b` | `qwen/qwen3.6-27b` | think | 16k | yes |
| `qwen36-35b-a3b` | `qwen/qwen3.6-35b-a3b` | think | 16k |  |
| `gemma-4-31b` | `google/gemma-4-31b-it` | nothink | 8k | yes |
| `mistral-small` | `mistralai/mistral-small-3.2-24b-instruct` | none | 8k |  |
| `ministral-3b` | `mistralai/ministral-3b-2512` | none | 8k |  |

Pin the provider and quantization (`--provider-order`, `--no-fallbacks`, `--require-parameters`); the record keeps the provider and usage per request.

## On-demand 80 GB node (4 cards)  (2 configurations, about 9.7 h)

| order | config id | model | cards | mode | parser | context | output | hours | 2x2 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `ax-4.0` | A.X-4.0 (72B) | 2 | none | `hermes` | 32k | 8k | 9.7 | yes |
| 2 | `xlam-70b` | xLAM-2-70B | 2 | none | `xlam` | 32k | 8k | 3.3 |  |

## Co-author 2, four-card host  (6 configurations, about 10.8 h)

| order | config id | model | cards | mode | parser | context | output | hours | 2x2 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `qwen35-27b-t` | Qwen3.5-27B (T) | 2 | think | `qwen3_coder` | 32k | 16k | 10.0 | yes |
| 2 | `qwen35-27b-nt` | Qwen3.5-27B (NT) | 2 | nothink | `qwen3_coder` | 32k | 16k | 4.9 | yes |
| 3 | `kanana-2-think` | Kanana-2-Think | 2 | always_on | `functionary_kanana` | 32k | 16k | 3.4 |  |
| 4 | `kanana-2-inst` | Kanana-2-Instruct | 2 | none | `functionary_kanana` | 32k | 8k | 1.7 |  |
| 5 | `dragon-qwen-fin` | Qwen-Open-Finance-R-8B | 1 | always_on | `hermes` | 32k | 16k | 0.8 |  |
| 6 | `qwen35-4b-t` | Qwen3.5-4B (T) | 1 | think | `qwen3_coder` | 32k | 16k | 0.8 |  |

## Co-author 1, host A (2 cards)  (4 configurations, about 6.1 h)

| order | config id | model | cards | mode | parser | context | output | hours | 2x2 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `exaone-32b` | EXAONE-4.0-32B | 2 | nothink | `hermes` | 32k | 8k | 4.9 | yes |
| 2 | `ax-light` | A.X-4.0-Light (7B) | 1 | none | `hermes` | 32k | 8k | 0.4 |  |
| 3 | `dragon-llama-fin` | Llama-Open-Finance-8B | 1 | none | `llama3_json` | 32k | 8k | 0.4 |  |
| 4 | `hermes-3-8b` | Hermes-3-8B | 1 | none | `hermes` | 32k | 8k | 0.4 |  |

## Co-author 1, host B (2 cards)  (6 configurations, about 1.9 h)

| order | config id | model | cards | mode | parser | context | output | hours | 2x2 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `phi-4-mini` | Phi-4-mini | 1 | none | `phi4_mini_json` | 32k | 8k | 0.4 |  |
| 2 | `llama-3.2-3b` | Llama-3.2-3B | 1 | none | `llama3_json` | 32k | 8k | 0.3 |  |
| 3 | `xlam-3b` | xLAM-2-3B | 1 | none | `xlam` | 32k | 8k | 0.3 |  |
| 4 | `qwen35-4b-nt` | Qwen3.5-4B (NT) | 1 | nothink | `qwen3_coder` | 32k | 16k | 0.3 |  |
| 5 | `gemma-4-e4b` | Gemma-4-E4B | 1 | nothink | `gemma4` | 32k | 8k | 0.3 |  |
| 6 | `exaone-1.2b` | EXAONE-4.0-1.2B | 1 | nothink | `hermes` | 32k | 8k | 0.3 |  |

## Order of work

1. Environments, model downloads, snapshot revisions in `model_revisions.json`.
2. `preflight.run --all --report --configs <your ids>`: gates 2 to 5 must pass.
3. One small configuration end to end as a pipeline check (40 cases plus the canary).
4. The configuration with the 2x2 arms first: it is the longest pole on each host.
5. The rest, longest first.

Send back the whole output directory, the server logs and the canary output. Do not score locally.
