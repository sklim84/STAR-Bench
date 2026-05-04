#!/usr/bin/env python3
"""Generate fine-grained per-model, per-category results tables for paper appendix.

Outputs:
  - _experiments/results/error_analysis_fine_grained.json
  - _experiments/results/error_analysis_fine_grained.xlsx
"""

import json
import glob
import sys
from pathlib import Path
from collections import defaultdict

import pandas as pd
import numpy as np

# ── paths ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
CKPT_DIR = ROOT / "_experiments" / "results" / "round1" / "checkpoint"
OUT_DIR = ROOT / "_experiments" / "results"

EXCLUDE_ERRORS = {"api_error", "parse_fail"}


# ── 1. Load & deduplicate ───────────────────────────────────────────────
def load_all_checkpoints() -> pd.DataFrame:
    rows = []
    for fp in sorted(CKPT_DIR.glob("checkpoint_*.jsonl")):
        for line in fp.open():
            rows.append(json.loads(line))
    df = pd.DataFrame(rows)
    print(f"Raw records: {len(df)}")

    # Exclude error types
    before = len(df)
    df = df[~df["error_type"].isin(EXCLUDE_ERRORS)]
    print(f"After excluding {EXCLUDE_ERRORS}: {len(df)} (removed {before - len(df)})")

    # Keep last entry per (model, case_id) for models with >1258 lines
    df = df.drop_duplicates(subset=["model", "case_id"], keep="last")
    print(f"After dedup by (model, case_id): {len(df)}")

    return df


# ── 2. Build pivot tables ───────────────────────────────────────────────
def build_pivot(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """Model (rows) × Category (cols) pivot of mean values."""
    pivot = df.pivot_table(
        index="model", columns="category", values=value_col, aggfunc="mean"
    )
    # Add overall mean column
    pivot["__Overall__"] = pivot.mean(axis=1)
    # Sort by overall descending
    pivot = pivot.sort_values("__Overall__", ascending=False)
    return pivot


def build_difficulty_table(df: pd.DataFrame) -> pd.DataFrame:
    """Model (rows) × Difficulty (cols) average score."""
    pivot = df.pivot_table(
        index="model", columns="difficulty", values="score", aggfunc="mean"
    )
    pivot["__Overall__"] = pivot.mean(axis=1)
    pivot = pivot.sort_values("__Overall__", ascending=False)
    return pivot


def build_category_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per-category summary stats across all models."""
    # First get per-model per-category means
    model_cat = df.pivot_table(
        index="model", columns="category", values="score", aggfunc="mean"
    )
    stats = pd.DataFrame({
        "mean": model_cat.mean(),
        "std": model_cat.std(),
        "min": model_cat.min(),
        "max": model_cat.max(),
        "median": model_cat.median(),
        "n_cases": df.groupby("category")["case_id"].nunique(),
    })
    stats = stats.sort_values("mean", ascending=False)
    return stats


# ── 3. Pretty-print top/bottom ──────────────────────────────────────────
def print_top_bottom(pivot: pd.DataFrame, n: int = 5):
    categories = [c for c in pivot.columns if c != "__Overall__"]
    for cat in sorted(categories):
        col = pivot[cat].dropna().sort_values(ascending=False)
        top = col.head(n)
        bot = col.tail(n)
        print(f"\n{'='*60}")
        print(f"Category: {cat}")
        print(f"  Top-{n}:")
        for m, v in top.items():
            print(f"    {m:55s} {v:.4f}")
        print(f"  Bottom-{n}:")
        for m, v in bot.items():
            print(f"    {m:55s} {v:.4f}")


# ── 4. Export ────────────────────────────────────────────────────────────
def to_json(tables: dict, path: Path):
    """Export all tables as JSON (DataFrames → dict)."""
    out = {}
    for name, tbl in tables.items():
        out[name] = json.loads(tbl.to_json(orient="split", force_ascii=False))
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nSaved JSON: {path}")


def to_excel(tables: dict, path: Path):
    """Export all tables as Excel with separate sheets."""
    # Sheet name max 31 chars
    sheet_names = {
        "score_matrix": "Score (Model x Cat)",
        "tool_hit_matrix": "ToolHit (Model x Cat)",
        "param_acc_matrix": "ParamAcc (Model x Cat)",
        "difficulty_breakdown": "Difficulty Breakdown",
        "category_summary": "Category Summary",
    }
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for key, tbl in tables.items():
            sheet = sheet_names.get(key, key[:31])
            df_out = tbl.copy()
            # Round floats
            for col in df_out.select_dtypes(include=[np.floating]).columns:
                df_out[col] = df_out[col].round(4)
            df_out.to_excel(writer, sheet_name=sheet)
    print(f"Saved Excel: {path}")


# ── main ─────────────────────────────────────────────────────────────────
def main():
    df = load_all_checkpoints()

    print(f"\nModels: {df['model'].nunique()}")
    print(f"Categories: {df['category'].nunique()}")
    print(f"Difficulties: {sorted(df['difficulty'].unique())}")

    # Build tables
    score_matrix = build_pivot(df, "score")
    tool_hit_matrix = build_pivot(df, "primary_tool_hit")
    param_acc_matrix = build_pivot(df, "param_accuracy")
    difficulty_tbl = build_difficulty_table(df)
    cat_summary = build_category_summary(df)

    tables = {
        "score_matrix": score_matrix,
        "tool_hit_matrix": tool_hit_matrix,
        "param_acc_matrix": param_acc_matrix,
        "difficulty_breakdown": difficulty_tbl,
        "category_summary": cat_summary,
    }

    # Print summary
    print("\n" + "=" * 70)
    print("SCORE MATRIX — Top/Bottom 5 per category")
    print("=" * 70)
    print_top_bottom(score_matrix)

    # Overall ranking
    print("\n" + "=" * 70)
    print("OVERALL RANKING (by mean score across categories)")
    print("=" * 70)
    overall = score_matrix["__Overall__"].sort_values(ascending=False)
    for i, (m, v) in enumerate(overall.items(), 1):
        print(f"  {i:2d}. {m:55s} {v:.4f}")

    # Difficulty breakdown summary
    print("\n" + "=" * 70)
    print("DIFFICULTY BREAKDOWN (top-10)")
    print("=" * 70)
    print(difficulty_tbl.head(10).to_string())

    # Category summary
    print("\n" + "=" * 70)
    print("CATEGORY SUMMARY STATS")
    print("=" * 70)
    print(cat_summary.to_string())

    # Export
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    to_json(tables, OUT_DIR / "error_analysis_fine_grained.json")
    to_excel(tables, OUT_DIR / "error_analysis_fine_grained.xlsx")


if __name__ == "__main__":
    main()
