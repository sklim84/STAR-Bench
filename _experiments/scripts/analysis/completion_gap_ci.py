#!/usr/bin/env python3
"""Is the completion spread inside the single-turn band larger than sampling noise?

Section 4.4 rests on one comparison: configurations that sit within a few points
of one another on single-turn tool hit complete very different fractions of the
STR workflows. That claim is taken over 50 multi-turn scenarios, few enough that
a reader should be told whether the spread survives resampling.

Every configuration sees the same 50 scenarios, so the test is paired: resample
scenarios, not configurations, and carry all configurations through the same
resampled index. Two statistics are reported per pair, a percentile interval on
the paired difference and McNemar's exact test on the discordant scenarios, the
second of which does not depend on the bootstrap at all.

The spread of the band as a whole (max minus min) is reported for completeness,
but as the range of noisy estimates it is biased upward and the paper quotes the
pairwise numbers instead.

Usage:  PYTHONPATH=. python _experiments/scripts/analysis/completion_gap_ci.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _experiments.scripts.analysis import load  # noqa: E402

BAND = 9          # the configurations Section 4.4 calls the band, by single-turn rank
SEED = 20260923
DRAWS = 10_000


def paired(piv, index, better: str, worse: str):
    difference = piv[better].values - piv[worse].values
    draws = difference[index].mean(axis=1)
    low, high = np.percentile(draws, [2.5, 97.5])
    b = int(((piv[better] == 1) & (piv[worse] == 0)).sum())
    c = int(((piv[better] == 0) & (piv[worse] == 1)).sum())
    p = stats.binomtest(b, b + c, 0.5).pvalue if b + c else float("nan")
    return difference.mean(), low, high, b, c, p


def main() -> int:
    hit = load.single("single").groupby("label")["h"].mean().sort_values(ascending=False)
    scenarios, _turns = load.multiturn("oracle")
    piv = scenarios.pivot_table(index="scenario_id", columns="label", values="c")
    band = list(hit.head(BAND).index)
    completion = piv[band].mean()

    rng = np.random.default_rng(SEED)
    n = len(piv)
    index = rng.integers(0, n, size=(DRAWS, n))

    print(f"band of {BAND}: single-turn tool hit {hit[band].min():.4f} to {hit[band].max():.4f}"
          f" ({(hit[band].max() - hit[band].min()) * 100:.1f} points), over {n} scenarios")
    for label in band:
        print(f"  {label:<20} h={hit[label]:.3f}  completion={completion[label]:.2f}")

    draws = piv[band].values[index].mean(axis=1)
    spread = draws.max(axis=1) - draws.min(axis=1)
    low, high = np.percentile(spread, [2.5, 97.5])
    print(f"\nband spread {completion.max() - completion.min():.2f}"
          f"  95% percentile interval [{low:.2f}, {high:.2f}]  (upward biased, not quoted)")

    worse = completion.idxmin()
    print("\npaired comparisons against the band's lowest completion"
          f" ({worse}, {completion[worse]:.2f}):")
    for better in (completion.idxmax(), piv.mean().idxmax()):
        mean, low, high, b, c, p = paired(piv, index, better, worse)
        print(f"  {better:<20} {mean:+.2f}  95% CI [{low:+.2f}, {high:+.2f}]"
              f"  McNemar b={b} c={c} p={p:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
