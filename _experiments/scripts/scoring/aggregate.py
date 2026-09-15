"""Aggregates. Every number is reported with the n it was computed over (Contract 3)."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


def mean_n(values: Iterable[Any]) -> dict:
    vals = [float(v) for v in values if v is not None]
    return {"mean": round(sum(vals) / len(vals), 6) if vals else None, "n": len(vals)}


def _single_block(results: list[dict]) -> dict:
    n_calls = sum(r["n_calls"] for r in results)
    n_gold_calls = sum(r["n_gold_calls"] for r in results)
    abstain = [r["abstain_ok"] for r in results if r["abstain_ok"] is not None]
    clarify = [r["clarification_ok"] for r in results if r["clarification_ok"] is not None]
    return {
        "n_cases": len(results),
        "h": mean_n(r["h"] for r in results),
        "r": mean_n(r["r"] for r in results),
        "a": mean_n(r["a"] for r in results),
        "o": mean_n(r["o"] for r in results),
        "f1_tools": mean_n(r["f1_tools"] for r in results),
        "p_micro": {"mean": round(n_gold_calls / n_calls, 6) if n_calls else None, "n_calls": n_calls,
                    "n_cases_with_calls": sum(1 for r in results if r["n_calls"])},
        "p_case": mean_n(r["p"] for r in results),
        "abstain_ok": {"mean": round(sum(abstain) / len(abstain), 6) if abstain else None, "n": len(abstain)},
        "clarification_ok": {"mean": round(sum(clarify) / len(clarify), 6) if clarify else None, "n": len(clarify)},
        "error_types": dict(Counter(r["error_type"] for r in results)),
        "n_error_flag": sum(1 for r in results if r["error_flag"]),
        "n_parser_artifacts": sum(1 for r in results if r["parser_artifacts"]),
        "n_malformed_arg_calls": sum(r["malformed_arg_calls"] for r in results),
        "hallucinated_params": {"total": sum(r["hallucinated_param_count"] for r in results), "n_calls": n_calls},
    }


def aggregate_single(results: list[dict]) -> dict:
    out = _single_block(results)
    groups: dict[str, list[dict]] = {}
    diffs: dict[str, list[dict]] = {}
    for r in results:
        groups.setdefault(r.get("category") or "", []).append(r)
        diffs.setdefault(r.get("difficulty") or "", []).append(r)
    out["by_category"] = {k: _single_block(v) for k, v in sorted(groups.items())}
    out["by_difficulty"] = {k: _single_block(v) for k, v in sorted(diffs.items())}
    return out


def _multiturn_block(scenarios: list[dict]) -> dict:
    turns = [t for s in scenarios for t in s["turns"]]
    checked = [t for t in turns if t["n_checks"]]
    ctx = [t for t in turns if t["context_hit"] is not None]
    clarify = [t["clarification_ok"] for t in turns if t["clarification_ok"] is not None]
    n_calls = sum(t["n_calls"] for t in turns)
    n_gold_calls = sum(t["n_gold_calls"] for t in turns)
    return {
        "n_scenarios": len(scenarios),
        "n_turns": len(turns),
        "c": mean_n(s["c"] for s in scenarios),
        "h": mean_n(t["h"] for t in turns),
        "a": {"mean": round(sum(t["a"] for t in checked) / len(checked), 6) if checked else None, "n": len(checked)},
        "f1_tools": mean_n(t["f1_tools"] for t in turns),
        "p_micro": {"mean": round(n_gold_calls / n_calls, 6) if n_calls else None, "n_calls": n_calls},
        "context_accuracy": {"mean": round(sum(1 for t in ctx if t["context_hit"]) / len(ctx), 6) if ctx else None,
                             "n": len(ctx)},
        "clarification_ok": {"mean": round(sum(clarify) / len(clarify), 6) if clarify else None, "n": len(clarify)},
        "error_types": dict(Counter(t["error_type"] for t in turns)),
        "n_turns_with_error": sum(1 for t in turns if t["error_flag"]),
        "n_missing_turn_records": sum(1 for t in turns if t["missing_record"]),
    }


def aggregate_multiturn(scenarios: list[dict]) -> dict:
    out = _multiturn_block(scenarios)
    groups: dict[str, list[dict]] = {}
    for s in scenarios:
        groups.setdefault(s.get("sub_category") or "", []).append(s)
    out["by_sub_category"] = {k: _multiturn_block(v) for k, v in sorted(groups.items())}
    return out
