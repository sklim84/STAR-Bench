"""Per-tool and per-difficulty Wilson score 95% CIs for STAR-Bench.

For each tool (the case `category`) and each difficulty level, reports:
- the number of distinct cases in the bucket and the number of
  (configuration, case) trials behind it
- the hit rate and its Wilson score 95% interval, whose width flags the small
  categories (n < 10, n < 20)
- the same interval per configuration inside the bucket, so a narrow bucket says
  which configuration is unstable rather than only that the bucket is small

**A case is correct when `h == 1`**, the binary primary tool hit the paper
reports. A Wilson interval is an interval for a binomial proportion and needs a
binary outcome, so `h` is what the interval is built on and the rate the output
carries is `h_mean`.

The cohort is the registry rather than the set of files on disk, so a
configuration cannot enter a bucket by appearing in a directory. The output names
how many configurations are scored and which ids are missing.

Output: `_experiments/results_RQ1/per_tool_wilson_ci_round1.json`, under the
directory `regenerate_analysis.py` advertises for this step.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

_SB = Path(__file__).resolve().parents[2]  # repository root
if str(_SB) not in sys.path:
    sys.path.insert(0, str(_SB))

from _experiments.scripts.analysis import load  # noqa: E402

OUT_DIR = _SB / "_experiments" / "results_RQ1"
COLUMN = "single"  # the main-table arm: Korean tool schema, Korean questions


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
    """Bucket every (configuration, case) row of the scored cohort by tool and difficulty."""
    cases = load.single(column=COLUMN)
    per_tool: dict[str, list[dict]] = defaultdict(list)
    per_difficulty: dict[str, list[dict]] = defaultdict(list)
    case_meta: dict[str, dict] = {}

    for row in cases.itertuples(index=False):
        tool = row.category if row.category is not None else "unknown"
        diff = row.difficulty if row.difficulty is not None else "unknown"
        case_meta.setdefault(row.case_id, {"tool": tool, "difficulty": diff})
        record = {"config_id": row.config_id, "label": row.label,
                  "case_id": row.case_id, "h": int(row.h)}
        per_tool[tool].append(record)
        per_difficulty[diff].append(record)

    tool_case_count: dict[str, int] = defaultdict(int)
    diff_case_count: dict[str, int] = defaultdict(int)
    for meta in case_meta.values():
        tool_case_count[meta["tool"]] += 1
        diff_case_count[meta["difficulty"]] += 1

    return {
        "per_tool": per_tool,
        "per_difficulty": per_difficulty,
        "tool_case_count": dict(tool_case_count),
        "diff_case_count": dict(diff_case_count),
        "config_ids": sorted(cases["config_id"].unique()),
    }


def cohort() -> dict:
    """How much of the 28-configuration registry this run covers (rule 4)."""
    table = load.missing()
    scored = table.loc[table[COLUMN], "config_id"].tolist()
    absent = table.loc[~table[COLUMN], "config_id"].tolist()
    return {"column": COLUMN, "n_configs": len(scored), "n_registry": len(table),
            "config_ids": scored, "missing_config_ids": absent}


def summarize(records: list[dict], n_cases: int) -> dict:
    """records = the (configuration, case) rows in one bucket."""
    if not records:
        return {"n_cases": 0, "h_mean": None, "wilson_ci_width": None}
    h = np.array([r["h"] for r in records], dtype=np.int64)
    correct = int(h.sum())
    total = int(h.size)
    ci_low, ci_high = wilson_ci(correct, total)
    return {
        "n_cases": n_cases,
        "n_model_case_pairs": total,
        "n_correct": correct,
        "h_mean": round(correct / total, 4),
        "wilson_ci_low": round(ci_low, 4),
        "wilson_ci_high": round(ci_high, 4),
        "wilson_ci_width": round(ci_high - ci_low, 4),
    }


def summarize_per_config_per_bucket(bucket_records: list[dict]) -> list[dict]:
    """Per-configuration Wilson CI inside a single bucket, to see which
    configuration is unstable when the bucket is small."""
    by_config: dict[str, dict] = {}
    for r in bucket_records:
        entry = by_config.setdefault(r["config_id"], {"label": r["label"], "h": []})
        entry["h"].append(r["h"])

    result = []
    for config_id, entry in by_config.items():
        arr = np.array(entry["h"], dtype=np.int64)
        correct = int(arr.sum())
        n = int(arr.size)
        ci_lo, ci_hi = wilson_ci(correct, n)
        result.append({
            "config_id": config_id,
            "label": entry["label"],
            "n": n,
            "n_correct": correct,
            "h_mean": round(correct / n, 4),
            "wilson_ci_low": round(ci_lo, 4),
            "wilson_ci_high": round(ci_hi, 4),
            "wilson_ci_width": round(ci_hi - ci_lo, 4),
        })
    result.sort(key=lambda d: -d["h_mean"])
    return result


def main() -> None:
    covered = cohort()
    print(f"[1/2] Loading per-case rows for {covered['n_configs']} of "
          f"{covered['n_registry']} configurations...")
    data = load_all_cases()
    print(f"  configurations: {covered['n_configs']}")
    if covered["missing_config_ids"]:
        print(f"  not scored yet ({len(covered['missing_config_ids'])}): "
              f"{', '.join(covered['missing_config_ids'])}")
    print(f"  unique tools: {len(data['tool_case_count'])}")
    print(f"  unique difficulties: {len(data['diff_case_count'])}")

    print("[2/2] Computing per-tool, per-difficulty Wilson intervals on h == 1...")

    per_tool_summary = {}
    for tool, n_cases in sorted(data["tool_case_count"].items(), key=lambda x: -x[1]):
        per_tool_summary[tool] = summarize(data["per_tool"][tool], n_cases)

    per_difficulty_summary = {}
    for diff, n_cases in sorted(data["diff_case_count"].items(), key=lambda x: -x[1]):
        per_difficulty_summary[diff] = summarize(data["per_difficulty"][diff], n_cases)

    top_configs_per_tool = {
        tool: summarize_per_config_per_bucket(records)[:5]
        for tool, records in data["per_tool"].items()
    }

    out = {
        "cohort": covered,
        "correct_definition": "h == 1 (primary tool hit)",
        "per_tool": per_tool_summary,
        "per_difficulty": per_difficulty_summary,
        "top5_per_tool_ci": top_configs_per_tool,
        "summary": {
            "total_cases": sum(data["tool_case_count"].values()),
            "n_tools": len(data["tool_case_count"]),
            "n_configs": covered["n_configs"],
            "missing_config_ids": covered["missing_config_ids"],
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

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "per_tool_wilson_ci_round1.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {out_path}")

    print()
    print("=" * 80)
    print(f"PER-TOOL SUMMARY (sorted by N), {covered['n_configs']} of "
          f"{covered['n_registry']} configurations:")
    print("=" * 80)
    print(f"{'Tool':<32} {'N':>4} {'h':>7} {'Wilson Width':>14}")
    print("-" * 80)
    for tool, s in per_tool_summary.items():
        print(f"{tool:<32} {s['n_cases']:>4} {s['h_mean']:>7.4f} {s['wilson_ci_width']:>14.4f}")

    print()
    print("=" * 80)
    print("PER-DIFFICULTY SUMMARY:")
    print("=" * 80)
    for diff, s in per_difficulty_summary.items():
        print(f"  {diff:<16} N={s['n_cases']:<4} h={s['h_mean']:.4f} "
              f"wilson_width={s['wilson_ci_width']:.4f}")

    print()
    print(f"Tools with N < 10: {len(out['summary']['small_tools_n_lt_10'])}")
    for t, n in out["summary"]["small_tools_n_lt_10"]:
        print(f"  {t}: N={n}")
    print(f"Tools with N < 20: {len(out['summary']['small_tools_n_lt_20'])}")


if __name__ == "__main__":
    main()
