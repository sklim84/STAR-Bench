#!/usr/bin/env python3
"""RQ3: context-accuracy vs scenario-completion partial correlation.

The inputs are `analysis/load.py` and nothing else. Three design choices decide
what the number means:

1. COHORT. The cohort is the serving registry, not a list in this file: a row is
   any configuration scored in BOTH the oracle multi-turn setting and the
   single-turn Korean arm, and `load.missing()` names the ones that are not in
   yet. The output carries `n_configs` and those ids, because a correlation over
   part of the cohort is not the correlation the caption claims.

2. CONTROL VARIABLE. The control is single-turn h, `aggregate["h"]["mean"]` of
   the single-turn arm, which is the h column of tab:overall. The multi-turn
   h-bar control (oracle `aggregate["h"]["mean"]`) is reported next to it.

3. PARTIAL METHOD. Proper rank-based partial Spearman: rank all three variables,
   then take the first-order partial Pearson on the ranks. Significance is the
   standard partial-correlation t-test, t = r*sqrt((n-3)/(1-r^2)), df = n-3,
   two-sided.

Every aggregate is the one the scorer wrote, and each carries its n:
context accuracy over turns where context was expected, completion over
scenarios, single-turn h over cases, multi-turn h-bar over turns.

Output: _experiments/results_RQ3/context_accuracy_correlation.json
        _experiments/results_RQ3/context_accuracy_per_model.csv

Usage: PYTHONPATH=. python _experiments/scripts/RQ3_context_accuracy_analysis.py
       python -m _experiments.scripts.RQ3_context_accuracy_analysis
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import rankdata, spearmanr
from scipy.stats import t as tdist

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _experiments.scripts.analysis import load  # noqa: E402

OUT_DIR = ROOT / "_experiments" / "results_RQ3"


def cohort(*settings: str) -> tuple[list[str], list[str], int]:
    """(scored, not scored, cohort size) for the columns this step reads."""
    todo = load.missing()
    have = todo[list(settings)].all(axis=1)
    return (todo.loc[have, "config_id"].tolist(),
            todo.loc[~have, "config_id"].tolist(), len(todo))


def partial_spearman(x, y, z):
    """First-order partial Spearman of (x, y) controlling z: rank then partial Pearson."""
    rx, ry, rz = rankdata(x), rankdata(y), rankdata(z)

    def pear(a, b):
        a, b = np.asarray(a, float), np.asarray(b, float)
        a, b = a - a.mean(), b - b.mean()
        return float((a * b).sum() / (np.sqrt((a * a).sum()) * np.sqrt((b * b).sum())))

    r_xy, r_xz, r_yz = pear(rx, ry), pear(rx, rz), pear(ry, rz)
    pr = (r_xy - r_xz * r_yz) / (np.sqrt(1 - r_xz**2) * np.sqrt(1 - r_yz**2))
    n = len(x)
    # partial-correlation t-test, df = n - 3 (one controlled variable)
    tstat = pr * np.sqrt((n - 3) / (1 - pr**2))
    p = 2 * tdist.sf(abs(tstat), df=n - 3)
    return float(pr), float(p), r_xy


def _stat(aggregate: dict, key: str) -> tuple[float | None, int]:
    """(mean, n) of one of the scorer's aggregates; a missing metric is None, not 0."""
    block = (aggregate or {}).get(key) or {}
    return block.get("mean"), int(block.get("n") or 0)


def main() -> int:
    scored, absent, n_cohort = cohort("oracle", "single")
    oracle = load.aggregates("oracle")
    single = load.aggregates("single")

    rows, skipped = [], []
    labels = load.configs()
    for config_id in scored:
        agg_o, agg_s = oracle.get(config_id), single.get(config_id)
        ctx, n_ctx = _stat(agg_o, "context_accuracy")
        comp, n_scen = _stat(agg_o, "c")
        hbar, n_turns = _stat(agg_o, "h")
        single_h, n_cases = _stat(agg_s, "h")
        if ctx is None or comp is None or single_h is None:
            skipped.append({"config_id": config_id, "context_accuracy": ctx,
                            "completion": comp, "single_h": single_h})
            continue
        rows.append({
            "config_id": config_id,
            "label": labels.loc[config_id, "label"] if config_id in labels.index else config_id,
            "group": labels.loc[config_id, "group"] if config_id in labels.index else "",
            "ctx_acc": ctx, "n_context_turns": n_ctx,
            "completion": comp, "n_scenarios": n_scen,
            "single_h": single_h, "n_cases": n_cases,
            "multi_hbar": hbar, "n_turns": n_turns,
        })

    n = len(rows)
    if n < 4:
        print(f"[RQ3-ctx] {n} configurations have both settings scored; "
              f"a partial correlation needs at least 4")
        return 1

    ctx = [r["ctx_acc"] for r in rows]
    comp = [r["completion"] for r in rows]
    sh = [r["single_h"] for r in rows]
    hb = [r["multi_hbar"] for r in rows]

    rho_cc, p_cc = spearmanr(ctx, comp)
    rho_ch, p_ch = spearmanr(ctx, sh)          # ctx vs single-turn h
    pr_sh, pp_sh, _ = partial_spearman(ctx, comp, sh)   # control single-turn h (the stated control)
    pr_hb, pp_hb, _ = partial_spearman(ctx, comp, hb)   # control multi-turn h-bar

    summary = {
        "cohort": ("every configuration scored in both the oracle multi-turn setting and the "
                   "single-turn Korean arm, taken from the serving registry"),
        "n_configs": n_cohort,
        "n_models": n,
        "config_ids": [r["config_id"] for r in rows],
        "missing_config_ids": absent,
        "skipped_scored_configs": skipped,
        "spearman_ctx_vs_completion": {"rho": round(rho_cc, 4), "p": round(float(p_cc), 4), "n": n},
        "spearman_ctx_vs_single_turn_h": {"rho": round(rho_ch, 4), "p": round(float(p_ch), 4),
                                          "n": n},
        "partial_spearman_ctx_completion_given_SINGLE_turn_h": {
            "rho": round(pr_sh, 4), "p": round(pp_sh, 4), "n": n,
            "note": "stated control variable (single-turn tool hit h, the tab:overall h column)"},
        "partial_spearman_ctx_completion_given_MULTI_turn_hbar": {
            "rho": round(pr_hb, 4), "p": round(pp_hb, 4), "n": n,
            "note": "control = oracle multi-turn h-bar (reported for comparison)"},
        "variables": {
            "ctx_acc": "oracle aggregate context_accuracy, over turns where context was expected",
            "completion": "oracle aggregate c, over scenarios",
            "single_h": "single-turn aggregate h, over cases",
            "multi_hbar": "oracle aggregate h, over turns",
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "context_accuracy_correlation.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    fields = ["config_id", "label", "group", "ctx_acc", "n_context_turns", "completion",
              "n_scenarios", "single_h", "n_cases", "multi_hbar", "n_turns"]
    with open(OUT_DIR / "context_accuracy_per_model.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[RQ3-ctx] n={n} of {n_cohort} configurations "
          f"({len(absent)} not scored in both settings)")
    if absent:
        print(f"  missing: {', '.join(absent)}")
    for row in skipped:
        print(f"  skipped (scored but no metric): {row}")
    print(f"  Spearman ctx~completion            = {rho_cc:.4f} (p={p_cc:.4f}, n={n})")
    print(f"  Spearman ctx~single_turn_h         = {rho_ch:.4f} (p={p_ch:.4f}, n={n})")
    print(f"  PARTIAL ctx~completion | single_h  = {pr_sh:.4f} (p={pp_sh:.4f}, n={n})")
    print(f"  PARTIAL ctx~completion | multi_hbar = {pr_hb:.4f} (p={pp_hb:.4f}, n={n})")
    print(f"  written: {OUT_DIR / 'context_accuracy_correlation.json'}, "
          f"{OUT_DIR / 'context_accuracy_per_model.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
