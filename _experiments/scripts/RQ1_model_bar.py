#!/usr/bin/env python3
"""RQ1 figure: tool hit h and parameter accuracy a, one pair of bars per configuration.

Reads `_experiments/scripts/analysis/load.py` and nothing else from the results
trees. The arm is `load.single()`, the Korean tool schema with Korean questions.

The cohort is the serving registry through `load.configs()`, so the bar count and
the title come from one number and cannot disagree about which models the reader
is looking at, and a configuration cannot enter the sort by appearing in a
directory. `load.missing()` names the configurations that are not scored yet in a
note under the axes. The display name is the registry `label`, which is the name
tab:overall prints.

`h` is a mean over every case. `a` is a mean over the cases that have parameter
checks, because `a` is undefined where there is nothing to check: counting it as
1.0 would lift the `a` bar of a model that called tools with no checkable
arguments. The per-configuration counts are printed to stdout next to each bar's
value, so a short `a` bar can be read against the number of cases it covers.

The bars are sorted by `h` because this figure is about the ranking; the tables
keep the registry order.

Output: _experiments/results_RQ1/fig_model_bar.{pdf,png}
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _plot_style import (  # noqa: E402
    FS_ANNOT, FS_LABEL, FS_LEGEND, FS_TICK, FS_TITLE, get_color, style_axes,
)

from _experiments.scripts.analysis import load  # noqa: E402

OUT_DIR = _ROOT / "_experiments" / "results_RQ1"

# The family a colour stands for, keyed by the vendor prefix of the registry
# `model`. It is a legend caption, not a cohort: a vendor that is not listed
# falls through to its own prefix.
FAMILY = {
    "Qwen": "Qwen", "LGAI-EXAONE": "EXAONE", "skt": "A.X",
    "mistralai": "Mistral", "meta-llama": "Llama",
    "Salesforce": "xLAM", "DragonLLM": "Finance SFT",
    "NousResearch": "Hermes", "microsoft": "Phi",
    "google": "Gemma", "openai": "gpt-oss",
    "kakaocorp": "Kanana",
}


def collect() -> tuple[list[dict], list[str], int]:
    """One entry per scored configuration, sorted by h, plus the missing ids."""
    cases = load.single()
    registry = load.configs()
    rows = []
    for config_id in registry["config_id"]:
        subset = cases[cases["config_id"] == config_id]
        if subset.empty:
            continue
        a_defined = subset["a"].dropna()
        rows.append({
            "config_id": config_id,
            "label": registry.loc[config_id, "label"],
            "model": registry.loc[config_id, "model"],
            "h": float(subset["h"].mean()), "n_h": int(subset["h"].notna().sum()),
            "a": float(a_defined.mean()) if len(a_defined) else float("nan"),
            "n_a": int(len(a_defined)),
        })
    rows.sort(key=lambda row: row["h"])          # ascending, for a horizontal bar
    todo = load.missing()
    absent = todo.loc[~todo["single"], "config_id"].tolist()
    return rows, absent, int(len(registry))


def main() -> int:
    rows, absent, total = collect()
    n = len(rows)

    labels = [row["label"] for row in rows]
    h_vals = [row["h"] for row in rows]
    a_vals = [row["a"] for row in rows]
    colors = [get_color(row["model"]) for row in rows]

    y = np.arange(n)
    bar_h = 0.38

    fig, ax = plt.subplots(figsize=(7.5, 6.8))
    bars_h = ax.barh(y + bar_h / 2, h_vals, bar_h, color=colors, alpha=0.92,
                     label="$h$ (tool hit)")
    ax.barh(y - bar_h / 2, a_vals, bar_h, color=colors, alpha=0.45,
            label="$a$ (param acc.)", hatch="///")

    for bar, value in zip(bars_h, h_vals):
        ax.text(value + 0.005, bar.get_y() + bar.get_height() / 2,
                f"{value:.3f}", va="center", ha="left", fontsize=FS_ANNOT - 1)

    ax.axvline(0.5, color="#999999", linewidth=0.8, linestyle="--", alpha=0.6)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=FS_TICK)
    ax.set_xlabel("Score", fontsize=FS_LABEL)
    ax.set_xlim(0, 1.08)
    style_axes(ax)

    seen = set()
    handles = []
    for row in rows:
        family = FAMILY.get(row["model"].split("/")[0], row["model"].split("/")[0])
        if family not in seen:
            seen.add(family)
            handles.append(mpatches.Patch(color=get_color(row["model"]), label=family))
    handles += [
        mpatches.Patch(facecolor="#AAAAAA", alpha=0.92, label="$h$ (tool hit)"),
        mpatches.Patch(facecolor="#AAAAAA", alpha=0.45, hatch="///", label="$a$ (param acc.)"),
    ]
    # Below the axes rather than inside them. Every bar starts at zero, so the
    # only clear space inside is past the shortest bars, and that is where their
    # value annotations sit: an inset legend hid the three lowest scores.
    ax.legend(handles=handles, fontsize=FS_LEGEND, loc="upper center",
              bbox_to_anchor=(0.5, -0.085), ncol=5, frameon=False,
              columnspacing=0.8, handlelength=1.2)

    ax.set_title(
        f"Tool hit $h$ and parameter accuracy $a$, {n} of {total} configurations\n"
        "(Korean tool schema, Korean questions; sorted by $h$)",
        fontsize=FS_TITLE, pad=6,
    )

    fig.tight_layout()

    if absent:
        note = ("Not scored yet, so not drawn (" + str(len(absent)) + " of "
                + str(total) + "): " + ", ".join(absent))
        fig.text(0.01, -0.055, "\n".join(textwrap.wrap(note, 110)),
                 fontsize=FS_ANNOT - 1, color="#555555", va="top", ha="left")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_pdf = OUT_DIR / "fig_model_bar.pdf"
    out_png = OUT_DIR / "fig_model_bar.png"
    fig.savefig(out_pdf, dpi=300, bbox_inches="tight")
    fig.savefig(out_png, dpi=300, bbox_inches="tight")

    print(f"n_configs={n} of {total}, arm=single (Korean tool schema, Korean questions)")
    print("not scored yet: " + (", ".join(absent) or "none"))
    for row in rows:
        print(f"  {row['config_id']:<18s} h={row['h']:.4f} (n={row['n_h']})  "
              f"a={row['a']:.4f} (n={row['n_a']})")
    print(f"Saved: {out_pdf}")
    print(f"Saved: {out_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
