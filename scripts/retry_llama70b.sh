#!/bin/bash
# Llama-3.3-70B context length error retry (121 cases)
# - Checkpoint already cleaned (api_error entries removed)
# - Uses --max-model-len 32768 (was 16384)
# - TP=2 requires both GPUs → wait for GPU 0 to be free

set -euo pipefail
cd /home/work/kftc_sklim/KA-001-AML-Assistant

LOG="_paper/results/logs/retry_llama70b_ctx.log"
MODEL="meta-llama/Llama-3.3-70B-Instruct"
PORT=11434
RESULTS_DIR="_paper/results"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "===== Llama-3.3-70B retry start (121 ctx_length errors, --max-model-len 32768) ====="

# Wait for GPU 0 benchmark to finish
log "Waiting for GPU 0 (Ministral-8B) to finish..."
while pgrep -f "vllm.*--port 11434" > /dev/null 2>&1; do
    sleep 30
done
log "GPU 0 is free"

# Also make sure GPU 1 is free
while pgrep -f "vllm.*--port 11435" > /dev/null 2>&1; do
    sleep 10
done
log "GPU 1 is free — both GPUs available for TP=2"

# Start vLLM with TP=2 and increased max-model-len
log "Starting vLLM: $MODEL (TP=2, max-model-len=32768)"
HF_HOME=/home/work/kftc_sklim/.hf_cache \
python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --port $PORT \
    --tensor-parallel-size 2 \
    --max-model-len 32768 \
    --gpu-memory-utilization 0.95 \
    --enforce-eager \
    --tool-call-parser llama3_json \
    --enable-auto-tool-choice \
    --download-dir /home/work/kftc_sklim/.hf_cache/vllm \
    > "_paper/results/logs/vllm/vllm_retry_llama-3.3-70b.log" 2>&1 &
VLLM_PID=$!
log "vLLM PID: $VLLM_PID"

# Wait for vLLM to be ready
TIMEOUT=300
ELAPSED=0
while ! curl -s "http://localhost:$PORT/v1/models" > /dev/null 2>&1; do
    sleep 5
    ELAPSED=$((ELAPSED + 5))
    if [ $ELAPSED -ge $TIMEOUT ]; then
        log "ERROR: vLLM failed to start within ${TIMEOUT}s"
        kill $VLLM_PID 2>/dev/null || true
        exit 1
    fi
done
log "vLLM ready (${ELAPSED}s)"

# Run benchmark (checkpoint will skip completed cases, only run 121 missing)
log "Benchmarking $MODEL (121 missing cases)..."
VLLM_BASE_URL="http://localhost:$PORT/v1" \
python -m _paper.scripts.benchmark \
    --models "$MODEL" \
    --checkpoint \
    --output "$RESULTS_DIR/" 2>&1 | tee -a "$LOG"

BENCH_EXIT=$?
log "Benchmark exit code: $BENCH_EXIT"

# Stop vLLM
log "Stopping vLLM..."
kill $VLLM_PID 2>/dev/null || true
wait $VLLM_PID 2>/dev/null || true
log "vLLM stopped"

log "===== Llama-3.3-70B retry complete ====="
