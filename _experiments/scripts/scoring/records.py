"""Reading Contract 2 run records into the call list the scorer works on."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

# Serving artefacts that leak into tool names, e.g. gpt-oss Harmony
# "query_transactions<|channel|>commentary" or "functions.query_transactions".
_SPECIAL_TOKEN_TAIL = re.compile(r"<\|.*$", re.S)
_RECIPIENT_PREFIX = "functions."


@dataclass
class Call:
    order: int
    round_idx: int
    id: str | None
    name: str
    name_raw: Any
    arguments: Any
    args_ok: bool
    source: str | None = None
    valid_json: bool | None = None
    name_artifact: bool = False
    executed: dict | None = None
    args_unavailable: bool = False  # legacy record that kept only the tool name

    @property
    def args(self) -> dict:
        return self.arguments if self.args_ok else {}


@dataclass
class RunView:
    record: dict
    calls: list[Call] = field(default_factory=list)
    final_text: str = ""
    error: dict | None = None
    stop_reason: str | None = None
    text_unavailable: bool = False  # legacy record that kept no final text

    @property
    def length_stop(self) -> bool:
        if self.stop_reason == "length":
            return True
        err_type = (self.error or {}).get("type") or ""
        return "length" in str(err_type).lower()

    @property
    def error_flag(self) -> bool:
        return self.error is not None or self.stop_reason == "error"

    @property
    def name_artifacts(self) -> list[str]:
        return [str(c.name_raw) for c in self.calls if c.name_artifact]


def normalize_tool_name(raw: Any) -> tuple[str, bool]:
    if not isinstance(raw, str):
        return "", True
    name = _SPECIAL_TOKEN_TAIL.sub("", raw).strip()
    if name.startswith(_RECIPIENT_PREFIX):
        name = name[len(_RECIPIENT_PREFIX):]
    return name, name != raw


def _parse_arguments(tc: dict) -> tuple[Any, bool]:
    args = tc.get("arguments")
    if args is None and isinstance(tc.get("arguments_raw"), str):
        args = tc["arguments_raw"]
    if isinstance(args, str):
        text = args.strip()
        if text == "":
            return {}, True
        try:
            args = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return args, False
    if args is None:
        return {}, tc.get("valid_json") is not False
    return args, isinstance(args, dict)


def view_record(record: dict) -> RunView:
    calls: list[Call] = []
    order = 0
    last_content = ""
    for r_pos, rnd in enumerate(record.get("rounds") or []):
        if not isinstance(rnd, dict):
            continue
        r_idx = rnd.get("idx", r_pos)
        if isinstance(rnd.get("content"), str):
            last_content = rnd["content"]
        executed = [e for e in (rnd.get("executed") or []) if isinstance(e, dict)]
        by_id = {e.get("tool_call_id"): e for e in executed if e.get("tool_call_id") is not None}
        for pos, tc in enumerate(rnd.get("tool_calls") or []):
            if not isinstance(tc, dict):
                continue
            name, artifact = normalize_tool_name(tc.get("name"))
            args, ok = _parse_arguments(tc)
            ex = by_id.get(tc.get("id"))
            if ex is None and not by_id and pos < len(executed):
                ex = executed[pos]
            calls.append(Call(
                order=order, round_idx=r_idx, id=tc.get("id"), name=name, name_raw=tc.get("name"),
                arguments=args, args_ok=ok, source=tc.get("source"), valid_json=tc.get("valid_json"),
                name_artifact=artifact, executed=ex,
                args_unavailable=tc.get("arguments_recorded") is False,
            ))
            order += 1
    if "final_text" in record:
        final_text = record.get("final_text") or ""
    else:
        final_text = last_content
    legacy = record.get("legacy") or {}
    return RunView(
        record=record, calls=calls, final_text=final_text if isinstance(final_text, str) else "",
        error=record.get("error"), stop_reason=record.get("stop_reason"),
        text_unavailable=legacy.get("final_text_recorded") is False,
    )


def iter_records(paths: Iterable[Path]) -> Iterator[dict]:
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_no}: not JSON ({exc})") from exc


def record_files(runs: Path) -> list[Path]:
    if runs.is_file():
        return [runs]
    return sorted(p for p in runs.rglob("*.jsonl") if p.is_file())


# ---------------------------------------------------------------------------
# Final-text checks for abstention and clarification (D19)
# ---------------------------------------------------------------------------

_CALL_MARKUP = re.compile(
    r"<tool_call>|</tool_call>|\[TOOL_CALLS\]|<\|python_tag\|>|<function=|<\|call\|>|"
    r"<\|tool_call|to=functions\.|<start_function_call>|<\|channel\|>",
    re.I,
)
_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.I)


def _json_objects(text: str) -> Iterator[Any]:
    decoder = json.JSONDecoder()
    i = 0
    while True:
        starts = [p for p in (text.find("{", i), text.find("[", i)) if p != -1]
        if not starts:
            return
        i = min(starts)
        try:
            obj, end = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            i += 1
            continue
        yield obj
        i = end


def _looks_like_call(obj: Any) -> bool:
    if isinstance(obj, list):
        return any(_looks_like_call(o) for o in obj)
    if not isinstance(obj, dict):
        return False
    if isinstance(obj.get("function"), dict) and "name" in obj["function"]:
        return True
    return isinstance(obj.get("name"), str) and any(k in obj for k in ("arguments", "parameters", "args"))


def is_unparsed_tool_call(text: str) -> bool:
    """True when the text carries a tool call the runner did not turn into a call."""
    if not text or not text.strip():
        return False
    if _CALL_MARKUP.search(text):
        return True
    bodies = _FENCE.findall(text) + [text]
    return any(_looks_like_call(obj) for body in bodies for obj in _json_objects(body))


def answer_text_ok(text: str) -> bool:
    return bool(text and text.strip()) and not is_unparsed_tool_call(text)
