"""RQ1 신규 figure: 도구 혼동 heatmap (top confused tool pairs).

wrong_func 오류 중 called_tool != expected_tool인 케이스를 집계하여
상위 혼동 도구 행·열만 추출한 heatmap을 생성한다.

출력: _paper/_experiments/results_RQ1/fig_confusion_heatmap.{pdf,png}
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

OUTLIERS = {
}

# ── 집계: expected_tool -> called_tool -> count ───────────────────────────────
conf = defaultdict(lambda: defaultdict(int))

for fn in sorted(os.listdir(EVAL_DIR)):
    if not fn.endswith(".json"):
        continue
    with open(os.path.join(EVAL_DIR, fn)) as f:
        d = json.load(f)
    if d["model"] in OUTLIERS:
        continue
    for cat, cat_data in d["by_category"].items():
        for case in cat_data["per_case"]:
            if case["error_type"] == "wrong_func":
                called = case.get("called_tools", [])
                if called and called[0] != cat:
                    conf[cat][called[0]] += 1

# ── 상위 혼동 도구 선택 ───────────────────────────────────────────────────────
# 각 expected_tool에서 가장 많이 confused된 called_tool의 합산 기준 상위 12개 expected
tool_total_conf = {exp: sum(v.values()) for exp, v in conf.items()}
top_expected = sorted(tool_total_conf, key=lambda x: -tool_total_conf[x])[:12]

# top_expected에 등장하는 called_tool 중 상위 12개
called_counter: dict[str, int] = defaultdict(int)
for exp in top_expected:
    for called, cnt in conf[exp].items():
        called_counter[called] += cnt
top_called = sorted(called_counter, key=lambda x: -called_counter[x])[:12]

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
fig, ax = plt.subplots(figsize=(7.0, 5.5))

# cmap: white -> deep blue (zero는 흰색)
cmap = matplotlib.colormaps["Blues"]
im = ax.imshow(mat, aspect="auto", cmap=cmap, vmin=0)

# 수치 주석
for i in range(mat.shape[0]):
    for j in range(mat.shape[1]):
        v = int(mat[i, j])
        if v == 0:
            continue
        text_color = "white" if mat[i, j] > mat.max() * 0.6 else "black"
        ax.text(j, i, str(v), ha="center", va="center",
                fontsize=FS_ANNOT - 1, color=text_color)

ax.set_xticks(range(len(col_labels)))
ax.set_xticklabels(col_labels, rotation=45, ha="right", fontsize=FS_TICK - 1)
ax.set_yticks(range(len(row_labels)))
ax.set_yticklabels(row_labels, fontsize=FS_TICK - 1)
ax.set_xlabel("Called tool (wrong)", fontsize=FS_LABEL)
ax.set_ylabel("Expected tool", fontsize=FS_LABEL)

cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
cb.set_label("Miscall count\n(28 valid models)", fontsize=FS_ANNOT)
cb.ax.tick_params(labelsize=FS_ANNOT)

# 대각선 없는 행렬이므로 대각 highlight 불필요
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
