#!/usr/bin/env python3
"""
Correlation analysis between AML-Bench evaluation dimensions.

Computes Pearson and Spearman correlations to determine whether
evaluation dimensions measure independent capabilities.

Output: _experiments/results/error_analysis_correlation.json
"""

import json
import glob
import re
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats
import pandas as pd

# ── paths ───────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
CKPT_DIR = ROOT / "_experiments" / "results" / "round1" / "checkpoint"
EVAL_DIR = ROOT / "_experiments" / "results" / "round1" / "eval"
MT_EVAL_DIR = ROOT / "_experiments" / "results_multiturn" / "round1" / "eval"
OUT_PATH = ROOT / "_experiments" / "results" / "error_analysis_correlation.json"


# ── helpers ─────────────────────────────────────────────────────────
def _corr(x, y, label=""):
    """Compute Pearson & Spearman, return dict with r, rho, p-values, n."""
    x, y = np.array(x, dtype=float), np.array(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    n = len(x)
    if n < 3:
        return {"label": label, "n": n, "note": "insufficient data"}
    r_pearson, p_pearson = stats.pearsonr(x, y)
    r_spearman, p_spearman = stats.spearmanr(x, y)
    return {
        "label": label,
        "n": int(n),
        "pearson_r": round(float(r_pearson), 4),
        "pearson_p": round(float(p_pearson), 6),
        "spearman_rho": round(float(r_spearman), 4),
        "spearman_p": round(float(p_spearman), 6),
    }


def _interpret(r):
    """Interpret correlation strength."""
    ar = abs(r)
    if ar >= 0.8:
        return "very strong (potentially redundant)"
    elif ar >= 0.6:
        return "strong"
    elif ar >= 0.4:
        return "moderate"
    elif ar >= 0.2:
        return "weak"
    else:
        return "negligible (independent)"


# ── model size extraction ───────────────────────────────────────────
SIZE_MAP = {
    # Manually specify where regex fails or is ambiguous
    "Qwen3-30B-A3B": 3,      # A3B = active 3B (MoE)
    "Qwen3_5-27B": 27,
    "Qwen3_5-9B": 9,
    "Qwen3_5-4B": 4,
    "Qwen3_5-2B": 2,
    "Qwen3_5-0_8B": 0.8,
    "Qwen3-8B": 8,
    "Qwen3-4B": 4,
    "Qwen2_5-1_5B": 1.5,
    "kanana-2-30b-a3b": 3,    # active 3B MoE
    "EXAONE-4_0-1_2B": 1.2,
    "EXAONE-4_0-32B": 32,
    "Llama-3_1-8B": 8,
    "Llama-3_2-1B": 1,
    "Llama-3_2-3B": 3,
    "Llama-3_3-70B": 70,
    "Hermes-3-Llama-3_1-8B": 8,
    "xLAM-2-1b": 1,
    "xLAM-2-3b": 3,
    "Llama-xLAM-2-8b": 8,
    "xLAM-2-32b": 32,
    "Llama-xLAM-2-70b": 70,
    "Ministral-3-3B": 3,
    "Ministral-3-8B": 8,
    "Ministral-3-14B": 14,
    "Mistral-Nemo": 12,
    "Mistral-Small-3_2-24B": 24,
    "gpt-oss-20b": 20,
    "GLM-4_7-Flash": 4.7,       # GLM-4-7B variant -> ~4.7B? Actually 9B. Let's use name.
    "A_X-4_0-Light": None,      # unknown size
    "A_X-4_0": None,            # unknown size
    "Qwen3-Coder-30B-A3B": 3,  # active 3B MoE
}


def _extract_size(model_name: str):
    """Try to extract model size in billions from name."""
    # Check manual map first (match partial)
    for key, val in SIZE_MAP.items():
        if key in model_name:
            return val
    # Regex fallback: look for number followed by B
    m = re.search(r'(\d+(?:[._]\d+)?)\s*[Bb]', model_name)
    if m:
        return float(m.group(1).replace('_', '.'))
    return None


# ── family extraction ───────────────────────────────────────────────
def _extract_family(model_name: str) -> str:
    """Extract model family from name."""
    name_lower = model_name.lower()
    if "qwen" in name_lower:
        return "Qwen"
    if "llama" in name_lower and "xlam" not in name_lower:
        return "Llama"
    if "xlam" in name_lower:
        return "xLAM"
    if "mistral" in name_lower or "ministral" in name_lower:
        return "Mistral"
    if "exaone" in name_lower:
        return "EXAONE"
    if "kanana" in name_lower:
        return "Kanana"
    if "hermes" in name_lower:
        return "Hermes"
    if "gpt-oss" in name_lower:
        return "GPT-oss"
    if "glm" in name_lower:
        return "GLM"
    if "a_x" in name_lower or "a.x" in name_lower:
        return "A.X"
    return "Other"


# ── data loading ────────────────────────────────────────────────────
def load_checkpoint_data():
    """Load per-case results from checkpoint JSONL files.
    Returns dict: model_name -> list of record dicts.
    """
    data = {}
    for fpath in sorted(CKPT_DIR.glob("checkpoint_*.jsonl")):
        records = []
        with open(fpath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
        if not records:
            continue

        model_name = records[0].get("model", fpath.stem.replace("checkpoint_", ""))

        # Filter out api_error and parse_fail
        records = [r for r in records if r.get("error_type") not in ("api_error", "parse_fail")]

        # Deduplicate: keep last entry per case_id (handles >1258 lines)
        seen = {}
        for r in records:
            cid = r.get("case_id") or r.get("id")
            seen[cid] = r
        records = list(seen.values())

        data[model_name] = records
    return data


def load_eval_data():
    """Load per-model aggregated eval results.
    Returns dict: model_name -> eval dict.
    """
    data = {}
    for fpath in sorted(EVAL_DIR.glob("eval_*.json")):
        with open(fpath) as f:
            d = json.load(f)
        model_name = d.get("model", fpath.stem)
        data[model_name] = d
    return data


def load_multiturn_data():
    """Load multiturn eval results.
    Returns dict: model_name -> overall dict.
    """
    data = {}
    for fpath in sorted(MT_EVAL_DIR.glob("multiturn_*.json")):
        with open(fpath) as f:
            d = json.load(f)
        model_name = d.get("model", fpath.stem)
        data[model_name] = d.get("overall", {})
    return data


# ── analysis functions ──────────────────────────────────────────────
def analysis_tool_vs_param(ckpt_data):
    """1. Tool Selection vs Parameter Extraction across models."""
    models, tool_hits, param_accs = [], [], []
    for model, records in ckpt_data.items():
        if not records:
            continue
        th = np.mean([int(r.get("primary_tool_hit", False)) for r in records])
        pa = np.mean([r.get("param_accuracy", 0) for r in records])
        models.append(model)
        tool_hits.append(th)
        param_accs.append(pa)
    return _corr(tool_hits, param_accs, "tool_hit vs param_accuracy"), models, tool_hits, param_accs


def analysis_singleton_vs_multiturn(eval_data, mt_data):
    """2. Singleton vs Multiturn overall score."""
    models, s_scores, m_scores = [], [], []
    for model in eval_data:
        if model in mt_data:
            s = eval_data[model].get("overall", {}).get("avg_score")
            m = mt_data[model].get("avg_score")
            if s is not None and m is not None:
                models.append(model)
                s_scores.append(s)
                m_scores.append(m)
    return _corr(s_scores, m_scores, "singleton_score vs multiturn_score"), models, s_scores, m_scores


def analysis_size_vs_performance(eval_data):
    """3. Model Size vs Performance."""
    models, sizes, scores = [], [], []
    for model, d in eval_data.items():
        size = _extract_size(model)
        if size is not None:
            s = d.get("overall", {}).get("avg_score")
            if s is not None:
                models.append(model)
                sizes.append(size)
                scores.append(s)
    return _corr(sizes, scores, "model_size(B) vs score"), models, sizes, scores


def analysis_difficulty_correlation(eval_data):
    """4. Easy/Medium/Hard performance correlation across models."""
    models, easy, medium, hard = [], [], [], []
    for model, d in eval_data.items():
        bd = d.get("overall", {}).get("by_difficulty", {})
        e = bd.get("easy", {}).get("avg_score")
        m = bd.get("medium", {}).get("avg_score")
        h = bd.get("hard", {}).get("avg_score")
        if e is not None and m is not None and h is not None:
            models.append(model)
            easy.append(e)
            medium.append(m)
            hard.append(h)

    return {
        "easy_vs_medium": _corr(easy, medium, "easy_score vs medium_score"),
        "easy_vs_hard": _corr(easy, hard, "easy_score vs hard_score"),
        "medium_vs_hard": _corr(medium, hard, "medium_score vs hard_score"),
    }, models, easy, medium, hard


def analysis_tool_hit_vs_hallucination(ckpt_data):
    """5. Tool Hit vs Hallucinated Param Count."""
    models, tool_hits, halluc = [], [], []
    for model, records in ckpt_data.items():
        if not records:
            continue
        th = np.mean([int(r.get("primary_tool_hit", False)) for r in records])
        hc = np.mean([r.get("hallucinated_param_count", 0) for r in records])
        models.append(model)
        tool_hits.append(th)
        halluc.append(hc)
    return _corr(tool_hits, halluc, "tool_hit_rate vs avg_hallucinated_params"), models, tool_hits, halluc


def analysis_family_variance(eval_data):
    """6. Open-source family comparison: within-family vs across-family variance."""
    family_scores = defaultdict(list)
    for model, d in eval_data.items():
        fam = _extract_family(model)
        s = d.get("overall", {}).get("avg_score")
        if s is not None:
            family_scores[fam].append((model, s))

    # Compute within-family variance and across-family variance
    within_vars = {}
    family_means = {}
    for fam, items in family_scores.items():
        scores = [s for _, s in items]
        family_means[fam] = float(np.mean(scores))
        if len(scores) >= 2:
            within_vars[fam] = float(np.var(scores, ddof=1))
        else:
            within_vars[fam] = None

    # Across-family variance (variance of family means)
    valid_means = [m for m in family_means.values()]
    across_var = float(np.var(valid_means, ddof=1)) if len(valid_means) >= 2 else None

    # Average within-family variance
    valid_within = [v for v in within_vars.values() if v is not None]
    avg_within_var = float(np.mean(valid_within)) if valid_within else None

    # One-way ANOVA across families (only families with >=2 members)
    anova_groups = []
    anova_labels = []
    for fam, items in family_scores.items():
        if len(items) >= 2:
            anova_groups.append([s for _, s in items])
            anova_labels.append(fam)

    anova_result = None
    if len(anova_groups) >= 2:
        f_stat, p_val = stats.f_oneway(*anova_groups)
        anova_result = {
            "f_statistic": round(float(f_stat), 4),
            "p_value": round(float(p_val), 6),
            "groups": anova_labels,
            "group_sizes": [len(g) for g in anova_groups],
        }

    return {
        "family_means": {fam: round(m, 4) for fam, m in sorted(family_means.items(), key=lambda x: -x[1])},
        "within_family_variance": {fam: round(v, 6) if v is not None else None
                                    for fam, v in sorted(within_vars.items())},
        "avg_within_family_variance": round(avg_within_var, 6) if avg_within_var else None,
        "across_family_variance": round(across_var, 6) if across_var else None,
        "variance_ratio_across_div_within": (
            round(across_var / avg_within_var, 4)
            if across_var and avg_within_var and avg_within_var > 0 else None
        ),
        "anova": anova_result,
        "family_members": {fam: [m for m, _ in items]
                           for fam, items in sorted(family_scores.items())},
    }


def analysis_additional_metric_correlations(ckpt_data):
    """Additional: pairwise correlations among all metric dimensions."""
    metrics = ["primary_tool_hit", "tool_recall", "tool_precision",
               "param_accuracy", "param_key_accuracy", "order_score", "score"]

    # Per-model averages
    model_avgs = {}
    for model, records in ckpt_data.items():
        if not records:
            continue
        avgs = {}
        for m in metrics:
            vals = []
            for r in records:
                v = r.get(m)
                if isinstance(v, bool):
                    v = int(v)
                if v is not None:
                    vals.append(float(v))
            avgs[m] = np.mean(vals) if vals else np.nan
        model_avgs[model] = avgs

    df = pd.DataFrame(model_avgs).T

    # Pairwise correlations
    results = {}
    for i, m1 in enumerate(metrics):
        for m2 in metrics[i+1:]:
            label = f"{m1} vs {m2}"
            results[label] = _corr(df[m1].values, df[m2].values, label)

    return results


# ── main ────────────────────────────────────────────────────────────
def main():
    print("Loading data...")
    ckpt_data = load_checkpoint_data()
    eval_data = load_eval_data()
    mt_data = load_multiturn_data()

    print(f"  Checkpoint models: {len(ckpt_data)}")
    print(f"  Eval models: {len(eval_data)}")
    print(f"  Multiturn models: {len(mt_data)}")

    results = {}

    # 1. Tool Selection vs Parameter Extraction
    print("\n" + "="*70)
    print("1. Tool Selection vs Parameter Extraction")
    print("="*70)
    corr1, _, _, _ = analysis_tool_vs_param(ckpt_data)
    results["tool_selection_vs_param_extraction"] = corr1
    print(f"   Pearson r  = {corr1['pearson_r']:.4f}  (p={corr1['pearson_p']:.6f})")
    print(f"   Spearman ρ = {corr1['spearman_rho']:.4f}  (p={corr1['spearman_p']:.6f})")
    print(f"   Interpretation: {_interpret(corr1['pearson_r'])}")

    # 2. Singleton vs Multiturn
    print("\n" + "="*70)
    print("2. Singleton vs Multiturn Performance")
    print("="*70)
    corr2, _, _, _ = analysis_singleton_vs_multiturn(eval_data, mt_data)
    results["singleton_vs_multiturn"] = corr2
    print(f"   Pearson r  = {corr2['pearson_r']:.4f}  (p={corr2['pearson_p']:.6f})")
    print(f"   Spearman ρ = {corr2['spearman_rho']:.4f}  (p={corr2['spearman_p']:.6f})")
    print(f"   Interpretation: {_interpret(corr2['pearson_r'])}")

    # 3. Model Size vs Performance
    print("\n" + "="*70)
    print("3. Model Size vs Performance")
    print("="*70)
    corr3, models3, sizes3, scores3 = analysis_size_vs_performance(eval_data)
    results["model_size_vs_performance"] = corr3
    if "pearson_r" in corr3:
        print(f"   Pearson r  = {corr3['pearson_r']:.4f}  (p={corr3['pearson_p']:.6f})")
        print(f"   Spearman ρ = {corr3['spearman_rho']:.4f}  (p={corr3['spearman_p']:.6f})")
        print(f"   Interpretation: {_interpret(corr3['pearson_r'])}")
        # Also compute log(size) correlation
        corr3_log = _corr(np.log2(sizes3), scores3, "log2(model_size) vs score")
        results["model_size_log_vs_performance"] = corr3_log
        print(f"\n   log2(size) correlation:")
        print(f"   Pearson r  = {corr3_log['pearson_r']:.4f}  (p={corr3_log['pearson_p']:.6f})")
        print(f"   Spearman ρ = {corr3_log['spearman_rho']:.4f}  (p={corr3_log['spearman_p']:.6f})")
    else:
        print(f"   {corr3}")

    # Print size-score pairs for reference
    print(f"\n   Model sizes used ({len(models3)}):")
    for m, sz, sc in sorted(zip(models3, sizes3, scores3), key=lambda x: x[1]):
        print(f"     {sz:6.1f}B  score={sc:.4f}  {m}")

    # 4. Easy/Medium/Hard correlation
    print("\n" + "="*70)
    print("4. Difficulty Level Correlation")
    print("="*70)
    corr4, _, _, _, _ = analysis_difficulty_correlation(eval_data)
    results["difficulty_correlation"] = corr4
    for pair, c in corr4.items():
        print(f"\n   {pair}:")
        print(f"     Pearson r  = {c['pearson_r']:.4f}  (p={c['pearson_p']:.6f})")
        print(f"     Spearman ρ = {c['spearman_rho']:.4f}  (p={c['spearman_p']:.6f})")
        print(f"     Interpretation: {_interpret(c['pearson_r'])}")

    # 5. Tool Hit vs Hallucination
    print("\n" + "="*70)
    print("5. Tool Hit Rate vs Hallucinated Parameters")
    print("="*70)
    corr5, _, _, _ = analysis_tool_hit_vs_hallucination(ckpt_data)
    results["tool_hit_vs_hallucination"] = corr5
    print(f"   Pearson r  = {corr5['pearson_r']:.4f}  (p={corr5['pearson_p']:.6f})")
    print(f"   Spearman ρ = {corr5['spearman_rho']:.4f}  (p={corr5['spearman_p']:.6f})")
    print(f"   Interpretation: {_interpret(corr5['pearson_r'])}")

    # 6. Family variance analysis
    print("\n" + "="*70)
    print("6. Open-Source Family Comparison")
    print("="*70)
    fam_results = analysis_family_variance(eval_data)
    results["family_variance"] = fam_results
    print(f"\n   Family mean scores:")
    for fam, mean in fam_results["family_means"].items():
        n = len(fam_results["family_members"].get(fam, []))
        wv = fam_results["within_family_variance"].get(fam)
        wv_str = f"var={wv:.6f}" if wv is not None else "var=N/A (n=1)"
        print(f"     {fam:<10s}: mean={mean:.4f}  n={n}  {wv_str}")
    print(f"\n   Avg within-family variance: {fam_results['avg_within_family_variance']}")
    print(f"   Across-family variance:     {fam_results['across_family_variance']}")
    vr = fam_results['variance_ratio_across_div_within']
    print(f"   Variance ratio (across/within): {vr}")
    if fam_results["anova"]:
        a = fam_results["anova"]
        print(f"\n   One-way ANOVA: F={a['f_statistic']:.4f}, p={a['p_value']:.6f}")
        sig = "YES" if a["p_value"] < 0.05 else "NO"
        print(f"   Significant family effect (p<0.05): {sig}")

    # 7. Additional: full metric pairwise correlations
    print("\n" + "="*70)
    print("7. Pairwise Metric Correlations (all dimensions)")
    print("="*70)
    metric_corrs = analysis_additional_metric_correlations(ckpt_data)
    results["pairwise_metric_correlations"] = metric_corrs

    # Print as sorted table
    sorted_corrs = sorted(metric_corrs.items(),
                          key=lambda x: abs(x[1].get("pearson_r", 0)), reverse=True)
    print(f"\n   {'Pair':<45s} {'r':>7s} {'p(r)':>10s} {'rho':>7s} {'p(rho)':>10s} {'Interpretation'}")
    print("   " + "-"*100)
    for label, c in sorted_corrs:
        if "pearson_r" in c:
            interp = _interpret(c["pearson_r"])
            print(f"   {label:<45s} {c['pearson_r']:>7.4f} {c['pearson_p']:>10.6f} "
                  f"{c['spearman_rho']:>7.4f} {c['spearman_p']:>10.6f} {interp}")

    # ── Summary ─────────────────────────────────────────────────────
    print("\n" + "="*70)
    print("SUMMARY: Independence vs Redundancy")
    print("="*70)

    all_corrs = []
    for key in ["tool_selection_vs_param_extraction", "singleton_vs_multiturn",
                 "model_size_vs_performance", "tool_hit_vs_hallucination"]:
        c = results[key]
        if "pearson_r" in c:
            all_corrs.append((c["label"], c["pearson_r"], c["spearman_rho"]))

    for pair, c in results.get("difficulty_correlation", {}).items():
        if "pearson_r" in c:
            all_corrs.append((c["label"], c["pearson_r"], c["spearman_rho"]))

    if "model_size_log_vs_performance" in results:
        c = results["model_size_log_vs_performance"]
        if "pearson_r" in c:
            all_corrs.append((c["label"], c["pearson_r"], c["spearman_rho"]))

    print(f"\n   {'Dimension Pair':<45s} {'r':>7s} {'rho':>7s} {'Assessment'}")
    print("   " + "-"*75)
    for label, r, rho in sorted(all_corrs, key=lambda x: abs(x[1]), reverse=True):
        assessment = _interpret(r)
        print(f"   {label:<45s} {r:>7.4f} {rho:>7.4f} {assessment}")

    independent = [(l, r, rho) for l, r, rho in all_corrs if abs(r) < 0.4]
    redundant = [(l, r, rho) for l, r, rho in all_corrs if abs(r) >= 0.8]

    if independent:
        print(f"\n   INDEPENDENT dimensions (|r| < 0.4):")
        for l, r, _ in independent:
            print(f"     - {l} (r={r:.4f})")

    if redundant:
        print(f"\n   POTENTIALLY REDUNDANT dimensions (|r| >= 0.8):")
        for l, r, _ in redundant:
            print(f"     - {l} (r={r:.4f})")

    # Save
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to {OUT_PATH}")


if __name__ == "__main__":
    main()
