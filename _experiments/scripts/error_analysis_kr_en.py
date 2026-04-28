"""Cross-lingual (KR vs EN) error analysis for AML-Bench.

Compares error patterns between Korean and English prompts across all models.
Output: _experiments/results/error_analysis_kr_en.json + printed summary.
"""

import json
import os
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
KR_DIR = ROOT / "_experiments" / "results" / "round1" / "checkpoint"
EN_DIR = ROOT / "_experiments" / "results" / "round1_en" / "checkpoint"
OUT_PATH = ROOT / "_experiments" / "results" / "error_analysis_kr_en.json"

EXCLUDE_ERRORS = {"api_error", "parse_fail"}


# ── Data loading ─────────────────────────────────────────────────────────
def load_checkpoints(directory: Path) -> pd.DataFrame:
    """Load all checkpoint JSONL files from a directory into a DataFrame.
    Dedup by keeping last entry per (model, case_id). Exclude api_error/parse_fail."""
    frames = []
    for p in sorted(directory.glob("checkpoint_*.jsonl")):
        records = []
        with open(p) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        if records:
            frames.append(pd.DataFrame(records))
    df = pd.concat(frames, ignore_index=True)
    # Dedup: keep last per (model, case_id)
    df = df.drop_duplicates(subset=["model", "case_id"], keep="last")
    # Exclude bad error types
    df = df[~df["error_type"].isin(EXCLUDE_ERRORS)].copy()
    return df


def short_model(name: str) -> str:
    """Shorten model name for display."""
    return name.split("/")[-1] if "/" in name else name


# ── Analysis functions ───────────────────────────────────────────────────

def analysis_1_per_model_delta(kr: pd.DataFrame, en: pd.DataFrame) -> dict:
    """Per-model KR vs EN score delta, decomposed into tool_hit and param_accuracy."""
    results = {}
    models = sorted(set(kr["model"]) & set(en["model"]))
    for m in models:
        k = kr[kr["model"] == m]
        e = en[en["model"] == m]
        # Align on case_id
        common = sorted(set(k["case_id"]) & set(e["case_id"]))
        if not common:
            continue
        kd = k.set_index("case_id").loc[common]
        ed = e.set_index("case_id").loc[common]

        score_kr = kd["score"].mean()
        score_en = ed["score"].mean()
        tool_hit_kr = kd["primary_tool_hit"].astype(float).mean()
        tool_hit_en = ed["primary_tool_hit"].astype(float).mean()
        param_kr = kd["param_accuracy"].mean()
        param_en = ed["param_accuracy"].mean()

        results[short_model(m)] = {
            "n_cases": len(common),
            "score_kr": round(score_kr, 4),
            "score_en": round(score_en, 4),
            "score_delta": round(score_kr - score_en, 4),
            "tool_hit_kr": round(tool_hit_kr, 4),
            "tool_hit_en": round(tool_hit_en, 4),
            "tool_hit_delta": round(tool_hit_kr - tool_hit_en, 4),
            "param_acc_kr": round(param_kr, 4),
            "param_acc_en": round(param_en, 4),
            "param_acc_delta": round(param_kr - param_en, 4),
        }
    return dict(sorted(results.items(), key=lambda x: x[1]["score_delta"], reverse=True))


def analysis_2_error_type_shift(kr: pd.DataFrame, en: pd.DataFrame) -> dict:
    """Per-model error_type distribution shift between KR and EN."""
    results = {}
    models = sorted(set(kr["model"]) & set(en["model"]))
    all_types = sorted(set(kr["error_type"]) | set(en["error_type"]))

    for m in models:
        k = kr[kr["model"] == m]
        e = en[en["model"] == m]
        kr_counts = Counter(k["error_type"])
        en_counts = Counter(e["error_type"])
        kr_total = len(k)
        en_total = len(e)

        dist = {}
        for t in all_types:
            kr_pct = round(kr_counts.get(t, 0) / kr_total * 100, 2) if kr_total else 0
            en_pct = round(en_counts.get(t, 0) / en_total * 100, 2) if en_total else 0
            dist[t] = {
                "kr_pct": kr_pct,
                "en_pct": en_pct,
                "delta_pp": round(kr_pct - en_pct, 2),
            }
        results[short_model(m)] = dist
    return results


def analysis_3_per_case_language_effect(kr: pd.DataFrame, en: pd.DataFrame) -> dict:
    """Per case_id, compute mean (KR_score - EN_score) across models."""
    # Merge on model+case_id
    merged = kr[["model", "case_id", "category", "score"]].merge(
        en[["model", "case_id", "score"]],
        on=["model", "case_id"],
        suffixes=("_kr", "_en"),
    )
    merged["delta"] = merged["score_kr"] - merged["score_en"]

    case_stats = merged.groupby(["case_id", "category"]).agg(
        mean_delta=("delta", "mean"),
        std_delta=("delta", "std"),
        n_models=("delta", "count"),
        kr_mean=("score_kr", "mean"),
        en_mean=("score_en", "mean"),
    ).reset_index()

    # Top 20 KR-advantaged and EN-advantaged cases
    case_stats = case_stats.sort_values("mean_delta")
    top_en = case_stats.head(20)  # EN better (most negative delta)
    top_kr = case_stats.tail(20).iloc[::-1]  # KR better (most positive delta)

    def rows_to_list(df):
        return [
            {
                "case_id": r["case_id"],
                "category": r["category"],
                "mean_delta": round(r["mean_delta"], 4),
                "std_delta": round(r["std_delta"], 4) if pd.notna(r["std_delta"]) else 0,
                "kr_mean": round(r["kr_mean"], 4),
                "en_mean": round(r["en_mean"], 4),
                "n_models": int(r["n_models"]),
            }
            for _, r in df.iterrows()
        ]

    return {
        "top_kr_advantaged": rows_to_list(top_kr),
        "top_en_advantaged": rows_to_list(top_en),
        "overall_mean_delta": round(case_stats["mean_delta"].mean(), 4),
        "cases_kr_better": int((case_stats["mean_delta"] > 0.01).sum()),
        "cases_en_better": int((case_stats["mean_delta"] < -0.01).sum()),
        "cases_neutral": int((case_stats["mean_delta"].abs() <= 0.01).sum()),
    }


def analysis_4_category_sensitivity(kr: pd.DataFrame, en: pd.DataFrame) -> dict:
    """Category-level language sensitivity."""
    merged = kr[["model", "case_id", "category", "score", "primary_tool_hit", "param_accuracy"]].merge(
        en[["model", "case_id", "score", "primary_tool_hit", "param_accuracy"]],
        on=["model", "case_id"],
        suffixes=("_kr", "_en"),
    )

    results = {}
    for cat, grp in merged.groupby("category"):
        n = len(grp)
        score_delta = grp["score_kr"].mean() - grp["score_en"].mean()
        tool_delta = grp["primary_tool_hit_kr"].astype(float).mean() - grp["primary_tool_hit_en"].astype(float).mean()
        param_delta = grp["param_accuracy_kr"].mean() - grp["param_accuracy_en"].mean()
        results[cat] = {
            "n_observations": n,
            "score_delta": round(score_delta, 4),
            "tool_hit_delta": round(tool_delta, 4),
            "param_acc_delta": round(param_delta, 4),
            "score_kr": round(grp["score_kr"].mean(), 4),
            "score_en": round(grp["score_en"].mean(), 4),
        }

    return dict(sorted(results.items(), key=lambda x: abs(x[1]["score_delta"]), reverse=True))


def _get_confusion_pairs(df: pd.DataFrame) -> Counter:
    """Extract (expected_tool, called_tool) confusion pairs from wrong_func errors."""
    pairs = Counter()
    wrong = df[df["error_type"] == "wrong_func"]
    for _, row in wrong.iterrows():
        expected = row["category"]
        called = row.get("called_tools", [])
        if isinstance(called, list) and called:
            for c in called:
                if c != expected:
                    pairs[(expected, c)] += 1
        else:
            pairs[(expected, "<none>")] += 1
    return pairs


def analysis_5_confusion_pairs(kr: pd.DataFrame, en: pd.DataFrame) -> dict:
    """Compare top confusion pairs KR vs EN."""
    kr_pairs = _get_confusion_pairs(kr)
    en_pairs = _get_confusion_pairs(en)

    all_pairs = set(kr_pairs.keys()) | set(en_pairs.keys())

    combined = []
    for p in all_pairs:
        kr_c = kr_pairs.get(p, 0)
        en_c = en_pairs.get(p, 0)
        combined.append({
            "expected": p[0],
            "called": p[1],
            "kr_count": kr_c,
            "en_count": en_c,
            "delta": kr_c - en_c,
        })

    # Sort by total frequency
    combined.sort(key=lambda x: x["kr_count"] + x["en_count"], reverse=True)

    top_overall = combined[:20]

    # Also find most language-dependent (largest absolute delta)
    most_language_dep = sorted(combined, key=lambda x: abs(x["delta"]), reverse=True)[:15]

    return {
        "top_20_by_frequency": top_overall,
        "top_15_by_language_delta": most_language_dep,
    }


def analysis_6_think_mode_interaction(kr: pd.DataFrame, en: pd.DataFrame) -> dict:
    """Think/nothink interaction with language."""
    # Find think/nothink pairs by model name
    kr_models = set(kr["model"].unique())
    en_models = set(en["model"].unique())
    common_models = kr_models & en_models

    pairs = {}
    for m in common_models:
        short = short_model(m)
        if "__think" in short:
            base = short.replace("__think", "")
            nothink_short = base + "__nothink"
            # Find the full model name for nothink
            for m2 in common_models:
                if short_model(m2) == nothink_short:
                    pairs[base] = (m, m2)  # (think_model, nothink_model)
                    break

    results = {}
    for base, (think_m, nothink_m) in sorted(pairs.items()):
        # KR think vs nothink
        kr_think = kr[kr["model"] == think_m]
        kr_nothink = kr[kr["model"] == nothink_m]
        en_think = en[en["model"] == think_m]
        en_nothink = en[en["model"] == nothink_m]

        # Align on common case_ids (should be all 1258 but be safe)
        common_cases = sorted(
            set(kr_think["case_id"]) & set(kr_nothink["case_id"])
            & set(en_think["case_id"]) & set(en_nothink["case_id"])
        )
        if not common_cases:
            continue

        def mean_score(df, cases):
            return df.set_index("case_id").loc[cases]["score"].mean()

        def mean_tool(df, cases):
            return df.set_index("case_id").loc[cases]["primary_tool_hit"].astype(float).mean()

        def mean_param(df, cases):
            return df.set_index("case_id").loc[cases]["param_accuracy"].mean()

        kr_think_score = mean_score(kr_think, common_cases)
        kr_nothink_score = mean_score(kr_nothink, common_cases)
        en_think_score = mean_score(en_think, common_cases)
        en_nothink_score = mean_score(en_nothink, common_cases)

        think_effect_kr = kr_think_score - kr_nothink_score
        think_effect_en = en_think_score - en_nothink_score

        results[base] = {
            "n_cases": len(common_cases),
            "kr_think_score": round(kr_think_score, 4),
            "kr_nothink_score": round(kr_nothink_score, 4),
            "think_effect_kr": round(think_effect_kr, 4),
            "en_think_score": round(en_think_score, 4),
            "en_nothink_score": round(en_nothink_score, 4),
            "think_effect_en": round(think_effect_en, 4),
            "interaction": round(think_effect_kr - think_effect_en, 4),
            "kr_advantage_think": round(kr_think_score - en_think_score, 4),
            "kr_advantage_nothink": round(kr_nothink_score - en_nothink_score, 4),
        }
    return results


# ── Summary printing ─────────────────────────────────────────────────────

def print_summary(output: dict):
    sep = "=" * 80

    # 1. Per-model delta
    print(f"\n{sep}")
    print("1. PER-MODEL KR vs EN SCORE DELTA (decomposed)")
    print(sep)
    a1 = output["per_model_delta"]
    print(f"{'Model':<45} {'Score_D':>8} {'ToolHit_D':>10} {'Param_D':>9}")
    print("-" * 75)
    for m, v in a1.items():
        print(f"{m:<45} {v['score_delta']:>+8.4f} {v['tool_hit_delta']:>+10.4f} {v['param_acc_delta']:>+9.4f}")

    # Aggregate: is the KR advantage more from tool or param?
    deltas = list(a1.values())
    avg_score = np.mean([d["score_delta"] for d in deltas])
    avg_tool = np.mean([d["tool_hit_delta"] for d in deltas])
    avg_param = np.mean([d["param_acc_delta"] for d in deltas])
    print(f"\n  Average across models: score={avg_score:+.4f}, tool_hit={avg_tool:+.4f}, param_acc={avg_param:+.4f}")
    if abs(avg_tool) > abs(avg_param):
        print("  >> KR advantage is primarily from TOOL SELECTION (not parameter extraction)")
    else:
        print("  >> KR advantage is primarily from PARAMETER EXTRACTION (not tool selection)")

    # 2. Error type shift
    print(f"\n{sep}")
    print("2. ERROR TYPE SHIFT (KR vs EN, selected models)")
    print(sep)
    a2 = output["error_type_shift"]
    # Show aggregate across all models
    all_types = set()
    for v in a2.values():
        all_types |= set(v.keys())
    all_types = sorted(all_types)

    print(f"{'Error Type':<20} {'KR_avg%':>8} {'EN_avg%':>8} {'Delta_pp':>9}")
    print("-" * 48)
    for t in all_types:
        kr_vals = [a2[m][t]["kr_pct"] for m in a2 if t in a2[m]]
        en_vals = [a2[m][t]["en_pct"] for m in a2 if t in a2[m]]
        kr_avg = np.mean(kr_vals) if kr_vals else 0
        en_avg = np.mean(en_vals) if en_vals else 0
        print(f"{t:<20} {kr_avg:>8.2f} {en_avg:>8.2f} {kr_avg - en_avg:>+9.2f}")

    # Models with largest wrong_func shift
    print("\n  Models with largest wrong_func shift (EN - KR):")
    wf_shifts = [(m, v.get("wrong_func", {}).get("delta_pp", 0)) for m, v in a2.items()]
    wf_shifts.sort(key=lambda x: x[1])
    for m, d in wf_shifts[:5]:
        print(f"    {m:<45} KR-EN delta: {d:+.2f}pp")

    # 3. Per-case effect
    print(f"\n{sep}")
    print("3. PER-CASE LANGUAGE EFFECT")
    print(sep)
    a3 = output["per_case_language_effect"]
    print(f"  Overall mean delta (KR-EN): {a3['overall_mean_delta']:+.4f}")
    print(f"  Cases KR better (delta>0.01): {a3['cases_kr_better']}")
    print(f"  Cases EN better (delta<-0.01): {a3['cases_en_better']}")
    print(f"  Cases neutral: {a3['cases_neutral']}")

    print("\n  Top 10 KR-advantaged cases:")
    print(f"  {'case_id':<15} {'category':<35} {'delta':>7} {'KR':>6} {'EN':>6}")
    for c in a3["top_kr_advantaged"][:10]:
        print(f"  {c['case_id']:<15} {c['category']:<35} {c['mean_delta']:>+7.4f} {c['kr_mean']:>6.3f} {c['en_mean']:>6.3f}")

    print("\n  Top 10 EN-advantaged cases:")
    for c in a3["top_en_advantaged"][:10]:
        print(f"  {c['case_id']:<15} {c['category']:<35} {c['mean_delta']:>+7.4f} {c['kr_mean']:>6.3f} {c['en_mean']:>6.3f}")

    # 4. Category sensitivity
    print(f"\n{sep}")
    print("4. CATEGORY-LEVEL LANGUAGE SENSITIVITY (sorted by |score_delta|)")
    print(sep)
    a4 = output["category_sensitivity"]
    print(f"{'Category':<35} {'Score_D':>8} {'ToolHit_D':>10} {'Param_D':>9} {'KR':>6} {'EN':>6}")
    print("-" * 80)
    for cat, v in a4.items():
        print(f"{cat:<35} {v['score_delta']:>+8.4f} {v['tool_hit_delta']:>+10.4f} {v['param_acc_delta']:>+9.4f} {v['score_kr']:>6.3f} {v['score_en']:>6.3f}")

    # 5. Confusion pairs
    print(f"\n{sep}")
    print("5. CONFUSION PAIRS (top 15 by frequency)")
    print(sep)
    a5 = output["confusion_pairs"]
    print(f"{'Expected':<35} {'Called':<35} {'KR':>5} {'EN':>5} {'D':>5}")
    print("-" * 88)
    for p in a5["top_20_by_frequency"][:15]:
        print(f"{p['expected']:<35} {p['called']:<35} {p['kr_count']:>5} {p['en_count']:>5} {p['delta']:>+5}")

    print("\n  Most language-dependent confusion pairs (top 10):")
    for p in a5["top_15_by_language_delta"][:10]:
        label = "KR>EN" if p["delta"] > 0 else "EN>KR"
        print(f"    {p['expected']} -> {p['called']}: KR={p['kr_count']}, EN={p['en_count']} ({label}, |d|={abs(p['delta'])})")

    # 6. Think mode interaction
    print(f"\n{sep}")
    print("6. THINK MODE x LANGUAGE INTERACTION")
    print(sep)
    a6 = output["think_mode_interaction"]
    if not a6:
        print("  No think/nothink paired models found.")
    else:
        print(f"{'Model':<40} {'ThinkEff_KR':>12} {'ThinkEff_EN':>12} {'Interact':>9} {'KRadv_T':>8} {'KRadv_NT':>9}")
        print("-" * 95)
        for m, v in a6.items():
            print(f"{m:<40} {v['think_effect_kr']:>+12.4f} {v['think_effect_en']:>+12.4f} {v['interaction']:>+9.4f} {v['kr_advantage_think']:>+8.4f} {v['kr_advantage_nothink']:>+9.4f}")

        # Summary
        interactions = [v["interaction"] for v in a6.values()]
        avg_inter = np.mean(interactions)
        print(f"\n  Average interaction (think_effect_KR - think_effect_EN): {avg_inter:+.4f}")
        if avg_inter > 0.005:
            print("  >> Think mode helps MORE in Korean than in English")
        elif avg_inter < -0.005:
            print("  >> Think mode helps MORE in English than in Korean")
        else:
            print("  >> Think mode effect is similar across languages")

    print(f"\n{sep}")
    print(f"Results saved to: {OUT_PATH}")
    print(sep)


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    print("Loading KR checkpoints...")
    kr = load_checkpoints(KR_DIR)
    print(f"  KR: {len(kr)} records, {kr['model'].nunique()} models")

    print("Loading EN checkpoints...")
    en = load_checkpoints(EN_DIR)
    print(f"  EN: {len(en)} records, {en['model'].nunique()} models")

    common_models = sorted(set(kr["model"]) & set(en["model"]))
    print(f"  Common models: {len(common_models)}")

    # Filter to common models only
    kr = kr[kr["model"].isin(common_models)].copy()
    en = en[en["model"].isin(common_models)].copy()

    print("\nRunning analyses...")

    output = {}

    print("  1/6 Per-model delta decomposition...")
    output["per_model_delta"] = analysis_1_per_model_delta(kr, en)

    print("  2/6 Error type shift...")
    output["error_type_shift"] = analysis_2_error_type_shift(kr, en)

    print("  3/6 Per-case language effect...")
    output["per_case_language_effect"] = analysis_3_per_case_language_effect(kr, en)

    print("  4/6 Category sensitivity...")
    output["category_sensitivity"] = analysis_4_category_sensitivity(kr, en)

    print("  5/6 Confusion pairs...")
    output["confusion_pairs"] = analysis_5_confusion_pairs(kr, en)

    print("  6/6 Think mode interaction...")
    output["think_mode_interaction"] = analysis_6_think_mode_interaction(kr, en)

    # Save JSON
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print_summary(output)


if __name__ == "__main__":
    main()
