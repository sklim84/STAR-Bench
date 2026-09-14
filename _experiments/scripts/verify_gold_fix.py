#!/usr/bin/env python3
"""정답 동기화 재실행이 제대로 끝났는지 검증한다.

fix_gold_param_keys.py → 재실행 → merge_partial_results.py 를 마친 뒤 실행한다.
세 가지를 본다.

  1) 정답에 한글 키/값이 남아 있지 않은가 (패치 누락 탐지)
  2) 고장났던 두 도구의 avg_param_accuracy가 정상 범위로 올라왔는가
     (기준: 재실행 전 predict_fraud 0.12, lookup_fiu_reference_types 0.13)
  3) 코호트 28설정의 전체 a가 얼마나 바뀌었고 순위가 유지되는가

단일턴은 설정마다 **가장 늦은 eval 하나만** 읽는다. 부분 재실행과 병합을 거치면 한 설정에
eval 파일이 여러 개 쌓이기 때문이다(아래 latest_evals 참조).

사용법
------
    python _experiments/scripts/verify_gold_fix.py
    python _experiments/scripts/verify_gold_fix.py --results _experiments/results_kr
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from pathlib import Path

_SB = Path(__file__).resolve().parents[2]
TARGET_TOOLS = ("predict_fraud", "lookup_fiu_reference_types")
BEFORE = {"predict_fraud": 0.120, "lookup_fiu_reference_types": 0.130}

# 도구별 '회복' 판정 여유폭. predict_fraud 는 키가 맞으면 값도 대부분 맞아 0.12 에서 0.7 대로
# 크게 오른다. lookup_fiu_reference_types 는 정답 검색어가 참조 데이터 원문에 맞춰져 있고
# 채점이 완전일치라, 모델이 동의어(nighttime, virtual assets 등)를 내면 감점된다. 그래서
# 수정이 제대로 먹어도 0.13 에서 0.2 대에 머무는 것이 정상이다. 같은 +0.2 를 쓰면 이 도구는
# 재실행을 마쳐도 늘 '누락 의심'으로 나온다.
RECOVERY_MARGIN = {"predict_fraud": 0.2, "lookup_fiu_reference_types": 0.05}

# 본문 28설정 코호트 밖 (generate_reg_vs_analysis.py의 EXCLUDE와 동일).
# kanana-2-30b-a3b-instruct-2601 은 오타가 아니다. benchmark.py 에 등록된 실제 모델이고
# 중복 릴리스라 분석에서 뺀다. 결과 디렉터리에 파일이 없어도 목록에 남겨 둔다.
EXCLUDE = {
    "Qwen_Qwen3-30B-A3B-Instruct-2507", "Qwen_Qwen3-4B-Instruct-2507", "Qwen_Qwen3-8B",
    "Qwen_Qwen3_5-9B__nothink", "Qwen_Qwen3_5-9B__think",
    "Salesforce_Llama-xLAM-2-8b-fc-r", "Salesforce_xLAM-2-1b-fc-r",
    "Salesforce_xLAM-2-32b-fc-r", "kakaocorp_kanana-2-30b-a3b-instruct-2601",
    "meta-llama_Llama-3_1-8B-Instruct",
}
HANGUL = re.compile(r"[가-힣]")
_EVAL_NAME = re.compile(r"^eval_(?P<name>.+)_(?P<ts>\d{8}_\d{6})\.json$")


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
    """predict_fraud 턴의 param_accuracy가 0에서 회복됐는지 본다 (재실행 전 0.000).

    멀티턴 결과는 설정당 multiturn_<model>.json 하나(타임스탬프 없는 고정 파일명)라
    단일턴과 달리 파일이 겹쳐 쌓이지 않는다.
    """
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


def latest_evals(eval_dir: Path):
    """설정별로 가장 늦은 eval 하나씩 고른다.

    부분 재실행과 병합을 거치면 한 설정에 파일이 여러 개 쌓인다(원본 / 케이스 필터 실행본 /
    병합본). 파일마다 한 설정으로 세면 재실행 전 원본이 계속 한 행씩 끼어들어, 다 끝났는데도
    '아직 재실행되지 않은 설정'으로 잡히고 평균이 섞인다. 2026-09-15 에 실제로 28/28 완료를
    '미재실행 28개'·predict_fraud 0.566(n=91)으로 보고했다. 파일명의 타임스탬프가 가장
    늦은 것이 병합 결과다.

    total_cases 가 0 인 파일은 서버 기동 실패로 남은 빈 결과라 후보에서 뺀다.

    반환: (이름 → (타임스탬프, eval), 읽은 파일 수,
           최신본이 병합 전 부분 실행본인 설정, 빈 결과만 있는 설정)
    """
    by_name: dict[str, list[tuple[str, dict]]] = {}
    n_files = 0
    for f in sorted(eval_dir.glob("eval_*.json")):
        m = _EVAL_NAME.match(f.name)
        if not m:
            continue
        n_files += 1
        by_name.setdefault(m["name"], []).append(
            (m["ts"], json.loads(f.read_text(encoding="utf-8"))))

    picked, partial, empty_only = {}, [], []
    for name, cands in by_name.items():
        full = [c for c in cands if c[1].get("total_cases")]
        if not full:
            empty_only.append(name)
            continue
        ts, d = max(full, key=lambda c: c[0])
        picked[name] = (ts, d)
        # 최신본이 같은 설정의 다른 파일보다 케이스가 적으면, 케이스 필터로 재실행한 뒤
        # merge_partial_results.py 를 돌리지 않은 상태다.
        if d.get("total_cases", 0) < max(c[1].get("total_cases", 0) for c in full):
            partial.append(name)
    return picked, n_files, sorted(partial), sorted(empty_only)


def check_results(results_dir: Path) -> None:
    picked, n_files, partial, empty_only = latest_evals(results_dir / "eval")
    rows = []
    for name, (_ts, d) in sorted(picked.items()):
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

    print(f"\n  코호트 설정 수: {len(rows)} (기대 28) — eval 파일 {n_files}개 중 설정별 최신본")

    cohort_partial = [n for n in partial if n not in EXCLUDE]
    if cohort_partial:
        print(f"\n  ** 최신 eval 이 병합 전 부분 실행본인 설정 {len(cohort_partial)}개 **")
        for n in cohort_partial:
            print(f"    {n}")
        print("    → merge_partial_results.py --output-dir <결과 디렉터리> --all 을 먼저 돌린다. "
              "부분 실행본은 케이스 일부만 담고 있어 아래 수치가 설정 전체를 대표하지 않는다.")

    cohort_empty = [n for n in empty_only if n not in EXCLUDE]
    if cohort_empty:
        print(f"\n  ** 빈 결과(total_cases 0)만 있는 설정 {len(cohort_empty)}개 **")
        for n in cohort_empty:
            print(f"    {n}")
        print("    → 서버 기동 실패다. _experiments/logs/vllm_kr_<alias>.log 를 먼저 확인할 것.")

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
        if mean > BEFORE[t] + RECOVERY_MARGIN[t]:
            verdict = "회복"
            if t == "lookup_fiu_reference_types":
                verdict += " — 값 완전일치 채점이라 낮은 상한이 정상"
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
