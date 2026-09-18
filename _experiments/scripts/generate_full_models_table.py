#!/usr/bin/env python3
"""The rows of tab:full_models, the appendix table of every configuration.

Reads `_experiments/scripts/analysis/load.py` and nothing else from the results
trees: `load.single()` for the five single-turn columns and
`load.multiturn("oracle")` for the three multi-turn ones. Both are the arm the
paper reports, the Korean tool schema with Korean questions.

What changed. The old version carried a `GROUPS` literal of nine vendor groups
over 28 model names, a `CHECK_NEEDED` set of four names that nothing read because
its one use sat behind `and False`, and a `_norm_model_key` that patched the two
spellings the pre-audit eval files used for the same model. All of it is gone.
The cohort and its order are the serving registry, the display name is the
registry `label`, and the group blocks are the registry `group`, which is the
three way split the paper argues about (Korean-Specialized, Finance-Specialized,
General-Purpose) rather than a vendor grouping that had to be edited by hand
whenever a model was added. `\\krmodel{}` wraps a row when its registry group is
Korean-Specialized, which is what the old `KR_GROUPS = {'kr'}` meant.

The two paths were relative to the working directory, so the step wrote
`_experiments/results_RQ1` under whatever directory it happened to be launched
from. They resolve from the repository root now (PORTING.md, Paths).

Column meanings, with the fixed metrics (D02). `h r p a o` are per-case means
over the cases where the metric is defined, so `p` skips the cases where the
model called nothing and `a` skips the cases with no parameter checks. A cell
cannot carry its own n without changing the table's shape, so the counts are a
comment block at the end of the file (PORTING.md rule 2), where they do not sit
between a person and the rows they came to paste. `h-bar` and `a-bar` are means
over turns and `c` is
the scenario completion rate over scenarios, which is what the oracle scorer
aggregates as `h`, `a` and `c`.

`$\\pm$0.000` stays in every cell. There is one run per configuration, so no
standard deviation was measured; the placeholder is there because the appendix
table's cells were laid out with a `mean$\\pm$sd` shape and a person pastes these
rows into that shape. It is a formatting filler, not a measured spread, and the
header comment says so in the file itself.

A configuration the registry names and the scorer has not reached is printed as a
comment line in its group position, so the gap is visible where the row belongs
and not only in the summary at the top (PORTING.md rule 4).

Output: _experiments/results_RQ1/full_models_table_rows.tex
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from _experiments.scripts.analysis import load  # noqa: E402

OUT_DIR = _ROOT / "_experiments" / "results_RQ1"

SINGLE_COLS = ("h", "r", "p", "a", "o")
KR_GROUP = "Korean-Specialized"


def fmt(value, decimals: int = 3, with_std: bool = True) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "--"
    if with_std:
        return f"{value:.{decimals}f}$\\pm$0.000"
    return f"{value:.{decimals}f}"


def _mean_n(series) -> tuple[float | None, int]:
    defined = series.dropna()
    return (float(defined.mean()) if len(defined) else None), int(len(defined))


def collect() -> tuple[dict[str, dict], dict[str, list[str]]]:
    """Per configuration numbers, and the ids each source is still missing."""
    cases = load.single()
    scenarios, turns = load.multiturn("oracle")

    # Registry order, so the file is the same bytes on two runs over the same
    # results and a diff shows a number that moved rather than a dict that did.
    values: dict[str, dict] = {}
    scored_single = set(cases["config_id"])
    scored_oracle = set(scenarios["config_id"])
    for config_id in load.configs()["config_id"]:
        row: dict = {}
        if config_id in scored_single:
            subset = cases[cases["config_id"] == config_id]
            row["n_cases"] = int(len(subset))
            for column in SINGLE_COLS:
                row[column], row[f"n_{column}"] = _mean_n(subset[column])
        if config_id in scored_oracle:
            turn_rows = turns[turns["config_id"] == config_id]
            scenario_rows = scenarios[scenarios["config_id"] == config_id]
            row["h_bar"], row["n_h_bar"] = _mean_n(turn_rows["h"])
            row["a_bar"], row["n_a_bar"] = _mean_n(turn_rows["a"])
            row["c"], row["n_c"] = _mean_n(scenario_rows["c"])
        if row:
            values[config_id] = row

    todo = load.missing()
    absent = {"single": todo.loc[~todo["single"], "config_id"].tolist(),
              "oracle": todo.loc[~todo["oracle"], "config_id"].tolist()}
    return values, absent


def provenance(absent: dict[str, list[str]], total: int) -> list[str]:
    """The header every output carries: which cohort this is (PORTING.md rule 4)."""
    n_single = total - len(absent["single"])
    n_oracle = total - len(absent["oracle"])
    return [f"n_configs={n_single} of {total} single-turn, {n_oracle} of {total} oracle; "
            f"arm=single (Korean tool schema, Korean questions)",
            "single-turn not scored yet: " + (", ".join(absent["single"]) or "none"),
            "oracle not scored yet: " + (", ".join(absent["oracle"]) or "none"),
            "$\\pm$0.000 is a layout filler, not a measured spread: one run per configuration",
            "the n behind every cell is in the comment block at the end of this file"]


def counts(values: dict[str, dict]) -> list[str]:
    """The n behind each cell (PORTING.md rule 2).

    It trails the rows rather than heading them. A cell cannot carry its own n
    without changing the table's shape, and eighteen count lines in front of the
    rows would bury the thing a person came to paste.
    """
    lines = ["per-configuration counts. p is over the cases that called a tool and a "
             "over the cases with parameter checks, so those are below n_cases:"]
    for config_id, row in values.items():
        if "h" not in row:
            continue
        lines.append(f"  {config_id}: n_cases={row['n_cases']} "
                     + " ".join(f"n_{c}={row[f'n_{c}']}" for c in SINGLE_COLS)
                     + (f" n_turns={row.get('n_h_bar', 0)} n_scenarios={row.get('n_c', 0)}"
                        if "h_bar" in row else " oracle=missing"))
    return lines


def main() -> int:
    values, absent = collect()
    registry = load.configs()

    rows: list[str] = []
    previous_group = None
    for config_id in registry["config_id"]:
        entry = registry.loc[config_id]
        if previous_group is not None and entry["group"] != previous_group:
            rows.append("\\midrule")
        previous_group = entry["group"]

        numbers = values.get(config_id)
        if not numbers or "h" not in numbers:
            rows.append(f"% [not scored] {entry['label']} ({config_id}), group {entry['group']}")
            continue

        name = (f"\\krmodel{{{entry['label']}}}" if entry["group"] == KR_GROUP
                else str(entry["label"]))
        cells = " & ".join(fmt(numbers[c]) for c in SINGLE_COLS)
        rows.append(f"{name:<35s} & {cells} & {fmt(numbers.get('h_bar'))}  & "
                    f"{fmt(numbers.get('a_bar'))}  & {fmt(numbers.get('c'))} \\\\")

    note = provenance(absent, total=len(registry))
    body = ([f"% {line}" for line in note] + rows
            + [f"% {line}" for line in counts(values)])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUT_DIR / "full_models_table_rows.tex"
    out_file.write_text("\n".join(body) + "\n", encoding="utf-8")

    print("=== full_models LaTeX rows ===")
    for line in body:
        print(line)
    print(f"\nSaved to: {out_file}")
    n_data_rows = sum(1 for r in rows if r and not r.startswith("%") and r != "\\midrule")
    print(f"Total data rows: {n_data_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
