#!/bin/bash
# L1 이 [2/3] qwen36-27b 로 넘어가는 순간 중단시킨다.
# 그 설정은 GPU 1 에서 따로 돌고 있어, 겹치면 같은 체크포인트에 두 프로세스가 동시에 append 한다.
# [2/3] 로그가 찍힌 직후는 qwen35-27b 가 T/NT 모두 저장을 마친 시점이라 잃는 것이 없다.
set -u
R=/home/mlp/hgyoo/bubble/codex/star-bench/STAR-Bench
LOG=$R/_experiments/logs/goldfix/moe2L1.log
W=$R/_experiments/logs/goldfix/l1guard.log
echo "[$(date +%H:%M:%S)] guard 시작" > "$W"
for i in $(seq 1 900); do
  if grep -qE "\[2/3\] qwen36-27b" "$LOG" 2>/dev/null; then
    P=$(pgrep -f "run_benchmark.*S2_LARGE_L1" | head -1)
    echo "[$(date +%H:%M:%S)] [2/3] 감지 -> L1 중단 (run_benchmark pid=$P)" >> "$W"
    [ -n "$P" ] && kill -TERM "$P" 2>/dev/null
    sleep 5
    V=$(pgrep -f "vllm.entrypoints.*--port 18454" | tr "\n" " ")
    echo "[$(date +%H:%M:%S)] port18454 vLLM 정리: $V" >> "$W"
    [ -n "$V" ] && kill -TERM $V 2>/dev/null
    sleep 5
    echo "[$(date +%H:%M:%S)] guard 완료. 잔여=$(pgrep -f "S2_LARGE_L1" | wc -l)" >> "$W"
    exit 0
  fi
  sleep 10
done
echo "[$(date +%H:%M:%S)] guard 타임아웃" >> "$W"
