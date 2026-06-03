"""BFCL v3 vs AML-Bench score comparison figure."""
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

import numpy as np
from pathlib import Path

FIGURES_DIR = Path(__file__).resolve().parent

# BFCL v3 scores (from xLAM paper Table 1, pricepertoken, llm-stats)
# AML-Bench scores (from repro_mean_std.json, 3-round mean)
data = [
    # (short_name, bfcl_v3, aml_score, aml_rank)
    ("xLAM-70B",       0.7819, 0.7900, 33),
    ("xLAM-32B",       0.7583, 0.9333,  3),
    ("GLM-4.7-Flash",  0.7460, 0.9178, 14),
    ("xLAM-8B",        0.7283, 0.8547, 28),
    ("xLAM-3B",        0.6574, 0.7232, 37),
    ("xLAM-1B",        0.4312, 0.5764, 42),
]

names = [d[0] for d in data]
bfcl = [d[1] for d in data]
aml = [d[2] for d in data]
ranks = [d[3] for d in data]

fig, ax = plt.subplots(figsize=(6, 5))

# Scatter
ax.scatter(bfcl, aml, s=100, c="#4E79A7", alpha=0.85, edgecolors="white", linewidths=1.0, zorder=3)

# Labels
for i, name in enumerate(names):
    offset_x, offset_y = 0.008, 0.015
    ha = "left"
    # Adjust specific labels to avoid overlap
    if name == "xLAM-70B":
        offset_y = -0.025
        ha = "left"
    elif name == "xLAM-32B":
        offset_x = -0.008
        ha = "right"
    elif name == "GLM-4.7-Flash":
        offset_x = -0.008
        ha = "right"
        offset_y = -0.02

    rank_str = f"(#{ranks[i]})"
    ax.annotate(f"{name} {rank_str}", (bfcl[i] + offset_x, aml[i] + offset_y),
                fontsize=9, ha=ha, va="bottom",
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white", alpha=0.8, edgecolor="none"))

# Trend line
z = np.polyfit(bfcl, aml, 1)
p = np.poly1d(z)
x_line = np.linspace(0.40, 0.82, 100)
ax.plot(x_line, p(x_line), "--", color="#E15759", alpha=0.6, linewidth=1.5)

# Spearman correlation
from scipy.stats import spearmanr, pearsonr
rho, p_val = spearmanr(bfcl, aml)
r, p_val_r = pearsonr(bfcl, aml)
ax.text(0.05, 0.95, f"Spearman $\\rho$ = {rho:.3f}\nPearson $r$ = {r:.3f}",
        transform=ax.transAxes, fontsize=10, va="top",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#F0F0F0", edgecolor="#CCCCCC"))

# Diagonal reference (perfect correlation)
ax.plot([0.4, 1.0], [0.4, 1.0], "k:", alpha=0.2, linewidth=0.8)

ax.set_xlabel("BFCL v3 Overall Accuracy", fontsize=12)
ax.set_ylabel("AML-Bench Composite Score", fontsize=12)
ax.tick_params(labelsize=11)
ax.set_xlim(0.38, 0.83)
ax.set_ylim(0.50, 1.00)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

plt.tight_layout()
out = FIGURES_DIR / "fig_bfcl_vs_aml.png"
plt.savefig(out, dpi=300, bbox_inches="tight")
plt.savefig(str(out).replace(".png", ".pdf"), bbox_inches="tight")
plt.close()
print(f"Saved: {out}")
print(f"Spearman rho={rho:.3f} (p={p_val:.4f}), Pearson r={r:.3f} (p={p_val_r:.4f})")
