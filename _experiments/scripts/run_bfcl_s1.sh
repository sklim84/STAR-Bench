#!/bin/bash
# ============================================================================
# S1 BFCL 분담 runner — 13 모델
#  Phase 1 (병렬 단일 GPU 11모델): Lane 0 (GPU 0, 6) + Lane 1 (GPU 1, 5)
#  Phase 2 (순차 TP=2 2모델): Llama-3.3-70B → A.X-4.0
#
# 사용법:
#   bash run_bfcl_s1.sh                   # 전체
#   bash run_bfcl_s1.sh phase1_lane0      # Lane 0만
#   bash run_bfcl_s1.sh phase1_lane1      # Lane 1만
#   bash run_bfcl_s1.sh phase2            # TP=2만
# ============================================================================
set -uo pipefail
ts() { date "+%Y-%m-%d %H:%M:%S"; }
PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RESULT_DIR="$PROJ/_experiments/bfcl_results/result"
SCORE_DIR="$PROJ/_experiments/bfcl_results/score"
LOG_DIR="$PROJ/_experiments/logs"
FAKE_FLASH="/tmp/fake_flash_attn"
HF_TOKEN_VAL=$(grep "^HF_TOKEN" "$PROJ/.env" | sed 's/^[^:=]*[: ]*=//' | tr -d ' "'"'"'')

mkdir -p "$RESULT_DIR" "$SCORE_DIR" "$LOG_DIR"

stop_vllm() {
    local port=$1
    pkill -9 -f "vllm.entrypoints.*--port $port" 2>/dev/null
    sleep 5
}

stop_all_vllm_on_gpu() {
    local gpu=$1
    nvidia-smi --query-compute-apps=pid,used_gpu_memory --format=csv,noheader -i "$gpu" 2>/dev/null | awk -F, '{print $1}' | xargs -r kill -9 2>/dev/null
    sleep 5
}

wait_server() {
    local port=$1
    for i in $(seq 1 1500); do
        if python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:$port/health', timeout=1)" 2>/dev/null; then
            return 0
        fi
        sleep 1
    done
    return 1
}

# run_bfcl <gpu> <port> <model> <parser> <max_len> <extra_args> <tag> [bfcl_model]
# bfcl_model 기본값은 $model. BFCL key가 vLLM model 이름과 다른 경우 (예: Llama-3.x -FC suffix) 8번째 인자로 분리 전달.
run_bfcl() {
    local gpu=$1 port=$2 model=$3 parser=$4 max_len=${5:-32768} extra=${6:-} tag=$7 bfcl_model=${8:-$3}

    echo "$(ts) [BFCL-$tag] === $model (bfcl key: $bfcl_model) ==="
    stop_vllm "$port"

    PYTHONPATH=${FAKE_FLASH}:${PYTHONPATH:-} HF_TOKEN=$HF_TOKEN_VAL CUDA_VISIBLE_DEVICES=$gpu \
    python -m vllm.entrypoints.openai.api_server \
        --model "$model" --port "$port" \
        --max-model-len "$max_len" --gpu-memory-utilization 0.92 \
        --tool-call-parser "$parser" --enable-auto-tool-choice \
        $extra > "$LOG_DIR/vllm_bfcl_${tag}.log" 2>&1 &
    local vllm_pid=$!

    if wait_server "$port"; then
        echo "$(ts) [BFCL-$tag] generate"
        REMOTE_OPENAI_BASE_URL="http://localhost:$port/v1" REMOTE_OPENAI_API_KEY="EMPTY" \
        bfcl generate --model "$bfcl_model" --backend vllm --skip-server-setup \
            --test-category all --num-threads 16 \
            --result-dir "$RESULT_DIR" --allow-overwrite \
            > "$LOG_DIR/bfcl_gen_${tag}.log" 2>&1 || echo "$(ts) [BFCL-$tag] generate error"

        echo "$(ts) [BFCL-$tag] evaluate"
        bfcl evaluate --model "$bfcl_model" --test-category all \
            --result-dir "$RESULT_DIR" --score-dir "$SCORE_DIR" \
            > "$LOG_DIR/bfcl_eval_${tag}.log" 2>&1 || \
        bfcl evaluate --model "$bfcl_model" --test-category all --partial-eval \
            --result-dir "$RESULT_DIR" --score-dir "$SCORE_DIR" \
            >> "$LOG_DIR/bfcl_eval_${tag}.log" 2>&1
    else
        echo "$(ts) [BFCL-$tag] vLLM 부팅 실패"
        tail -30 "$LOG_DIR/vllm_bfcl_${tag}.log"
    fi
    kill $vllm_pid 2>/dev/null
    stop_vllm "$port"
    echo "$(ts) [BFCL-$tag] 완료"
}

# ─────────────────────────────────────────────────────────────────
# Phase 1 Lane 0 (GPU 0): 6 모델
# ─────────────────────────────────────────────────────────────────
phase1_lane0() {
    run_bfcl 0 11434 "LGAI-EXAONE/EXAONE-4.0-1.2B" "hermes" 32768 "--trust-remote-code" "exaone_1.2b"
    run_bfcl 0 11434 "meta-llama/Llama-3.2-3B-Instruct" "llama3_json" 32768 "" "llama_3.2_3b"
    run_bfcl 0 11434 "microsoft/Phi-4-mini-instruct" "phi4_mini_json" 16384 "--chat-template $PROJ/_experiments/scripts/tool_chat_template_phi4_mini.jinja" "phi4_mini"
    run_bfcl 0 11434 "NousResearch/Hermes-3-Llama-3.1-8B" "hermes" 32768 "" "hermes3_8b"
    run_bfcl 0 11434 "DragonLLM/Llama-Open-Finance-8B" "llama3_json" 32768 "" "dragon_llama_fin"
    run_bfcl 0 11434 "LGAI-EXAONE/EXAONE-4.0-32B" "hermes" 16384 "--trust-remote-code" "exaone_32b"
}

# ─────────────────────────────────────────────────────────────────
# Phase 1 Lane 1 (GPU 1): 5 모델
# ─────────────────────────────────────────────────────────────────
phase1_lane1() {
    run_bfcl 1 11435 "google/gemma-4-E4B-it" "gemma4" 32768 "" "gemma4_e4b"
    run_bfcl 1 11435 "mistralai/Ministral-3-3B-Instruct-2512" "mistral" 32768 "" "ministral_3b"
    run_bfcl 1 11435 "skt/A.X-4.0-Light" "hermes" 16384 "" "ax_light"
    run_bfcl 1 11435 "DragonLLM/Qwen-Open-Finance-R-8B" "qwen3_xml" 32768 "--reasoning-parser qwen3" "dragon_qwen_fin"
    run_bfcl 1 11435 "mistralai/Mistral-Small-3.2-24B-Instruct-2506" "mistral" 32768 "" "mistral_small_24b"
}

# ─────────────────────────────────────────────────────────────────
# Phase 2 TP=2 (GPU 0+1): 2 모델
# ─────────────────────────────────────────────────────────────────
phase2() {
    # Llama-3.3-70B는 BFCL에 'meta-llama/Llama-3.3-70B-Instruct-FC' key로 등록 (model_config.py:1360)
    run_bfcl "0,1" 11434 "meta-llama/Llama-3.3-70B-Instruct" "llama3_json" 16384 \
        "--tensor-parallel-size 2 --enforce-eager" "llama_3.3_70b" \
        "meta-llama/Llama-3.3-70B-Instruct-FC"
    run_bfcl "0,1" 11434 "skt/A.X-4.0" "hermes" 8192 \
        "--tensor-parallel-size 2 --enforce-eager" "ax_4.0"
}

# ─────────────────────────────────────────────────────────────────
# Recovery — 이름 mismatch로 실패한 모델 (-FC suffix)
# Llama-3.2-3B는 BFCL에 'meta-llama/Llama-3.2-3B-Instruct-FC' key로 등록 (model_config.py:1348)
# ─────────────────────────────────────────────────────────────────
recovery() {
    # GPU 1, port 11435 (Lane 1 GPU 활용 — Phase 1 Lane 0이 GPU 0 점유 중일 때 안전)
    run_bfcl 1 11435 "meta-llama/Llama-3.2-3B-Instruct" "llama3_json" 32768 "" "llama_3.2_3b_fc" \
        "meta-llama/Llama-3.2-3B-Instruct-FC"
}

# ─────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────
target="${1:-all}"
echo "$(ts) ==== S1 BFCL runner 시작 (target=$target) ===="
START=$(date +%s)

case "$target" in
    phase1_lane0) phase1_lane0 ;;
    phase1_lane1) phase1_lane1 ;;
    phase2) phase2 ;;
    recovery) recovery ;;
    all)
        # Phase 1: 양 lane 병렬
        phase1_lane0 > "$LOG_DIR/bfcl_lane0.log" 2>&1 &
        PID0=$!
        phase1_lane1 > "$LOG_DIR/bfcl_lane1.log" 2>&1 &
        PID1=$!
        echo "$(ts) Phase 1 양 lane PID=$PID0,$PID1"
        wait $PID0 || echo "$(ts) Lane 0 종료 (rc=$?)"
        wait $PID1 || echo "$(ts) Lane 1 종료 (rc=$?)"
        echo "$(ts) Phase 1 완료"
        # Phase 2: 순차 TP=2
        phase2
        ;;
    *) echo "Unknown target: $target"; exit 1 ;;
esac

ELAPSED=$(($(date +%s) - START))
echo "$(ts) ==== 완료 — 소요 $((ELAPSED/3600))시간 $((ELAPSED%3600/60))분 ===="
