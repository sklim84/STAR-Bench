#!/usr/bin/env python3
"""RQ1 figure: the tool-confusion heatmap, which tool was called instead of the right one.

What it reads
    `_experiments/scripts/analysis/load.py` and nothing else from the results
    trees: `load.single()` gives one row per (configuration, case) for the
    main-table arm (Korean schema, Korean questions), with `category`,
    `called_tools`, `gold_tools` and `error_type` already joined to the serving
    registry. It no longer walks `_experiments/results_kr/eval/*.json`, and the
    `EXCLUDE_MODELS` / `_CANONICAL_NAMES` literals are gone: the cohort is the
    registry (PORTING rule 3) and the configurations that are not scored yet are
    named on the figure and in the caption this script prints (PORTING rule 4).

What it counts, and what changed
    The old filter was `error_type == "wrong_func"`. That vocabulary is gone
    (PORTING rule 5). Its successor is `wrong_tool`, which the scorer assigns
    when the model called tools and not one of the gold tools was among them
    (`r == 0`, so `h == 0`). That is exactly "a tool was called instead of the
    right one", so this figure counts `wrong_tool` and nothing else, one count
    per case, attributed to the first tool the model called.

    Two neighbouring classes of the new taxonomy were considered and left out.
    The script prints how many cases each one holds, so what the figure does not
    show is visible next to what it does.

    `missing_tool` (`r > 0` and `h == 0`, the model called a gold tool but not
    the primary one) is an incompleteness failure, not a substitution: 304 of
    its 307 cases are `multi_tool`, and in 141 of them every tool the model
    called was a gold tool for that case, so nothing was called *instead* of
    anything. Counting it would print gold tool names in a column headed
    "Called tool (wrong)".

    `over_call` with `h == 0` is an abstain or clarification case where the model
    called a tool instead of asking for what was missing. Its expected side is
    "no tool at all", so it has no row on an "Expected tool" axis; the pre-audit
    taxonomy called these `hallucinated_call` and the old figure excluded them
    too. `over_call` with `h == 1` called the right tool and some extras, which
    are additions rather than substitutions.

    `no_call`, `length_stop`, `system_error` and `parse_fail` either call nothing
    or fail before the model has chosen a tool, so they have no column at all.

Output: _experiments/results_RQ1/fig_confusion_heatmap.{pdf,png}
"""

from __future__ import annotations

import sys
import textwrap
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import PowerNorm  # noqa: E402

from _experiments.scripts._plot_style import FS_ANNOT, FS_LABEL, FS_TICK  # noqa: E402
from _experiments.scripts.analysis import load  # noqa: E402

OUT_DIR = ROOT / "_experiments" / "results_RQ1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# The one error type this figure is about. See the header for the two classes
# that were considered and left out.
COUNTED = "wrong_tool"
# Reported beside the figure so the exclusions are visible, never drawn.
NOT_COUNTED = ("missing_tool", "over_call", "no_call", "param_error", "order_error",
               "length_stop", "system_error", "parse_fail")

N_EXPECTED_ROWS = 10
N_CALLED_COLS = 10

# Display-only abbreviation of tool names, so ten of them fit on an axis. This
# is not a cohort: the rows and columns come from the data.
SHORT = {
    "get_statistics":             "get_stats",
    "query_transactions":         "qry_txn",
    "analyze_network":            "analyze_net",
    "predict_fraud":              "pred_fraud",
    "detect_aml_patterns":        "aml_pat",
    "multi_tool":                 "multi_tool",
    "get_account_profile":        "acct_profile",
    "get_fraud_type_summary":     "fraud_type_sum",
    "compare_periods":            "cmp_period",
    "get_institution_report":     "inst_rpt",
    "rank_risky_transactions":    "rank_risky",
    "detect_ctr_candidates":      "ctr_cand",
    "score_account_risk":         "acct_risk",
    "detect_monitoring_alerts":   "mon_alert",
    "detect_dormant_reactivation": "dormant",
    "detect_smurfing_network":    "smurf_net",
    "get_trend_analysis":         "trend",
    "analyze_channel_risk":       "chan_risk",
    "get_receiving_account_profile": "recv_prof",
    "analyze_cross_institution_flow": "cross_inst",
    "missing_parameters":         "miss_p",
    "lookup_fiu_reference_types": "fiu_ref",
    "validate_str_fields":        "val_str",
    "get_aml_glossary":           "glossary",
}


def sn(tool: str) -> str:
    return SHORT.get(tool, tool[:10])


def cohort(column: str = "single") -> tuple[int, list[str]]:
    """(configurations scored, the ids of the 28 that are not) for one arm."""
    table = load.missing()
    absent = sorted(table.loc[~table[column], "config_id"])
    return int(table[column].sum()), absent


def main() -> int:
    cases = load.single()
    n_configs, absent = cohort()
    n_registry = n_configs + len(absent)

    counted = cases[cases["error_type"] == COUNTED]
    # expected tool (the case category) -> the tool the model reached for first
    conf: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    n_no_calls = 0
    n_same_name = 0
    for row in counted.itertuples():
        called = row.called_tools
        if not called:                      # r == 0 with no call cannot happen, but do not assume
            n_no_calls += 1
            continue
        if called[0] == row.category:       # the guard the old script carried; never fires for wrong_tool
            n_same_name += 1
            continue
        conf[row.category][called[0]] += 1

    # ── top confused expected tools, then the tools they were confused with ──
    tool_total_conf = {expected: sum(v.values()) for expected, v in conf.items()}
    top_expected = sorted(tool_total_conf, key=lambda t: -tool_total_conf[t])[:N_EXPECTED_ROWS]

    called_counter: dict[str, int] = defaultdict(int)
    for expected in top_expected:
        for called, count in conf[expected].items():
            called_counter[called] += count
    top_called = sorted(called_counter, key=lambda t: -called_counter[t])[:N_CALLED_COLS]

    mat = np.zeros((len(top_expected), len(top_called)), dtype=float)
    for i, expected in enumerate(top_expected):
        for j, called in enumerate(top_called):
            mat[i, j] = conf[expected].get(called, 0)

    row_labels = [sn(t) for t in top_expected]
    col_labels = [sn(t) for t in top_called]

    # ── plot ────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(5.0, 4.3))

    # cmap: viridis reversed (large value = dark), zero cells a pale tone rather
    # than pure white. PowerNorm(0.5) keeps the mid-range readable when one cell
    # dominates the linear scale.
    cmap = matplotlib.colormaps["viridis_r"].copy()
    cmap.set_bad("#F2F5E1")
    mat_display = np.where(mat > 0, mat, np.nan)
    im = ax.imshow(mat_display, aspect="auto", cmap=cmap,
                   norm=PowerNorm(gamma=0.5, vmin=0, vmax=mat.max() if mat.size else 1))

    # Every non-zero cell is annotated, which is why there is no colorbar.
    BOLD_MIN = 40
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            value = int(mat[i, j])
            if value == 0:
                continue
            text_color = "white" if im.norm(mat[i, j]) > 0.5 else "black"
            big = value >= BOLD_MIN
            ax.text(j, i, str(value), ha="center", va="center",
                    fontsize=FS_ANNOT if big else FS_ANNOT - 2,
                    color=text_color, fontweight="bold" if big else "normal")

    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, rotation=45, ha="right", fontsize=FS_TICK)
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels, fontsize=FS_TICK)
    ax.set_xlabel("Called tool (wrong)", fontsize=FS_LABEL)
    ax.set_ylabel("Expected tool", fontsize=FS_LABEL)

    # Rule 4: the figure says how much of the cohort it draws, and which ids it
    # does not, rather than letting a caption claim 28.
    note = (f"wrong_tool cases only; {n_configs} of {n_registry} configurations scored"
            + (f". Not scored: {', '.join(absent)}" if absent else ""))
    fig.tight_layout()
    fig.text(0.0, -0.02, "\n".join(textwrap.wrap(note, 96)),
             fontsize=FS_ANNOT - 2.5, va="top", ha="left", color="#444444")

    out_pdf = OUT_DIR / "fig_confusion_heatmap.pdf"
    out_png = OUT_DIR / "fig_confusion_heatmap.png"
    fig.savefig(out_pdf, dpi=300, bbox_inches="tight")
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_pdf}")
    print(f"Saved: {out_png}")

    # ── caption text, and what the figure leaves out ────────────────────────
    total_counted = int(sum(tool_total_conf.values()))
    print(f"\nCohort: {n_configs} of {n_registry} configurations scored "
          f"({len(cases)} case rows).")
    print(f"Not scored: {', '.join(absent) if absent else '(none)'}")
    print(f"\nTotal {COUNTED} pairs aggregated: {int(mat.sum())} drawn "
          f"of {total_counted} counted ({len(counted)} {COUNTED} cases, "
          f"{n_no_calls} with no call, {n_same_name} on the diagonal).")

    print("\nNot counted (present in the data, deliberately outside this figure):")
    by_type = cases["error_type"].value_counts()
    for name in NOT_COUNTED:
        if name not in by_type:
            continue
        rows = cases[cases["error_type"] == name]
        extra = ""
        if name == "over_call":
            extra = f"  (h==0: {int((rows['h'] == 0).sum())}, h==1: {int((rows['h'] == 1).sum())})"
        print(f"  {name:13s} {int(by_type[name]):5d}{extra}")

    print("\nTop-5 confusion pairs:")
    pairs = []
    for i, expected in enumerate(top_expected):
        for j, called in enumerate(top_called):
            if mat[i, j] > 0:
                pairs.append((expected, called, int(mat[i, j])))
    pairs.sort(key=lambda p: -p[2])
    for expected, called, count in pairs[:5]:
        print(f"  {sn(expected)} -> {sn(called)}: {count}")

    caption = (
        f"Tool confusion over the {n_configs} of {n_registry} configurations scored so far "
        f"(not scored: {', '.join(absent) if absent else 'none'}). "
        f"A cell counts the cases whose error type is {COUNTED}, that is, the model called "
        f"tools and none of the gold tools was among them; the row is the case category and "
        f"the column is the first tool the model called. "
        f"The arm holds {len(counted)} such cases; {total_counted} of them have a column "
        f"(the rest were dropped by the same-name guard), and the "
        f"{N_EXPECTED_ROWS}x{N_CALLED_COLS} block drawn here holds {int(mat.sum())}. "
        f"missing_tool (the model called a gold tool but missed the primary one, almost all of "
        f"them multi-tool cases) and over_call (the right tool plus extras, or a tool where the "
        f"case asked the model to abstain) are not substitutions and are not counted here."
    )
    print("\ncaption:")
    print("\n".join(textwrap.wrap(caption, 92)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
