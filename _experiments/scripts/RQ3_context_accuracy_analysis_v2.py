#!/usr/bin/env python3
"""RQ3 (corrected): context-accuracy vs scenario-completion partial correlation.

Fixes three issues in RQ3_context_accuracy_analysis.py that made its output
(context_accuracy_correlation.json) inconsistent with the paper:

1. COHORT. The old script globbed every multiturn_*.json with no filtering, so it
   silently included the redundant `kanana-2-30b-a3b-instruct-2601` (dropped in
   every other analysis: reg_vs_analysis, fig4 scatter, Fig 5 turnwise) and could
   omit `kanana-2-30b-a3b-thinking-2601` (= Kanana-2-Think, the multi-turn
   completion leader, which IS in the paper's Table VI). Here we pin the canonical
   28-model cohort explicitly (identical to Table VI).

2. CONTROL VARIABLE. The old "partial" controlled for `avg_tool_hit` = the
   MULTI-turn per-turn hit (h-bar), but the paper text states the control is the
   SINGLE-turn tool hit h. We control for single-turn h (results_kr
   overall.primary_tool_hit_rate, the Table VI h column) as the paper states, and
   also report the multi-turn-h-bar control for transparency.

3. PARTIAL METHOD. The old code mixed a linear (np.polyfit) residualization with a
   Spearman on the residuals. Here we use a proper rank-based partial Spearman:
   rank all three variables, then take the first-order partial Pearson on the ranks.
   Significance is the standard partial-correlation t-test, t = r*sqrt((n-3)/(1-r^2)),
   df = n-3, two-sided.

Join keys: multiturn uses norm(model_id) (keeps __think/__nothink); single-turn uses
norm(model); norm(s) = s.replace('/','_').replace('.','_').

Output: _experiments/results_RQ3/context_accuracy_correlation_v2.json (+ _v2 CSV).
Does NOT overwrite the original files.

Usage: PYTHONPATH=. python _experiments/scripts/RQ3_context_accuracy_analysis_v2.py
"""
import json
import csv
import glob
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr, rankdata

SB = Path(__file__).resolve().parents[2]
MT_DIR = SB / "_experiments" / "results_mt" / "eval"
KR_DIR = SB / "_experiments" / "results_kr" / "eval"
OUT_DIR = SB / "_experiments" / "results_RQ3"

# Canonical 28-model cohort (identical to Table VI). Toggle models are two entries.
COHORT = [
    "skt/A.X-4.0-Light", "skt/A.X-4.0",
    "LGAI-EXAONE/EXAONE-4.0-1.2B", "LGAI-EXAONE/EXAONE-4.0-32B",
    "kakaocorp/kanana-2-30b-a3b-instruct", "kakaocorp/kanana-2-30b-a3b-thinking-2601",
    "DragonLLM/Llama-Open-Finance-8B", "DragonLLM/Qwen-Open-Finance-R-8B",
    "openai/gpt-oss-20b__nothink", "openai/gpt-oss-20b__think",
    "openai/gpt-oss-120b__nothink", "openai/gpt-oss-120b__think",
    "meta-llama/Llama-3.2-3B-Instruct", "meta-llama/Llama-3.3-70B-Instruct",
    "NousResearch/Hermes-3-Llama-3.1-8B",
    "mistralai/Ministral-3-3B-Instruct-2512",
    "mistralai/Mistral-Small-3.2-24B-Instruct-2506", "microsoft/Phi-4-mini-instruct",
    "Qwen/Qwen3.5-4B__nothink", "Qwen/Qwen3.5-4B__think",
    "Qwen/Qwen3.5-27B__nothink", "Qwen/Qwen3.5-27B__think",
    "Qwen/Qwen3.6-27B", "Qwen/Qwen3.6-35B-A3B",
    "Salesforce/xLAM-2-3b-fc-r", "Salesforce/Llama-xLAM-2-70b-fc-r",
    "google/gemma-4-E4B-it", "google/gemma-4-31B-it",
]


def norm(s):
    return (s or "").replace("/", "_").replace(".", "_")


def partial_spearman(x, y, z):
    """First-order partial Spearman of (x, y) controlling z: rank then partial Pearson."""
    rx, ry, rz = rankdata(x), rankdata(y), rankdata(z)

    def pear(a, b):
        a, b = np.asarray(a, float), np.asarray(b, float)
        a, b = a - a.mean(), b - b.mean()
        return float((a * b).sum() / (np.sqrt((a * a).sum()) * np.sqrt((b * b).sum())))

    r_xy, r_xz, r_yz = pear(rx, ry), pear(rx, rz), pear(ry, rz)
    pr = (r_xy - r_xz * r_yz) / (np.sqrt(1 - r_xz**2) * np.sqrt(1 - r_yz**2))
    n = len(x)
    # partial-correlation t-test, df = n - 3 (one controlled variable)
    from scipy.stats import t as tdist
    tstat = pr * np.sqrt((n - 3) / (1 - pr**2))
    p = 2 * tdist.sf(abs(tstat), df=n - 3)
    return float(pr), float(p), r_xy


def main():
    # index multiturn by norm(model_id); single-turn h by norm(model)
    mt = {}
    for f in glob.glob(str(MT_DIR / "multiturn_*.json")):
        d = json.load(open(f))
        mt[norm(d.get("model_id") or d.get("model"))] = d
    kr_h = {}
    for f in glob.glob(str(KR_DIR / "eval_*.json")):
        d = json.load(open(f))
        ov = d.get("overall", {})
        h = ov.get("primary_tool_hit_rate")
        if h is None:
            cats = d.get("by_category", {})
            hs = [c["aggregated"]["primary_tool_hit_rate"] for c in cats.values() if "aggregated" in c]
            h = sum(hs) / len(hs) if hs else None
        kr_h[norm(d.get("model"))] = h

    rows, missing = [], []
    for m in COHORT:
        k = norm(m)
        md = mt.get(k)
        h = kr_h.get(k)
        if md is None or h is None:
            missing.append((m, md is None, h is None))
            continue
        ov = md.get("overall", {})
        ctx = ov.get("context_accuracy")
        comp = ov.get("scenario_complete_rate")
        hbar = ov.get("avg_tool_hit")
        if ctx is None or comp is None:
            missing.append((m, "no ctx/comp", False))
            continue
        rows.append({"model": m, "ctx_acc": ctx, "completion": comp,
                     "single_h": h, "multi_hbar": hbar})

    n = len(rows)
    ctx = [r["ctx_acc"] for r in rows]
    comp = [r["completion"] for r in rows]
    sh = [r["single_h"] for r in rows]
    hb = [r["multi_hbar"] for r in rows]

    rho_cc, p_cc = spearmanr(ctx, comp)
    rho_ch, p_ch = spearmanr(ctx, sh)          # ctx vs single-turn h
    pr_sh, pp_sh, _ = partial_spearman(ctx, comp, sh)   # control single-turn h (paper's stated control)
    pr_hb, pp_hb, _ = partial_spearman(ctx, comp, hb)   # control multi-turn h-bar (old file's control)

    summary = {
        "cohort": "canonical 28 (Table VI): incl. kanana-thinking-2601, excl. kanana-instruct-2601",
        "n_models": n,
        "spearman_ctx_vs_completion": {"rho": round(rho_cc, 4), "p": round(float(p_cc), 4)},
        "spearman_ctx_vs_single_turn_h": {"rho": round(rho_ch, 4), "p": round(float(p_ch), 4)},
        "partial_spearman_ctx_completion_given_SINGLE_turn_h": {
            "rho": round(pr_sh, 4), "p": round(pp_sh, 4),
            "note": "paper-stated control variable (single-turn tool hit h, Table VI column)"},
        "partial_spearman_ctx_completion_given_MULTI_turn_hbar": {
            "rho": round(pr_hb, 4), "p": round(pp_hb, 4),
            "note": "old context_accuracy_correlation.json control (avg_tool_hit)"},
        "missing": missing,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json.dump(summary, open(OUT_DIR / "context_accuracy_correlation_v2.json", "w"),
              ensure_ascii=False, indent=2)
    with open(OUT_DIR / "context_accuracy_per_model_v2.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["model", "ctx_acc", "completion", "single_h", "multi_hbar"])
        w.writeheader()
        w.writerows(rows)

    print(f"[RQ3-v2] canonical cohort n={n} (missing {len(missing)})")
    for m in missing:
        print("   missing:", m)
    print(f"  Spearman ctx~completion           = {rho_cc:.4f} (p={p_cc:.4f})")
    print(f"  Spearman ctx~single_turn_h        = {rho_ch:.4f} (p={p_ch:.4f})")
    print(f"  PARTIAL ctx~completion | single_h = {pr_sh:.4f} (p={pp_sh:.4f})   <- paper control; paper text says 0.197, p=0.304")
    print(f"  PARTIAL ctx~completion | multi_hbar = {pr_hb:.4f} (p={pp_hb:.4f}) <- old file control; old json says 0.408, p=0.031")


if __name__ == "__main__":
    main()
