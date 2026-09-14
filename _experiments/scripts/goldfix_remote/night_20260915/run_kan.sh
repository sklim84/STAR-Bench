#!/bin/bash
# kanana 2설정 재시도. --enforce-eager 로 CUDA 그래프 캡처를 건너뛴다(그 단계에서 3회 교착).
set -u
R=/home/mlp/hgyoo/bubble/codex/star-bench/STAR-Bench; cd "$R" || exit 1
export CUDA_HOME=/usr/local/cuda-12.8 FLASHINFER_NVCC=/usr/local/cuda-12.8/bin/nvcc
export PATH=$CUDA_HOME/bin:$PATH HF_HOME=/home/mlp/hgyoo/bubble/codex/star-bench/hf_cache
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
source /home/mlp/hgyoo/bubble/codex/star-bench/.venv312/bin/activate || exit 1
PYTHONPATH=/tmp/fake_flash_attn python -c "
import importlib.metadata as md
from transformers.utils.import_utils import is_flash_attn_2_available
assert md.version('flash_attn')=='2.0.0'; assert is_flash_attn_2_available() is False" || { echo "PREFLIGHT FAIL stub"; exit 1; }
echo "PREFLIGHT OK"
IDS=_experiments/rerun_gold_fix/case_ids.txt
S=_experiments/scripts/run_benchmark_fin2.sh
L=_experiments/logs/goldfix
go(){ bash "$S" --gpu "$1" --port "$2" --group "$3" --mode kr --case-ids-file "$IDS" --force-rerun > "$L/$4.log" 2>&1; }
go 2 18482 KAN2_I kan2I &
sleep 120
go 3 18483 KAN2_T kan2T &
wait
