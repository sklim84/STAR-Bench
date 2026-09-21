#!/usr/bin/env python3
"""Each finance fine-tune against the model it was tuned from, per sub-domain.

The claim this figure carries is pairwise: finance tuning moves capability
between sub-domains rather than adding it, and Regulatory Reporting is the one
sub-domain where both pairs lose. A figure of group means cannot show that,
because the three groups hold two, six and twenty configurations of different
sizes, so a difference between them is mostly a difference in what is in them.

Reads `results_RQ5/finance_specialization.json`, which the step beside this one
writes; run that first.

    python -m _experiments.scripts.RQ5_subdomain_grouped_bar
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

_SB = Path(__file__).resolve().parents[2]
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from _plot_style import FS_TICK, FS_LABEL, FS_LEGEND, style_axes  # noqa: E402

OUT_DIR = _SB / "_experiments" / "results_RQ5"
SPEC_FILE = OUT_DIR / "finance_specialization.json"
# One short word per sub-domain: four full names do not fit across a wrapfigure,
# and the caption gives them in full.
SHORT = {"Transaction Inquiry & Statistics": "Inquiry",
         "Suspicious Activity Detection": "Detection",
         "Money Flow & Network Analysis": "Network",
         "Regulatory Reporting": "Reporting"}
BASE_COLOUR, FINE_COLOUR = "#A9C0D6", "#2A6099"


def main() -> int:
    if not SPEC_FILE.exists():
        raise SystemExit(f"{SPEC_FILE} does not exist; run RQ5_finance_specialization.py first")
    spec = json.loads(SPEC_FILE.read_text(encoding="utf-8"))
    base = spec.get("base_comparison") or {}
    if not base.get("available"):
        raise SystemExit("base_comparison is not available: score the base models first")

    pairs = base["pairs"]
    subdomains = list(spec["sub_domains"])
    declines = set(base["subdomains_where_every_pair_declines"])

    # Drawn 1:1 for a 0.42\\textwidth wrapfigure, so nothing is scaled at use.
    fig, ax = plt.subplots(figsize=(2.35, 1.58))
    x = np.arange(len(subdomains))
    width = 0.20
    for slot, (fine_id, pair) in enumerate(pairs.items()):
        centre = (slot - (len(pairs) - 1) / 2) * (2 * width + 0.07)
        for j, which in enumerate(("base", "fine")):
            values = [pair["by_subdomain"][sd][which] or 0 for sd in subdomains]
            ax.bar(x + centre + (j - 0.5) * width, values, width,
                   color=BASE_COLOUR if which == "base" else FINE_COLOUR,
                   edgecolor="white", linewidth=0.5,
                   label=(pair["base_label"] if which == "base" else pair.get("fine_label", fine_id))
                   if slot < len(pairs) else None)
    for k, sd in enumerate(subdomains):
        if sd in declines:
            ax.axvspan(k - 0.46, k + 0.46, color="#D9534F", alpha=0.07, linewidth=0, zorder=0)

    ax.set_xticks(x)
    ax.set_xticklabels([SHORT.get(sd, sd) for sd in subdomains], fontsize=5.2)
    ax.set_ylabel("Tool hit $h$", fontsize=5.6)
    ax.set_ylim(0, 1.12)
    ax.tick_params(axis="y", labelsize=5, pad=1.5)
    ax.tick_params(axis="x", length=0, pad=2)
    # Four entries as two pairs: each row is one base-and-fine-tune pair, which is
    # the comparison the bars make, and it costs half the vertical space.
    ax.legend(fontsize=4.2, ncol=2, frameon=False, loc="lower left",
              bbox_to_anchor=(-0.02, -0.28), handlelength=0.9,
              labelspacing=0.18, columnspacing=0.6, borderpad=0.1)
    ax.text(0.99, 0.99, "shaded: both pairs decline", transform=ax.transAxes,
            ha="right", va="top", fontsize=4.2, color="#A0554F")
    style_axes(ax)
    # style_axes sets a shared tick size; this figure is drawn small, so it keeps its own.
    ax.tick_params(axis="y", labelsize=5, pad=1.5)
    ax.tick_params(axis="x", labelsize=5.2, length=0, pad=2)
    fig.tight_layout()
    for suffix in ("pdf", "png"):
        fig.savefig(OUT_DIR / f"fig_subdomain_grouped_bar.{suffix}", dpi=300, bbox_inches="tight")
    plt.close(fig)

    print(f"Saved fig_subdomain_grouped_bar to {OUT_DIR}")
    for fine_id, pair in pairs.items():
        print(f"  {pair['base_label']} -> {fine_id}: "
              + ", ".join(f"{SHORT.get(sd, sd)} "
                          f"{100 * (pair['by_subdomain'][sd]['delta'] or 0):+.1f}"
                          for sd in subdomains))
    print("  every pair declines in: " + (", ".join(sorted(declines)) or "no sub-domain"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
