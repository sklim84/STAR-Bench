# End-to-end tool error and empty-result rates

Source: `_experiments/results_2026rerun`, end-to-end setting. 3,111 executed tool calls from 15 of 28 configurations.

| outcome | calls | share |
|---|---:|---:|
| answered | 2,951 | 94.9% |
| empty result | 105 | 3.4% |
| error | 55 | 1.8% |

212 answered calls (6.8%) were shortened before they went back into the history. That is a delivery note, not an error.

## Errors by cause

| cause | family | calls | share of all calls |
|---|---|---:|---:|
| `model_bad_argument` | model | 19 | 0.6% |
| `model_unknown_tool` | model | 12 | 0.4% |
| `model_bad_sql` | model | 9 | 0.3% |
| `model_missing_argument` | model | 6 | 0.2% |
| `model_unknown_term` | model | 6 | 0.2% |
| `model_malformed_arguments` | model | 3 | 0.1% |

## Errors by family

| family | calls | share of all calls |
|---|---:|---:|
| model | 55 | 1.8% |

`platform` and `data` causes are ours, not the model's: a caption that reads the end-to-end drop as error propagation has to subtract them.

13 of 28 configurations have no end-to-end run and are not in these counts: ax-light, exaone-1.2b, exaone-32b, kanana-2-inst, kanana-2-think, dragon-llama-fin, dragon-qwen-fin, llama-3.2-3b, hermes-3-8b, phi-4-mini, qwen35-4b-nt, xlam-3b, gemma-4-e4b.
