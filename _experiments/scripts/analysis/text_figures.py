#!/usr/bin/env python3
"""The figures the paper states in prose rather than in a table.

The generated tables carry most of the paper's numbers, but a benchmark paper
also argues in sentences: a range, a share of failures, a correlation, a split
of the cases. Those numbers had been computed once and typed in, which is how
two of them outlived a rerun. This step computes each one from the scored
records and writes them to one file, keyed by where the paper states them, so a
number in the prose has an artefact behind it like a number in a table.

Conventions follow the paper. A case is correct when h == 1. Multi-turn h-bar is
the mean over turns. "Failures" are the cases with h == 0, split by the scorer's
error type. A case has no gold tool when its scored gold-tool set is empty; the
scorer counts a case whose gold is given only as an alternative as having one.

Usage:  PYTHONPATH=. python -m _experiments.scripts.analysis.text_figures
Output: _experiments/results_RQ1/text_figures.json
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

from scipy import stats

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _experiments.scripts.analysis import load  # noqa: E402

OUT = ROOT / "_experiments" / "results_RQ1" / "text_figures.json"
GAP = ROOT / "_experiments" / "results_RQ2" / "regulatory_vs_analysis_gap.json"
MULTI = ROOT / "benchmarks_multiturn" / "cases_str_workflow.json"
BENCH = ROOT / "benchmarks"


def _gold_count(value) -> int:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            value = [value] if value else []
    return len(set(value or []))


def _share(frame, column: str) -> dict:
    counts = frame[column].value_counts()
    total = int(counts.sum())
    return {"n_failures": total,
            **{str(k): round(100 * v / total, 1) for k, v in counts.items()}}


def _pct(series) -> float:
    return round(100 * float(series.astype(float).mean()), 1)


def main() -> int:
    single = load.single("single")
    single = single.assign(n_gold=single["gold_tools"].map(_gold_count))
    groups = json.loads(GAP.read_text(encoding="utf-8"))
    analysis_tools = set(groups["analysis_categories"])
    reporting_tools = set(groups["regulatory_categories"])
    out: dict = {}

    # Section 4.2: the single-turn range and the per-tool spread.
    by_config = single.groupby("config_id")["h"].mean()
    by_tool = single[single["category"].isin(analysis_tools | reporting_tools)] \
        .groupby("category")["h"].mean().sort_values()
    out["sec4_2"] = {
        "single_turn_h_min": round(float(by_config.min()), 3),
        "single_turn_h_max": round(float(by_config.max()), 3),
        "per_tool_h_min": {by_tool.index[0]: round(float(by_tool.iloc[0]), 3)},
        "per_tool_h_max": {by_tool.index[-1]: round(float(by_tool.iloc[-1]), 3)},
    }

    # Section 4.3: how the failures (h == 0) divide by error type.
    failures = single[single["h"] == 0]
    out["sec4_3_failure_composition_pct"] = {
        "analysis_tools": _share(failures[failures["category"].isin(analysis_tools)], "error_type"),
        **{tool: _share(failures[failures["category"] == tool], "error_type")
           for tool in sorted(reporting_tools)},
    }

    # Section 4.4: single-turn hit against completion, and where the workflow breaks.
    scenarios, turns = load.multiturn("oracle")
    completion = scenarios.groupby("config_id")["c"].mean()
    turn_hit = turns.groupby("config_id")["h"].mean()
    rho_single = stats.spearmanr(by_config[completion.index], completion)
    rho_turn = stats.spearmanr(turn_hit[completion.index], completion)
    cases = json.loads(MULTI.read_text(encoding="utf-8"))
    str_turn = {case["id"]: next((t["turn"] for t in case["turns"]
                                  if any(c["name"] == "generate_str"
                                         for c in (t.get("tool_calls") or ()))), None)
                for case in cases}
    is_str = [str_turn.get(s) == t for s, t in zip(turns["scenario_id"], turns["turn"])]
    by_kind = turns.assign(is_str=is_str).groupby("is_str")["h"].mean()
    out["sec4_4"] = {
        "spearman_single_h_vs_completion": {"rho": round(float(rho_single.statistic), 4),
                                            "p": round(float(rho_single.pvalue), 4),
                                            "n": int(len(completion))},
        "spearman_turn_h_vs_completion": round(float(rho_turn.statistic), 4),
        "mean_hit_by_turn": {int(k): round(float(v), 3)
                             for k, v in turns.groupby("turn")["h"].mean().items()},
        "scenarios_with_str_at_turn_4": sum(1 for v in str_turn.values() if v == 4),
        "n_scenarios": len(cases),
        "str_turn_gap_points": round(100 * float(by_kind[False] - by_kind[True]), 1),
    }

    # Appendix A: what the single-turn cases are and how each kind is answered.
    one = single[single["config_id"] == single["config_id"].iloc[0]]
    no_gold = single[single["n_gold"] == 0]
    asks = no_gold[no_gold["clarification_ok"].notna()]
    declines = no_gold[no_gold["clarification_ok"].isna()]
    alternatives = 0
    for path in sorted(BENCH.glob("cases_*.json")):
        for case in json.loads(path.read_text(encoding="utf-8")):
            if (case.get("expected") or {}).get("alternatives"):
                alternatives += 1
    one_no_gold = one[one["n_gold"] == 0]
    out["appendix_a"] = {
        "gold_tool_count": {int(k): int(v) for k, v in
                            sorted(collections.Counter(one["n_gold"]).items())},
        "no_gold_out_of_scope": int(one_no_gold["clarification_ok"].isna().sum()),
        "no_gold_asks_for_argument": int(one_no_gold["clarification_ok"].notna().sum()),
        "cases_accepting_an_alternative": alternatives,
        "difficulty": {k: int(v) for k, v in one["difficulty"].value_counts().items()},
        "correct_pct": {
            "out_of_scope": _pct(declines["h"]),
            "asks_for_argument": _pct(asks["h"]),
            "no_gold_pooled": _pct(no_gold["h"]),
            **{f"{d}_with_gold": _pct(single[(single["n_gold"] > 0)
                                             & (single["difficulty"] == d)]["h"])
               for d in ("easy", "medium", "hard")},
        },
        "multi_turn_lengths": {int(k): int(v) for k, v in sorted(
            collections.Counter(len(case["turns"]) for case in cases).items())},
        "multi_turn_total_turns": sum(len(case["turns"]) for case in cases),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1)[:1800])
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
