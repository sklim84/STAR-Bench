#!/bin/bash
# 금키 재실행 (단일턴 68케이스 x 28설정) — H200 4장 병렬
set -u
R=/home/mlp/hgyoo/bubble/codex/star-bench/STAR-Bench
VENV=/home/mlp/hgyoo/bubble/codex/star-bench/.venv312   # cu128. .venv 는 cu130 이라 드라이버 12.8 과 불일치
STUB=/tmp/fake_flash_attn
cd "$R" || exit 1
export HF_HOME=/home/mlp/hgyoo/bubble/codex/star-bench/hf_cache
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
source "$VENV/bin/activate" || { echo "PREFLIGHT FAIL: venv"; exit 1; }

PYTHONPATH="$STUB" python - <<'PY' || exit 1
import sys
import torch, vllm
from transformers.utils.import_utils import is_flash_attn_2_available
if not torch.cuda.is_available():
    print("PREFLIGHT FAIL: CUDA 불가"); sys.exit(1)
try:
    fa = is_flash_attn_2_available()
except Exception as e:
    print("PREFLIGHT FAIL: flash_attn 조회 예외", type(e).__name__, e); sys.exit(1)
if fa:
    print("PREFLIGHT FAIL: 스텁이 사용 가능으로 보고됨(True) — 실제 커널이 없어 생성 중 터진다"); sys.exit(1)
from transformers import AutoConfig
AutoConfig.from_pretrained("meta-llama/Llama-3.2-3B-Instruct")
print(f"  torch {torch.__version__} · GPU {torch.cuda.device_count()}장 · vllm {vllm.__version__} · flash_attn2={fa} · 게이트모델 OK")
PY
for p in 18434 18435 18436 18437; do
  ss -ltn 2>/dev/null | grep -q ":$p " && { echo "PREFLIGHT FAIL: 포트 $p 사용 중"; exit 1; }
done
echo "PREFLIGHT OK"

IDS=_experiments/rerun_gold_fix/case_ids.txt
S=_experiments/scripts/run_benchmark.sh
L=_experiments/logs/goldfix
mkdir -p "$L"
ts(){ echo "[$(date +%H:%M:%S)] $*"; }
run_groups(){ local gpu=$1 port=$2 name=$3; shift 3
  { for g in "$@"; do
      ts "=== $g 시작 (gpu=$gpu port=$port) ==="
      bash "$S" --gpu "$gpu" --port "$port" --group "$g" --mode kr --case-ids-file "$IDS" --force-rerun
      ts "=== $g 종료 rc=$? ==="
    done; } > "$L/$name.log" 2>&1; }

ts "###### 1단계: 단일 GPU 4레인 (23설정) ######" >> "$L/main.log"
run_groups 0 18434 laneA S1_A &
run_groups 1 18435 laneB S1_B &
run_groups 2 18436 laneC S2_LARGE_L1 S2_LARGE_L2 &
run_groups 3 18437 laneD S2_LARGE_L3 &
wait
ts "###### 1단계 완료 ######" >> "$L/main.log"
ts "###### 2단계: TP 그룹 (5설정) ######" >> "$L/main.log"
run_groups 0,1 18434 laneTP2 S2_TP2_A S2_TP2_B S2_TP2_C
run_groups 0,1,2,3 18434 laneTP4 S2_TP4
ts "###### 전체 완료 ######" >> "$L/main.log"
