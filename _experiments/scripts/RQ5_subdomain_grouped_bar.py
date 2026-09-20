"""RQ5 figure: mean tool hit per AML sub-domain, one bar group per registry group.

Reads only what `RQ5_finance_specialization.py` wrote, so run that step first.
It touches no results tree of its own, and every number here is the one that step
computed from `h`, the primary tool hit (0/1).

Nothing in this file names a model or a group: the bar groups, their display
labels with the configuration count, their order, the sub-domain axis, the cohort
size and the unscored ids all come out of `finance_specialization.json`. That is
what keeps this figure from drawing a cohort the data does not have; the
sub-domain short names below are line-wrapping for the axis, not a selection.

The bars are the registry groups rather than each fine-tune beside the model it
was tuned from, because neither base is a configuration in the serving registry.
`base_comparison` in the JSON names the two absent bases.

출력: _experiments/results_RQ5/fig_subdomain_grouped_bar.{pdf,png}
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

_SB = Path(__file__).resolve().parents[2]   # repository root
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

OUT_DIR = _SB / "_experiments" / "results_RQ5"
SPEC_FILE = OUT_DIR / "finance_specialization.json"

if not SPEC_FILE.exists():
    raise SystemExit(f"{SPEC_FILE} does not exist; run RQ5_finance_specialization.py first")
spec = json.loads(SPEC_FILE.read_text(encoding="utf-8"))

sub_domains = spec["sub_domains"]
group_means = spec["group_means"]
# Groups, their order and their labels are the step's, not this file's.
GROUP_ORDER = spec["group_order"]
GROUP_LABELS = spec["group_labels"]
n_configs = spec["n_configs"]
missing = spec["configs_missing_from_28"]
cohort_note = spec["cohort_note"]

import matplotlib as _mpl  # viridis 계열(blue->green->yellow)로 통일 — 색감 통일 샘플
_VIR = _mpl.colormaps["viridis"]
GROUP_COLORS = {g: _VIR(v) for g, v in
                zip(GROUP_ORDER, np.linspace(0.25, 0.90, len(GROUP_ORDER)))}

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

for grp, off in zip(GROUP_ORDER, offsets):
    vals = [group_means[grp][sd] for sd in sub_domains]
    bars = ax.bar(
        x + off, [v if v is not None else 0.0 for v in vals], bar_w,
        color=GROUP_COLORS[grp],
        alpha=0.88,
        label=GROUP_LABELS[grp],
        edgecolor="white",
        linewidth=0.4,
    )
    # 수치 주석 (상단에, 작게). 값이 없는 서브도메인은 빈 막대가 아니라 "n/a"로 적는다.
    for bar, val in zip(bars, vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.015,
            f"{val:.2f}" if val is not None else "n/a",
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
# Rule 4: the cohort is on the figure, under the legend, so a caption cannot
# claim 28 configurations while the bars average fewer.
ax.text(0.0, 1.30, cohort_note, transform=ax.transAxes, fontsize=6,
        color="#555555", ha="left", va="bottom")

ax.legend(
    fontsize=7.5,
    loc="lower center",
    bbox_to_anchor=(0.5, 1.0),
    frameon=False,
    ncol=n_grp,
    handlelength=1.0,
    handletextpad=0.4,
    columnspacing=0.8,
)

fig.tight_layout()

out_pdf = OUT_DIR / "fig_subdomain_grouped_bar.pdf"
out_png = OUT_DIR / "fig_subdomain_grouped_bar.png"
fig.savefig(out_pdf, dpi=300, bbox_inches="tight")
fig.savefig(out_png, dpi=300, bbox_inches="tight")
print(f"Saved: {out_pdf}")
print(f"Saved: {out_png}")

# 통계 출력
print(f"\n{cohort_note}")
if missing:
    print("not scored: " + ", ".join(missing))
print("\nGroup means per subdomain:")
for sd in sub_domains:
    row = "  " + SD_SHORT.get(sd, sd).replace("\n", " ") + ":"
    for grp in GROUP_ORDER:
        val = group_means[grp][sd]
        row += f"  {GROUP_LABELS[grp]}={'n/a' if val is None else f'{val:.3f}'}"
    print(row)
