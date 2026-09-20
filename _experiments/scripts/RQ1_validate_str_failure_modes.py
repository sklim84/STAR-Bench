#!/usr/bin/env python3
"""RQ1: the failure modes of `validate_str_fields`.

What it reads
    `_experiments/scripts/analysis/load.py` and nothing else from the results
    trees: `load.single()` gives one row per (configuration, case) for the
    main-table arm (Korean schema, Korean questions), and this step keeps the
    rows whose `category` is `validate_str_fields`. The cohort is the serving
    registry, and every output names how many of its configurations are scored
    and which are not.

What it counts
    Four call-unit modes (`no_call`, `correct_only`, `correct_with_extra`,
    `miscall_only`), one unit per (configuration, case):

    - `called_tools` is a tuple of plain tool-name strings.
    - the csv carries `h`, because "did this case come out right" is `h == 1`.
    - `a` is null for a case with no parameter checks, so it is never read as
      zero: the summary reports its mean over the non-null rows together with
      that count.
    - the unit count is computed from the data rather than written into the
      note, so it follows the arm instead of a sentence that goes stale.
    - `error_type` values are the scorer's own; the distribution is written out
      so the modes can be read against it.
    - the keys of `per_model_breakdown` are `config_id`s, not model names.
      Thinking and non-thinking are separate configurations, and each entry
      carries the registry `label` and `group`.

Outputs: _experiments/results_RQ1/validate_str_failure_modes.{csv,json}
         _experiments/results_RQ1/fig_validate_str_modes.{pdf,png}
         _experiments/results_RQ1/fig_validate_str_miscalled.{pdf,png}
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _experiments.scripts._plot_style import (COL_ACCENT, COL_BAD, COL_GOOD,  # noqa: E402
                                              COL_PURPLE, FS_ANNOT, FS_LABEL, FS_TICK,
                                              plt, style_axes)
from _experiments.scripts.analysis import load  # noqa: E402

OUT_DIR = ROOT / "_experiments" / "results_RQ1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TOOL = "validate_str_fields"   # a `category` value in load.single()
MODES = ("no_call", "correct_only", "correct_with_extra", "miscall_only")
MODE_LABELS = ("No call", "Correct only", "Correct+extra", "Miscall only")


def classify_mode(tool_names: tuple[str, ...]) -> str:
    if not tool_names:
        return "no_call"
    has_correct = TOOL in tool_names
    if has_correct and len(tool_names) == 1:
        return "correct_only"
    if has_correct:
        return "correct_with_extra"
    return "miscall_only"


def cohort(column: str = "single") -> tuple[int, list[str]]:
    """(configurations scored, the ids of the 28 that are not) for one arm."""
    table = load.missing()
    absent = sorted(table.loc[~table[column], "config_id"])
    return int(table[column].sum()), absent


def _mean_with_n(series) -> tuple[float | None, int]:
    """Rule 2: the mean over the non-null rows, and how many rows that was."""
    values = series.dropna()
    return (round(float(values.mean()), 4) if len(values) else None), int(len(values))


def main() -> int:
    cases = load.single()
    n_configs, absent = cohort()
    n_registry = n_configs + len(absent)
    missing_ids = "|".join(absent)

    subset = cases[cases["category"] == TOOL].sort_values(["config_id", "case_id"])
    if subset.empty:
        raise SystemExit(f"no {TOOL} cases in the scored arm")

    rows = []
    mode_count: dict[str, int] = defaultdict(int)
    miscall_dist: dict[str, int] = defaultdict(int)
    per_config: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for case in subset.itertuples():
        names = tuple(case.called_tools)
        mode = classify_mode(names)
        mode_count[mode] += 1
        per_config[case.config_id][mode] += 1
        per_config[case.config_id]["total"] += 1
        if mode in ("miscall_only", "correct_with_extra"):
            for name in names:
                if name != TOOL:
                    miscall_dist[name] += 1
        rows.append({
            "config_id": case.config_id, "label": case.label, "group": case.group,
            "case_id": case.case_id, "difficulty": case.difficulty, "mode": mode,
            "called_tools": "|".join(names),
            "h": case.h, "a": "" if case.a is None else case.a,
            "n_checks": case.n_checks, "error_type": case.error_type,
            "n_configs": n_configs, "n_configs_expected": n_registry,
            "missing_config_ids": missing_ids,
        })

    with (OUT_DIR / "validate_str_failure_modes.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    total_units = sum(mode_count.values())
    n_cases = int(subset["case_id"].nunique())
    h_mean, h_n = _mean_with_n(subset["h"])
    a_mean, a_n = _mean_with_n(subset["a"])
    labels = load.configs()["label"].to_dict()
    groups = load.configs()["group"].to_dict()

    summary = {
        "tool": TOOL,
        "n_configs": n_configs,
        "n_configs_expected": n_registry,
        "missing_config_ids": absent,
        "n_cases": n_cases,
        "total_call_units": total_units,
        "h_mean": h_mean, "h_n": h_n,
        "a_mean": a_mean, "a_n": a_n,
        "mode_distribution": {m: mode_count.get(m, 0) for m in MODES},
        "mode_distribution_pct": {m: round(100 * mode_count.get(m, 0) / total_units, 1)
                                  for m in MODES},
        "error_type_distribution": {k: int(v) for k, v in
                                    subset["error_type"].value_counts().items()},
        "miscalled_tools_distribution": dict(sorted(miscall_dist.items(), key=lambda x: -x[1])),
        "per_model_breakdown": {
            config_id: {"label": labels.get(config_id, config_id),
                        "group": groups.get(config_id, ""), **dict(counts)}
            for config_id, counts in sorted(per_config.items())
        },
        "note": (
            f"{TOOL} = {n_cases} cases x {n_configs} configurations = {total_units} call units. "
            f"{n_configs} of {n_registry} configurations are scored; the rest are listed in "
            f"missing_config_ids and are absent from every number here. "
            "no_call: the model called no tool. "
            f"correct_only: {TOOL} alone. "
            f"correct_with_extra: {TOOL} plus other tools. "
            f"miscall_only: {TOOL} not called, other tools called. "
            "Keys of per_model_breakdown are config_ids: thinking and non-thinking are "
            "separate configurations. "
            "h == 1 is the case outcome: did this case come out right. "
            "a_mean is taken over the a_n cases that have parameter "
            "checks, never over nulls read as zero."
        ),
    }
    (OUT_DIR / "validate_str_failure_modes.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # Rule 4: the figures say how much of the cohort they draw, and which ids
    # they do not, rather than letting a caption claim 28.
    cohort_note = (f"{TOOL}: {n_cases} cases x {n_configs} of {n_registry} configurations "
                   f"= {total_units} call units"
                   + (f". Not scored: {', '.join(absent)}" if absent else ""))

    try:
        # Plot A: the distribution of failure modes
        counts = [mode_count.get(m, 0) for m in MODES]
        colors = [COL_BAD, COL_GOOD, COL_ACCENT, COL_PURPLE]
        fig, ax = plt.subplots(figsize=(4.5, 3.2))
        ax.bar(range(len(MODE_LABELS)), counts, color=colors, alpha=0.85, width=0.65)
        ax.set_xticks(range(len(MODE_LABELS)))
        ax.set_xticklabels(MODE_LABELS, fontsize=FS_TICK, rotation=20, ha="right")
        ax.set_ylabel("Call units", fontsize=FS_LABEL)
        for i, count in enumerate(counts):
            ax.text(i, count + 1, str(count), ha="center", fontsize=FS_ANNOT)
        style_axes(ax)
        plt.tight_layout()
        plt.figtext(0.0, -0.02, cohort_note, fontsize=FS_ANNOT - 2.5, va="top",
                    ha="left", color="#444444", wrap=True)
        plt.savefig(OUT_DIR / "fig_validate_str_modes.pdf", dpi=300, bbox_inches="tight")
        plt.savefig(OUT_DIR / "fig_validate_str_modes.png", dpi=300, bbox_inches="tight")
        plt.close()

        # Plot B: which tools were called instead
        if miscall_dist:
            sorted_mis = sorted(miscall_dist.items(), key=lambda x: -x[1])[:8]
            # The panel height follows the bar count, because a fixed 3.2 inches
            # stretches a single bar across the whole figure when only one tool
            # was miscalled.
            fig, ax = plt.subplots(figsize=(4.5, min(3.2, 0.42 * len(sorted_mis) + 0.95)))
            ax.barh([t for t, _ in sorted_mis][::-1], [c for _, c in sorted_mis][::-1],
                    color=COL_PURPLE, alpha=0.85)
            ax.set_xlabel("Count", fontsize=FS_LABEL)
            style_axes(ax)
            plt.tight_layout()
            plt.figtext(0.0, -0.02, cohort_note, fontsize=FS_ANNOT - 2.5, va="top",
                        ha="left", color="#444444", wrap=True)
            plt.savefig(OUT_DIR / "fig_validate_str_miscalled.pdf", dpi=300, bbox_inches="tight")
            plt.savefig(OUT_DIR / "fig_validate_str_miscalled.png", dpi=300, bbox_inches="tight")
            plt.close()
    except Exception as exc:                                  # noqa: BLE001
        print(f"plot failed: {exc}")

    print(f"[RQ1] completed: {len(rows)} call units "
          f"({n_cases} cases x {n_configs} of {n_registry} configurations)")
    print(f"  not scored: {', '.join(absent) if absent else '(none)'}")
    print(f"  modes: {dict(summary['mode_distribution'])}")
    print(f"  h mean {h_mean} (n={h_n}), a mean {a_mean} (n={a_n})")
    print(f"  error types: {summary['error_type_distribution']}")
    print(f"  miscall: {dict(list(summary['miscalled_tools_distribution'].items())[:5])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
