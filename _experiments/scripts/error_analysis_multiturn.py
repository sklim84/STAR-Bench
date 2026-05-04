#!/usr/bin/env python3
"""Comprehensive error analysis of multiturn benchmark results."""

import json
import glob
import re
import os
from collections import defaultdict
from pathlib import Path

BASE = Path("/home/work/kftc_sklim/KA-001-AML-Assistant/_experiments")
MT_DIR = BASE / "results_multiturn/round1/eval"
ST_DIR = BASE / "results/round1/eval"
OUT_PATH = BASE / "results/error_analysis_multiturn.json"

FRAUD_LABELS = {
    1: "자금세탁", 2: "신규거래처", 3: "대포통장",
    4: "보이스피싱", 5: "불법도박", 6: "유사수신", 7: "기타"
}

# ── helpers ──────────────────────────────────────────────────────────
def short_name(model_id: str) -> str:
    """Shorten model name for display."""
    return model_id.replace("/", "/").split("/")[-1] if "/" in model_id else model_id

def extract_size_b(name: str) -> float | None:
    """Try to extract parameter size in billions from model name."""
    m = re.search(r"(\d+)[._]?(\d*)B", name, re.IGNORECASE)
    if m:
        whole = m.group(1)
        frac = m.group(2) or "0"
        return float(f"{whole}.{frac}")
    # MoE patterns like 30B-A3B
    m2 = re.search(r"(\d+)b", name, re.IGNORECASE)
    if m2:
        return float(m2.group(1))
    return None

def load_jsons(pattern):
    results = []
    for f in sorted(glob.glob(str(pattern))):
        with open(f) as fh:
            results.append(json.load(fh))
    return results

# ── 1. Load all multiturn evals ─────────────────────────────────────
mt_evals = load_jsons(MT_DIR / "multiturn_*.json")
print(f"=== 멀티턴 평가 파일 로드: {len(mt_evals)}개 모델 ===\n")

# ── 2. Model-level summary ──────────────────────────────────────────
print("=" * 100)
print("1. 모델별 종합 성능 요약")
print("=" * 100)

model_rows = []
for e in mt_evals:
    o = e["overall"]
    think_label = ""
    if e.get("think") is True:
        think_label = " (think)"
    elif e.get("think") is False:
        think_label = " (nothink)"
    row = {
        "model": short_name(e["model"]) + think_label,
        "model_id": e["model_id"],
        "think": e.get("think"),
        "avg_score": o["avg_score"],
        "avg_tool_hit": o["avg_tool_hit"],
        "avg_param_accuracy": o.get("avg_param_accuracy", 0),
        "context_accuracy": o.get("context_accuracy", 0),
        "scenario_complete_rate": o.get("scenario_complete_rate", 0),
        "total_elapsed_sec": e.get("total_elapsed_sec", 0),
    }
    model_rows.append(row)

model_rows.sort(key=lambda r: r["avg_score"], reverse=True)

header = f"{'순위':>4} {'모델':<55} {'Score':>7} {'ToolHit':>8} {'ParamAcc':>9} {'CtxAcc':>7} {'완료율':>7}"
print(header)
print("-" * len(header))
for i, r in enumerate(model_rows, 1):
    print(f"{i:>4} {r['model']:<55} {r['avg_score']:>7.4f} {r['avg_tool_hit']:>8.4f} "
          f"{r['avg_param_accuracy']:>9.4f} {r['context_accuracy']:>7.4f} {r['scenario_complete_rate']:>7.2%}")

# ── 3. Sub-category difficulty ──────────────────────────────────────
print("\n" + "=" * 100)
print("2. 서브카테고리별 난이도 분석 (전체 모델 평균)")
print("=" * 100)

subcat_scores = defaultdict(list)
subcat_complete = defaultdict(list)
for e in mt_evals:
    for sc, v in e.get("by_sub_category", {}).items():
        subcat_scores[sc].append(v["avg_score"])
        subcat_complete[sc].append(v.get("complete_rate", 0))

subcat_summary = []
for sc in sorted(subcat_scores.keys()):
    scores = subcat_scores[sc]
    comps = subcat_complete[sc]
    subcat_summary.append({
        "sub_category": sc,
        "n_models": len(scores),
        "avg_score": sum(scores) / len(scores),
        "min_score": min(scores),
        "max_score": max(scores),
        "avg_complete_rate": sum(comps) / len(comps),
    })

subcat_summary.sort(key=lambda x: x["avg_score"])
print(f"{'서브카테고리':<25} {'평균Score':>10} {'최저':>8} {'최고':>8} {'평균완료율':>10}")
print("-" * 70)
for s in subcat_summary:
    print(f"{s['sub_category']:<25} {s['avg_score']:>10.4f} {s['min_score']:>8.4f} "
          f"{s['max_score']:>8.4f} {s['avg_complete_rate']:>10.2%}")

# ── 4. Turn-by-turn degradation ────────────────────────────────────
print("\n" + "=" * 100)
print("3. 턴별 성능 변화 (Turn-by-turn degradation)")
print("=" * 100)

# Global across all models
turn_scores_global = defaultdict(list)
turn_tool_hit_global = defaultdict(list)
turn_param_global = defaultdict(list)

# Per-model
turn_scores_per_model = defaultdict(lambda: defaultdict(list))

for e in mt_evals:
    mname = short_name(e["model"])
    if e.get("think") is True:
        mname += " (think)"
    elif e.get("think") is False:
        mname += " (nothink)"
    for sc in e.get("scenarios", []):
        for t in sc.get("turns", []):
            tn = t["turn"]
            turn_scores_global[tn].append(t["score"])
            turn_tool_hit_global[tn].append(t["tool_hit"])
            turn_param_global[tn].append(t["param_accuracy"])
            turn_scores_per_model[mname][tn].append(t["score"])

print(f"\n{'턴':>4} {'평균Score':>10} {'평균ToolHit':>12} {'평균ParamAcc':>12} {'샘플수':>8}")
print("-" * 55)
for tn in sorted(turn_scores_global.keys()):
    s = turn_scores_global[tn]
    th = turn_tool_hit_global[tn]
    pa = turn_param_global[tn]
    print(f"{tn:>4} {sum(s)/len(s):>10.4f} {sum(th)/len(th):>12.4f} {sum(pa)/len(pa):>12.4f} {len(s):>8}")

# Per-model turn degradation (turn 1 vs last turn)
print("\n--- 모델별 턴 1 → 최종 턴 성능 하락폭 (Score) ---")
degradation = []
for mname, turns in turn_scores_per_model.items():
    t1 = turns.get(1, [])
    max_turn = max(turns.keys())
    tN = turns.get(max_turn, [])
    if t1 and tN:
        avg1 = sum(t1) / len(t1)
        avgN = sum(tN) / len(tN)
        degradation.append({"model": mname, "turn1": avg1, f"turn{max_turn}": avgN, "drop": avg1 - avgN})

degradation.sort(key=lambda x: x["drop"], reverse=True)
print(f"{'모델':<55} {'Turn1':>7} {'TurnN':>7} {'하락폭':>7}")
print("-" * 80)
for d in degradation[:10]:
    tn_key = [k for k in d if k.startswith("turn") and k != "turn1"][0]
    print(f"{d['model']:<55} {d['turn1']:>7.4f} {d[tn_key]:>7.4f} {d['drop']:>+7.4f}")
print("  ... (상위 10개만 표시)")

# ── 5. Scenario completion analysis ────────────────────────────────
print("\n" + "=" * 100)
print("4. 시나리오별 완료 분석")
print("=" * 100)

scenario_complete_count = defaultdict(lambda: {"complete": 0, "total": 0, "desc": "", "sub_cat": "", "fraud_type": None, "scores": []})
for e in mt_evals:
    for sc in e.get("scenarios", []):
        sid = sc["id"]
        scenario_complete_count[sid]["total"] += 1
        scenario_complete_count[sid]["desc"] = sc.get("scenario", "")
        scenario_complete_count[sid]["sub_cat"] = sc.get("sub_category", "")
        scenario_complete_count[sid]["fraud_type"] = sc.get("fraud_type")
        scenario_complete_count[sid]["scores"].append(sc.get("avg_score", 0))
        if sc.get("scenario_complete"):
            scenario_complete_count[sid]["complete"] += 1

# Never completed
never_completed = [(sid, v) for sid, v in scenario_complete_count.items() if v["complete"] == 0]
never_completed.sort(key=lambda x: sum(x[1]["scores"]) / max(len(x[1]["scores"]), 1))
print(f"\n--- 어떤 모델도 완료하지 못한 시나리오: {len(never_completed)}개 ---")
for sid, v in never_completed[:15]:
    avg_s = sum(v["scores"]) / max(len(v["scores"]), 1)
    ft = FRAUD_LABELS.get(v["fraud_type"], "N/A")
    print(f"  {sid:<15} [{v['sub_cat']:<20}] 유형={ft:<10} 평균Score={avg_s:.4f} | {v['desc'][:60]}")

# Most completed
most_completed = sorted(scenario_complete_count.items(), key=lambda x: x[1]["complete"], reverse=True)
print(f"\n--- 가장 많이 완료된 시나리오 (상위 10) ---")
for sid, v in most_completed[:10]:
    avg_s = sum(v["scores"]) / max(len(v["scores"]), 1)
    ft = FRAUD_LABELS.get(v["fraud_type"], "N/A")
    print(f"  {sid:<15} [{v['sub_cat']:<20}] 완료={v['complete']:>2}/{v['total']:<2} 유형={ft:<10} 평균Score={avg_s:.4f}")

# ── 6. Fraud type analysis ──────────────────────────────────────────
print("\n" + "=" * 100)
print("5. 이상거래유형별 성능 분석")
print("=" * 100)

fraud_scores = defaultdict(list)
fraud_complete = defaultdict(lambda: {"complete": 0, "total": 0})
for e in mt_evals:
    for sc in e.get("scenarios", []):
        ft = sc.get("fraud_type")
        if ft is not None:
            fraud_scores[ft].append(sc.get("avg_score", 0))
            fraud_complete[ft]["total"] += 1
            if sc.get("scenario_complete"):
                fraud_complete[ft]["complete"] += 1

print(f"\n{'유형코드':>8} {'유형명':<12} {'시나리오수':>10} {'평균Score':>10} {'완료율':>8}")
print("-" * 60)
for ft in sorted(fraud_scores.keys()):
    scores = fraud_scores[ft]
    comp = fraud_complete[ft]
    cr = comp["complete"] / max(comp["total"], 1)
    label = FRAUD_LABELS.get(ft, f"유형{ft}")
    print(f"{ft:>8} {label:<12} {len(scores):>10} {sum(scores)/len(scores):>10.4f} {cr:>8.2%}")

# ── 7. Context accuracy analysis ───────────────────────────────────
print("\n" + "=" * 100)
print("6. 컨텍스트 유지 능력 분석 (모델 크기 상관관계)")
print("=" * 100)

ctx_data = []
for r in model_rows:
    size = extract_size_b(r["model_id"])
    ctx_data.append({
        "model": r["model"],
        "size_b": size,
        "context_accuracy": r["context_accuracy"],
        "avg_score": r["avg_score"],
    })

ctx_data.sort(key=lambda x: x["context_accuracy"], reverse=True)
print(f"\n{'모델':<55} {'크기(B)':>8} {'CtxAcc':>8} {'Score':>7}")
print("-" * 82)
for c in ctx_data:
    sz = f"{c['size_b']:.1f}" if c["size_b"] else "N/A"
    print(f"{c['model']:<55} {sz:>8} {c['context_accuracy']:>8.4f} {c['avg_score']:>7.4f}")

# Correlation between size and context accuracy
sizes = [(c["size_b"], c["context_accuracy"]) for c in ctx_data if c["size_b"] is not None]
if len(sizes) >= 3:
    sx = [s[0] for s in sizes]
    sy = [s[1] for s in sizes]
    mean_x = sum(sx) / len(sx)
    mean_y = sum(sy) / len(sy)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(sx, sy)) / len(sx)
    std_x = (sum((x - mean_x) ** 2 for x in sx) / len(sx)) ** 0.5
    std_y = (sum((y - mean_y) ** 2 for y in sy) / len(sy)) ** 0.5
    corr = cov / (std_x * std_y) if std_x > 0 and std_y > 0 else 0
    print(f"\n모델 크기 ↔ 컨텍스트 정확도 상관계수(Pearson r): {corr:.4f}")

# ── 8. Thinking vs Non-thinking ─────────────────────────────────────
print("\n" + "=" * 100)
print("7. Thinking vs Non-thinking 모델 비교 (멀티턴)")
print("=" * 100)

think_pairs = defaultdict(dict)
for r in model_rows:
    base = r["model_id"].replace("__think", "").replace("__nothink", "")
    if r["think"] is True:
        think_pairs[base]["think"] = r
    elif r["think"] is False:
        think_pairs[base]["nothink"] = r

paired = {k: v for k, v in think_pairs.items() if "think" in v and "nothink" in v}
if paired:
    print(f"\n{'기본 모델':<45} {'Think Score':>12} {'NoThink Score':>14} {'차이':>8} {'Think 완료':>10} {'NoThink 완료':>12}")
    print("-" * 110)
    think_wins = 0
    for base, pair in sorted(paired.items()):
        t = pair["think"]
        n = pair["nothink"]
        diff = t["avg_score"] - n["avg_score"]
        if diff > 0:
            think_wins += 1
        print(f"{short_name(base):<45} {t['avg_score']:>12.4f} {n['avg_score']:>14.4f} {diff:>+8.4f} "
              f"{t['scenario_complete_rate']:>10.2%} {n['scenario_complete_rate']:>12.2%}")
    print(f"\nThinking 모드 우위: {think_wins}/{len(paired)}개 쌍")

    # Average across all think vs nothink
    think_all = [r for r in model_rows if r["think"] is True]
    nothink_all = [r for r in model_rows if r["think"] is False]
    if think_all and nothink_all:
        avg_t = sum(r["avg_score"] for r in think_all) / len(think_all)
        avg_n = sum(r["avg_score"] for r in nothink_all) / len(nothink_all)
        print(f"전체 Think 평균 Score: {avg_t:.4f} | 전체 NoThink 평균 Score: {avg_n:.4f} | 차이: {avg_t - avg_n:+.4f}")
else:
    print("Think/NoThink 쌍이 없습니다.")

# ── 9. Single-turn vs Multiturn gap ───────────────────────────────────
print("\n" + "=" * 100)
print("8. 싱글턴 vs 멀티턴 성능 차이 분석")
print("=" * 100)

st_evals = load_jsons(ST_DIR / "eval_*.json")
st_map = {}
for se in st_evals:
    # The model field already contains __think/__nothink suffix for thinking models
    key = se.get("model", "")
    # Compute overall avg_score from by_category
    cats = se.get("by_category", {})
    if cats:
        total_cases = 0
        weighted_score = 0
        for cat, cv in cats.items():
            agg = cv.get("aggregated", {})
            n = agg.get("total", 0)
            s = agg.get("avg_score", 0)
            total_cases += n
            weighted_score += n * s
        st_map[key] = weighted_score / total_cases if total_cases > 0 else 0

gaps = []
for e in mt_evals:
    mt_score = e["overall"]["avg_score"]
    # Multiturn model_id has __think/__nothink suffix matching single_turn model field
    st_score = st_map.get(e["model_id"])
    if st_score is None:
        # Fallback: try model field (for non-think models)
        st_score = st_map.get(e["model"])

    think_label = ""
    if e.get("think") is True:
        think_label = " (think)"
    elif e.get("think") is False:
        think_label = " (nothink)"

    gaps.append({
        "model": short_name(e["model"]) + think_label,
        "single_turn_score": st_score,
        "multiturn_score": mt_score,
        "gap": (st_score - mt_score) if st_score is not None else None,
    })

gaps_valid = [g for g in gaps if g["gap"] is not None]
gaps_valid.sort(key=lambda x: x["gap"], reverse=True)

print(f"\n{'모델':<55} {'싱글턴':>8} {'멀티턴':>8} {'차이(S-M)':>10}")
print("-" * 85)
for g in gaps_valid:
    print(f"{g['model']:<55} {g['single_turn_score']:>8.4f} {g['multiturn_score']:>8.4f} {g['gap']:>+10.4f}")

no_match = [g for g in gaps if g["gap"] is None]
if no_match:
    print(f"\n(싱글턴 결과 미매칭 모델: {', '.join(g['model'] for g in no_match)})")

if gaps_valid:
    avg_gap = sum(g["gap"] for g in gaps_valid) / len(gaps_valid)
    print(f"\n전체 평균 성능 차이 (싱글턴 - 멀티턴): {avg_gap:+.4f}")
    print(f"  가장 큰 하락: {gaps_valid[0]['model']} ({gaps_valid[0]['gap']:+.4f})")
    print(f"  가장 작은 하락/상승: {gaps_valid[-1]['model']} ({gaps_valid[-1]['gap']:+.4f})")

# ── Build output JSON ───────────────────────────────────────────────
output = {
    "analysis_date": "2026-04-04",
    "num_models": len(mt_evals),
    "1_model_summary": model_rows,
    "2_subcategory_difficulty": subcat_summary,
    "3_turn_degradation": {
        "global": {
            str(tn): {
                "avg_score": round(sum(turn_scores_global[tn]) / len(turn_scores_global[tn]), 4),
                "avg_tool_hit": round(sum(turn_tool_hit_global[tn]) / len(turn_tool_hit_global[tn]), 4),
                "avg_param_accuracy": round(sum(turn_param_global[tn]) / len(turn_param_global[tn]), 4),
                "n_samples": len(turn_scores_global[tn]),
            }
            for tn in sorted(turn_scores_global.keys())
        },
        "per_model_drop_top10": degradation[:10],
    },
    "4_scenario_completion": {
        "never_completed": [{"id": sid, "sub_category": v["sub_cat"], "fraud_type": v["fraud_type"],
                             "avg_score": round(sum(v["scores"]) / max(len(v["scores"]), 1), 4),
                             "description": v["desc"][:80]}
                            for sid, v in never_completed],
        "most_completed": [{"id": sid, "complete_count": v["complete"], "total": v["total"],
                            "sub_category": v["sub_cat"], "fraud_type": v["fraud_type"],
                            "avg_score": round(sum(v["scores"]) / max(len(v["scores"]), 1), 4)}
                           for sid, v in most_completed[:15]],
    },
    "5_fraud_type_analysis": {
        str(ft): {
            "label": FRAUD_LABELS.get(ft, f"유형{ft}"),
            "n_scenario_instances": len(scores),
            "avg_score": round(sum(scores) / len(scores), 4),
            "complete_rate": round(fraud_complete[ft]["complete"] / max(fraud_complete[ft]["total"], 1), 4),
        }
        for ft, scores in sorted(fraud_scores.items())
    },
    "6_context_accuracy": {
        "model_rankings": [{"model": c["model"], "size_b": c["size_b"],
                            "context_accuracy": c["context_accuracy"]}
                           for c in ctx_data],
        "size_context_correlation": round(corr, 4) if len(sizes) >= 3 else None,
    },
    "7_think_vs_nothink": {
        base: {
            "think_score": pair["think"]["avg_score"],
            "nothink_score": pair["nothink"]["avg_score"],
            "diff": round(pair["think"]["avg_score"] - pair["nothink"]["avg_score"], 4),
        }
        for base, pair in sorted(paired.items())
    } if paired else {},
    "8_single_turn_vs_multiturn": {
        "gaps": gaps_valid,
        "avg_gap": round(avg_gap, 4) if gaps_valid else None,
    },
}

os.makedirs(OUT_PATH.parent, exist_ok=True)
with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n\n=== 분석 결과 저장 완료: {OUT_PATH} ===")
