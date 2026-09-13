#!/usr/bin/env python3
"""멀티턴 결과를 고쳐진 정답으로 재채점한다 — 재실행 불필요.

배경
----
2026-04-21 영문화 이후 정답의 인자 키가 스키마와 어긋나 `predict_fraud` 턴이
항상 0점으로 채점됐다(자세한 경위는 fix_gold_param_keys.py 참조).

단일턴과 달리 **멀티턴은 재실행이 필요 없다**. 2026-06-06 커밋 9f166c1이
`turn_result["actual_tool_calls"]`를 저장하기 시작했고, 멀티턴 코호트 실행은
2026-09-09/10이라 모델이 낸 인자가 그대로 남아 있다. 정답을 고친 지금 저장된
인자와 다시 대조하기만 하면 참값이 복원된다.

  예) mt_str_001 turn 2 — 기록된 param_accuracy = 0.0
      모델 인자 {"time_slot": 0, "sender_bank": 134, ...}
      패치 후 정답 {"time_slot": 0, "sender_bank": 134, ...}  (완전 동일)

채점은 `benchmark_multiturn._evaluate_turn`을 **그대로 재사용**한다. 되묻기 턴,
`tool_calls_alt` 최고점 채택, 빈 정답 처리 같은 분기를 다시 구현하면 원본과
미묘하게 어긋나기 때문이다.

안전장치
--------
- `actual_tool_calls` 키가 없는 턴은 **건드리지 않는다**. 기록이 없으면 모델이
  도구를 안 불렀는지 저장이 누락됐는지 구분할 수 없으므로, 추정하지 않고 원래
  점수를 유지한 뒤 집계에서 제외 대상으로 보고한다.
- 정답 인자가 이번 패치와 무관한 턴은 재채점 결과가 같아야 한다. 달라지면
  경고한다(로직 재현이 틀렸다는 신호).
- 원본은 .bak 로 백업하고 --dry-run 을 지원한다.

사용법
------
    python _experiments/scripts/rescore_gold_fix_multiturn.py --dry-run
    python _experiments/scripts/rescore_gold_fix_multiturn.py
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

_SB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_SB))

from _experiments.scripts.benchmark_multiturn import (  # noqa: E402
    _evaluate_turn,
    _aggregate_by_subcategory,
)

ARMS = ("results_mt_oracle", "results_mt_real")
GOLD = _SB / "benchmarks_multiturn" / "cases_str_workflow.json"


def load_gold() -> dict[str, dict]:
    return {s["id"]: s for s in json.loads(GOLD.read_text(encoding="utf-8"))}


def rescore_file(path: Path, gold: dict, dry_run: bool) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    stat = {"turns": 0, "rescored": 0, "no_record": 0, "changed": 0, "drift": 0,
            "before": data.get("overall", {}).get("avg_param_accuracy"), "after": None}

    for sc in data.get("scenarios", []):
        gsc = gold.get(sc.get("id"))
        if not gsc:
            continue
        gturns = gsc.get("turns", [])
        for t in sc.get("turns", []):
            stat["turns"] += 1
            idx = (t.get("turn") or 1) - 1
            if idx >= len(gturns):
                continue
            if "actual_tool_calls" not in t:
                stat["no_record"] += 1
                continue
            new = _evaluate_turn(gturns[idx], t.get("actual_tool_calls") or [])
            stat["rescored"] += 1
            old_p, old_h = t.get("param_accuracy"), t.get("tool_hit")
            if new["tool_hit"] != old_h:
                # 도구 적중은 인자 키와 무관하다. 달라지면 로직 재현이 어긋난 것이다.
                stat["drift"] += 1
            if new["param_accuracy"] != old_p:
                stat["changed"] += 1
            t["param_accuracy"] = new["param_accuracy"]
            t["score"] = new["score"]

        turns = sc.get("turns", [])
        if turns:
            sc["avg_param_accuracy"] = round(
                sum(x.get("param_accuracy", 0.0) for x in turns) / len(turns), 4)
            sc["avg_score"] = round(sum(x.get("score", 0.0) for x in turns) / len(turns), 4)

    scen = data.get("scenarios", [])
    if scen:
        ov = data.setdefault("overall", {})
        ov["avg_param_accuracy"] = round(
            sum(s.get("avg_param_accuracy", 0.0) for s in scen) / len(scen), 4)
        ov["avg_score"] = round(sum(s.get("avg_score", 0.0) for s in scen) / len(scen), 4)
        data["by_sub_category"] = _aggregate_by_subcategory(scen)
        stat["after"] = ov["avg_param_accuracy"]

    if not dry_run and stat["changed"]:
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stat


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="파일을 쓰지 않고 요약만 출력")
    args = ap.parse_args()
    gold = load_gold()

    for arm in ARMS:
        d = _SB / "_experiments" / arm / "eval"
        files = sorted(d.glob("*.json"))
        if not files:
            print(f"[{arm}] eval 파일 없음"); continue
        tot = {"turns": 0, "rescored": 0, "no_record": 0, "changed": 0, "drift": 0}
        befores, afters = [], []
        for f in files:
            s = rescore_file(f, gold, args.dry_run)
            for k in tot:
                tot[k] += s[k]
            if s["before"] is not None:
                befores.append(s["before"])
            if s["after"] is not None:
                afters.append(s["after"])
        print(f"[{arm}] 파일 {len(files)}개")
        print(f"  턴 {tot['turns']} | 재채점 {tot['rescored']} | 기록없음 {tot['no_record']} "
              f"| 점수변경 {tot['changed']}")
        if tot["drift"]:
            print(f"  ** 경고: tool_hit 이 {tot['drift']}건 달라졌다. 채점 로직 재현이 어긋났을 수 있다 **")
        if befores and afters:
            print(f"  ā  {sum(befores)/len(befores):.4f} → {sum(afters)/len(afters):.4f} "
                  f"({'dry-run, 미기록' if args.dry_run else '기록됨'})")


if __name__ == "__main__":
    main()
