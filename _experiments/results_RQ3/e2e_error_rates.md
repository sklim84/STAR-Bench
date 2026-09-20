# End-to-end tool error and empty-result rates

Source: `_experiments/results_2026rerun`, end-to-end setting. 4,434 executed tool calls from 25 of 28 configurations.

| outcome | calls | share |
|---|---:|---:|
| answered | 4,106 | 92.6% |
| empty result | 227 | 5.1% |
| error | 101 | 2.3% |

250 answered calls (5.6%) were shortened before they went back into the history. That is a delivery note, not an error.

## Errors by cause

| cause | family | calls | share of all calls |
|---|---|---:|---:|
| `model_bad_argument` | model | 41 | 0.9% |
| `model_bad_sql` | model | 18 | 0.4% |
| `model_unknown_tool` | model | 18 | 0.4% |
| `model_missing_argument` | model | 13 | 0.3% |
| `model_unknown_term` | model | 7 | 0.2% |
| `model_malformed_arguments` | model | 3 | 0.1% |
| `other` | unattributed | 1 | 0.0% |

## Errors by family

| family | calls | share of all calls |
|---|---:|---:|
| model | 100 | 2.3% |
| unattributed | 1 | 0.0% |

`platform` and `data` causes are ours, not the model's: a caption that reads the end-to-end drop as error propagation has to subtract them.

3 of 28 configurations have no end-to-end run and are not in these counts: kanana-2-inst, kanana-2-think, dragon-qwen-fin.
