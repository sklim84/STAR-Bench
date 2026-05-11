#!/bin/bash
# 2026-05-08 T/NT 정정 재실험 통합 런처
# 사용법:
#   GPU별로 nohup 백그라운드 실행:
#     nohup bash run_rerun_all.sh gpt_oss_20b 1 11434 > /home/work/kftc_model/.tmp/rerun_gpt_oss_20b.log 2>&1 &
#     nohup bash run_rerun_all.sh gpt_oss_120b 2,3,4,5 11435 > /home/work/kftc_model/.tmp/rerun_gpt_oss_120b.log 2>&1 &
#     nohup bash run_rerun_all.sh kanana_inst_2601 6 11436 > /home/work/kftc_model/.tmp/rerun_kanana_inst_2601.log 2>&1 &

set -uo pipefail

# 모든 캐시를 /home/work/kftc_model/.cache로 강제 (49GB 작은 /home/work 우회)
export HF_HOME="/home/work/kftc_model/.cache/huggingface"
export HF_HUB_CACHE="/home/work/kftc_model/.cache/huggingface/hub"
export HF_DATASETS_CACHE="/home/work/kftc_model/.cache/huggingface/datasets"
export HF_XET_CACHE_DIR="/home/work/kftc_model/.cache/huggingface/xet"
export TRANSFORMERS_CACHE="/home/work/kftc_model/.cache/huggingface/hub"
export TMPDIR="/home/work/kftc_model/.tmp"
export TORCH_COMPILE_CACHE_DIR="/home/work/kftc_model/.cache/vllm/torch_compile_cache"
export VLLM_CACHE_ROOT="/home/work/kftc_model/.cache/vllm"
mkdir -p "$HF_HOME" "$TMPDIR" "$VLLM_CACHE_ROOT"

# 케이스 병렬 실행 (ThreadPoolExecutor). vLLM batched inference 활용
export BENCH_CONCURRENCY="${BENCH_CONCURRENCY:-8}"

TARGET="${1:-}"
GPU="${2:-0}"
PORT="${3:-11434}"

PROJECT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
RUNNER="$PROJECT_ROOT/_paper/_experiments/scripts/run_benchmark.sh"

case "$TARGET" in
    gpt_oss_20b)        GROUP="RERUN_GPT_OSS_20B" ;;
    gpt_oss_120b)       GROUP="RERUN_GPT_OSS_120B" ;;
    kanana_inst_2601)   GROUP="RERUN_KANANA_INST_2601" ;;
    kanana_think)       GROUP="RERUN_KANANA_THINK" ;;
    *) echo "Usage: $0 {gpt_oss_20b|gpt_oss_120b|kanana_inst_2601} <gpu> <port>"; exit 1 ;;
esac

echo "[$(date)] === $TARGET 재실험 시작 (GPU=$GPU PORT=$PORT GROUP=$GROUP) ==="

for MODE in kr en mt; do
    echo "[$(date)] --- $TARGET $MODE phase 시작 ---"
    bash "$RUNNER" --gpu "$GPU" --port "$PORT" --group "$GROUP" --mode "$MODE"
    rc=$?
    echo "[$(date)] --- $TARGET $MODE phase 완료 (exit=$rc) ---"
done

echo "[$(date)] === $TARGET 재실험 전체 완료 ==="
