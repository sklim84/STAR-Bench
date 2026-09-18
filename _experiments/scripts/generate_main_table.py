#!/usr/bin/env python3
"""The single-turn columns of tab:overall in main.tex (h, r, p, a, o).

Reads `_experiments/scripts/analysis/load.py` and nothing else from the results
trees. The arm is `load.single()`, the Korean tool schema with Korean questions,
which is the arm tab:overall reports.

What changed. The old version carried a 28 entry `ROWS` literal that paired an
eval `model` string with a display name and a group, and it normalised that
string by hand because the pre-audit eval files spelled the model two ways and
kept `think` as a separate boolean. Rows now come from `load.single()` joined to
`load.configs()`: the display name is the registry `label`, the group is the
registry `group`, and a thinking pair is two `config_id`s with two labels instead
of one model name with a suffix. No name list is left to drift from the registry.

The metrics are the fixed ones (D02), so a mean is taken over the cases where the
metric is defined and is printed with that count in the CSV. `p` is null for a
case where the model called no tool and `a` is null for a case with no parameter
checks; the pre-audit keys wrote 1.0 into both, which inflated `p` for a model
that abstained often and `a` for a model that called tools with no checkable
arguments. `avg_tool_precision` therefore does not map onto a single new number:
the per-case mean over the cases with calls is the honest counterpart, and it is
what `load.single()["p"]` gives and what the scorer records as `p_case`.

The row order is the registry order, because tab:overall lists its rows in that
order and a person transcribes this file into the table line by line. Every other
ordering in the analysis comes from the metric.

Ranks are computed over the scored rows only. 18 of the 28 configurations are
scored today, so the bold and the underline say which of those 18 leads, not
which of the 28 does; the header comment in the .tex says so and names the
configurations that are missing (PORTING.md rule 4).

Multi-turn columns (h-bar, a-bar, c) are not made here. tab:overall takes them
from the oracle setting, and `generate_full_models_table.py` is the step that
reads both settings at once.

Output: _experiments/results_RQ1/main_table_single_turn.{tex,csv}
"""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from _experiments.scripts.analysis import load  # noqa: E402

OUT_DIR = _ROOT / "_experiments" / "results_RQ1"

# The table's five single-turn columns, in the order tab:overall prints them.
COLS = ("h", "r", "p", "a", "o")


def fmt(value) -> str:
    """The manuscript's notation: three decimals, no leading zero (.544)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "--"
    return f"{value:.3f}".lstrip("0")


def rank_marks(values: list) -> list[str]:
    """Column values -> printed cells. Best is bold, second is underlined.

    The comparison is on the rounded string, so two models that print the same
    three decimals are marked the same rather than separated by a difference the
    table does not show.
    """
    shown = sorted({fmt(v) for v in values} - {"--"}, reverse=True)
    first = shown[0] if shown else None
    second = shown[1] if len(shown) > 1 else None
    marks = []
    for value in values:
        cell = fmt(value)
        if cell == first:
            marks.append(f"\\textbf{{{cell}}}")
        elif cell == second:
            marks.append(f"\\underline{{{cell}}}")
        else:
            marks.append(cell)
    return marks


def collect() -> tuple[list[dict], list[str]]:
    """One row per scored configuration, in registry order, plus the missing ids."""
    cases = load.single()
    registry = load.configs()
    scored = set(cases["config_id"])

    rows = []
    for config_id in registry["config_id"]:
        if config_id not in scored:
            continue
        subset = cases[cases["config_id"] == config_id]
        row = {"config_id": config_id,
               "model": registry.loc[config_id, "model"],
               "label": registry.loc[config_id, "label"],
               "group": registry.loc[config_id, "group"],
               "n_cases": int(len(subset))}
        for column in COLS:
            defined = subset[column].dropna()
            row[column] = float(defined.mean()) if len(defined) else None
            row[f"n_{column}"] = int(len(defined))
        rows.append(row)

    todo = load.missing()
    absent = todo.loc[~todo["single"], "config_id"].tolist()
    return rows, absent


def provenance(rows: list[dict], absent: list[str]) -> list[str]:
    """The comment block every output carries (PORTING.md rule 4)."""
    total = len(rows) + len(absent)
    lines = [f"n_configs={len(rows)} of {total} in the serving registry, "
             f"arm=single (Korean tool schema, Korean questions)"]
    if absent:
        lines.append("not scored yet: " + ", ".join(absent))
        lines.append("bold and underline rank the scored rows only, so they can move "
                     "when the rest arrive")
    else:
        lines.append("not scored yet: none")
    return lines


def main() -> int:
    rows, absent = collect()
    marked = {column: rank_marks([row[column] for row in rows]) for column in COLS}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    note = provenance(rows, absent)

    lines = [f"% {line}" for line in note]
    for index, row in enumerate(rows):
        cells = " & ".join(marked[column][index] for column in COLS)
        lines.append(f"{row['label']:<24s} & {cells} \\\\")
    tex_path = OUT_DIR / "main_table_single_turn.tex"
    tex_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    csv_path = OUT_DIR / "main_table_single_turn.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        for line in note:
            handle.write(f"# {line}\n")
        writer = csv.writer(handle)
        # n_<metric> is the count the mean was taken over, which is not n_cases
        # for p, a and o: those are null where the metric does not apply.
        writer.writerow(["config_id", "model", "display_name", "group", *COLS,
                         *(f"n_{c}" for c in COLS), "n_cases"])
        for row in rows:
            writer.writerow([row["config_id"], row["model"], row["label"], row["group"],
                             *(("" if row[c] is None else round(row[c], 4)) for c in COLS),
                             *(row[f"n_{c}"] for c in COLS), row["n_cases"]])

    print("\n".join(lines))
    print(f"\n{len(rows)} rows -> {tex_path}")
    print(f"{len(rows)} rows -> {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
