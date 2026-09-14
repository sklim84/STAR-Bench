#!/bin/bash
# 남은 3설정(qwen36-27b, kanana-inst, kanana-think)을 GPU 가 비는 대로 스스로 물린다.
# 접속이 끊겨도 계속 돌도록 큐를 서버에 남긴다.
# 주의: run_benchmark.sh 는 vLLM 기동 실패해도 rc=0 "전체 완료!" 를 찍는다. 완료 판정은 eval 의 timestamp 로 한다.
set -u
R=/home/mlp/hgyoo/bubble/codex/star-bench/STAR-Bench
VENV=/home/mlp/hgyoo/bubble/codex/star-bench/.venv312
cd "$R" || exit 1
export CUDA_HOME=/usr/local/cuda-12.8
export FLASHINFER_NVCC="$CUDA_HOME/bin/nvcc"
export PATH="$CUDA_HOME/bin:$PATH"
export HF_HOME=/home/mlp/hgyoo/bubble/codex/star-bench/hf_cache
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
source "$VENV/bin/activate" || { echo "FAIL venv"; exit 1; }
IDS=_experiments/rerun_gold_fix/case_ids.txt
L=_experiments/logs/goldfix
Q=$L/queue.log
echo "[$(date +%H:%M:%S)] 큐 시작" > "$Q"

free_mb(){ nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$1" 2>/dev/null | tr -d " "; }
wait_free(){ local i=$1 n=$2
  for k in $(seq 1 540); do
    m=$(free_mb "$i"); [ -n "$m" ] && [ "$m" -lt 5000 ] && { echo "[$(date +%H:%M:%S)] GPU$i 해제 확인 (${m}MiB) -> $n" >> "$Q"; return 0; }
    sleep 20
  done
  echo "[$(date +%H:%M:%S)] GPU$i 대기 타임아웃 -> $n 미실행" >> "$Q"; return 1; }
launch(){ local gpu=$1 port=$2 name=$3 grp=$4 sc=$5
  { echo "[$(date +%H:%M:%S)] === $grp 시작 (gpu=$gpu port=$port) ==="
    bash "$sc" --gpu "$gpu" --port "$port" --group "$grp" --mode kr --case-ids-file "$IDS" --force-rerun
    echo "[$(date +%H:%M:%S)] === $grp 종료 rc=$? ==="; } > "$L/$name.log" 2>&1
  echo "[$(date +%H:%M:%S)] $grp 종료(rc 는 신뢰불가, eval 확인 필요)" >> "$Q"; }

GF2=_experiments/scripts/run_benchmark_gf2.sh
GF3=_experiments/scripts/run_benchmark_gf3.sh

( wait_free 1 qwen36-27b   && launch 1 18458 idleG1 GF_36_27B $GF2 ) &
( wait_free 2 kanana-inst  && launch 2 18460 kanI   GF_KAN_I  $GF3 ) &
( wait_free 0 kanana-think && launch 0 18461 kanT   GF_KAN_T  $GF3 ) &
wait
echo "[$(date +%H:%M:%S)] 큐 완료" >> "$Q"
