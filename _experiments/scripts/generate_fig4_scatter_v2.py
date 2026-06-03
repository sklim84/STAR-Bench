"""fig4_kr_en_scatter.png 재생성 (v3, 2026-06-01).

results_{kr,en}/eval 의 29-모델 overall h (KR-KR vs EN-KR) 산점도.
가독성 확보: 짧은 이름 + 핵심 모델만 라벨링(겹침 방지), 단일 컬럼 크기.
"""
import json
import glob
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

from pathlib import Path

PAPER_ROOT = Path(__file__).resolve().parent.parent
STARBENCH = _SB
KR_EVAL = STARBENCH / "_experiments" / "results_kr" / "eval"
EN_EVAL = STARBENCH / "_experiments" / "results_en" / "eval"
OUT = Path(__file__).resolve().parent / "fig4_kr_en_scatter.png"

EXCLUDE = {
    "Qwen_Qwen3-30B-A3B-Instruct-2507", "Qwen_Qwen3-4B-Instruct-2507",
    "Qwen_Qwen3-8B", "Qwen_Qwen3_5-9B__nothink", "Qwen_Qwen3_5-9B__think",
    "Salesforce_Llama-xLAM-2-8b-fc-r", "Salesforce_xLAM-2-1b-fc-r",
    "Salesforce_xLAM-2-32b-fc-r",
}

# 라벨링할 핵심 모델 (substring -> (표시명, ha, va, dx, dy))
# 모두 축 박스 안쪽으로 향하도록 배치(오른쪽 경계 침범 방지).
LABELS = {
    "kakaocorp/kanana-2-30b-a3b-instruct": ("Kanana-2-Instruct", "center", "top", 0, -6),
    "kakaocorp_kanana-2-30b-a3b-instruct": ("Kanana-2-Instruct", "center", "top", 0, -6),
    "meta-llama_Llama-3_3-70B-Instruct":   ("Llama-3.3-70B", "center", "top", 0, -7),
    "skt_A_X-4_0-Light":                   ("A.X-4.0-Light", "left", "bottom", 6, 2),
    # EN-advantaged outlier (좌측 빈 공간으로): text가 점 왼쪽으로 뻗음
    "microsoft_Phi-4-mini-instruct":       ("Phi-4-mini", "right", "center", -6, 0),
    # KR-advantaged outlier (위쪽 빈 공간으로)
    "Salesforce_Llama-xLAM-2-70b-fc-r":    ("xLAM-2-70B", "center", "bottom", 0, 6),
}


def load(evdir):
    out = {}
    for f in glob.glob(str(evdir / "eval_*.json")):
        d = json.load(open(f))
        m = d["model"]
        if m in EXCLUDE:
            continue
        out[m] = d.get("overall", {}).get("primary_tool_hit_rate")
    return out


def label_for(mid):
    # kanana plain instruct (EN-advantaged outlier): exclude 2601/thinking variants
    if ("kanana-2-30b-a3b-instruct" in mid
            and "2601" not in mid and "thinking" not in mid):
        return LABELS["kakaocorp_kanana-2-30b-a3b-instruct"]
    for key, v in LABELS.items():
        if "kanana" in key:
            continue
        if key in mid:
            return v
    return None


def main():
    kr, en = load(KR_EVAL), load(EN_EVAL)
    common = sorted(set(kr) & set(en))
    rows = [(m, kr[m], en[m]) for m in common if kr[m] is not None and en[m] is not None]

    kr_v = np.array([r[1] for r in rows])
    en_v = np.array([r[2] for r in rows])
    delta = kr_v - en_v
    colors = ["#1F4E79" if d >= 0 else "#5B8DBE" for d in delta]

    fig, ax = plt.subplots(figsize=(3.5, 3.15))
    # 라벨된 outlier는 크게 + 굵은 진한 테두리로 강조, 나머지는 연하게
    _hi = [i for i, (m, _, _) in enumerate(rows) if label_for(m) is not None]
    _pl = [i for i in range(len(rows)) if i not in _hi]
    ax.scatter(kr_v[_pl], en_v[_pl], c=[colors[i] for i in _pl], alpha=0.65, s=30,
               edgecolors="white", linewidths=0.5, zorder=3)
    # 강조점은 속을 비워(흰 면) 파란 테두리와 면 색이 확실히 구분되게 함.
    # (면=white, 테두리=blue → 면≠테두리; KR/EN 우위 방향은 대각선 기준 위치로 드러남)
    ax.scatter(kr_v[_hi], en_v[_hi], c="white", alpha=1.0, s=42,
               edgecolors="#1E90FF", linewidths=2.2, zorder=5)

    lo = min(kr_v.min(), en_v.min()) - 0.04
    hi = max(kr_v.max(), en_v.max()) + 0.04
    ax.plot([lo, hi], [lo, hi], "--", color="gray", linewidth=0.9,
            label=r"$h_{\mathrm{KR}}{=}h_{\mathrm{EN}}$", zorder=1)

    for m, k, e in rows:
        lab = label_for(m)
        if lab:
            name, ha, va, dx, dy = lab
            ax.annotate(name, (k, e), fontsize=6.5, color="#222",
                        xytext=(dx, dy), textcoords="offset points",
                        ha=ha, va=va, zorder=6)

    ax.set_xlabel(r"$h_{\mathrm{KR}}$ (Korean query)", fontsize=9)
    ax.set_ylabel(r"$h_{\mathrm{EN}}$ (English query)", fontsize=9)
    ax.tick_params(axis="both", labelsize=8)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)

    ax.legend(fontsize=7.5, loc="lower right", frameon=False)
    ax.grid(True, alpha=0.22)
    plt.tight_layout()
    plt.savefig(OUT, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Saved {OUT}")
    print(f"n={len(rows)} KR={kr_v.mean():.4f} EN={en_v.mean():.4f} "
          f"gap={(kr_v.mean()-en_v.mean())*100:.1f}pp "
          f"KRadv={int((delta>0).sum())} ENadv={int((delta<0).sum())}")


if __name__ == "__main__":
    main()
