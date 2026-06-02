"""RQ5 신규 figure: Finance SFT / 한국어 특화 / 범용 8B 모델군의
서브도메인별 h 비교 grouped bar chart.

출력: _paper/_experiments/results_RQ5/fig_subdomain_grouped_bar.{pdf,png}
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from _plot_style import (
    PALETTE, FS_TICK, FS_LABEL, FS_TITLE, FS_LEGEND, FS_ANNOT,
    COL_GOOD, COL_BAD, COL_NEUTRAL, COL_ACCENT, COL_PURPLE,
    style_axes,
)

SPEC_FILE = os.path.join(
    os.path.dirname(__file__),
    "../../_experiments/results_RQ5/finance_specialization.json",
)
OUT_DIR = os.path.join(os.path.dirname(__file__), "../../_experiments/results_RQ5/")
os.makedirs(OUT_DIR, exist_ok=True)

with open(SPEC_FILE) as f:
    spec = json.load(f)

sub_domains = spec["sub_domains"]
group_means = spec["group_means"]

# ── 표시할 그룹 4개 ──────────────────────────────────────────────────────────
# finance / specialized_kr / general_8b / small_general
GROUP_ORDER  = ["finance", "specialized_kr", "general_8b", "small_general"]
GROUP_LABELS = {
    "finance":       "Finance SFT (8B)",
    "specialized_kr": "KR-specialized (small)",
    "general_8b":    "General 8B",
    "small_general": "Small general (≤3B)",
}
GROUP_COLORS = {
    "finance":        COL_GOOD,     # 초록
    "specialized_kr": COL_PURPLE,   # 보라
    "general_8b":     COL_NEUTRAL,  # 파랑
    "small_general":  COL_ACCENT,   # 주황
}

# ── 서브도메인 단축명 ─────────────────────────────────────────────────────────
SD_SHORT = {
    "Transaction Stats & Inquiry":  "Txn Stats",
    "AML Detection & Reporting":    "AML Detect",
    "CTR, Risk & Monitoring":       "CTR & Risk",
    "Flow, Trend & Channel":        "Flow & Trend",
    "AML Reference":                "AML Compliance",
}
sd_labels = [SD_SHORT.get(sd, sd) for sd in sub_domains]

n_sd    = len(sub_domains)
n_grp   = len(GROUP_ORDER)
x       = np.arange(n_sd)
total_w = 0.75
bar_w   = total_w / n_grp
offsets = np.linspace(-(total_w - bar_w) / 2, (total_w - bar_w) / 2, n_grp)

# ── 플롯 ─────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(4.6, 3.8))

for idx, (grp, off) in enumerate(zip(GROUP_ORDER, offsets)):
    vals = [group_means[grp][sd] for sd in sub_domains]
    bars = ax.bar(
        x + off, vals, bar_w,
        color=GROUP_COLORS[grp],
        alpha=0.88,
        label=GROUP_LABELS[grp],
        edgecolor="white",
        linewidth=0.4,
    )
    # 수치 주석 (상단에, 작게)
    for bar, val in zip(bars, vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.015,
            f"{val:.2f}",
            ha="center", va="bottom",
            rotation=90,
            fontsize=9,
            color="#1a1a1a",
        )

ax.set_xticks(x)
ax.set_xticklabels(sd_labels, fontsize=12, rotation=20, ha="right")
ax.set_ylabel("Tool hit $h$", fontsize=13)
ax.set_ylim(0, 1.18)
ax.axhline(0.5, color="#aaaaaa", linewidth=0.7, linestyle="--", alpha=0.7)
# 네모박스: 4면 spine 모두 표시 (fig:bfcl과 일치)
ax.grid(True, alpha=0.3)
ax.tick_params(axis="y", labelsize=12)

ax.legend(
    fontsize=10,
    loc="upper center",
    bbox_to_anchor=(0.5, -0.26),
    frameon=False,
    ncol=2,
    handlelength=1.2,
    columnspacing=1.2,
)

fig.tight_layout()

out_pdf = os.path.join(OUT_DIR, "fig_subdomain_grouped_bar.pdf")
out_png = os.path.join(OUT_DIR, "fig_subdomain_grouped_bar.png")
fig.savefig(out_pdf, dpi=300, bbox_inches="tight")
fig.savefig(out_png, dpi=300, bbox_inches="tight")
print(f"Saved: {out_pdf}")
print(f"Saved: {out_png}")

# 통계 출력
print("\nGroup means per subdomain:")
for sd in sub_domains:
    row = "  " + SD_SHORT.get(sd, sd) + ":"
    for grp in GROUP_ORDER:
        row += f"  {GROUP_LABELS[grp][:8]}={group_means[grp][sd]:.3f}"
    print(row)
