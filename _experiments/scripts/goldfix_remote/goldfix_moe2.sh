#!/bin/bash
# MoE 3설정 따라잡기 (2차) — 오염된 flashinfer JIT 캐시를 지우고 돌린다.
# 원인: 캐시된 build.ninja 상단에 cuda_home = /usr 가 박혀 있어(02:47/02:53 생성,
#       당시 CUDA_HOME 미설정) 규칙 nvcc = $cuda_home/bin/nvcc 가 CUDA 11.5 를 불렀고
#       compute_90a 를 모르는 그 컴파일러가 MoE 커널 빌드를 깨뜨렸다.
#       환경변수 전달은 정상이었다(실증 완료). 파일에 박힌 값이 문제였다.
set -u
R=/home/mlp/hgyoo/bubble/codex/star-bench/STAR-Bench
VENV=/home/mlp/hgyoo/bubble/codex/star-bench/.venv312
FICACHE=/home/mlp/hgyoo/bubble/.identity_profiles/webconsole/.cache/flashinfer
cd "$R" || exit 1
export CUDA_HOME=/usr/local/cuda-12.8
export FLASHINFER_NVCC="$CUDA_HOME/bin/nvcc"
export PATH="$CUDA_HOME/bin:$PATH"
export HF_HOME=/home/mlp/hgyoo/bubble/codex/star-bench/hf_cache
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
source "$VENV/bin/activate" || { echo "PREFLIGHT FAIL: venv"; exit 1; }

VER=$(nvcc --version 2>/dev/null | grep -oE "release [0-9]+\.[0-9]+" | cut -d" " -f2)
case "$VER" in 12.*|13.*) : ;; *) echo "PREFLIGHT FAIL: nvcc $VER"; exit 1 ;; esac
PYTHONPATH=/tmp/fake_flash_attn python -c "
import torch
from transformers.utils.import_utils import is_flash_attn_2_available
assert torch.cuda.is_available()
assert is_flash_attn_2_available() is False
print('  torch', torch.__version__, 'GPU', torch.cuda.device_count(), 'flash_attn2 False')
" || exit 1

# 오염된 컴파일 규칙 제거 (flashinfer 만. vllm 캐시 2.5GB 는 건드리지 않는다)
BAD=$(grep -rl "cuda_home = /usr$" "$FICACHE" 2>/dev/null | wc -l)
echo "  오염된 build.ninja ${BAD}개 발견 → flashinfer 캐시 삭제"
rm -rf "$FICACHE"
echo "  삭제 후 존재: $([ -d "$FICACHE" ] && echo 예 || echo 아니오)"
echo "  nvcc=$(command -v nvcc) FLASHINFER_NVCC=$FLASHINFER_NVCC"
echo "PREFLIGHT OK"

IDS=_experiments/rerun_gold_fix/case_ids.txt
S=_experiments/scripts/run_benchmark.sh
L=_experiments/logs/goldfix
mkdir -p "$L"
ts(){ echo "[$(date +%H:%M:%S)] $*"; }
run_one(){ local gpu=$1 port=$2 name=$3 g=$4
  { ts "=== $g 시작 (gpu=$gpu port=$port CUDA_HOME=$CUDA_HOME) ==="
    bash "$S" --gpu "$gpu" --port "$port" --group "$g" --mode kr --case-ids-file "$IDS" --force-rerun
    ts "=== $g 종료 rc=$? ==="; } > "$L/$name.log" 2>&1; }

ts "###### MoE 따라잡기 2차 ######" >> "$L/moe2.log"
run_one 0 18454 moe2L1 S2_LARGE_L1 &
run_one 1 18455 moe2L3 S2_LARGE_L3 &
wait
ts "###### 2차 완료 ######" >> "$L/moe2.log"
for m in Qwen_Qwen3_6-35B-A3B kakaocorp_kanana-2-30b-a3b-instruct kakaocorp_kanana-2-30b-a3b-thinking-2601; do
  n=$(find _experiments/results_kr/eval -name "eval_${m}_*.json" -newermt "2026-09-14 07:30:00" 2>/dev/null | wc -l)
  ts "   $m : ${n}개" >> "$L/moe2.log"
done
