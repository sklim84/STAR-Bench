#!/usr/bin/env python3
"""Oracle against end-to-end execution on the multi-turn STR workflow.

The oracle setting injects the gold tool call and the gold tool result into the
history at every turn, so each turn is scored against a perfect prior context.
The end-to-end setting executes the model's OWN calls against the live HOFINET
backend and feeds the real results forward, so a mistake carries. The gap
between the two says how much of a model's multi-turn score depends on never
seeing its own output.

The setting is called `e2e` everywhere now; the old name was `real`. The
`--real` flag is `--e2e`, and each flag names an eval root that holds that
setting's directory (`mt_oracle/`, `mt_e2e/`), so the two can come from
different rerun trees. The file names stay `oracle_vs_real.{json,csv}` because
a manuscript object reads them by name.

Ported to the scored rerun; the input is `analysis/load.py` and nothing else
(see `analysis/PORTING.md`):

  - metrics are the fixed ones: `h_mean`, `a_mean`, `context_accuracy` and `c`
    per scenario, averaged over the scenarios that carry them, with the n next
    to each number (rule 2). These are the columns tab:e2e-subset and
    app:e2e_full are built from.
  - the cohort is the serving registry, not the `EXCLUDE` list that used to sit
    in this file (rule 3).
  - a configuration with an oracle run and no end-to-end run is a row that says
    so and why, not a row that disappears (rule 4). Three of them have no
    end-to-end column because the end-to-end setting serves a longer context
    than the model's own window.
  - the JSON is an object, not a bare list, so it can carry `n_configs` and the
    ids that are missing; the rows are under `rows`.

Usage:
  PYTHONPATH=. python _experiments/scripts/RQ_oracle_vs_real.py
  python -m _experiments.scripts.RQ_oracle_vs_real \
      --oracle _experiments/runs/eval --e2e _experiments/runs/eval
Output: _experiments/results_RQ3/oracle_vs_real.{json,csv}
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _experiments.scripts.analysis import load  # noqa: E402
from _experiments.scripts.runner import registry  # noqa: E402

OUT_DIR = ROOT / "_experiments" / "results_RQ3"

# The scenario-level metrics, in the order the tables print them. h_mean and c
# are the two the manuscript tables carry; a_mean and context_accuracy are the
# diagnostic pair that say where the end-to-end run loses them.
METRICS = ("h_mean", "a_mean", "context_accuracy", "c")


def cohort(*settings: str) -> tuple[list[str], list[str], int]:
    """(scored, not scored, cohort size) for the settings this step reads."""
    todo = load.missing()
    have = todo[list(settings)].all(axis=1)
    return (todo.loc[have, "config_id"].tolist(),
            todo.loc[~have, "config_id"].tolist(), len(todo))


def per_config(scenarios) -> dict[str, dict]:
    """config_id -> the scenario means and the n each one covers."""
    out = {}
    for config_id, frame in scenarios.groupby("config_id", sort=True):
        row = {"n_scenarios": int(len(frame))}
        for metric in METRICS:
            values = frame[metric].dropna()
            row[metric] = round(float(values.mean()), 4) if len(values) else None
            row[f"n_{metric}"] = int(len(values))
        out[config_id] = row
    return out


def _from_root(path: str | Path) -> Path:
    """Every path resolves from the repository root, never from the working directory."""
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def absence_reason(config) -> str:
    """Why a configuration with an oracle run has no end-to-end run."""
    window = getattr(config, "model_window", None)
    if window is not None and window < registry.CONTEXT_E2E:
        return (f"not run: the end-to-end setting serves {registry.CONTEXT_E2E} tokens and "
                f"this model's context window is {window}")
    return "not scored yet"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--oracle", default=str(load.DEFAULT_EVAL_ROOT),
                    help="eval root holding the oracle setting's directory (mt_oracle/)")
    ap.add_argument("--e2e", default=str(load.DEFAULT_EVAL_ROOT),
                    help="eval root holding the end-to-end setting's directory (mt_e2e/)")
    ap.add_argument("--out", default=str(OUT_DIR), help="directory for oracle_vs_real.{json,csv}")
    args = ap.parse_args(argv)

    oracle_scenarios, _ = load.multiturn("oracle", eval_root=_from_root(args.oracle))
    oracle = per_config(oracle_scenarios)
    try:
        e2e_scenarios, _ = load.multiturn("e2e", eval_root=_from_root(args.e2e))
        e2e = per_config(e2e_scenarios)
    except FileNotFoundError as error:
        print(f"no end-to-end results: {error}")
        print("Run: PYTHONPATH=. python -m _experiments.scripts.runner.cli "
              "--setting e2e --configs <ids>")
        return 1

    _scored, absent, n_configs = cohort("oracle")
    by_id = {config.config_id: config for config in registry.CONFIGS}
    labels = load.configs()

    rows = []
    for config_id in sorted(oracle, key=lambda cid: -(oracle[cid]["h_mean"] or -1)):
        o, e = oracle[config_id], e2e.get(config_id)
        row = {
            "config_id": config_id,
            "label": labels.loc[config_id, "label"] if config_id in labels.index else config_id,
            "model": labels.loc[config_id, "model"] if config_id in labels.index else "",
            "group": labels.loc[config_id, "group"] if config_id in labels.index else "",
            "n": o["n_scenarios"],
            "n_e2e": e["n_scenarios"] if e else 0,
            "e2e_absent_reason": "" if e else absence_reason(by_id.get(config_id)),
        }
        for metric in METRICS:
            ov, ev = o[metric], (e[metric] if e else None)
            row[f"oracle_{metric}"] = ov
            row[f"e2e_{metric}"] = ev
            row[f"drop_{metric}"] = round(ov - ev, 4) if (ov is not None and ev is not None) else None
            row[f"n_oracle_{metric}"] = o[f"n_{metric}"]
            row[f"n_e2e_{metric}"] = e[f"n_{metric}"] if e else 0
        rows.append(row)

    both = [r for r in rows if r["n_e2e"]]
    oracle_only = [r for r in rows if not r["n_e2e"]]

    def avg(rows_, key):
        values = [r[key] for r in rows_ if r[key] is not None]
        return round(sum(values) / len(values), 4) if values else None

    payload = {
        "n_configs": n_configs,
        "n_oracle": len(rows),
        "n_e2e": len(both),
        "missing_config_ids": absent,
        "oracle_without_e2e": [{"config_id": r["config_id"], "label": r["label"],
                                "reason": r["e2e_absent_reason"]} for r in oracle_only],
        "n_scenarios": int(oracle_scenarios["scenario_id"].nunique()),
        "paired_means": {
            f"{prefix}_{metric}": avg(both, f"{prefix}_{metric}")
            for metric in METRICS for prefix in ("oracle", "e2e", "drop")},
        "note": ("means are over the scenarios that carry the metric, per configuration; "
                 "paired_means average those over the configurations that have both settings "
                 f"(n={len(both)}). drop = oracle - e2e."),
        "rows": rows,
    }

    out_dir = _from_root(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "oracle_vs_real.json", "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    cols = (["config_id", "label", "model", "group", "n", "n_e2e", "e2e_absent_reason"]
            + [f"{prefix}_{metric}" for metric in METRICS for prefix in ("oracle", "e2e", "drop")]
            + [f"n_{prefix}_{metric}" for metric in METRICS for prefix in ("oracle", "e2e")])
    with open(out_dir / "oracle_vs_real.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in cols})

    print(f"[oracle-vs-e2e] {len(rows)} of {n_configs} configurations have oracle, "
          f"{len(both)} have end-to-end, over {payload['n_scenarios']} scenarios")
    print(f"  {'configuration':24s} {'h̄ oracle→e2e':>22s} {'c oracle→e2e':>22s}")
    for row in rows:
        h = (f"{row['oracle_h_mean']}→{row['e2e_h_mean']}" if row["n_e2e"]
             else f"{row['oracle_h_mean']}→--")
        c = (f"{row['oracle_c']}→{row['e2e_c']}" if row["n_e2e"]
             else f"{row['oracle_c']}→--")
        print(f"  {row['label'][:24]:24s} {h:>22s} {c:>22s}")
    means = payload["paired_means"]
    print(f"  paired mean (n={len(both)}): h̄ {means['oracle_h_mean']}→{means['e2e_h_mean']} "
          f"(drop {means['drop_h_mean']}), c {means['oracle_c']}→{means['e2e_c']} "
          f"(drop {means['drop_c']})")
    for row in oracle_only:
        print(f"  no end-to-end: {row['label']} — {row['e2e_absent_reason']}")
    if absent:
        print(f"  not scored in the oracle setting either: {', '.join(absent)}")
    print(f"  written: {out_dir / 'oracle_vs_real.json'}, {out_dir / 'oracle_vs_real.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
