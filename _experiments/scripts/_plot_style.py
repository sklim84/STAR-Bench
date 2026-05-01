"""main.tex 기존 figure(generate_paper_figures.py)와 일관된 plot 스타일 헬퍼."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# main.tex 기존 figure (Fig 1-6)와 동일 팔레트
PALETTE = {
    "Qwen": "#4E79A7",
    "Mistral": "#E15759",
    "Llama": "#59A14F",
    "xLAM": "#F28E2B",
    "EXAONE": "#B07AA1",
    "Kanana": "#76B7B2",
    "GLM": "#EDC948",
    "gpt-oss": "#FF9DA7",
    "skt": "#9C755F",
    "DragonLLM": "#76B7B2",
    "Hermes": "#59A14F",
    "Phi": "#FF9DA7",
    "Gemma": "#F28E2B",
    "Ministral": "#E15759",
    "Other": "#BAB0AC",
}

# Think vs NoThink 표준 색
COL_NOTHINK = "#4E79A7"
COL_THINK = "#E15759"

# KR/EN
COL_KR = "#1F4E79"
COL_EN = "#5B8DBE"

# 강조용
COL_GOOD = "#59A14F"   # 초록
COL_BAD = "#E15759"    # 빨강
COL_NEUTRAL = "#4E79A7"  # 파랑
COL_ACCENT = "#F28E2B"   # 주황
COL_PURPLE = "#B07AA1"

# Font sizes
FS_TICK = 10
FS_LABEL = 11
FS_TITLE = 12
FS_LEGEND = 9
FS_ANNOT = 8

def get_color(model):
    """모델명으로부터 계열 색상 추정."""
    m = model.lower()
    for k, v in PALETTE.items():
        if k.lower() in m:
            return v
    return PALETTE["Other"]

def style_axes(ax):
    """축 스타일 통일 (격자 약하게, 큰 변 제거)."""
    ax.grid(alpha=0.3, linestyle="--", linewidth=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=FS_TICK)

def short_name(model, max_len=22):
    """긴 모델명 단축."""
    s = model.split("/")[-1]
    return s if len(s) <= max_len else s[:max_len - 1] + "…"
