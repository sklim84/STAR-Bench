"""One request/response layer for both runners.

Everything that decides what a model is asked and how its answer is read lives
here: schema arm and prompt, token budget, the labelled reasoning mode, the
gateway `choices` guard, the empty-reply guard, provider pinning, the retry
policy, the fallback parser and the serialisation of parallel calls. The
single-turn and the multi-turn runner both go through `ModelClient.round`, so
neither can drift from the other the way the multi-turn runner did (it applied no
reasoning mode, no token budget and no gateway guard at all).

The layer never rewrites what the model sent. A tool name or an argument goes to
the tool layer and into the record exactly as it arrived, because the scorer
reports serving artefacts as serving artefacts and cannot report what the runner
has already cleaned up.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .records import CallRecord

__all__ = ["ChatOptions", "RoundResult", "ModelClient", "parse_fallback_calls",
           "fallback_call_id", "strip_reasoning_markup", "RETRYABLE_STATUS"]

# A 429 or a 5xx is worth another attempt; a 400 is the template or the request
# and will fail the same way every time.
RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


def fallback_call_id(round_idx: int, index: int) -> str:
    """Nine alphanumeric characters, which is what the Mistral server requires.

    The old `fallback_000` ids broke that rule and produced 948 HTTP 400s in the
    multi-turn runs.
    """
    return f"F{round_idx:02d}{index:02d}".ljust(9, "0")[:9]


# ---------------------------------------------------------------------------
# Fallback parsing
# ---------------------------------------------------------------------------

_THINK_BLOCK = re.compile(
    r"<(think|thinking|reasoning)>.*?</\1>|<\|thinking\|>.*?<\|/thinking\|>", re.S | re.I)
_THINK_OPEN = re.compile(r"<(think|thinking|reasoning)>.*$", re.S | re.I)


def strip_reasoning_markup(text: str) -> str:
    """Removes reasoning blocks before anything is read as a tool call.

    A model that reasons about calling `generate_str` is not calling it. The old
    parser read the reasoning text as well and accepted any JSON object with a
    `name` key, which is how a plan became a call.
    """
    if not text:
        return ""
    out = _THINK_BLOCK.sub(" ", text)
    return _THINK_OPEN.sub(" ", out)


def _loads(text: str) -> tuple[Any, bool]:
    try:
        return json.loads(text), True
    except (json.JSONDecodeError, ValueError):
        return text, False


def _call_from_obj(obj: Any) -> tuple[str, Any] | None:
    if not isinstance(obj, dict):
        return None
    if isinstance(obj.get("function"), dict) and isinstance(obj["function"].get("name"), str):
        func = obj["function"]
        return func["name"], func.get("arguments", {})
    if isinstance(obj.get("name"), str):
        for key in ("arguments", "parameters", "args"):
            if key in obj:
                return obj["name"], obj[key]
    return None


def _objects(text: str) -> list[Any]:
    """Top-level JSON values inside a fragment, in order."""
    decoder = json.JSONDecoder()
    out, i = [], 0
    while i < len(text):
        ch = text[i]
        if ch in "{[":
            try:
                obj, end = decoder.raw_decode(text, i)
            except json.JSONDecodeError:
                i += 1
                continue
            out.append(obj)
            i = end
            continue
        i += 1
    return out


# Every explicit tool-call marker a served model in the cohort emits. A bare JSON
# object in prose is NOT one of them: that path is what let reasoning text become
# a call, and it is gone.
_TAGGED = (
    re.compile(r"<tool_call>(.*?)(?:</tool_call>|$)", re.S | re.I),
    re.compile(r"<\|tool_call\|>(.*?)(?:<\|/tool_call\|>|$)", re.S | re.I),
    re.compile(r"\[TOOL_CALLS\]\s*(\[.*?\]|\{.*?\})", re.S),
    re.compile(r"<\|python_tag\|>(.*?)(?:<\|eom_id\|>|<\|eot_id\|>|$)", re.S),
    re.compile(r"functools\s*(\[.*?\])", re.S),
    re.compile(r"<tool▁call▁begin\|?>(.*?)(?:<\|?tool▁call▁end\|?>|$)", re.S),
)
_FUNCTION_TAG = re.compile(r"<function=([A-Za-z0-9_.\-]+)>(.*?)(?:</function>|$)", re.S)


def parse_fallback_calls(content: str, round_idx: int) -> list[CallRecord]:
    """Tool calls the server did not parse, read from explicit markers only.

    Returns every call it finds, each marked `source="fallback"` with the raw
    fragment kept, so the share of a model's calls that needed the fallback can be
    reported.
    """
    text = strip_reasoning_markup(content or "")
    if not text.strip():
        return []
    found: list[tuple[str, Any, str]] = []   # name, arguments, raw fragment
    for pattern in _TAGGED:
        for match in pattern.finditer(text):
            fragment = match.group(1).strip()
            for obj in _objects(fragment) or ([_loads(fragment)[0]] if fragment else []):
                items = obj if isinstance(obj, list) else [obj]
                for item in items:
                    call = _call_from_obj(item)
                    if call:
                        found.append((call[0], call[1], fragment))
    for match in _FUNCTION_TAG.finditer(text):
        name, body = match.group(1), match.group(2).strip()
        args, _ok = _loads(body) if body else ({}, True)
        found.append((name, args, match.group(0)))

    calls: list[CallRecord] = []
    seen: set[str] = set()
    for name, args, _fragment in found:
        key = f"{name}|{json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)}"
        if key in seen:
            continue
        seen.add(key)
        if isinstance(args, str):
            parsed, ok = _loads(args)
            raw, args, valid = args, parsed, ok
        else:
            raw, valid = json.dumps(args, ensure_ascii=False, default=str), True
        calls.append(CallRecord(
            id=fallback_call_id(round_idx, len(calls)), name=name, arguments_raw=raw,
            arguments=args, source="fallback", valid_json=valid,
            args_is_object=isinstance(args, dict)))
    return calls


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

@dataclass
class ChatOptions:
    """Everything the request layer needs, from the registry and the CLI."""
    model: str
    max_tokens: int = 8192
    temperature: float = 0.0
    seed: int | None = None
    chat_template_kwargs: dict | None = None
    reasoning_effort: str | None = None
    reasoning_history_key: str | None = "reasoning_content"
    serialize_parallel_calls: bool = False
    max_retries: int = 2
    retry_backoff_s: float = 2.0
    timeout_s: float = 300.0
    provider: dict | None = None          # OpenRouter provider pinning
    extra_body: dict = field(default_factory=dict)

    def body(self) -> dict:
        body = dict(self.extra_body)
        if self.chat_template_kwargs:
            body["chat_template_kwargs"] = dict(self.chat_template_kwargs)
        if self.provider:
            body["provider"] = dict(self.provider)
        return body


@dataclass
class RoundResult:
    content: str = ""
    reasoning: str | None = None
    finish_reason: str | None = None
    usage: dict | None = None
    tool_calls: list[CallRecord] = field(default_factory=list)
    attempts: int = 1
    error: dict | None = None
    elapsed_s: float = 0.0
    provider: str | None = None
    served_model: str | None = None
    assistant_message: dict | None = None

    @property
    def reasoning_chars(self) -> int:
        return len(self.reasoning or "")


def _status_of(exc: BaseException) -> int | None:
    for attr in ("status_code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


def _error_block(exc: BaseException, *, kind: str | None = None) -> dict:
    status = _status_of(exc)
    return {"type": kind or type(exc).__name__, "status": status, "message": str(exc)[:2000]}


def _usage_dict(usage: Any) -> dict | None:
    if usage is None:
        return None
    if isinstance(usage, dict):
        return usage
    for attr in ("model_dump", "dict", "to_dict"):
        fn = getattr(usage, attr, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                pass
    return {k: getattr(usage, k) for k in
            ("prompt_tokens", "completion_tokens", "total_tokens") if hasattr(usage, k)}


class GatewayError(RuntimeError):
    """The server answered, but not with a usable completion."""


class EmptyReply(RuntimeError):
    """The server answered with no text, no reasoning and no tool call."""


class ModelClient:
    """One OpenAI-compatible endpoint, with the guards and the retry policy."""

    def __init__(self, client, options: ChatOptions, *, sleep: Callable[[float], None] = time.sleep):
        self.client = client
        self.options = options
        self._sleep = sleep

    # -- request ---------------------------------------------------------
    def request_kwargs(self, messages: list[dict], tools: list[dict]) -> dict:
        opt = self.options
        kwargs: dict[str, Any] = {
            "model": opt.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "max_completion_tokens": opt.max_tokens,
        }
        # The reasoning API models refuse a temperature; everything served locally takes it.
        if not opt.model.startswith(("o1", "o3", "o4", "gpt-5")):
            kwargs["temperature"] = opt.temperature
        if opt.seed is not None:
            kwargs["seed"] = opt.seed
        if opt.reasoning_effort:
            kwargs["reasoning_effort"] = opt.reasoning_effort
        body = opt.body()
        if body:
            kwargs["extra_body"] = body
        return kwargs

    # -- response --------------------------------------------------------
    def round(self, messages: list[dict], tools: list[dict], *, round_idx: int) -> RoundResult:
        opt = self.options
        kwargs = self.request_kwargs(messages, tools)
        started = time.time()
        attempts = 0
        last_error: dict | None = None
        while attempts <= opt.max_retries:
            attempts += 1
            try:
                response = self.client.chat.completions.create(**kwargs)
                result = self._read(response, round_idx)
                result.attempts = attempts
                result.elapsed_s = time.time() - started
                if last_error is not None:
                    # The round succeeded; the earlier failures stay visible as the
                    # attempt count, and the record keeps the last one for context.
                    result.error = None
                return result
            except EmptyReply as exc:
                last_error = _error_block(exc, kind="empty_reply")
            except GatewayError as exc:
                last_error = _error_block(exc, kind="gateway_error")
            except Exception as exc:
                last_error = _error_block(exc)
                status = last_error.get("status")
                if status is not None and status not in RETRYABLE_STATUS:
                    break
            if attempts <= opt.max_retries:
                self._sleep(opt.retry_backoff_s * attempts)
        return RoundResult(attempts=attempts, error=last_error,
                           elapsed_s=time.time() - started)

    def _read(self, response: Any, round_idx: int) -> RoundResult:
        choices = getattr(response, "choices", None)
        if not choices:
            # Observed on OpenRouter: a 200 with no choices. Left alone it raises
            # 'NoneType is not subscriptable' inside the case handler and the case
            # is recorded as a silent zero.
            raise GatewayError(f"the gateway returned no choices (model={self.options.model})")
        choice = choices[0]
        msg = getattr(choice, "message", None)
        if msg is None:
            raise GatewayError("the gateway returned a choice with no message")
        content = getattr(msg, "content", None) or ""
        reasoning = (getattr(msg, "reasoning_content", None)
                     or getattr(msg, "reasoning", None) or None)
        finish_reason = getattr(choice, "finish_reason", None)
        usage = _usage_dict(getattr(response, "usage", None))

        calls: list[CallRecord] = []
        for i, tc in enumerate(getattr(msg, "tool_calls", None) or []):
            func = getattr(tc, "function", None)
            raw = getattr(func, "arguments", None)
            raw = raw if isinstance(raw, str) else json.dumps(raw or {}, ensure_ascii=False,
                                                              default=str)
            args, ok = _loads(raw) if raw.strip() else ({}, True)
            calls.append(CallRecord(
                id=getattr(tc, "id", None) or fallback_call_id(round_idx, i),
                name=getattr(func, "name", None), arguments_raw=raw, arguments=args,
                source="native", valid_json=ok, args_is_object=isinstance(args, dict)))
        if not calls:
            calls = parse_fallback_calls(content, round_idx)

        if not calls and not content.strip() and not (reasoning or "").strip() \
                and finish_reason not in ("length", "content_filter"):
            raise EmptyReply(
                f"the model returned no text and no tool call (finish_reason={finish_reason})")

        return RoundResult(
            content=content, reasoning=reasoning, finish_reason=finish_reason, usage=usage,
            tool_calls=calls, provider=getattr(response, "provider", None),
            served_model=getattr(response, "model", None),
            assistant_message=self.assistant_message(content, reasoning, calls))

    # -- history ---------------------------------------------------------
    def assistant_message(self, content: str, reasoning: str | None,
                          calls: list[CallRecord]) -> dict:
        """The assistant turn as it goes back into the history.

        The model's own text is kept, and its reasoning goes back under the key
        the chat template reads, so a thinking configuration does not continue
        rounds 2 to 5 with no reasoning at all.
        """
        message: dict[str, Any] = {"role": "assistant", "content": content or ""}
        key = self.options.reasoning_history_key
        if reasoning and key:
            message[key] = reasoning
        if calls:
            message["tool_calls"] = [
                {"id": c.id, "type": "function",
                 "function": {"name": c.name,
                              "arguments": c.arguments_raw if c.valid_json
                              else json.dumps(c.arguments, ensure_ascii=False, default=str)}}
                for c in calls]
        return message

    def history_turns(self, message: dict, calls: list[CallRecord],
                      results: dict[str, str]) -> list[dict]:
        """Assistant turn(s) plus tool results, serialised when the template needs it.

        A template trained on one call per turn (Llama-3.x) answers a parallel call
        with an HTTP 400 in the next round, which used to throw away the calls the
        model had already made and score the whole case zero. The calls are sent as
        consecutive single-call turns instead.
        """
        if not calls:
            return [message]
        if not self.options.serialize_parallel_calls or len(calls) == 1:
            turns = [message]
            for call in calls:
                turns.append({"role": "tool", "tool_call_id": call.id,
                              "content": results.get(call.id, "")})
            return turns
        turns = []
        text = message.get("content") or ""
        for i, call in enumerate(calls):
            single = {k: v for k, v in message.items() if k != "tool_calls"}
            single["content"] = text if i == 0 else ""
            single["tool_calls"] = [
                {"id": call.id, "type": "function",
                 "function": {"name": call.name, "arguments": call.arguments_raw}}]
            turns.append(single)
            turns.append({"role": "tool", "tool_call_id": call.id,
                          "content": results.get(call.id, "")})
        return turns
