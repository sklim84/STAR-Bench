#!/bin/bash
# MoE 3설정 따라잡기 — nvcc 를 CUDA 12.8 로 고정해 FlashInfer JIT 실패를 푼다.
#
# 원인: PATH 의 /usr/bin/nvcc 가 CUDA 11.5 라 compute_90a 를 모른다.
#       FlashInfer 가 fused_moe 커널을 JIT 컴파일할 때만 터지므로 MoE 셋만 걸렸고
#       dense 모델은 그 경로를 타지 않아 전부 정상이었다.
#
# 대상 3설정과 소속 그룹:
#   Qwen3.6-35B-A3B            -> S2_LARGE_L1 (qwen35-27b, qwen36-27b 는 재실행됨)
#   kanana-2-30b-a3b-instruct  -> S2_LARGE_L3 (gpt-oss-20b 는 재실행됨)
#   kanana-2-30b-a3b-thinking  -> S2_LARGE_L3
# RERUN_KANANA_INST_2601 은 instruct-2601 이라는 다른 모델이고 코호트 밖이라 쓰지 않는다.
set -u
R=/home/mlp/hgyoo/bubble/codex/star-bench/STAR-Bench
VENV=/home/mlp/hgyoo/bubble/codex/star-bench/.venv312
cd "$R" || exit 1
export CUDA_HOME=/usr/local/cuda-12.8
export PATH="$CUDA_HOME/bin:$PATH"
export HF_HOME=/home/mlp/hgyoo/bubble/codex/star-bench/hf_cache
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
source "$VENV/bin/activate" || { echo "PREFLIGHT FAIL: venv"; exit 1; }

VER=$(nvcc --version 2>/dev/null | grep -oE "release [0-9]+\.[0-9]+" | cut -d" " -f2)
echo "  nvcc: $(command -v nvcc) (release $VER)"
case "$VER" in 12.*|13.*) : ;; *) echo "PREFLIGHT FAIL: nvcc $VER 는 compute_90a 불가"; exit 1 ;; esac
nvcc --help 2>/dev/null | grep -q "90a" || { echo "PREFLIGHT FAIL: compute_90a 미지원"; exit 1; }
PYTHONPATH=/tmp/fake_flash_attn python -c "
import torch
from transformers.utils.import_utils import is_flash_attn_2_available
assert torch.cuda.is_available(), 'CUDA 불가'
assert is_flash_attn_2_available() is False, 'flash_attn 스텁이 True 로 보고됨'
print('  torch', torch.__version__, '· GPU', torch.cuda.device_count(), '장 · flash_attn2 False')
" || exit 1
for p in 18444 18445; do ss -ltn 2>/dev/null | grep -q ":$p " && { echo "PREFLIGHT FAIL: 포트 $p 사용 중"; exit 1; }; done
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

ts "###### MoE 따라잡기 시작 ######" >> "$L/moe.log"
run_one 0 18444 moeL1 S2_LARGE_L1 &
run_one 1 18445 moeL3 S2_LARGE_L3 &
wait
ts "###### MoE 따라잡기 완료 ######" >> "$L/moe.log"

# 목표 3설정이 실제로 생성됐는지 자체 검증
ts "── 결과 확인" >> "$L/moe.log"
for m in Qwen_Qwen3_6-35B-A3B kakaocorp_kanana-2-30b-a3b-instruct kakaocorp_kanana-2-30b-a3b-thinking-2601; do
  n=$(ls _experiments/results_kr/eval/eval_${m}_*.json 2>/dev/null | wc -l)
  ts "   $m : ${n}개" >> "$L/moe.log"
done
