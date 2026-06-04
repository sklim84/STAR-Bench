"""체크포인트 리스코어링: abstain bug fix 반영.

수정 내용:
- abstain 케이스(primary_tool=="")에서 도구 호출 시 primary_tool_hit=False로 교정
- score를 새 h 값 기반 가중합으로 재계산
- 원본 체크포인트는 .bak 백업 후 in-place 업데이트

대상 디렉토리: _experiments/results/{round1,round2,round3,round1_en,round2_en,round3_en,round1_tools_en,round1_en_tools_en}/checkpoint/
"""
import json
import glob
import os
import shutil
from pathlib import Path
from collections import defaultdict

_SB = Path(__file__).resolve().parents[2]  # star-bench root
PROJ = str(_SB)

# 가중치 (evaluator.py와 동일)
WEIGHTS = {
    "primary_tool_hit": 0.30,
    "tool_recall":      0.25,
    "tool_precision":   0.10,
    "param_accuracy":   0.25,
    "order_score":      0.10,
}


def load_abstain_ids():
    """벤치마크 케이스에서 abstain(primary_tool=='') 케이스 ID 수집."""
    abstain = set()
    for cf in glob.glob(f'{PROJ}/benchmarks/cases_*.json'):
        with open(cf) as f:
            for c in json.load(f):
                expected = c.get('expected', {})
                if isinstance(expected, dict) and not expected.get('primary_tool', ''):
                    abstain.add(c['id'])
    return abstain


def rescore_record(rec: dict, abstain_ids: set) -> tuple[dict, bool]:
    """단일 레코드 리스코어링. 변경 시 (new_rec, True) 반환."""
    case_id = rec.get('id')
    if case_id not in abstain_ids:
        return rec, False

    called_tools = rec.get('called_tools', [])
    old_hit = rec.get('primary_tool_hit', False)
    new_hit = len(called_tools) == 0

    if old_hit == new_hit:
        return rec, False  # 변경 없음 (이미 올바른 상태)

    # h 값 변경 → score 재계산
    new_rec = dict(rec)
    new_rec['primary_tool_hit'] = new_hit
    # parse_fail은 모든 지표 0이므로 제외
    if rec.get('error_type') == 'parse_fail':
        return rec, False
    r = rec.get('tool_recall', 0.0)
    p = rec.get('tool_precision', 0.0)
    a = rec.get('param_accuracy', 0.0)
    o = rec.get('order_score', 0.0)
    new_score = (
        WEIGHTS["primary_tool_hit"] * float(new_hit)
        + WEIGHTS["tool_recall"] * r
        + WEIGHTS["tool_precision"] * p
        + WEIGHTS["param_accuracy"] * a
        + WEIGHTS["order_score"] * o
    )
    new_rec['score'] = round(new_score, 4)
    return new_rec, True


def main():
    abstain_ids = load_abstain_ids()
    print(f"Abstain case IDs: {len(abstain_ids)}")

    conditions = ['round1', 'round2', 'round3', 'round1_en', 'round2_en', 'round3_en',
                  'round1_tools_en', 'round1_en_tools_en']
    total_files = 0
    total_records = 0
    total_changed = 0
    per_model_changes = defaultdict(int)

    for cond in conditions:
        cond_dir = f'{PROJ}/_experiments/results/{cond}/checkpoint'
        if not os.path.isdir(cond_dir):
            continue
        files = sorted(glob.glob(f'{cond_dir}/checkpoint_*.jsonl'))
        for fp in files:
            total_files += 1
            # 백업 (.bak) 없으면 생성
            bak = fp + '.bak'
            if not os.path.isfile(bak):
                shutil.copy2(fp, bak)

            records = []
            changed = 0
            with open(bak) as f:  # 원본(백업)에서 읽어 새 값 계산
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        records.append(line)  # keep raw
                        continue
                    new_rec, did_change = rescore_record(rec, abstain_ids)
                    if did_change:
                        changed += 1
                    records.append(new_rec)
                    total_records += 1

            # in-place 저장
            with open(fp, 'w') as f:
                for r in records:
                    if isinstance(r, dict):
                        f.write(json.dumps(r, ensure_ascii=False) + '\n')
                    else:
                        f.write(r + '\n')

            total_changed += changed
            model_name = os.path.basename(fp).replace('checkpoint_', '').replace('.jsonl', '')
            per_model_changes[(cond, model_name)] = changed

    print(f"\n=== Rescore Summary ===")
    print(f"Files processed: {total_files}")
    print(f"Records scanned: {total_records}")
    print(f"Records changed: {total_changed}")
    print(f"Change rate: {100*total_changed/total_records:.2f}%")

    # 상위 변경 모델 (조건별)
    top_changes = sorted(per_model_changes.items(), key=lambda x: -x[1])[:15]
    print(f"\nTop 15 (cond, model) with most changes:")
    for (cond, model), n in top_changes:
        if n > 0:
            print(f"  [{cond}] {model}: {n} abstain-failure corrections")


if __name__ == '__main__':
    main()
