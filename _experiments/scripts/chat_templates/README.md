# Chat templates served with the benchmark

`hashes.json` carries the sha256 of every file here; the same hash goes into the
`config.chat_template_sha256` field of every run record, so a record says which
template produced it (R2C-003, D21).

A configuration that names no template here is served on the model's own
template. `_experiments/scripts/runner/registry.py` is the list of which is which.

## `llama3_tools.jinja`

Base: the `chat_template` of `meta-llama/Llama-3.1-8B-Instruct`, snapshot
`0e9e39f`. Served for `Llama-3.2-3B`, `Llama-3.3-70B` and
`Llama-Open-Finance-8B`, which ship the same template.

Three changes, all in the message loop; the system block, the tool block and the
tools-in-first-user-message handling are untouched.

1. A tool result that is a string is emitted as it is. The vendor template tests
   `message.content is mapping or message.content is iterable`, and a string is
   iterable in Jinja, so every tool result went through `| tojson` and reached the
   model as a JSON string literal with escaped quotes: `"[{\"date\": 20241015}]"`
   (C2-007).
2. An assistant message with more than one tool call renders one assistant turn
   per call instead of raising `This model only supports single tool-calls at
   once!`. That exception aborted the request in the round after a parallel call
   and cost Llama-3.2-3B 203 of 1,258 cases (L5-005). The runner sends the calls
   serialised for the same reason (D21); the template no longer makes the
   conversation unrenderable if one slips through.
3. An assistant message that carries text as well as calls keeps its text. The
   vendor template drops it, so the model never saw what it had said (C2-010).

## `phi4_mini_tools.jinja`

Base: `_experiments/scripts/tool_chat_template_phi4_mini.jinja`, the file the
2026 runs used (kept, unused, for provenance).

1. The tool-result branch tested `message.role == "tools"`. The API sends
   `"tool"`, so no tool result ever took that branch and results reached the model
   through the plain-content branch without the `{"result": ...}` wrapper the
   model is trained on. Both role names are accepted now (C2-018).
2. Previous assistant calls were rendered as a bare
   `{"name": ..., "arguments": ...}` object while the system text tells the model
   to emit `functools[{...}, ...]`. History and instruction now agree (C2-018).
3. `arguments` is emitted as JSON whether it arrives as a JSON string (from the
   API) or as an object (from a replay). It used to render a Python `dict` repr.
4. Assistant text alongside calls is kept (C2-010).

## `kanana_tool_calls/lmalign_v1.jinja`

Unchanged, and now served only for `kanana-2-30b-a3b-instruct`.
`kanana-2-30b-a3b-thinking-2601` used to be served on this same functionary
template with no reasoning parser, which is why the "thinking" row showed no
reasoning at all (L5-008). It is now served on its own template (no
`--chat-template`) with `--reasoning-parser deepseek_r1`.

## Still needs a GPU smoke test

Every repaired template needs one round-trip against the real server before the
rerun: that the tool-call parser still matches what the template renders, and, for
Kanana-2-Think and Qwen-Open-Finance-R-8B, that reasoning tokens appear and that
the reasoning parser does not swallow the tool calls.
