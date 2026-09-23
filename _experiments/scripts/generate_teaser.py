"""The opening figure: single-turn tool hit against workflow completion.

The figure carries the result the paper leads with: single-turn tool accuracy
does not predict workflow completion.

One point per scored configuration. The shaded band marks the configurations
within seven points of one another on single-turn tool hit, whose completion
rates still span thirty points; that band is the claim, so it is drawn rather
than described.

    python -m _experiments.scripts.generate_teaser
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent.parent
sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_ROOT))

from _figure_out import install as _install_figure_out  # noqa: E402
from _experiments.scripts.analysis import load  # noqa: E402

FIG = _install_figure_out()
BAND_LOW, BAND_HIGH = 0.90, 0.97
import matplotlib as _mpl  # 그림 전체가 viridis 한 계열에서 색을 뽑는다
_VIR = _mpl.colormaps["viridis"]
# Colour carries the two claims, so the figure needs no legend. The configurations
# in the band are drawn dark blue and the 30-point arrow and its label share that
# colour; the configuration that completes the most workflows is green, and so is
# its label; everything else is grey context. The green is viridis(0.62) darkened
# to 5.1:1 contrast on white so its label stays legible at 6.5 pt; the blue is
# 7.6:1. The three also keep distinct lightness in greyscale print.
BAND_COLOUR = _VIR(0.25)
LEADER_COLOUR = "#1b7d5d"
OTHER_COLOUR = "#C4C4CC"
# The one configuration named in the figure: it completes the most workflows while
# sitting in the lower half on single-turn tool hit (17th of 28).
LABELLED = "mistral-small"


def main() -> int:
    cases = load.single()
    oracle = load.aggregates("oracle")
    configs = load.configs()
    rows = []
    for config_id, group in cases.groupby("config_id"):
        if config_id not in oracle:
            continue
        rows.append((config_id, float(group["h"].mean()),
                     float(oracle[config_id]["c"]["mean"]),
                     configs.loc[config_id, "label"], configs.loc[config_id, "group"]))
    if not rows:
        raise SystemExit("no configuration is scored in both settings")

    missing = load.missing()
    absent = missing.loc[~missing["single"], "config_id"].tolist()

    # Drawn 1:1 for the 0.45\\textwidth wrapfigure (about 179 pt), so the type sizes
    # above are the sizes on the page.
    fig, ax = plt.subplots(figsize=(2.37, 1.9))
    ax.axvspan(BAND_LOW, BAND_HIGH, color="#E4E4EA", linewidth=0, zorder=1)
    ranked = sorted(rows, key=lambda r: -r[1])
    for config_id, h, c, label, group in rows:
        inside = BAND_LOW <= h <= BAND_HIGH
        colour = LEADER_COLOUR if config_id == LABELLED else BAND_COLOUR if inside else OTHER_COLOUR
        ax.scatter(h, c, s=20, zorder=4 if colour != OTHER_COLOUR else 3, linewidths=0.5,
                   edgecolors="white", color=colour)
    for config_id, h, c, label, group in rows:
        if config_id != LABELLED:
            continue
        rank = [r[0] for r in ranked].index(config_id) + 1
        ax.annotate(f"{label}\nhighest $c$, {rank}th on $h$", (h, c),
                    textcoords="offset points", xytext=(-5, 0), ha="right", va="center",
                    fontsize=6.5, color=LEADER_COLOUR, linespacing=1.15)

    band = [r for r in rows if BAND_LOW <= r[1] <= BAND_HIGH]
    if band:
        low, high = min(r[2] for r in band), max(r[2] for r in band)
        x = BAND_HIGH + 0.018
        ax.annotate("", xy=(x, low), xytext=(x, high),
                    arrowprops=dict(arrowstyle="<->", color=BAND_COLOUR, linewidth=0.8,
                                    shrinkA=0, shrinkB=0))
        ax.text(x + 0.012, (low + high) / 2, f"{100 * (high - low):.0f} pts",
                fontsize=7, va="center", ha="left", color=BAND_COLOUR)

    ax.set_xlabel("Single-turn tool hit $h$", fontsize=7.5, labelpad=2)
    ax.set_ylabel("Workflow completion $c$", fontsize=7.5, labelpad=2)
    ax.tick_params(labelsize=7, length=2, pad=1.5)
    ax.set_xlim(min(r[1] for r in rows) - 0.04, 1.09)
    ax.set_xticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_ylim(-0.02, 0.85)
    ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8])
    ax.spines[["top", "right"]].set_visible(False)
    for spine in ax.spines.values():
        spine.set_linewidth(0.6)
    fig.tight_layout(pad=0.3)
    for suffix in ("pdf", "png"):
        fig.savefig(FIG / f"fig_teaser_single_vs_workflow.{suffix}", dpi=300,
                    bbox_inches="tight")
    plt.close(fig)

    print(f"Saved fig_teaser_single_vs_workflow.{{pdf,png}} -> {FIG}")
    print(f"  {len(rows)} configurations; band {BAND_LOW}-{BAND_HIGH} holds {len(band)}, "
          f"completion {min(r[2] for r in band):.2f} to {max(r[2] for r in band):.2f}")
    if absent:
        print(f"  not scored ({len(absent)}): {', '.join(absent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
