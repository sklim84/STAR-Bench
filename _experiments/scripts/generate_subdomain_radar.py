"""Intro teaser: per-sub-domain tool-hit radar for four representative configurations.

Each axis is one of the four AML sub-domains (tab:tool_suite); each polygon is one
configuration's mean tool hit `h` over the tools in that sub-domain. The point is
that AML competence is multi-dimensional and configuration-specific, with the
Regulatory Reporting axis the most divergent.

The metric is `h`, the primary tool hit (0/1): whether the configuration reached
for the right tool on the case. A sub-domain value is the unweighted mean over
its tools' category means.

Which four are drawn is a rule rather than a list of names, so the figure follows
the registry instead of failing whenever a named model is not in the results:

    the highest-h configuration of each registry `group`, plus the lowest-h
    configuration in the cohort

so the polygons are the best of each kind the registry distinguishes
(General-Purpose, Korean-Specialized, Finance-Specialized) against the weakest
configuration overall, which is what makes the spread on the Regulatory Reporting
axis visible. Ranking is by overall single-turn `h`. If the weakest is already a
group leader the next weakest is taken, and if the registry ever holds more
groups than the radar can carry, the groups are taken in descending leader order.
The chosen ids and their ranks are printed on every run, and the figure says how
many of the registry's configurations are scored.

`SUBDOMAINS` below is the manuscript's tool mapping rather than a cohort list; a
member tool with no `category` in `load.single()` is reported. Figures are
written inside this repository only; copying into the manuscript is one explicit
step (_figure_out).

Outputs
    _experiments/figures/fig_subdomain_radar.{png,pdf}
"""
import statistics as st
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_SB = Path(__file__).resolve().parents[2]   # repository root
for _p in (str(Path(__file__).resolve().parent), str(_SB)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _figure_out import install as _install_figure_out  # noqa: E402
from _experiments.scripts.analysis import load  # noqa: E402

SB_FIG = _install_figure_out()
OUT = Path(__file__).resolve().parent / "fig_subdomain_radar.png"

# Four AML subdomains -> member tools (matches tab:tool_suite); generate_str excluded (multi-turn only)
SUBDOMAINS = {
    "Txn\nInquiry": ["get_statistics", "query_transactions", "get_account_profile",
                     "compare_periods", "get_institution_report", "get_fraud_type_summary",
                     "get_receiving_account_profile"],
    "Suspicious\nDetection": ["predict_fraud", "rank_risky_transactions",
                              "score_account_risk", "detect_monitoring_alerts"],
    "Money Flow\n& Network": ["analyze_network", "detect_aml_patterns", "detect_smurfing_network",
                              "detect_dormant_reactivation", "analyze_cross_institution_flow",
                              "get_trend_analysis", "analyze_channel_risk"],
    "Regulatory\nReporting": ["detect_ctr_candidates", "lookup_fiu_reference_types",
                              "validate_str_fields", "get_aml_glossary"],
}

N_POLYGONS = 4   # four polygons is what the 0.38\textwidth teaser stays legible at

import matplotlib as _mplD  # 색감 통일: 4 archetype 라인을 viridis(blue->green->yellow)에서 샘플
_VIRD = _mplD.colormaps["viridis"]
COLORS = [_VIRD(v) for v in (0.25, 0.50, 0.72, 0.90)]


def cohort_note():
    """(n_configs, missing ids, one line saying so) for the scored cohort."""
    todo = load.missing()
    missing = sorted(todo.loc[~todo["single"], "config_id"])
    n_total = len(todo)
    n_scored = n_total - len(missing)
    return n_scored, missing, n_total, f"{n_scored} of {n_total} configurations scored"


def choose(overall):
    """The configurations to draw: each group's leader, then the weakest overall.

    `overall` is one row per configuration, sorted by `h` descending. Selection is
    by registry `group` and by the metric, never by a name (rule 3).
    """
    chosen, why = [], {}
    for _group, block in sorted(overall.groupby("group"),
                                key=lambda kv: -kv[1]["h"].max()):
        leader = block.iloc[0]          # `overall` is already sorted by h descending
        if len(chosen) >= N_POLYGONS - 1:
            break
        chosen.append(leader["config_id"])
        why[leader["config_id"]] = f"highest h in group {leader['group']}"
    for _, row in overall.iloc[::-1].iterrows():        # weakest first
        if len(chosen) >= N_POLYGONS:
            break
        if row["config_id"] not in chosen:
            chosen.append(row["config_id"])
            why[row["config_id"]] = "lowest h in the cohort"
    return chosen, why


def load_profiles():
    cases = load.single()
    per_cat = (cases.groupby(["config_id", "label", "group", "category"])
                    .agg(h_mean=("h", "mean"), n_cases=("h", "size")).reset_index())
    present = set(per_cat["category"])
    tools_missing = {sd: [t for t in tools if t not in present]
                     for sd, tools in SUBDOMAINS.items()}

    overall = (cases.groupby(["config_id", "label", "group"])["h"].mean()
                    .reset_index().sort_values("h", ascending=False).reset_index(drop=True))
    if overall.empty:
        raise SystemExit("no scored configuration in the single-turn column")
    chosen, why = choose(overall)

    prof = {}
    for config_id, color in zip(chosen, COLORS):
        block = per_cat[per_cat["config_id"] == config_id]
        by_tool = dict(zip(block["category"], block["h_mean"]))
        vals = []
        for _sd, tools in SUBDOMAINS.items():
            hits = [by_tool[t] for t in tools if t in by_tool]
            vals.append(st.mean(hits) if hits else 0.0)
        label = block["label"].iloc[0]
        prof[label] = (vals, color)
        why[label] = why.pop(config_id)
    return prof, why, tools_missing, overall


def main():
    n_configs, missing, n_total, note = cohort_note()
    prof, why, tools_missing, overall = load_profiles()
    axes = list(SUBDOMAINS.keys())
    N = len(axes)
    ang = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    ang += ang[:1]

    # 본문에는 폭 0.38\textwidth(약 2.1in) wrapfigure로 들어간다. bbox_inches="tight"로 잘린 뒤
    # 폭이 약 2.1in가 되어 1:1로 찍힌다. 글자는 5~7pt, 범례는 레이더 아래 2열.
    fig, ax = plt.subplots(figsize=(2.45, 2.55), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi / 2 + np.pi / 4)   # rotate 45deg: 4 axes at corners
    ax.set_theta_direction(-1)              # clockwise
    for disp, (vals, color) in prof.items():
        vv = vals + vals[:1]
        ax.plot(ang, vv, color=color, linewidth=1.0, marker="o", markersize=2.2,
                markeredgecolor="white", markeredgewidth=0.3, label=disp, zorder=3)
        ax.fill(ang, vv, color=color, alpha=0.06, zorder=2)

    ax.set_xticks(ang[:-1])
    ax.set_xticklabels(axes, fontsize=7)
    ax.tick_params(axis="x", pad=4)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels([".25", ".5", ".75", "1"], fontsize=5, color="#888888")
    ax.set_rlabel_position(90)
    ax.spines["polar"].set_color("#cccccc")
    ax.spines["polar"].set_linewidth(0.8)
    ax.grid(color="#d0d0d0", alpha=0.9, linewidth=0.5)
    ax.set_facecolor("#f0f3f7")  # radar 원에 옅은 바탕색
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2,
              fontsize=7, frameon=False, handletextpad=0.4,
              handlelength=1.2, labelspacing=0.35, columnspacing=1.0)
    # Rule 4: the four polygons are picked out of a cohort that is not yet whole,
    # and the figure says so rather than leaving it to the caption.
    fig.text(0.5, 1.0, f"{note}, {len(prof)} shown", ha="center", va="top",
             fontsize=5, color="#888888")
    plt.tight_layout()
    plt.savefig(OUT, dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.savefig(str(OUT).replace(".png", ".pdf"), bbox_inches="tight", pad_inches=0.02)
    plt.close()
    print(f"Saved {OUT.stem}.{{png,pdf}} -> {SB_FIG}")
    print(f"n_configs={n_configs} of {n_total}; "
          f"missing: {', '.join(missing) if missing else 'none'}")
    print(f"drawn ({len(prof)} of {n_configs} scored), axes: "
          + " ".join(a.replace(chr(10), ' ') for a in axes))
    for disp, (vals, _) in prof.items():
        print(f"  {disp:24s} " + " ".join(f"{v:.3f}" for v in vals) + f"   [{why[disp]}]")
    for sd, tools in tools_missing.items():
        if tools:
            print(f"  sub-domain tool with no category: {sd!r}: {', '.join(tools)}")


if __name__ == "__main__":
    main()
