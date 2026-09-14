#!/bin/bash
# OpenRouter 2x2 재실험: 질의 언어 x 도구 정의 언어, 4팔 x (3모델 + Qwen3.5 T/NT)
set -u
cd /home/recordame/workspace/seonkyu/AML-Assistant/STAR-Bench
SB=/tmp/claude-1001/-home-recordame-workspace-seonkyu-AML-Assistant/bcc3dd42-ce7d-49f0-b796-7888ef67b761/scratchpad
PY=$SB/benchvenv/bin/python
export PYTHONPATH=.
export BENCH_CONCURRENCY=6

ts(){ echo "[$(date +%H:%M:%S)] $*"; }

credits(){ $PY - <<'PYEOF'
import json, os, pathlib, urllib.request
for line in pathlib.Path(".env").read_text(encoding="utf-8").splitlines():
    if line.strip() and not line.startswith("#") and "=" in line:
        k,_,v = line.partition("="); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
try:
    r = urllib.request.Request("https://openrouter.ai/api/v1/credits",
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"})
    d = json.load(urllib.request.urlopen(r, timeout=20))["data"]
    print(f"누적사용 ${d.get('total_usage',0):.4f}")
except Exception as e:
    print("조회실패", e)
PYEOF
}

TRIO="google/gemma-4-31b-it qwen/qwen3.6-27b meta-llama/llama-3.3-70b-instruct"
SOLO="qwen/qwen3.5-27b"

ts "=== 시작 · 기준 $(credits) ==="

# arm: 이름|케이스디렉터리|도구언어
for arm in "kr_tools_kr|benchmarks|kr" "en_tools_kr|benchmarks_en|kr" \
           "kr_tools_en|benchmarks|en" "en_tools_en|benchmarks_en|en"; do
  IFS='|' read -r name cases tl <<< "$arm"
  OUT=_experiments/results_or_${name}
  ts "──────── 팔 ${name} (cases=${cases}, tools=${tl}) → ${OUT}"

  ts "  [1/2] 3모델"
  $PY -m _experiments.scripts.benchmark_openrouter \
      --models $TRIO --think none --cases-dir "$cases" --tools-lang "$tl" \
      --output "$OUT" --checkpoint --resume
  ts "  [1/2] 종료코드 $? · $(credits)"

  ts "  [2/2] Qwen3.5 T/NT"
  $PY -m _experiments.scripts.benchmark_openrouter \
      --models $SOLO --think both --cases-dir "$cases" --tools-lang "$tl" \
      --output "$OUT" --checkpoint --resume
  ts "  [2/2] 종료코드 $? · $(credits)"

  ts "  팔 ${name} 산출: $(ls -1 ${OUT}/eval/ 2>/dev/null | wc -l)개"
done

ts "=== 전체 종료 · $(credits) ==="
