"""fig:reg_vs_anal - the regulatory vs. analysis tool-hit dumbbell (single column).

One vertical dumbbell per configuration: the analysis-tool mean h and the
regulatory-tool mean h joined by a thin segment, configurations sorted by the
analysis mean. A dumbbell rather than two lines, because a line across
categorical models invents a continuity that is not there.

The metric is `h`, the primary tool hit (0/1). The pre-audit figure read
`by_category[t].aggregated.primary_tool_hit_rate`, a key that is gone with the
weighted score it sat beside (D02); `h` is the same quantity under the scorer's
own name (PORTING rule 1).

Regulatory Reporting is four single-turn tools: STR-field validation,
CTR-candidate detection, FIU reference-type lookup and AML glossary lookup.
`generate_str` is in the subdomain but is multi-turn only, so no single-turn
category carries it. `multi_tool` and `missing_parameters` are case groups, not
tools, and sit on neither side. Each side is the unweighted mean over its
category means, the definition the manuscript states.

The cohort is the serving registry through `load.single()`; the `EXCLUDE` and
`NAME` literals are gone (rule 3) and the display name is the registry `label`.
The figure states how many of the 28 configurations it draws, and the run prints
the ids that are missing, so the caption cannot claim 28 while the plot shows
fewer (rule 4).

Figures are written inside this repository only; copying into the manuscript is
one explicit step (_figure_out, R2C-007).

Outputs
    _experiments/figures/fig_regulatory_vs_analysis_v2.{png,pdf}
"""
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
OUT = Path(__file__).resolve().parent   # _figure_out redirects savefig by file name

# Regulatory Reporting subdomain (single-turn tools; generate_str is multi-turn only)
REG = {"detect_ctr_candidates", "lookup_fiu_reference_types",
       "validate_str_fields", "get_aml_glossary"}
# Not tools: synthetic case groups, on neither side.
SPECIAL = {"multi_tool", "missing_parameters"}

import matplotlib as _mpl  # 색감 통일: viridis 2색 (analysis=blue, regulatory=green)  # noqa: E402
_VIR = _mpl.colormaps["viridis"]
C_ANA, C_REG = _VIR(0.25), _VIR(0.72)


def cohort_note():
    """(n_configs, missing ids, one line saying so) for the scored cohort."""
    todo = load.missing()
    missing = sorted(todo.loc[~todo["single"], "config_id"])
    n_total = len(todo)
    return n_total - len(missing), missing, n_total


def main():
    n_configs, missing, n_total = cohort_note()

    cases = load.single()
    per_cat = (cases.groupby(["config_id", "label", "category"])
                    .agg(h_mean=("h", "mean"), n_cases=("h", "size")).reset_index())
    per_cat = per_cat[~per_cat["category"].isin(SPECIAL)]

    rows = []
    for (_config_id, label), block in per_cat.groupby(["config_id", "label"], sort=False):
        reg_block = block[block["category"].isin(REG)]
        ana_block = block[~block["category"].isin(REG)]
        if reg_block.empty or ana_block.empty:
            continue
        rows.append((label, float(reg_block["h_mean"].mean()), float(ana_block["h_mean"].mean()),
                     int(reg_block["n_cases"].sum()), int(ana_block["n_cases"].sum())))

    rows.sort(key=lambda r: r[2])  # sort by analysis h ascending
    labels = [r[0] for r in rows]
    reg = np.array([r[1] for r in rows])
    ana = np.array([r[2] for r in rows])
    n_reg_cases = sum(r[3] for r in rows)
    n_ana_cases = sum(r[4] for r in rows)
    x = np.arange(len(rows))

    # 부록 전폭(5.5in)에 1:1로 들어가도록 그린다. tight bbox 후 폭이 약 5.5in이므로
    # LaTeX에서 확대·축소 없이 눈금·범례 글자가 설정한 크기(6~8pt)로 찍힌다.
    fig, ax = plt.subplots(figsize=(5.6, 2.4))
    ax.vlines(x, reg, ana, color="#BBBBBB", lw=0.9, zorder=1)
    ax.scatter(x, ana, s=16, color=C_ANA, zorder=3, label="Analysis tools")
    ax.scatter(x, reg, s=16, color=C_REG, marker="s", zorder=3, label="Regulatory tools")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=90, ha="center", fontsize=6.5)
    ax.tick_params(axis="y", labelsize=8)
    ax.set_ylabel("Mean tool hit $h$", fontsize=8)
    # Rule 4: the cohort is on the figure, so a caption cannot claim 28 rows while
    # the plot draws fewer.
    ax.set_title(f"{len(rows)} of {n_total} configurations scored", fontsize=6.5,
                 loc="left", color="#555555", pad=3)
    # The limits follow the data: a fixed 0.95 top clipped the highest marker
    # (Gemma-4-31B analysis h = .955) in half (L6-048).
    low = min(reg.min(), ana.min())
    high = max(reg.max(), ana.max())
    pad = max(0.02, (high - low) * 0.08)
    ax.set_ylim(max(0.0, low - pad), min(1.0, high + pad))
    ax.set_xlim(-0.7, len(rows) - 0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(fontsize=6, loc="lower right", frameon=True, framealpha=0.9,
              markerscale=0.9, handletextpad=0.3, borderpad=0.3)

    plt.tight_layout()
    plt.savefig(OUT / "fig_regulatory_vs_analysis_v2.png", dpi=300, bbox_inches="tight")
    plt.savefig(OUT / "fig_regulatory_vs_analysis_v2.pdf", bbox_inches="tight")
    plt.close()
    print(f"Saved fig_regulatory_vs_analysis_v2.{{png,pdf}} -> {SB_FIG}")
    print(f"n_configs={len(rows)} of {n_total}; "
          f"missing: {', '.join(missing) if missing else 'none'}")
    print(f"reg={reg.mean():.3f} (n={n_reg_cases} cases) ana={ana.mean():.3f} "
          f"(n={n_ana_cases} cases) gap={(ana.mean() - reg.mean()) * 100:.1f}pp; "
          f"worse on regulatory: {int((ana > reg).sum())}/{len(rows)}")


if __name__ == "__main__":
    main()
