"""추가 논문 Figure 생성 스크립트.

7개 figure:
- Fig: Think vs NoThink diverging bar (tab:think 대체)
- Fig: Per-turn hit rate line chart (fig:turnwise 대체)
- Fig: Question length boxplot by category (신규, appendix)
- Fig: Difficulty distribution stacked bar (신규)
- Fig: Parameter complexity bar (신규, appendix)
- Fig: Size vs Performance scatter (신규, appendix)
- Fig: t-SNE semantic space (신규, appendix)
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

import matplotlib.ticker as mticker
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FIGURES_DIR = _WS / "star-bench-paper" / "figures"
BENCHMARKS_DIR = _SB / "benchmarks"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# ── Color palette (consistent with generate_paper_figures.py) ──
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
    "Other": "#BAB0AC",
}

DIFFICULTY_COLORS = {
    "easy": "#59A14F",
    "medium": "#F28E2B",
    "hard": "#E15759",
    "irrelevance": "#B07AA1",
}


def get_family(model):
    for key in ["Qwen", "Mistral", "Ministral", "Llama", "xLAM", "EXAONE",
                 "Kanana", "kanana", "GLM", "gpt-oss", "skt", "A.X", "A_X"]:
        if key.lower() in model.lower():
            if key in ("Ministral",):
                return "Mistral"
            if key in ("kanana",):
                return "Kanana"
            if key in ("A.X", "A_X"):
                return "skt"
            return key
    return "Other"


def get_color(model):
    return COLORS.get(get_family(model), COLORS["Other"])


# ── Shared plot style ──
def apply_style(ax, title=None, xlabel=None, ylabel=None):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if title:
        ax.set_title(title, fontsize=14, fontweight="bold", pad=8)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=13)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=13)


# ═══════════════════════════════════════════════════════════════════
# Fig 1: Think vs NoThink Diverging Bar Chart
# ═══════════════════════════════════════════════════════════════════
def fig_think_diverging():
    """Think vs NoThink Δh (tool hit) as diverging horizontal bar chart."""
    # Δh = h_think - h_nothink from repro_mean_std.json (Korean, 3-round mean)
    data = [
        ("Qwen3.5-0.8B",  -0.129),
        ("Qwen3.5-2B",    -0.062),
        ("Qwen3.5-9B",    -0.015),
        ("gpt-oss-20B",   -0.001),
        ("Qwen3-4B-Think",-0.000),
        ("Qwen3-30B-Think",+0.000),
        ("Kanana-2-Think", +0.001),
        ("Qwen3.5-27B",   +0.006),
        ("Qwen3.5-4B",    +0.008),
    ]

    models = [d[0] for d in data]
    deltas = [d[1] for d in data]

    fig, ax = plt.subplots(figsize=(5, 4))
    y = np.arange(len(models))
    bar_colors = ["#E15759" if d < 0 else "#4E79A7" for d in deltas]

    bars = ax.barh(y, deltas, color=bar_colors, alpha=0.85, height=0.6, edgecolor="white", linewidth=0.5)

    # Add value labels — 음수 값은 바 왼쪽 끝(왼쪽 밖), 양수는 오른쪽 밖
    for i, (val, bar) in enumerate(zip(deltas, bars)):
        if val < 0:
            # 큰 음수는 바 왼쪽 끝 바깥
            offset = -0.004
            ha = "right"
        elif val > 0:
            offset = 0.003
            ha = "left"
        else:
            offset = 0.003
            ha = "left"
        label = f"{val:+.3f}" if val != 0 else "0.000"
        ax.text(val + offset, i, label, va="center", ha=ha, fontsize=9, fontweight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels(models, fontsize=12)
    ax.axvline(0, color="black", linewidth=0.8, linestyle="-")
    ax.set_xlim(-0.165, 0.03)
    ax.tick_params(axis='x', labelsize=12)

    # Annotations
    ax.text(-0.16, -0.8, "← Hurts", fontsize=10, color="#E15759", fontstyle="italic")
    ax.text(0.005, -0.8, "Helps →", fontsize=10, color="#4E79A7", fontstyle="italic")

    apply_style(ax, xlabel="$\\Delta h$ (think $-$ nothink)")
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig_think_delta.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("  Saved: fig_think_delta.png (compact)")


# ═══════════════════════════════════════════════════════════════════
# Fig 2: Per-turn Hit Rate Line Chart
# ═══════════════════════════════════════════════════════════════════
def fig_turnwise_line():
    """Cohort-level per-turn tool hit rate, column width.

    Aggregate over the full 29-model cohort: mean tool hit per turn with a
    +/-1 std band across models (no per-model selection). Turns 1-4 cover all
    50 scenarios; turn 5 covers the 18 longer scenarios (>=5 turns); turn 6
    (n=1 scenario) is excluded.
    """
    from collections import defaultdict
    MT = _SB / "_experiments" / "results_mt_oracle" / "eval"
    MAX_TURN = 5
    EXCLUDE = {  # 28-model cohort: drop 8 non-cohort variants + redundant Kanana-2-Instruct-2601
        "Qwen_Qwen3-30B-A3B-Instruct-2507", "Qwen_Qwen3-4B-Instruct-2507",
        "Qwen_Qwen3-8B", "Qwen_Qwen3_5-9B__nothink", "Qwen_Qwen3_5-9B__think",
        "Salesforce_Llama-xLAM-2-8b-fc-r", "Salesforce_xLAM-2-1b-fc-r",
        "Salesforce_xLAM-2-32b-fc-r",
        "kakaocorp_kanana-2-30b-a3b-instruct-2601",
    }
    turns = list(range(1, MAX_TURN + 1))
    # per-model per-turn mean hit, then aggregate across models
    per_model = []  # list of dict turn->rate
    for f in glob.glob(str(MT / "multiturn_*.json")):
        stem = Path(f).stem.replace("multiturn_", "")
        if stem in EXCLUDE:
            continue
        d = json.load(open(f))
        s, c = defaultdict(float), defaultdict(int)
        for sc in d["scenarios"]:
            for t in sc["turns"]:
                if t["turn"] <= MAX_TURN and t.get("tool_hit") is not None:
                    s[t["turn"]] += t["tool_hit"]; c[t["turn"]] += 1
        per_model.append({tn: (s[tn] / c[tn] * 100) for tn in turns if c[tn]})
    mean = np.array([np.mean([m[tn] for m in per_model if tn in m]) for tn in turns])
    std = np.array([np.std([m[tn] for m in per_model if tn in m]) for tn in turns])

    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    ax.fill_between(turns, np.clip(mean - std, 0, 100), np.clip(mean + std, 0, 100),
                    color=_VIR_SD(0.92), alpha=0.30, linewidth=0,
                    label=r"$\pm$1 SD")
    ax.plot(turns, mean, color="#2A7F79", marker="o", markersize=4.5,
            linewidth=1.8, label="Mean")
    # per-turn value labels (1 decimal): rising turns above, drop turns below the marker
    for i, tn in enumerate(turns):
        above = i < 3
        ax.annotate(f"{mean[i]:.1f}%", (tn, mean[i]),
                    textcoords="offset points", xytext=(0, 7 if above else -8),
                    ha="center", va="bottom" if above else "top",
                    fontsize=6, color="#2A7F79",
                    bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.75))
    # annotate the drop into the synthesis/validation turn in percentage points
    ax.annotate("", xy=(4, mean[3]), xytext=(3, mean[2]),
                arrowprops=dict(arrowstyle="->", color="#555555", lw=1.2))
    ax.text(3.58, (mean[2] + mean[3]) / 2 + 3,
            f"$-${mean[2] - mean[3]:.1f} pp", fontsize=6.5, color="#555555",
            ha="left", va="center", fontstyle="italic")

    ax.set_xticks(turns)
    ax.set_xticklabels([f"T{t}" for t in turns], fontsize=7.5)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax.tick_params(axis="y", labelsize=7.5)
    ax.set_xlabel("Turn", fontsize=8.5)
    ax.set_ylabel("Tool hit ($h$)", fontsize=8.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(fontsize=6.5, loc="lower left", frameon=True, framealpha=0.9,
              handlelength=1.6, handletextpad=0.4, borderpad=0.3, labelspacing=0.3)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig_turnwise_line.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("  Saved: fig_turnwise_line.png (cohort mean +/-1SD)")


# ═══════════════════════════════════════════════════════════════════
# Fig 3: Question Length Boxplot
# ═══════════════════════════════════════════════════════════════════
def fig_question_length_boxplot():
    """Question length distribution boxplot by category."""
    case_files = sorted(glob.glob(str(BENCHMARKS_DIR / "cases_*.json")))

    lengths_by_tool = {}
    for f in case_files:
        with open(f) as fh:
            data = json.load(fh)
        tool = os.path.basename(f).replace("cases_", "").replace(".json", "")
        lengths_by_tool[tool] = [len(c.get("question", "")) for c in data]

    # Sort by median length
    sorted_tools = sorted(lengths_by_tool.keys(),
                          key=lambda t: np.median(lengths_by_tool[t]), reverse=True)

    fig, ax = plt.subplots(figsize=(12, 4))
    box_data = [lengths_by_tool[t] for t in sorted_tools]
    labels = [t.replace("_", "\n", 1) if len(t) > 20 else t for t in sorted_tools]

    bp = ax.boxplot(box_data, patch_artist=True, vert=True,
                    medianprops=dict(color="black", linewidth=1.5),
                    whiskerprops=dict(linewidth=0.8),
                    capprops=dict(linewidth=0.8),
                    flierprops=dict(marker="o", markersize=3, alpha=0.5))

    # Color by subdomain
    subdomain_map = {
        "get_statistics": "Basic", "query_transactions": "Basic",
        "get_account_profile": "Basic", "get_fraud_type_summary": "Basic",
        "compare_periods": "Basic", "get_institution_report": "Basic",
        "rank_risky_transactions": "Basic", "get_trend_analysis": "Basic",
        "analyze_channel_risk": "Basic", "get_receiving_account_profile": "Basic",
        "analyze_network": "Network", "detect_aml_patterns": "Network",
        "analyze_cross_institution_flow": "Network",
        "detect_smurfing_network": "Network",
        "predict_fraud": "Detection", "detect_monitoring_alerts": "Detection",
        "detect_ctr_candidates": "Detection", "detect_dormant_reactivation": "Detection",
        "score_account_risk": "Detection",
        "generate_str": "Agent", "missing_parameters": "Agent",
        "validate_str_fields": "Reference", "get_aml_glossary": "Reference",
        "lookup_fiu_reference_types": "Reference",
        "multi_tool": "Multi-tool",
    }
    subdomain_colors = {
        "Basic": "#4E79A7", "Network": "#76B7B2", "Detection": "#E15759",
        "Agent": "#F28E2B", "Reference": "#B07AA1", "Multi-tool": "#EDC948",
    }

    for patch, tool in zip(bp["boxes"], sorted_tools):
        sd = subdomain_map.get(tool, "Basic")
        patch.set_facecolor(subdomain_colors.get(sd, "#BAB0AC"))
        patch.set_alpha(0.7)

    ax.set_xticklabels([t.replace("_", "\n") for t in sorted_tools],
                       fontsize=10, rotation=45, ha="right")
    apply_style(ax, ylabel="Question Length (chars)")

    # Legend
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor=c, alpha=0.7, label=s)
                       for s, c in subdomain_colors.items()]
    ax.legend(handles=legend_elements, fontsize=10, loc="upper right", ncol=2)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig_question_length_boxplot.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("  Saved: fig_question_length_boxplot.png")


# ═══════════════════════════════════════════════════════════════════
# Fig 4: Difficulty Distribution Stacked Bar
# ═══════════════════════════════════════════════════════════════════
def fig_difficulty_distribution():
    """Difficulty distribution stacked bar by tool category."""
    case_files = sorted(glob.glob(str(BENCHMARKS_DIR / "cases_*.json")))

    diff_by_tool = {}
    for f in case_files:
        with open(f) as fh:
            data = json.load(fh)
        tool = os.path.basename(f).replace("cases_", "").replace(".json", "")
        counts = {}
        for c in data:
            d = c.get("difficulty", "unknown")
            counts[d] = counts.get(d, 0) + 1
        diff_by_tool[tool] = counts

    # Sort by total cases descending
    sorted_tools = sorted(diff_by_tool.keys(),
                          key=lambda t: sum(diff_by_tool[t].values()), reverse=True)

    fig, ax = plt.subplots(figsize=(12, 4))
    x = np.arange(len(sorted_tools))
    width = 0.7

    bottom = np.zeros(len(sorted_tools))
    for diff_level in ["easy", "medium", "hard"]:
        vals = [diff_by_tool[t].get(diff_level, 0) for t in sorted_tools]
        ax.bar(x, vals, width, bottom=bottom, label=diff_level.capitalize(),
               color=DIFFICULTY_COLORS[diff_level], alpha=0.85, edgecolor="white", linewidth=0.5)
        bottom += np.array(vals)

    ax.set_xticks(x)
    ax.set_xticklabels([t.replace("_", "\n") for t in sorted_tools],
                       fontsize=10, rotation=45, ha="right")
    apply_style(ax, ylabel="Number of Cases")
    ax.legend(fontsize=11, loc="upper right")

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig_difficulty_distribution.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("  Saved: fig_difficulty_distribution.png")


# ═══════════════════════════════════════════════════════════════════
# Fig 5: Parameter Complexity Bar
# ═══════════════════════════════════════════════════════════════════
def fig_param_complexity():
    """Average required parameters per tool category."""
    case_files = sorted(glob.glob(str(BENCHMARKS_DIR / "cases_*.json")))

    param_counts = {}
    for f in case_files:
        with open(f) as fh:
            data = json.load(fh)
        tool = os.path.basename(f).replace("cases_", "").replace(".json", "")
        counts = []
        for c in data:
            exp = c.get("expected", {})
            if isinstance(exp, dict):
                pc = exp.get("param_checks", {})
                counts.append(sum(len(v) for v in pc.values()))
        if counts:
            param_counts[tool] = {"mean": np.mean(counts), "max": max(counts), "n": len(counts)}

    # Sort by mean descending
    sorted_tools = sorted(param_counts.keys(), key=lambda t: param_counts[t]["mean"], reverse=True)

    fig, ax = plt.subplots(figsize=(10, 5))
    y = np.arange(len(sorted_tools))
    means = [param_counts[t]["mean"] for t in sorted_tools]
    maxes = [param_counts[t]["max"] for t in sorted_tools]

    ax.barh(y, means, height=0.6, color="#4E79A7", alpha=0.85, label="Mean",
            edgecolor="white", linewidth=0.5)
    ax.scatter(maxes, y, color="#E15759", marker="|", s=80, linewidth=2,
              label="Max", zorder=5)

    ax.set_yticks(y)
    ax.set_yticklabels([t.replace("_", " ") for t in sorted_tools], fontsize=11)
    ax.invert_yaxis()
    apply_style(ax, xlabel="Number of Required Parameters")
    ax.legend(fontsize=11, loc="lower right")

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig_param_complexity.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("  Saved: fig_param_complexity.png")


# ═══════════════════════════════════════════════════════════════════
# Fig 6: Size vs Performance Scatter
# ═══════════════════════════════════════════════════════════════════
def fig_size_vs_performance():
    """Model size vs tool hit ($h$) scatter plot."""
    # Model name → (params_B, is_MoE_active_B_or_None)
    SIZE_MAP = {
        "Qwen_Qwen3_5-27B": 27, "Qwen_Qwen3_5-9B": 9, "Qwen_Qwen3_5-4B": 4,
        "Qwen_Qwen3_5-2B": 2, "Qwen_Qwen3_5-0_8B": 0.8,
        "Qwen_Qwen3-30B-A3B-Thinking-2507": 3,  # active params
        "Qwen_Qwen3-30B-A3B-Instruct-2507": 3,
        "Qwen_Qwen3-4B-Thinking-2507": 4,
        "Qwen_Qwen3-4B-Instruct-2507": 4,
        "Qwen_Qwen3-8B": 8,
        "Qwen_Qwen3-Coder-30B-A3B-Instruct": 3,
        "Qwen_Qwen2_5-1_5B-Instruct": 1.5,
        "Salesforce_xLAM-2-32b-fc-r": 32,
        "Salesforce_Llama-xLAM-2-8b-fc-r": 8,
        "Salesforce_xLAM-2-3b-fc-r": 3,
        "Salesforce_xLAM-2-1b-fc-r": 1,
        "Salesforce_Llama-xLAM-2-70b-fc-r": 70,
        "mistralai_Mistral-Small-3_2-24B-Instruct-2506": 24,
        "mistralai_Ministral-3-14B-Instruct-2512": 14,
        "mistralai_Ministral-3-8B-Instruct-2512": 8,
        "mistralai_Ministral-3-3B-Instruct-2512": 3,
        "mistralai_Mistral-Nemo-Instruct-2407": 12,
        "meta-llama_Llama-3_3-70B-Instruct": 70,
        "meta-llama_Llama-3_1-8B-Instruct": 8,
        "meta-llama_Llama-3_2-3B-Instruct": 3,
        "meta-llama_Llama-3_2-1B-Instruct": 1,
        "LGAI-EXAONE_EXAONE-4_0-32B": 32,
        "LGAI-EXAONE_EXAONE-4_0-1_2B": 1.2,
        "kakaocorp_kanana-2-30b-a3b-thinking-2601": 3,
        "kakaocorp_kanana-2-30b-a3b-instruct": 3,
        "zai-org_GLM-4_7-Flash": 9,
        "openai_gpt-oss-20b": 20,
        "skt_A_X-4_0": 72,
        "skt_A_X-4_0-Light": 7,
        "NousResearch_Hermes-3-Llama-3_1-8B": 8,
    }

    # results_kr/eval/eval_*.json single-round 결과를 repro_mean_std-like list로 빌드 (repro_mean_std.json 누락 대체)
    import re, glob, os
    results_kr_eval = _SB / "_experiments" / "results_kr" / "eval"
    repro = []
    for f in sorted(glob.glob(str(results_kr_eval / "eval_*.json"))):
        base = os.path.basename(f).replace('.json', '')
        m = re.match(r'eval_(.+?)_\d{8}_\d{6}$', base)
        if not m:
            continue
        fid = m.group(1)
        with open(f) as fp:
            d = json.load(fp)
        repro.append({"model": fid, "h_mean": d['overall']['primary_tool_hit_rate']})

    fig, ax = plt.subplots(figsize=(3.5, 2.7))

    # Collect (size, h) per family
    from collections import defaultdict
    family_points = defaultdict(list)
    for item in repro:
        model = item["model"]
        base = model.replace("__think", "").replace("__nothink", "")
        size = SIZE_MAP.get(base)
        if size is None:
            continue
        family = get_family(model)
        marker = "^" if "__think" in model else ("v" if "__nothink" in model else "o")
        family_points[family].append((size, item["h_mean"], marker, model))

    plotted_families = set()
    for family, pts in family_points.items():
        color = COLORS.get(family, COLORS["Other"])
        # For line: take max h per size within family (best variant at each size)
        size_best = {}
        for size, h, _, _ in pts:
            if size not in size_best or h > size_best[size]:
                size_best[size] = h
        sizes_sorted = sorted(size_best.keys())
        hs_sorted = [size_best[s] for s in sizes_sorted]
        if len(sizes_sorted) >= 2:
            ax.plot(sizes_sorted, hs_sorted, '-', color=color, alpha=0.35, linewidth=1.0, zorder=3)

        # Plot points (all variants)
        for size, h, marker, model in pts:
            label = family if family not in plotted_families else None
            plotted_families.add(family)
            ax.scatter(size, h, c=color, s=20, alpha=0.85,
                       edgecolors="white", linewidths=0.4, marker=marker, label=label, zorder=5)

    ax.set_xscale("log")
    ax.set_xticks([1, 3, 8, 24, 70])
    ax.get_xaxis().set_major_formatter(mticker.ScalarFormatter())
    ax.set_xlim(0.7, 100)
    ax.set_ylim(0.45, 1.0)

    apply_style(ax)
    ax.set_xlabel("Parameters (B, log scale)", fontsize=8.5)
    ax.set_ylabel("Tool Hit ($h$)", fontsize=8.5)
    ax.tick_params(labelsize=7.5)
    leg = ax.legend(fontsize=6, loc="lower right", ncol=2, frameon=True,
                    framealpha=0.9, title="Family",
                    markerscale=0.9, handletextpad=0.3, columnspacing=0.8,
                    borderpad=0.3, labelspacing=0.3)
    leg.get_title().set_fontsize(6.5)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig_size_vs_performance.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("  Saved: fig_size_vs_performance.png")


# ═══════════════════════════════════════════════════════════════════
# Fig 7: t-SNE Semantic Space
# ═══════════════════════════════════════════════════════════════════
def fig_tsne_semantic():
    """t-SNE visualization of benchmark question embeddings."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.manifold import TSNE
    except ImportError:
        print("  SKIP: fig_tsne_semantic.png (scikit-learn not available)")
        return

    case_files = sorted(glob.glob(str(BENCHMARKS_DIR / "cases_*.json")))

    questions = []
    tool_labels = []
    for f in case_files:
        with open(f) as fh:
            data = json.load(fh)
        tool = os.path.basename(f).replace("cases_", "").replace(".json", "")
        for c in data:
            questions.append(c.get("question", ""))
            tool_labels.append(tool)

    # TF-IDF → t-SNE (no external embedding model needed)
    vectorizer = TfidfVectorizer(max_features=500, analyzer="char_wb", ngram_range=(2, 4))
    X = vectorizer.fit_transform(questions).toarray()

    tsne = TSNE(n_components=2, random_state=42, perplexity=30, max_iter=1000)
    coords = tsne.fit_transform(X)

    # Assign colors by subdomain (matches tab:tool_suite taxonomy)
    subdomain_map = {
        "get_statistics": "Txn Inquiry", "query_transactions": "Txn Inquiry",
        "get_account_profile": "Txn Inquiry", "compare_periods": "Txn Inquiry",
        "get_fraud_type_summary": "Txn Inquiry", "get_institution_report": "Txn Inquiry",
        "get_receiving_account_profile": "Txn Inquiry",
        "predict_fraud": "Suspicious Detection", "rank_risky_transactions": "Suspicious Detection",
        "score_account_risk": "Suspicious Detection", "detect_monitoring_alerts": "Suspicious Detection",
        "analyze_network": "Money Flow & Network", "detect_aml_patterns": "Money Flow & Network",
        "detect_smurfing_network": "Money Flow & Network", "detect_dormant_reactivation": "Money Flow & Network",
        "analyze_cross_institution_flow": "Money Flow & Network", "get_trend_analysis": "Money Flow & Network",
        "analyze_channel_risk": "Money Flow & Network",
        "detect_ctr_candidates": "Regulatory Reporting", "lookup_fiu_reference_types": "Regulatory Reporting",
        "validate_str_fields": "Regulatory Reporting", "get_aml_glossary": "Regulatory Reporting",
        "generate_str": "Regulatory Reporting",
        "multi_tool": "Multi-tool", "missing_parameters": "Missing-param",
    }
    subdomain_colors = {  # 색감 통일: Fig 9와 동일한 viridis 서브도메인 매핑
        "Txn Inquiry": _VIR_SD(0.08), "Suspicious Detection": _VIR_SD(0.24), "Money Flow & Network": _VIR_SD(0.40),
        "Regulatory Reporting": _VIR_SD(0.56),
        "Multi-tool": _VIR_SD(0.72), "Missing-param": _VIR_SD(0.86),
    }

    # 2-panel figure*(\app:diversity)용: 패널 실제 폭(~3.5in)에 맞춰 figsize/폰트 재설정 → 다운스케일 없이 가독성 확보
    fig, ax = plt.subplots(figsize=(3.6, 2.3))

    plotted_subdomains = set()
    for i, (x, y) in enumerate(coords):
        sd = subdomain_map.get(tool_labels[i], "Missing-param")
        color = subdomain_colors.get(sd, "#BAB0AC")
        plotted_subdomains.add(sd)
        ax.scatter(x, y, color=color, s=10, alpha=0.6, edgecolors="none")

    apply_style(ax)
    ax.tick_params(length=3, labelsize=7)  # tick 값 표시(축 라벨은 생략)
    # 범례 순서를 Fig 9(qlen)의 SUBDOMAIN_ORDER와 동일하게 강제(명시적 handle)
    from matplotlib.lines import Line2D as _L2D
    _tsne_order = ["Txn Inquiry", "Suspicious Detection", "Money Flow & Network",
                   "Regulatory Reporting", "Multi-tool", "Missing-param"]
    _handles = [_L2D([0], [0], marker="o", linestyle="", markersize=5,
                     markerfacecolor=subdomain_colors[sd], markeredgecolor="none", label=sd)
                for sd in _tsne_order if sd in plotted_subdomains]
    ax.legend(handles=_handles, fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, -0.22),
              ncol=2, frameon=False, columnspacing=1.0, handletextpad=0.3, labelspacing=0.3)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig_tsne_semantic.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("  Saved: fig_tsne_semantic.png")


# ═══════════════════════════════════════════════════════════════════
# Fig: Difficulty Distribution Summary (by subdomain, for main text)
# ═══════════════════════════════════════════════════════════════════

# Subdomain mapping consistent with Table 1 (tab:tool_suite)
SUBDOMAIN_MAP = {
    "get_statistics": "Txn\nInquiry",
    "query_transactions": "Txn\nInquiry",
    "get_account_profile": "Txn\nInquiry",
    "compare_periods": "Txn\nInquiry",
    "get_fraud_type_summary": "Txn\nInquiry",
    "get_institution_report": "Txn\nInquiry",
    "get_receiving_account_profile": "Txn\nInquiry",
    "predict_fraud": "Suspicious\nDetection",
    "rank_risky_transactions": "Suspicious\nDetection",
    "score_account_risk": "Suspicious\nDetection",
    "detect_monitoring_alerts": "Suspicious\nDetection",
    "analyze_network": "Money Flow\n& Network",
    "detect_aml_patterns": "Money Flow\n& Network",
    "detect_smurfing_network": "Money Flow\n& Network",
    "detect_dormant_reactivation": "Money Flow\n& Network",
    "analyze_cross_institution_flow": "Money Flow\n& Network",
    "get_trend_analysis": "Money Flow\n& Network",
    "analyze_channel_risk": "Money Flow\n& Network",
    "detect_ctr_candidates": "Regulatory\nReporting",
    "lookup_fiu_reference_types": "Regulatory\nReporting",
    "validate_str_fields": "Regulatory\nReporting",
    "get_aml_glossary": "Regulatory\nReporting",
    "generate_str": "Regulatory\nReporting",
    "multi_tool": "Multi-tool",  # includes generate_STR (no separate cases_generate_str.json)
    "missing_parameters": "Missing-\nparam",
}

SUBDOMAIN_ORDER = [
    "Txn\nInquiry", "Suspicious\nDetection",
    "Money Flow\n& Network", "Regulatory\nReporting",
    "Multi-tool", "Missing-\nparam",
]

import matplotlib as _mpl  # 색감 통일: 서브도메인 색을 viridis 계열(blue->green->yellow)에서 샘플
_VIR_SD = _mpl.colormaps["viridis"]
SUBDOMAIN_COLORS_BAR = [_VIR_SD(x) for x in [0.08, 0.24, 0.40, 0.56, 0.72, 0.86, 0.97]]


def fig_difficulty_distribution_summary():
    """Difficulty distribution stacked bar by subdomain (main text version)."""
    case_files = sorted(glob.glob(str(BENCHMARKS_DIR / "cases_*.json")))

    # Aggregate by subdomain
    diff_by_sd = {sd: {} for sd in SUBDOMAIN_ORDER}
    for f in case_files:
        with open(f) as fh:
            data = json.load(fh)
        tool = os.path.basename(f).replace("cases_", "").replace(".json", "")
        sd = SUBDOMAIN_MAP.get(tool, "Multi-tool")
        for c in data:
            d = c.get("difficulty", "unknown")
            diff_by_sd[sd][d] = diff_by_sd[sd].get(d, 0) + 1

    fig, ax = plt.subplots(figsize=(9, 5.5))
    x = np.arange(len(SUBDOMAIN_ORDER))
    width = 0.55

    bottom = np.zeros(len(SUBDOMAIN_ORDER))
    for diff_level in ["easy", "medium", "hard"]:
        vals = [diff_by_sd[sd].get(diff_level, 0) for sd in SUBDOMAIN_ORDER]
        bars = ax.bar(x, vals, width, bottom=bottom, label=diff_level.capitalize(),
               color=DIFFICULTY_COLORS[diff_level], alpha=0.85,
               edgecolor="white", linewidth=0.5)
        bottom += np.array(vals)

    # Total count on top of each bar
    for i, sd in enumerate(SUBDOMAIN_ORDER):
        total = sum(diff_by_sd[sd].values())
        ax.text(i, bottom[i] + 3, str(total), ha="center", va="bottom", fontsize=11, color="#444")

    ax.set_xticks(x)
    ax.set_xticklabels([sd for sd in SUBDOMAIN_ORDER], fontsize=18, rotation=40, ha="right", rotation_mode="anchor")
    ax.tick_params(axis='y', labelsize=16)
    apply_style(ax, ylabel="Number of Cases")
    ax.yaxis.label.set_size(16)
    ax.legend(fontsize=14, loc="upper right", ncol=2)
    ax.set_ylim(0, max(bottom) * 1.12)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig_difficulty_distribution_summary.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("  Saved: fig_difficulty_distribution_summary.png")


# ═══════════════════════════════════════════════════════════════════
# Fig: Benchmark Composition combined (stacked, shared x-axis, column width)
# ═══════════════════════════════════════════════════════════════════
def fig_benchmark_composition_combined():
    """Single column-width figure: difficulty (top) + question length (bottom),
    stacked with a shared subdomain x-axis (labels shown once at bottom)."""
    case_files = sorted(glob.glob(str(BENCHMARKS_DIR / "cases_*.json")))

    diff_by_sd = {sd: {} for sd in SUBDOMAIN_ORDER}
    lengths_by_sd = {sd: [] for sd in SUBDOMAIN_ORDER}
    for f in case_files:
        with open(f) as fh:
            data = json.load(fh)
        tool = os.path.basename(f).replace("cases_", "").replace(".json", "")
        sd = SUBDOMAIN_MAP.get(tool, "Multi-tool")
        for c in data:
            d = c.get("difficulty", "unknown")
            diff_by_sd[sd][d] = diff_by_sd[sd].get(d, 0) + 1
            lengths_by_sd[sd].append(len(c.get("question", "")))

    x = np.arange(len(SUBDOMAIN_ORDER))
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(3.4, 4.3), sharex=True,
        gridspec_kw={"hspace": 0.12, "height_ratios": [1, 1]})

    # ── (a) Difficulty stacked bars ──
    bottom = np.zeros(len(SUBDOMAIN_ORDER))
    for diff_level in ["easy", "medium", "hard"]:
        vals = [diff_by_sd[sd].get(diff_level, 0) for sd in SUBDOMAIN_ORDER]
        ax1.bar(x, vals, 0.62, bottom=bottom, label=diff_level.capitalize(),
                color=DIFFICULTY_COLORS[diff_level], alpha=0.85,
                edgecolor="white", linewidth=0.4)
        bottom += np.array(vals)
    for i, sd in enumerate(SUBDOMAIN_ORDER):
        ax1.text(i, bottom[i] + 4, str(int(bottom[i])), ha="center",
                 va="bottom", fontsize=5.5, color="#444")
    ax1.set_ylim(0, max(bottom) * 1.18)
    ax1.set_ylabel("Number of cases", fontsize=8)
    ax1.tick_params(axis="y", labelsize=6)
    ax1.legend(fontsize=6, loc="upper center", ncol=3, frameon=False,
               handlelength=1.0, columnspacing=1.0, handletextpad=0.4,
               borderpad=0.2)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.text(-0.16, 1.0, "(a)", transform=ax1.transAxes, fontsize=9,
             va="top", ha="right")

    # ── (b) Question length boxplot ──
    box_data = [lengths_by_sd[sd] for sd in SUBDOMAIN_ORDER]
    bp = ax2.boxplot(box_data, positions=x, widths=0.55, patch_artist=True,
                     medianprops=dict(color="black", linewidth=1.0),
                     whiskerprops=dict(linewidth=0.7),
                     capprops=dict(linewidth=0.7),
                     flierprops=dict(marker="o", markersize=2, alpha=0.4))
    for patch, color in zip(bp["boxes"], SUBDOMAIN_COLORS_BAR):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax2.set_ylabel("Question length (chars)", fontsize=8)
    ax2.tick_params(axis="y", labelsize=6)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.text(-0.16, 1.0, "(b)", transform=ax2.transAxes, fontsize=9,
             va="top", ha="right")

    # ── Shared x-axis (labels at bottom only) ──
    ax2.set_xticks(x)
    ax2.set_xticklabels(SUBDOMAIN_ORDER, fontsize=6.5, rotation=40,
                        ha="right", rotation_mode="anchor")
    ax2.set_xlim(-0.6, len(SUBDOMAIN_ORDER) - 0.4)

    plt.savefig(FIGURES_DIR / "fig_benchmark_composition.png", dpi=300,
                bbox_inches="tight")
    plt.close()
    print("  Saved: fig_benchmark_composition.png")


# ═══════════════════════════════════════════════════════════════════
# Fig: Question Length Summary (by subdomain, for main text)
# ═══════════════════════════════════════════════════════════════════
def fig_question_length_boxplot_summary():
    """Question length distribution boxplot by subdomain (main text version)."""
    case_files = sorted(glob.glob(str(BENCHMARKS_DIR / "cases_*.json")))

    # Aggregate by subdomain
    lengths_by_sd = {sd: [] for sd in SUBDOMAIN_ORDER}
    for f in case_files:
        with open(f) as fh:
            data = json.load(fh)
        tool = os.path.basename(f).replace("cases_", "").replace(".json", "")
        sd = SUBDOMAIN_MAP.get(tool, "Multi-tool")
        lengths_by_sd[sd].extend([len(c.get("question", "")) for c in data])

    # 2-panel figure*(\app:diversity)용: 패널 실제 폭(~3.5in)에 맞춰 figsize/폰트 재설정 → 다운스케일 없이 가독성 확보
    fig, ax = plt.subplots(figsize=(3.6, 2.3))
    box_data = [lengths_by_sd[sd] for sd in SUBDOMAIN_ORDER]

    bp = ax.boxplot(box_data, patch_artist=True, vert=True,
                    boxprops=dict(linewidth=0.6),
                    medianprops=dict(color="black", linewidth=0.8),
                    whiskerprops=dict(linewidth=0.5),
                    capprops=dict(linewidth=0.5),
                    flierprops=dict(marker="o", markersize=2, alpha=0.5))

    for patch, color in zip(bp["boxes"], SUBDOMAIN_COLORS_BAR):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_xticklabels([sd for sd in SUBDOMAIN_ORDER], fontsize=7, rotation=40, ha="right", rotation_mode="anchor")
    ax.tick_params(axis='y', labelsize=7)
    apply_style(ax, ylabel="Question Length (chars)")
    ax.yaxis.label.set_size(7)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig_question_length_boxplot_summary.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("  Saved: fig_question_length_boxplot_summary.png")


# ═══════════════════════════════════════════════════════════════════
# Fig: Thinking mode — (a) Qwen3.5 size dependence (b) per-model paired bar
# ═══════════════════════════════════════════════════════════════════
def fig_think_modes():
    """Two PNGs for RQ3 thinking mode subfigures.

    (a) fig_think_size.png — Qwen3.5 size dependence on Delta h / Delta h_bar.
    (b) fig_think_amp.png  — All 9 models paired bar (single- vs. multi-turn).
    """
    # 3-round mean (post-rescore) Δh and Δh_bar for Qwen3.5 think vs nothink
    qwen35 = [
        ("0.8B", 0.8, -0.122, -0.365),
        ("2B", 2.0, -0.057, -0.212),
        ("4B", 4.0, -0.012, -0.021),
        ("9B", 9.0, -0.042, -0.055),
        ("27B", 27.0, -0.010, -0.049),
    ]
    others = [
        ("Qwen3-4B", -0.000, -0.011),
        ("Qwen3-30B", +0.000, +0.000),
        ("gpt-oss-20B", -0.001, +0.007),
        ("Kanana-2-30B", +0.001, +0.010),
    ]

    SINGLE_C = "#1F4E79"   # Deep navy
    MULTI_C = "#5B8DBE"    # Steel blue (paired with navy)

    # ─── Panel (a): Qwen3.5 size dependence (line chart, log x-axis) ──
    fig, ax = plt.subplots(figsize=(7, 4.8))

    sizes_unsorted = [d[1] for d in qwen35]
    sorted_idx = np.argsort(sizes_unsorted)
    sizes = [qwen35[i][1] for i in sorted_idx]
    labels = [qwen35[i][0] for i in sorted_idx]
    delta_h = [qwen35[i][2] for i in sorted_idx]
    delta_h_bar = [qwen35[i][3] for i in sorted_idx]

    ax.axhline(y=0, color="#666", linestyle="--", linewidth=1, zorder=1, alpha=0.7)

    ax.fill_between(sizes, delta_h_bar, delta_h, alpha=0.13,
                     color="#999", zorder=2)

    ax.plot(sizes, delta_h, "o-", color=SINGLE_C, linewidth=2.4,
             markersize=11, label=r"Single-turn $\Delta h$",
             markeredgecolor="white", markeredgewidth=1.5, zorder=4)
    ax.plot(sizes, delta_h_bar, "s-", color=MULTI_C, linewidth=2.4,
             markersize=11, label=r"Multi-turn $\Delta \bar{h}$",
             markeredgecolor="white", markeredgewidth=1.5, zorder=4)

    ax.set_xscale("log")
    ax.set_xticks(sizes)
    ax.set_xticklabels(labels, fontsize=14)
    ax.set_xlabel("Qwen3.5 model size (log scale)", fontsize=14)
    ax.set_ylabel(r"Think $-$ NoThink delta", fontsize=14)
    ax.set_ylim(-0.42, 0.05)
    ax.legend(loc="lower right", fontsize=12, frameon=True,
               framealpha=0.95, edgecolor="#ccc")
    ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="y", labelsize=13)

    # Annotate amplification at largest gap
    ax.annotate(r"$\times 2.8$ amp.", xy=(0.8, (delta_h[0] + delta_h_bar[0]) / 2),
                 xytext=(15, 0), textcoords="offset points",
                 fontsize=10.5, color="#444", style="italic",
                 ha="left", va="center")

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig_think_size.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("  Saved: fig_think_size.png")

    # ─── Panel (b): All 9 models paired bar ──
    fig, ax = plt.subplots(figsize=(8, 4.8))

    qwen35_sorted = sorted(qwen35, key=lambda d: d[1])
    qwen35_names = [f"Qwen3.5-{d[0]}" for d in qwen35_sorted]
    qwen35_dh = [d[2] for d in qwen35_sorted]
    qwen35_dhb = [d[3] for d in qwen35_sorted]

    other_names = [d[0] for d in others]
    other_dh = [d[1] for d in others]
    other_dhb = [d[2] for d in others]

    all_names = qwen35_names + other_names
    all_dh = qwen35_dh + other_dh
    all_dhb = qwen35_dhb + other_dhb

    x = np.arange(len(all_names))
    width = 0.4

    ax.axhline(y=0, color="#666", linestyle="--", linewidth=1,
                zorder=1, alpha=0.7)
    ax.bar(x - width / 2, all_dh, width, color=SINGLE_C,
            label=r"Single-turn $\Delta h$",
            edgecolor="white", linewidth=0.8, zorder=3)
    ax.bar(x + width / 2, all_dhb, width, color=MULTI_C,
            label=r"Multi-turn $\Delta \bar{h}$",
            edgecolor="white", linewidth=0.8, zorder=3)

    sep_x = len(qwen35) - 0.5
    ax.axvline(x=sep_x, color="#999", linestyle=":", linewidth=1.2, zorder=2)

    ax.set_ylim(-0.42, 0.07)
    ax.text((len(qwen35) - 1) / 2, 0.04, "Qwen3.5 series",
             fontsize=10.5, color="#555", ha="center", style="italic")
    ax.text(sep_x + (len(others)) / 2, 0.04, "Other models",
             fontsize=10.5, color="#555", ha="center", style="italic")

    ax.set_xticks(x)
    ax.set_xticklabels(all_names, rotation=30, ha="right",
                        fontsize=13, rotation_mode="anchor")
    ax.set_ylabel(r"Think $-$ NoThink delta", fontsize=14)
    ax.legend(loc="lower left", fontsize=12, frameon=True,
               framealpha=0.95, edgecolor="#ccc")
    ax.grid(True, alpha=0.3, axis="y", linestyle="--", linewidth=0.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="y", labelsize=13)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig_think_amp.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("  Saved: fig_think_amp.png")


# ═══════════════════════════════════════════════════════════════════
# Fig: Error modes — error type distribution + family x error heatmap (RQ4)
# ═══════════════════════════════════════════════════════════════════
def fig_error_modes():
    """Error type distribution + family x error type heatmap for RQ4."""
    results_path = _SB / "_experiments" / "results_RQ1" / "error_analysis_single_turn.json"
    with open(results_path) as f:
        data = json.load(f)

    families = data["3_family_error_distribution"]["by_family"]

    err_types_order = ["correct", "wrong_func", "other", "wrong_value",
                        "hallucinated_call", "missing_param", "api_error"]
    err_colors = {
        "correct": "#59A14F",
        "wrong_func": "#E15759",
        "other": "#BAB0AC",
        "wrong_value": "#F28E2B",
        "hallucinated_call": "#B07AA1",
        "missing_param": "#4E79A7",
        "api_error": "#76B7B2",
    }

    overall = {et: 0 for et in err_types_order}
    for info in families.values():
        for et, c in info["error_distribution"].items():
            if et in overall:
                overall[et] += c["count"]
    total = sum(overall.values())
    overall_pct = {et: overall[et] / total * 100 for et in err_types_order}

    err_focus = ["wrong_func", "wrong_value", "hallucinated_call", "missing_param"]
    family_order = sorted(families.keys())
    heatmap_data = []
    for fam in family_order:
        info = families[fam]
        n = info["n_records"]
        row = []
        for et in err_focus:
            c = info["error_distribution"].get(et, {"count": 0})["count"]
            row.append(c / n * 100)
        heatmap_data.append(row)
    heatmap_data = np.array(heatmap_data)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.8),
                                     gridspec_kw={"width_ratios": [1, 1.15]})

    # (a) Horizontal stacked bar
    left = 0
    for et in err_types_order:
        pct = overall_pct[et]
        ax1.barh([0], [pct], left=left, color=err_colors[et],
                 label=f"{et} ({pct:.1f}%)", edgecolor="white", linewidth=0.6)
        if pct >= 4:
            text_color = "white" if et != "other" else "black"
            ax1.text(left + pct / 2, 0, f"{pct:.1f}%", ha="center", va="center",
                     fontsize=10, color=text_color, fontweight="bold")
        left += pct
    ax1.set_xlim(0, 100)
    ax1.set_xlabel("Share of all calls (%)", fontsize=12)
    ax1.set_yticks([])
    ax1.set_title("(a) Error type distribution (n={:,})".format(total),
                   fontsize=12, pad=10)
    ax1.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18),
                ncol=3, fontsize=9, frameon=False, columnspacing=0.8)
    ax1.set_xticks([0, 20, 40, 60, 80, 100])
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.spines["left"].set_visible(False)

    # (b) Heatmap family x error type
    im = ax2.imshow(heatmap_data, aspect="auto", cmap="YlOrRd",
                     vmin=0, vmax=max(heatmap_data.max(), 1))
    ax2.set_xticks(range(len(err_focus)))
    ax2.set_xticklabels([e.replace("_", "\n") for e in err_focus], fontsize=10)
    ax2.set_yticks(range(len(family_order)))
    ax2.set_yticklabels(family_order, fontsize=10)
    ax2.set_title("(b) Error rate by family (% of family calls)",
                   fontsize=12, pad=10)

    vmax = heatmap_data.max()
    for i in range(len(family_order)):
        for j in range(len(err_focus)):
            v = heatmap_data[i, j]
            color = "white" if v > vmax * 0.55 else "black"
            ax2.text(j, i, f"{v:.1f}", ha="center", va="center",
                      fontsize=9, color=color)

    cbar = plt.colorbar(im, ax=ax2, fraction=0.05, pad=0.03)
    cbar.set_label("% of calls", fontsize=10)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig_error_modes.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("  Saved: fig_error_modes.png")


def fig_error_by_family():
    """Family x error-type heatmap only (panel (b) of fig_error_modes),
    sized for a column-width subfigure in the main text."""
    results_path = _SB / "_experiments" / "results_RQ1" / "error_analysis_single_turn.json"
    with open(results_path) as f:
        data = json.load(f)
    families = data["3_family_error_distribution"]["by_family"]

    err_focus = ["wrong_func", "wrong_value", "hallucinated_call", "missing_param"]
    family_order = sorted(families.keys())
    heatmap_data = []
    for fam in family_order:
        info = families[fam]
        n = info["n_records"]
        heatmap_data.append([
            info["error_distribution"].get(et, {"count": 0})["count"] / n * 100
            for et in err_focus
        ])
    heatmap_data = np.array(heatmap_data)

    fig, ax = plt.subplots(figsize=(5.2, 4.2))
    im = ax.imshow(heatmap_data, aspect="auto", cmap="YlOrRd",
                   vmin=0, vmax=max(heatmap_data.max(), 1))
    ax.set_xticks(range(len(err_focus)))
    ax.set_xticklabels([e.replace("_", "\n") for e in err_focus], fontsize=11)
    ax.set_yticks(range(len(family_order)))
    ax.set_yticklabels(family_order, fontsize=11)

    vmax = heatmap_data.max()
    for i in range(len(family_order)):
        for j in range(len(err_focus)):
            v = heatmap_data[i, j]
            ax.text(j, i, f"{v:.1f}", ha="center", va="center",
                    fontsize=10, color="white" if v > vmax * 0.55 else "black")

    cbar = plt.colorbar(im, ax=ax, fraction=0.05, pad=0.03)
    cbar.set_label("% of family calls", fontsize=10)
    cbar.ax.tick_params(labelsize=9)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig_error_by_family.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("  Saved: fig_error_by_family.png")


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Generating new paper figures...")
    fig_think_diverging()
    fig_turnwise_line()
    fig_question_length_boxplot()
    fig_difficulty_distribution()
    fig_param_complexity()
    fig_size_vs_performance()
    fig_tsne_semantic()
    fig_difficulty_distribution_summary()
    fig_question_length_boxplot_summary()
    fig_benchmark_composition_combined()
    fig_think_modes()
    fig_error_modes()
    fig_error_by_family()
    print("Done!")
