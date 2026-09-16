# End-to-end tool error and empty-result rates

Source: `_experiments/results_mt_real`. 5,550 executed tool calls.

| outcome | calls | share |
|---|---:|---:|
| answered | 3,047 | 54.9% |
| empty result | 1,179 | 21.2% |
| error | 1,324 | 23.9% |

## Errors by cause

| cause | family | calls | share of all calls |
|---|---|---:|---:|
| `platform_nan` | platform | 538 | 9.7% |
| `entity_absent` | data | 281 | 5.1% |
| `platform_model_artifact` | platform | 169 | 3.0% |
| `platform_key_error` | platform | 109 | 2.0% |
| `model_bad_argument` | model | 87 | 1.6% |
| `graph_backend_absent` | platform | 47 | 0.8% |
| `model_missing_argument` | model | 44 | 0.8% |
| `model_bad_sql` | model | 35 | 0.6% |
| `model_unknown_tool` | model | 14 | 0.3% |

## Errors by family

| family | calls | share of all calls |
|---|---:|---:|
| platform | 863 | 15.5% |
| data | 281 | 5.1% |
| model | 180 | 3.2% |

`platform` and `data` causes are ours, not the model's: a caption that reads the end-to-end drop as error propagation has to subtract them.
