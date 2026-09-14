#!/bin/bash
# GPU 1 (moe2L3 종료로 해제) 에 마지막 미배정 설정 qwen36-27b 투입
set -u
R=/home/mlp/hgyoo/bubble/codex/star-bench/STAR-Bench
VENV=/home/mlp/hgyoo/bubble/codex/star-bench/.venv312
cd "$R" || exit 1
export CUDA_HOME=/usr/local/cuda-12.8
export FLASHINFER_NVCC="$CUDA_HOME/bin/nvcc"
export PATH="$CUDA_HOME/bin:$PATH"
export HF_HOME=/home/mlp/hgyoo/bubble/codex/star-bench/hf_cache
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
source "$VENV/bin/activate" || { echo "PREFLIGHT FAIL: venv"; exit 1; }
VER=$(nvcc --version 2>/dev/null | grep -oE "release [0-9]+\.[0-9]+" | cut -d" " -f2)
case "$VER" in 12.*|13.*) : ;; *) echo "PREFLIGHT FAIL: nvcc $VER"; exit 1 ;; esac
command -v python >/dev/null || { echo "PREFLIGHT FAIL: python"; exit 1; }
echo "PREFLIGHT OK (nvcc=$(command -v nvcc))"
IDS=_experiments/rerun_gold_fix/case_ids.txt
S=_experiments/scripts/run_benchmark_gf2.sh
L=_experiments/logs/goldfix
{ echo "[$(date +%H:%M:%S)] === GF_36_27B 시작 (gpu=1 port=18458) ==="
  bash "$S" --gpu 1 --port 18458 --group GF_36_27B --mode kr --case-ids-file "$IDS" --force-rerun
  echo "[$(date +%H:%M:%S)] === GF_36_27B 종료 rc=$? ==="; } > "$L/idleG1.log" 2>&1
