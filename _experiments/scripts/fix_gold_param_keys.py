#!/usr/bin/env python3
"""정답(param_checks)을 현행 도구 스키마에 맞춘다 — 2026-04-21 영문화 이후 누락된 동기화.

배경
----
STAR-Bench-Web 커밋 6c024d9(2026-04-21, "Translate Kor to Eng")가 도구 계층을
영문화했으나 benchmarks/의 정답은 한국어 시절 그대로 남았다. 실행(2026-05-03)은
영문화 이후였으므로 두 도구에서 정답과 모델이 보는 스키마가 어긋난 채 채점됐다.

  1) predict_fraud — 정답 키가 한글(거래시간대 등), agent.py는 영어(time_slot 등)를
     제시한다. evaluator._evaluate_params는 arguments[key]를 문자 그대로 찾으므로
     모든 검사가 실패하고, 모델이 낸 영어 키는 전부 할루시네이션으로 집계된다.
     결과: avg_param_accuracy 0.12 (다른 도구는 0.87 근처).

  2) lookup_fiu_reference_types — 정답 값이 한글 키워드('분할거래' 등)인데
     참조 데이터 _FIU_REFERENCE_TYPES는 31개 항목 전부 영어다. 한글로는 구조적으로
     0건이 반환된다. 결과: avg_param_accuracy 0.13.

도구 적중(h)은 영향을 받지 않는다. 도구 선택은 인자 이름과 무관하기 때문이다.
따라서 논문의 h 기반 결론은 그대로이고, 영향은 파라미터 정확도(a) 한 열이다.

이 스크립트는 정답만 고친다. 고친 뒤 해당 케이스를 재실행해야 값이 채워진다.
재실행 절차는 STAR-Bench-manu/_manuscript/202609_ICLR/RERUN_GOLD_FIX.md 참조.

사용법
------
    python _experiments/scripts/fix_gold_param_keys.py --dry-run   # 변경 요약만
    python _experiments/scripts/fix_gold_param_keys.py             # 실제 패치 + .bak

출력
----
    benchmarks/, benchmarks_en/ 의 두 케이스 파일 패치 (.bak 백업)
    _experiments/rerun_gold_fix/case_ids.txt  — 재실행할 case ID 목록
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

_SB = Path(__file__).resolve().parents[2]
CASE_DIRS = ["benchmarks", "benchmarks_en"]
# 멀티턴 시나리오도 같은 결함을 갖는다. turns[].tool_calls 가 그대로 채점 정답이며
# (benchmark_multiturn.py:222), 21개 도구 중 predict_fraud 만 인자 키가 한글이다.
# 측정: predict_fraud 턴의 param_accuracy 가 28설정 전부에서 0.000 (그 외 턴 0.555).
MULTITURN_DIRS = ["benchmarks_multiturn", "benchmarks_multiturn_en"]
OUT_DIR = _SB / "_experiments" / "rerun_gold_fix"

# 한글 정답 키 → agent.py가 선언한 영어 파라미터명.
# 영문화 커밋 6c024d9 의 전후(6c024d9^ vs 현재)를 도구별로 대조해 도출했다.
# 도구를 손으로 열거하지 않고 정답 전체에서 이 키들을 전수 치환한다 — predict_fraud 만
# 지정했다가 cases_multi_tool.json 과 get_institution_report 를 놓친 적이 있다.
PF_KEY_MAP = {
    "거래시간대": "time_slot",
    "거래일자": "date",
    "거래금액": "amount",
    "매체구분": "media_type",
    "자금구분": "fund_type",
    "이상거래유형": "fraud_type",
    "출금금융회사일련번호": "sender_bank",
    "출금계좌일련번호": "sender_acc",
    "입금금융회사일련번호": "receiver_bank",
    "입금계좌일련번호": "receiver_acc",
    "금융회사일련번호": "bank_id",  # get_institution_report (인자 수가 달라 자동 대조에서 빠짐)
}

# lookup_fiu_reference_types: 한글 키워드 → 영어 참조 데이터에서 실제로 결과를 내는 검색어.
# 각 값은 aml_reference.lookup_fiu_reference_types()로 검증했고, 괄호는 의도한 참조유형 no.
FIU_KEYWORD_MAP = {
    "분할거래": "structuring",        # no=17 structuring
    "심야": "24-hour",                # no=30 24-hour bulk transactions
    "비대면": "Non-face-to-face",     # Banking - Non-face-to-face (7건)
    "가상자산": "virtual asset",      # no=3 외 3건
    "타인명의": "others' names",      # no=12
    "휴면": "dormancy",               # no=11
    "분할": "split",                  # securities no=2
    "법인": "corporate",              # no=1 외 3건
}


def patch_file(path: Path, dry_run: bool) -> tuple[int, list[str]]:
    """한 케이스 파일의 param_checks를 고치고 (변경 건수, 변경된 case id)를 반환한다."""
    if not path.exists():
        return 0, []
    cases = json.loads(path.read_text(encoding="utf-8"))
    changed_ids: list[str] = []

    for case in cases:
        pc = case.get("expected", {}).get("param_checks") or {}
        touched = False

        # (1) 한글 인자 키를 쓰는 모든 도구를 전수 치환 (도구 이름을 가정하지 않는다)
        for tname, checks in pc.items():
            if not isinstance(checks, dict) or not checks:
                continue
            if any(k in PF_KEY_MAP for k in checks):
                pc[tname] = {PF_KEY_MAP.get(k, k): v for k, v in checks.items()}
                touched = True

        # (2) FIU 검색어는 값 자체가 낡았다 (참조 데이터가 전부 영어로 바뀌었다)
        fiu = pc.get("lookup_fiu_reference_types")
        if isinstance(fiu, dict) and fiu.get("keyword") in FIU_KEYWORD_MAP:
            fiu["keyword"] = FIU_KEYWORD_MAP[fiu["keyword"]]
            touched = True

        if touched:
            changed_ids.append(case["id"])

    if changed_ids and not dry_run:
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        path.write_text(
            json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return len(changed_ids), changed_ids


def patch_multiturn(path: Path, dry_run: bool) -> tuple[int, list[str]]:
    """멀티턴 시나리오의 turns[].tool_calls[].arguments 키를 고친다.

    benchmark_multiturn.py:222 가 turns[].tool_calls 를 그대로 채점 정답으로 쓰고,
    _evaluate_tool_calls 가 actual_args.get(key) 로 키를 문자 그대로 찾는다.
    21개 도구 중 predict_fraud 만 인자 키가 한글로 남아 있어 그 턴만 항상 0점이었다.
    """
    if not path.exists():
        return 0, []
    scenarios = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    sids: list[str] = []

    for sc in scenarios:
        touched = False
        for turn in sc.get("turns", []):
            for field in ("tool_calls", "tool_calls_alt"):
                for call in turn.get(field) or []:
                    args = call.get("arguments") or {}
                    if not any(k in PF_KEY_MAP for k in args):
                        continue
                    call["arguments"] = {PF_KEY_MAP.get(k, k): v for k, v in args.items()}
                    changed += 1
                    touched = True
        if touched:
            sids.append(sc.get("id"))

    if changed and not dry_run:
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        path.write_text(
            json.dumps(scenarios, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return changed, sids


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="파일을 쓰지 않고 요약만 출력")
    args = ap.parse_args()
    tag = "(dry-run)" if args.dry_run else "패치"

    all_ids: set[str] = set()
    total = 0
    print("[단일턴]")
    # 파일명을 가정하지 않고 전체 케이스 파일을 훑는다. predict_fraud 검사는
    # cases_predict_fraud.json 뿐 아니라 cases_multi_tool.json 안에도 들어 있다.
    for d in CASE_DIRS:
        for p in sorted((_SB / d).glob("cases_*.json")):
            n, ids = patch_file(p, args.dry_run)
            if not n:
                continue
            total += n
            all_ids.update(ids)
            print(f"  {d}/{p.name} : {n}건 {tag}")

    all_sids: set[str] = set()
    mt_total = 0
    print("[멀티턴]")
    for d in MULTITURN_DIRS:
        p = _SB / d / "cases_str_workflow.json"
        n, sids = patch_multiturn(p, args.dry_run)
        mt_total += n
        all_sids.update(s for s in sids if s)
        print(f"  {d}/cases_str_workflow.json : {n}개 호출 {tag} ({len(sids)} 시나리오)")

    ids_sorted, sids_sorted = sorted(all_ids), sorted(all_sids)
    print(f"\n단일턴 {total}건 패치 → 고유 case ID {len(ids_sorted)}개")
    print(f"멀티턴 {mt_total}개 호출 패치 → 고유 시나리오 {len(sids_sorted)}개")

    if not args.dry_run:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        head = ("# 2026-04-21 영문화 이후 정답-스키마 불일치로 재실행이 필요한 항목\n"
                "# --case-ids-file 로 그대로 사용한다. ID는 접두어를 포함한 전체 형태여야 한다\n"
                "# (benchmark.py --case-ids 도움말의 'pf_001' 예시는 틀렸다. 완전일치로 비교한다)\n")
        (OUT_DIR / "case_ids.txt").write_text(head + "\n".join(ids_sorted) + "\n", encoding="utf-8")
        (OUT_DIR / "scenario_ids.txt").write_text(head + "\n".join(sids_sorted) + "\n", encoding="utf-8")
        print(f"재실행 목록: {(OUT_DIR / 'case_ids.txt').relative_to(_SB)}, "
              f"{(OUT_DIR / 'scenario_ids.txt').relative_to(_SB)}")


if __name__ == "__main__":
    main()
