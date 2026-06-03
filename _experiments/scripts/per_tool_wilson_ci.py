"""Per-tool and per-difficulty Wilson score 95% CIs for AML-Bench.

For each of the 23 tools and each difficulty level,
reports:
- Sample size N
- Mean score (averaged over 3 rounds across all 44 configs) — domain-level view
- Wilson 95% CI width — flags small categories (n < 10)
- Top model accuracy with Wilson CI for small categories

This directly addresses reviewer concerns about category-level reliability
(Reviewer w7S5 / yR5N of KFinEval pattern).
"""
from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict
import numpy as np

ROUND1_CKPT = Path("/home/work/kftc_sklim/KA-001-AML-Assistant/_experiments/results/round1/checkpoint")


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 95% CI for a binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    halfw = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, centre - halfw), min(1.0, centre + halfw))


def load_all_cases() -> dict:
    """Merge all 44 model checkpoints into per-case records."""
    files = sorted(ROUND1_CKPT.glob("checkpoint_*.jsonl"))
    per_tool: dict[str, list[dict]] = defaultdict(list)
    per_difficulty: dict[str, list[dict]] = defaultdict(list)
    per_tool_difficulty: dict[tuple[str, str], list[dict]] = defaultdict(list)
    case_meta: dict[str, dict] = {}

    for fp in files:
        model = fp.stem.replace("checkpoint_", "")
        with fp.open() as f:
            for line in f:
                rec = json.loads(line)
                cid = rec["id"]
                tool = rec.get("category", "unknown")
                diff = rec.get("difficulty", "unknown")
                case_meta.setdefault(cid, {"tool": tool, "difficulty": diff})
                per_tool[tool].append({"model": model, "id": cid, "score": rec["score"]})
                per_difficulty[diff].append({"model": model, "id": cid, "score": rec["score"]})
                per_tool_difficulty[(tool, diff)].append({"model": model, "id": cid, "score": rec["score"]})

    # Per-case unique count
    tool_case_count: dict[str, int] = defaultdict(int)
    diff_case_count: dict[str, int] = defaultdict(int)
    for meta in case_meta.values():
        tool_case_count[meta["tool"]] += 1
        diff_case_count[meta["difficulty"]] += 1

    return {
        "per_tool": per_tool,
        "per_difficulty": per_difficulty,
        "per_tool_difficulty": per_tool_difficulty,
        "tool_case_count": dict(tool_case_count),
        "diff_case_count": dict(diff_case_count),
        "n_configs": len(files),
    }


def summarize(records: list[dict], n_cases: int) -> dict:
    """records = list of {model, id, score} across all models/cases in this bucket."""
    if not records:
        return {"n_cases": 0, "mean_score": None, "ci_width": None}
    scores = np.array([r["score"] for r in records], dtype=np.float32)

    mean_score = float(np.mean(scores))
    # Correct count: score >= 0.9 threshold (aligned with evaluator primary_tool_hit approximation)
    correct_count = int(np.sum(scores >= 0.9))
    total = len(scores)
    ci_low, ci_high = wilson_ci(correct_count, total)

    return {
        "n_cases": n_cases,
        "n_model_case_pairs": total,
        "mean_score": round(mean_score, 4),
        "prop_correct_0_9": round(correct_count / total, 4),
        "wilson_ci_low": round(ci_low, 4),
        "wilson_ci_high": round(ci_high, 4),
        "wilson_ci_width": round(ci_high - ci_low, 4),
    }


def summarize_per_model_per_bucket(bucket_records: list[dict]) -> dict:
    """Per-model Wilson CI inside a single bucket (for identifying which models
    are unstable when N is small)."""
    by_model: dict[str, list[float]] = defaultdict(list)
    for r in bucket_records:
        by_model[r["model"]].append(r["score"])

    result = []
    for model, scores in by_model.items():
        arr = np.array(scores, dtype=np.float32)
        correct = int(np.sum(arr >= 0.9))
        n = len(arr)
        ci_lo, ci_hi = wilson_ci(correct, n)
        result.append({
            "model": model,
            "n": n,
            "mean_score": round(float(np.mean(arr)), 4),
            "prop_correct": round(correct / n, 4),
            "wilson_ci_low": round(ci_lo, 4),
            "wilson_ci_high": round(ci_hi, 4),
            "wilson_ci_width": round(ci_hi - ci_lo, 4),
        })
    result.sort(key=lambda d: -d["mean_score"])
    return result


def main() -> None:
    print("[1/2] Loading all per-case records across 44 configs...")
    data = load_all_cases()
    print(f"  configs: {data['n_configs']}")
    print(f"  unique tools: {len(data['tool_case_count'])}")
    print(f"  unique difficulties: {len(data['diff_case_count'])}")

    print("[2/2] Computing per-tool, per-difficulty stats...")

    per_tool_summary = {}
    for tool, n_cases in sorted(data["tool_case_count"].items(), key=lambda x: -x[1]):
        per_tool_summary[tool] = summarize(data["per_tool"][tool], n_cases)

    per_difficulty_summary = {}
    for diff, n_cases in sorted(data["diff_case_count"].items(), key=lambda x: -x[1]):
        per_difficulty_summary[diff] = summarize(data["per_difficulty"][diff], n_cases)

    # For top-5 models, per-tool Wilson CI width (flags which tools are "noisy")
    top_models_per_tool: dict[str, list[dict]] = {}
    for tool, records in data["per_tool"].items():
        stats = summarize_per_model_per_bucket(records)
        top_models_per_tool[tool] = stats[:5]

    out = {
        "per_tool": per_tool_summary,
        "per_difficulty": per_difficulty_summary,
        "top5_per_tool_ci": top_models_per_tool,
        "summary": {
            "total_cases": sum(data["tool_case_count"].values()),
            "n_tools": len(data["tool_case_count"]),
            "small_tools_n_lt_10": sorted(
                [(t, n) for t, n in data["tool_case_count"].items() if n < 10],
                key=lambda x: x[1],
            ),
            "small_tools_n_lt_20": sorted(
                [(t, n) for t, n in data["tool_case_count"].items() if n < 20],
                key=lambda x: x[1],
            ),
        },
    }

    out_path = Path("/home/work/kftc_sklim/KA-001-AML-Assistant/_experiments/results/per_tool_wilson_ci_round1.json")
    with out_path.open("w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {out_path}")

    print()
    print("=" * 80)
    print("PER-TOOL SUMMARY (sorted by N):")
    print("=" * 80)
    print(f"{'Tool':<32} {'N':>4} {'Mean':>7} {'Wilson Width':>14}")
    print("-" * 80)
    for tool, s in per_tool_summary.items():
        print(f"{tool:<32} {s['n_cases']:>4} {s['mean_score']:>7.4f} {s['wilson_ci_width']:>14.4f}")

    print()
    print("=" * 80)
    print("PER-DIFFICULTY SUMMARY:")
    print("=" * 80)
    for diff, s in per_difficulty_summary.items():
        print(f"  {diff:<16} N={s['n_cases']:<4} mean={s['mean_score']:.4f} wilson_width={s['wilson_ci_width']:.4f}")

    print()
    print(f"Tools with N < 10: {len(out['summary']['small_tools_n_lt_10'])}")
    for t, n in out["summary"]["small_tools_n_lt_10"]:
        print(f"  {t}: N={n}")
    print(f"Tools with N < 20: {len(out['summary']['small_tools_n_lt_20'])}")


if __name__ == "__main__":
    main()
