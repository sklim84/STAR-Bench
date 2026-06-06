#!/usr/bin/env python3
"""Regenerate fig_turnwise_line.png from REAL multi-turn benchmark data.

이전 버전(figures/generate_new_figures.py)은 하드코딩 placeholder + 29-모델 세트에 없는
모델(Qwen3-8B, Ministral-14B) 포함.
본 스크립트는 results_mt_oracle/eval/multiturn_*.json에서 per-turn tool_hit를 직접 집계하여
§4.4 RQ3 narrative와 일치하는 6개 모델만 plot.

선정 6개:
  - Mistral-Small-24B (catastrophic, gap −0.170)
  - Ministral-3-3B (catastrophic, 소형 대조)
  - Kanana-2-Think NT (멀티턴 1위, h_bar=0.852)
  - xLAM-2-70B (gap +0.085, 일관성 우세)
  - Llama-3.3-70B (h_bar=0.801)
  - Qwen3.6-27B (gap −0.150, 회복)
"""
import json
from collections import defaultdict
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

MT_DIR = Path("_experiments/results_mt_oracle/eval")
OUT_DIR = Path("_experiments/figures")

TARGETS = [
    ("mistralai/Mistral-Small-3.2-24B-Instruct-2506", "Mistral-Small-24B", "#E15759", "v", "--"),
    ("mistralai/Ministral-3-3B-Instruct-2512",        "Ministral-3-3B",    "#C44E52", "X", "--"),
    ("kakaocorp/kanana-2-30b-a3b-thinking-2601__nothink", "Kanana-2-Think (NT)", "#76B7B2", "s", "-"),
    ("Salesforce/Llama-xLAM-2-70b-fc-r",              "xLAM-2-70B",        "#F28E2B", "o", "-"),
    ("meta-llama/Llama-3.3-70B-Instruct",             "Llama-3.3-70B",     "#59A14F", "D", "-"),
    ("Qwen/Qwen3.6-27B",                              "Qwen3.6-27B",       "#4E79A7", "^", "-"),
]


def load_per_turn(model_id):
    """Return list of mean tool_hit per turn index (1..max_turn)."""
    fname = "multiturn_" + model_id.replace("/", "_").replace(".", "_") + ".json"
    path = MT_DIR / fname
    if not path.exists():
        return None
    d = json.load(path.open())
    by_turn = defaultdict(list)
    for sc in d.get("scenarios", []):
        for t in sc.get("turns", []):
            by_turn[t["turn"]].append(t.get("tool_hit", 0))
    if not by_turn:
        return None
    max_turn = max(by_turn.keys())
    return [sum(by_turn[i]) / len(by_turn[i]) * 100 if by_turn[i] else 0
            for i in range(1, max_turn + 1)]


def main():
    fig, ax = plt.subplots(figsize=(5.5, 4.2))

    max_turn_seen = 0
    for mid, label, color, marker, ls in TARGETS:
        rates = load_per_turn(mid)
        if rates is None:
            print(f"  [skip] {mid}")
            continue
        turns = list(range(1, len(rates) + 1))
        max_turn_seen = max(max_turn_seen, len(rates))
        ax.plot(turns, rates, label=label, color=color,
                marker=marker, markersize=6, linewidth=2,
                linestyle=ls, alpha=0.9)
        print(f"  {label}: {[f'{r:.1f}' for r in rates]}")

    turns = list(range(1, max_turn_seen + 1))
    ax.set_xticks(turns)
    ax.set_xticklabels([f"Turn {t}" for t in turns], fontsize=11)
    ax.set_xlabel("Turn", fontsize=12)
    ax.set_ylabel("Tool hit rate (%)", fontsize=12)
    ax.set_ylim(-5, 105)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax.tick_params(axis="y", labelsize=11)
    ax.grid(True, alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax.axhspan(0, 10, alpha=0.08, color="#E15759")
    ax.text(turns[len(turns) // 2], 3, "Catastrophic failure zone",
            fontsize=9, color="#E15759", fontstyle="italic", ha="center")

    ax.legend(fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.13),
              frameon=True, framealpha=0.9, ncol=3, columnspacing=1.0)
    plt.tight_layout()
    out = OUT_DIR / "fig_turnwise_line.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.savefig(OUT_DIR / "fig_turnwise_line.pdf", dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
