#!/bin/bash
# 유휴 GPU 2·3 투입: qwen35-4b(미배정) + qwen36-35b-a3b(L1 대기열에서 당겨옴)
# run_benchmark.sh 사본(run_benchmark_gf.sh)을 쓴다 — 원본은 실행 중인 레인이 읽고 있다.
# flashinfer 캐시는 지우지 않는다 — moe2 가 이미 정리했고 두 레인이 사용 중이다.
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
command -v python >/dev/null || { echo "PREFLIGHT FAIL: python 없음"; exit 1; }
PYTHONPATH=/tmp/fake_flash_attn python -c "
import torch, vllm
from transformers.utils.import_utils import is_flash_attn_2_available
assert torch.cuda.is_available()
assert is_flash_attn_2_available() is False
print('  torch', torch.__version__, 'GPU', torch.cuda.device_count(), 'vllm', vllm.__version__)
" || { echo "PREFLIGHT FAIL: import"; exit 1; }
for p in 18456 18457; do
  if ss -ltn 2>/dev/null | grep -q ":$p "; then echo "PREFLIGHT FAIL: port $p 사용중"; exit 1; fi
done
echo "  flashinfer 캐시 유지(실행 중 레인 보호), nvcc=$(command -v nvcc)"
echo "PREFLIGHT OK"

IDS=_experiments/rerun_gold_fix/case_ids.txt
[ -f "$IDS" ] || { echo "PREFLIGHT FAIL: case_ids 없음"; exit 1; }
S=_experiments/scripts/run_benchmark_gf.sh
L=_experiments/logs/goldfix
mkdir -p "$L"
ts(){ echo "[$(date +%H:%M:%S)] $*"; }
run_one(){ local gpu=$1 port=$2 name=$3 g=$4
  { ts "=== $g 시작 (gpu=$gpu port=$port) ==="
    bash "$S" --gpu "$gpu" --port "$port" --group "$g" --mode kr --case-ids-file "$IDS" --force-rerun
    ts "=== $g 종료 rc=$? ==="; } > "$L/$name.log" 2>&1; }

ts "###### 유휴 GPU 투입 (2:GF_4B, 3:GF_35BA3B) ######" >> "$L/idle.log"
run_one 2 18456 idleG2 GF_4B &
run_one 3 18457 idleG3 GF_35BA3B &
wait
ts "###### 유휴 GPU 완료 ######" >> "$L/idle.log"
