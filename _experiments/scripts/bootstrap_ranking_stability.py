"""Bootstrap Kendall's tau ranking stability for AML-Bench.

Resamples the 1,258 single_turn cases with replacement and recomputes model
rankings for each bootstrap iteration. Reports:
- Mean Kendall's tau between bootstrap ranking and the original ranking
- 95% CI (percentile method)
- % of iterations with tau > 0.8
- Per-model 95% CI for rank position (top-10 focus)

Uses the canonical KR eval JSONs (results_kr/eval) as the source: each case's
`id` and `score` are read from `by_category[*].per_case`. The model cohort is the
28-model set (drops 8 non-cohort variants and the redundant Kanana-2-Instruct-2601).
"""
from __future__ import annotations

import glob
import json
from pathlib import Path
import numpy as np
from scipy.stats import kendalltau

_SB = Path(__file__).resolve().parents[2]
EVAL_DIR = _SB / "_experiments" / "results_kr" / "eval"
EXCLUDE = {  # 28-model cohort: drop 8 non-cohort variants + redundant Kanana-2-Instruct-2601
    "Qwen_Qwen3-30B-A3B-Instruct-2507", "Qwen_Qwen3-4B-Instruct-2507",
    "Qwen_Qwen3-8B", "Qwen_Qwen3_5-9B__nothink", "Qwen_Qwen3_5-9B__think",
    "Salesforce_Llama-xLAM-2-8b-fc-r", "Salesforce_xLAM-2-1b-fc-r",
    "Salesforce_xLAM-2-32b-fc-r",
    "kakaocorp/kanana-2-30b-a3b-instruct-2601",
}
N_ITER = 10_000
SEED = 42

def load_model_scores() -> tuple[list[str], np.ndarray, list[str]]:
    """Return (models, score_matrix[M,N], case_ids) for the 28-model KR cohort."""
    files = sorted(glob.glob(str(EVAL_DIR / "eval_*.json")))
    models: list[str] = []
    per_model: dict[str, dict[str, float]] = {}
    all_ids: set[str] = set()

    for fp in files:
        d = json.load(open(fp))
        model = d["model"]
        if model in EXCLUDE:
            continue
        scores: dict[str, float] = {}
        for cat in d.get("by_category", {}).values():
            for pc in cat.get("per_case", []):
                scores[pc["id"]] = pc["score"]
        if not scores:
            continue
        models.append(model)
        per_model[model] = scores
        all_ids.update(scores.keys())

    case_ids = sorted(all_ids)
    matrix = np.full((len(models), len(case_ids)), np.nan, dtype=np.float32)
    for i, m in enumerate(models):
        for j, cid in enumerate(case_ids):
            v = per_model[m].get(cid)
            if v is not None:
                matrix[i, j] = v
    return models, matrix, case_ids


def compute_model_means(matrix: np.ndarray, case_idx: np.ndarray) -> np.ndarray:
    """Mean score per model over selected case indices, ignoring NaN."""
    sub = matrix[:, case_idx]
    return np.nanmean(sub, axis=1)


def bootstrap(matrix: np.ndarray, models: list[str]) -> dict:
    rng = np.random.default_rng(SEED)
    n_models, n_cases = matrix.shape

    original_means = np.nanmean(matrix, axis=1)
    original_rank = np.argsort(-original_means)  # descending

    taus = np.empty(N_ITER, dtype=np.float64)
    rank_positions = np.zeros((n_models, N_ITER), dtype=np.int32)

    for it in range(N_ITER):
        idx = rng.integers(0, n_cases, size=n_cases)
        means = compute_model_means(matrix, idx)
        # rank 1 = highest score
        ranks = np.empty(n_models, dtype=np.int32)
        order = np.argsort(-means)
        for pos, m in enumerate(order):
            ranks[m] = pos + 1  # 1-indexed
        rank_positions[:, it] = ranks

        tau, _ = kendalltau(-original_means, -means)
        taus[it] = tau

    tau_mean = float(np.mean(taus))
    tau_ci = (float(np.quantile(taus, 0.025)), float(np.quantile(taus, 0.975)))
    frac_above_08 = float(np.mean(taus > 0.8))

    original_ranks = np.empty(n_models, dtype=np.int32)
    order = np.argsort(-original_means)
    for pos, m in enumerate(order):
        original_ranks[m] = pos + 1

    per_model_rank_ci = []
    for i in range(n_models):
        rs = rank_positions[i]
        per_model_rank_ci.append({
            "model": models[i],
            "mean_score": float(original_means[i]),
            "rank": int(original_ranks[i]),
            "rank_ci_low": int(np.quantile(rs, 0.025)),
            "rank_ci_high": int(np.quantile(rs, 0.975)),
            "rank_median": float(np.median(rs)),
        })
    per_model_rank_ci.sort(key=lambda d: d["rank"])

    return {
        "n_models": n_models,
        "n_cases": n_cases,
        "n_iter": N_ITER,
        "tau_mean": tau_mean,
        "tau_ci_low": tau_ci[0],
        "tau_ci_high": tau_ci[1],
        "frac_tau_above_0_8": frac_above_08,
        "per_model": per_model_rank_ci,
    }


def main() -> None:
    print("[1/3] Loading KR eval per-case scores (28-model cohort)...")
    models, matrix, case_ids = load_model_scores()
    print(f"  models: {len(models)}, cases: {len(case_ids)}")
    nan_frac = float(np.mean(np.isnan(matrix)))
    print(f"  NaN fraction: {nan_frac:.4f}")

    print(f"[2/3] Bootstrapping ({N_ITER} iterations)...")
    result = bootstrap(matrix, models)

    print("[3/3] Writing results...")
    out = _SB / "_experiments" / "results" / "ranking_stability.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {out}")

    print()
    print("=" * 60)
    print(f"Mean Kendall's tau: {result['tau_mean']:.4f}")
    print(f"95% CI: [{result['tau_ci_low']:.4f}, {result['tau_ci_high']:.4f}]")
    print(f"% iterations tau > 0.8: {result['frac_tau_above_0_8']:.1%}")
    print("=" * 60)
    print()
    print("Top-10 models with rank 95% CI:")
    for row in result["per_model"][:10]:
        print(f"  #{row['rank']:2d} [{row['rank_ci_low']:2d}-{row['rank_ci_high']:2d}] "
              f"{row['mean_score']:.4f}  {row['model']}")


if __name__ == "__main__":
    main()
