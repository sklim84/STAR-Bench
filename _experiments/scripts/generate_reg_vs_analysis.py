"""Regulatory vs. analysis tool-hit dumbbell plot for RQ2 (single-column).

Per-model vertical dumbbell: analysis-mean h (green) and regulatory-mean h (red)
connected by a thin segment, models sorted by analysis h. Avoids the
false-continuity of connecting a line across categorical models.
"""
import json, glob
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# === relocated to star-bench/_experiments/scripts/; figures saved to BOTH star-bench and paper ===
from pathlib import Path as _P
_SB = _P(__file__).resolve().parents[2]            # star-bench root
_WS = _SB.parent                                    # workspace root
SB_FIG = _SB / "_experiments" / "figures"
PAPER_FIG = _WS / "star-bench-paper" / "figures"
SB_FIG.mkdir(parents=True, exist_ok=True); PAPER_FIG.mkdir(parents=True, exist_ok=True)
import matplotlib.pyplot as _pltD
from matplotlib.figure import Figure as _FigD
__osf, __ofsf = _pltD.savefig, _FigD.savefig
def __dual_plt(fname, *a, **k):
    _n = _P(str(fname)).name
    __osf(str(SB_FIG / _n), *a, **k); __osf(str(PAPER_FIG / _n), *a, **k)
def __dual_fig(self, fname, *a, **k):
    _n = _P(str(fname)).name
    __ofsf(self, str(SB_FIG / _n), *a, **k); __ofsf(self, str(PAPER_FIG / _n), *a, **k)
_pltD.savefig = __dual_plt; _FigD.savefig = __dual_fig
# === end relocation header ===


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EVAL = _SB / "_experiments" / "results_kr" / "eval"
OUT = Path(__file__).resolve().parent

# Regulatory Reporting subdomain (single-turn tools; generate_str is multi-turn only)
REG = {"detect_ctr_candidates", "lookup_fiu_reference_types", "validate_str_fields", "get_aml_glossary"}
SPECIAL = {"multi_tool", "missing_parameters"}
EXCLUDE = {
    "Qwen_Qwen3-30B-A3B-Instruct-2507", "Qwen_Qwen3-4B-Instruct-2507",
    "Qwen_Qwen3-8B", "Qwen_Qwen3_5-9B__nothink", "Qwen_Qwen3_5-9B__think",
    "Salesforce_Llama-xLAM-2-8b-fc-r", "Salesforce_xLAM-2-1b-fc-r",
    "Salesforce_xLAM-2-32b-fc-r",
    "kakaocorp/kanana-2-30b-a3b-instruct-2601",  # drop redundant Kanana release (keep orig + Think)
}
NAME = {
    "DragonLLM_Llama-Open-Finance-8B": "Llama-Fin-8B",
    "DragonLLM_Qwen-Open-Finance-R-8B": "Qwen-Fin-8B",
    "LGAI-EXAONE_EXAONE-4_0-1_2B": "EXAONE-1.2B",
    "LGAI-EXAONE_EXAONE-4_0-32B": "EXAONE-32B",
    "NousResearch_Hermes-3-Llama-3_1-8B": "Hermes-3-8B",
    "Qwen_Qwen3_5-27B__nothink": "Qwen3.5-27B(NT)",
    "Qwen_Qwen3_5-27B__think": "Qwen3.5-27B(T)",
    "Qwen_Qwen3_5-4B__nothink": "Qwen3.5-4B(NT)",
    "Qwen_Qwen3_5-4B__think": "Qwen3.5-4B(T)",
    "Qwen_Qwen3_6-27B": "Qwen3.6-27B",
    "Qwen_Qwen3_6-35B-A3B": "Qwen3.6-35B-A3B",
    "Salesforce_Llama-xLAM-2-70b-fc-r": "xLAM-2-70B",
    "Salesforce_xLAM-2-3b-fc-r": "xLAM-2-3B",
    "google_gemma-4-31B-it": "Gemma-4-31B",
    "google_gemma-4-E4B-it": "Gemma-4-E4B",
    "kakaocorp/kanana-2-30b-a3b-instruct-2601": "Kanana-2-Inst-2601",
    "kakaocorp/kanana-2-30b-a3b-thinking-2601": "Kanana-2-Think",
    "kakaocorp_kanana-2-30b-a3b-instruct": "Kanana-2-Inst",
    "meta-llama_Llama-3_2-3B-Instruct": "Llama-3.2-3B",
    "meta-llama_Llama-3_3-70B-Instruct": "Llama-3.3-70B",
    "microsoft_Phi-4-mini-instruct": "Phi-4-mini",
    "mistralai_Ministral-3-3B-Instruct-2512": "Ministral-3-3B",
    "mistralai_Mistral-Small-3_2-24B-Instruct-2506": "Mistral-Small-24B",
    "openai/gpt-oss-120b__nothink": "gpt-oss-120B(NT)",
    "openai/gpt-oss-120b__think": "gpt-oss-120B(T)",
    "openai/gpt-oss-20b__nothink": "gpt-oss-20B(NT)",
    "openai/gpt-oss-20b__think": "gpt-oss-20B(T)",
    "skt_A_X-4_0": "A.X-4.0",
    "skt_A_X-4_0-Light": "A.X-4.0-Light",
}

import matplotlib as _mpl  # 색감 통일: viridis 2색 (analysis=blue, regulatory=green)
_VIR = _mpl.colormaps["viridis"]
C_ANA, C_REG = _VIR(0.25), _VIR(0.72)

rows = []
for f in sorted(glob.glob(str(EVAL / "eval_*.json"))):
    d = json.load(open(f))
    mid = d.get("model", "?")
    if mid in EXCLUDE:
        continue
    cats = d.get("by_category", {})
    reg = [cats[t]["aggregated"]["primary_tool_hit_rate"] for t in REG if t in cats]
    ana = [cats[t]["aggregated"]["primary_tool_hit_rate"]
           for t in cats if t not in REG and t not in SPECIAL]
    if not reg or not ana:
        continue
    rows.append((NAME.get(mid, mid), sum(reg) / len(reg), sum(ana) / len(ana)))

rows.sort(key=lambda r: r[2])  # sort by analysis h ascending
labels = [r[0] for r in rows]
ana = np.array([r[2] for r in rows])
reg = np.array([r[1] for r in rows])
x = np.arange(len(rows))

# single-column (\columnwidth): set figsize to the column width (~3.45in) so the
# PDF is NOT downscaled in LaTeX and the tick/legend fonts render at true size.
fig, ax = plt.subplots(figsize=(3.45, 2.7))
ax.vlines(x, reg, ana, color="#BBBBBB", lw=0.9, zorder=1)
ax.scatter(x, ana, s=16, color=C_ANA, zorder=3, label="Analysis tools")
ax.scatter(x, reg, s=16, color=C_REG, marker="s", zorder=3, label="Regulatory tools")

ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=90, ha="center", fontsize=6.5)
ax.tick_params(axis="y", labelsize=8)
ax.set_ylabel("Mean tool hit $h$", fontsize=8)
ax.set_ylim(0.25, 0.95)
ax.set_xlim(-0.7, len(rows) - 0.3)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.legend(fontsize=6, loc="lower right", frameon=True, framealpha=0.9,
          markerscale=0.9, handletextpad=0.3, borderpad=0.3)

plt.tight_layout()
plt.savefig(OUT / "fig_regulatory_vs_analysis_v2.png", dpi=300, bbox_inches="tight")
plt.savefig(OUT / "fig_regulatory_vs_analysis_v2.pdf", bbox_inches="tight")
plt.close()
print("Saved fig_regulatory_vs_analysis_v2.{png,pdf}")
print(f"n={len(rows)} reg={reg.mean():.3f} ana={ana.mean():.3f} "
      f"gap={(ana.mean()-reg.mean())*100:.1f}pp")
