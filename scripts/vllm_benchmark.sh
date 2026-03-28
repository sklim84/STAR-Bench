#!/bin/bash
# =============================================================================
# vLLM 0.17.0 본격 벤치마크 (전체 1,258건)
#
# 목적: smoke test 통과 모델을 대상으로 전체 케이스 벤치마크 실행
#
# 사용법:
#   bash vllm_benchmark.sh                          # 전체 모델 순차 테스트
#   bash vllm_benchmark.sh --gpu 0 --port 11434     # GPU/포트 지정
#   bash vllm_benchmark.sh --models qwen3-8b        # 특정 모델만
#   bash vllm_benchmark.sh --list                   # 모델 목록 출력
#   bash vllm_benchmark.sh --only-missing           # eval 결과 없는 모델만
# =============================================================================

set -uo pipefail

WORK_DIR="/home/work/kftc_sklim/KA-001-AML-Assistant"
RESULTS_DIR="$WORK_DIR/_paper/results"
BENCH_SCRIPT="$WORK_DIR/_paper/scripts/benchmark.py"
LOG_DIR="$RESULTS_DIR/logs"

# HuggingFace 캐시 + 토큰
export HF_HOME="/home/work/kftc_sklim/.hf_cache"
if [ -f "$WORK_DIR/.env" ]; then
    HF_TOKEN_VAL=$(grep "^HF_TOKEN" "$WORK_DIR/.env" | sed 's/^[^:=]*[: ]*=//' | sed 's/^[^:=]*: *//' | tr -d ' "'"'"'')
    [ -n "$HF_TOKEN_VAL" ] && export HF_TOKEN="$HF_TOKEN_VAL"
fi

# flash-attn 호환성 우회
FLASH_ATTN_STUB="/tmp/fake_flash_attn"
if [ ! -f "$FLASH_ATTN_STUB/flash_attn/__init__.py" ]; then
    mkdir -p "$FLASH_ATTN_STUB/flash_attn/ops/triton"
    echo "pass" > "$FLASH_ATTN_STUB/flash_attn/__init__.py"
    cat > "$FLASH_ATTN_STUB/flash_attn/flash_attn_interface.py" << 'PYEOF'
def flash_attn_varlen_func(*args, **kwargs):
    raise NotImplementedError("flash_attn stub")
PYEOF
    echo "pass" > "$FLASH_ATTN_STUB/flash_attn/ops/__init__.py"
    echo "pass" > "$FLASH_ATTN_STUB/flash_attn/ops/triton/__init__.py"
    cat > "$FLASH_ATTN_STUB/flash_attn/ops/triton/rotary.py" << 'PYEOF'
def apply_rotary(*args, **kwargs):
    raise NotImplementedError("flash_attn rotary stub")
PYEOF
    ts "flash-attn 스텁 생성 완료: $FLASH_ATTN_STUB"
fi
export PYTHONPATH="$FLASH_ATTN_STUB:${PYTHONPATH:-}"

# Kanana 커스텀 파서
KANANA_PARSER_PLUGIN="$WORK_DIR/_paper/scripts/kanana_tool_calls/kanana_tool_calls/functionary_kanana_tool_parser.py"
KANANA_CHAT_TEMPLATE="$WORK_DIR/_paper/scripts/kanana_tool_calls/kanana_tool_calls/lmalign_v1.jinja"
KANANA_EXTRA="--tool-parser-plugin $KANANA_PARSER_PLUGIN --chat-template $KANANA_CHAT_TEMPLATE"

# 기본값
VLLM_PORT=11434
GPU_ID=""

# =============================================================================
# 모델 레지스트리 (smoke test 통과 30개)
# 형식: "그룹키|HF모델|tool-parser|추가옵션|벤치마크키"
# =============================================================================
MODEL_GROUPS=(
    # ── Kanana (커스텀 파서) ──
    "kanana-2.1b|kakaocorp/kanana-1.5-2.1b-instruct-2505|functionary_v3_llama_31|$KANANA_EXTRA|kakaocorp/kanana-1.5-2.1b-instruct-2505"
    "kanana-8b|kakaocorp/kanana-1.5-8b-instruct-2505|functionary_v3_llama_31|$KANANA_EXTRA|kakaocorp/kanana-1.5-8b-instruct-2505"
    "kanana-15.7b|kakaocorp/kanana-1.5-15.7b-a3b-instruct|functionary_v3_llama_31|$KANANA_EXTRA|kakaocorp/kanana-1.5-15.7b-a3b-instruct"

    # ── Qwen3 ──
    "qwen3-4b|Qwen/Qwen3-4B-Instruct-2507|qwen3_xml||Qwen/Qwen3-4B-Instruct-2507"
    "qwen3-4b-think|Qwen/Qwen3-4B-Thinking-2507|qwen3_xml|--reasoning-parser qwen3|Qwen/Qwen3-4B-Thinking-2507__nothink,Qwen/Qwen3-4B-Thinking-2507__think"
    "qwen3-8b|Qwen/Qwen3-8B|qwen3_xml||Qwen/Qwen3-8B"
    "qwen3-30b|Qwen/Qwen3-30B-A3B-Instruct-2507|qwen3_xml|--max-model-len 32768|Qwen/Qwen3-30B-A3B-Instruct-2507"
    "qwen3-30b-think|Qwen/Qwen3-30B-A3B-Thinking-2507|qwen3_xml|--max-model-len 32768 --reasoning-parser qwen3|Qwen/Qwen3-30B-A3B-Thinking-2507__nothink,Qwen/Qwen3-30B-A3B-Thinking-2507__think"
    "qwen25-1.5b|Qwen/Qwen2.5-1.5B-Instruct|hermes||Qwen/Qwen2.5-1.5B-Instruct"

    # ── Qwen3.5 (thinking 모델) ──
    "qwen35-0.8b|Qwen/Qwen3.5-0.8B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-0.8B__nothink,Qwen/Qwen3.5-0.8B__think"
    "qwen35-2b|Qwen/Qwen3.5-2B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-2B__nothink,Qwen/Qwen3.5-2B__think"
    "qwen35-4b|Qwen/Qwen3.5-4B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-4B__nothink,Qwen/Qwen3.5-4B__think"
    "qwen35-9b|Qwen/Qwen3.5-9B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-9B__nothink,Qwen/Qwen3.5-9B__think"
    "qwen35-27b|Qwen/Qwen3.5-27B|qwen3_coder|--reasoning-parser qwen3 --enforce-eager|Qwen/Qwen3.5-27B__nothink,Qwen/Qwen3.5-27B__think"

    # ── Phi-4 (Microsoft) ──
    "phi4-mini|microsoft/Phi-4-mini-instruct|phi4_mini_json|--max-model-len 16384|microsoft/Phi-4-mini-instruct"
    "phi4-mini-reason|microsoft/Phi-4-mini-reasoning|phi4_mini_json|--max-model-len 16384|microsoft/Phi-4-mini-reasoning"

    # ── Mistral ──
    "mistral-small|mistralai/Mistral-Small-3.2-24B-Instruct-2506|mistral||mistralai/Mistral-Small-3.2-24B-Instruct-2506"
    "ministral-3b|mistralai/Ministral-3-3B-Instruct-2512|mistral||mistralai/Ministral-3-3B-Instruct-2512"
    "ministral-8b|mistralai/Ministral-3-8B-Instruct-2512|mistral||mistralai/Ministral-3-8B-Instruct-2512"
    "ministral-14b|mistralai/Ministral-3-14B-Instruct-2512|mistral||mistralai/Ministral-3-14B-Instruct-2512"

    # ── OpenAI GPT-OSS (reasoning) ──
    "gpt-oss-20b|openai/gpt-oss-20b|openai|--reasoning-parser openai_gptoss|openai/gpt-oss-20b__nothink,openai/gpt-oss-20b__think"

    # ── Llama (Meta) ──
    "llama-3.1-8b|meta-llama/Llama-3.1-8B-Instruct|llama3_json||meta-llama/Llama-3.1-8B-Instruct"
    "llama-3.3-70b|meta-llama/Llama-3.3-70B-Instruct|llama3_json|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager|meta-llama/Llama-3.3-70B-Instruct"
    "llama-4-scout-17b|meta-llama/Llama-4-Scout-17B-16E-Instruct|llama3_json|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager --quantization bitsandbytes --load-format bitsandbytes|meta-llama/Llama-4-Scout-17B-16E-Instruct"

    # ── EXAONE (LG AI Research) ──
    "exaone-3.5-7.8b|LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct|hermes|--trust-remote-code|LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct"
    "exaone-3.5-32b|LGAI-EXAONE/EXAONE-3.5-32B-Instruct|hermes|--trust-remote-code --max-model-len 16384|LGAI-EXAONE/EXAONE-3.5-32B-Instruct"
    "exaone-4.0-1.2b|LGAI-EXAONE/EXAONE-4.0-1.2B|hermes|--trust-remote-code|LGAI-EXAONE/EXAONE-4.0-1.2B"
    "exaone-4.0-32b|LGAI-EXAONE/EXAONE-4.0-32B|hermes|--trust-remote-code|LGAI-EXAONE/EXAONE-4.0-32B"
    "exaone-deep-7.8b|LGAI-EXAONE/EXAONE-Deep-7.8B|hermes|--trust-remote-code|LGAI-EXAONE/EXAONE-Deep-7.8B"
    "exaone-deep-32b|LGAI-EXAONE/EXAONE-Deep-32B|hermes|--trust-remote-code|LGAI-EXAONE/EXAONE-Deep-32B"

    # ── Gemma 3 (Google) ──
    "gemma-3-12b|google/gemma-3-12b-it|pythonic||google/gemma-3-12b-it"
    "gemma-3-27b|google/gemma-3-27b-it|pythonic||google/gemma-3-27b-it"

    # ── Granite (IBM) ──
    "granite-8b|ibm-granite/granite-3.1-8b-instruct|granite|--trust-remote-code|ibm-granite/granite-3.1-8b-instruct"

    # ── GLM (Zhipu) ──
    "glm-4.7-flash|zai-org/GLM-4.7-Flash|glm47|--trust-remote-code|zai-org/GLM-4.7-Flash"
)

# =============================================================================
# 유틸리티
# =============================================================================
ts() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

list_models() {
    echo "벤치마크 대상 모델 (${#MODEL_GROUPS[@]}개):"
    echo ""
    printf "  %-22s %-55s %-18s %s\n" "그룹키" "HF 모델" "파서" "벤치마크 키"
    printf "  %-22s %-55s %-18s %s\n" "------" "--------" "----" "----------"
    for entry in "${MODEL_GROUPS[@]}"; do
        IFS='|' read -r key hf_model parser _ bench_keys <<< "$entry"
        printf "  %-22s %-55s %-18s %s\n" "$key" "$hf_model" "$parser" "$bench_keys"
    done
}

has_eval_result() {
    local group_key="$1"
    local bench_keys_str="$2"
    IFS=',' read -ra keys <<< "$bench_keys_str"
    for key in "${keys[@]}"; do
        local safe_key="$(echo "$key" | tr '/' '_')"
        if ! ls "$RESULTS_DIR"/eval/eval_${safe_key}_*.json 1>/dev/null 2>&1; then
            return 1
        fi
    done
    return 0
}

# =============================================================================
# vLLM 서버 관리
# =============================================================================
stop_vllm() {
    local pids=$(pgrep -f "vllm serve.*--port $VLLM_PORT" 2>/dev/null)
    if [ -n "$pids" ]; then
        ts "vLLM 중지 (port=$VLLM_PORT, PIDs: $pids)"
        echo "$pids" | xargs kill 2>/dev/null || true
        sleep 5
        pids=$(pgrep -f "vllm serve.*--port $VLLM_PORT" 2>/dev/null)
        if [ -n "$pids" ]; then
            echo "$pids" | xargs kill -9 2>/dev/null || true
            sleep 3
        fi
    fi
}

start_vllm() {
    local model="$1"
    local parser="$2"
    local extra_args="${3:-}"
    local safe_name="$(echo "$model" | tr '/' '.')"
    local log_file="$LOG_DIR/vllm/vllm_${safe_name}.log"

    ts "vLLM 시작: model=$model, parser=$parser"
    [ -n "$extra_args" ] && ts "  옵션: $extra_args"

    local gpu_prefix=""
    if [ -n "$GPU_ID" ]; then
        # TP=2인 경우 양쪽 GPU 모두 노출
        if echo "$extra_args" | grep -q "tensor-parallel-size 2"; then
            gpu_prefix="CUDA_VISIBLE_DEVICES=0,1"
        else
            gpu_prefix="CUDA_VISIBLE_DEVICES=$GPU_ID"
        fi
    fi

    eval $gpu_prefix HF_HOME="$HF_HOME" HF_TOKEN="${HF_TOKEN:-}" nohup vllm serve "$model" \
        --port "$VLLM_PORT" \
        --gpu-memory-utilization 0.9 \
        --download-dir "$HF_HOME/vllm" \
        --enable-auto-tool-choice \
        --tool-call-parser "$parser" \
        $extra_args \
        > "$log_file" 2>&1 &

    local vllm_pid=$!

    # 서버 준비 대기 (최대 10분)
    # NOTE: vLLM이 fork하면 원래 PID가 종료되므로 PID 체크 대신
    #       포트 기반 헬스체크 + 로그 파일 에러 감지로 판정
    local max_wait=120
    for i in $(seq 1 $max_wait); do
        if curl -s "http://localhost:$VLLM_PORT/v1/models" > /dev/null 2>&1; then
            ts "vLLM 준비 완료 ($(($i * 5))초)"
            return 0
        fi
        # 로그에 치명적 에러가 있으면 실패 처리
        if grep -qE "(^Traceback|^ERROR |RuntimeError:|ValueError:|OSError:)" "$log_file" 2>/dev/null; then
            ts "ERROR: vLLM 로그에서 에러 감지"
            tail -30 "$log_file" 2>/dev/null || true
            return 1
        fi
        sleep 5
    done
    ts "ERROR: vLLM 시작 타임아웃 (10분)"
    tail -30 "$log_file" 2>/dev/null || true
    stop_vllm
    return 1
}

# =============================================================================
# 벤치마크 실행 (전체 케이스)
# =============================================================================
run_benchmark() {
    local group_key="$1"
    local bench_keys_str="$2"
    local safe_key="$(echo "$group_key" | tr '/' '_')"

    IFS=',' read -ra bench_keys <<< "$bench_keys_str"

    for key in "${bench_keys[@]}"; do
        local bench_log="$LOG_DIR/bench/bench_${safe_key}.log"
        ts "  벤치마크: $key (전체 케이스)"

        VLLM_BASE_URL="http://localhost:$VLLM_PORT/v1" \
        python "$BENCH_SCRIPT" \
            --models "$key" \
            --checkpoint \
            -v \
            --log-file "$bench_log" \
            --output "$RESULTS_DIR/" 2>&1 | tail -5

        local rc=$?
        if [ $rc -eq 0 ]; then
            ts "  -> 성공 (exit=$rc)"
        else
            ts "  -> 실패 (exit=$rc)"
        fi
    done
}

# =============================================================================
# 메인 루프
# =============================================================================
run_model_group() {
    local group_key="$1"
    local hf_model="$2"
    local parser="$3"
    local extra_args="$4"
    local bench_keys="$5"

    ts "========================================================"
    ts "  [$group_key] $hf_model"
    ts "  parser=$parser"
    ts "========================================================"

    local gpu_q="${GPU_ID:-0}"
    ts "GPU$gpu_q: $(nvidia-smi --query-gpu=memory.free --format=csv,noheader -i $gpu_q 2>/dev/null || echo 'N/A') free"

    stop_vllm

    local start_time=$(date +%s)

    if ! start_vllm "$hf_model" "$parser" "$extra_args"; then
        ts "FAIL: vLLM 서버 시작 실패 - $group_key"
        echo "$group_key|FAIL_SERVE|$hf_model|$parser" >> "$RESULTS_DIR/benchmark_results.csv"
        return 1
    fi

    run_benchmark "$group_key" "$bench_keys"
    local bench_rc=$?

    stop_vllm

    local end_time=$(date +%s)
    local elapsed=$(( end_time - start_time ))
    local elapsed_min=$(( elapsed / 60 ))

    if [ $bench_rc -eq 0 ]; then
        ts "OK: $group_key (${elapsed_min}분 ${elapsed}초)"
        echo "$group_key|OK|$hf_model|$parser|${elapsed_min}m" >> "$RESULTS_DIR/benchmark_results.csv"
    else
        ts "FAIL: $group_key 벤치마크 실패 (${elapsed_min}분)"
        echo "$group_key|FAIL_BENCH|$hf_model|$parser|${elapsed_min}m" >> "$RESULTS_DIR/benchmark_results.csv"
    fi
    echo ""
}

# =============================================================================
# 인자 파싱
# =============================================================================
SELECTED_MODELS=()
ONLY_MISSING=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --list)
            list_models
            exit 0
            ;;
        --only-missing)
            ONLY_MISSING=true
            shift
            ;;
        --gpu)
            GPU_ID="$2"
            shift 2
            ;;
        --port)
            VLLM_PORT="$2"
            shift 2
            ;;
        --models)
            shift
            while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do
                SELECTED_MODELS+=("$1")
                shift
            done
            ;;
        *)
            echo "사용법: $0 [--list] [--only-missing] [--gpu N] [--port N] [--models 키1 키2 ...]"
            exit 1
            ;;
    esac
done

# =============================================================================
# 실행
# =============================================================================
mkdir -p "$RESULTS_DIR" "$LOG_DIR/vllm" "$LOG_DIR/bench" "$RESULTS_DIR/eval" "$RESULTS_DIR/checkpoint"

ts "=========================================="
ts "  vLLM 0.17.0 전체 벤치마크 (1,258건)"
ts "  GPU: ${GPU_ID:-auto}  |  포트: $VLLM_PORT"
ts "  대상: ${SELECTED_MODELS[*]:-전체 (${#MODEL_GROUPS[@]}개)}"
ts "=========================================="

# CSV 헤더
if [ ! -f "$RESULTS_DIR/benchmark_results.csv" ]; then
    echo "group_key|status|hf_model|parser|elapsed" > "$RESULTS_DIR/benchmark_results.csv"
fi

completed=0
skipped=0
failed=0

for entry in "${MODEL_GROUPS[@]}"; do
    IFS='|' read -r group_key hf_model parser extra_args bench_keys <<< "$entry"

    # --models 필터
    if [ ${#SELECTED_MODELS[@]} -gt 0 ]; then
        match=false
        for sel in "${SELECTED_MODELS[@]}"; do
            if [[ "$group_key" == "$sel" ]]; then
                match=true
                break
            fi
        done
        if ! $match; then
            continue
        fi
    fi

    # --only-missing 필터
    if $ONLY_MISSING && has_eval_result "$group_key" "$bench_keys"; then
        ts "SKIP (이미 완료): $group_key"
        ((skipped++))
        continue
    fi

    if run_model_group "$group_key" "$hf_model" "$parser" "$extra_args" "$bench_keys"; then
        ((completed++))
    else
        ((failed++))
    fi
done

# =============================================================================
# 결과 요약
# =============================================================================
ts "=========================================="
ts "  벤치마크 완료!"
ts "  완료: $completed  |  스킵: $skipped  |  실패: $failed"
ts "=========================================="
echo ""
ts "결과 요약:"
echo ""
printf "  %-22s %-12s %-55s %s\n" "모델" "상태" "HF 모델" "시간"
printf "  %-22s %-12s %-55s %s\n" "------" "------" "--------" "----"
while IFS='|' read -r key status model parser elapsed; do
    [ "$key" = "group_key" ] && continue
    printf "  %-22s %-12s %-55s %s\n" "$key" "$status" "$model" "${elapsed:-}"
done < "$RESULTS_DIR/benchmark_results.csv"
echo ""
ts "상세 로그: $LOG_DIR/"
ts "평가 결과: $RESULTS_DIR/eval/"
ts "체크포인트: $RESULTS_DIR/checkpoint/"
