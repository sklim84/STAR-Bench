#!/usr/bin/env python3
"""RQ2: keyword accuracy on `lookup_fiu_reference_types`, the tool-hit/parameter gap.

What it reads
    `_experiments/scripts/analysis/load.py` and nothing else from the results
    trees. `load.single()` gives one row per (configuration, case) for the
    main-table arm (Korean schema, Korean questions), and this step keeps the
    rows whose `category` is `lookup_fiu_reference_types`. `load.calls("single")`
    gives the arguments the model actually passed, for the csv column described
    below. It no longer walks `_experiments/results_kr/eval/*.json`, no longer
    resolves its paths against the working directory, and no longer carries an
    `EXCLUDE_MODELS` / `_CANONICAL_NAMES` literal: the cohort is the serving
    registry (the rule), and every output names how many of the 28
    configurations are scored and which are not (the rule).

What changed in what it counts
    The question is the same, the gap between finding the tool and filling its
    keyword, but two of the old numbers were wrong in a way the new fields fix.

    - `param_accuracy` was read as `float(... or 0)`, which turned a case with no
      parameter checks into a zero and inflated the gap. `a` is null for such a
      case, so every mean over it is taken across the non-null rows and carries
      its own n beside it (the rule). `hit_mean` and `param_acc_mean` can
      therefore rest on different denominators, and both are written out.
    - the per-case weighted `score` is gone with its definition (the rule);
      `h` is the case outcome, and `error_type` now comes from the new taxonomy
      (the rule), so its distribution is written out as well.
    - `param_check_details` became `checks`, which `load.single()` does not
      expose, so the csv cannot carry the expected/actual pair per check. What it
      carries instead is `call_arguments`: the arguments the model passed to
      `lookup_fiu_reference_types`, taken from `load.calls("single")`. That is
      the keyword the model produced, which is the half of the old column this
      step was named for. `n_checks` says how many checks stood behind `a`.
    - the unit count follows the data rather than a sentence: the arm now holds
      25 `lookup_fiu_reference_types` cases, not 8.
    - the keys of `per_model_summary` are `config_id`s, not model names. Thinking
      and non-thinking are separate configurations, and each entry carries the
      registry `label` and `group`.

Outputs: _experiments/results_RQ2/lookup_fiu_per_case.csv
         _experiments/results_RQ2/lookup_fiu_keyword_analysis.json
         _experiments/results_RQ2/fig_lookup_fiu_per_case.{pdf,png}
         _experiments/results_RQ2/fig_lookup_fiu_model_gap.{pdf,png}
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

from _experiments.scripts._plot_style import (COL_BAD, COL_GOOD, COL_PURPLE,  # noqa: E402
                                              FS_ANNOT, FS_LABEL, FS_LEGEND, FS_TICK,
                                              plt, style_axes)
from _experiments.scripts.analysis import load  # noqa: E402

OUT_DIR = ROOT / "_experiments" / "results_RQ2"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TOOL = "lookup_fiu_reference_types"   # a `category` value in load.single()
CASE_PREFIX = "st_fiu_"
N_GAP_ROWS = 15


def cohort(column: str = "single") -> tuple[int, list[str]]:
    """(configurations scored, the ids of the 28 that are not) for one arm."""
    table = load.missing()
    absent = sorted(table.loc[~table[column], "config_id"])
    return int(table[column].sum()), absent


def _mean_with_n(series) -> tuple[float | None, int]:
    """Rule 2: the mean over the non-null rows, and how many rows that was."""
    values = series.dropna()
    return (round(float(values.mean()), 4) if len(values) else None), int(len(values))


def _gap(hit: float | None, param: float | None) -> float | None:
    return None if (hit is None or param is None) else round(hit - param, 4)


def _arguments_by_case() -> dict[tuple[str, str], list]:
    """What each configuration passed to the tool, per case, in call order.

    `load.single()` does not expose the scorer's `checks`, so this is where the
    keyword the model produced comes from. A checkout without run records simply
    leaves the column empty rather than failing the step.
    """
    try:
        calls = load.calls("single")
    except (FileNotFoundError, ValueError) as exc:
        print(f"no run records, call_arguments left empty: {exc}")
        return {}
    wanted = calls[calls["tool"] == TOOL]
    out: dict[tuple[str, str], list] = defaultdict(list)
    for call in wanted.itertuples():
        out[(call.config_id, call.case_id)].append(call.arguments)
    return out


def main() -> int:
    cases = load.single()
    n_configs, absent = cohort()
    n_registry = n_configs + len(absent)
    missing_ids = "|".join(absent)

    subset = cases[cases["category"] == TOOL].sort_values(["config_id", "case_id"])
    if subset.empty:
        raise SystemExit(f"no {TOOL} cases in the scored arm")
    arguments = _arguments_by_case()

    rows = []
    for case in subset.itertuples():
        rows.append({
            "config_id": case.config_id, "label": case.label, "group": case.group,
            "case_id": case.case_id, "difficulty": case.difficulty,
            "h": case.h, "a": "" if case.a is None else case.a,
            "n_checks": case.n_checks,
            "call_arguments": json.dumps(arguments.get((case.config_id, case.case_id), []),
                                         ensure_ascii=False),
            "called_tools": json.dumps(list(case.called_tools), ensure_ascii=False),
            "error_type": case.error_type,
            "n_configs": n_configs, "n_configs_expected": n_registry,
            "missing_config_ids": missing_ids,
        })

    with (OUT_DIR / "lookup_fiu_per_case.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    # ── per case, across the configurations that are scored ─────────────────
    case_summary = {}
    for case_id, group in subset.groupby("case_id", sort=True):
        hit_mean, hit_n = _mean_with_n(group["h"])
        param_mean, param_n = _mean_with_n(group["a"])
        case_summary[case_id] = {
            "n_configs": int(len(group)),
            "hit_mean": hit_mean, "hit_n": hit_n,
            "param_acc_mean": param_mean, "param_acc_n": param_n,
            "gap": _gap(hit_mean, param_mean),
        }

    # ── per configuration, across the cases ─────────────────────────────────
    labels = load.configs()["label"].to_dict()
    groups = load.configs()["group"].to_dict()
    model_summary = {}
    for config_id, group in subset.groupby("config_id", sort=True):
        hit_mean, hit_n = _mean_with_n(group["h"])
        param_mean, param_n = _mean_with_n(group["a"])
        model_summary[config_id] = {
            "label": labels.get(config_id, config_id), "group": groups.get(config_id, ""),
            "n_cases": int(len(group)),
            "hit_mean": hit_mean, "hit_n": hit_n,
            "param_acc_mean": param_mean, "param_acc_n": param_n,
            "gap": _gap(hit_mean, param_mean),
        }

    overall_hit, overall_hit_n = _mean_with_n(subset["h"])
    overall_param, overall_param_n = _mean_with_n(subset["a"])

    summary = {
        "tool": TOOL,
        "n_configs": n_configs,
        "n_configs_expected": n_registry,
        "missing_config_ids": absent,
        "total_cases": int(subset["case_id"].nunique()),
        "total_models": int(subset["config_id"].nunique()),
        "total_call_units": len(rows),
        "overall_hit_mean": overall_hit, "overall_hit_n": overall_hit_n,
        "overall_param_acc_mean": overall_param, "overall_param_acc_n": overall_param_n,
        "overall_gap": _gap(overall_hit, overall_param),
        "error_type_distribution": {k: int(v) for k, v in
                                    subset["error_type"].value_counts().items()},
        "per_case_summary": case_summary,
        "per_model_summary": dict(sorted(model_summary.items(),
                                         key=lambda item: -(item[1]["gap"] or 0))),
        "note": (
            f"{TOOL} case study: {subset['case_id'].nunique()} cases x {n_configs} "
            f"configurations = {len(rows)} call units. "
            f"{n_configs} of {n_registry} configurations are scored; the rest are listed in "
            "missing_config_ids and are absent from every number here. "
            "gap = hit_mean - param_acc_mean, how far the model gets past finding the tool "
            "without filling its keyword. "
            "param_acc_mean is the mean of a over the param_acc_n cases that carry parameter "
            "checks; a is null, never zero, for a case with none (the rule), so hit_n "
            "and param_acc_n can differ and the gap is a difference of two means over "
            "different denominators. "
            "Keys of per_model_summary are config_ids: thinking and non-thinking are separate "
            "configurations. "
            "The csv column call_arguments holds what the model passed to the tool, from "
            "load.calls(); the scorer's per-check expected/actual pairs are not exposed by "
            "load.single()."
        ),
    }
    (OUT_DIR / "lookup_fiu_keyword_analysis.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # Rule 4: the figures say how much of the cohort they draw, and which ids
    # they do not, rather than letting a caption claim 28.
    cohort_note = (f"{TOOL}: {subset['case_id'].nunique()} cases x {n_configs} of "
                   f"{n_registry} configurations = {len(rows)} call units"
                   + (f". Not scored: {', '.join(absent)}" if absent else ""))

    try:
        # Plot A: per case, tool hit against parameter accuracy
        case_ids = list(case_summary)
        # a case with no parameter checks anywhere has no a at all; it draws no
        # bar rather than a bar at zero (the rule)
        nan = float("nan")
        hits = [nan if case_summary[c]["hit_mean"] is None else case_summary[c]["hit_mean"]
                for c in case_ids]
        params = [nan if case_summary[c]["param_acc_mean"] is None
                  else case_summary[c]["param_acc_mean"] for c in case_ids]
        x = range(len(case_ids))
        fig, ax = plt.subplots(figsize=(6.4, 3.2))
        ax.bar([i - 0.2 for i in x], hits, 0.4, label=r"Tool hit $h$",
               color=COL_GOOD, alpha=0.85)
        ax.bar([i + 0.2 for i in x], params, 0.4, label=r"Param acc. $a$",
               color=COL_BAD, alpha=0.85)
        ax.set_xticks(list(x))
        # the arm holds 25 cases where it held 8, so the shared prefix moves to
        # the axis label and the ticks keep only what distinguishes them
        ax.set_xticklabels([c.removeprefix(CASE_PREFIX) for c in case_ids],
                           rotation=60, ha="right", fontsize=FS_TICK - 2)
        ax.set_xlabel(f"Case ({CASE_PREFIX}*)", fontsize=FS_LABEL)
        ax.set_ylabel("Score", fontsize=FS_LABEL)
        # 25 cases leave no empty corner for an inset legend, so it sits above
        ax.legend(fontsize=FS_LEGEND, loc="lower center", bbox_to_anchor=(0.5, 1.0),
                  ncol=2, frameon=False)
        style_axes(ax)
        plt.tight_layout()
        plt.figtext(0.0, -0.02, cohort_note, fontsize=FS_ANNOT - 2.5, va="top",
                    ha="left", color="#444444", wrap=True)
        plt.savefig(OUT_DIR / "fig_lookup_fiu_per_case.pdf", dpi=300, bbox_inches="tight")
        plt.savefig(OUT_DIR / "fig_lookup_fiu_per_case.png", dpi=300, bbox_inches="tight")
        plt.close()

        # Plot B: the configurations with the widest gap. Display names come
        # from the registry label (the rule), not a name table.
        ranked = [(cid, v) for cid, v in model_summary.items() if v["gap"] is not None]
        ranked.sort(key=lambda item: -item[1]["gap"])
        ranked = ranked[:N_GAP_ROWS]
        fig, ax = plt.subplots(figsize=(5, min(3.6, 0.24 * len(ranked) + 0.9)))
        ax.barh([v["label"] for _, v in ranked][::-1], [v["gap"] for _, v in ranked][::-1],
                color=COL_PURPLE, alpha=0.85)
        ax.set_xlabel(r"Gap $h - a$", fontsize=FS_LABEL)
        style_axes(ax)
        plt.tight_layout()
        plt.figtext(0.0, -0.02, cohort_note, fontsize=FS_ANNOT - 2.5, va="top",
                    ha="left", color="#444444", wrap=True)
        plt.savefig(OUT_DIR / "fig_lookup_fiu_model_gap.pdf", dpi=300, bbox_inches="tight")
        plt.savefig(OUT_DIR / "fig_lookup_fiu_model_gap.png", dpi=300, bbox_inches="tight")
        plt.close()
    except Exception as exc:                                  # noqa: BLE001
        print(f"plot failed: {exc}")

    print(f"[RQ2-lookup_fiu] completed: {len(rows)} units "
          f"({subset['case_id'].nunique()} cases x {n_configs} of {n_registry} configurations)")
    print(f"  not scored: {', '.join(absent) if absent else '(none)'}")
    print(f"  overall hit={overall_hit} (n={overall_hit_n}), "
          f"param_acc={overall_param} (n={overall_param_n}), gap={summary['overall_gap']}")
    print(f"  error types: {summary['error_type_distribution']}")
    widest = list(summary["per_model_summary"].items())[:3]
    print("  widest gaps: "
          + ", ".join(f"{v['label']} {v['gap']}" for _, v in widest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
