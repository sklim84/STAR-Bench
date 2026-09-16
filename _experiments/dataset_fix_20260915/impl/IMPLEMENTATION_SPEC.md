# STAR-Bench audit fixes: implementation spec (2026-09-16)

Source of truth for WHAT to fix: `../round2/FINAL/register_final.json` (179 issues; field `fix_ko`) and the
decisions below (all 23 are final). This file fixes the shared CONTRACTS so parallel work streams fit together.
Deadline: ICLR 2027 submission 2026-09-25; the rerun needs 2–3 days, so code/data fixes must land fast.

## Repository policy
- Work on branch `audit-fixes` in each repo (create from current `main`). Commit in small logical commits with
  `git -c user.name=recordame -c user.email=ai.tx.now.01@gmail.com commit`. Commit messages end with
  two trailer lines:
  `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01SV9keZjffkrjNC4HuNDkyD`.
  Do NOT push, do NOT open PRs, do NOT touch `main`.
- Never modify or delete existing results (`_experiments/results_*`, `_backup`, `_contaminated_*`, `results_mt_smoke_*`),
  `_experiments/human_eval/`, or `_experiments/dataset_fix_20260915/` (except your own notes under `impl/`).
- No GPU jobs, no LLM/API calls, no model downloads, do not modify conda environments. Use venvs inside the scratchpad.
- No hardware names (H200, GB10, ...) in paths or file names. No secrets in files.
- Write code that reads like the surrounding code. Keep comments sparse.

## Final decisions (1-based option numbers)
D01 h stays the primary metric, defined as "every gold tool appears among the calls"; tool-set F1 computed for the appendix.
D02 Main table reports h, a, c only. c = every turn has h=1. a = mean over cases that have parameter checks.
    p and o are still computed and stored but are not headline metrics.
D03 FULL REBUILD: single-turn account ids (268 cases) become role-appropriate real HOFINET accounts; the 45 STR
    multi-turn scenarios are rewritten on real accounts/banks/amounts/time slots; oracle tool results are the outputs of
    executing the gold calls on the fixed platform.
D04 STR quality checker redesigned after the rerun (not in this phase), drafts must be stored.
D05 One labeled mode per model; T/NT pairs only for Qwen3.5 (enable_thinking) and gpt-oss (reasoning_effort high/low).
    Reasoning configs get a 16k output budget; finish_reason is recorded; reasoning is sent back in history the way the
    chat template expects; Kanana-2-Think served with its own template + reasoning parser (verified by smoke test later).
D06 Deterministic DuckDB/NetworkX replacement for all Memgraph-backed paths (detect_aml_patterns all modes,
    analyze_network hops>2). Document that rings/layering do not occur in HOFINET; funnel requires outbound flows to exist.
D07 All 28 configurations and all four 2×2 cells on ONE pinned local vLLM stack, concurrency 1, ≥32k context.
    DEVIATION (2026-09-16, deliberate): the registry default is `CONCURRENCY = 8`, not 1. 28 configurations ×
    3 columns do not fit the 2026-09-25 deadline one request at a time, and the tool-layer race that forced
    serial execution is fixed (per-call DuckDB cursors; 504 tagged concurrent calls at 6 and 10 workers
    identical to serial, 0 errors, 0 wrong tags). Everything else in D07 stands: one stack, ≥32k context, one
    pinned revision per configuration. What batching can still change is the server's own decoding, so the
    cost is measured rather than assumed: `preflight/run_plan.json` carries a batching-agreement run
    (`qwen35-4b-nt`, full single-turn benchmark, twice at 8 and once at 1, three separate output directories),
    `run_master.sh --agreement` runs it, and gate 5 fails while the registry default differs from 1 and the
    plan holds no such run. The agreement number is measured after the rerun and reported in the appendix;
    a configuration whose agreement is low enough to move a ranking is rerun with `--concurrency 1`.
D08 System prompt: fix factual errors (fraud_description real values, date range/format, account id format), remove the
    15-step recommended flow, neutral wording. Prompt ablation (listing reporting tools) is re-run later from tracked code.
D09 Delete the 143 `*_ex01..08` duplicate cases.
D10 General concept explanations are no-tool; glossary/FIU cases are rewritten so they need the catalog content.
    Fix the 16 clear mislabels; the 14 ambiguous ones accept both tool and no-tool. No Korean aliases in the glossary;
    tool descriptions say keys are English; FIU catalog stays an excerpt (disclosed).
D11 Ambiguous tool boundaries: add a discriminating cue to each question so exactly ONE gold remains; fix tool
    descriptions accordingly (no alternative-tool acceptance except D10's ambiguous 14).
D12 Keep the XGBoost model; call its output a risk score (not a calibrated probability); remove `is_fraud_actual` from
    model-visible outputs; `score_account_risk` label-based history stays but is described; predict_fraud gold inputs
    re-mapped into the data distribution (868fd28 R3/R7 mapping: 48 real amount values, fund_type 4 redistributed).
D13 Every schema arm: answer in the language of the user's question.
D14 BFCL comparison removed from the paper (no work here).
D15 Anonymous mirror before submission (later step).
D16 `tools_en.py` retired. English arm = platform `agent.TOOLS` + platform English prompt. Korean arm = `tools_kr.py`
    with v3 schema changes, structurally identical to `agent.TOOLS` (same names, params, enums, defaults, required, items);
    an automated parity test enforces this.
D17 All main-table columns (single-turn, multi-turn oracle, E2E, STR) run with the Korean schema + Korean prompt.
D18 Monitoring rules redefined to fit HOFINET value structure (R001 night bulk must be able to fire on real data,
    e.g. time slots incl. 21 with a data-grounded amount band; R003 = repeated identical amounts per account, not
    "amount % 1M == 0"); account_id and dates honored by every rule.
D19 Clarification cases only when a schema-required argument (or an unresolved reference to it) is missing.
    Success = no tool call AND non-empty text that is not an unparsed tool-call JSON. validate_str_fields cases get drafts.
D20 Regulatory-reporting results reported case-weighted with per-tool n and bootstrap CIs (analysis step, later).
D21 Vendor-recommended formats (Mistral tokenizer/config format, Kanana own template); broken templates replaced by
    minimally repaired templates (published with hashes); parallel calls serialized into consecutive single-call turns
    for templates that reject them; calls executed before an error are recorded and scored, with an error flag.
D22 New blind expert evaluation on rerun outputs (later). D23 Difficulty relabeled by explicit rules (data step).

## Contract 1: gold format (single-turn `benchmarks/`, `benchmarks_en/`)
Keep existing fields. Changes:
- Parameter keys are the platform English keys for every arm (the KR schema has identical structure).
- `query_transactions` checks: replace `sql_contains` with
  `"sql_conditions": [{"column": "fraud_type", "op": "=", "value": 7}, ...]` (ops: = != > >= < <= IN BETWEEN LIKE)
  and keep `"sql_valid": true`. Each case that expects query_transactions also gets `"reference_sql"` under
  `expected.reference_calls.query_transactions.sql` (executable on HOFINET) for gold-call execution and oracle history.
- Free-string FIU/glossary args (`keyword`, `term`) keep the gold string; the evaluator compares the RESULT SETS the
  platform returns for the model's and the gold's value (pure function of the catalog).
- Missing optional parameters are filled with schema defaults before comparison (evaluator side); gold may keep them.
- Alternatives (only where D10 allows): `expected.alternatives = [{"abstain": true}]` or
  `[{"tools_must_include": [...], "param_checks": {...}}]`; score = best over primary and alternatives.
- Clarification cases: `expected.expect_clarification = true` (no tool call, non-empty text).
- Every change is produced by a committed script with a log; data files carry no ad-hoc edits.

## Contract 2: run record (JSONL, one line per case or per multi-turn turn)
```
{"run_id","case_id","turn"(multi-turn only),"setting":"single|oracle|e2e","tools_lang":"kr|en","query_lang":"kr|en",
 "config":{"model","model_revision","engine","engine_version","parser","reasoning_parser","reasoning_mode",
           "chat_template_sha256","max_model_len","max_tokens","temperature","seed","concurrency"},
 "provenance":{"star_bench_commit","platform_commit","data_sha256","db_sha256","model_file_sha256",
               "system_prompt_sha256","tools_sha256","streamlit_stubbed","started_at"},
 "rounds":[{"idx","finish_reason","content","reasoning_chars","usage",
            "tool_calls":[{"id","name","arguments_raw","arguments","source":"native|fallback","valid_json"}],
            "executed":[{"tool_call_id","name","arguments","result","error"}],
            "error":null|{"type","status","message"},"attempts"}],
 "final_text","stop_reason":"no_tool_call|max_rounds|error|length","error":null|{"type","message","round"},
 "elapsed_s"}
```
Scores are NOT stored in run records; the evaluator reads records + gold and writes eval files. Old checkpoints are
never read by new runs (fresh output directories only).

## Contract 3: evaluator output
Per case: h, r, p, a (null when no checks), o (null when no order), f1_tools, abstain_ok, clarification_ok,
error_flag, per-check details. Per multi-turn turn: h, a, context_hit (from the run's own executed results in E2E),
turn_error; per scenario: c (all turns h=1). Aggregates carry n for every metric.

## Work streams and ownership
- WS-A platform (`STAR-Bench-Web`): register step 3 + prompt (D08/D13) + D06/D12/D18 + DB/hash guards (step 2 platform
  part) + tests incl. gold-call smoke harness that reads benchmark files from a path argument.
- WS-B evaluator (`STAR-Bench/_experiments/scripts/evaluator.py` + new `scoring/` module + tests): register step 7,
  D01/D02/D19/D21 scoring, contracts 1–3.
- WS-C runners (`benchmark.py`, `benchmark_multiturn.py`, `benchmark_openrouter.py`, `run_benchmark.sh`, `tools_kr.py`,
  model registry, templates): register steps 2 (runner part), 4, 5, 6 (config files; GPU smoke later), contract 2.
- WS-D single-turn data: register step 8, contract 1, D03/D09/D10/D11/D12/D19/D23.
- WS-E multi-turn rebuild: register step 9 on the fixed platform (after WS-A), D03.
- WS-F pre-flight suite: register step 10 (data linter, gold-call execution, evaluator counterexamples, parity tests,
  mock-server runner dry run, canary/anomaly gates definition).

## Hardware available for the rerun (for serving configs; do not put hardware names in paths)
- Co-author 1: 2–3 servers with 2× NVIDIA L40S (48 GB) each.
- Co-author 2: one server with 4× L40S, plus on-demand servers via VESSL.
Serving configs must fit these (e.g., 70B-class BF16 needs TP4 on 4× L40S; gpt-oss-120B MXFP4; ≥32k context).
