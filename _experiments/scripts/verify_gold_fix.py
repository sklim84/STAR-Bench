#!/usr/bin/env python3
"""정답 동기화 재실행이 제대로 끝났는지 검증한다.

fix_gold_param_keys.py → 재실행 → merge_partial_results.py 를 마친 뒤 실행한다.
세 가지를 본다.

  1) 정답에 한글 키/값이 남아 있지 않은가 (패치 누락 탐지)
  2) 고장났던 두 도구의 avg_param_accuracy가 정상 범위로 올라왔는가
     (기준: 재실행 전 predict_fraud 0.12, lookup_fiu_reference_types 0.13)
  3) 코호트 28설정의 전체 a가 얼마나 바뀌었고 순위가 유지되는가

사용법
------
    python _experiments/scripts/verify_gold_fix.py
    python _experiments/scripts/verify_gold_fix.py --results _experiments/results_kr
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
from pathlib import Path

_SB = Path(__file__).resolve().parents[2]
TARGET_TOOLS = ("predict_fraud", "lookup_fiu_reference_types")
BEFORE = {"predict_fraud": 0.120, "lookup_fiu_reference_types": 0.130}

# 본문 28설정 코호트 밖 (generate_reg_vs_analysis.py의 EXCLUDE와 동일)
EXCLUDE = {
    "Qwen_Qwen3-30B-A3B-Instruct-2507", "Qwen_Qwen3-4B-Instruct-2507", "Qwen_Qwen3-8B",
    "Qwen_Qwen3_5-9B__nothink", "Qwen_Qwen3_5-9B__think",
    "Salesforce_Llama-xLAM-2-8b-fc-r", "Salesforce_xLAM-2-1b-fc-r",
    "Salesforce_xLAM-2-32b-fc-r", "kakaocorp_kanana-2-30b-a3b-instruct-2601",
    "meta-llama_Llama-3_1-8B-Instruct",
}
HANGUL = re.compile(r"[가-힣]")


def check_gold() -> bool:
    ok = True
    # 파일명이나 도구명을 가정하지 않고 전체 케이스 파일을 훑는다. 패치와 검증이
    # 같은 가정을 공유하면 검증이 맹점을 함께 물려받는다.
    for d in ("benchmarks", "benchmarks_en"):
        for p in sorted((_SB / d).glob("cases_*.json")):
            left = []
            for case in json.loads(p.read_text(encoding="utf-8")):
                for tname, checks in (case.get("expected", {}).get("param_checks") or {}).items():
                    if not isinstance(checks, dict):
                        continue
                    for k, v in checks.items():
                        if HANGUL.search(str(k)) or (
                            tname in TARGET_TOOLS and HANGUL.search(str(v))
                        ):
                            left.append((case["id"], tname, k, v))
            if left:
                print(f"  {d}/{p.name} : 남음 {len(left)}건 예: {left[:2]}")
                ok = False
    if ok:
        print("  benchmarks/, benchmarks_en/ : 전체 케이스 파일 OK")

    # 멀티턴: turns[].tool_calls 가 채점 정답이다 (benchmark_multiturn.py:222)
    for d in ("benchmarks_multiturn", "benchmarks_multiturn_en"):
        p = _SB / d / "cases_str_workflow.json"
        if not p.exists():
            continue
        left = []
        for sc in json.loads(p.read_text(encoding="utf-8")):
            for turn in sc.get("turns", []):
                for field in ("tool_calls", "tool_calls_alt"):
                    for call in turn.get(field) or []:
                        for k in (call.get("arguments") or {}):
                            if HANGUL.search(str(k)):
                                left.append((sc.get("id"), call.get("name"), k))
        mark = "OK" if not left else f"남음 {len(left)}건 예: {left[:2]}"
        print(f"  {d}/cases_str_workflow.json : {mark}")
        ok = ok and not left
    return ok


def check_multiturn(results_dir: Path) -> None:
    """predict_fraud 턴의 param_accuracy가 0에서 회복됐는지 본다 (재실행 전 0.000)."""
    gold_path = _SB / "benchmarks_multiturn" / "cases_str_workflow.json"
    if not gold_path.exists() or not results_dir.exists():
        return
    gold = {}
    for sc in json.loads(gold_path.read_text(encoding="utf-8")):
        for i, turn in enumerate(sc.get("turns", [])):
            gold[(sc.get("id"), i)] = {c.get("name") for c in (turn.get("tool_calls") or [])}

    pf, other = [], []
    for f in glob.glob(str(results_dir / "eval" / "*.json")):
        d = json.load(open(f, encoding="utf-8"))
        for sc in d.get("scenarios", []):
            for t in sc.get("turns", []):
                a = t.get("param_accuracy")
                if a is None:
                    continue
                key = (sc.get("id"), (t.get("turn") or 1) - 1)
                (pf if "predict_fraud" in gold.get(key, set()) else other).append(a)
    if not pf:
        print(f"  {results_dir.name}: predict_fraud 턴을 찾지 못함")
        return
    m = sum(pf) / len(pf)
    verdict = "회복" if m > 0.2 else "여전히 0 — 재실행 누락 의심"
    print(f"  {results_dir.name}: predict_fraud 턴 {m:.3f} ({verdict}, n={len(pf)}) / "
          f"그 외 턴 {sum(other)/len(other):.3f}")


def check_results(results_dir: Path) -> None:
    rows = []
    for f in glob.glob(str(results_dir / "eval" / "*.json")):
        d = json.load(open(f, encoding="utf-8"))
        name = re.sub(r"_\d{8}_\d{6}.*$", "", os.path.basename(f)[len("eval_"):])
        if name in EXCLUDE:
            continue
        cats = d.get("by_category", {})
        num = den = 0.0
        per = {}
        for t, v in cats.items():
            ag = v.get("aggregated", {})
            n, a = ag.get("total"), ag.get("avg_param_accuracy")
            if n is None or a is None:
                continue
            num += a * n
            den += n
            if t in TARGET_TOOLS:
                per[t] = a
        if den:
            rows.append((name, num / den, per))

    print(f"\n  코호트 설정 수: {len(rows)} (기대 28)")

    # 설정별 미완료 목록: 서버 기동 실패로 조용히 건너뛴 모델을 잡아낸다.
    # run_benchmark.sh 는 기동 실패 시 continue 하고 그룹은 "전체 완료"로 끝난다.
    pending = sorted(
        (n, p.get("predict_fraud")) for n, _, p in rows
        if p.get("predict_fraud") is not None and p["predict_fraud"] < 0.3
    )
    if pending:
        print(f"\n  ** 아직 재실행되지 않은 설정 {len(pending)}개 "
              f"(predict_fraud a < 0.3) **")
        for n, v in pending:
            print(f"    {n[:50]:<50} {v:.3f}")
        print("    → 해당 설정이 속한 그룹만 다시 돌린다. "
              "_experiments/logs/vllm_kr_<alias>.log 에서 기동 실패를 먼저 확인할 것.")
    else:
        print("\n  모든 설정이 재실행 완료 상태다 (predict_fraud a >= 0.3)")

    for t in TARGET_TOOLS:
        vals = [p[t] for _, _, p in rows if t in p]
        if not vals:
            print(f"  {t}: 데이터 없음")
            continue
        mean = sum(vals) / len(vals)
        if mean > BEFORE[t] + 0.2:
            verdict = "회복"
        else:
            # 정답만 고치고 아직 재실행 전이면 값이 그대로인 것이 정상이다.
            verdict = "낮음 — 재실행 전이면 정상, 재실행 후라면 누락 의심"
        print(f"  {t}: {BEFORE[t]:.3f} → {mean:.3f} ({verdict}, n={len(vals)})")

    if rows:
        print(f"\n  코호트 평균 a = {sum(r[1] for r in rows) / len(rows):.3f}")
        print("  상위 5개 (a 기준):")
        for name, a, _ in sorted(rows, key=lambda r: -r[1])[:5]:
            print(f"    {name[:44]:<44} {a:.3f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", default="_experiments/results_kr",
                    help="검증할 결과 디렉터리 (기본: _experiments/results_kr)")
    args = ap.parse_args()

    print("[1] 정답 파일에 한글 키/값이 남았는지")
    gold_ok = check_gold()
    print("\n[2][3] 단일턴 재실행 결과")
    check_results(_SB / args.results)
    print("\n[4] 멀티턴 재실행 결과")
    for arm in ("results_mt_oracle", "results_mt_real"):
        check_multiturn(_SB / "_experiments" / arm)
    print("\n정답 패치 상태:", "정상" if gold_ok else "누락 있음 — fix_gold_param_keys.py 재실행 필요")


if __name__ == "__main__":
    main()
