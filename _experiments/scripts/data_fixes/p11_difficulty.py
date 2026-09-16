"""Pass 11 - relabel difficulty by an explicit rule (D23, L1-022).

The old labels were author intuition: over 28 configurations the mean h was .841
for easy, .778 for medium and .808 for hard, so hard was easier than medium, and
the rank correlation between a case's h and its difficulty was -0.17. D23 replaces
them with a rule computed from the case itself, so the label is reproducible and
the paper can state it.

    points = tool_count + argument_derivation + tool_overlap + information_gap

* tool_count        0 for one gold tool, 1 for two, 2 for three or more.
* argument_derivation  how many gold values are NOT written in the question and
                    have to be derived from it (a fraud type from its name, a date
                    range from "the first half of 2024", a threshold from a phrase):
                    0 for none, 1 for one, 2 for two or more.
* tool_overlap      0 when no other tool answers anything like this one, 1 when one
                    to three do, 2 when four or more do. The overlap map is the one
                    D11 fixed, tool by tool.
* information_gap   1 when the case expects no tool call at all, because the model
                    has to decide that from the question alone.

    0-1 points -> easy, 2 -> medium, 3 or more -> hard.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both, dump_json, CHANGELOG

# The tool pairs D11 had to separate, and the pairs their descriptions still place close together.
OVERLAP_PAIRS = [
    ("detect_aml_patterns", "score_account_risk"),
    ("detect_aml_patterns", "detect_smurfing_network"),
    ("detect_aml_patterns", "analyze_network"),
    ("detect_ctr_candidates", "detect_smurfing_network"),
    ("detect_ctr_candidates", "get_fraud_type_summary"),
    ("detect_ctr_candidates", "detect_monitoring_alerts"),
    ("get_statistics", "get_fraud_type_summary"),
    ("get_statistics", "query_transactions"),
    ("get_institution_report", "get_fraud_type_summary"),
    ("detect_monitoring_alerts", "query_transactions"),
    ("get_receiving_account_profile", "detect_smurfing_network"),
    ("get_receiving_account_profile", "get_account_profile"),
    ("get_account_profile", "analyze_network"),
    ("query_transactions", "analyze_channel_risk"),
    ("query_transactions", "get_trend_analysis"),
    ("compare_periods", "get_trend_analysis"),
    ("get_aml_glossary", "lookup_fiu_reference_types"),
    ("rank_risky_transactions", "score_account_risk"),
]
OVERLAP: dict[str, set[str]] = {}
for a, b in OVERLAP_PAIRS:
    OVERLAP.setdefault(a, set()).add(b)
    OVERLAP.setdefault(b, set()).add(a)

SPECIAL = {"sql_conditions", "sql_valid", "sql_contains", "hops_min", "hops_max",
           "result_contains", "result_row_count_min", "result_row_count_max"}


def gold_tools(case: dict) -> list[str]:
    expected = case.get("expected") or {}
    tools = list(expected.get("tools_must_include") or [])
    primary = expected.get("primary_tool") or ""
    if primary and primary not in tools:
        tools.insert(0, primary)
    return tools


def derivation_steps(case: dict) -> int:
    """Gold values the question does not spell out, so the model has to derive them."""
    question = case["question"].replace(",", "")
    steps = 0
    for checks in (case["expected"].get("param_checks") or {}).values():
        if not isinstance(checks, dict):
            continue
        for key, value in checks.items():
            if key in SPECIAL or isinstance(value, (dict, list, bool)):
                continue
            if str(value) not in question:
                steps += 1
    return steps


def points(case: dict) -> tuple[int, dict]:
    tools = gold_tools(case)
    tool_count = 0 if len(tools) <= 1 else 1 if len(tools) == 2 else 2
    derived = derivation_steps(case)
    argument_derivation = 0 if derived == 0 else 1 if derived == 1 else 2
    neighbours = max((len(OVERLAP.get(t, ())) for t in tools), default=0)
    tool_overlap = 0 if neighbours == 0 else 1 if neighbours <= 3 else 2
    information_gap = 0 if tools else 1
    parts = {"tool_count": tool_count, "argument_derivation": argument_derivation,
             "tool_overlap": tool_overlap, "information_gap": information_gap,
             "n_tools": len(tools), "n_derived": derived, "n_overlapping_tools": neighbours}
    return tool_count + argument_derivation + tool_overlap + information_gap, parts


def label(total: int) -> str:
    return "easy" if total <= 1 else "medium" if total == 2 else "hard"


def apply(kr: Bench, en: Bench, log: ChangeLog) -> dict:
    kr_by, en_by = kr.by_id(), en.by_id()
    moves = Counter()
    rows = {}
    for case_id, case in kr_by.items():
        total, parts = points(case)
        new = label(total)
        rows[case_id] = {"points": total, "difficulty": new, **parts}
        old = case.get("difficulty")
        if old != new:
            moves[(old, new)] += 1
        why = (f"D23 rule: {total} points ("
               f"tool_count {parts['tool_count']} for {parts['n_tools']} gold tools, "
               f"argument_derivation {parts['argument_derivation']} for {parts['n_derived']} values not "
               f"written in the question, tool_overlap {parts['tool_overlap']} for "
               f"{parts['n_overlapping_tools']} confusable tools, "
               f"information_gap {parts['information_gap']})")
        log.set_field(case, "kr", "difficulty", new, "L1-022/D23", why)
        log.set_field(en_by[case_id], "en", "difficulty", new, "L1-022/D23", why)
    log.note("moves: " + ", ".join(f"{a}->{b}: {n}" for (a, b), n in sorted(moves.items())))
    return rows


def main() -> int:
    kr, en = both()
    before = Counter(c.get("difficulty") for _, c in kr.cases())
    log = ChangeLog("p11_difficulty", "Relabel difficulty by the explicit D23 rule (L1-022).")
    rows = apply(kr, en, log)
    kr.save()
    en.save()
    after = Counter(c.get("difficulty") for _, c in kr.cases())
    dump_json(CHANGELOG / "p11_difficulty_scores.json",
              {"rule": __doc__.split("    points =")[1].strip(), "before": dict(sorted(before.items())),
               "after": dict(sorted(after.items())), "per_case": rows})
    print(log.report())
    for n in log.notes:
        print("  " + n)
    print(f"before {dict(sorted(before.items()))} -> after {dict(sorted(after.items()))}")
    print(f"log: {log.write()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
