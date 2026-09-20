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
# Two lines, because four sub-domain names do not fit across a column at one line.
SHORT = {"Transaction Inquiry & Statistics": "Txn Inquiry\n& Statistics",
         "Suspicious Activity Detection": "Suspicious\nDetection",
         "Money Flow & Network Analysis": "Money Flow\n& Network",
         "Regulatory Reporting": "Regulatory\nReporting"}
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

    fig, ax = plt.subplots(figsize=(5.5, 2.3))
    x = np.arange(len(subdomains))
    width = 0.19
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
    ax.set_xticklabels([SHORT.get(sd, sd) for sd in subdomains], fontsize=6.5,
                       linespacing=1.15)
    ax.set_ylabel("Tool hit $h$", fontsize=7.5)
    ax.set_ylim(0, 1.08)
    ax.tick_params(axis="y", labelsize=6.5)
    ax.tick_params(axis="x", length=0, pad=2)
    ax.legend(fontsize=6, ncol=2, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.22), handlelength=1.4, columnspacing=1.2)
    ax.text(0.99, 0.97, "shaded: both pairs decline", transform=ax.transAxes,
            ha="right", va="top", fontsize=5.8, color="#A0554F")
    style_axes(ax)
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
