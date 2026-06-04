"""McNemar's test for Think mode effect in AML-Bench.

For models that were run with both __think and __nothink configurations,
this script runs McNemar's test on paired per-case outcomes:
- b = cases where nothink was wrong BUT think was correct
- c = cases where nothink was correct BUT think was wrong
- chi^2 = (|b - c| - 1)^2 / (b + c)  (with continuity correction)

"Correct" is defined as score >= 0.9 (primary_tool_hit approximation).

Output: per-model McNemar table with chi^2, p-value, effect size.
This answers KFinEval-reviewer-style questions about whether the observed
think-mode improvement is statistically significant and asymmetric.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
from scipy.stats import chi2

_SB = Path(__file__).resolve().parents[2]  # star-bench root
ROUND1_CKPT = _SB / "_experiments" / "results_kr" / "checkpoint"

SCORE_THRESHOLD = 0.9


def load_per_case(fp: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    with fp.open() as f:
        for line in f:
            rec = json.loads(line)
            out[rec["id"]] = rec["score"]
    return out


def find_think_pairs() -> list[tuple[str, Path, Path]]:
    """Return list of (base_model, nothink_path, think_path) pairs."""
    files = list(ROUND1_CKPT.glob("checkpoint_*.jsonl"))
    by_base: dict[str, dict[str, Path]] = {}
    for fp in files:
        name = fp.stem.replace("checkpoint_", "")
        if "__think" in name:
            base = name.replace("__think", "")
            by_base.setdefault(base, {})["think"] = fp
        elif "__nothink" in name:
            base = name.replace("__nothink", "")
            by_base.setdefault(base, {})["nothink"] = fp

    pairs = []
    for base, d in sorted(by_base.items()):
        if "think" in d and "nothink" in d:
            pairs.append((base, d["nothink"], d["think"]))
    return pairs


def mcnemar(b: int, c: int) -> tuple[float, float]:
    """Return (chi2_statistic, p_value) with continuity correction."""
    if b + c == 0:
        return 0.0, 1.0
    stat = (abs(b - c) - 1) ** 2 / (b + c)
    p = 1.0 - chi2.cdf(stat, df=1)
    return stat, p


def main() -> None:
    pairs = find_think_pairs()
    print(f"Found {len(pairs)} think/nothink pairs.")
    print()

    rows = []
    for base, nothink_fp, think_fp in pairs:
        n_scores = load_per_case(nothink_fp)
        t_scores = load_per_case(think_fp)
        common = sorted(set(n_scores) & set(t_scores))
        if not common:
            continue

        n_correct = np.array([n_scores[c] >= SCORE_THRESHOLD for c in common])
        t_correct = np.array([t_scores[c] >= SCORE_THRESHOLD for c in common])

        # contingency
        a = int(np.sum(~n_correct & ~t_correct))  # both wrong
        b = int(np.sum(~n_correct & t_correct))   # nothink wrong, think correct
        c = int(np.sum(n_correct & ~t_correct))   # nothink correct, think wrong
        d = int(np.sum(n_correct & t_correct))    # both correct

        stat, p = mcnemar(b, c)

        nothink_acc = float(np.mean(n_correct))
        think_acc = float(np.mean(t_correct))

        rows.append({
            "model": base,
            "n_cases": len(common),
            "nothink_acc": round(nothink_acc, 4),
            "think_acc": round(think_acc, 4),
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

    print(f"{'Model':<50} {'N':>4} {'NoT%':>6} {'Th%':>6} {'Δpp':>6} "
          f"{'b':>4} {'c':>4} {'chi2':>6} {'p':>10} {'sig':>5}")
    print("-" * 120)
    for r in rows:
        sig = "***" if r["significant_001"] else ("*" if r["significant_05"] else "n.s.")
        print(f"{r['model']:<50} {r['n_cases']:>4} "
              f"{r['nothink_acc']*100:>6.2f} {r['think_acc']*100:>6.2f} "
              f"{r['delta_pp']:>+6.2f} {r['flip_to_correct']:>4} {r['flip_to_wrong']:>4} "
              f"{r['mcnemar_chi2']:>6.2f} {r['p_value']:>10} {sig:>5}")

    out_path = _SB / "_experiments" / "results" / "mcnemar_think_round1.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {out_path}")

    # Summary
    sig_001 = [r for r in rows if r["significant_001"]]
    sig_05 = [r for r in rows if r["significant_05"] and not r["significant_001"]]
    ns = [r for r in rows if not r["significant_05"]]
    print()
    print(f"Summary: {len(sig_001)} pairs significant at p<0.001, "
          f"{len(sig_05)} at 0.001<=p<0.05, {len(ns)} n.s.")
    if sig_001:
        print("Models with p<0.001:")
        for r in sig_001:
            print(f"  {r['model']}: Δ={r['delta_pp']:+.2f}pp (b={r['flip_to_correct']}, c={r['flip_to_wrong']})")
    if ns:
        print("Models n.s. (think mode has NO significant effect):")
        for r in ns:
            print(f"  {r['model']}: Δ={r['delta_pp']:+.2f}pp (b={r['flip_to_correct']}, c={r['flip_to_wrong']})")


if __name__ == "__main__":
    main()
