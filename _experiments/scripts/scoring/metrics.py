"""Metric definitions shared by single-turn cases and multi-turn turns.

h  every gold tool appears among the calls (D01)
r  fraction of gold tools called
p  calls that name a gold tool / calls made (None when nothing was called)
o  first occurrences of the ordered tools are strictly increasing (L4-028)
a  mean score of the parameter checks, None when the case has no checks (D02)
f1 F1 of the called tool SET against the gold tool set (D01 companion metric)
"""

from __future__ import annotations

from .compare import SpecMatch
from .records import Call


def tool_metrics(gold_tools: list[str], calls: list[Call]) -> dict:
    called = [c.name for c in calls]
    called_set = set(called)
    gold_set = set(gold_tools)
    n_calls = len(called)
    n_gold_calls = sum(1 for name in called if name in gold_set)
    if gold_set:
        h = 1 if gold_set <= called_set else 0
        r = len(gold_set & called_set) / len(gold_set)
        hits = len(gold_set & called_set)
        precision = hits / len(called_set) if called_set else 0.0
        recall = hits / len(gold_set)
        f1 = 0.0 if hits == 0 else 2 * precision * recall / (precision + recall)
    else:  # abstention: the gold tool set is empty
        h = 0 if called_set else 1
        r = None
        f1 = 0.0 if called_set else 1.0
    return {
        "h": h,
        "r": r,
        "p": (n_gold_calls / n_calls) if n_calls else None,
        "f1_tools": f1,
        "n_calls": n_calls,
        "n_gold_calls": n_gold_calls,
        "called_tools": called,
        "extra_tools": sorted(called_set - gold_set),
    }


def order_metric(tool_order: list[str], calls: list[Call]) -> int | None:
    """None unless an order is specified and every ordered tool was called (D02)."""
    if not tool_order:
        return None
    first: dict[str, int] = {}
    for c in calls:
        first.setdefault(c.name, c.order)
    if any(t not in first for t in tool_order):
        return None
    positions = [first[t] for t in tool_order]
    return 1 if all(a < b for a, b in zip(positions, positions[1:])) else 0


def param_accuracy(matches: list[SpecMatch]) -> tuple[float | None, int]:
    total = sum(m.total for m in matches)
    if total == 0:
        return None, 0
    return sum(m.earned for m in matches) / total, total
