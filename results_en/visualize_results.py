"""
AML Agent Benchmark 시각화 (KFinEval 스타일 참고)
- Figure 1: 모델별 종합 성능 비교 (수평 막대 차트)
- Figure 2: 카테고리별 성능 레이더 차트 (상위 모델)
- Figure 3: 모델별 에러 유형 분포 (스택 막대)
- Figure 4: 난이도별 성능 히트맵
- Figure 5: 도구정확도 vs 파라미터정확도 산점도
"""

import json
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")
plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.unicode_minus"] = False

RESULTS_DIR = os.path.dirname(os.path.abspath(__file__))
FIGURES_DIR = os.path.join(RESULTS_DIR, "figures")
EVAL_DIR = os.path.join(RESULTS_DIR, "eval")

# ── 데이터 로드 ──────────────────────────────────────────────────────

def load_all_evals():
    by_model = {}  # model_name → result dict (최신 파일이 덮어씀)
    for f in sorted(os.listdir(EVAL_DIR)):
        if not f.startswith("eval_") or not f.endswith(".json"):
            continue
        with open(os.path.join(EVAL_DIR, f)) as fp:
            d = json.load(fp)
        model = d.get("model", f)
        o = d["overall"]
        # by_category → categories (aggregated 레벨 평탄화)
        raw_cats = d.get("by_category", d.get("categories", {}))
        flat_cats = {
            cat_name: (cat_val["aggregated"] if isinstance(cat_val, dict) and "aggregated" in cat_val else cat_val)
            for cat_name, cat_val in raw_cats.items()
        }
        # 중복 모델은 최신 결과(마지막 파일)로 덮어씀
        by_model[model] = {
            "model": model,
            "avg_score": o["avg_score"],
            "tool_hit": o["primary_tool_hit_rate"],
            "param_acc": o["avg_param_accuracy"],
            "tool_recall": o.get("avg_tool_recall", 0),
            "tool_precision": o.get("avg_tool_precision", 0),
            "param_key_acc": o.get("avg_param_key_accuracy", 0),
            "order_score": o.get("avg_order_score", 0),
            "total": o["total"],
            "hallucinated": o.get("total_hallucinated_params", 0),
            "by_error": o.get("by_error_type", {}),
            "by_difficulty": o.get("by_difficulty", {}),
            "categories": flat_cats,
        }
    # vLLM 아키텍처 미지원으로 실험 실패한 모델 제외 (전체 0점)
    results = [r for r in by_model.values() if r["avg_score"] > 0.01]
    results.sort(key=lambda x: -x["avg_score"])
    return results


def short_name(model: str) -> str:
    """모델명 축약"""
    name_map = {
        # Qwen
        "Qwen/Qwen2.5-1.5B-Instruct": "Qwen2.5-1.5B",
        "Qwen/Qwen3-4B-Instruct-2507": "Qwen3-4B-Instruct",
        "Qwen/Qwen3-4B-Thinking-2507__think": "Qwen3-4B-Think (T)",
        "Qwen/Qwen3-4B-Thinking-2507__nothink": "Qwen3-4B-Think (NT)",
        "Qwen/Qwen3-8B": "Qwen3-8B",
        "Qwen/Qwen3-30B-A3B-Instruct-2507": "Qwen3-30B-Instruct",
        "Qwen/Qwen3-30B-A3B-Thinking-2507__think": "Qwen3-30B-Think (T)",
        "Qwen/Qwen3-30B-A3B-Thinking-2507__nothink": "Qwen3-30B-Think (NT)",
        "Qwen/Qwen3.5-0.8B__think": "Qwen3.5-0.8B (T)",
        "Qwen/Qwen3.5-0.8B__nothink": "Qwen3.5-0.8B (NT)",
        "Qwen/Qwen3.5-2B__think": "Qwen3.5-2B (T)",
        "Qwen/Qwen3.5-2B__nothink": "Qwen3.5-2B (NT)",
        "Qwen/Qwen3.5-4B__think": "Qwen3.5-4B (T)",
        "Qwen/Qwen3.5-4B__nothink": "Qwen3.5-4B (NT)",
        "Qwen/Qwen3.5-9B__think": "Qwen3.5-9B (T)",
        "Qwen/Qwen3.5-9B__nothink": "Qwen3.5-9B (NT)",
        # OpenAI
        "openai/gpt-oss-120b__think": "GPT-OSS-120B (T)",
        "openai/gpt-oss-120b__nothink": "GPT-OSS-120B (NT)",
        "openai/gpt-oss-20b__think": "GPT-OSS-20B (T)",
        "openai/gpt-oss-20b__nothink": "GPT-OSS-20B (NT)",
        # Mistral
        "mistralai/Mistral-Small-3.2-24B-Instruct-2506": "Mistral-Small-24B",
        # Meta
        "meta-llama/Llama-3.1-8B-Instruct": "Llama-3.1-8B",
        "meta-llama/Llama-3.3-70B-Instruct": "Llama-3.3-70B",
        "meta-llama/Llama-4-Scout-17B-16E-Instruct": "Llama-4-Scout",
        # Kakao
        "kakaocorp/kanana-1.5-2.1b-instruct-2505": "Kanana-2.1B",
        "kakaocorp/kanana-1.5-8b-instruct-2505": "Kanana-8B",
        "kakaocorp/kanana-1.5-15.7b-a3b-instruct": "Kanana-15.7B",
        # IBM
        # ibm-granite/granite-3.1-8b-instruct: 제외
        # EXAONE
        # LGAI-EXAONE/EXAONE-3.5-7.8B/32B-Instruct: 제외
        "LGAI-EXAONE/EXAONE-4.0-1.2B": "EXAONE-4.0-1.2B",
        "LGAI-EXAONE/EXAONE-4.0-32B": "EXAONE-4.0-32B",
        # Others
        "naver-hyperclovax/HyperCLOVAX-SEED-Think-32B": "HCX-SEED-32B",
        "naver-hyperclovax/HyperCLOVAX-SEED-Think-14B": "HCX-SEED-14B",
        "zai-org/GLM-4.7-Flash": "GLM-4.7-Flash",
        # microsoft/Phi-4-mini-instruct: 제외
        # Salesforce xLAM
        "Salesforce/xLAM-2-1b-fc-r": "xLAM-1B",
        "Salesforce/xLAM-2-3b-fc-r": "xLAM-3B",
        "Salesforce/Llama-xLAM-2-8b-fc-r": "xLAM-8B",
        "Salesforce/xLAM-2-32b-fc-r": "xLAM-32B",
        # NousResearch
        "NousResearch/Hermes-3-Llama-3.1-8B": "Hermes-3-8B",
        # InternLM
        # internlm/internlm3-8b-instruct: 제외
        # Mistral
        "mistralai/Ministral-3-3B-Instruct-2512": "Ministral-3B",
        "mistralai/Ministral-3-8B-Instruct-2512": "Ministral-8B",
        "mistralai/Ministral-3-14B-Instruct-2512": "Ministral-14B",
        "mistralai/Mistral-Nemo-Instruct-2407": "Mistral-Nemo-12B",
        # Cohere
        "CohereForAI/c4ai-command-r7b-12-2024": "Command-R-7B",
        # Microsoft
        # microsoft/Phi-4: 제외
        # Qwen
        "Qwen/Qwen3.5-27B__think": "Qwen3.5-27B (T)",
        "Qwen/Qwen3.5-27B__nothink": "Qwen3.5-27B (NT)",
        "Qwen/Qwen3-Coder-30B-A3B-Instruct": "Qwen3-Coder-30B",
        # Tencent / Allen AI / DeepSeek / GLM / Granite
        "tencent/Hunyuan-A13B-Instruct": "Hunyuan-A13B",
        "allenai/OLMo-3-7B-Instruct": "OLMo-3-7B",
        "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B": "DeepSeek-R1-Qwen3-8B",
        "zai-org/GLM-4.5-Air": "GLM-4.5-Air",
        "ibm-granite/granite-3.2-8b-instruct": "Granite-3.2-8B",
        # Meta Llama 3.2
        "meta-llama/Llama-3.2-1B-Instruct": "Llama-3.2-1B",
        "meta-llama/Llama-3.2-3B-Instruct": "Llama-3.2-3B",
    }
    return name_map.get(model, model.split("/")[-1])


# 색상 팔레트 (KFinEval 스타일 — 구분 명확한 학술 색상)
COLORS_TIER = {
    "top": "#2E86AB",     # 상위 (파랑)
    "mid": "#A23B72",     # 중위 (자주)
    "low": "#F18F01",     # 하위 (주황)
    "fail": "#C73E1D",    # 파서 실패 (빨강)
}


def get_tier_color(score):
    if score >= 0.8:
        return COLORS_TIER["top"]
    elif score >= 0.7:
        return COLORS_TIER["mid"]
    elif score >= 0.3:
        return COLORS_TIER["low"]
    else:
        return COLORS_TIER["fail"]


# ── Figure 1: 종합 성능 비교 (수평 막대 차트) ──────────────────────────

def fig1_overall_performance(results):
    n = len(results)
    fig, ax = plt.subplots(figsize=(12, max(8, n * 0.45)))

    models = [short_name(r["model"]) for r in reversed(results)]
    scores = [r["avg_score"] for r in reversed(results)]
    tool_hits = [r["tool_hit"] for r in reversed(results)]
    param_accs = [r["param_acc"] for r in reversed(results)]

    y = np.arange(len(models))
    height = 0.25

    bars1 = ax.barh(y - height, scores, height, label="Avg Score", color="#2E86AB", alpha=0.9)
    bars2 = ax.barh(y, tool_hits, height, label="Tool Hit Rate", color="#A23B72", alpha=0.9)
    bars3 = ax.barh(y + height, param_accs, height, label="Param Accuracy", color="#F18F01", alpha=0.9)

    ax.set_yticks(y)
    ax.set_yticklabels(models, fontsize=10)
    ax.set_xlabel("Score", fontsize=12)
    ax.set_title("AML Agent Benchmark: Overall Model Performance", fontsize=14, fontweight="bold")
    ax.legend(loc="lower right", fontsize=10)
    ax.set_xlim(0, 1.05)
    ax.axvline(x=0.8, color="gray", linestyle="--", alpha=0.5, label="H1/H4 threshold")
    ax.grid(axis="x", alpha=0.3)

    # 점수 레이블
    for bar in bars1:
        w = bar.get_width()
        if w > 0.15:
            ax.text(w - 0.01, bar.get_y() + bar.get_height()/2, f"{w:.3f}",
                    ha="right", va="center", fontsize=7, color="white", fontweight="bold")

    plt.tight_layout()
    path = os.path.join(FIGURES_DIR, "fig1_overall_performance.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


# ── Figure 2: 카테고리별 레이더 차트 (상위 6개 모델) ───────────────────

def fig2_radar_chart(results):
    # 상위 6개 모델 + 하위 대표 2개
    top_models = results[:6]
    # 카테고리 목록 (multi_tool, missing_parameters 제외한 도구별)
    sample = top_models[0]
    all_cats = sorted(sample["categories"].keys())
    # 주요 카테고리만 선택 (레이더 가독성)
    key_cats = [c for c in all_cats if c not in ("missing_parameters",)]
    if len(key_cats) > 15:
        # 대표 카테고리 선별
        key_cats = [
            "get_statistics", "query_transactions", "predict_fraud",
            "analyze_network", "detect_aml_patterns", "generate_str",
            "detect_ctr_candidates", "score_account_risk", "detect_monitoring_alerts",
            "detect_smurfing_network", "get_trend_analysis", "multi_tool",
            "get_account_profile", "rank_risky_transactions", "compare_periods",
        ]
        key_cats = [c for c in key_cats if c in all_cats]

    N = len(key_cats)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))

    colors = ["#2E86AB", "#E84855", "#F18F01", "#44BBA4", "#A23B72", "#7B68EE"]
    for i, r in enumerate(top_models):
        values = []
        for cat in key_cats:
            cat_data = r["categories"].get(cat, {})
            values.append(cat_data.get("avg_score", 0))
        values += values[:1]
        ax.plot(angles, values, "o-", linewidth=1.5, markersize=3,
                label=short_name(r["model"]), color=colors[i % len(colors)], alpha=0.8)
        ax.fill(angles, values, alpha=0.05, color=colors[i % len(colors)])

    # 카테고리 라벨 축약
    cat_labels = [c.replace("detect_", "det_").replace("get_", "").replace("analyze_", "ana_")
                  .replace("_transactions", "_tx").replace("_account", "_acct")
                  for c in key_cats]
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(cat_labels, fontsize=7)
    ax.set_ylim(0.6, 1.0)
    ax.set_yticks([0.6, 0.7, 0.8, 0.9, 1.0])
    ax.set_yticklabels(["0.6", "0.7", "0.8", "0.9", "1.0"], fontsize=7, color="gray")
    ax.set_title("Category-wise Performance Radar (Top 6 Models)", fontsize=13, fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=9)

    plt.tight_layout()
    path = os.path.join(FIGURES_DIR, "fig2_radar_chart.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


# ── Figure 3: 에러 유형 분포 (스택 막대) ──────────────────────────────

def fig3_error_distribution(results):
    n = len(results)
    fig, ax = plt.subplots(figsize=(max(14, n * 0.7), 7))

    models = [short_name(r["model"]) for r in results]
    correct = [r["by_error"].get("correct", 0) for r in results]
    wrong_func = [r["by_error"].get("wrong_func", 0) for r in results]
    wrong_val = [r["by_error"].get("wrong_value", 0) for r in results]
    parse_fail = [r["by_error"].get("parse_fail", 0) for r in results]
    conn_err = [r["by_error"].get("connection_error", 0) for r in results]

    x = np.arange(len(models))
    width = 0.6

    ax.bar(x, correct, width, label="Correct", color="#44BBA4")
    ax.bar(x, wrong_val, width, bottom=correct, label="Wrong Value", color="#F18F01")
    bottom2 = [c + w for c, w in zip(correct, wrong_val)]
    ax.bar(x, wrong_func, width, bottom=bottom2, label="Wrong Function", color="#A23B72")
    bottom3 = [b + w for b, w in zip(bottom2, wrong_func)]
    ax.bar(x, parse_fail, width, bottom=bottom3, label="Parse Fail", color="#E84855")
    bottom4 = [b + p for b, p in zip(bottom3, parse_fail)]
    ax.bar(x, conn_err, width, bottom=bottom4, label="Connection Error", color="#333333")

    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Number of Cases", fontsize=11)
    ax.set_title("Error Type Distribution by Model (N=1,258)", fontsize=13, fontweight="bold")
    ax.legend(loc="upper right", fontsize=9)
    ax.set_ylim(0, 1400)

    plt.tight_layout()
    path = os.path.join(FIGURES_DIR, "fig3_error_distribution.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


# ── Figure 4: 난이도별 성능 히트맵 ───────────────────────────────────

def fig4_difficulty_heatmap(results):
    difficulties = ["easy", "medium", "hard", "irrelevance"]
    models_data = []
    model_names = []

    for r in results:
        row = []
        for diff in difficulties:
            diff_data = r["by_difficulty"].get(diff, {})
            row.append(diff_data.get("avg_score", 0))
        models_data.append(row)
        model_names.append(short_name(r["model"]))

    data = np.array(models_data)
    n = len(model_names)
    fig, ax = plt.subplots(figsize=(8, max(8, n * 0.45)))
    im = ax.imshow(data, cmap="RdYlGn", aspect="auto", vmin=0, vmax=1)

    ax.set_xticks(np.arange(len(difficulties)))
    ax.set_xticklabels([d.capitalize() for d in difficulties], fontsize=11)
    ax.set_yticks(np.arange(len(model_names)))
    ax.set_yticklabels(model_names, fontsize=9)

    # 셀 값 표시
    for i in range(len(model_names)):
        for j in range(len(difficulties)):
            val = data[i, j]
            color = "white" if val < 0.4 or val > 0.8 else "black"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=8, color=color)

    ax.set_title("Performance by Difficulty Level", fontsize=13, fontweight="bold")
    fig.colorbar(im, ax=ax, shrink=0.6, label="Avg Score")

    plt.tight_layout()
    path = os.path.join(FIGURES_DIR, "fig4_difficulty_heatmap.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


# ── Figure 5: 도구정확도 vs 파라미터정확도 산점도 ──────────────────────

def fig5_tool_vs_param_scatter(results):
    from adjustText import adjust_text

    fig, ax = plt.subplots(figsize=(11, 8))

    texts = []
    for r in results:
        color = get_tier_color(r["avg_score"])
        ax.scatter(r["tool_hit"], r["param_acc"], s=120, c=color, alpha=0.8,
                   edgecolors="white", linewidth=0.8, zorder=3)
        texts.append(ax.text(r["tool_hit"], r["param_acc"], short_name(r["model"]),
                             fontsize=7, alpha=0.9))

    # H1/H4 임계선
    ax.axvline(x=0.8, color="gray", linestyle="--", alpha=0.4, linewidth=1)
    ax.axhline(y=0.75, color="gray", linestyle="--", alpha=0.4, linewidth=1)
    ax.text(0.81, 0.41, "H1 ≥ 0.80", fontsize=8, color="gray", alpha=0.6)
    ax.text(0.11, 0.76, "H4 ≥ 0.75", fontsize=8, color="gray", alpha=0.6)

    # 사분면 배경
    # ymin/ymax는 축 비율: (0.75-0.4)/(1.02-0.4) ≈ 0.565
    ax.axvspan(0.8, 1.0, ymin=0.565, ymax=1.0, alpha=0.03, color="green")

    ax.set_xlabel("Primary Tool Hit Rate (H1)", fontsize=12)
    ax.set_ylabel("Avg Parameter Accuracy (H4)", fontsize=12)
    ax.set_title("Tool Selection vs Parameter Extraction Accuracy", fontsize=13, fontweight="bold")
    ax.set_xlim(0.1, 1.02)
    ax.set_ylim(0.4, 1.02)
    ax.grid(alpha=0.2)

    # 범례 (tier별)
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COLORS_TIER["top"], markersize=10, label="Score ≥ 0.80"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COLORS_TIER["mid"], markersize=10, label="0.70–0.80"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COLORS_TIER["low"], markersize=10, label="0.30–0.70"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COLORS_TIER["fail"], markersize=10, label="< 0.30 (parser fail)"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", fontsize=9)

    adjust_text(texts, ax=ax, arrowprops=dict(arrowstyle="-", color="gray", alpha=0.4, lw=0.5),
                expand=(1.5, 1.8), force_text=(0.8, 1.0), force_points=(0.3, 0.3),
                ensure_inside_axes=True)

    plt.tight_layout()
    path = os.path.join(FIGURES_DIR, "fig5_tool_vs_param.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


# ── Figure 6: 카테고리별 히트맵 (모델 x 카테고리) ────────────────────

def fig6_category_heatmap(results):
    # EXAONE-32B(connection error)만 제외
    valid = [r for r in results if r["avg_score"] > 0.1]

    all_cats = sorted(valid[0]["categories"].keys())
    model_names = [short_name(r["model"]) for r in valid]

    data = []
    for r in valid:
        row = []
        for cat in all_cats:
            cat_data = r["categories"].get(cat, {})
            row.append(cat_data.get("avg_score", 0))
        data.append(row)

    data = np.array(data)
    cat_labels = [c.replace("detect_", "det_").replace("get_", "").replace("analyze_", "ana_")
                  .replace("_transactions", "_tx").replace("_account", "_acct")
                  for c in all_cats]

    n_models = len(model_names)
    fig, ax = plt.subplots(figsize=(18, max(7, n_models * 0.45)))
    im = ax.imshow(data, cmap="RdYlGn", aspect="auto", vmin=0, vmax=1)

    ax.set_xticks(np.arange(len(all_cats)))
    ax.set_xticklabels(cat_labels, rotation=60, ha="right", fontsize=7)
    ax.set_yticks(np.arange(len(model_names)))
    ax.set_yticklabels(model_names, fontsize=9)

    for i in range(len(model_names)):
        for j in range(len(all_cats)):
            val = data[i, j]
            color = "white" if val < 0.35 or val > 0.85 else "black"
            ax.text(j, i, f"{val:.0%}", ha="center", va="center", fontsize=6, color=color)

    ax.set_title("Category-wise Performance Heatmap (Viable Models)", fontsize=13, fontweight="bold")
    fig.colorbar(im, ax=ax, shrink=0.5, label="Avg Score")

    plt.tight_layout()
    path = os.path.join(FIGURES_DIR, "fig6_category_heatmap.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


# ── main ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Loading eval results...")
    results = load_all_evals()
    print(f"  {len(results)} models loaded\n")

    os.makedirs(FIGURES_DIR, exist_ok=True)
    print("Generating figures...")
    fig1_overall_performance(results)
    fig2_radar_chart(results)
    fig3_error_distribution(results)
    fig4_difficulty_heatmap(results)
    fig5_tool_vs_param_scatter(results)
    fig6_category_heatmap(results)
    print("\nDone!")
