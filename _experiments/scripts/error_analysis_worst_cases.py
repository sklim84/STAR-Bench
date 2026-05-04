#!/usr/bin/env python3
"""Worst-Case Instance Analysis for AML-Bench.

Identifies benchmark instances where most/all models fail,
following the Failure Analysis pattern from KFinEval (KDD'26, Appendix K).
"""

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev

# ── paths ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
CKPT_DIR = ROOT / "_experiments" / "results" / "round1" / "checkpoint"
BENCH_DIR = ROOT / "_paper" / "benchmarks"
OUT_PATH = ROOT / "_experiments" / "results" / "error_analysis_worst_cases.json"

EXCLUDE_ERRORS = {"api_error", "parse_fail"}


# ── load benchmark questions ───────────────────────────────────────────
def load_questions() -> dict:
    """Return {case_id: {question, difficulty, category}} from benchmark JSONs."""
    qmap = {}
    for fp in sorted(BENCH_DIR.glob("cases_*.json")):
        category = fp.stem.replace("cases_", "")
        cases = json.loads(fp.read_text(encoding="utf-8"))
        for c in cases:
            qmap[c["id"]] = {
                "question": c["question"],
                "difficulty": c.get("difficulty", "unknown"),
                "category": category,
                "expected": c.get("expected", {}),
            }
    return qmap


# ── load checkpoint results ───────────────────────────────────────────
def load_checkpoints() -> list[dict]:
    """Load all checkpoint JSONL files, keep last entry per (model, case_id)."""
    all_records = []
    for fp in sorted(CKPT_DIR.glob("checkpoint_*.jsonl")):
        seen = {}  # case_id -> record (keep last)
        for line in fp.read_text(encoding="utf-8").strip().splitlines():
            rec = json.loads(line)
            seen[rec["case_id"]] = rec
        all_records.extend(seen.values())
    return all_records


# ── main analysis ─────────────────────────────────────────────────────
def main():
    questions = load_questions()
    records = load_checkpoints()

    # filter out api_error / parse_fail
    records = [r for r in records if r.get("error_type") not in EXCLUDE_ERRORS]

    # group by case_id
    by_case: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_case[r["case_id"]].append(r)

    # ── 1. Per-case stats ──────────────────────────────────────────────
    case_stats = []
    for cid, recs in by_case.items():
        scores = [r["score"] for r in recs]
        n_models = len(scores)
        avg_s = mean(scores)
        std_s = stdev(scores) if len(scores) > 1 else 0.0
        n_zero = sum(1 for s in scores if s == 0)
        n_perfect = sum(1 for s in scores if s == 1.0)

        # most common error_type
        err_counts = Counter(r.get("error_type", "unknown") for r in recs)
        most_common_err = err_counts.most_common(1)[0]

        # most common wrong tool (when wrong_func)
        wrong_tools = []
        for r in recs:
            if r.get("error_type") == "wrong_func":
                for t in r.get("called_tools", []):
                    wrong_tools.append(t)
        wrong_tool_counter = Counter(wrong_tools)
        most_common_wrong_tool = wrong_tool_counter.most_common(1)[0] if wrong_tool_counter else (None, 0)

        q_info = questions.get(cid, {})
        case_stats.append({
            "case_id": cid,
            "category": recs[0].get("category", q_info.get("category", "")),
            "difficulty": recs[0].get("difficulty", q_info.get("difficulty", "")),
            "avg_score": round(avg_s, 4),
            "std_score": round(std_s, 4),
            "n_models": n_models,
            "n_zero": n_zero,
            "n_perfect": n_perfect,
            "question": q_info.get("question", ""),
            "expected_primary_tool": q_info.get("expected", {}).get("primary_tool", ""),
            "most_common_error": most_common_err[0],
            "most_common_error_count": most_common_err[1],
            "most_common_wrong_tool": most_common_wrong_tool[0],
            "most_common_wrong_tool_count": most_common_wrong_tool[1],
        })

    # sort by avg_score ascending (worst first)
    case_stats.sort(key=lambda x: (x["avg_score"], -x["std_score"]))

    # ── 2. Worst-20 ───────────────────────────────────────────────────
    worst_20 = case_stats[:20]

    # ── 3. Universal failures: ALL models < 0.5 ───────────────────────
    universal_failures = [c for c in case_stats if c["avg_score"] < 0.5 and c["n_perfect"] == 0]
    # stricter: every model score < 0.5
    strict_universal = []
    for c in case_stats:
        recs = by_case[c["case_id"]]
        if all(r["score"] < 0.5 for r in recs):
            strict_universal.append(c)

    # ── 4. Discriminating instances (highest variance) ─────────────────
    disc_stats = sorted(case_stats, key=lambda x: -x["std_score"])
    discriminating_top20 = disc_stats[:20]

    # ── 5. Per-difficulty worst ────────────────────────────────────────
    per_diff = {}
    for c in case_stats:
        d = c["difficulty"]
        if d not in per_diff:
            per_diff[d] = c  # already sorted, first is worst

    # ── 6. Per-category worst ──────────────────────────────────────────
    per_cat = {}
    for c in case_stats:
        cat = c["category"]
        if cat not in per_cat:
            per_cat[cat] = c

    # ── 7. Failure pattern grouping ────────────────────────────────────
    failure_patterns = defaultdict(list)
    for c in worst_20:
        err = c["most_common_error"]
        failure_patterns[err].append({
            "case_id": c["case_id"],
            "category": c["category"],
            "question": c["question"],
            "avg_score": c["avg_score"],
            "expected_tool": c["expected_primary_tool"],
            "wrong_tool_called": c["most_common_wrong_tool"],
        })

    # ── aggregate stats ────────────────────────────────────────────────
    total_cases = len(case_stats)
    below_50 = sum(1 for c in case_stats if c["avg_score"] < 0.5)
    below_25 = sum(1 for c in case_stats if c["avg_score"] < 0.25)
    perfect_all = sum(1 for c in case_stats if c["avg_score"] == 1.0)

    # ── build output ───────────────────────────────────────────────────
    output = {
        "summary": {
            "total_cases": total_cases,
            "total_models": len(set(r["model"] for r in records)),
            "cases_avg_below_0.5": below_50,
            "cases_avg_below_0.25": below_25,
            "cases_perfect_all_models": perfect_all,
            "universal_failures_strict": len(strict_universal),
        },
        "worst_20": worst_20,
        "universal_failures": strict_universal[:30],
        "discriminating_top20": discriminating_top20,
        "per_difficulty_worst": per_diff,
        "per_category_worst": per_cat,
        "failure_patterns": {k: v for k, v in failure_patterns.items()},
        "all_cases_ranked": case_stats,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n✓ Saved to {OUT_PATH}\n")

    # ── print readable summary ─────────────────────────────────────────
    print("=" * 90)
    print("  WORST-CASE INSTANCE ANALYSIS — AML-Bench (44 models × 1,258 cases)")
    print("=" * 90)

    print(f"\n  Total cases analysed: {total_cases}")
    print(f"  Cases with avg score < 0.50: {below_50}")
    print(f"  Cases with avg score < 0.25: {below_25}")
    print(f"  Cases perfect across all models: {perfect_all}")
    print(f"  Strict universal failures (all models < 0.5): {len(strict_universal)}")

    print(f"\n{'─' * 90}")
    print("  TOP-10 WORST CASES")
    print(f"{'─' * 90}")
    for i, c in enumerate(worst_20[:10], 1):
        print(f"\n  #{i}  {c['case_id']}  [{c['category']}]  difficulty={c['difficulty']}")
        print(f"      avg={c['avg_score']:.4f}  std={c['std_score']:.4f}  "
              f"score=0: {c['n_zero']}/{c['n_models']}  score=1: {c['n_perfect']}/{c['n_models']}")
        q = c["question"]
        if len(q) > 100:
            q = q[:100] + "…"
        print(f"      Q: {q}")
        print(f"      Expected tool: {c['expected_primary_tool']}")
        print(f"      Most common error: {c['most_common_error']} ({c['most_common_error_count']}x)")
        if c["most_common_wrong_tool"]:
            print(f"      Most common wrong tool: {c['most_common_wrong_tool']} ({c['most_common_wrong_tool_count']}x)")

    print(f"\n{'─' * 90}")
    print("  UNIVERSAL FAILURES (all models score < 0.5)")
    print(f"{'─' * 90}")
    for c in strict_universal[:10]:
        q = c["question"][:80] + ("…" if len(c["question"]) > 80 else "")
        print(f"  {c['case_id']:12s}  avg={c['avg_score']:.4f}  {c['category']:30s}  Q: {q}")

    print(f"\n{'─' * 90}")
    print("  TOP-10 DISCRIMINATING INSTANCES (highest inter-model variance)")
    print(f"{'─' * 90}")
    for c in discriminating_top20[:10]:
        q = c["question"][:70] + ("…" if len(c["question"]) > 70 else "")
        print(f"  {c['case_id']:12s}  avg={c['avg_score']:.4f}  std={c['std_score']:.4f}  "
              f"0s={c['n_zero']}  1s={c['n_perfect']}  Q: {q}")

    print(f"\n{'─' * 90}")
    print("  PER-DIFFICULTY WORST CASE")
    print(f"{'─' * 90}")
    for d in ["easy", "medium", "hard"]:
        if d in per_diff:
            c = per_diff[d]
            q = c["question"][:70] + ("…" if len(c["question"]) > 70 else "")
            print(f"  {d:8s}  {c['case_id']:12s}  avg={c['avg_score']:.4f}  Q: {q}")

    print(f"\n{'─' * 90}")
    print("  PER-CATEGORY WORST CASE")
    print(f"{'─' * 90}")
    for cat in sorted(per_cat.keys()):
        c = per_cat[cat]
        print(f"  {cat:35s}  {c['case_id']:12s}  avg={c['avg_score']:.4f}  err={c['most_common_error']}")

    print(f"\n{'─' * 90}")
    print("  FAILURE PATTERN GROUPS (from worst-20)")
    print(f"{'─' * 90}")
    for pattern, cases in sorted(failure_patterns.items(), key=lambda x: -len(x[1])):
        print(f"\n  [{pattern}] — {len(cases)} cases")
        for c in cases[:5]:
            q = c["question"][:70] + ("…" if len(c["question"]) > 70 else "")
            wt = f" → called {c['wrong_tool_called']}" if c.get("wrong_tool_called") else ""
            print(f"    {c['case_id']:12s}  avg={c['avg_score']:.4f}  expected={c['expected_tool']}{wt}")
            print(f"                  Q: {q}")

    # ── Paper table: representative failure examples ───────────────────
    print(f"\n{'─' * 90}")
    print("  PAPER TABLE: Representative Failure Examples")
    print(f"{'─' * 90}")
    print(f"  {'Case ID':<12} {'Cat':<25} {'Diff':<6} {'Avg':<6} {'#0':<4} {'Error':<15} {'Question (truncated)'}")
    print(f"  {'─'*12} {'─'*25} {'─'*6} {'─'*6} {'─'*4} {'─'*15} {'─'*40}")
    for c in worst_20[:10]:
        q = c["question"][:40] + ("…" if len(c["question"]) > 40 else "")
        print(f"  {c['case_id']:<12} {c['category']:<25} {c['difficulty']:<6} "
              f"{c['avg_score']:<6.3f} {c['n_zero']:<4} {c['most_common_error']:<15} {q}")

    print()


if __name__ == "__main__":
    main()
