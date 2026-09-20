#!/usr/bin/env python3
"""fig4_kr_en_scatter: per-configuration h with Korean questions against English questions.

Reads `_experiments/scripts/analysis/load.py` and nothing else from the results
trees. The two arms are `load.single()` and `load.single(column="krtools_enq")`.

Why that pair. Both arms serve the Korean tool schema, so the only thing that
differs between a point's x and its y is the language of the question, which is
what the figure claims to measure. `load.single()` is also the arm tab:overall
reports, so a point's x is the h the main table prints for that configuration.
Each arm is named for what varies in it, so the pairing is checkable rather than
remembered: `load.COLUMNS["krtools_enq"]` is ("kr", "en") against
`load.COLUMNS["single"]` ("kr", "kr").

The cohort is the serving registry, so there is nothing to exclude, and every
point is labelled from its registry `label` rather than a chosen few. Label
offsets alternate by rank so two adjacent points do not collide, and each label
keeps its leader line, which is what lets every point carry a name without an
offset table that has to be retuned whenever a point moves.

The English-question arm covers fewer configurations than the Korean one, so the
figure states next to the axes how many it draws and lists the configurations it
could not.

Output: _experiments/figures/fig4_kr_en_scatter.png (via _figure_out)
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Figures are written inside this repository only; the manuscript copy is one
# explicit step (_figure_out).
from _figure_out import install as _install_figure_out  # noqa: E402

from _experiments.scripts.analysis import load  # noqa: E402

SB_FIG = _install_figure_out()
OUT = SB_FIG / "fig4_kr_en_scatter.png"

KR_ARM = "single"          # Korean tool schema, Korean questions
EN_ARM = "krtools_enq"     # Korean tool schema, English questions


def collect() -> tuple[list[dict], list[str], int]:
    """One point per configuration scored in both arms, in registry order."""
    kr = load.single(column=KR_ARM).groupby("config_id")["h"].agg(["mean", "count"])
    en = load.single(column=EN_ARM).groupby("config_id")["h"].agg(["mean", "count"])
    registry = load.configs()

    rows = []
    for config_id in registry["config_id"]:
        if config_id not in kr.index or config_id not in en.index:
            continue
        rows.append({"config_id": config_id,
                     "label": str(registry.loc[config_id, "label"]),
                     "kr": float(kr.loc[config_id, "mean"]),
                     "en": float(en.loc[config_id, "mean"]),
                     "n_kr": int(kr.loc[config_id, "count"]),
                     "n_en": int(en.loc[config_id, "count"])})

    todo = load.missing()
    drawn = {row["config_id"] for row in rows}
    absent = [c for c in todo["config_id"] if c not in drawn]
    return rows, absent, int(len(registry))


LABEL_FONT = 6.3
LABEL_GAP_PT = 8.5      # a little over one line of LABEL_FONT


def _label_points(fig, ax, rows, kr_v, en_v, lo, hi) -> None:
    """Names every point, pushing labels apart instead of consulting a name table.

    A label goes inward, away from the axis edge and the colour bar, and the
    labels are spread vertically until they clear each other by one line. That is
    what lets every point carry a name without a table of per-model offsets that
    has to be retuned whenever a point moves. The spacing is read off the axes as
    they will be drawn, so `tight_layout` has to have run already.
    """
    dpi = fig.dpi
    pixels = ax.transData.transform(np.column_stack([kr_v, en_v]))
    gap = LABEL_GAP_PT * dpi / 72.0

    order = np.argsort(pixels[:, 1])
    spread = pixels[order, 1].astype(float).copy()
    for i in range(1, len(spread)):
        spread[i] = max(spread[i], spread[i - 1] + gap)
    # Re-centre, so pushing the crowded points apart does not drift the whole
    # block off one end of the axes.
    spread += ((pixels[order, 1].min() + pixels[order, 1].max())
               - (spread.min() + spread.max())) / 2.0

    middle = (lo + hi) / 2.0
    for rank, index in enumerate(order):
        inward_left = kr_v[index] > middle
        dx = -9.0 if inward_left else 9.0
        dy = (spread[rank] - pixels[index, 1]) * 72.0 / dpi
        ax.annotate(rows[index]["label"], (kr_v[index], en_v[index]),
                    fontsize=LABEL_FONT, color="#111", fontweight="bold",
                    xytext=(dx, dy), textcoords="offset points",
                    ha="right" if inward_left else "left", va="center", zorder=6,
                    arrowprops=dict(arrowstyle="-", lw=0.5, color="#777",
                                    shrinkA=1, shrinkB=3))


def main() -> int:
    rows, absent, total = collect()
    if not rows:
        raise SystemExit(f"no configuration is scored in both {KR_ARM!r} and {EN_ARM!r}")

    kr_v = np.array([row["kr"] for row in rows])
    en_v = np.array([row["en"] for row in rows])
    mean_h = (kr_v + en_v) / 2.0           # colour = how well the pair does overall
    norm = mcolors.Normalize(vmin=mean_h.min(), vmax=mean_h.max())

    fig, ax = plt.subplots(figsize=(3.8, 3.15))
    sc = ax.scatter(kr_v, en_v, c=mean_h, cmap="viridis", norm=norm,
                    s=52, edgecolors="white", linewidths=0.6, zorder=4)
    cbar = fig.colorbar(sc, ax=ax, fraction=0.036, pad=0.015, shrink=0.7)
    cbar.set_label(r"mean $h$", fontsize=7)
    cbar.ax.tick_params(labelsize=6)
    cbar.outline.set_linewidth(0.4)

    lo = min(kr_v.min(), en_v.min()) - 0.04
    hi = max(kr_v.max(), en_v.max()) + 0.04
    ax.plot([lo, hi], [lo, hi], "--", color="gray", linewidth=0.9,
            label=r"$h_{\mathrm{KR}}{=}h_{\mathrm{EN}}$", zorder=1)

    ax.set_xlabel(r"$h_{\mathrm{KR}}$ (Korean question)", fontsize=9)
    ax.set_ylabel(r"$h_{\mathrm{EN}}$ (English question)", fontsize=9)
    ax.tick_params(axis="both", labelsize=8)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.legend(fontsize=7.5, loc="lower right", frameon=False)
    ax.grid(True, alpha=0.22)

    ax.set_title(f"{len(rows)} of {total} configurations, Korean tool schema on both axes",
                 fontsize=7.5, pad=4)

    plt.tight_layout()
    _label_points(fig, ax, rows, kr_v, en_v, lo, hi)

    if absent:
        note = "both arms not scored yet: " + ", ".join(absent)
        fig.text(0.0, -0.02, "\n".join(textwrap.wrap(note, 78)),
                 fontsize=4.2, color="#666666", va="top", ha="left")

    plt.savefig(OUT, dpi=300, bbox_inches="tight")
    plt.close()

    delta = kr_v - en_v
    print(f"Saved {OUT}")
    print(f"n_configs={len(rows)} of {total}; x={KR_ARM} (kr tools, kr questions), "
          f"y={EN_ARM} (kr tools, en questions)")
    print("both arms not scored yet: " + (", ".join(absent) or "none"))
    print(f"n={len(rows)} KR={kr_v.mean():.4f} EN={en_v.mean():.4f} "
          f"gap={(kr_v.mean() - en_v.mean()) * 100:.1f}pp "
          f"KRadv={int((delta > 0).sum())} ENadv={int((delta < 0).sum())}")
    for row in rows:
        print(f"  {row['config_id']:<16s} kr={row['kr']:.4f} (n={row['n_kr']})  "
              f"en={row['en']:.4f} (n={row['n_en']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
