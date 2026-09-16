#!/bin/bash
set -u
# The repository root is where this script lives, the way run_benchmark.sh and
# run_master.sh find it; the interpreter comes from $BENCH_PYTHON (default
# python3), so no checkout or virtual environment path is baked in (L5-021).
PROJECT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$PROJECT_ROOT"
PY="${BENCH_PYTHON:-python3}"
export PYTHONPATH="$PROJECT_ROOT"
export BENCH_CONCURRENCY="${BENCH_CONCURRENCY:-6}"
ts(){ echo "[$(date +%H:%M:%S)] $*"; }
PAIR="qwen/qwen3.6-35b-a3b meta-llama/llama-3.2-3b-instruct"
OSS="openai/gpt-oss-120b openai/gpt-oss-20b"
ts "=== 추가 6설정 시작 (병렬 6) ==="
for arm in "kr_tools_kr|benchmarks" "en_tools_kr|benchmarks_en"; do
  IFS='|' read -r name cases <<< "$arm"
  OUT=_experiments/results_or_${name}
  ts "──── 팔 ${name}"
  ts "  [1/2] Qwen3.6-35B-A3B · Llama-3.2-3B"
  $PY -m _experiments.scripts.benchmark_openrouter --models $PAIR --think none \
      --cases-dir "$cases" --tools-lang kr --output "$OUT" --checkpoint --resume
  ts "  rc=$?"
  ts "  [2/2] gpt-oss 120b/20b (effort high/low)"
  $PY -m _experiments.scripts.benchmark_openrouter --models $OSS --think both \
      --cases-dir "$cases" --tools-lang kr --output "$OUT" --checkpoint --resume
  ts "  rc=$?"
done
ts "=== 추가분 종료 ==="
