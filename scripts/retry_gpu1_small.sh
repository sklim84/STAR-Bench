#!/bin/bash
# GPU 1: 미완료 소형 모델 retry (Ministral-14B 완료 전까지 GPU 1 활용)
set -euo pipefail
cd /home/work/kftc_sklim/KA-001-AML-Assistant

PORT=11435
GPU=1
RESULTS_DIR="_paper/results"
LOG="_paper/results/logs/retry_gpu1_small.log"
HF_CACHE="/home/work/kftc_sklim/.hf_cache"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

start_vllm() {
    local model=$1 parser=$2 extra=${3:-}
    log "Starting vLLM: $model (parser=$parser) on GPU $GPU"
    CUDA_VISIBLE_DEVICES=$GPU HF_HOME=$HF_CACHE PYTHONPATH="/tmp/fake_flash_attn:$PYTHONPATH" \
    python -m vllm.entrypoints.openai.api_server \
        --model "$model" \
        --port $PORT \
        --max-model-len 65536 \
        --gpu-memory-utilization 0.95 \
        --tool-call-parser "$parser" \
        --enable-auto-tool-choice \
        --download-dir "$HF_CACHE/vllm" \
        $extra \
        > "_paper/results/logs/vllm/vllm_retry2_gpu1_$(echo $model | tr '/' '_').log" 2>&1 &
    VLLM_PID=$!

    local elapsed=0
    while ! curl -s "http://localhost:$PORT/v1/models" > /dev/null 2>&1; do
        sleep 5; elapsed=$((elapsed + 5))
        if [ $elapsed -ge 300 ]; then
            log "ERROR: vLLM timeout for $model"
            kill $VLLM_PID 2>/dev/null || true
            return 1
        fi
    done
    log "vLLM ready (${elapsed}s)"
}

run_bench() {
    local model=$1
    log "Benchmarking $model..."
    VLLM_BASE_URL="http://localhost:$PORT/v1" \
    python -m _paper.scripts.benchmark \
        --models "$model" \
        --checkpoint \
        --output "$RESULTS_DIR/" 2>&1 | tail -5 | tee -a "$LOG"
}

stop_vllm() {
    log "Stopping vLLM (port $PORT)..."
    pkill -f "vllm.*--port $PORT" 2>/dev/null || true
    sleep 5
}

log "===== GPU1 small retry start ====="

# 1. Mistral-Small-24B (4 missing)
start_vllm "mistralai/Mistral-Small-3.2-24B-Instruct-2506" "mistral" && \
run_bench "mistralai/Mistral-Small-3.2-24B-Instruct-2506"
stop_vllm

# 2. Kanana-8B (9 missing)
start_vllm "kakaocorp/kanana-1.5-8b-instruct-2505" "functionary_v3_llama_31" && \
run_bench "kakaocorp/kanana-1.5-8b-instruct-2505"
stop_vllm

# 3. Kanana-15.7B (10 missing)
start_vllm "kakaocorp/kanana-1.5-15.7b-a3b-instruct" "functionary_v3_llama_31" && \
run_bench "kakaocorp/kanana-1.5-15.7b-a3b-instruct"
stop_vllm

# 4. Kanana-2.1B (16 missing)
start_vllm "kakaocorp/kanana-1.5-2.1b-instruct-2505" "functionary_v3_llama_31" && \
run_bench "kakaocorp/kanana-1.5-2.1b-instruct-2505"
stop_vllm

# 5. Ministral-3B (18 missing)
start_vllm "mistralai/Ministral-3-3B-Instruct-2512" "mistral" && \
run_bench "mistralai/Ministral-3-3B-Instruct-2512"
stop_vllm

log "===== GPU1 small retry complete ====="
