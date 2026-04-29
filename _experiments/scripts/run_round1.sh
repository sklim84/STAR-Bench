#!/bin/bash
# ============================================================================
# Round 1 재실험 스크립트 (HOFINET 정정 후)
#
# 44개 모델 × 3 차원(KR single_turn, EN single_turn, multi-turn STR) × 1 round
# 결과 저장: _paper/_experiments/round1{,_en,_multiturn}/eval/
#
# 사용법:
#   bash _experiments/scripts/run_round1.sh --gpu 0 --port 11434 --group A --mode kr
#   bash _experiments/scripts/run_round1.sh --gpu 1 --port 11435 --group B --mode kr
#   bash _experiments/scripts/run_round1.sh --gpu 0,1 --port 11434 --group TP2 --mode kr
#
# group: A (GPU 0 small), B (GPU 1 small), C (medium 20-32B), TP2 (70B+ 양 GPU)
# mode:  kr (KR single_turn), en (EN single_turn), mt (multi-turn STR)
# ============================================================================

set -uo pipefail

GPU_ID="0"
PORT="11434"
GROUP="A"
MODE="kr"
HF_TOKEN="${HF_TOKEN:-}"
PROJECT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

# 결과 디렉토리 (mode별)
RESULT_KR="$PROJECT_ROOT/_paper/_experiments/round1"
RESULT_EN="$PROJECT_ROOT/_paper/_experiments/round1_en"
RESULT_MT="$PROJECT_ROOT/_paper/_experiments/round1_multiturn"
CASES_KR="$PROJECT_ROOT/_paper/benchmarks"
CASES_EN="$PROJECT_ROOT/_paper/benchmarks_en"
LOG_DIR="$PROJECT_ROOT/_paper/_experiments/logs"
MAX_TOTAL="${BENCH_MAX_TOTAL:-}"

# CLI 파싱
while [[ $# -gt 0 ]]; do
    case "$1" in
        --gpu)   GPU_ID="$2"; shift 2 ;;
        --port)  PORT="$2"; shift 2 ;;
        --group) GROUP="$2"; shift 2 ;;
        --mode)  MODE="$2"; shift 2 ;;
        *) echo "Unknown: $1"; exit 1 ;;
    esac
done

# .env 토큰 로드
if [ -z "$HF_TOKEN" ] && [ -f "$PROJECT_ROOT/.env" ]; then
    HF_TOKEN_VAL=$(grep "^HF_TOKEN" "$PROJECT_ROOT/.env" | sed 's/^[^:=]*[: ]*=//' | sed 's/^[^:=]*: *//' | tr -d ' "'"'"'')
    [ -n "$HF_TOKEN_VAL" ] && HF_TOKEN="$HF_TOKEN_VAL"
fi

# flash_attn 스텁
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
fi

# Kanana 커스텀 파서
KANANA_PARSER_PLUGIN="$PROJECT_ROOT/_paper/_experiments/scripts/kanana_tool_calls/kanana_tool_calls/functionary_kanana_tool_parser.py"
KANANA_CHAT_TEMPLATE="$PROJECT_ROOT/_paper/_experiments/scripts/kanana_tool_calls/kanana_tool_calls/lmalign_v1.jinja"

# ── 모델 정의 (44 모델 = 11 + 11 + 10 + 3 entries, think/nothink 확장 포함) ──
GROUP_A=(
    "qwen35-0.8b|Qwen/Qwen3.5-0.8B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-0.8B"
    "qwen35-2b|Qwen/Qwen3.5-2B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-2B"
    "qwen35-4b|Qwen/Qwen3.5-4B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-4B"
    "qwen35-9b|Qwen/Qwen3.5-9B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-9B"
    "qwen3-4b|Qwen/Qwen3-4B-Instruct-2507|qwen3_xml||Qwen/Qwen3-4B-Instruct-2507"
    "qwen25-1.5b|Qwen/Qwen2.5-1.5B-Instruct|hermes||Qwen/Qwen2.5-1.5B-Instruct"
    "qwen3-8b|Qwen/Qwen3-8B|qwen3_xml||Qwen/Qwen3-8B"
    "exaone-4.0-1.2b|LGAI-EXAONE/EXAONE-4.0-1.2B|hermes|--trust-remote-code|LGAI-EXAONE/EXAONE-4.0-1.2B"
    "glm-4.7-flash|zai-org/GLM-4.7-Flash|glm47|--trust-remote-code|zai-org/GLM-4.7-Flash"
    "hermes-3-8b|NousResearch/Hermes-3-Llama-3.1-8B|hermes||NousResearch/Hermes-3-Llama-3.1-8B"
    "ax-light|skt/A.X-4.0-Light|hermes||skt/A.X-4.0-Light"
)
# qwen3-4b-think를 GROUP_B 끝에 배치 (thinking 모드 9h+ 소요로 GPU 1을 마지막에 점유,
# GPU 0의 Group A가 먼저 끝나면 idle 발생 — 추후 A_OFFLOAD 패턴으로 보완 가능)
GROUP_B=(
    "xlam-1b|Salesforce/xLAM-2-1b-fc-r|xlam||Salesforce/xLAM-2-1b-fc-r"
    "xlam-3b|Salesforce/xLAM-2-3b-fc-r|xlam||Salesforce/xLAM-2-3b-fc-r"
    "xlam-8b|Salesforce/Llama-xLAM-2-8b-fc-r|xlam||Salesforce/Llama-xLAM-2-8b-fc-r"
    "llama-3.2-1b|meta-llama/Llama-3.2-1B-Instruct|llama3_json||meta-llama/Llama-3.2-1B-Instruct"
    "llama-3.2-3b|meta-llama/Llama-3.2-3B-Instruct|llama3_json||meta-llama/Llama-3.2-3B-Instruct"
    "llama-3.1-8b|meta-llama/Llama-3.1-8B-Instruct|llama3_json||meta-llama/Llama-3.1-8B-Instruct"
    "ministral-3b|mistralai/Ministral-3-3B-Instruct-2512|mistral||mistralai/Ministral-3-3B-Instruct-2512"
    "ministral-8b|mistralai/Ministral-3-8B-Instruct-2512|mistral||mistralai/Ministral-3-8B-Instruct-2512"
    "ministral-14b|mistralai/Ministral-3-14B-Instruct-2512|mistral||mistralai/Ministral-3-14B-Instruct-2512"
    "mistral-nemo|mistralai/Mistral-Nemo-Instruct-2407|mistral||mistralai/Mistral-Nemo-Instruct-2407"
    "qwen3-4b-think|Qwen/Qwen3-4B-Thinking-2507|qwen3_xml|--reasoning-parser qwen3|Qwen/Qwen3-4B-Thinking-2507"
)
GROUP_C=(
    "qwen35-27b|Qwen/Qwen3.5-27B|qwen3_coder|--reasoning-parser qwen3 --enforce-eager|Qwen/Qwen3.5-27B"
    "qwen3-30b|Qwen/Qwen3-30B-A3B-Instruct-2507|qwen3_xml|--max-model-len 32768|Qwen/Qwen3-30B-A3B-Instruct-2507"
    "qwen3-30b-think|Qwen/Qwen3-30B-A3B-Thinking-2507|qwen3_xml|--max-model-len 32768 --reasoning-parser qwen3|Qwen/Qwen3-30B-A3B-Thinking-2507"
    "qwen3-coder-30b|Qwen/Qwen3-Coder-30B-A3B-Instruct|qwen3_xml|--max-model-len 32768|Qwen/Qwen3-Coder-30B-A3B-Instruct"
    "exaone-4.0-32b|LGAI-EXAONE/EXAONE-4.0-32B|hermes|--trust-remote-code|LGAI-EXAONE/EXAONE-4.0-32B"
    "xlam-32b|Salesforce/xLAM-2-32b-fc-r|xlam||Salesforce/xLAM-2-32b-fc-r"
    "mistral-small|mistralai/Mistral-Small-3.2-24B-Instruct-2506|mistral||mistralai/Mistral-Small-3.2-24B-Instruct-2506"
    "gpt-oss-20b|openai/gpt-oss-20b|openai|--reasoning-parser openai_gptoss|openai/gpt-oss-20b"
    "kanana-2-inst|kakaocorp/kanana-2-30b-a3b-instruct|hermes||kakaocorp/kanana-2-30b-a3b-instruct"
    "kanana-2-think|kakaocorp/kanana-2-30b-a3b-thinking-2601|hermes|--reasoning-parser deepseek_r1|kakaocorp/kanana-2-30b-a3b-thinking-2601"
)
GROUP_TP2=(
    "llama-3.3-70b|meta-llama/Llama-3.3-70B-Instruct|llama3_json|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager|meta-llama/Llama-3.3-70B-Instruct"
    "xlam-70b|Salesforce/Llama-xLAM-2-70b-fc-r|xlam|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager|Salesforce/Llama-xLAM-2-70b-fc-r"
    "ax-4.0|skt/A.X-4.0|hermes|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager|skt/A.X-4.0"
)

# Group C 분할 (GPU 0/1 병렬, 변형 수 균형)
GROUP_C1=(
    "${GROUP_C[0]}"  # qwen35-27b (think/nothink, 2변형)
    "${GROUP_C[3]}"  # qwen3-coder-30b
    "${GROUP_C[5]}"  # xlam-32b
    "${GROUP_C[7]}"  # gpt-oss-20b (think/nothink, 2변형)
    "${GROUP_C[6]}"  # mistral-small
)
GROUP_C2=(
    "${GROUP_C[1]}"  # qwen3-30b
    "${GROUP_C[2]}"  # qwen3-30b-think (2변형)
    "${GROUP_C[4]}"  # exaone-4.0-32b
    "${GROUP_C[8]}"  # kanana-2-inst
    "${GROUP_C[9]}"  # kanana-2-think (2변형)
)

# SMOKE: 파이프라인 검증용 (가장 작은 2개 모델)
GROUP_SMOKE=(
    "qwen35-0.8b|Qwen/Qwen3.5-0.8B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-0.8B"
    "qwen25-1.5b|Qwen/Qwen2.5-1.5B-Instruct|hermes||Qwen/Qwen2.5-1.5B-Instruct"
)

# RECOVERY: Group B 비정상 종료로 누락된 mistral-nemo 단독 실행
GROUP_RECOVERY=(
    "mistral-nemo|mistralai/Mistral-Nemo-Instruct-2407|mistral||mistralai/Mistral-Nemo-Instruct-2407"
)

# A_OFFLOAD: Group A 후반부 5 entries를 GPU 1 idle 시간에 병렬 처리 (master Group A는 자체 흐름 유지)
# Master Group A가 [7/11]~[11/11] 도달 시점에 이미 결과 존재 → --resume으로 즉시 skip
GROUP_A_OFFLOAD=(
    "exaone-4.0-1.2b|LGAI-EXAONE/EXAONE-4.0-1.2B|hermes|--trust-remote-code|LGAI-EXAONE/EXAONE-4.0-1.2B"
    "qwen3-8b|Qwen/Qwen3-8B|qwen3_xml||Qwen/Qwen3-8B"
    "ax-light|skt/A.X-4.0-Light|hermes||skt/A.X-4.0-Light"
    "hermes-3-8b|NousResearch/Hermes-3-Llama-3.1-8B|hermes||NousResearch/Hermes-3-Llama-3.1-8B"
    "glm-4.7-flash|zai-org/GLM-4.7-Flash|glm47|--trust-remote-code|zai-org/GLM-4.7-Flash"
)

case "$GROUP" in
    A)     MODELS=("${GROUP_A[@]}") ;;
    B)     MODELS=("${GROUP_B[@]}") ;;
    C)     MODELS=("${GROUP_C[@]}") ;;
    C1)    MODELS=("${GROUP_C1[@]}") ;;
    C2)    MODELS=("${GROUP_C2[@]}") ;;
    TP2)   MODELS=("${GROUP_TP2[@]}") ;;
    SMOKE) MODELS=("${GROUP_SMOKE[@]}") ;;
    RECOVERY) MODELS=("${GROUP_RECOVERY[@]}") ;;
    A_OFFLOAD) MODELS=("${GROUP_A_OFFLOAD[@]}") ;;
    *)     echo "Unknown group: $GROUP (A, B, C, C1, C2, TP2, SMOKE)"; exit 1 ;;
esac

# Mode → output/cases 결정
case "$MODE" in
    kr) OUTPUT_DIR="$RESULT_KR";       BENCH_MODULE="_experiments.scripts.benchmark";          BENCH_EXTRA="--checkpoint --resume" ;;
    en) OUTPUT_DIR="$RESULT_EN";       BENCH_MODULE="_experiments.scripts.benchmark";          BENCH_EXTRA="--cases-dir $CASES_EN --checkpoint --resume" ;;
    mt) OUTPUT_DIR="$RESULT_MT";       BENCH_MODULE="_experiments.scripts.benchmark_multiturn"; BENCH_EXTRA="" ;;
    *)  echo "Unknown mode: $MODE (kr, en, mt)"; exit 1 ;;
esac

mkdir -p "$OUTPUT_DIR/eval" "$OUTPUT_DIR/checkpoint" "$LOG_DIR"

# 유틸리티
ts() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }

wait_for_server() {
    local port=$1 max_wait=${2:-600}
    ts "  서버 기동 대기 (port $port, max ${max_wait}s)..."
    for ((i=1; i<=max_wait/5; i++)); do
        if python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:$port/health', timeout=3)" 2>/dev/null; then
            ts "  서버 준비 완료 (${i}*5초)"
            return 0
        fi
        sleep 5
    done
    ts "  [ERROR] 서버 기동 타임아웃!"
    return 1
}

stop_server() {
    local port=$1
    local pids=$(lsof -ti:$port 2>/dev/null)
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill 2>/dev/null || true
        sleep 5
        echo "$pids" | xargs kill -9 2>/dev/null || true
        ts "  vLLM 서버 종료 (port=$port)"
    fi
    pkill -9 -f "vllm.*--port $port" 2>/dev/null || true
    sleep 2
}

run_benchmark() {
    local model_names=$1
    local max_env=""
    [ -n "$MAX_TOTAL" ] && max_env="BENCH_MAX_TOTAL=$MAX_TOTAL"
    ts "  벤치마크: $max_env PYTHONPATH=$PROJECT_ROOT/_paper python -m $BENCH_MODULE --models $model_names --output $OUTPUT_DIR $BENCH_EXTRA"
    env $max_env PYTHONPATH="$PROJECT_ROOT/_paper:${PYTHONPATH:-}" python -m "$BENCH_MODULE" --models $model_names --output "$OUTPUT_DIR" $BENCH_EXTRA
}

# 메인 루프
ts "============================================================"
ts "Round 1 재실험: GROUP=$GROUP MODE=$MODE GPU=$GPU_ID PORT=$PORT"
ts "OUTPUT: $OUTPUT_DIR"
ts "총 ${#MODELS[@]}개 모델 (think/nothink 변형 포함)"
ts "============================================================"

cd "$PROJECT_ROOT"

for ((idx=0; idx<${#MODELS[@]}; idx++)); do
    IFS='|' read -r alias hf_model parser extra_args bench_models <<< "${MODELS[$idx]}"

    ts ""
    ts "━━━ [$((idx+1))/${#MODELS[@]}] $alias ($hf_model) [$MODE] ━━━"

    stop_server "$PORT"

    # GPU 할당 (TP=2 vs 단일)
    if echo "$extra_args" | grep -q "tensor-parallel-size 2"; then
        CUDA_DEVICES="0,1"
    else
        CUDA_DEVICES="$GPU_ID"
    fi

    # Kanana 커스텀 파서 옵션
    KANANA_OPTS=""
    if [[ "$alias" == kanana-2-* ]]; then
        KANANA_OPTS="--tool-parser-plugin $KANANA_PARSER_PLUGIN --chat-template $KANANA_CHAT_TEMPLATE"
    fi

    vllm_cmd="CUDA_VISIBLE_DEVICES=$CUDA_DEVICES PYTHONPATH=$FLASH_ATTN_STUB:\${PYTHONPATH:-} HF_TOKEN=$HF_TOKEN python -m vllm.entrypoints.openai.api_server --model $hf_model --port $PORT --max-model-len 32768 --gpu-memory-utilization 0.95 --tool-call-parser $parser --enable-auto-tool-choice $extra_args $KANANA_OPTS"
    ts "  vLLM 시작 (CUDA=$CUDA_DEVICES)"
    eval "$vllm_cmd" > "$LOG_DIR/vllm_round1_${MODE}_${alias}.log" 2>&1 &

    if ! wait_for_server "$PORT" 600; then
        ts "  [SKIP] $alias 서버 기동 실패"
        tail -50 "$LOG_DIR/vllm_round1_${MODE}_${alias}.log" 2>/dev/null || true
        stop_server "$PORT"
        continue
    fi

    # bench_models 공백 분리
    bench_models_spaced=$(echo "$bench_models" | tr ',' ' ')
    VLLM_BASE_URL="http://localhost:$PORT/v1" run_benchmark "$bench_models_spaced" || true

    stop_server "$PORT"
    ts "  $alias 완료"
done

ts ""
ts "============================================================"
ts "Group $GROUP / Mode $MODE 전체 완료!"
ts "============================================================"
