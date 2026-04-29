#!/usr/bin/env python3
"""Model-size scaling analysis for AML-Bench.

Analyses:
1. Within-family scaling curves (log-linear fit)
2. Cross-family comparison at similar sizes
3. Parameter efficiency (score / log(params))
4. Single-turn vs multiturn scaling
5. Diminishing returns detection
6. Think/nothink delta vs size
7. Error-type distribution by model size
"""

from __future__ import annotations

import json
import glob
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = ROOT / "_experiments" / "results" / "round1" / "eval"
MT_EVAL_DIR = ROOT / "_experiments" / "results_multiturn" / "round1" / "eval"
OUTPUT_PATH = ROOT / "_experiments" / "results" / "error_analysis_scaling.json"

# ---------------------------------------------------------------------------
# Model -> size (billions) mapping
# ---------------------------------------------------------------------------
MODEL_SIZE_MAP: dict[str, float] = {
    # Qwen3.5
    "Qwen/Qwen3.5-0.8B__think": 0.8,
    "Qwen/Qwen3.5-0.8B__nothink": 0.8,
    "Qwen/Qwen3.5-2B__think": 2,
    "Qwen/Qwen3.5-2B__nothink": 2,
    "Qwen/Qwen3.5-4B__think": 4,
    "Qwen/Qwen3.5-4B__nothink": 4,
    "Qwen/Qwen3.5-9B__think": 9,
    "Qwen/Qwen3.5-9B__nothink": 9,
    "Qwen/Qwen3.5-27B__think": 27,
    "Qwen/Qwen3.5-27B__nothink": 27,
    # Qwen3
    "Qwen/Qwen3-4B-Instruct-2507": 4,
    "Qwen/Qwen3-4B-Thinking-2507__think": 4,
    "Qwen/Qwen3-4B-Thinking-2507__nothink": 4,
    "Qwen/Qwen3-8B": 8,
    "Qwen/Qwen3-30B-A3B-Instruct-2507": 30,  # 30B total, 3B active (MoE)
    "Qwen/Qwen3-30B-A3B-Thinking-2507__think": 30,
    "Qwen/Qwen3-30B-A3B-Thinking-2507__nothink": 30,
    "Qwen/Qwen3-Coder-30B-A3B-Instruct": 30,
    # Qwen2.5
    "Qwen/Qwen2.5-1.5B-Instruct": 1.5,
    # Llama
    "meta-llama/Llama-3.2-1B-Instruct": 1,
    "meta-llama/Llama-3.2-3B-Instruct": 3,
    "meta-llama/Llama-3.1-8B-Instruct": 8,
    "NousResearch/Hermes-3-Llama-3.1-8B": 8,
    "meta-llama/Llama-3.3-70B-Instruct": 70,
    # xLAM (Salesforce, Llama-based)
    "Salesforce/xLAM-2-1b-fc-r": 1,
    "Salesforce/xLAM-2-3b-fc-r": 3,
    "Salesforce/Llama-xLAM-2-8b-fc-r": 8,
    "Salesforce/xLAM-2-32b-fc-r": 32,
    "Salesforce/Llama-xLAM-2-70b-fc-r": 70,
    # Mistral
    "mistralai/Ministral-3-3B-Instruct-2512": 3,
    "mistralai/Ministral-3-8B-Instruct-2512": 8,
    "mistralai/Ministral-3-14B-Instruct-2512": 14,
    "mistralai/Mistral-Nemo-Instruct-2407": 12,  # Mistral Nemo = 12B
    "mistralai/Mistral-Small-3.2-24B-Instruct-2506": 24,
    # EXAONE
    "LGAI-EXAONE/EXAONE-4.0-1.2B": 1.2,
    "LGAI-EXAONE/EXAONE-4.0-32B": 32,
    # Kanana
    "kakaocorp/kanana-2-30b-a3b-instruct": 30,
    "kakaocorp/kanana-2-30b-a3b-thinking-2601__think": 30,
    "kakaocorp/kanana-2-30b-a3b-thinking-2601__nothink": 30,
    # OpenAI gpt-oss
    "openai/gpt-oss-20b__think": 20,
    "openai/gpt-oss-20b__nothink": 20,
    # skt A.X
    "skt/A.X-4.0": 14,       # estimated ~14B (undisclosed)
    "skt/A.X-4.0-Light": 2.1, # estimated ~2.1B (undisclosed)
    # GLM
    "zai-org/GLM-4.7-Flash": 4.7,
}

# Family assignment
FAMILY_MAP: dict[str, str] = {}
FAMILY_RULES = [
    ("Qwen/Qwen3.5-", "Qwen3.5"),
    ("Qwen/Qwen3-Coder", "Qwen3"),
    ("Qwen/Qwen3-", "Qwen3"),
    ("Qwen/Qwen2.5-", "Qwen2.5"),
    ("meta-llama/", "Llama"),
    ("NousResearch/Hermes-3-Llama", "Llama"),
    ("Salesforce/", "xLAM"),
    ("mistralai/", "Mistral"),
    ("LGAI-EXAONE/", "EXAONE"),
    ("kakaocorp/", "Kanana"),
    ("openai/gpt-oss", "gpt-oss"),
    ("skt/", "A.X"),
    ("zai-org/", "GLM"),
]

def get_family(model: str) -> str:
    for prefix, family in FAMILY_RULES:
        if model.startswith(prefix):
            return family
    return "other"

def get_mode(model: str) -> str | None:
    if "__think" in model:
        return "think"
    if "__nothink" in model:
        return "nothink"
    return None


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
def load_single_turn_evals() -> list[dict]:
    records = []
    for fp in sorted(EVAL_DIR.glob("eval_*.json")):
        with open(fp) as f:
            d = json.load(f)
        model = d["model"]
        o = d["overall"]
        size = MODEL_SIZE_MAP.get(model)
        if size is None:
            print(f"[WARN] No size mapping for {model}, skipping")
            continue
        records.append({
            "model": model,
            "family": get_family(model),
            "size_B": size,
            "log_size": math.log2(size),
            "mode": get_mode(model),
            "avg_score": o["avg_score"],
            "primary_tool_hit_rate": o["primary_tool_hit_rate"],
            "avg_param_accuracy": o["avg_param_accuracy"],
            "by_difficulty": o.get("by_difficulty", {}),
            "by_error_type": o.get("by_error_type", {}),
        })
    return records


def load_multiturn_evals() -> list[dict]:
    records = []
    for fp in sorted(MT_EVAL_DIR.glob("multiturn_*.json")):
        with open(fp) as f:
            d = json.load(f)
        model = d["model"]
        # multiturn model names don't have __think/__nothink in model field
        # but filename does
        fname = fp.stem  # multiturn_Qwen_Qwen3_5-4B__think
        mode = None
        if "__think" in fname:
            mode = "think"
        elif "__nothink" in fname:
            mode = "nothink"

        # Build lookup key: model + mode suffix
        lookup = model + ("__" + mode if mode else "")
        size = MODEL_SIZE_MAP.get(lookup)
        if size is None:
            # try without mode
            size = MODEL_SIZE_MAP.get(model)
        if size is None:
            print(f"[WARN-MT] No size mapping for {model} ({fname}), skipping")
            continue

        o = d["overall"]
        records.append({
            "model": lookup,
            "family": get_family(model),
            "size_B": size,
            "log_size": math.log2(size),
            "mode": mode,
            "avg_score": o["avg_score"],
            "scenario_complete_rate": o.get("scenario_complete_rate", None),
        })
    return records


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------
def linreg(x: list[float], y: list[float]) -> dict:
    """Simple linear regression. Returns slope, intercept, R^2."""
    x = np.array(x, dtype=float)
    y = np.array(y, dtype=float)
    if len(x) < 2:
        return {"slope": None, "intercept": None, "r_squared": None, "n": len(x)}
    mx, my = x.mean(), y.mean()
    ss_xx = ((x - mx) ** 2).sum()
    ss_yy = ((y - my) ** 2).sum()
    ss_xy = ((x - mx) * (y - my)).sum()
    if ss_xx == 0:
        return {"slope": None, "intercept": None, "r_squared": None, "n": len(x)}
    slope = float(ss_xy / ss_xx)
    intercept = float(my - slope * mx)
    r_sq = float((ss_xy ** 2) / (ss_xx * ss_yy)) if ss_yy > 0 else 0.0
    return {"slope": round(slope, 6), "intercept": round(intercept, 4),
            "r_squared": round(r_sq, 4), "n": int(len(x))}


# ---------------------------------------------------------------------------
# 1. Within-family scaling curves
# ---------------------------------------------------------------------------
def within_family_scaling(records: list[dict]) -> dict:
    families: dict[str, list] = defaultdict(list)
    for r in records:
        families[r["family"]].append(r)

    results = {}
    for fam, recs in sorted(families.items()):
        # Deduplicate: for think/nothink, pick best score per size
        size_best: dict[float, dict] = {}
        for r in recs:
            s = r["size_B"]
            if s not in size_best or r["avg_score"] > size_best[s]["avg_score"]:
                size_best[s] = r
        points = sorted(size_best.values(), key=lambda x: x["size_B"])
        if len(points) < 2:
            continue
        xs = [p["log_size"] for p in points]
        ys = [p["avg_score"] for p in points]
        fit = linreg(xs, ys)
        results[fam] = {
            "sizes": [p["size_B"] for p in points],
            "scores": [round(p["avg_score"], 4) for p in points],
            "models": [p["model"] for p in points],
            "log_linear_fit": fit,
        }
    return results


# ---------------------------------------------------------------------------
# 2. Cross-family comparison at similar sizes
# ---------------------------------------------------------------------------
def cross_family_comparison(records: list[dict]) -> dict:
    size_buckets = {
        "~1B": (0.5, 1.9),
        "~3B": (2.0, 4.9),
        "~8B": (5.0, 12.0),
        "~14-20B": (12.1, 24.9),
        "~27-32B": (25.0, 39.9),
        "~70B": (40.0, 100.0),
    }
    results = {}
    for bucket_name, (lo, hi) in size_buckets.items():
        entries = []
        for r in records:
            if lo <= r["size_B"] <= hi:
                entries.append({
                    "model": r["model"],
                    "family": r["family"],
                    "size_B": r["size_B"],
                    "avg_score": round(r["avg_score"], 4),
                })
        if entries:
            entries.sort(key=lambda x: -x["avg_score"])
            results[bucket_name] = entries
    return results


# ---------------------------------------------------------------------------
# 3. Parameter efficiency
# ---------------------------------------------------------------------------
def parameter_efficiency(records: list[dict]) -> list[dict]:
    results = []
    for r in records:
        log_s = math.log2(r["size_B"])
        eff = r["avg_score"] / log_s if log_s > 0 else None
        results.append({
            "model": r["model"],
            "family": r["family"],
            "size_B": r["size_B"],
            "avg_score": round(r["avg_score"], 4),
            "efficiency": round(eff, 4) if eff else None,
        })
    results.sort(key=lambda x: -(x["efficiency"] or 0))
    return results


# ---------------------------------------------------------------------------
# 4. Single-turn vs Multiturn scaling
# ---------------------------------------------------------------------------
def single_turn_vs_multiturn(single_turn: list[dict], multiturn: list[dict]) -> dict:
    # Build lookup by model key
    mt_map = {r["model"]: r for r in multiturn}
    paired = []
    for sr in single_turn:
        mr = mt_map.get(sr["model"])
        if mr:
            paired.append({
                "model": sr["model"],
                "family": sr["family"],
                "size_B": sr["size_B"],
                "single_turn_score": round(sr["avg_score"], 4),
                "multiturn_score": round(mr["avg_score"], 4),
                "scenario_complete_rate": mr.get("scenario_complete_rate"),
                "delta": round(sr["avg_score"] - mr["avg_score"], 4),
            })
    paired.sort(key=lambda x: x["size_B"])

    # Fit scaling for each
    families: dict[str, list] = defaultdict(list)
    for p in paired:
        families[p["family"]].append(p)

    family_fits = {}
    for fam, pts in families.items():
        if len(pts) < 2:
            continue
        xs = [math.log2(p["size_B"]) for p in pts]
        s_ys = [p["single_turn_score"] for p in pts]
        m_ys = [p["multiturn_score"] for p in pts]
        family_fits[fam] = {
            "single_turn_fit": linreg(xs, s_ys),
            "multiturn_fit": linreg(xs, m_ys),
        }

    return {"paired_models": paired, "family_fits": family_fits}


# ---------------------------------------------------------------------------
# 5. Diminishing returns
# ---------------------------------------------------------------------------
def diminishing_returns(records: list[dict]) -> dict:
    families: dict[str, list] = defaultdict(list)
    for r in records:
        families[r["family"]].append(r)

    results = {}
    for fam, recs in sorted(families.items()):
        size_best: dict[float, float] = {}
        for r in recs:
            s = r["size_B"]
            if s not in size_best or r["avg_score"] > size_best[s]:
                size_best[s] = r["avg_score"]
        points = sorted(size_best.items())
        if len(points) < 3:
            continue
        # Compute marginal gain per log-size step
        marginals = []
        for i in range(1, len(points)):
            s0, sc0 = points[i - 1]
            s1, sc1 = points[i]
            d_log = math.log2(s1) - math.log2(s0)
            d_score = sc1 - sc0
            marginal = d_score / d_log if d_log > 0 else 0
            marginals.append({
                "from": s0, "to": s1,
                "score_gain": round(d_score, 4),
                "log_size_step": round(d_log, 3),
                "marginal_gain_per_log2B": round(marginal, 4),
            })
        # Where does it plateau? Find first segment with marginal < threshold
        plateau_size = None
        for m in marginals:
            if m["marginal_gain_per_log2B"] < 0.005:  # <0.5% per doubling
                plateau_size = m["from"]
                break
        results[fam] = {
            "sizes": [p[0] for p in points],
            "scores": [round(p[1], 4) for p in points],
            "marginal_gains": marginals,
            "plateau_at_B": plateau_size,
        }
    return results


# ---------------------------------------------------------------------------
# 6. Think mode scaling
# ---------------------------------------------------------------------------
def think_mode_scaling(records: list[dict]) -> dict:
    # Group by (family, size) then find think/nothink pairs
    grouped: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for r in records:
        if r["mode"] in ("think", "nothink"):
            key = (r["family"], r["size_B"])
            grouped[key][r["mode"]] = r

    pairs = []
    for (fam, size), modes in sorted(grouped.items()):
        if "think" in modes and "nothink" in modes:
            t = modes["think"]
            n = modes["nothink"]
            pairs.append({
                "family": fam,
                "size_B": size,
                "think_model": t["model"],
                "nothink_model": n["model"],
                "think_score": round(t["avg_score"], 4),
                "nothink_score": round(n["avg_score"], 4),
                "delta": round(t["avg_score"] - n["avg_score"], 4),
            })

    # Within each family, does delta change with size?
    family_deltas: dict[str, list] = defaultdict(list)
    for p in pairs:
        family_deltas[p["family"]].append(p)

    family_trends = {}
    for fam, pts in family_deltas.items():
        pts_sorted = sorted(pts, key=lambda x: x["size_B"])
        if len(pts_sorted) >= 2:
            xs = [math.log2(p["size_B"]) for p in pts_sorted]
            ys = [p["delta"] for p in pts_sorted]
            family_trends[fam] = {
                "points": pts_sorted,
                "delta_vs_size_fit": linreg(xs, ys),
            }
        else:
            family_trends[fam] = {"points": pts_sorted, "delta_vs_size_fit": None}

    return {"pairs": pairs, "family_trends": family_trends}


# ---------------------------------------------------------------------------
# 7. Error type scaling
# ---------------------------------------------------------------------------
def error_type_scaling(records: list[dict]) -> dict:
    size_buckets = {
        "small (<=3B)": (0, 3.9),
        "medium (4-12B)": (4, 12.9),
        "large (13-32B)": (13, 39.9),
        "xlarge (>=40B)": (40, 200),
    }
    results = {}
    for bucket_name, (lo, hi) in size_buckets.items():
        bucket_errors: dict[str, list[float]] = defaultdict(list)
        total_items = []
        for r in records:
            if lo <= r["size_B"] <= hi and r["by_error_type"]:
                errs = r["by_error_type"]
                total = sum(errs.values())
                if total > 0:
                    for etype, cnt in errs.items():
                        bucket_errors[etype].append(cnt / total)
                    total_items.append(r["model"])
        if not total_items:
            continue
        avg_rates = {}
        for etype, rates in bucket_errors.items():
            avg_rates[etype] = round(float(np.mean(rates)), 4)
        results[bucket_name] = {
            "n_models": len(total_items),
            "avg_error_rates": avg_rates,
            "models": total_items,
        }
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("AML-Bench Model Size Scaling Analysis")
    print("=" * 70)

    single_turn = load_single_turn_evals()
    multiturn = load_multiturn_evals()
    print(f"\nLoaded {len(single_turn)} single_turn evals, {len(multiturn)} multiturn evals")

    # 1. Within-family scaling
    print("\n" + "=" * 70)
    print("1. WITHIN-FAMILY SCALING CURVES")
    print("=" * 70)
    wf = within_family_scaling(single_turn)
    for fam, data in wf.items():
        fit = data["log_linear_fit"]
        print(f"\n  {fam} ({fit['n']} sizes: {data['sizes']})")
        print(f"    Scores: {data['scores']}")
        if fit["slope"] is not None:
            print(f"    Log-linear fit: slope={fit['slope']:.4f}, R²={fit['r_squared']:.4f}")
            print(f"    → +{fit['slope']*100:.2f}% score per doubling of params")

    # 2. Cross-family comparison
    print("\n" + "=" * 70)
    print("2. CROSS-FAMILY COMPARISON AT SIMILAR SIZES")
    print("=" * 70)
    cf = cross_family_comparison(single_turn)
    for bucket, entries in cf.items():
        print(f"\n  {bucket} ({len(entries)} models):")
        for e in entries[:5]:
            print(f"    {e['avg_score']:.4f}  {e['model']} ({e['size_B']}B)")
        if len(entries) > 5:
            print(f"    ... and {len(entries)-5} more")

    # 3. Parameter efficiency
    print("\n" + "=" * 70)
    print("3. PARAMETER EFFICIENCY (score / log2(params))")
    print("=" * 70)
    pe = parameter_efficiency(single_turn)
    print("\n  Top 10 most parameter-efficient:")
    for i, e in enumerate(pe[:10], 1):
        print(f"    {i:2d}. {e['efficiency']:.4f}  {e['model']} ({e['size_B']}B, score={e['avg_score']:.4f})")
    print("\n  Bottom 5:")
    valid_pe = [e for e in pe if e["efficiency"] is not None]
    for e in valid_pe[-5:]:
        print(f"      {e['efficiency']:.4f}  {e['model']} ({e['size_B']}B, score={e['avg_score']:.4f})")

    # 4. Single-turn vs Multiturn
    print("\n" + "=" * 70)
    print("4. SINGLE_TURN VS MULTITURN SCALING")
    print("=" * 70)
    svm = single_turn_vs_multiturn(single_turn, multiturn)
    for p in svm["paired_models"][:10]:
        scr = p.get("scenario_complete_rate")
        scr_str = f", SCR={scr:.2f}" if scr is not None else ""
        print(f"  {p['size_B']:5.1f}B  {p['family']:10s}  "
              f"single={p['single_turn_score']:.4f}  multi={p['multiturn_score']:.4f}  "
              f"delta={p['delta']:+.4f}{scr_str}  {p['model']}")
    print("\n  Family-level fit comparison:")
    for fam, fits in svm["family_fits"].items():
        sf = fits["single_turn_fit"]
        mf = fits["multiturn_fit"]
        if sf["slope"] is not None and mf["slope"] is not None:
            print(f"    {fam}: single_turn slope={sf['slope']:.4f} R²={sf['r_squared']:.4f} | "
                  f"multiturn slope={mf['slope']:.4f} R²={mf['r_squared']:.4f}")

    # 5. Diminishing returns
    print("\n" + "=" * 70)
    print("5. DIMINISHING RETURNS ANALYSIS")
    print("=" * 70)
    dr = diminishing_returns(single_turn)
    for fam, data in dr.items():
        print(f"\n  {fam} ({data['sizes']})")
        for m in data["marginal_gains"]:
            arrow = "↑" if m["marginal_gain_per_log2B"] > 0.005 else "→"
            print(f"    {m['from']}B→{m['to']}B: "
                  f"gain={m['score_gain']:+.4f} ({m['marginal_gain_per_log2B']:+.4f}/log2B) {arrow}")
        if data["plateau_at_B"]:
            print(f"    ⇒ Plateau detected at ~{data['plateau_at_B']}B")
        else:
            print(f"    ⇒ No clear plateau detected")

    # 6. Think mode scaling
    print("\n" + "=" * 70)
    print("6. THINK/NOTHINK DELTA VS MODEL SIZE")
    print("=" * 70)
    tms = think_mode_scaling(single_turn)
    for p in tms["pairs"]:
        sign = "+" if p["delta"] >= 0 else ""
        print(f"  {p['family']:10s} {p['size_B']:5.1f}B  "
              f"think={p['think_score']:.4f}  nothink={p['nothink_score']:.4f}  "
              f"delta={sign}{p['delta']:.4f}")
    print("\n  Family trends:")
    for fam, trend in tms["family_trends"].items():
        fit = trend.get("delta_vs_size_fit")
        if fit and fit.get("slope") is not None:
            direction = "increases" if fit["slope"] > 0 else "decreases"
            print(f"    {fam}: delta {direction} with size "
                  f"(slope={fit['slope']:.4f}, R²={fit['r_squared']:.4f})")

    # 7. Error type scaling
    print("\n" + "=" * 70)
    print("7. ERROR TYPE DISTRIBUTION BY SIZE BUCKET")
    print("=" * 70)
    ets = error_type_scaling(single_turn)
    for bucket, data in ets.items():
        print(f"\n  {bucket} ({data['n_models']} models):")
        for etype, rate in sorted(data["avg_error_rates"].items(),
                                  key=lambda x: -x[1]):
            bar = "#" * int(rate * 50)
            print(f"    {etype:20s} {rate:.4f} {bar}")

    # ---------------------------------------------------------------------------
    # Save results
    # ---------------------------------------------------------------------------
    output = {
        "within_family_scaling": wf,
        "cross_family_comparison": cf,
        "parameter_efficiency": pe[:20],  # top 20
        "single_turn_vs_multiturn": svm,
        "diminishing_returns": dr,
        "think_mode_scaling": tms,
        "error_type_by_size": ets,
        "summary": {
            "total_single_turn_models": len(single_turn),
            "total_multiturn_models": len(multiturn),
            "families_analyzed": list(wf.keys()),
            "key_findings": [],
        },
    }

    # Generate key findings
    findings = output["summary"]["key_findings"]

    # Best scaling family
    best_slope_fam = max(wf.items(),
                         key=lambda x: x[1]["log_linear_fit"]["slope"] or 0)
    findings.append(
        f"Best scaling family: {best_slope_fam[0]} "
        f"(slope={best_slope_fam[1]['log_linear_fit']['slope']:.4f}, "
        f"R²={best_slope_fam[1]['log_linear_fit']['r_squared']:.4f})")

    # Most efficient model
    top_eff = pe[0]
    findings.append(
        f"Most parameter-efficient: {top_eff['model']} "
        f"(eff={top_eff['efficiency']:.4f}, score={top_eff['avg_score']:.4f}, "
        f"{top_eff['size_B']}B)")

    # Think/nothink trend
    for p in tms["pairs"]:
        pass  # just to get last
    avg_delta = np.mean([p["delta"] for p in tms["pairs"]])
    findings.append(
        f"Think mode avg delta: {avg_delta:+.4f} "
        f"({'think helps' if avg_delta > 0 else 'nothink better'})")

    # Plateau findings
    for fam, data in dr.items():
        if data["plateau_at_B"]:
            findings.append(f"{fam}: performance plateaus around {data['plateau_at_B']}B")

    # Multiturn harder
    if svm["paired_models"]:
        avg_gap = np.mean([p["delta"] for p in svm["paired_models"]])
        findings.append(
            f"Avg single_turn-multiturn gap: {avg_gap:.4f} "
            f"(single_turn {'harder' if avg_gap < 0 else 'easier'})")

    # Error type shift
    small_errs = ets.get("small (<=3B)", {}).get("avg_error_rates", {})
    large_errs = ets.get("large (13-32B)", {}).get("avg_error_rates", {})
    if small_errs and large_errs:
        for etype in ["correct", "wrong_func", "hallucinated_call"]:
            s_r = small_errs.get(etype, 0)
            l_r = large_errs.get(etype, 0)
            findings.append(
                f"Error shift ({etype}): small={s_r:.4f} → large={l_r:.4f} "
                f"(delta={l_r - s_r:+.4f})")

    print("\n" + "=" * 70)
    print("KEY FINDINGS")
    print("=" * 70)
    for f in findings:
        print(f"  - {f}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as fout:
        json.dump(output, fout, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
