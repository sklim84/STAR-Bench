"""Intro teaser: per-subdomain tool-hit radar for four representative models.

Data-driven from star-bench/_experiments/results_kr/eval. Each axis is one of the
five AML subdomains (tab:tool_suite); each polygon is one model's mean tool hit $h$
over the tools in that subdomain. Shows that AML competence is multi-dimensional and
model-specific, with the AML Compliance axis the most divergent.
"""
import json
import glob
import statistics as st
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


PAPER_ROOT = Path(__file__).resolve().parent.parent
EVAL = _SB / "_experiments" / "results_kr" / "eval"
OUT = Path(__file__).resolve().parent / "fig_subdomain_radar.png"

# Five AML subdomains -> member tools (matches tab:tool_suite)
SUBDOMAINS = {
    "Txn\nStats": ["get_statistics", "query_transactions", "get_account_profile",
                   "compare_periods", "get_fraud_type_summary", "get_institution_report"],
    "AML\nDetection": ["analyze_network", "detect_aml_patterns",
                    "rank_risky_transactions", "predict_fraud"],
    "CTR\n& Risk": ["detect_ctr_candidates", "score_account_risk", "detect_monitoring_alerts"],
    "Flow\n& Trend": ["detect_dormant_reactivation", "detect_smurfing_network",
                     "get_trend_analysis", "analyze_channel_risk",
                     "get_receiving_account_profile", "analyze_cross_institution_flow"],
    "AML\nCompliance": ["lookup_fiu_reference_types", "validate_str_fields", "get_aml_glossary"],
}

# Four representative archetypes (substring match on eval model id) -> (display, color)
MODELS = [
    ("google_gemma-4-31B-it",                      "Gemma-4-31B",     "#4E79A7"),
    ("kakaocorp/kanana-2-30b-a3b-thinking-2601",   "Kanana-2-Think",  "#76B7B2"),
    ("DragonLLM_Llama-Open-Finance-8B",            "Llama-Fin-8B",    "#59A14F"),
    ("microsoft_Phi-4-mini-instruct",              "Phi-4-mini",      "#E15759"),
]


def load_profiles():
    files = {json.load(open(f))["model"]: f for f in glob.glob(str(EVAL / "eval_*.json"))}
    prof = {}
    for key, disp, color in MODELS:
        mid = next((m for m in files if key in m), None)
        if mid is None:
            raise SystemExit(f"model not found: {key}")
        cats = json.load(open(files[mid])).get("by_category", {})
        vals = []
        for sd, tools in SUBDOMAINS.items():
            hs = [cats[t]["aggregated"]["primary_tool_hit_rate"] for t in tools if t in cats]
            vals.append(st.mean(hs) if hs else 0.0)
        prof[disp] = (vals, color)
    return prof


def main():
    prof = load_profiles()
    axes = list(SUBDOMAINS.keys())
    N = len(axes)
    ang = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    ang += ang[:1]

    fig, ax = plt.subplots(figsize=(4.3, 3.0), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi / 2)          # first axis at top
    ax.set_theta_direction(-1)              # clockwise
    for disp, (vals, color) in prof.items():
        vv = vals + vals[:1]
        ax.plot(ang, vv, color=color, linewidth=1.7, marker="o", markersize=3,
                markeredgecolor="white", markeredgewidth=0.4, label=disp, zorder=3)
        ax.fill(ang, vv, color=color, alpha=0.06, zorder=2)

    ax.set_xticks(ang[:-1])
    ax.set_xticklabels(axes, fontsize=8.5)
    ax.tick_params(axis="x", pad=4)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels([".25", ".5", ".75", "1"], fontsize=6, color="#888888")
    ax.set_rlabel_position(90)
    ax.spines["polar"].set_color("#cccccc")
    ax.spines["polar"].set_linewidth(0.8)
    ax.grid(color="#d0d0d0", alpha=0.9, linewidth=0.5)
    ax.set_facecolor("white")
    ax.legend(loc="center left", bbox_to_anchor=(1.20, 0.5), ncol=1,
              fontsize=8, frameon=False, handletextpad=0.5,
              handlelength=1.4, labelspacing=0.9)
    plt.tight_layout()
    plt.savefig(OUT, dpi=300, bbox_inches="tight")
    plt.savefig(str(OUT).replace(".png", ".pdf"), bbox_inches="tight")
    plt.close()
    print(f"Saved {OUT}")
    for disp, (vals, _) in prof.items():
        print(f"  {disp:16s} " + " ".join(f"{v:.3f}" for v in vals))


if __name__ == "__main__":
    main()
