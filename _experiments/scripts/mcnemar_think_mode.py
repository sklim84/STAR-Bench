"""McNemar's test for the thinking-mode effect in STAR-Bench.

For the models the registry serves twice, once reasoning and once not, this
script runs McNemar's test on the paired per-case outcomes:
- b = cases the non-thinking arm got wrong BUT the thinking arm got right
- c = cases the non-thinking arm got right BUT the thinking arm got wrong
- chi^2 = (|b - c| - 1)^2 / (b + c)  (with continuity correction, df = 1)

**A case is correct when `h == 1`**, the binary primary tool hit the paper
reports. McNemar's test is a test on a paired binary outcome, so `h` is the
outcome it is run on, with a continuity correction and a chi-square with one
degree of freedom.

Pairing. In the serving registry the two arms are separate `config_id`s, so the
pairs come from `load.configs()`: two configurations that share a `model` and
differ in `reasoning_mode`, with the mode itself saying which arm is the thinking
one. Nothing is matched on a file name and no list of model names is kept here,
so a pair cannot drift from what was served. A registry pair with only one arm
scored is reported as such instead of being dropped in silence.

Output: `_experiments/results_RQ4/mcnemar_think_round1.json`, under the directory
`regenerate_analysis.py` advertises for this step. It is an object rather than a
bare list so the cohort can travel with the rows: the per-pair rows are under
`pairs`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import chi2

_SB = Path(__file__).resolve().parents[2]  # repository root
if str(_SB) not in sys.path:
    sys.path.insert(0, str(_SB))

from _experiments.scripts.analysis import load  # noqa: E402

OUT_DIR = _SB / "_experiments" / "results_RQ4"
COLUMN = "single"  # the main-table arm: Korean tool schema, Korean questions

# The registry's `reasoning_mode` vocabulary, split into the two arms of a
# toggle. `none` and `always_on` are not a toggle and are not in the map, so a
# model served under either one has no pair here.
THINKING_ARM = {"nothink": "nothink", "effort_low": "nothink",
                "think": "think", "effort_high": "think"}


def registry_pairs() -> list[dict]:
    """Configurations that share a model and differ in reasoning mode."""
    cfgs = load.configs()
    pairs = []
    for model, group in cfgs.groupby("model", sort=False):
        arms: dict[str, list] = {}
        for row in group.itertuples(index=False):
            arm = THINKING_ARM.get(row.reasoning_mode)
            if arm:
                arms.setdefault(arm, []).append(row)
        if len(arms.get("think", [])) != 1 or len(arms.get("nothink", [])) != 1:
            continue
        think, nothink = arms["think"][0], arms["nothink"][0]
        pairs.append({
            "model": model,
            "label": think.label.replace(" (T)", "").strip(),
            "nothink_config_id": nothink.config_id, "think_config_id": think.config_id,
            "nothink_label": nothink.label, "think_label": think.label,
            "nothink_reasoning_mode": nothink.reasoning_mode,
            "think_reasoning_mode": think.reasoning_mode,
        })
    return pairs


def mcnemar(b: int, c: int) -> tuple[float, float]:
    """Return (chi2_statistic, p_value) with continuity correction."""
    if b + c == 0:
        return 0.0, 1.0
    stat = (abs(b - c) - 1) ** 2 / (b + c)
    p = 1.0 - chi2.cdf(stat, df=1)
    return stat, p


def main() -> None:
    table = load.missing()
    scored = set(table.loc[table[COLUMN], "config_id"])
    absent = table.loc[~table[COLUMN], "config_id"].tolist()

    pairs = registry_pairs()
    complete = [p for p in pairs
                if p["nothink_config_id"] in scored and p["think_config_id"] in scored]
    incomplete = [
        {**p, "missing_arm": [cid for cid in (p["nothink_config_id"], p["think_config_id"])
                              if cid not in scored]}
        for p in pairs if p not in complete
    ]

    print(f"Registry holds {len(pairs)} think/nothink pair(s); "
          f"{len(complete)} have both arms scored.")
    for p in complete:
        print(f"  {p['label']}: {p['nothink_config_id']} ({p['nothink_reasoning_mode']}) "
              f"vs {p['think_config_id']} ({p['think_reasoning_mode']})")
    for p in incomplete:
        print(f"  SKIPPED {p['label']}: not scored yet: {', '.join(p['missing_arm'])}")
    print()

    cases = load.single(column=COLUMN)
    by_config = {cid: group.set_index("case_id")["h"]
                 for cid, group in cases.groupby("config_id")}

    rows = []
    for pair in complete:
        n_h = by_config[pair["nothink_config_id"]]
        t_h = by_config[pair["think_config_id"]]
        common = sorted(set(n_h.index) & set(t_h.index))
        if not common:
            continue

        # Rule 1: "correct" is h == 1, not the weighted score at >= 0.9.
        n_correct = n_h.loc[common].to_numpy() == 1
        t_correct = t_h.loc[common].to_numpy() == 1

        a = int(np.sum(~n_correct & ~t_correct))  # both wrong
        b = int(np.sum(~n_correct & t_correct))   # nothink wrong, think correct
        c = int(np.sum(n_correct & ~t_correct))   # nothink correct, think wrong
        d = int(np.sum(n_correct & t_correct))    # both correct

        stat, p = mcnemar(b, c)
        nothink_acc = float(np.mean(n_correct))
        think_acc = float(np.mean(t_correct))

        rows.append({
            "model": pair["model"],
            "label": pair["label"],
            "nothink_config_id": pair["nothink_config_id"],
            "think_config_id": pair["think_config_id"],
            "nothink_reasoning_mode": pair["nothink_reasoning_mode"],
            "think_reasoning_mode": pair["think_reasoning_mode"],
            "n_cases": len(common),
            "nothink_h": round(nothink_acc, 4),
            "think_h": round(think_acc, 4),
            "delta_pp": round((think_acc - nothink_acc) * 100, 2),
            "both_wrong": a,
            "flip_to_correct": b,
            "flip_to_wrong": c,
            "both_correct": d,
            "mcnemar_chi2": round(stat, 3),
            "p_value": f"{p:.4g}",
            "significant_05": bool(p < 0.05),
            "significant_001": bool(p < 0.001),
        })

    rows.sort(key=lambda r: -r["delta_pp"])

    print(f"{'Pair':<26} {'N':>5} {'NoT%':>6} {'Th%':>6} {'dpp':>7} "
          f"{'b':>4} {'c':>4} {'chi2':>7} {'p':>10} {'sig':>5}")
    print("-" * 92)
    for r in rows:
        sig = "***" if r["significant_001"] else ("*" if r["significant_05"] else "n.s.")
        print(f"{r['label']:<26} {r['n_cases']:>5} "
              f"{r['nothink_h']*100:>6.2f} {r['think_h']*100:>6.2f} "
              f"{r['delta_pp']:>+7.2f} {r['flip_to_correct']:>4} {r['flip_to_wrong']:>4} "
              f"{r['mcnemar_chi2']:>7.2f} {r['p_value']:>10} {sig:>5}")

    payload = {
        "cohort": {
            "column": COLUMN,
            "n_configs": len(scored),
            "n_registry": len(table),
            "config_ids": sorted(scored),
            "missing_config_ids": absent,
        },
        "correct_definition": "h == 1 (primary tool hit)",
        "test": "McNemar, continuity corrected, chi-square with df = 1",
        "n_registry_pairs": len(pairs),
        "n_pairs_tested": len(rows),
        "pairs_without_both_arms": incomplete,
        "pairs": rows,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "mcnemar_think_round1.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {out_path}")

    sig_001 = [r for r in rows if r["significant_001"]]
    sig_05 = [r for r in rows if r["significant_05"] and not r["significant_001"]]
    ns = [r for r in rows if not r["significant_05"]]
    print()
    print(f"Cohort: {len(scored)} of {len(table)} configurations scored; "
          f"{len(rows)} of {len(pairs)} registry pairs testable.")
    print(f"Summary: {len(sig_001)} pairs significant at p<0.001, "
          f"{len(sig_05)} at 0.001<=p<0.05, {len(ns)} n.s.")
    if sig_001:
        print("Pairs with p<0.001:")
        for r in sig_001:
            print(f"  {r['label']}: d={r['delta_pp']:+.2f}pp "
                  f"(b={r['flip_to_correct']}, c={r['flip_to_wrong']})")
    if ns:
        print("Pairs n.s. (thinking mode has NO significant effect):")
        for r in ns:
            print(f"  {r['label']}: d={r['delta_pp']:+.2f}pp "
                  f"(b={r['flip_to_correct']}, c={r['flip_to_wrong']})")


if __name__ == "__main__":
    main()
