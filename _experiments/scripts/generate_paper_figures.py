"""논문용 Figure 생성 스크립트.

54개 모델을 논문에 적합한 형태로 시각화.
- Fig 1: 상위 20개 모델 종합 성능 (수평 막대)
- Fig 2: 도구정확도 vs 파라미터정확도 scatter (전체 모델, 계열별 색상)
- Fig 3: Think vs NoThink 비교 (paired bar)
- Fig 4: KR vs EN delta (상위 20개 모델)
- Fig 5: 카테고리별 난이도 히트맵 (상위 10개 모델)
- Fig 6: 모델 크기 vs 성능 scatter
"""

import json
import glob
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# === relocated to star-bench/_experiments/scripts/; figures saved to BOTH star-bench and paper ===
from pathlib import Path as _P
_SB = _P(__file__).resolve().parents[2]            # star-bench root
_WS = _SB.parent                                    # workspace root
SB_FIG = _SB / "_experiments" / "figures"
PAPER_FIG = _WS / "star-bench-paper" / "figures"
SB_FIG.mkdir(parents=True, exist_ok=True); PAPER_FIG.mkdir(parents=True, exist_ok=True)
import matplotlib.pyplot as _pltD
from matplotlib.figure import Figure as _FigD
__osf, __ofsf = _pltD.savefig, _FigD.savefig
def __dual_plt(fname, *a, **k):
    _n = _P(str(fname)).name
    __osf(str(SB_FIG / _n), *a, **k); __osf(str(PAPER_FIG / _n), *a, **k)
def __dual_fig(self, fname, *a, **k):
    _n = _P(str(fname)).name
    __ofsf(self, str(SB_FIG / _n), *a, **k); __ofsf(self, str(PAPER_FIG / _n), *a, **k)
_pltD.savefig = __dual_plt; _FigD.savefig = __dual_fig
# === end relocation header ===

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = _SB / "_experiments" / "results_kr"
RESULTS_EN_DIR = _SB / "_experiments" / "results_en"
FIGURES_DIR = _WS / "star-bench-paper" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# ── Color palette (dark theme style) ──
COLORS = {
    "Qwen": "#4E79A7",
    "Mistral": "#E15759",
    "Llama": "#59A14F",
    "xLAM": "#F28E2B",
    "EXAONE": "#B07AA1",
    "Kanana": "#76B7B2",
    "GLM": "#EDC948",
    "gpt-oss": "#FF9DA7",
    "skt": "#9C755F",
    "Gemma": "#F28E2B",
    "Finance": "#59A14F",
    "Other": "#BAB0AC",
}

SHORT_NAMES = {
    "Qwen/Qwen3.5-27B": "Qwen3.5-27B",
    "Qwen/Qwen3.5-9B": "Qwen3.5-9B",
    "Qwen/Qwen3.5-4B": "Qwen3.5-4B",
    "Qwen/Qwen3.5-2B": "Qwen3.5-2B",
    "Qwen/Qwen3.5-0.8B": "Qwen3.5-0.8B",
    "Qwen/Qwen3-30B-A3B-Thinking-2507": "Qwen3-30B-Think",
    "Qwen/Qwen3-30B-A3B-Instruct-2507": "Qwen3-30B",
    "Qwen/Qwen3-4B-Thinking-2507": "Qwen3-4B-Think",
    "Qwen/Qwen3-4B-Instruct-2507": "Qwen3-4B",
    "Qwen/Qwen3-8B": "Qwen3-8B",
    "Qwen/Qwen3-Coder-30B-A3B-Instruct": "Qwen3-Coder-30B",
    "Qwen/Qwen2.5-1.5B-Instruct": "Qwen2.5-1.5B",
    "Salesforce/xLAM-2-32b-fc-r": "xLAM-32B",
    "Salesforce/Llama-xLAM-2-8b-fc-r": "xLAM-8B",
    "Salesforce/xLAM-2-3b-fc-r": "xLAM-3B",
    "Salesforce/xLAM-2-1b-fc-r": "xLAM-1B",
    "Salesforce/Llama-xLAM-2-70b-fc-r": "xLAM-70B",
    "mistralai/Mistral-Small-3.2-24B-Instruct-2506": "Mistral-Small-24B",
    "mistralai/Ministral-3-14B-Instruct-2512": "Ministral-14B",
    "mistralai/Ministral-3-8B-Instruct-2512": "Ministral-8B",
    "mistralai/Ministral-3-3B-Instruct-2512": "Ministral-3B",
    "mistralai/Mistral-Nemo-Instruct-2407": "Mistral-Nemo-12B",
    "meta-llama/Llama-3.3-70B-Instruct": "Llama-3.3-70B",
    "meta-llama/Llama-3.1-8B-Instruct": "Llama-3.1-8B",
    "meta-llama/Llama-3.2-3B-Instruct": "Llama-3.2-3B",
    "meta-llama/Llama-3.2-1B-Instruct": "Llama-3.2-1B",
    "meta-llama/Llama-4-Scout-17B-16E-Instruct": "Llama-4-Scout-17B",
    "LGAI-EXAONE/EXAONE-4.0-32B": "EXAONE-4.0-32B",
    "LGAI-EXAONE/EXAONE-4.0-1.2B": "EXAONE-4.0-1.2B",
    "google/gemma-4-31B-it": "Gemma-4-31B",
    "google/gemma-4-E4B-it": "Gemma-4-E4B",
    "DragonLLM/Llama-Open-Finance-8B": "Llama-Finance-8B",
    "DragonLLM/Qwen-Open-Finance-R-8B": "Qwen-Finance-R-8B",
    "NousResearch/Hermes-3-Llama-3.1-8B": "Hermes-3-8B",
    "microsoft/Phi-4-mini-instruct": "Phi-4-mini",
    "kakaocorp/kanana-2-30b-a3b-instruct": "Kanana-2-30B",
    "kakaocorp/kanana-2-30b-a3b-thinking-2601": "Kanana-2-Think",
    "kakaocorp/kanana-1.5-15.7b-a3b-instruct": "Kanana-1.5-15.7B",
    "kakaocorp/kanana-1.5-8b-instruct-2505": "Kanana-1.5-8B",
    "kakaocorp/kanana-1.5-2.1b-instruct-2505": "Kanana-1.5-2.1B",
    "zai-org/GLM-4.7-Flash": "GLM-4.7-Flash",
    "openai/gpt-oss-20b": "gpt-oss-20B",
    "skt/A.X-4.0": "A.X-4.0-72B",
    "skt/A.X-4.0-Light": "A.X-Light-7B",
    "NousResearch/Hermes-3-Llama-3.1-8B": "Hermes-3-8B",
    "allenai/OLMo-3-7B-Instruct": "OLMo-3-7B",
    "ibm-granite/granite-3.2-8b-instruct": "Granite-3.2-8B",
    "CohereForAI/c4ai-command-r7b-12-2024": "Command-R-7B",
    "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B": "DeepSeek-R1-8B",
    "gpt-4o-mini": "gpt-4o-mini",
    "claude-haiku-4-5-20251001": "Claude-Haiku-4.5",
}


def get_short_name(model):
    base = model.replace("__think", "").replace("__nothink", "")
    short = SHORT_NAMES.get(base, base.split("/")[-1])
    if "__think" in model:
        short += " (T)"
    elif "__nothink" in model:
        short += " (NT)"
    return short


def get_family(model):
    m = model.lower()
    if "dragonllm" in m or "open-finance" in m:
        return "Finance"
    if "gemma" in m:
        return "Gemma"
    if "hermes" in m or "phi" in m:
        return "Other"
    for key in ["Qwen", "Mistral", "Ministral", "Llama", "xLAM", "EXAONE", "Kanana", "kanana", "GLM", "gpt-oss", "skt", "A.X"]:
        if key.lower() in m:
            if key in ("Ministral",):
                return "Mistral"
            if key in ("kanana",):
                return "Kanana"
            if key in ("A.X",):
                return "skt"
            return key
    return "Other"


def get_color(model):
    return COLORS.get(get_family(model), COLORS["Other"])


def load_evals(eval_dir):
    results = {}
    for f in sorted(glob.glob(str(eval_dir / "eval" / "eval_*.json"))):
        with open(f) as fp:
            d = json.load(fp)
        results[d["model"]] = d
    return results


def fig1_top20_bar(kr_data):
    """상위 10 / 하위 10 모델 종합 성능 — 개별 파일 2개."""
    all_sorted = sorted(kr_data.items(), key=lambda x: x[1]["overall"]["primary_tool_hit_rate"], reverse=True)
    top10 = all_sorted[:10]
    bot10 = all_sorted[-10:]

    for group, fname, ylim in [
        (top10, "fig1a_top10.png", (0.88, 0.96)),
        (bot10, "fig1b_bottom10.png", (0.45, 0.85)),
    ]:
        fig, ax = plt.subplots(figsize=(5, 2.8))
        models = [get_short_name(m) for m, _ in group]
        scores = [d["overall"]["primary_tool_hit_rate"] for _, d in group]
        tools = [d["overall"]["primary_tool_hit_rate"] for _, d in group]
        colors = [get_color(m) for m, _ in group]

        x = np.arange(len(models))
        ax.bar(x, scores, color=colors, alpha=0.85, width=0.65)
        ax.scatter(x, tools, color="white", edgecolor="black", s=18, zorder=5, label="Tool Acc.")
        ax.set_xticks(x)
        ax.set_xticklabels(models, fontsize=10, rotation=45, ha="right")
        ax.set_ylabel("Tool Hit $h$", fontsize=11)
        ax.set_ylim(*ylim)
        ax.legend(loc="lower left", fontsize=9)
        plt.tight_layout()
        plt.savefig(FIGURES_DIR / fname, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"  Saved: {fname}")


def fig2_tool_vs_param(kr_data):
    """도구정확도 vs 파라미터정확도 scatter + 상위 밀집 구간 inset 확대."""
    fig, ax = plt.subplots(figsize=(5, 4))

    # Collect all points
    points = []
    for model, d in kr_data.items():
        o = d["overall"]
        if o["primary_tool_hit_rate"] < 0.01:
            continue
        x = o["primary_tool_hit_rate"]
        y = o["avg_param_accuracy"]
        points.append((model, x, y, o["primary_tool_hit_rate"]))
        ax.scatter(x, y, c=get_color(model), s=40, alpha=0.75, edgecolors="white", linewidths=0.3, zorder=3)

    # Legend
    for fam, color in COLORS.items():
        if fam != "Other":
            ax.scatter([], [], c=color, s=40, label=fam)
    ax.legend(fontsize=8, ncol=2, loc="lower right", framealpha=0.9)

    # Label bottom 3 only (outliers)
    points.sort(key=lambda p: p[3], reverse=True)
    for model, x, y, s in points[-3:]:
        name = get_short_name(model)
        ax.annotate(name, (x, y), fontsize=8, ha="left", va="bottom",
                    xytext=(3, 3), textcoords="offset points",
                    bbox=dict(boxstyle="round,pad=0.1", facecolor="white", alpha=0.8, edgecolor="none"))

    ax.plot([0, 1], [0, 1], "k--", alpha=0.15, linewidth=0.5)
    ax.set_xlabel("Tool Selection Accuracy", fontsize=13)
    ax.set_ylabel("Parameter Accuracy", fontsize=13)
    ax.tick_params(labelsize=12)
    ax.set_xlim(0.1, 1.02)
    ax.set_ylim(0.2, 1.02)

    # Inset: zoom into dense upper-right region
    from mpl_toolkits.axes_grid1.inset_locator import inset_axes, mark_inset
    axins = inset_axes(ax, width="45%", height="45%", loc="upper left",
                       bbox_to_anchor=(0.05, 0.0, 1, 1), bbox_transform=ax.transAxes)
    for model, x, y, s in points:
        axins.scatter(x, y, c=get_color(model), s=25, alpha=0.75, edgecolors="white", linewidths=0.3)
    # Label top 5 in inset
    for model, x, y, s in points[:5]:
        name = get_short_name(model)
        axins.annotate(name, (x, y), fontsize=7, ha="left", va="bottom",
                       xytext=(2, 2), textcoords="offset points",
                       bbox=dict(boxstyle="round,pad=0.1", facecolor="white", alpha=0.8, edgecolor="none"))
    axins.set_xlim(0.85, 0.97)
    axins.set_ylim(0.85, 0.97)
    axins.tick_params(labelsize=8)
    axins.plot([0, 1], [0, 1], "k--", alpha=0.15, linewidth=0.5)
    mark_inset(ax, axins, loc1=2, loc2=4, fc="none", ec="0.5", linewidth=0.5)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig2_tool_vs_param.png", dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved: fig2_tool_vs_param.png (with inset zoom)")


def fig3_think_nothink(kr_data):
    """Think vs NoThink paired bar."""
    pairs = {}
    for m, d in kr_data.items():
        base = m.replace("__think", "").replace("__nothink", "")
        if base == m:
            continue
        if base not in pairs:
            pairs[base] = {}
        if "__think" in m:
            pairs[base]["think"] = d["overall"]["primary_tool_hit_rate"]
        else:
            pairs[base]["nothink"] = d["overall"]["primary_tool_hit_rate"]

    complete = {b: v for b, v in pairs.items() if "think" in v and "nothink" in v}
    sorted_pairs = sorted(complete.items(), key=lambda x: x[1]["nothink"], reverse=True)

    fig, ax = plt.subplots(figsize=(8, 4))
    x = np.arange(len(sorted_pairs))
    w = 0.35
    nothink_vals = [v["nothink"] for _, v in sorted_pairs]
    think_vals = [v["think"] for _, v in sorted_pairs]
    names = [get_short_name(b) for b, _ in sorted_pairs]

    bars1 = ax.bar(x - w/2, nothink_vals, w, label="NoThink", color="#4E79A7", alpha=0.85)
    bars2 = ax.bar(x + w/2, think_vals, w, label="Think", color="#E15759", alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=10, rotation=30, ha="right")
    ax.set_ylabel("Tool Hit $h$", fontsize=13)
    ax.set_ylim(0.6, 1.0)
    ax.legend(fontsize=12)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig3_think_nothink.png", dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved: fig3_think_nothink.png")


def fig4_kr_en_delta(kr_data, en_data):
    """KR vs EN delta — 3-round valid aggregate(h>=0.2) 사용."""
    import re, os, statistics
    from collections import defaultdict

    def agg_rounds(dirs, metric='primary_tool_hit_rate', threshold=0.2):
        by = defaultdict(list)
        for d in dirs:
            for f in sorted(glob.glob(str(d / "eval" / "eval_*.json"))):
                base = os.path.basename(f)
                mm = re.match(r'eval_(.+?)_\d{8}_\d{6}\.json$', base)
                if not mm:
                    continue
                mid = mm.group(1)
                try:
                    with open(f) as fp:
                        dd = json.load(fp)
                except Exception:
                    continue
                ov = dd.get('overall', {})
                v = ov.get(metric)
                if v is None or v < threshold:
                    continue
                by[mid].append(v)
        return {m: statistics.mean(v) for m, v in by.items() if v}

    # KR/EN h: results_{kr,en}/eval/eval_*.json single-round 평균 (repro_mean_std.json 누락 대체)
    import re
    def _load_h_from_eval_dir(eval_dir):
        result = {}
        for f in sorted(glob.glob(str(eval_dir / "eval" / "eval_*.json"))):
            base = os.path.basename(f).replace('.json', '')
            m = re.match(r'eval_(.+?)_\d{8}_\d{6}$', base)
            if not m:
                continue
            fid = m.group(1)
            with open(f) as fp:
                d = json.load(fp)
            result[fid] = d['overall']['primary_tool_hit_rate']
        return result

    kr_h_agg = _load_h_from_eval_dir(RESULTS_DIR)
    en_h_agg = _load_h_from_eval_dir(RESULTS_EN_DIR)

    # Convert model IDs (file naming uses / but eval JSON model key uses /) to match kr_data
    # kr_data keys look like "Salesforce/Llama-xLAM-2-8b-fc-r" (with /)
    # our aggregation keys look like "Salesforce_Llama-xLAM-2-8b-fc-r" (with _)
    def to_fid(model_name):
        return model_name.replace('/', '_').replace('.', '_')

    deltas = []
    for m in kr_data:
        fid = to_fid(m)
        if fid in kr_h_agg and fid in en_h_agg:
            kr_s = kr_h_agg[fid]
            en_s = en_h_agg[fid]
            if kr_s > 0.3:
                deltas.append((m, kr_s, en_s, kr_s - en_s))

    deltas.sort(key=lambda x: x[3], reverse=True)

    # Scatter: KR vs EN h, all models in one panel (compact for wrapfigure)
    fig, ax = plt.subplots(figsize=(5, 4))
    kr_vals = [d[1] for d in deltas]
    en_vals = [d[2] for d in deltas]
    delta_vals = [d[3] for d in deltas]

    # Color by sign of delta
    colors = ["#1F4E79" if v >= 0 else "#5B8DBE" for v in delta_vals]
    ax.scatter(kr_vals, en_vals, c=colors, alpha=0.75, s=60, edgecolors="black", linewidths=0.5)

    # Diagonal y=x
    lo = min(min(kr_vals), min(en_vals)) - 0.05
    hi = max(max(kr_vals), max(en_vals)) + 0.05
    ax.plot([lo, hi], [lo, hi], "--", color="gray", linewidth=1, label="$h_{\\mathrm{KR}}=h_{\\mathrm{EN}}$")

    # Annotate notable outliers (top 4 KR-advantaged + top 3 EN-advantaged)
    annotate_set = deltas[:4] + deltas[-3:]
    for m, kr_s, en_s, _ in annotate_set:
        name = get_short_name(m)
        ax.annotate(name, (kr_s, en_s), fontsize=8,
                    xytext=(5, -2), textcoords="offset points",
                    color="#333")

    ax.set_xlabel("$h_{\\mathrm{KR}}$ (Korean query)", fontsize=11)
    ax.set_ylabel("$h_{\\mathrm{EN}}$ (English query)", fontsize=11)
    ax.tick_params(axis='both', labelsize=9)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)

    # Annotated regions
    ax.text(hi - 0.02, lo + 0.02, "KR-advantaged", fontsize=9,
            ha="right", va="bottom", color="#1F4E79", style="italic")
    ax.text(lo + 0.02, hi - 0.02, "EN-advantaged", fontsize=9,
            ha="left", va="top", color="#5B8DBE", style="italic")
    ax.legend(fontsize=9, loc="lower right")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig4_kr_en_scatter.png", dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved: fig4_kr_en_scatter.png")


def fig4b_2x2_interaction():
    """2x2 ablation interaction plot: query lang × tool schema lang."""
    # Mean h from 43 valid models (Appendix Table tab:2x2_ablation)
    kr_kr, en_kr, kr_en, en_en = 0.839, 0.772, 0.793, 0.802

    fig, ax = plt.subplots(figsize=(5, 4))
    x = [0, 1]
    xticks = ["KR tools", "EN tools"]

    # KR query line (KR-KR → KR-EN)
    ax.plot(x, [kr_kr, kr_en], "o-", color="#1F4E79", linewidth=2.2,
            markersize=10, label="Korean query",
            markeredgecolor="white", markeredgewidth=1.2, zorder=3)
    # EN query line (EN-KR → EN-EN)
    ax.plot(x, [en_kr, en_en], "s--", color="#5B8DBE", linewidth=2.2,
            markersize=10, label="English query",
            markeredgecolor="white", markeredgewidth=1.2, zorder=3)

    # Annotate values
    for xi, yi, txt in [(0, kr_kr, f"{kr_kr:.3f}"), (1, kr_en, f"{kr_en:.3f}"),
                        (0, en_kr, f"{en_kr:.3f}"), (1, en_en, f"{en_en:.3f}")]:
        ax.annotate(txt, (xi, yi), textcoords="offset points",
                    xytext=(8, -3), fontsize=9, color="#333")

    ax.set_xticks(x)
    ax.set_xticklabels(xticks, fontsize=11)
    ax.set_xlim(-0.25, 1.25)
    ax.set_ylim(0.74, 0.86)
    ax.set_xlabel("Tool schema language", fontsize=11)
    ax.set_ylabel("$h$ (mean across models)", fontsize=11)
    ax.tick_params(axis='y', labelsize=9)
    ax.legend(fontsize=10, loc="lower left")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig4_2x2_interaction.png", dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved: fig4_2x2_interaction.png")


def fig5_category_heatmap(kr_data):
    """카테고리별 히트맵 (상위 5 모델, 가로형: 모델=y축, 카테고리=x축). 컴팩트."""
    sorted_models = sorted(kr_data.items(), key=lambda x: x[1]["overall"]["primary_tool_hit_rate"], reverse=True)[:5]

    categories = sorted(kr_data[sorted_models[0][0]]["by_category"].keys())
    model_names = [get_short_name(m) for m, _ in sorted_models]

    # Short category names
    cat_short = {
        "analyze_channel_risk": "Ch.Risk",
        "analyze_cross_institution_flow": "Cr.Inst",
        "analyze_network": "Network",
        "compare_periods": "CmpPrd",
        "detect_aml_patterns": "AMLPat",
        "detect_ctr_candidates": "CTR",
        "detect_dormant_reactivation": "Dormnt",
        "detect_monitoring_alerts": "MonAlt",
        "detect_smurfing_network": "Smurf",
        "generate_str": "GenSTR",
        "get_account_profile": "AcctPf",
        "get_aml_glossary": "Gloss.",
        "get_fraud_type_summary": "FrdSum",
        "get_institution_report": "InstRp",
        "get_receiving_account_profile": "RcvPf",
        "get_statistics": "Stats",
        "get_trend_analysis": "Trend",
        "lookup_fiu_reference_types": "FIURef",
        "missing_parameters": "MissP.",
        "multi_tool": "Multi",
        "predict_fraud": "PrdFrd",
        "query_transactions": "QryTxn",
        "rank_risky_transactions": "RskRnk",
        "score_account_risk": "AccRsk",
        "validate_str_fields": "ValSTR",
    }
    cat_labels = [cat_short.get(c, c) for c in categories]

    # Sort categories by mean h across top-5 models (ascending: hardest on top)
    cat_means = []
    for cat in categories:
        vals = []
        for _, d in sorted_models:
            cat_data = d["by_category"].get(cat, {})
            agg = cat_data.get("aggregated", cat_data)
            vals.append(agg.get("primary_tool_hit_rate", 0))
        cat_means.append((cat, np.mean(vals)))
    cat_means.sort(key=lambda x: x[1])  # hardest first
    categories = [c for c, _ in cat_means]
    cat_labels = [cat_short.get(c, c) for c in categories]

    # data: categories=rows, models=cols (전치 portrait)
    data = []
    for cat in categories:
        row = []
        for _, d in sorted_models:
            cat_data = d["by_category"].get(cat, {})
            agg = cat_data.get("aggregated", cat_data)
            row.append(agg.get("primary_tool_hit_rate", 0))
        data.append(row)
    data = np.array(data)  # categories=rows, models=cols

    fig, ax = plt.subplots(figsize=(5, 7))
    im = ax.imshow(data, cmap="RdYlGn", aspect="auto", vmin=0.3, vmax=1.0)

    ax.set_yticks(np.arange(len(cat_labels)))
    ax.set_yticklabels(cat_labels, fontsize=9)
    ax.set_xticks(np.arange(len(model_names)))
    ax.set_xticklabels(model_names, fontsize=9, rotation=30, ha="right")
    ax.tick_params(top=True, bottom=False, labeltop=True, labelbottom=False)

    # cell scores
    for i in range(len(cat_labels)):
        for j in range(len(model_names)):
            val = data[i, j]
            color = "white" if val < 0.55 else "black"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=8, color=color)

    plt.colorbar(im, ax=ax, shrink=0.6, label="Tool Hit $h$", pad=0.03)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig5_category_heatmap.png", dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved: fig5_category_heatmap.png (24 cat x 5 models, portrait)")


def fig6_subdomain_radar(kr_data):
    """상위 5개 모델의 5개 하위 도메인별 성능 radar chart."""
    SUBDOMAIN = {
        "get_statistics": "Txn Inquiry", "query_transactions": "Txn Inquiry",
        "get_account_profile": "Txn Inquiry", "compare_periods": "Txn Inquiry",
        "get_fraud_type_summary": "Txn Inquiry", "get_institution_report": "Txn Inquiry",
        "get_receiving_account_profile": "Txn Inquiry",
        "predict_fraud": "Suspicious Detection", "rank_risky_transactions": "Suspicious Detection",
        "score_account_risk": "Suspicious Detection", "detect_monitoring_alerts": "Suspicious Detection",
        "analyze_network": "Money Flow & Network", "detect_aml_patterns": "Money Flow & Network",
        "detect_smurfing_network": "Money Flow & Network", "detect_dormant_reactivation": "Money Flow & Network",
        "get_trend_analysis": "Money Flow & Network", "analyze_channel_risk": "Money Flow & Network",
        "analyze_cross_institution_flow": "Money Flow & Network",
        "detect_ctr_candidates": "Regulatory Reporting", "lookup_fiu_reference_types": "Regulatory Reporting",
        "validate_str_fields": "Regulatory Reporting", "get_aml_glossary": "Regulatory Reporting",
        "generate_str": "Regulatory Reporting",
    }
    SUBDOMAINS = ["Txn Inquiry", "Suspicious Detection", "Money Flow & Network", "Regulatory Reporting"]

    # 대조 있는 5개 계열 대표 모델 선정 (top-5가 아닌 family diversity)
    preferred_fids = [
        "Qwen/Qwen3.5-27B",
        "mistralai/Ministral-3-14B-Instruct-2512",
        "Salesforce/xLAM-2-32b-fc-r",
        "kakaocorp/kanana-2-30b-a3b-thinking-2601",
        "meta-llama/Llama-3.3-70B-Instruct",
    ]
    sorted_models = []
    for pref in preferred_fids:
        matched = None
        for m in kr_data:
            if pref.lower() in m.lower() or m.lower() in pref.lower():
                matched = m
                break
        if matched:
            sorted_models.append((matched, kr_data[matched]))
    if len(sorted_models) < 5:
        used = {m for m, _ in sorted_models}
        remain = sorted(
            [(m, d) for m, d in kr_data.items() if m not in used],
            key=lambda x: x[1]["overall"]["primary_tool_hit_rate"], reverse=True
        )
        sorted_models.extend(remain[: 5 - len(sorted_models)])

    # Compute subdomain averages
    model_scores = {}
    for model, d in sorted_models:
        scores = {sd: [] for sd in SUBDOMAINS}
        for cat, cat_data in d["by_category"].items():
            sd = SUBDOMAIN.get(cat)
            if sd:
                agg = cat_data.get("aggregated", cat_data)
                scores[sd].append(agg.get("primary_tool_hit_rate", 0))
        model_scores[model] = [np.mean(scores[sd]) if scores[sd] else 0 for sd in SUBDOMAINS]

    # Radar plot
    angles = np.linspace(0, 2 * np.pi, len(SUBDOMAINS), endpoint=False).tolist()
    angles += angles[:1]  # close polygon

    fig, ax = plt.subplots(figsize=(5, 4), subplot_kw=dict(polar=True))

    radar_colors = ["#4E79A7", "#E15759", "#F28E2B", "#59A14F", "#B07AA1"]
    for i, (model, _) in enumerate(sorted_models):
        vals = model_scores[model] + model_scores[model][:1]
        ax.plot(angles, vals, "o-", linewidth=1.8, markersize=4, label=get_short_name(model),
                color=radar_colors[i], alpha=0.85)
        ax.fill(angles, vals, alpha=0.08, color=radar_colors[i])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(SUBDOMAINS, fontsize=12)
    ax.set_ylim(0.5, 1.0)
    ax.set_yticks([0.6, 0.7, 0.8, 0.9, 1.0])
    ax.set_yticklabels(["0.60", "0.70", "0.80", "0.90", "1.00"], fontsize=10, color="#888")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), fontsize=10, framealpha=0.9,
              ncol=3, columnspacing=1.0)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig6_subdomain_radar.png", dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved: fig6_subdomain_radar.png")


if __name__ == "__main__":
    print("Loading eval results...")
    kr_data = load_evals(RESULTS_DIR)
    en_data = load_evals(RESULTS_EN_DIR)
    print(f"  KR: {len(kr_data)} models, EN: {len(en_data)} models")

    print("\nGenerating figures...")
    fig1_top20_bar(kr_data)
    fig2_tool_vs_param(kr_data)
    fig3_think_nothink(kr_data)
    fig4_kr_en_delta(kr_data, en_data)
    fig4b_2x2_interaction()
    fig5_category_heatmap(kr_data)
    fig6_subdomain_radar(kr_data)
    print("\nDone!")
