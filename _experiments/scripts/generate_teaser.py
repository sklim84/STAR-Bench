"""The opening figure: single-turn tool hit against workflow completion.

The figure carries the result the paper leads with: single-turn tool accuracy
does not predict workflow completion.

One point per scored configuration. The shaded band marks the configurations
within six points of one another on single-turn tool hit, whose completion rates
still span thirty points; that band is the claim, so it is drawn rather than
described.

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
# 세 그룹을 viridis 위에서 충분히 떨어뜨려 뽑는다. 흑백 인쇄에서도 명도 순서가
# 유지되도록 어두운 쪽부터 General, Korean, Finance 순으로 둔다.
GROUP_COLOR = {"General-Purpose": _VIR(0.15), "Korean-Specialized": _VIR(0.50),
               "Finance-Specialized": _VIR(0.80)}
# One label only. At 2.1 inches three model names of this length cannot sit near
# their points without covering others, and the band and the arrow already carry
# the claim. The one worth naming is the configuration that completes the most
# workflows while sitting in the lower half on single-turn tool hit (17th of 28).
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

    fig, ax = plt.subplots(figsize=(2.5, 2.0))
    ax.axvspan(BAND_LOW, BAND_HIGH, color="#BBBBBB", alpha=0.22, linewidth=0, zorder=1)
    for config_id, h, c, label, group in rows:
        ax.scatter(h, c, s=22, zorder=3, linewidths=0.4, edgecolors="white",
                   color=GROUP_COLOR.get(group, "#888888"))
    for config_id, h, c, label, group in rows:
        if config_id != LABELLED:
            continue
        ax.annotate(f"{label}\nbest workflow,\n17th of {len(rows)} on $h$", (h, c),
                    textcoords="offset points", xytext=(4, 16), ha="left", va="bottom",
                    fontsize=5.0, color="#333333", linespacing=1.25,
                    arrowprops=dict(arrowstyle="-", color="#999999", linewidth=0.5,
                                    shrinkA=0, shrinkB=2))

    band = [r for r in rows if BAND_LOW <= r[1] <= BAND_HIGH]
    if band:
        low, high = min(r[2] for r in band), max(r[2] for r in band)
        ax.annotate("", xy=(BAND_HIGH + 0.004, low), xytext=(BAND_HIGH + 0.004, high),
                    arrowprops=dict(arrowstyle="<->", color="#666666", linewidth=0.7))
        ax.text(BAND_HIGH + 0.009, (low + high) / 2, f"{100 * (high - low):.0f} pts",
                fontsize=5.2, rotation=90, va="center", ha="left", color="#666666")

    ax.set_xlabel("Single-turn tool hit $h$", fontsize=6.5)
    ax.set_ylabel("Workflow completion $c$", fontsize=6.5)
    ax.tick_params(labelsize=5.8, length=2, pad=1.5)
    ax.set_xlim(min(r[1] for r in rows) - 0.02, max(r[1] for r in rows) + 0.035)
    ax.set_ylim(0, max(r[2] for r in rows) * 1.45)
    ax.spines[["top", "right"]].set_visible(False)
    for spine in ax.spines.values():
        spine.set_linewidth(0.6)
    # Inside the axes at the foot: a title here would sit under the annotation.
    ax.text(0.02, 0.03, f"{len(rows)} of {len(missing)} configurations",
            transform=ax.transAxes, fontsize=5.0, color="#888888",
            ha="left", va="bottom")
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
