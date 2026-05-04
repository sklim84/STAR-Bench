#!/usr/bin/env python3
"""
Comprehensive Error Analysis for AML Tool-Calling Benchmark (Single-turn, KR Round1).

Reads checkpoint JSONL files (per-case granular data) and eval JSON files (pre-aggregated),
then produces:
  1. Model-level summary table
  2. Category-level difficulty analysis
  3. Error type distribution by model family & size
  4. Thinking vs Non-thinking comparison
  5. Per-category error heatmap data
  6. Parameter-level analysis (hallucinated params, param accuracy)
  7. Difficulty discrimination analysis

Output: _experiments/results/error_analysis_single_turn.json + stdout summary
"""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

# ── Paths ──────────────────────────────────────────────────────────────────
BASE = Path(__file__).resolve().parent.parent  # _experiments/
CKPT_DIR = BASE / "results" / "round1" / "checkpoint"
EVAL_DIR = BASE / "results" / "round1" / "eval"
OUTPUT_PATH = BASE / "results" / "error_analysis_single_turn.json"

EXCLUDE_ERRORS = {"api_error", "parse_fail"}


# ── Helpers ────────────────────────────────────────────────────────────────
def load_checkpoint(path: Path) -> list[dict]:
    """Load JSONL, keep LAST entry per case_id, exclude api_error/parse_fail."""
    by_case = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            by_case[rec["case_id"]] = rec  # last wins
    return [r for r in by_case.values() if r.get("error_type") not in EXCLUDE_ERRORS]


def load_all_checkpoints() -> dict[str, list[dict]]:
    """Return {model_short_name: [records]}."""
    result = {}
    for p in sorted(CKPT_DIR.glob("checkpoint_*.jsonl")):
        name = p.stem.replace("checkpoint_", "")
        result[name] = load_checkpoint(p)
    return result


def load_all_evals() -> dict[str, dict]:
    """Return {model_short_name: eval_dict}."""
    result = {}
    for p in sorted(EVAL_DIR.glob("eval_*.json")):
        # Extract model name between first 'eval_' and the timestamp '_YYYYMMDD_'
        stem = p.stem
        parts = stem.split("_")
        # Find timestamp portion (8-digit date)
        ts_idx = None
        for i, part in enumerate(parts):
            if len(part) == 8 and part.isdigit():
                ts_idx = i
                break
        if ts_idx:
            name = "_".join(parts[1:ts_idx])
        else:
            name = "_".join(parts[1:])
        result[name] = json.load(open(p, "r", encoding="utf-8"))
    return result


def infer_family(model_name: str) -> str:
    """Classify model into family."""
    n = model_name.lower()
    if "exaone" in n:
        return "EXAONE"
    if "qwen" in n:
        return "Qwen"
    if "xlam" in n:
        return "xLAM"
    if "llama" in n and "xlam" not in n:
        return "Llama"
    if "kanana" in n:
        return "Kanana"
    if "mistral" in n or "ministral" in n:
        return "Mistral"
    if "hermes" in n:
        return "Hermes"
    if "gpt-oss" in n:
        return "GPT-oss"
    if "a_x" in n:
        return "A.X"
    if "glm" in n:
        return "GLM"
    return "Other"


def infer_size_b(model_name: str) -> float | None:
    """Try to extract parameter size in billions from model name."""
    import re
    n = model_name.replace("-", "_").replace(".", "_")
    # Patterns like 8B, 70b, 1_2B, 30B, 3b, 0_8B, 27B, 20b, 24B, 14B
    # Also handle A3B (mixture) — use the total param count if present before A
    m = re.search(r"(\d+(?:_\d+)?)B", n, re.IGNORECASE)
    if m:
        val = m.group(1).replace("_", ".")
        return float(val)
    return None


def is_thinking_pair(name: str) -> tuple[str | None, str | None]:
    """Return (base_model, mode) if model is a think/nothink variant."""
    if "__think" in name:
        base = name.replace("__think", "")
        return base, "think"
    if "__nothink" in name:
        base = name.replace("__nothink", "")
        return base, "nothink"
    return None, None


# ── Analysis functions ─────────────────────────────────────────────────────
def analysis_1_model_summary(all_ckpt: dict) -> list[dict]:
    """Model-level summary: overall_score, by_error_type, by_difficulty."""
    rows = []
    for model, records in sorted(all_ckpt.items()):
        error_counts = defaultdict(int)
        diff_scores = defaultdict(list)
        scores = []
        for r in records:
            scores.append(r["score"])
            error_counts[r["error_type"]] += 1
            diff_scores[r["difficulty"]].append(r["score"])

        row = {
            "model": model,
            "n_cases": len(records),
            "avg_score": round(mean(scores), 4) if scores else 0,
            "error_type_counts": dict(error_counts),
            "by_difficulty": {
                d: {"count": len(ss), "avg_score": round(mean(ss), 4)}
                for d, ss in sorted(diff_scores.items())
            },
        }
        rows.append(row)
    return sorted(rows, key=lambda x: -x["avg_score"])


def analysis_2_category_difficulty(all_ckpt: dict) -> dict:
    """Per-category avg score across all models. Identify hardest/easiest."""
    cat_scores = defaultdict(list)
    cat_model_scores = defaultdict(lambda: defaultdict(list))
    for model, records in all_ckpt.items():
        for r in records:
            cat_scores[r["category"]].append(r["score"])
            cat_model_scores[r["category"]][model].append(r["score"])

    cats = {}
    for cat, ss in sorted(cat_scores.items()):
        per_model = {
            m: round(mean(mss), 4)
            for m, mss in cat_model_scores[cat].items()
        }
        cats[cat] = {
            "n_total": len(ss),
            "avg_score": round(mean(ss), 4),
            "std_score": round(stdev(ss), 4) if len(ss) > 1 else 0,
            "best_model": max(per_model, key=per_model.get),
            "best_score": max(per_model.values()),
            "worst_model": min(per_model, key=per_model.get),
            "worst_score": min(per_model.values()),
        }
    ranked = sorted(cats.items(), key=lambda x: x[1]["avg_score"])
    return {
        "by_category": dict(ranked),
        "hardest_5": [{"category": k, **v} for k, v in ranked[:5]],
        "easiest_5": [{"category": k, **v} for k, v in ranked[-5:]],
    }


def analysis_3_family_error(all_ckpt: dict) -> dict:
    """Error type distribution grouped by model family and size."""
    family_errors = defaultdict(lambda: defaultdict(int))
    family_scores = defaultdict(list)
    family_models = defaultdict(list)
    size_errors = defaultdict(lambda: defaultdict(int))

    for model, records in all_ckpt.items():
        fam = infer_family(model)
        size = infer_size_b(model)
        family_models[fam].append(model)
        for r in records:
            family_errors[fam][r["error_type"]] += 1
            family_scores[fam].append(r["score"])
            if size is not None:
                bucket = f"{size}B"
                size_errors[bucket][r["error_type"]] += 1

    result = {}
    for fam in sorted(family_errors):
        total = sum(family_errors[fam].values())
        result[fam] = {
            "models": sorted(family_models[fam]),
            "n_records": total,
            "avg_score": round(mean(family_scores[fam]), 4),
            "error_distribution": {
                k: {"count": v, "pct": round(v / total * 100, 1)}
                for k, v in sorted(family_errors[fam].items(), key=lambda x: -x[1])
            },
        }
    return {"by_family": result, "by_size": {k: dict(v) for k, v in sorted(size_errors.items(), key=lambda x: infer_size_b(x[0]) or 0)}}


def analysis_4_think_vs_nothink(all_ckpt: dict) -> list[dict]:
    """Compare think vs nothink variants of the same base model."""
    # Group by base model
    pairs = defaultdict(dict)
    for model in all_ckpt:
        base, mode = is_thinking_pair(model)
        if base and mode:
            pairs[base][mode] = model

    comparisons = []
    for base, modes in sorted(pairs.items()):
        if "think" not in modes or "nothink" not in modes:
            continue
        think_recs = all_ckpt[modes["think"]]
        nothink_recs = all_ckpt[modes["nothink"]]

        think_scores = [r["score"] for r in think_recs]
        nothink_scores = [r["score"] for r in nothink_recs]

        think_errors = defaultdict(int)
        nothink_errors = defaultdict(int)
        for r in think_recs:
            think_errors[r["error_type"]] += 1
        for r in nothink_recs:
            nothink_errors[r["error_type"]] += 1

        # Per-difficulty comparison
        think_diff = defaultdict(list)
        nothink_diff = defaultdict(list)
        for r in think_recs:
            think_diff[r["difficulty"]].append(r["score"])
        for r in nothink_recs:
            nothink_diff[r["difficulty"]].append(r["score"])

        # Per-category delta
        think_cat = defaultdict(list)
        nothink_cat = defaultdict(list)
        for r in think_recs:
            think_cat[r["category"]].append(r["score"])
        for r in nothink_recs:
            nothink_cat[r["category"]].append(r["score"])

        cat_deltas = {}
        all_cats = set(think_cat) | set(nothink_cat)
        for cat in sorted(all_cats):
            t = mean(think_cat[cat]) if think_cat[cat] else 0
            n = mean(nothink_cat[cat]) if nothink_cat[cat] else 0
            cat_deltas[cat] = round(t - n, 4)

        comp = {
            "base_model": base,
            "think_model": modes["think"],
            "nothink_model": modes["nothink"],
            "think_avg_score": round(mean(think_scores), 4),
            "nothink_avg_score": round(mean(nothink_scores), 4),
            "delta": round(mean(think_scores) - mean(nothink_scores), 4),
            "think_error_counts": dict(think_errors),
            "nothink_error_counts": dict(nothink_errors),
            "by_difficulty": {
                d: {
                    "think": round(mean(think_diff[d]), 4) if think_diff[d] else None,
                    "nothink": round(mean(nothink_diff[d]), 4) if nothink_diff[d] else None,
                }
                for d in sorted(set(list(think_diff) + list(nothink_diff)))
            },
            "category_deltas_top5_think_better": sorted(
                cat_deltas.items(), key=lambda x: -x[1]
            )[:5],
            "category_deltas_top5_nothink_better": sorted(
                cat_deltas.items(), key=lambda x: x[1]
            )[:5],
        }
        comparisons.append(comp)
    return comparisons


def analysis_5_heatmap(all_ckpt: dict) -> dict:
    """Per (model, category): dominant error type and avg score."""
    data = defaultdict(lambda: defaultdict(lambda: {"scores": [], "errors": defaultdict(int)}))
    for model, records in all_ckpt.items():
        for r in records:
            cell = data[model][r["category"]]
            cell["scores"].append(r["score"])
            cell["errors"][r["error_type"]] += 1

    heatmap = {}
    for model in sorted(data):
        heatmap[model] = {}
        for cat in sorted(data[model]):
            cell = data[model][cat]
            dominant = max(cell["errors"], key=cell["errors"].get)
            heatmap[model][cat] = {
                "avg_score": round(mean(cell["scores"]), 4),
                "dominant_error": dominant,
                "error_counts": dict(cell["errors"]),
            }
    return heatmap


def analysis_6_parameter(all_ckpt: dict) -> dict:
    """Which categories have most hallucinated params? Worst param_accuracy?"""
    cat_halluc = defaultdict(list)
    cat_param_acc = defaultdict(list)
    cat_key_acc = defaultdict(list)
    model_halluc = defaultdict(int)

    for model, records in all_ckpt.items():
        for r in records:
            cat_halluc[r["category"]].append(r.get("hallucinated_param_count", 0))
            cat_param_acc[r["category"]].append(r.get("param_accuracy", 0))
            cat_key_acc[r["category"]].append(r.get("param_key_accuracy", 0))
            model_halluc[model] += r.get("hallucinated_param_count", 0)

    by_category = {}
    for cat in sorted(cat_halluc):
        by_category[cat] = {
            "total_hallucinated": sum(cat_halluc[cat]),
            "avg_hallucinated": round(mean(cat_halluc[cat]), 3),
            "avg_param_accuracy": round(mean(cat_param_acc[cat]), 4),
            "avg_param_key_accuracy": round(mean(cat_key_acc[cat]), 4),
        }

    worst_param_acc = sorted(by_category.items(), key=lambda x: x[1]["avg_param_accuracy"])[:10]
    most_halluc = sorted(by_category.items(), key=lambda x: -x[1]["total_hallucinated"])[:10]
    worst_models_halluc = sorted(model_halluc.items(), key=lambda x: -x[1])[:10]

    return {
        "by_category": by_category,
        "worst_param_accuracy_categories": [{"category": k, **v} for k, v in worst_param_acc],
        "most_hallucinated_categories": [{"category": k, **v} for k, v in most_halluc],
        "most_hallucinated_models": [{"model": k, "total_hallucinated": v} for k, v in worst_models_halluc],
    }


def analysis_7_difficulty_discrimination(all_ckpt: dict) -> dict:
    """Do easy/medium/hard labels correlate with performance?"""
    # Global
    diff_scores = defaultdict(list)
    # Per model
    model_diff = defaultdict(lambda: defaultdict(list))

    for model, records in all_ckpt.items():
        for r in records:
            diff_scores[r["difficulty"]].append(r["score"])
            model_diff[model][r["difficulty"]].append(r["score"])

    global_stats = {}
    for d in ["easy", "medium", "hard", "irrelevance"]:
        ss = diff_scores.get(d, [])
        if ss:
            global_stats[d] = {
                "count": len(ss),
                "avg_score": round(mean(ss), 4),
                "std_score": round(stdev(ss), 4) if len(ss) > 1 else 0,
                "pct_correct": round(sum(1 for s in ss if s == 1.0) / len(ss) * 100, 1),
            }

    # Per-model discrimination: does every model show easy > medium > hard?
    monotonic_count = 0
    total_models = 0
    per_model_summary = {}
    for model in sorted(model_diff):
        md = model_diff[model]
        avgs = {}
        for d in ["easy", "medium", "hard"]:
            if md[d]:
                avgs[d] = round(mean(md[d]), 4)
        if "easy" in avgs and "medium" in avgs and "hard" in avgs:
            total_models += 1
            is_monotonic = avgs["easy"] >= avgs["medium"] >= avgs["hard"]
            if is_monotonic:
                monotonic_count += 1
            per_model_summary[model] = {
                "easy": avgs["easy"],
                "medium": avgs["medium"],
                "hard": avgs["hard"],
                "monotonic_decreasing": is_monotonic,
            }

    # Error type distribution per difficulty
    diff_error = defaultdict(lambda: defaultdict(int))
    for model, records in all_ckpt.items():
        for r in records:
            diff_error[r["difficulty"]][r["error_type"]] += 1

    return {
        "global_by_difficulty": global_stats,
        "monotonic_models": monotonic_count,
        "total_models": total_models,
        "monotonic_rate": round(monotonic_count / total_models * 100, 1) if total_models else 0,
        "per_model": per_model_summary,
        "error_type_by_difficulty": {d: dict(e) for d, e in diff_error.items()},
    }


# ── Main ───────────────────────────────────────────────────────────────────
def main():
    print("=" * 80)
    print("AML Tool-Calling Benchmark: Comprehensive Error Analysis (KR Round1)")
    print("=" * 80)

    print(f"\nLoading checkpoints from {CKPT_DIR} ...")
    all_ckpt = load_all_checkpoints()
    print(f"  → {len(all_ckpt)} models loaded")
    for m, recs in sorted(all_ckpt.items()):
        print(f"    {m}: {len(recs)} cases")

    print(f"\nLoading evals from {EVAL_DIR} ...")
    all_evals = load_all_evals()
    print(f"  → {len(all_evals)} eval files loaded")

    # ── 1. Model-level summary ──
    print("\n" + "─" * 80)
    print("1. MODEL-LEVEL SUMMARY (sorted by avg_score desc)")
    print("─" * 80)
    summary = analysis_1_model_summary(all_ckpt)
    print(f"{'Model':<55} {'N':>5} {'Score':>7} {'Correct':>8} {'WrongF':>7} {'WrongV':>7} {'MissP':>6} {'Halluc':>7} {'Other':>6}")
    print("-" * 110)
    for row in summary:
        ec = row["error_type_counts"]
        print(
            f"{row['model']:<55} {row['n_cases']:>5} {row['avg_score']:>7.4f}"
            f" {ec.get('correct',0):>8} {ec.get('wrong_func',0):>7}"
            f" {ec.get('wrong_value',0):>7} {ec.get('missing_param',0):>6}"
            f" {ec.get('hallucinated_call',0):>7} {ec.get('other',0):>6}"
        )

    # ── 2. Category difficulty ──
    print("\n" + "─" * 80)
    print("2. CATEGORY-LEVEL DIFFICULTY (avg score across all models)")
    print("─" * 80)
    cat_diff = analysis_2_category_difficulty(all_ckpt)
    print(f"\n  {'Category':<40} {'AvgScore':>8} {'StdDev':>8}")
    print("  " + "-" * 60)
    for cat, info in cat_diff["by_category"].items():
        print(f"  {cat:<40} {info['avg_score']:>8.4f} {info['std_score']:>8.4f}")

    print("\n  ▼ Hardest 5 categories:")
    for item in cat_diff["hardest_5"]:
        print(f"    {item['category']:<40} avg={item['avg_score']:.4f}  worst={item['worst_model']}({item['worst_score']:.4f})")
    print("\n  ▲ Easiest 5 categories:")
    for item in cat_diff["easiest_5"]:
        print(f"    {item['category']:<40} avg={item['avg_score']:.4f}  best={item['best_model']}({item['best_score']:.4f})")

    # ── 3. Family error distribution ──
    print("\n" + "─" * 80)
    print("3. ERROR TYPE DISTRIBUTION BY MODEL FAMILY")
    print("─" * 80)
    family_err = analysis_3_family_error(all_ckpt)
    for fam, info in family_err["by_family"].items():
        print(f"\n  [{fam}] ({len(info['models'])} models, avg_score={info['avg_score']:.4f})")
        for etype, einfo in info["error_distribution"].items():
            bar = "█" * int(einfo["pct"] / 2)
            print(f"    {etype:<20} {einfo['count']:>6}  ({einfo['pct']:>5.1f}%) {bar}")

    # ── 4. Think vs Nothink ──
    print("\n" + "─" * 80)
    print("4. THINKING vs NON-THINKING COMPARISON")
    print("─" * 80)
    think_cmp = analysis_4_think_vs_nothink(all_ckpt)
    if not think_cmp:
        print("  No think/nothink pairs found.")
    for comp in think_cmp:
        delta_sign = "+" if comp["delta"] >= 0 else ""
        print(f"\n  {comp['base_model']}")
        print(f"    Think:   {comp['think_avg_score']:.4f}  |  Nothink: {comp['nothink_avg_score']:.4f}  |  Δ = {delta_sign}{comp['delta']:.4f}")
        print(f"    By difficulty:")
        for d, vals in comp["by_difficulty"].items():
            t = f"{vals['think']:.4f}" if vals["think"] is not None else "N/A"
            n = f"{vals['nothink']:.4f}" if vals["nothink"] is not None else "N/A"
            print(f"      {d:<12} think={t}  nothink={n}")

    # ── 5. Heatmap (abbreviated) ──
    print("\n" + "─" * 80)
    print("5. PER-CATEGORY ERROR HEATMAP (abbreviated, full data in JSON)")
    print("─" * 80)
    heatmap = analysis_5_heatmap(all_ckpt)
    # Show worst 10 (model, category) cells
    worst_cells = []
    for model, cats in heatmap.items():
        for cat, info in cats.items():
            worst_cells.append((model, cat, info["avg_score"], info["dominant_error"]))
    worst_cells.sort(key=lambda x: x[2])
    print(f"\n  Worst 15 (model, category) cells:")
    print(f"  {'Model':<50} {'Category':<35} {'Score':>6} {'DominantError'}")
    print("  " + "-" * 110)
    for m, c, s, e in worst_cells[:15]:
        print(f"  {m:<50} {c:<35} {s:>6.4f} {e}")

    # ── 6. Parameter analysis ──
    print("\n" + "─" * 80)
    print("6. PARAMETER-LEVEL ANALYSIS")
    print("─" * 80)
    param_info = analysis_6_parameter(all_ckpt)
    print(f"\n  Categories with WORST param_accuracy:")
    for item in param_info["worst_param_accuracy_categories"]:
        print(f"    {item['category']:<40} param_acc={item['avg_param_accuracy']:.4f}  key_acc={item['avg_param_key_accuracy']:.4f}")
    print(f"\n  Categories with MOST hallucinated params (total across all models):")
    for item in param_info["most_hallucinated_categories"]:
        print(f"    {item['category']:<40} total_halluc={item['total_hallucinated']:>6}  avg_halluc={item['avg_hallucinated']:.3f}")
    print(f"\n  Models with MOST hallucinated params:")
    for item in param_info["most_hallucinated_models"]:
        print(f"    {item['model']:<55} total_halluc={item['total_hallucinated']:>6}")

    # ── 7. Difficulty discrimination ──
    print("\n" + "─" * 80)
    print("7. DIFFICULTY DISCRIMINATION")
    print("─" * 80)
    disc = analysis_7_difficulty_discrimination(all_ckpt)
    print(f"\n  Global performance by difficulty:")
    for d, info in disc["global_by_difficulty"].items():
        print(f"    {d:<12} n={info['count']:>6}  avg_score={info['avg_score']:.4f}  std={info['std_score']:.4f}  %correct={info['pct_correct']:.1f}%")
    print(f"\n  Monotonic decreasing (easy ≥ medium ≥ hard): {disc['monotonic_models']}/{disc['total_models']} models ({disc['monotonic_rate']:.1f}%)")

    print(f"\n  Error types by difficulty:")
    for d in ["easy", "medium", "hard", "irrelevance"]:
        if d in disc["error_type_by_difficulty"]:
            errs = disc["error_type_by_difficulty"][d]
            total = sum(errs.values())
            top3 = sorted(errs.items(), key=lambda x: -x[1])[:4]
            parts = ", ".join(f"{k}={v}({v/total*100:.1f}%)" for k, v in top3)
            print(f"    {d:<12} {parts}")

    # ── Save JSON ──
    output = {
        "description": "AML Tool-Calling Benchmark Error Analysis (KR Round1, single_turn)",
        "n_models": len(all_ckpt),
        "excluded_error_types": list(EXCLUDE_ERRORS),
        "1_model_summary": summary,
        "2_category_difficulty": cat_diff,
        "3_family_error_distribution": family_err,
        "4_think_vs_nothink": think_cmp,
        "5_heatmap": heatmap,
        "6_parameter_analysis": param_info,
        "7_difficulty_discrimination": disc,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n{'=' * 80}")
    print(f"Full analysis saved to: {OUTPUT_PATH}")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
