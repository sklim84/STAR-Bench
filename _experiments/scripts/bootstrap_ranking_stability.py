"""Bootstrap Kendall's tau ranking stability for STAR-Bench.

Resamples the single-turn cases with replacement and recomputes the
configuration ranking for each bootstrap iteration. Reports:
- Mean Kendall's tau between the bootstrap ranking and the original ranking
- 95% CI (percentile method)
- % of iterations with tau > 0.8
- Per-configuration 95% CI for rank position (top-10 focus)

**A case is correct when `h == 1`**, so the ranking is over the mean of `h`, the
binary primary tool hit the paper reports. The resampling is 10,000 iterations
under seed 42, with percentile intervals and Kendall tau.

Cohort. The rows are the configurations `load.single()` returns, which is the
registry, so a configuration cannot leak in by appearing in a directory. Display
names come from `label`. The output names how many of the registry's
configurations are scored and which ids are missing.

Output: `_experiments/results_RQ1/ranking_stability.json`, under the directory
`regenerate_analysis.py` advertises for this step.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import kendalltau

_SB = Path(__file__).resolve().parents[2]  # repository root
if str(_SB) not in sys.path:
    sys.path.insert(0, str(_SB))

from _experiments.scripts.analysis import load  # noqa: E402

OUT_DIR = _SB / "_experiments" / "results_RQ1"
COLUMN = "single"  # the main-table arm: Korean tool schema, Korean questions
N_ITER = 10_000
SEED = 42


def cohort() -> dict:
    """How much of the 28-configuration registry this run covers (rule 4)."""
    table = load.missing()
    scored = table.loc[table[COLUMN], "config_id"].tolist()
    absent = table.loc[~table[COLUMN], "config_id"].tolist()
    return {"column": COLUMN, "n_configs": len(scored), "n_registry": len(table),
            "config_ids": scored, "missing_config_ids": absent}


def load_config_hits() -> tuple[list[str], list[str], np.ndarray, list[str]]:
    """(config_ids, labels, h_matrix[C,N], case_ids) for the scored cohort.

    A cell is 1 when the configuration got that case right and 0 when it did
    not; NaN means the configuration has no row for the case, which a mean over
    the column skips rather than scoring as a miss.
    """
    cases = load.single(column=COLUMN)
    matrix_frame = cases.pivot(index="config_id", columns="case_id", values="h")
    config_ids = list(matrix_frame.index)
    case_ids = list(matrix_frame.columns)
    labels_by_id = cases.drop_duplicates("config_id").set_index("config_id")["label"]
    labels = [labels_by_id.get(c, c) for c in config_ids]
    return config_ids, labels, matrix_frame.to_numpy(dtype=np.float32), case_ids


def compute_config_means(matrix: np.ndarray, case_idx: np.ndarray) -> np.ndarray:
    """Mean h per configuration over the selected case indices, ignoring NaN."""
    sub = matrix[:, case_idx]
    return np.nanmean(sub, axis=1)


def bootstrap(matrix: np.ndarray, config_ids: list[str], labels: list[str]) -> dict:
    rng = np.random.default_rng(SEED)
    n_configs, n_cases = matrix.shape

    original_means = np.nanmean(matrix, axis=1)

    taus = np.empty(N_ITER, dtype=np.float64)
    rank_positions = np.zeros((n_configs, N_ITER), dtype=np.int32)

    for it in range(N_ITER):
        idx = rng.integers(0, n_cases, size=n_cases)
        means = compute_config_means(matrix, idx)
        # rank 1 = highest h
        ranks = np.empty(n_configs, dtype=np.int32)
        order = np.argsort(-means)
        for pos, m in enumerate(order):
            ranks[m] = pos + 1  # 1-indexed
        rank_positions[:, it] = ranks

        tau, _ = kendalltau(-original_means, -means)
        taus[it] = tau

    tau_mean = float(np.mean(taus))
    tau_ci = (float(np.quantile(taus, 0.025)), float(np.quantile(taus, 0.975)))
    frac_above_08 = float(np.mean(taus > 0.8))

    original_ranks = np.empty(n_configs, dtype=np.int32)
    order = np.argsort(-original_means)
    for pos, m in enumerate(order):
        original_ranks[m] = pos + 1

    per_config_rank_ci = []
    for i in range(n_configs):
        rs = rank_positions[i]
        per_config_rank_ci.append({
            "config_id": config_ids[i],
            "label": labels[i],
            "h_mean": float(original_means[i]),
            "n_cases": int(np.sum(~np.isnan(matrix[i]))),
            "rank": int(original_ranks[i]),
            "rank_ci_low": int(np.quantile(rs, 0.025)),
            "rank_ci_high": int(np.quantile(rs, 0.975)),
            "rank_median": float(np.median(rs)),
        })
    per_config_rank_ci.sort(key=lambda d: d["rank"])

    return {
        "n_configs": n_configs,
        "n_cases": n_cases,
        "n_iter": N_ITER,
        "seed": SEED,
        "tau_mean": tau_mean,
        "tau_ci_low": tau_ci[0],
        "tau_ci_high": tau_ci[1],
        "frac_tau_above_0_8": frac_above_08,
        "per_model": per_config_rank_ci,
    }


def main() -> None:
    covered = cohort()
    print(f"[1/3] Loading single-turn h per case "
          f"({covered['n_configs']} of {covered['n_registry']} configurations)...")
    config_ids, labels, matrix, case_ids = load_config_hits()
    print(f"  configurations: {len(config_ids)}, cases: {len(case_ids)}")
    if covered["missing_config_ids"]:
        print(f"  not scored yet ({len(covered['missing_config_ids'])}): "
              f"{', '.join(covered['missing_config_ids'])}")
    nan_frac = float(np.mean(np.isnan(matrix)))
    print(f"  NaN fraction: {nan_frac:.4f}")

    print(f"[2/3] Bootstrapping ({N_ITER} iterations, seed {SEED})...")
    result = bootstrap(matrix, config_ids, labels)
    result["cohort"] = covered
    result["nan_fraction"] = nan_frac
    result["ranked_on"] = ("mean h (primary tool hit); a case is correct when "
                           "h == 1")

    print("[3/3] Writing results...")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "ranking_stability.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {out}")

    print()
    print("=" * 60)
    print(f"Mean Kendall's tau: {result['tau_mean']:.4f}")
    print(f"95% CI: [{result['tau_ci_low']:.4f}, {result['tau_ci_high']:.4f}]")
    print(f"% iterations tau > 0.8: {result['frac_tau_above_0_8']:.1%}")
    print(f"Cohort: {covered['n_configs']} of {covered['n_registry']} configurations")
    print("=" * 60)
    print()
    print("Top-10 configurations with rank 95% CI:")
    for row in result["per_model"][:10]:
        print(f"  #{row['rank']:2d} [{row['rank_ci_low']:2d}-{row['rank_ci_high']:2d}] "
              f"{row['h_mean']:.4f}  {row['label']} ({row['config_id']})")


if __name__ == "__main__":
    main()
