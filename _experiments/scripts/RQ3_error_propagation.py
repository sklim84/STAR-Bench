#!/usr/bin/env python3
"""RQ3: how a wrong first turn carries into the rest of an oracle scenario.

For every configuration and every STR scenario, turn 1 either hit its gold tool
or it did not, and this step compares the h of turns 2..N under the two
outcomes, plus the recovery rate at turn 2 (turn 1 missed, turn 2 hit).

The input is `analysis/load.py` and nothing else:

  - the turn metric is `h`, the paper's primary metric, and it is already 0/1.
    A turn fails when `h == 0`, which is what "is this turn correct" means.
  - the cohort is the serving registry rather than a list in this file. Rows are
    the configurations scored in the oracle setting, and `load.missing()` names
    the rest.
  - the outputs and the two figures carry `n_configs` and the ids that were
    missing, so a figure says how many configurations it covers.

Cited in the text as: how far subsequent-turn h drops after a failed turn 1,
and how much of that a model recovers by the next turn.

Output: _experiments/results_RQ3/error_propagation_per_model.csv
        _experiments/results_RQ3/error_propagation_summary.json
        _experiments/results_RQ3/fig_error_propagation.{pdf,png}
        _experiments/results_RQ3/fig_recovery_distribution.{pdf,png}

Usage: PYTHONPATH=. python _experiments/scripts/RQ3_error_propagation.py
       python -m _experiments.scripts.RQ3_error_propagation
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _experiments.scripts.analysis import load  # noqa: E402
from _experiments.scripts._plot_style import (  # noqa: E402
    plt, COL_GOOD, COL_BAD, COL_PURPLE, FS_ANNOT, FS_LABEL, FS_LEGEND,
    style_axes, short_name)

OUT_DIR = ROOT / "_experiments" / "results_RQ3"


def cohort(*settings: str) -> tuple[list[str], list[str], int]:
    """(scored, not scored, cohort size) for the settings this step reads."""
    todo = load.missing()
    have = todo[list(settings)].all(axis=1)
    return (todo.loc[have, "config_id"].tolist(),
            todo.loc[~have, "config_id"].tolist(), len(todo))


def _mean(values):
    return round(sum(values) / len(values), 4) if values else None


def per_config(turns) -> list[dict]:
    """One row per configuration: turn-1 outcome against the turns that follow."""
    labels = load.configs()
    rows = []
    for config_id, frame in turns.groupby("config_id", sort=True):
        n_total = n_t1_fail = n_t1_succ = 0
        after_fail, after_succ = [], []
        n_recover = n_fail_with_t2 = 0
        for _scenario_id, scenario in frame.groupby("scenario_id", sort=True):
            scenario = scenario.sort_values("turn")
            first = scenario[scenario["turn"] == 1]
            if first.empty or first.iloc[0]["h"] is None:
                continue
            n_total += 1
            later = scenario[scenario["turn"] > 1]
            subsequent = [int(h) for h in later["h"].tolist() if h is not None]
            if int(first.iloc[0]["h"]) == 0:
                n_t1_fail += 1
                after_fail.extend(subsequent)
                second = scenario[scenario["turn"] == 2]
                if not second.empty and second.iloc[0]["h"] is not None:
                    n_fail_with_t2 += 1
                    n_recover += int(second.iloc[0]["h"] == 1)
            else:
                n_t1_succ += 1
                after_succ.extend(subsequent)
        row = {
            "config_id": config_id,
            "label": labels.loc[config_id, "label"] if config_id in labels.index else config_id,
            "group": labels.loc[config_id, "group"] if config_id in labels.index else "",
            "n_scenarios_total": n_total,
            "n_t1_fail": n_t1_fail, "n_t1_succ": n_t1_succ,
            "t1_hit_rate": round(n_t1_succ / n_total, 4) if n_total else None,
            "subseq_hit_after_t1_fail": _mean(after_fail),
            "subseq_hit_after_t1_succ": _mean(after_succ),
            "n_subseq_after_fail": len(after_fail),
            "n_subseq_after_succ": len(after_succ),
            "recovery_rate_t2": round(n_recover / n_fail_with_t2, 4) if n_fail_with_t2 else None,
            "n_t1_fail_with_t2": n_fail_with_t2,
            "gap_succ_minus_fail": None,
        }
        if row["subseq_hit_after_t1_succ"] is not None and row["subseq_hit_after_t1_fail"] is not None:
            row["gap_succ_minus_fail"] = round(
                row["subseq_hit_after_t1_succ"] - row["subseq_hit_after_t1_fail"], 4)
        rows.append(row)
    return rows


def figures(rows: list[dict], valid: list[dict], n_configs: int, n_missing: int) -> None:
    note = f"{len(rows)} of {n_configs} configurations scored"

    ordered = sorted(valid, key=lambda r: r["gap_succ_minus_fail"])
    names = [short_name(r["label"], 18) for r in ordered]
    x = range(len(ordered))
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.plot(x, [r["subseq_hit_after_t1_succ"] for r in ordered], "o-",
            color=COL_GOOD, label="After t1 succ", markersize=4, linewidth=1.2, alpha=0.85)
    ax.plot(x, [r["subseq_hit_after_t1_fail"] for r in ordered], "s-",
            color=COL_BAD, label="After t1 fail", markersize=4, linewidth=1.2, alpha=0.85)
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=90, fontsize=7)
    ax.set_ylabel(r"Subsequent turn $h$", fontsize=FS_LABEL)
    ax.set_title(note, fontsize=FS_ANNOT, loc="right")
    ax.legend(fontsize=FS_LEGEND, loc="lower right")
    style_axes(ax)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "fig_error_propagation.pdf", dpi=300, bbox_inches="tight")
    plt.savefig(OUT_DIR / "fig_error_propagation.png", dpi=300, bbox_inches="tight")
    plt.close()

    recovery = [r["recovery_rate_t2"] for r in rows if r["recovery_rate_t2"] is not None]
    fig, ax = plt.subplots(figsize=(5, 3.2))
    ax.hist(recovery, bins=15, color=COL_PURPLE, alpha=0.85, edgecolor="white")
    if recovery:
        mean = sum(recovery) / len(recovery)
        ax.axvline(mean, color=COL_BAD, linestyle="--", linewidth=1.2, label=f"mean={mean:.3f}")
    ax.set_xlabel(r"Turn-2 recovery rate ($h$ | t1 fail)", fontsize=FS_LABEL)
    ax.set_ylabel("Configurations", fontsize=FS_LABEL)
    ax.set_title(f"{len(recovery)} of {n_configs} configurations, {n_missing} not scored",
                 fontsize=FS_ANNOT, loc="right")
    ax.legend(fontsize=FS_LEGEND)
    style_axes(ax)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "fig_recovery_distribution.pdf", dpi=300, bbox_inches="tight")
    plt.savefig(OUT_DIR / "fig_recovery_distribution.png", dpi=300, bbox_inches="tight")
    plt.close()


def main() -> int:
    scored, absent, n_configs = cohort("oracle")
    _scenarios, turns = load.multiturn("oracle")
    rows = per_config(turns)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    fields = ["config_id", "label", "group", "n_scenarios_total", "n_t1_fail", "n_t1_succ",
              "t1_hit_rate", "subseq_hit_after_t1_fail", "subseq_hit_after_t1_succ",
              "n_subseq_after_fail", "n_subseq_after_succ", "recovery_rate_t2",
              "n_t1_fail_with_t2", "gap_succ_minus_fail"]
    with (OUT_DIR / "error_propagation_per_model.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    valid = [r for r in rows if r["gap_succ_minus_fail"] is not None]
    with_fail = [r for r in rows if r["subseq_hit_after_t1_fail"] is not None]
    with_succ = [r for r in rows if r["subseq_hit_after_t1_succ"] is not None]
    with_recovery = [r for r in rows if r["recovery_rate_t2"] is not None]
    summary = {
        "n_configs": n_configs,
        "missing_config_ids": absent,
        "n_models_total": len(rows),
        "n_models_with_both_outcomes": len(valid),
        "mean_gap_succ_minus_fail": _mean([r["gap_succ_minus_fail"] for r in valid]),
        "n_gap": len(valid),
        "mean_t1_hit_rate": _mean([r["t1_hit_rate"] for r in rows
                                   if r["t1_hit_rate"] is not None]),
        "mean_subseq_after_fail": _mean([r["subseq_hit_after_t1_fail"] for r in with_fail]),
        "n_subseq_after_fail": len(with_fail),
        "mean_subseq_after_succ": _mean([r["subseq_hit_after_t1_succ"] for r in with_succ]),
        "n_subseq_after_succ": len(with_succ),
        "mean_recovery_rate": _mean([r["recovery_rate_t2"] for r in with_recovery]),
        "n_recovery": len(with_recovery),
        "top_5_largest_gap": [
            {"config_id": r["config_id"], "label": r["label"],
             "gap": r["gap_succ_minus_fail"], "n_t1_fail": r["n_t1_fail"]}
            for r in sorted(valid, key=lambda x: -x["gap_succ_minus_fail"])[:5]],
        "top_5_smallest_gap_robust": [
            {"config_id": r["config_id"], "label": r["label"],
             "gap": r["gap_succ_minus_fail"], "n_t1_fail": r["n_t1_fail"]}
            for r in sorted(valid, key=lambda x: x["gap_succ_minus_fail"])[:5]],
        "note": ("gap_succ_minus_fail = subseq_hit_after_t1_succ - subseq_hit_after_t1_fail, "
                 "over turns 2..N of the oracle scenarios. A turn fails when h == 0. "
                 "A large gap means an early miss carries; a small or negative gap means "
                 "the turns that follow are largely independent of it."),
    }
    with (OUT_DIR / "error_propagation_summary.json").open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)

    try:
        figures(rows, valid, n_configs, len(absent))
    except Exception as error:      # a missing font or backend is not a reason to lose the tables
        print(f"plot failed: {error}")

    print(f"[RQ3-prop] {len(rows)} of {n_configs} configurations scored in the oracle setting "
          f"({len(absent)} missing)")
    if absent:
        print(f"  missing: {', '.join(absent)}")
    print(f"  mean gap (succ - fail) = {summary['mean_gap_succ_minus_fail']} over n={len(valid)}")
    print(f"  mean subsequent h after t1 fail = {summary['mean_subseq_after_fail']} "
          f"(n={len(with_fail)}), after t1 succ = {summary['mean_subseq_after_succ']} "
          f"(n={len(with_succ)})")
    print(f"  mean turn-2 recovery = {summary['mean_recovery_rate']} (n={len(with_recovery)})")
    print(f"  written: {OUT_DIR / 'error_propagation_per_model.csv'}, "
          f"{OUT_DIR / 'error_propagation_summary.json'}")
    unexpected = set(scored) ^ {r["config_id"] for r in rows}
    if unexpected:
        print(f"  note: scored ids and table rows differ: {sorted(unexpected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
