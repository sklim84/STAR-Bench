#!/bin/bash
# 금키 잔여 4설정. GPU 4장에 하나씩. 2026-09-15
# 08:10 에 웹콘솔 재시작으로 레인이 딸려 죽었으므로 setsid 로 완전 분리해 띄운다.
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
command -v python >/dev/null || { echo "PREFLIGHT FAIL: python"; exit 1; }
PYTHONPATH=/tmp/fake_flash_attn python -c "
import torch, vllm
from transformers.utils.import_utils import is_flash_attn_2_available
assert torch.cuda.is_available() and torch.cuda.device_count() == 4
assert is_flash_attn_2_available() is False
print('  torch', torch.__version__, 'GPU 4 vllm', vllm.__version__)
" || { echo "PREFLIGHT FAIL: import"; exit 1; }
if nvidia-smi --query-compute-apps=pid --format=csv,noheader | grep -q .; then
  echo "PREFLIGHT FAIL: GPU 사용 중인 프로세스가 있다"; exit 1; fi
BAD=$(grep -rl "cuda_home = /usr$" "$FICACHE" 2>/dev/null | wc -l)
echo "  오염된 build.ninja ${BAD}개 → flashinfer 캐시 삭제 (레인 없음 확인됨)"
rm -rf "$FICACHE"
echo "PREFLIGHT OK  nvcc=$(command -v nvcc)"

IDS=_experiments/rerun_gold_fix/case_ids.txt
S=_experiments/scripts/run_benchmark_fin.sh
L=_experiments/logs/goldfix
mkdir -p "$L"
ts(){ echo "[$(date +%H:%M:%S)] $*"; }
run(){ local gpu=$1 port=$2 name=$3 grp=$4 force=$5
  { ts "=== $grp gpu=$gpu port=$port force=$force ==="
    if [ "$force" = "yes" ]; then
      bash "$S" --gpu "$gpu" --port "$port" --group "$grp" --mode kr --case-ids-file "$IDS" --force-rerun
    else
      bash "$S" --gpu "$gpu" --port "$port" --group "$grp" --mode kr --case-ids-file "$IDS"
    fi
    ts "=== $grp 종료 rc=$? (rc 는 신뢰불가 — 체크포인트로 판정) ==="; } > "$L/$name.log" 2>&1; }

ts "###### 잔여 4설정 시작 ######" >> "$L/fin.log"
run 0 18470 finQ3527 FIN_Q35_27B no  &
run 1 18471 finQ3627 FIN_Q36_27B yes &
run 2 18472 finKanI  FIN_KAN_I   yes &
run 3 18473 finKanT  FIN_KAN_T   yes &
wait
ts "###### 잔여 4설정 완료 ######" >> "$L/fin.log"
