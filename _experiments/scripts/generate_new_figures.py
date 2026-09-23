"""The remaining paper figures: the benchmark's own shape, and two over results.

Figures are written inside `_experiments/figures/` and copied to the manuscript
in one explicit step, so drawing a figure here cannot replace one the paper
builds from.

The figures fall in two groups. The benchmark figures read `benchmarks/`
directly and do not depend on any run: question length, difficulty, parameter
complexity, composition, t-SNE. The result figures read `analysis/load.py` like
every other step: per-turn hit, size against performance, and the two error
figures, whose categories are the scorer's own error types so that a figure and
a table classify the same failure the same way.
"""

import json
import glob
import os
import re
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Figures are written inside this repository only; the manuscript copy is one
# explicit step (_figure_out).
import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parent))
from _figure_out import install as _install_figure_out
_SB = _P(__file__).resolve().parents[2]
SB_FIG = _install_figure_out()

import matplotlib.ticker as mticker
from pathlib import Path

PROJECT_ROOT = _SB
FIGURES_DIR = SB_FIG
BENCHMARKS_DIR = _SB / "benchmarks"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

_sys.path.insert(0, str(_SB))
from _experiments.scripts.analysis import load  # noqa: E402


def _cohort_note() -> str:
    table = load.missing()
    absent = table.loc[~table["single"], "config_id"].tolist()
    scored = len(table) - len(absent)
    if not absent:
        return f"all {len(table)} configurations scored"
    return f"{scored} of {len(table)} configurations scored"

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
# ═══════════════════════════════════════════════════════════════════
# Fig 2: Per-turn Hit Rate Line Chart
# ═══════════════════════════════════════════════════════════════════
def fig_turnwise_line():
    """Cohort-level per-turn tool hit rate, half-column width.

    Mean tool hit per turn with a +/-1 SD band across the scored configurations,
    from the oracle setting. Turn 6 is left out: one scenario reaches it, so the
    band there is one model's variance and not the cohort's.
    """
    MAX_TURN = 5
    turns = list(range(1, MAX_TURN + 1))
    _, turn_rows = load.multiturn("oracle")
    kept = turn_rows[turn_rows["turn"] <= MAX_TURN]
    per_config = (kept.groupby(["config_id", "turn"])["h"].mean() * 100).unstack("turn")
    per_model = [{tn: row[tn] for tn in turns if tn in row and row[tn] == row[tn]}
                 for _, row in per_config.iterrows()]
    mean = np.array([np.mean([m[tn] for m in per_model if tn in m]) for tn in turns])
    std = np.array([np.std([m[tn] for m in per_model if tn in m]) for tn in turns])

    # Drawn 1:1 for a 0.45\\textwidth wrapfigure, so nothing is scaled at use.
    # The y axis stays pinned to 0-100%, so the taller aspect changes the shape
    # of the drop on the page but not what it is worth.
    fig, ax = plt.subplots(figsize=(2.45, 1.85))
    ax.fill_between(turns, np.clip(mean - std, 0, 100), np.clip(mean + std, 0, 100),
                    color=_VIR_SD(0.92), alpha=0.30, linewidth=0,
                    label=r"$\pm$1 SD")
    ax.plot(turns, mean, color=_VIR_SD(0.55), marker="o", markersize=4.5,
            linewidth=1.2, label="Mean")
    # per-turn value labels (1 decimal): rising turns above, drop turns below the marker
    for i, tn in enumerate(turns):
        above = i < 3
        ha = "left" if i == 0 else "center"   # T1 left-align to clear the y-axis
        xoff = 2 if i == 0 else 0
        ax.annotate(f"{mean[i]:.1f}%", (tn, mean[i]),
                    textcoords="offset points", xytext=(xoff, 7 if above else -8),
                    ha=ha, va="bottom" if above else "top",
                    fontsize=4.8, color=_VIR_SD(0.55))
    # annotate the drop into the synthesis/validation turn in percentage points
    ax.annotate("", xy=(4, mean[3]), xytext=(3, mean[2]),
                arrowprops=dict(arrowstyle="->", color="#555555", lw=1.2))
    ax.text(3.58, (mean[2] + mean[3]) / 2 + 3,
            f"$-${mean[2] - mean[3]:.1f} pp", fontsize=5.2, color="#555555",
            ha="left", va="center", fontstyle="italic")

    ax.set_xticks(turns)
    ax.set_xticklabels([f"T{t}" for t in turns], fontsize=5.4)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax.tick_params(axis="y", labelsize=5.4, pad=1.5)
    ax.set_xlabel("Turn", fontsize=5.8, labelpad=2)
    ax.set_ylabel("Tool hit ($h$)", fontsize=5.8, labelpad=2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(fontsize=4.8, loc="lower left", frameon=True, framealpha=0.9,
              handlelength=1.2, handletextpad=0.3, borderpad=0.25, labelspacing=0.25)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig_turnwise_line.png", dpi=300, bbox_inches="tight")
    plt.savefig(FIGURES_DIR / "fig_turnwise_line.pdf", bbox_inches="tight")
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
    """Model size against tool hit, over the scored configurations.

    Size comes from the registry label, which names it for every configuration
    but four. Those four are here by name with the reason: three are mixtures of
    experts, where the axis is the active parameter count and not the total, and
    Phi-4-mini's label does not carry a size at all. A configuration whose size
    cannot be resolved is named on the console and left out of the figure rather
    than placed at a guessed x.
    """
    BY_NAME = {
        "kanana-2-inst": 3.0,     # 30B total, A3B active
        "kanana-2-think": 3.0,    # 30B total, A3B active
        "qwen36-35b-a3b": 3.0,    # 35B total, A3B active
        "phi-4-mini": 3.8,        # the label carries no size
    }
    THINKING = {"think", "effort_high", "always_on"}

    def size_of(config_id: str, label: str):
        if config_id in BY_NAME:
            return BY_NAME[config_id]
        found = re.findall(r"(\d+(?:\.\d+)?)\s*B\b", label)
        return float(found[-1]) if found else None

    cases = load.single()
    configs = load.configs()
    h_by_config = cases.groupby("config_id")["h"].mean()

    repro, unresolved = [], []
    for config_id, h in h_by_config.items():
        row = configs.loc[config_id]
        size = size_of(config_id, row["label"])
        if size is None:
            unresolved.append(config_id)
            continue
        marker = "^" if row["reasoning_mode"] in THINKING else (
            "v" if row["reasoning_mode"] == "nothink" or row["reasoning_mode"] == "effort_low"
            else "o")
        repro.append({"model": row["model"], "label": row["label"], "size": size,
                      "h_mean": float(h), "marker": marker})
    if unresolved:
        print(f"  size unresolved, left out: {', '.join(unresolved)}")
    print(f"  {_cohort_note()}")

    fig, ax = plt.subplots(figsize=(3.5, 2.7))

    # Collect (size, h) per family
    from collections import defaultdict
    family_points = defaultdict(list)
    for item in repro:
        family = get_family(item["model"])
        family_points[family].append((item["size"], item["h_mean"], item["marker"],
                                      item["label"]))

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

    # 부록에서 두 패널을 나란히(각 0.49\textwidth ≈ 2.7in) 둔다. tight bbox 후 폭이 약 2.7in가 되어 1:1로 찍힌다.
    fig, ax = plt.subplots(figsize=(2.8, 2.15))

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
    "multi_tool": "Multi-tool",  # includes generate_str (no separate cases_generate_str.json)
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

    # 부록에서 두 패널을 나란히(각 0.49\textwidth ≈ 2.7in) 둔다. tight bbox 후 폭이 약 2.7in가 되어 1:1로 찍힌다.
    fig, ax = plt.subplots(figsize=(2.8, 2.15))
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
# ═══════════════════════════════════════════════════════════════════
# Fig: Error modes — error type distribution + family x error heatmap (RQ4)
# ═══════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Generating new paper figures...")
    fig_turnwise_line()
    fig_question_length_boxplot()
    fig_difficulty_distribution()
    fig_param_complexity()
    fig_size_vs_performance()
    fig_tsne_semantic()
    fig_difficulty_distribution_summary()
    fig_question_length_boxplot_summary()
    fig_benchmark_composition_combined()
    print("Done!")
