"""Compatibility layer over the scoring library.

Scoring lives in :mod:`_experiments.scripts.scoring` and runs after the fact:
runners write Contract 2 run records, ``scoring/score_runs.py`` reads those
records plus the gold and writes the eval files. Nothing in a run record is a
score any more.

This module stays for entry points that still hold a list of tool events in
memory (the pre-rerun runners, ad-hoc re-scoring notebooks). It wraps those
events in a run record and returns the Contract 3 result, so a caller gets the
fixed metrics rather than the pre-audit ones:

    h, r, p, a, o, f1_tools, abstain_ok, clarification_ok, error_type, error_flag

The pre-audit keys (``primary_tool_hit``, ``tool_recall``, ``tool_precision``,
``param_accuracy``, ``order_score``, the weighted ``score``) are gone on
purpose: p and o were 1.0 for a model that called nothing, a was 1.0 for a case
without checks, and the weighted score has no definition in the paper (D02).
"""

from __future__ import annotations

import json
import warnings
from typing import Any

from _experiments.scripts.scoring import aggregate_single, score_case
from _experiments.scripts.scoring.compare import ScoringContext

_CONTEXT: ScoringContext | None = None

ERROR_TYPES = ("correct", "no_call", "wrong_tool", "missing_tool", "over_call", "param_error",
               "order_error", "parse_fail", "system_error", "length_stop")


def get_context() -> ScoringContext:
    """Process-wide scoring context (tool schema, catalog, SQL executor)."""
    global _CONTEXT
    if _CONTEXT is None:
        from _experiments.scripts.scoring.score_runs import build_context

        _CONTEXT = build_context()
    return _CONTEXT


def set_context(ctx: ScoringContext) -> None:
    global _CONTEXT
    _CONTEXT = ctx


def record_from_tool_events(case_id: str, tool_events: list[dict], *, final_text: str = "",
                            error: dict | None = None, stop_reason: str | None = None) -> dict:
    """Wrap ``[{name, arguments, result}, ...]`` in a Contract 2 run record."""
    calls, executed = [], []
    for i, ev in enumerate(tool_events or []):
        call_id = ev.get("id") or f"ev{i}"
        args = ev.get("arguments")
        calls.append({"id": call_id, "name": ev.get("name"), "arguments": args,
                      "arguments_raw": json.dumps(args, ensure_ascii=False, default=str),
                      "source": ev.get("source", "native"), "valid_json": isinstance(args, dict)})
        if "result" in ev or ev.get("error") is not None:
            executed.append({"tool_call_id": call_id, "name": ev.get("name"), "arguments": args,
                             "result": ev.get("result"), "error": ev.get("error")})
    return {"run_id": "inline", "case_id": case_id, "setting": "single",
            "rounds": [{"idx": 0, "content": "", "tool_calls": calls, "executed": executed, "error": None}],
            "final_text": final_text, "stop_reason": stop_reason, "error": error}


def evaluate_case(case: dict, tool_events: list[dict], *, final_text: str = "",
                  error: dict | None = None, stop_reason: str | None = None,
                  context: ScoringContext | None = None, category: str | None = None) -> dict:
    """Contract 3 result for one case (see :mod:`_experiments.scripts.scoring.single`)."""
    record = record_from_tool_events(case.get("id", ""), tool_events, final_text=final_text,
                                     error=error, stop_reason=stop_reason)
    return score_case(case, record, context or get_context(), category=category)


def aggregate_results(results: list[dict]) -> dict:
    """Aggregates with n for every metric (see :mod:`_experiments.scripts.scoring.aggregate`)."""
    return aggregate_single(results) if results else {}


def classify_exception_error_type(exc: BaseException) -> str:
    """Map a runner exception to a Contract 3 error type."""
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    name = type(exc).__name__.lower()
    text = f"{name} {exc}".lower()
    if isinstance(exc, json.JSONDecodeError) or "parse" in name or "tool call" in text or "invalid json" in text:
        return "parse_fail"
    if "length" in text or status == 413:
        return "length_stop"
    return "system_error"


def normalize_exception_result(result: dict, exc: BaseException) -> dict:
    """Mark a case whose run raised: the calls it did make stay scored (D21)."""
    out = dict(result)
    out["error_type"] = classify_exception_error_type(exc)
    out["error_flag"] = True
    out["error"] = {"type": out["error_type"], "message": str(exc)}
    return out


def normalize_parse_fail_result(result: dict) -> dict:
    out = dict(result)
    out["error_type"] = "parse_fail"
    out["error_flag"] = True
    return out


def __getattr__(name: str) -> Any:  # pragma: no cover - guidance for old call sites
    removed = {"_values_equal": "scoring.compare.compare_value",
               "_evaluate_params": "scoring.compare.match_specs",
               "_evaluate_order": "scoring.metrics.order_metric",
               "_determine_error_type": "scoring.single._error_type"}
    if name in removed:
        raise AttributeError(f"{name} was replaced by {removed[name]}; see _experiments/scripts/scoring/README.md")
    raise AttributeError(name)


warnings.warn(
    "_experiments.scripts.evaluator is a compatibility layer; score runs with "
    "_experiments/scripts/scoring/score_runs.py over Contract 2 run records.",
    DeprecationWarning, stacklevel=2,
)
