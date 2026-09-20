# Chat templates served with the benchmark

`hashes.json` carries the sha256 of every file here; the same hash goes into the
`config.chat_template_sha256` field of every run record, so a record says which
template produced it and a result can be tied to the exact prompt text the model
saw.

A configuration that names no template here is served on the model's own
template. `_experiments/scripts/runner/registry.py` is the list of which is which.

Each template below is a vendor template with a small number of deliberate
differences. They are listed because a template decides what the model is shown,
so a difference in it is a difference in the experiment, not a detail of the
serving stack.

## `llama3_tools.jinja`

Base: the `chat_template` of `meta-llama/Llama-3.1-8B-Instruct`, snapshot
`0e9e39f`. Served for `Llama-3.2-3B`, `Llama-3.3-70B` and
`Llama-Open-Finance-8B`, which ship the same template.

Three differences, all in the message loop; the system block, the tool block and
the tools-in-first-user-message handling are untouched.

1. A tool result that is a string is emitted as it is. The vendor template tests
   `message.content is mapping or message.content is iterable`, and a string is
   iterable in Jinja, so every tool result goes through `| tojson` and reaches the
   model as a JSON string literal with escaped quotes:
   `"[{\"date\": 20241015}]"`. The model is then reading escaped text rather than
   a tool result.
2. An assistant message with more than one tool call renders one assistant turn
   per call instead of raising `This model only supports single tool-calls at
   once!`. That exception makes the whole conversation unrenderable as soon as a
   model emits a parallel call, which loses every later turn of a case rather
   than the one call. The runner serialises parallel calls for the same reason;
   the template no longer depends on it having done so.
3. An assistant message that carries text as well as calls keeps its text. The
   vendor template drops it, so the model never sees what it itself said.

## `phi4_mini_tools.jinja`

Base: `_experiments/scripts/tool_chat_template_phi4_mini.jinja`, kept unused for
provenance.

1. The tool-result branch tested `message.role == "tools"`. The API sends
   `"tool"`, so no tool result takes that branch and results reach the model
   through the plain-content branch without the `{"result": ...}` wrapper the
   model is trained on. Both role names are accepted.
2. Previous assistant calls were rendered as a bare
   `{"name": ..., "arguments": ...}` object while the system text tells the model
   to emit `functools[{...}, ...]`. History and instruction agree, so the model is
   not shown one format and asked for another.
3. `arguments` is emitted as JSON whether it arrives as a JSON string (from the
   API) or as an object (from a replay). A Python `dict` repr is not JSON and the
   model is not trained on it.
4. Assistant text alongside calls is kept.

## `kanana_tool_calls/lmalign_v1.jinja`

Unchanged, and served only for `kanana-2-30b-a3b-instruct`.
`kanana-2-30b-a3b-thinking-2601` is served on its own template (no
`--chat-template`) with `--reasoning-parser deepseek_r1`, because a functionary
template with no reasoning parser yields no reasoning at all, which would make a
thinking configuration indistinguishable from a non-thinking one.

## Before a template is used for a run

A template change needs one round-trip against the real server: that the
tool-call parser still matches what the template renders, and, for the
reasoning configurations, that reasoning tokens appear and that the reasoning
parser does not swallow the tool calls. Both failures are silent in the output,
so nothing downstream catches them.
