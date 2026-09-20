#!/bin/bash
# OpenRouter: 망가진 두 팔만 (KR 도구 스키마) · KR질의/EN질의
set -u
# The repository root is where this script lives, the way run_benchmark.sh and
# run_master.sh find it; the interpreter comes from $BENCH_PYTHON (default
# python3), so no checkout or virtual environment path is baked in.
PROJECT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$PROJECT_ROOT"
PY="${BENCH_PYTHON:-python3}"
export PYTHONPATH="$PROJECT_ROOT"
export BENCH_CONCURRENCY="${BENCH_CONCURRENCY:-10}"
ts(){ echo "[$(date +%H:%M:%S)] $*"; }
credits(){ $PY - <<'PYEOF'
import json, os, pathlib, urllib.request
for line in pathlib.Path(".env").read_text(encoding="utf-8").splitlines():
    if line.strip() and not line.startswith("#") and "=" in line:
        k,_,v = line.partition("="); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
try:
    r = urllib.request.Request("https://openrouter.ai/api/v1/credits",
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"})
    print(f"누적 ${json.load(urllib.request.urlopen(r, timeout=20))['data']['total_usage']:.4f}")
except Exception as e: print("조회실패", e)
PYEOF
}
TRIO="google/gemma-4-31b-it qwen/qwen3.6-27b meta-llama/llama-3.3-70b-instruct"
SOLO="qwen/qwen3.5-27b"
ts "=== 시작 · $(credits) · 병렬 ${BENCH_CONCURRENCY} ==="
for arm in "kr_tools_kr|benchmarks" "en_tools_kr|benchmarks_en"; do
  IFS='|' read -r name cases <<< "$arm"
  OUT=_experiments/results_or_${name}
  ts "──── 팔 ${name} (cases=${cases}, tools=kr) → ${OUT}"
  ts "  [1/2] 3모델"
  $PY -m _experiments.scripts.benchmark_openrouter --models $TRIO --think none \
      --cases-dir "$cases" --tools-lang kr --output "$OUT" --checkpoint --resume
  ts "  [1/2] rc=$? · $(credits)"
  ts "  [2/2] Qwen3.5 T/NT"
  $PY -m _experiments.scripts.benchmark_openrouter --models $SOLO --think both \
      --cases-dir "$cases" --tools-lang kr --output "$OUT" --checkpoint --resume
  ts "  [2/2] rc=$? · $(credits)"
  ts "  산출 $(ls -1 ${OUT}/eval/ 2>/dev/null | wc -l)개"
done
ts "=== 전체 종료 · $(credits) ==="
