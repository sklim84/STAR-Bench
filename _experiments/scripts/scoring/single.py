"""Single-turn scoring: one gold case against one run record."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .compare import ScoringContext, hallucinated_params, match_specs
from .metrics import order_metric, param_accuracy, tool_metrics
from .records import RunView, answer_text_ok, is_unparsed_tool_call, view_record

ERROR_TYPES = (
    "correct", "no_call", "wrong_tool", "missing_tool", "over_call", "param_error",
    "order_error", "parse_fail", "system_error", "length_stop",
)


@dataclass
class Candidate:
    label: str
    kind: str  # "tools" | "abstain" | "clarification"
    tools: list[str]
    specs: list[tuple[str, dict]]
    tool_order: list[str]


def _tools_candidate(label: str, spec: dict) -> Candidate:
    tools = list(spec.get("tools_must_include") or [])
    primary = spec.get("primary_tool") or ""
    if primary and primary not in tools:
        tools.insert(0, primary)
    checks = spec.get("param_checks") or {}
    return Candidate(label=label, kind="tools", tools=tools,
                     specs=[(t, checks.get(t, {})) for t in tools],
                     tool_order=list(spec.get("tool_order") or []))


def candidates(case: dict) -> list[Candidate]:
    expected = case.get("expected") or {}
    out: list[Candidate] = []
    if expected.get("expect_clarification"):
        out.append(Candidate("primary", "clarification", [], [], []))
    elif not (expected.get("tools_must_include") or expected.get("primary_tool")):
        out.append(Candidate("primary", "abstain", [], [], []))
    else:
        out.append(_tools_candidate("primary", expected))
    for i, alt in enumerate(expected.get("alternatives") or []):
        label = f"alternative:{i}"
        if alt.get("abstain"):
            out.append(Candidate(label, "abstain", [], [], []))
        elif alt.get("expect_clarification"):
            out.append(Candidate(label, "clarification", [], [], []))
        else:
            out.append(_tools_candidate(label, alt))
    return out


def _score_candidate(cand: Candidate, view: RunView, ctx: ScoringContext) -> dict:
    if cand.kind in ("abstain", "clarification"):
        answered = not view.calls and (view.text_unavailable or answer_text_ok(view.final_text))
        ok = 1 if answered else 0
        out = tool_metrics([], view.calls)
        out.update(h=ok, a=None, n_checks=0, o=None, checks=[],
                   abstain_ok=bool(ok) if cand.kind == "abstain" else None,
                   clarification_ok=bool(ok) if cand.kind == "clarification" else None)
        return out
    matches = match_specs(cand.specs, view.calls, ctx)
    a, n_checks = param_accuracy(matches)
    out = tool_metrics(cand.tools, view.calls)
    out.update(
        a=a, n_checks=n_checks, o=order_metric(cand.tool_order, view.calls),
        checks=[{"tool": m.tool, "call": m.call.order if m.call else None, "results": m.checks} for m in matches],
        abstain_ok=None, clarification_ok=None,
    )
    return out


def _rank(scored: dict) -> tuple:
    return (scored["h"], scored["a"] if scored["a"] is not None else 1.0,
            scored["f1_tools"], scored["o"] if scored["o"] is not None else 1)


def _is_correct(cand: Candidate, s: dict) -> bool:
    if cand.kind in ("abstain", "clarification"):
        return s["h"] == 1
    return (s["h"] == 1 and (s["a"] is None or s["a"] == 1.0)
            and (s["o"] is None or s["o"] == 1) and not s["extra_tools"])


def _error_type(cand: Candidate, s: dict, view: RunView) -> str:
    if _is_correct(cand, s):
        return "correct"
    if view.length_stop:
        return "length_stop"
    if view.run_failed:
        return "system_error"
    if not view.calls and (is_unparsed_tool_call(view.final_text) or not view.final_text.strip()):
        return "parse_fail"
    if cand.kind in ("abstain", "clarification"):
        return "over_call" if view.calls else "parse_fail"
    if not view.calls:
        return "no_call"
    if s["r"] == 0:
        return "wrong_tool"
    if s["h"] == 0:
        return "missing_tool"
    if s["a"] is not None and s["a"] < 1.0:
        return "param_error"
    if s["o"] == 0:
        return "order_error"
    return "over_call"


def score_case(case: dict, record: dict | None, ctx: ScoringContext, *,
               category: str | None = None) -> dict:
    """Eval result for one case. ``record`` None means the run has no record for it."""
    view = view_record(record or {"rounds": [], "final_text": "",
                                  "error": {"type": "missing_record", "message": "no run record"},
                                  "stop_reason": "error"})
    scored = [(c, _score_candidate(c, view, ctx)) for c in candidates(case)]
    cand, best = max(scored, key=lambda cs: _rank(cs[1]))
    halluc = hallucinated_params(view.calls, ctx.schemas)
    out: dict[str, Any] = {
        "case_id": case.get("id", ""),
        "run_id": (record or {}).get("run_id"),
        "category": category,
        "difficulty": case.get("difficulty", ""),
        "setting": (record or {}).get("setting", "single"),
        "matched": cand.label,
        "gold_tools": cand.tools,
        "h": best["h"],
        "r": best["r"],
        "p": best["p"],
        "a": None if best["a"] is None else round(best["a"], 6),
        "o": best["o"],
        "f1_tools": round(best["f1_tools"], 6),
        "n_checks": best["n_checks"],
        "n_calls": best["n_calls"],
        "n_gold_calls": best["n_gold_calls"],
        "called_tools": best["called_tools"],
        "extra_tools": best["extra_tools"],
        "abstain_ok": best["abstain_ok"],
        "clarification_ok": best["clarification_ok"],
        "error_flag": view.error_flag,
        "error": view.error or (view.round_errors[0] if view.round_errors else None),
        "round_errors": len(view.round_errors),
        "stop_reason": view.stop_reason,
        "parser_artifacts": view.name_artifacts,
        "malformed_arg_calls": sum(1 for c in view.calls if not c.args_ok),
        "fallback_parsed_calls": sum(1 for c in view.calls if c.source == "fallback"),
        "hallucinated_param_count": len(halluc),
        "hallucinated_params": halluc,
        "final_text_ok": answer_text_ok(view.final_text),
        "checks": best["checks"],
        "error_type": _error_type(cand, best, view),
        "missing_record": record is None,
    }
    if len(scored) > 1:
        out["candidate_scores"] = [{"label": c.label, "h": s["h"], "a": s["a"], "f1_tools": round(s["f1_tools"], 6)}
                                   for c, s in scored]
    return out
