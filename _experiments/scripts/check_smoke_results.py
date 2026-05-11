#!/usr/bin/env python3
"""스모크 테스트 결과 검증: T와 NT runs 사이 응답이 실제로 다른지 확인.

reasoning_effort 패치가 정상 작동하면:
- T (high)와 NT (low)의 평균 elapsed_sec, error_type 분포가 달라야 함.
"""
import json
import sys
from pathlib import Path
from collections import Counter

PHASE = sys.argv[1] if len(sys.argv) > 1 else 'kr'
MODEL = sys.argv[2] if len(sys.argv) > 2 else 'openai_gpt-oss-20b'

evdir = Path(f'_paper/_experiments/results_{PHASE}/eval')
ckdir = Path(f'_paper/_experiments/results_{PHASE}/checkpoint')

def latest_eval(mode):
    files = sorted(evdir.glob(f'eval_{MODEL}__{mode}_*.json'))
    return json.load(files[-1].open()) if files else None

def avg_elapsed(mode):
    fp = ckdir / f'checkpoint_{MODEL}__{mode}.jsonl'
    if not fp.exists(): return None, 0
    es = []
    for line in fp.open():
        try:
            r = json.loads(line)
            if (e := r.get('elapsed_sec')) is not None: es.append(e)
        except: pass
    return (sum(es)/len(es)) if es else None, len(es)

print(f'=== {MODEL} smoke test ({PHASE} phase) ===\n')
for mode in ('think', 'nothink'):
    label = 'T (high)' if mode == 'think' else 'NT (low)'
    print(f'[{label}]')
    e = latest_eval(mode)
    if e is None:
        print(f'  no eval file')
        continue
    print(f'  total_cases: {e.get("total_cases")}')
    overall = e.get('overall', {})
    print(f'  avg_score:   {overall.get("avg_score")}')
    print(f'  hit_rate:    {overall.get("primary_tool_hit_rate")}')
    err = overall.get('by_error_type', {})
    print(f'  error_types: {Counter(err).most_common(5)}')
    avg_e, n = avg_elapsed(mode)
    if avg_e is not None:
        print(f'  avg_elapsed: {avg_e:.2f}s (n={n})')
    print()

# Verdict
print('=== Verdict ===')
t_e, _ = avg_elapsed('think')
nt_e, _ = avg_elapsed('nothink')
if t_e and nt_e:
    ratio = t_e / nt_e
    print(f'  T_elapsed / NT_elapsed = {ratio:.2f}')
    if ratio > 1.5:
        print('  ✅ reasoning_effort 패치 작동 — T가 NT보다 명확히 오래 걸림')
    elif ratio > 1.1:
        print('  ⚠ 차이 작음 — 케이스 수 늘려서 재확인 권장')
    else:
        print('  ❌ T ≈ NT — 패치 실패 또는 토글 무효')
