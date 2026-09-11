"""RQ5 figure: Finance SFT / 각자의 base / 한국어 특화 / 소형 범용 모델군의
서브도메인별 h 비교 grouped bar chart.

finance 바로 옆에 base_8b 를 두어 같은 base 에서 금융 SFT 가 무엇을 바꾸는지
막대 두 개로 바로 읽히게 한다.

출력: _experiments/results_RQ5/fig_subdomain_grouped_bar.{pdf,png}
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
GROUP_ORDER  = ["finance", "base_8b", "specialized_kr", "small_general"]
GROUP_LABELS = {
    "finance":       "Finance SFT (8B)",
    "base_8b":       "Their base (8B)",
    "specialized_kr": "KR-specialized (small, ≤7B)",
    "small_general": "General (small, ≤3B)",
}
import matplotlib as _mpl  # viridis 계열(blue->green->yellow)로 통일 — 색감 통일 샘플
_VIR = _mpl.colormaps["viridis"]
GROUP_COLORS = {
    "finance":        _VIR(0.25),   # blue
    "base_8b":        _VIR(0.50),   # teal — finance 바로 옆에 두어 짝 비교가 보이게 한다
    "specialized_kr": _VIR(0.72),   # green
    "small_general":  _VIR(0.90),   # yellow-green
}

# ── 서브도메인 단축명 ─────────────────────────────────────────────────────────
SD_SHORT = {
    "Transaction Inquiry & Statistics": "Txn\nInquiry",
    "Suspicious Activity Detection":    "Suspicious\nDetection",
    "Money Flow & Network Analysis":    "Money Flow\n& Network",
    "Regulatory Reporting":             "Regulatory\nReporting",
}
# 축 라벨은 두 줄로 둔다. 한 줄이면 전폭(5.5in)에서도 이웃 라벨과 겹친다.
sd_labels = [SD_SHORT.get(sd, sd) for sd in sub_domains]

n_sd    = len(sub_domains)
n_grp   = len(GROUP_ORDER)
x       = np.arange(n_sd)
total_w = 0.75
bar_w   = total_w / n_grp
offsets = np.linspace(-(total_w - bar_w) / 2, (total_w - bar_w) / 2, n_grp)

# ── 플롯 ─────────────────────────────────────────────────────────────────────
# 본문 폭(5.5in)에 1:1로 들어가도록 가로로 넓고 낮게 그린다. 글자는 6~8pt.
fig, ax = plt.subplots(figsize=(5.5, 2.0))

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
            fontsize=6,
            color="#1a1a1a",
        )

ax.set_xticks(x)
ax.set_xticklabels(sd_labels, fontsize=7.5, rotation=0, ha="center")
ax.set_ylabel("Tool hit $h$", fontsize=8)
ax.set_ylim(0, 1.18)
# 네모박스: 4면 spine 모두 표시 (fig:bfcl과 일치)
ax.grid(True, alpha=0.3)
ax.tick_params(axis="y", labelsize=7)

ax.legend(
    fontsize=7.5,
    loc="lower center",
    bbox_to_anchor=(0.5, 1.0),
    frameon=False,
    ncol=4,
    handlelength=1.0,
    handletextpad=0.4,
    columnspacing=0.8,
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
