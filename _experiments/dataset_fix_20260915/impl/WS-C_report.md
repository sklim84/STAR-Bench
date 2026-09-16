# Audit fixes: runners, serving configuration, run logging (WS-C)

Branch `audit-fixes` in `STAR-Bench`. Scope: register step 2 (runner part), steps 4, 5 and 6,
decisions D05, D07, D13, D16, D17, D21, and Contract 2 of
`_experiments/dataset_fix_20260915/impl/IMPLEMENTATION_SPEC.md`.

Files owned by this stream: `_experiments/scripts/benchmark.py`, `benchmark_multiturn.py`,
`benchmark_openrouter.py`, `merge_partial_results.py`, `serve.py`, `run_benchmark.sh`,
`run_master.sh`, `tools_kr.py`, `gen_tools_kr.py`, `tools_kr_text.json`, `tools_en.py`,
`runner/`, `chat_templates/`, `prompt_variants/`, `tests_runner/`, `_experiments/env/`.

## Commits

| commit | content |
|---|---|
| `e452faa` | schema arms: `tools_kr.py` generated from `agent.TOOLS`, `tools_en.py` retired, record writer, provenance guards |
| `aca0519` | serving registry, repaired chat templates, model revision pins |
| `4496844` | shared request/response layer and the two tool-calling loops |
| `5856972` | both runners rewritten as record writers; resume, partial runs, merger |
| `ac169b8` | mock-server test suite; tool-result truncation; T/NT budget symmetry |
| `9d5e689` | split environment pins, container recipes, registry-driven launcher |
| `c3f76fe` | tracked prompt-ablation variants |
| `bbba9b6` | repo-relative serving paths, environment pin file, guard tests |

## Register ids

| id | fix | where | verification |
|---|---|---|---|
| L5-018 | every record carries run id, config (model, revision, engine, parser, reasoning parser and mode, template sha, context, budget, temperature, seed, concurrency, TP) and provenance (both commits, parquet/db/model sha256, prompt and tools sha256, `streamlit_stubbed`, library versions); per round the raw content, reasoning length, `finish_reason`, usage, every tool call with raw arguments, every executed result; plus final text and stop reason. Server logs get a per-run name. | `runner/records.py`, `runner/provenance.py`, `runner/loop.py`, `run_benchmark.sh` | `test_contract2.py::test_every_case_gets_a_record_with_provenance_and_config`, `::test_a_tool_call_is_recorded_with_its_raw_arguments_result_and_source`, `test_guards.py::test_the_collected_provenance_carries_what_contract_2_asks_for` |
| L5-019 | every attempted case and turn is recorded with an explicit error type, HTTP status and message; exceptions are classified by status and class, not by string; a turn that errored is `stop_reason: error`, never "no call"; the runner verifies the record count against the case list and exits non-zero when it is short | `runner/client.py` (`_error_block`, `_status_of`), `runner/loop.py`, `runner/records.py` (`verify_run_complete`) | `test_contract2.py::test_a_gateway_reply_without_choices_is_an_error_and_not_a_silent_zero`, `::test_an_empty_reply_is_an_error_type_of_its_own`, `test_multiturn.py::test_a_turn_that_errors_is_recorded_as_an_error_and_not_as_no_call`, `test_resume.py::test_an_incomplete_run_exits_non_zero` |
| L5-024 | round count and stop reason recorded; `max_rounds` (5) and a ceiling of 8 calls per round, with the ceiling reported as an error type | `runner/loop.py` (`MAX_ROUNDS`, `MAX_CALLS_PER_ROUND`) | `test_contract2.py::test_the_round_ceiling_stops_the_loop_and_says_so` |
| C2-013 | the OpenAI client is built with `max_retries=0`; the runner retries itself, only on 429/5xx and transport errors, and records the attempt count per round | `runner/cli.py` (`open_client`), `runner/client.py` (`RETRYABLE_STATUS`) | `test_contract2.py::test_a_retryable_status_is_retried_and_the_attempts_are_recorded`, `::test_a_deterministic_4xx_is_not_retried` |
| C2-017 | a non-object argument is recorded with `args_is_object: false` and its raw text, is not executed, and becomes an `arguments_not_object` error instead of a `TypeError` | `runner/loop.py` (`_execute`), `runner/records.py` (`CallRecord`) | `test_contract2.py::test_arguments_that_are_not_an_object_are_flagged_and_not_executed`, `::test_unparsable_arguments_keep_the_raw_string` |
| C2-012 | one request/response layer for both runners: schema arm, prompt, budget, reasoning mode, gateway guard, empty-reply guard, provider pinning, retry policy. `benchmark_multiturn.py` takes the same options, including `--tools-lang`, `--max-tokens` and the provider options | `runner/client.py`, `runner/cli.py`, both runners | `test_multiturn.py::test_the_multi_turn_runner_sends_the_reasoning_mode_and_the_budget` |
| L5-005, D21 | parallel calls are sent as consecutive single-call turns for templates trained on one call; every call is executed and recorded before any error, and an error after a call does not discard it | `runner/client.py` (`history_turns`), `runner/loop.py`, `chat_templates/llama3_tools.jinja` | `test_tool_calls.py::test_parallel_calls_become_consecutive_single_call_turns`, `::test_every_llama_configuration_serialises`, `test_contract2.py::test_an_error_stops_the_case_but_keeps_the_calls_made_before_it` |
| L5-011 | the fallback parser strips reasoning blocks first, reads only explicit markers (`<tool_call>`, `[TOOL_CALLS]`, `<|python_tag|>`, `functools[...]`, `<function=...>`, `<\|tool_call\|>`), returns every call it finds, marks each `source: fallback` with the raw fragment, and gives it a nine-character alphanumeric id | `runner/client.py` (`parse_fallback_calls`, `fallback_call_id`) | `test_tool_calls.py`, 10 tests including `::test_a_json_object_in_prose_is_not_a_call` and `::test_a_fallback_call_id_is_nine_alphanumeric_characters` |
| C2-004 | the assistant turn goes back into the history with `reasoning_content` when the configuration has a reasoning parser | `runner/client.py` (`assistant_message`), `registry.reasoning_history_key` | `test_contract2.py::test_the_reasoning_goes_back_into_the_history` |
| C2-010 | the model's own text stays in the history and in the record; an oracle clarification turn gets a neutral reply instead of the gold annotation note; an end-to-end turn without a call keeps the model's answer instead of `(no tool call)` | `runner/loop.py` (`_oracle_turns`, `run_scenario`), both repaired templates | `test_multiturn.py::test_an_oracle_clarification_turn_gets_a_neutral_reply_not_the_gold_note`, `::test_an_e2e_turn_without_a_call_keeps_the_models_own_text_in_the_history`, `test_contract2.py::test_assistant_text_alongside_a_call_stays_in_the_history` |
| L4-016, C2-014, C2-015, L5-027 | runs write into a fresh directory and never read an old checkpoint; `--resume` reads only that directory, refuses records from another benchmark, refuses a directory holding partial files and refuses to skip every case; `--case-ids` requires `--partial` and writes a `.partial` file with its own run id; the merger reports the source run per key and refuses to fall back to an older record | `runner/records.py` (`resume_state`, `verify_run_complete`), `runner/cli.py`, `merge_partial_results.py` | `test_resume.py`, 9 tests |
| D16, C2-005, K3, L5-015 | `tools_kr.py` is generated from `agent.TOOLS` plus a Korean prose file, so names, parameters, types, enums, defaults, `required` lists and item schemas are identical; `tools_en.py` is retired and the English arm is the platform schema; the v3 Korean content (English column names, the real fraud-type table, the §VI STR classification, `fraud_type` enum without code 6) is applied; the `EN_KO_PARAM_MAP` reversion is gone | `gen_tools_kr.py`, `tools_kr_text.json`, `tools_kr.py`, `runner/arms.py`, `tools_en.py` | `test_schema_arms.py`, 15 tests incl. `::test_the_structures_are_identical`, `::test_the_generated_arm_is_up_to_date`, `::test_tools_en_is_retired` |
| C2-006 | the value-normalisation map that rewrote Korean FIU keywords and glossary terms is deleted; the runner executes the arguments the model sent | `tools_kr.py` (generated, no `normalize_args`), `runner/loop.py` | `test_schema_arms.py::test_there_is_no_value_normalisation_map_left` |
| D13, R1-N5 | one response-language rule in both arms: "answer in the language of the user's question" / "사용자 질문의 언어로 답하세요" | `tools_kr_text.json`, platform prompt | `test_schema_arms.py::test_both_prompts_carry_the_same_response_language_rule` |
| R1-N4 | the Korean prompt states the real column names, the INTEGER date range and format, the 16-digit account ids, the bank code ranges, the amount value count and the Korean `fraud_description` values; the 15-step flow and the "always query first" block are gone | `tools_kr_text.json` | `test_schema_arms.py::test_the_korean_prompt_states_the_real_column_names_and_fraud_labels` |
| D17, L6-032 | `--tools-lang` on both runners, so single-turn, multi-turn oracle, end-to-end and STR can all run on the Korean schema | `runner/cli.py`, `benchmark_multiturn.py` | `test_multiturn.py::test_the_multi_turn_runner_sends_the_reasoning_mode_and_the_budget` (schema sent), `test_schema_arms.py` |
| L3-023 | the Anthropic path and its Korean key reversion are gone; the cohort has no Anthropic model and the runner no longer carries the code | `benchmark.py` (rewritten) | absence; `grep -n '_KO_EN_KEY_MAP' _experiments/scripts` returns nothing |
| R2C-004 | the prompt to evaluate is the arm prompt; the two ablation variants are tracked, the variant name and the prompt hash are recorded, and the variant goes into the run id | `prompt_variants/`, `runner/arms.py`, `runner/cli.py` | `test_schema_arms.py::test_a_prompt_variant_changes_the_prompt_hash_and_is_named`, `test_contract2.py::test_the_prompt_variant_is_recorded_and_lands_in_the_run_id` |
| D05, D07, L5-009, L5-010, L5-008, L5-025, C2-007, C2-018, C2-001, L5-006, L5-012, R1-R3 | one registry entry per configuration: model and revision, template with sha256, tool-call parser, reasoning parser, one labelled mode, >= 32k context (E2E larger), 16k output for reasoning configs, temperature 0, seed, concurrency 1, TP size. Phi-4-mini back to 32768; the finance Qwen on `hermes`; Kanana-2-Think on its own template with a reasoning parser; Qwen3.6 with a reasoning parser and an explicit mode; the Mistral models on the vendor format; the Llama-3.x and Phi-4-mini templates repaired in the repository with hashes and a note of what changed. Tool results are truncated to the same token count in every arm | `runner/registry.py`, `chat_templates/`, `runner/preflight.py`, `runner/loop.py` | `test_serving.py`, 20 tests; `test_templates.py`, 7 tests |
| L5-017 | the launcher takes the devices from `--gpu`, refuses a device count that does not match the configuration's TP size, and exits non-zero when the server does not answer `/health`; the orchestrator lists the configurations a host cannot serve and exits non-zero with the failures | `serve.py`, `run_benchmark.sh`, `run_master.sh`, `runner/plan.py` | `python -m _experiments.scripts.serve --config llama-3.3-70b --gpu 0,1 --print-only` exits 2 with the reason; `bash -n` on both scripts |
| L5-014 | the OpenRouter path pins the provider (`allow_fallbacks: false`, `require_parameters: true`, order and quantizations) and records the provider, the served model and the usage per round | `benchmark_openrouter.py`, `runner/cli.py` (`_provider`), `runner/records.py` | code review; the provider block is built only when pinned and the record carries `provider` / `served_model` |
| L5-020, C1-004, C2-016, R2C-003 | the run refuses to start unless the platform tool layer imports, the `hofinet` columns are the released ones, the Streamlit cache is stubbed and the pinned hashes match; every value is recorded. Model revisions are pinned in `model_revisions.json` and passed as `--revision`/`--tokenizer-revision`; a configuration without one refuses to serve. Both runners reach the database through the platform's single entry point | `runner/provenance.py`, `runner/cli.py`, `model_revisions.json`, `runner/registry.py` | `test_guards.py`, 7 tests; `test_serving.py::test_an_unpinned_revision_refuses_to_serve` |
| R1-R4 | the serving stack and the evaluation stack are pinned in separate files, which resolves the numpy conflict (serving follows vLLM and torch, evaluation follows the tool layer's numpy 2); `check_env` compares the two files with each other and with what is installed; container recipes for both | `_experiments/env/` , `requirements.txt` | `python -m _experiments.env.check_env` names every difference; run in the scratch venv it reported four |
| C2-001 (preflight) | before every run the system prompt, the tool schema and the longest question are rendered and the headroom asserted; with the serving tokenizer when it can be loaded offline, otherwise a calibrated byte estimate | `runner/preflight.py`, `runner/cli.py` | `test_serving.py::test_the_preflight_refuses_the_context_that_was_registered_for_phi_4_mini`, `::test_every_configuration_clears_the_preflight_on_the_korean_arm` |

### Not fixed here, and why

| id | reason |
|---|---|
| L5-001, L5-004, L5-023, R1-R1 | the rerun itself (step 11). The runner side is ready; the run is a GPU job. |
| L5-003 | the pre-flight gate suite is step 10 (WS-F). The pieces this stream owns (prompt budget, schema parity, resume refusal, record verification) are in place and callable. |
| L5-002, L5-021, L5-022, L6-* | manuscript and repository-release work, after the rerun. |
| R1-R4 (run-to-run variance) | the lock files and `seed` are in place; the repeated-run variance measurement belongs to the analysis step, on real runs. |
| D04, D22 | STR quality checker and the blind evaluation, after the rerun. |

## Configuration registry

Produced by `python -m _experiments.scripts.runner.plan --format markdown`. Every row also carries
temperature 0, seed 20260925, concurrency 1, and `--enable-auto-tool-choice`.

| Configuration | Model | Mode | Tool parser | Reasoning parser | Template | Template sha | TP 48G | TP 80G | Context | Context E2E | Output |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A.X-4.0-Light (7B) | skt/A.X-4.0-Light | none | hermes | - | model's own | - | 1 | 1 | 32768 | 65536 | 8192 |
| A.X-4.0 (72B) | skt/A.X-4.0 | none | hermes | - | model's own | - | 4 | 2 | 32768 | 65536 | 8192 |
| EXAONE-4.0-1.2B | LGAI-EXAONE/EXAONE-4.0-1.2B | nothink | hermes | - | model's own | - | 1 | 1 | 32768 | 65536 | 8192 |
| EXAONE-4.0-32B | LGAI-EXAONE/EXAONE-4.0-32B | nothink | hermes | - | model's own | - | 2 | 1 | 32768 | 65536 | 8192 |
| Kanana-2-Instruct | kakaocorp/kanana-2-30b-a3b-instruct | none | functionary_kanana | - | kanana_tool_calls/kanana_tool_calls/lmalign_v1.jinja | 8817945446b3 | 2 | 1 | 32768 | 65536 | 8192 |
| Kanana-2-Think | kakaocorp/kanana-2-30b-a3b-thinking-2601 | always_on | functionary_kanana | deepseek_r1 | model's own | - | 2 | 1 | 32768 | 65536 | 16384 |
| Llama-Open-Finance-8B | DragonLLM/Llama-Open-Finance-8B | none | llama3_json | - | llama3_tools.jinja | 6a09afa2de3d | 1 | 1 | 32768 | 32768 | 8192 |
| Qwen-Open-Finance-R-8B | DragonLLM/Qwen-Open-Finance-R-8B | always_on | hermes | qwen3 | model's own | - | 1 | 1 | 32768 | 65536 | 16384 |
| gpt-oss-20B (NT) | openai/gpt-oss-20b | effort_low | openai | openai_gptoss | model's own | - | 1 | 1 | 32768 | 65536 | 16384 |
| gpt-oss-20B (T) | openai/gpt-oss-20b | effort_high | openai | openai_gptoss | model's own | - | 1 | 1 | 32768 | 65536 | 16384 |
| gpt-oss-120B (NT) | openai/gpt-oss-120b | effort_low | openai | openai_gptoss | model's own | - | 4 | 2 | 32768 | 65536 | 16384 |
| gpt-oss-120B (T) | openai/gpt-oss-120b | effort_high | openai | openai_gptoss | model's own | - | 4 | 2 | 32768 | 65536 | 16384 |
| Llama-3.2-3B | meta-llama/Llama-3.2-3B-Instruct | none | llama3_json | - | llama3_tools.jinja | 6a09afa2de3d | 1 | 1 | 32768 | 65536 | 8192 |
| Llama-3.3-70B | meta-llama/Llama-3.3-70B-Instruct | none | llama3_json | - | llama3_tools.jinja | 6a09afa2de3d | 4 | 2 | 32768 | 65536 | 8192 |
| Hermes-3-8B | NousResearch/Hermes-3-Llama-3.1-8B | none | hermes | - | model's own | - | 1 | 1 | 32768 | 32768 | 8192 |
| Ministral-3-3B | mistralai/Ministral-3-3B-Instruct-2512 | none | mistral | - | model's own | - | 1 | 1 | 32768 | 65536 | 8192 |
| Mistral-Small-24B | mistralai/Mistral-Small-3.2-24B-Instruct-2506 | none | mistral | - | model's own | - | 2 | 1 | 32768 | 65536 | 8192 |
| Phi-4-mini | microsoft/Phi-4-mini-instruct | none | phi4_mini_json | - | phi4_mini_tools.jinja | 802cb284daab | 1 | 1 | 32768 | 65536 | 8192 |
| Qwen3.5-4B (NT) | Qwen/Qwen3.5-4B | nothink | qwen3_coder | qwen3 | model's own | - | 1 | 1 | 32768 | 65536 | 16384 |
| Qwen3.5-4B (T) | Qwen/Qwen3.5-4B | think | qwen3_coder | qwen3 | model's own | - | 1 | 1 | 32768 | 65536 | 16384 |
| Qwen3.5-27B (NT) | Qwen/Qwen3.5-27B | nothink | qwen3_coder | qwen3 | model's own | - | 2 | 1 | 32768 | 65536 | 16384 |
| Qwen3.5-27B (T) | Qwen/Qwen3.5-27B | think | qwen3_coder | qwen3 | model's own | - | 2 | 1 | 32768 | 65536 | 16384 |
| Qwen3.6-27B | Qwen/Qwen3.6-27B | think | qwen3_xml | qwen3 | model's own | - | 2 | 1 | 32768 | 65536 | 16384 |
| Qwen3.6-35B-A3B | Qwen/Qwen3.6-35B-A3B | think | qwen3_xml | qwen3 | model's own | - | 2 | 1 | 32768 | 65536 | 16384 |
| xLAM-2-3B | Salesforce/xLAM-2-3b-fc-r | none | xlam | - | model's own | - | 1 | 1 | 32768 | 32768 | 8192 |
| xLAM-2-70B | Salesforce/Llama-xLAM-2-70b-fc-r | none | xlam | - | model's own | - | 4 | 2 | 32768 | 32768 | 8192 |
| Gemma-4-E4B | google/gemma-4-E4B-it | nothink | gemma4 | - | model's own | - | 1 | 1 | 32768 | 65536 | 8192 |
| Gemma-4-31B | google/gemma-4-31B-it | nothink | gemma4 | - | model's own | - | 2 | 1 | 32768 | 65536 | 8192 |

`TP 48G` is the plan for hosts with 48 GB cards, `TP 80G` for the on-demand 80 GB hosts.
The five configurations that need the four-card host are `ax-4.0`, `llama-3.3-70b`, `xlam-70b`,
`gpt-oss-120b-nt` and `gpt-oss-120b-t`; everything else fits a two-card host.
`python -m _experiments.scripts.runner.plan --host-gpus N` prints the device assignment for a host
and names the configurations it cannot serve.

Model revisions: three of the 25 models are pinned in `_experiments/scripts/model_revisions.json`
(the ones already in the local cache). The rest are filled by whoever downloads them; until then a
configuration refuses to emit serving arguments without `--allow-unpinned-revision`.

## What still needs a GPU smoke test

Nothing here has touched a GPU. Before the rerun, one round-trip per item:

1. **Every repaired template** (`llama3_tools.jinja`, `phi4_mini_tools.jinja`): that the tool-call
   parser still matches what the template renders, and that a tool result arrives unescaped.
2. **Kanana-2-Think**: that its own template loads, that `--reasoning-parser deepseek_r1` produces
   reasoning tokens and that it does not swallow the tool calls. This is the L5-008 row, and the
   registry entry is a plan, not a measurement.
3. **Qwen-Open-Finance-R-8B on `hermes`**: that calls now arrive natively rather than through the
   fallback parser. The record's `source` field is the measurement.
4. **Qwen3.6 with `--reasoning-parser qwen3` and explicit `enable_thinking`**: that the mode is
   actually applied, measured as reasoning characters per round.
5. **The Mistral vendor format** (`--tokenizer-mode mistral --config-format mistral
   --load-format mistral`): that the server starts and that the tool_call_id rule is satisfied.
6. **gpt-oss reasoning effort**: that `reasoning_effort` high and low produce different reasoning
   lengths. The 2026 multi-turn (T)/(NT) rows were the same configuration twice.
7. **The prompt budget with the real tokenizers**: the preflight fell back to a byte estimate here.
   With the serving tokenizer the Korean arm measured about 7.9k prompt tokens on the cached Qwen
   tokenizer against an estimate of 9.6k, so the estimate is conservative, but it should be
   confirmed per model.
8. **Each configuration's maximum position embeddings** for the 65,536-token end-to-end context. The
   entries that cap at 32,768 are marked in the table; a server that refuses the larger context
   needs its registry row lowered rather than a command-line override.

## Verification run without a GPU

`python -m pytest _experiments/scripts/tests_runner -q` : **102 passed**.

The suite runs both runners end to end through the real `openai` client against a mock
OpenAI-compatible HTTP server (`tests_runner/mock_server.py`), and covers the Contract 2 record
shape, the gateway and empty-reply guards, the retry policy, parallel-call serialisation, the
fallback parser, resume refusals, partial runs, the environment guards, schema-arm parity, the
serving registry, the repaired templates and the prompt budget.

Contract 2 was also checked against the scorer that consumes it: 48 real single-turn cases and 5
real multi-turn scenarios were run against the mock server and then scored with
`python -m _experiments.scripts.scoring.score_runs`, with no adapter. Coverage came back complete in
all three settings, and the eval file carried the runner's `config` and `provenance` blocks
unchanged.

## What the other streams need to know

- **Data streams**: the runner sends the platform parameter names in both arms and executes the
  model's arguments unchanged, so gold parameter keys are the platform keys in every arm, as
  Contract 1 says. Nothing is renamed before execution or before scoring any more.
- **Data streams**: a tool result longer than about 4,000 tokens reaches the model truncated, the
  same way in every arm; the record keeps the whole result, so `result_row_count_*` checks are
  unaffected. A case whose gold depends on the model reading past that point will not work.
- **Scoring**: run records live in the directory the runner was given, one `*.jsonl` per run plus a
  `*.manifest.json`; a `.partial.jsonl` is a filtered run and must not be aggregated with a full one.
  `run_id` is in every line.
- **Scoring**: tool names are recorded exactly as the server returned them, serving artefacts
  included, as the scorer asked.
- **The rerun**: one column is one command
  (`bash _experiments/scripts/run_benchmark.sh --config <id> --gpu <devices> --mode single|oracle|e2e
  --tools-lang kr --out-root <fresh root>`), and the output directory is named for the column, so two
  columns can never share one.
