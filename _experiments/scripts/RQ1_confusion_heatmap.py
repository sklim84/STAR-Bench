"""RQ1 신규 figure: 도구 혼동 heatmap (top confused tool pairs).

wrong_func 오류 중 called_tool != expected_tool인 케이스를 집계하여
상위 혼동 도구 행·열만 추출한 heatmap을 생성한다.

출력: _experiments/results_RQ1/fig_confusion_heatmap.{pdf,png}
"""
import json
import os
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from _plot_style import FS_TICK, FS_LABEL, FS_TITLE, FS_ANNOT, style_axes

EVAL_DIR = os.path.join(os.path.dirname(__file__), "../../_experiments/results_kr/eval/")
OUT_DIR  = os.path.join(os.path.dirname(__file__), "../../_experiments/results_RQ1/")
os.makedirs(OUT_DIR, exist_ok=True)

# 28-모델 코호트: 구세대/중간크기 변형 8개 + 중복 Kanana 릴리스 제외.
# 다른 분석 스크립트(generate_new_figures, bootstrap_ranking_stability, RQ3,
# RQ_oracle_vs_real, RQ_str_generation_quality, generate_reg_vs_analysis,
# generate_fig4_scatter_v2)와 동일하며, 본문의 "28 configurations"와 맞는다.
EXCLUDE_MODELS = {
    "Qwen_Qwen3-30B-A3B-Instruct-2507", "Qwen_Qwen3-4B-Instruct-2507",
    "Qwen_Qwen3-8B", "Qwen_Qwen3_5-9B__nothink", "Qwen_Qwen3_5-9B__think",
    "Salesforce_Llama-xLAM-2-8b-fc-r", "Salesforce_xLAM-2-1b-fc-r",
    "Salesforce_xLAM-2-32b-fc-r",
    "kakaocorp/kanana-2-30b-a3b-instruct-2601",
}

# 표기 정규화 전용 (safe 파일명 -> 논문 표기). 코호트 선택에는 쓰지 않는다.
_CANONICAL_NAMES = {
    "skt/A.X-4.0-Light", "skt/A.X-4.0",
    "LGAI-EXAONE/EXAONE-4.0-1.2B", "LGAI-EXAONE/EXAONE-4.0-32B",
    "kakaocorp/kanana-2-30b-a3b-instruct",
    "kakaocorp/kanana-2-30b-a3b-thinking-2601__nothink",
    "kakaocorp/kanana-2-30b-a3b-thinking-2601__think",
    "DragonLLM/Llama-Open-Finance-8B", "DragonLLM/Qwen-Open-Finance-R-8B",
    "openai/gpt-oss-20b__nothink", "openai/gpt-oss-20b__think",
    "openai/gpt-oss-120b__nothink", "openai/gpt-oss-120b__think",
    "meta-llama/Llama-3.2-3B-Instruct", "meta-llama/Llama-3.3-70B-Instruct",
    "mistralai/Ministral-3-3B-Instruct-2512",
    "mistralai/Mistral-Small-3.2-24B-Instruct-2506",
    "microsoft/Phi-4-mini-instruct",
    "Qwen/Qwen3.5-4B__nothink", "Qwen/Qwen3.5-4B__think",
    "Qwen/Qwen3.5-27B__nothink", "Qwen/Qwen3.5-27B__think",
    "Qwen/Qwen3.6-27B", "Qwen/Qwen3.6-35B-A3B",
    "Salesforce/xLAM-2-3b-fc-r", "Salesforce/Llama-xLAM-2-70b-fc-r",
    "google/gemma-4-E4B-it", "google/gemma-4-31B-it",
    "NousResearch/Hermes-3-Llama-3.1-8B",
}


_SAFE_TO_CANONICAL = {m.replace('/', '_').replace('.', '_'): m for m in _CANONICAL_NAMES}
def _canonicalize(m): return _SAFE_TO_CANONICAL.get(m, m)
# ── 집계: expected_tool -> called_tool -> count ───────────────────────────────
conf = defaultdict(lambda: defaultdict(int))
n_models_used = 0

for fn in sorted(os.listdir(EVAL_DIR)):
    if not fn.endswith(".json"):
        continue
    with open(os.path.join(EVAL_DIR, fn)) as f:
        d = json.load(f)
    if d["model"] in EXCLUDE_MODELS or _canonicalize(d["model"]) in EXCLUDE_MODELS:
        continue
    n_models_used += 1
    for cat, cat_data in d["by_category"].items():
        for case in cat_data["per_case"]:
            if case["error_type"] == "wrong_func":
                called = case.get("called_tools", [])
                if called and called[0] != cat:
                    conf[cat][called[0]] += 1

# ── 상위 혼동 도구 선택 ───────────────────────────────────────────────────────
# 각 expected_tool에서 가장 많이 confused된 called_tool의 합산 기준 상위 12개 expected
tool_total_conf = {exp: sum(v.values()) for exp, v in conf.items()}
top_expected = sorted(tool_total_conf, key=lambda x: -tool_total_conf[x])[:10]

# top_expected에 등장하는 called_tool 중 상위 10개
called_counter: dict[str, int] = defaultdict(int)
for exp in top_expected:
    for called, cnt in conf[exp].items():
        called_counter[called] += cnt
top_called = sorted(called_counter, key=lambda x: -called_counter[x])[:10]

# ── 단축 이름 매핑 ────────────────────────────────────────────────────────────
SHORT = {
    "get_statistics":             "get_stats",
    "query_transactions":         "qry_txn",
    "analyze_network":            "analyze_net",
    "predict_fraud":              "pred_fraud",
    "detect_aml_patterns":        "aml_pat",
    "multi_tool":                 "multi_tool",
    "get_account_profile":        "acct_profile",
    "get_fraud_type_summary":     "fraud_type_sum",
    "compare_periods":            "cmp_period",
    "get_institution_report":     "inst_rpt",
    "rank_risky_transactions":    "rank_risky",
    "detect_ctr_candidates":      "ctr_cand",
    "score_account_risk":         "acct_risk",
    "detect_monitoring_alerts":   "mon_alert",
    "detect_dormant_reactivation":"dormant",
    "detect_smurfing_network":    "smurf_net",
    "get_trend_analysis":         "trend",
    "analyze_channel_risk":       "chan_risk",
    "get_receiving_account_profile":"recv_prof",
    "analyze_cross_institution_flow":"cross_inst",
    "missing_parameters":         "miss_p",
    "lookup_fiu_reference_types": "fiu_ref",
    "validate_str_fields":        "val_str",
    "get_aml_glossary":           "glossary",
}

def sn(t: str) -> str:
    return SHORT.get(t, t[:10])

# ── 행렬 구성 ────────────────────────────────────────────────────────────────
mat = np.zeros((len(top_expected), len(top_called)), dtype=float)
for i, exp in enumerate(top_expected):
    for j, called in enumerate(top_called):
        mat[i, j] = conf[exp].get(called, 0)

row_labels = [sn(t) for t in top_expected]
col_labels = [sn(t) for t in top_called]

# ── 플롯 ─────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(5.0, 4.3))

# cmap: white -> deep blue (zero는 흰색). PowerNorm(0.5)로 중간값 색 대비 강화
# (205 같은 이상치가 선형 스케일을 지배하는 문제 완화).
from matplotlib.colors import PowerNorm
import numpy as _np
cmap = matplotlib.colormaps["viridis_r"].copy()  # 색감 통일: viridis 역방향(큰 값=진한색, 0 셀은 흰색)
cmap.set_bad("#F2F5E1")  # 0 셀: 순백 대신 viridis 저단(연노랑)에 가까운 옅은 톤
_mat_disp = _np.where(mat > 0, mat, _np.nan)
im = ax.imshow(_mat_disp, aspect="auto", cmap=cmap,
               norm=PowerNorm(gamma=0.5, vmin=0, vmax=mat.max()))

# 수치 주석: 모든 0 아닌 셀에 표기(colorbar 대체). 핵심 혼동(>=BOLD_MIN)은 굵게/크게.
BOLD_MIN = 40
for i in range(mat.shape[0]):
    for j in range(mat.shape[1]):
        v = int(mat[i, j])
        if v == 0:
            continue
        text_color = "white" if im.norm(mat[i, j]) > 0.5 else "black"
        big = v >= BOLD_MIN
        ax.text(j, i, str(v), ha="center", va="center",
                fontsize=FS_ANNOT if big else FS_ANNOT - 2,
                color=text_color, fontweight="bold" if big else "normal")

ax.set_xticks(range(len(col_labels)))
ax.set_xticklabels(col_labels, rotation=45, ha="right", fontsize=FS_TICK)
ax.set_yticks(range(len(row_labels)))
ax.set_yticklabels(row_labels, fontsize=FS_TICK)
ax.set_xlabel("Called tool (wrong)", fontsize=FS_LABEL)
ax.set_ylabel("Expected tool", fontsize=FS_LABEL)

# colorbar 제거: 각 셀에 수치를 직접 표기하므로 색 스케일 바는 중복(색은 시각 보조).
fig.tight_layout()

out_pdf = os.path.join(OUT_DIR, "fig_confusion_heatmap.pdf")
out_png = os.path.join(OUT_DIR, "fig_confusion_heatmap.png")
fig.savefig(out_pdf, dpi=300, bbox_inches="tight")
fig.savefig(out_png, dpi=300, bbox_inches="tight")
print(f"Saved: {out_pdf}")
print(f"Saved: {out_png}")

# 통계 출력
print(f"\nTotal wrong_func pairs aggregated: {int(mat.sum())}")
print("Top-5 confusion pairs:")
pairs = []
for i, exp in enumerate(top_expected):
    for j, called in enumerate(top_called):
        if mat[i, j] > 0:
            pairs.append((top_expected[i], top_called[j], int(mat[i, j])))
pairs.sort(key=lambda x: -x[2])
for exp, called, cnt in pairs[:5]:
    print(f"  {sn(exp)} -> {sn(called)}: {cnt}")
