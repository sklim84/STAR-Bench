"""Contract 2 run records: one JSONL line per case, or per turn in multi-turn.

The runner records what the model did and never what it scored. The evaluator
reads these records together with the gold and writes the eval files
(`_experiments/scripts/scoring/score_runs.py`), so a scoring rule can change
without re-running a model (L4-016).

A run writes into a fresh directory. Old checkpoints are never read: a rerun
that wants to skip finished cases passes `--resume`, which reads the records
this very run directory already holds and refuses anything that does not carry
the expected case count (C2-014, C2-015, L5-027).
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

__all__ = [
    "CallRecord", "ExecutedRecord", "RoundRecord", "RunRecord", "RecordWriter",
    "new_run_id", "read_records", "case_ids_in", "RESUME_REFUSED", "ResumeRefused",
]

STOP_REASONS = ("no_tool_call", "tool_call", "max_rounds", "error", "length",
                "max_calls")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_run_id(prefix: str) -> str:
    """Run identifier: <prefix>-<utc timestamp>-<6 hex>.

    Every record carries it, so a partial rerun merged next to an earlier run
    still says which run each line came from (L5-027).
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe = "".join(c if c.isalnum() or c in "-._" else "_" for c in prefix)
    return f"{safe}-{stamp}-{uuid.uuid4().hex[:6]}"


@dataclass
class CallRecord:
    """One tool call as the server returned it."""
    id: str | None
    name: Any
    arguments_raw: str
    arguments: Any
    source: str = "native"          # native | fallback
    valid_json: bool = True
    args_is_object: bool = True     # C2-017: a list/str/null argument is flagged, never dropped

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExecutedRecord:
    tool_call_id: str | None
    name: Any
    arguments: Any
    result: Any = None
    error: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RoundRecord:
    idx: int
    finish_reason: str | None = None
    content: str = ""
    reasoning_chars: int = 0
    reasoning: str | None = None
    usage: dict | None = None
    tool_calls: list[CallRecord] = field(default_factory=list)
    executed: list[ExecutedRecord] = field(default_factory=list)
    error: dict | None = None
    attempts: int = 1
    elapsed_s: float | None = None
    serialized_from: int | None = None   # D21: index of the parallel round this turn was split from
    provider: str | None = None          # gateway that served the request (L5-014)
    served_model: str | None = None      # model id the gateway reports having used

    def to_dict(self) -> dict:
        out = {
            "idx": self.idx,
            "finish_reason": self.finish_reason,
            "content": self.content,
            "reasoning_chars": self.reasoning_chars,
            "usage": self.usage,
            "tool_calls": [c.to_dict() for c in self.tool_calls],
            "executed": [e.to_dict() for e in self.executed],
            "error": self.error,
            "attempts": self.attempts,
        }
        if self.elapsed_s is not None:
            out["elapsed_s"] = round(self.elapsed_s, 3)
        if self.serialized_from is not None:
            out["serialized_from"] = self.serialized_from
        for key in ("provider", "served_model"):
            if getattr(self, key) is not None:
                out[key] = getattr(self, key)
        return out


@dataclass
class RunRecord:
    run_id: str
    case_id: str
    setting: str                      # single | oracle | e2e
    tools_lang: str                   # kr | en
    query_lang: str                   # kr | en
    config: dict
    provenance: dict
    turn: int | None = None           # multi-turn only
    rounds: list[RoundRecord] = field(default_factory=list)
    final_text: str = ""
    stop_reason: str | None = None
    error: dict | None = None
    elapsed_s: float = 0.0
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        out: dict[str, Any] = {"run_id": self.run_id, "case_id": self.case_id}
        if self.turn is not None:
            out["turn"] = self.turn
        out.update({
            "setting": self.setting,
            "tools_lang": self.tools_lang,
            "query_lang": self.query_lang,
            "config": self.config,
            "provenance": self.provenance,
            "rounds": [r.to_dict() for r in self.rounds],
            "final_text": self.final_text,
            "stop_reason": self.stop_reason,
            "error": self.error,
            "elapsed_s": round(self.elapsed_s, 3),
        })
        if self.extra:
            out.update(self.extra)
        return out


class ResumeRefused(RuntimeError):
    """A resume that would silently reuse a record set the run cannot trust."""


RESUME_REFUSED = ResumeRefused


class RecordWriter:
    """Appends Contract 2 lines to one JSONL file, and writes the run manifest.

    The file is named after the run id, so a partial rerun never writes into the
    file of the run it is patching (L5-027, C2-014). `partial=True` marks the
    manifest and the file name, so a merge step can tell a complete run from a
    filtered one.
    """

    def __init__(self, out_dir: Path | str, run_id: str, *, partial: bool = False):
        self.dir = Path(out_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.partial = partial
        suffix = ".partial.jsonl" if partial else ".jsonl"
        self.path = self.dir / f"{run_id}{suffix}"
        self._lock = threading.Lock()
        self._n = 0

    def write(self, record: RunRecord | dict) -> None:
        payload = record.to_dict() if isinstance(record, RunRecord) else record
        line = json.dumps(payload, ensure_ascii=False, default=str)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            self._n += 1

    @property
    def count(self) -> int:
        return self._n

    def sort_by(self, order: Iterable[str]) -> int:
        """Rewrites the file with the records in benchmark order.

        Workers finish out of order, so the file is sorted once at the end and a
        parallel run produces the same file a serial one does. Keys the order
        does not name keep their relative position at the end.
        """
        index = {key: i for i, key in enumerate(order)}
        with self._lock:
            rows = list(read_records(self.path))
            if not rows:
                return 0

            def key(row: dict) -> tuple:
                case_id = row.get("case_id") or ""
                name = case_id if row.get("turn") is None else f"{case_id}#{row['turn']}"
                return (index.get(name, len(index)), name, row.get("turn") or 0)

            rows.sort(key=key)
            with open(self.path, "w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
        return len(rows)

    def manifest(self, payload: dict) -> Path:
        path = self.dir / f"{self.run_id}.manifest.json"
        body = dict(payload)
        body.update({"run_id": self.run_id, "partial": self.partial,
                     "records_file": self.path.name, "written_at": _utcnow()})
        path.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
        return path


def read_records(path: Path | str) -> Iterator[dict]:
    path = Path(path)
    if not path.exists():
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def _record_files(out_dir: Path) -> list[Path]:
    return sorted(p for p in Path(out_dir).glob("*.jsonl") if p.is_file())


def case_ids_in(out_dir: Path | str, *, include_partial: bool = False) -> dict[str, str]:
    """Maps case key -> run_id for every record already in this run directory.

    The key is the case id for single-turn and `<case id>#<turn>` for multi-turn.
    """
    found: dict[str, str] = {}
    for path in _record_files(Path(out_dir)):
        if not include_partial and path.name.endswith(".partial.jsonl"):
            continue
        for rec in read_records(path):
            case_id = rec.get("case_id")
            if case_id is None:
                continue
            key = case_id if rec.get("turn") is None else f"{case_id}#{rec['turn']}"
            found[key] = rec.get("run_id") or path.stem
    return found


def resume_state(out_dir: Path | str, expected_keys: Iterable[str], *,
                 allow_partial: bool = False) -> set[str]:
    """Keys a `--resume` run may skip, or a refusal.

    Refuses when the directory holds records the benchmark does not know about,
    when it holds partial files (which are, by construction, not a full run) and
    when every expected key is already there, because a resume that skips
    everything is a configuration mistake and not a finished run (C2-015).
    """
    out_dir = Path(out_dir)
    expected = set(expected_keys)
    partials = [p.name for p in _record_files(out_dir) if p.name.endswith(".partial.jsonl")]
    if partials and not allow_partial:
        raise ResumeRefused(
            f"{out_dir} holds partial run files ({', '.join(partials)}). A partial run is not a "
            f"resumable run: score it separately or start a fresh output directory."
        )
    done = case_ids_in(out_dir, include_partial=allow_partial)
    unknown = sorted(set(done) - expected)
    if unknown:
        raise ResumeRefused(
            f"{out_dir} holds {len(unknown)} record(s) for cases this benchmark does not contain "
            f"(first: {unknown[:3]}). The directory belongs to another benchmark or another "
            f"schema arm; use a fresh output directory."
        )
    missing = expected - set(done)
    if not missing:
        raise ResumeRefused(
            f"{out_dir} already holds all {len(expected)} expected records. Nothing to resume; "
            f"a resume that skips every case would report 'complete' without running anything."
        )
    return set(done)


def verify_run_complete(path: Path | str, expected_keys: Iterable[str]) -> dict:
    """Checks a finished record file against the case list it claims to cover."""
    expected = set(expected_keys)
    seen: dict[str, int] = {}
    for rec in read_records(path):
        case_id = rec.get("case_id")
        key = case_id if rec.get("turn") is None else f"{case_id}#{rec['turn']}"
        seen[key] = seen.get(key, 0) + 1
    missing = sorted(expected - set(seen))
    unknown = sorted(set(seen) - expected)
    duplicates = sorted(k for k, n in seen.items() if n > 1)
    return {"n_records": sum(seen.values()), "n_expected": len(expected),
            "missing": missing, "unknown": unknown, "duplicates": duplicates,
            "complete": not missing and not unknown and not duplicates}
