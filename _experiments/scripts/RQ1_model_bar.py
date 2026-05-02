"""RQ1 신규 figure: 28개 유효 모델 전체 h bar chart (계열별 색상, h+a 병렬).

출력: _paper/_experiments/results_RQ1/fig_model_bar.{pdf,png}
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# _plot_style import
sys.path.insert(0, os.path.dirname(__file__))
from _plot_style import (
    PALETTE, FS_TICK, FS_LABEL, FS_TITLE, FS_LEGEND, FS_ANNOT,
    get_color, style_axes, short_name,
)

EVAL_DIR = os.path.join(os.path.dirname(__file__), "../../_experiments/results_kr/eval/")
OUT_DIR  = os.path.join(os.path.dirname(__file__), "../../_experiments/results_RQ1/")
os.makedirs(OUT_DIR, exist_ok=True)

OUTLIERS = {
    "google/gemma-4-31B-it",
    "kakaocorp/kanana-2-30b-a3b-instruct",
    "kakaocorp/kanana-2-30b-a3b-thinking-2601__nothink",
    "kakaocorp/kanana-2-30b-a3b-thinking-2601__think",
}

# ── 데이터 로드 ──────────────────────────────────────────────────────────────
rows = []
for fn in sorted(os.listdir(EVAL_DIR)):
    if not fn.endswith(".json"):
        continue
    with open(os.path.join(EVAL_DIR, fn)) as f:
        d = json.load(f)
    if d["model"] in OUTLIERS:
        continue
    h = d["overall"]["primary_tool_hit_rate"]
    a = d["overall"]["avg_param_accuracy"]
    rows.append({"model": d["model"], "h": h, "a": a})

rows.sort(key=lambda x: x["h"])  # ascending for horizontal bar

# ── 표시 이름 단축 ────────────────────────────────────────────────────────────
def display_name(model_id: str) -> str:
    s = model_id.split("/")[-1]
    # think/nothink suffix
    s = s.replace("__nothink", " (NT)").replace("__think", " (T)")
    # common replacements
    replacements = [
        ("kanana-2-30b-a3b-thinking-2601", "Kanana-2-Think"),
        ("kanana-2-30b-a3b-instruct", "Kanana-2-30B"),
        ("Llama-Open-Finance-8B", "Llama-Finance-8B"),
        ("Qwen-Open-Finance-R-8B", "Qwen-Finance-R-8B"),
        ("Hermes-3-Llama-3.1-8B", "Hermes-3-8B"),
        ("Mistral-Small-3.2-24B-Instruct-2506", "Mistral-Small-24B"),
        ("Ministral-3-3B-Instruct-2512", "Ministral-3-3B"),
        ("Qwen3-30B-A3B-Instruct-2507", "Qwen3-30B-A3B"),
        ("Llama-xLAM-2-70b-fc-r", "xLAM-2-70B"),
        ("Llama-xLAM-2-8b-fc-r", "xLAM-2-8B"),
        ("xLAM-2-3b-fc-r", "xLAM-2-3B"),
        ("xLAM-2-1b-fc-r", "xLAM-2-1B"),
        ("Llama-3.2-3B-Instruct", "Llama-3.2-3B"),
        ("Llama-3.3-70B-Instruct", "Llama-3.3-70B"),
        ("Phi-4-mini-instruct", "Phi-4-mini"),
        ("EXAONE-4.0-1.2B", "EXAONE-4.0-1.2B"),
        ("EXAONE-4.0-32B", "EXAONE-4.0-32B"),
        ("gemma-4-E4B-it", "Gemma-4-E4B"),
        ("A.X-4.0-Light", "A.X-4.0-Light"),
    ]
    for old, new in replacements:
        s = s.replace(old, new)
    # trim if still long
    return s if len(s) <= 24 else s[:23] + "…"

labels = [display_name(r["model"]) for r in rows]
h_vals = [r["h"] for r in rows]
a_vals = [r["a"] for r in rows]
colors = [get_color(r["model"]) for r in rows]

n = len(rows)
y = np.arange(n)
bar_h = 0.38

# ── 플롯 ─────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7.5, 6.8))

bars_h = ax.barh(y + bar_h / 2, h_vals, bar_h, color=colors, alpha=0.92, label="$h$ (tool hit)")
bars_a = ax.barh(y - bar_h / 2, a_vals, bar_h, color=colors, alpha=0.45, label="$a$ (param acc.)", hatch="///")

# 수치 주석 (h만, 우측에)
for i, (bar, val) in enumerate(zip(bars_h, h_vals)):
    ax.text(val + 0.005, bar.get_y() + bar.get_height() / 2,
            f"{val:.3f}", va="center", ha="left", fontsize=FS_ANNOT - 1)

ax.axvline(0.5, color="#999999", linewidth=0.8, linestyle="--", alpha=0.6)
ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=FS_TICK)
ax.set_xlabel("Score", fontsize=FS_LABEL)
ax.set_xlim(0, 1.08)
style_axes(ax)

# legend: family colors
seen = set()
handles = []
for r in rows:
    c = get_color(r["model"])
    fam = r["model"].split("/")[0]
    # use short family name
    fam_label = {
        "Qwen": "Qwen", "LGAI-EXAONE": "EXAONE", "skt": "A.X",
        "mistralai": "Mistral", "meta-llama": "Llama",
        "Salesforce": "xLAM", "DragonLLM": "Finance SFT",
        "NousResearch": "Hermes", "microsoft": "Phi",
        "google": "Gemma", "openai": "gpt-oss",
        "kakaocorp": "Kanana",
    }.get(fam, fam)
    if fam_label not in seen:
        seen.add(fam_label)
        handles.append(mpatches.Patch(color=c, label=fam_label))

metric_handles = [
    mpatches.Patch(facecolor="#AAAAAA", alpha=0.92, label="$h$ (tool hit)"),
    mpatches.Patch(facecolor="#AAAAAA", alpha=0.45, hatch="///", label="$a$ (param acc.)"),
]
ax.legend(
    handles=handles + metric_handles,
    fontsize=FS_LEGEND,
    loc="lower right",
    ncol=2,
    framealpha=0.85,
    columnspacing=0.8,
    handlelength=1.2,
)

ax.set_title(
    f"Tool hit $h$ and parameter accuracy $a$ across {n} valid models\n"
    "(Korean prompts, thinking off; sorted by $h$)",
    fontsize=FS_TITLE,
    pad=6,
)

fig.tight_layout()

out_pdf = os.path.join(OUT_DIR, "fig_model_bar.pdf")
out_png = os.path.join(OUT_DIR, "fig_model_bar.png")
fig.savefig(out_pdf, dpi=300, bbox_inches="tight")
fig.savefig(out_png, dpi=300, bbox_inches="tight")
print(f"Saved: {out_pdf}")
print(f"Saved: {out_png}")
