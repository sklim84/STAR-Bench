#!/bin/bash
# ============================================================================
# Per-GPU 벤치마크 실행기 (HOFINET 정정본, 24-model 분담)
#
# 24개 모델 × 3 차원(KR single_turn, EN single_turn, multi-turn STR)
# 결과 저장: _paper/_experiments/results_{kr,en,mt}/eval/
#
# 사용법:
#   bash _experiments/scripts/run_benchmark.sh --gpu 0 --port 11434 --group S1_A --mode kr
#   bash _experiments/scripts/run_benchmark.sh --gpu 1 --port 11435 --group S1_B --mode kr
#   bash _experiments/scripts/run_benchmark.sh --gpu 0,1 --port 11434 --group S2_TP2_A --mode kr
#
# group: S1_A/S1_B (서버1 단일-GPU), S2_TP4/S2_TP2_*/S2_LARGE_* (서버2)
#        SMOKE (파이프라인 검증), RQ2_REPS (RQ2 ablation 6 representatives)
# mode:  kr (KR single_turn), en (EN single_turn), mt (multi-turn STR)
# ============================================================================

set -uo pipefail

GPU_ID="0"
PORT="11434"
GROUP="A"
MODE="kr"
TOOLS_LANG=""           # "" (default = KR tools), "en" (RQ2 ablation)
CASE_IDS_FILE=""        # 부분 재실험: case ID 목록 파일
FORCE_RERUN=""          # 1이면 --force-rerun 추가 (체크포인트 캐시 무시)
HF_TOKEN="${HF_TOKEN:-}"
PROJECT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

# 결과 디렉토리 (mode별)
RESULT_KR="$PROJECT_ROOT/_paper/_experiments/results_kr"
RESULT_EN="$PROJECT_ROOT/_paper/_experiments/results_en"
RESULT_MT="$PROJECT_ROOT/_paper/_experiments/results_mt"
CASES_KR="$PROJECT_ROOT/_paper/benchmarks"
CASES_EN="$PROJECT_ROOT/_paper/benchmarks_en"
LOG_DIR="$PROJECT_ROOT/_paper/_experiments/logs"
MAX_TOTAL="${BENCH_MAX_TOTAL:-}"

# CLI 파싱
while [[ $# -gt 0 ]]; do
    case "$1" in
        --gpu)        GPU_ID="$2"; shift 2 ;;
        --port)       PORT="$2"; shift 2 ;;
        --group)      GROUP="$2"; shift 2 ;;
        --mode)       MODE="$2"; shift 2 ;;
        --tools-lang) TOOLS_LANG="$2"; shift 2 ;;
        --case-ids-file) CASE_IDS_FILE="$2"; shift 2 ;;
        --force-rerun)   FORCE_RERUN="1"; shift 1 ;;
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

# ===========================================================================
# 서버별 GROUP (MODELS.md 24-model 기준)
# ===========================================================================
# Server 1 (2× H100 80GB) — 11 모델: small/medium 단일-GPU
# Server 2 (6× H100 80GB) — 13 모델: large + TP=2 + TP=4
# ===========================================================================

# Server 1 GPU 0 (6 모델)
# - Gemma-4-E4B-it: 공식 multimodal + gemma4 parser (vLLM 0.19 + transformers 5.7.0 필수)
# - Phi-4-mini: phi4_mini_json + vLLM 공식 jinja chat template (functools[...] 형식 강제)
# - DragonLLM/Llama-Open-Finance-8B: A안 swap (Llama-Fin-8b 0/5 대체, smoke 3/5 score 0.78)
GROUP_S1_A=(
    "qwen35-4b|Qwen/Qwen3.5-4B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-4B"
    "gemma-4-e4b|google/gemma-4-E4B-it|gemma4||google/gemma-4-E4B-it"
    "phi-4-mini|microsoft/Phi-4-mini-instruct|phi4_mini_json|--chat-template $PROJECT_ROOT/_paper/_experiments/scripts/tool_chat_template_phi4_mini.jinja|microsoft/Phi-4-mini-instruct"
    "xlam-3b|Salesforce/xLAM-2-3b-fc-r|xlam||Salesforce/xLAM-2-3b-fc-r"
    "exaone-1.2b|LGAI-EXAONE/EXAONE-4.0-1.2B|hermes|--trust-remote-code|LGAI-EXAONE/EXAONE-4.0-1.2B"
    "dragon-llama-fin|DragonLLM/Llama-Open-Finance-8B|llama3_json||DragonLLM/Llama-Open-Finance-8B"
)

# Server 1 GPU 1 (5 모델)
# - DragonLLM/Qwen-Open-Finance-R-8B: A안 swap (Fino1-8B 0/5 대체, smoke 3/5 score 0.73)
GROUP_S1_B=(
    "llama-3.2-3b|meta-llama/Llama-3.2-3B-Instruct|llama3_json||meta-llama/Llama-3.2-3B-Instruct"
    "ministral-3b|mistralai/Ministral-3-3B-Instruct-2512|mistral||mistralai/Ministral-3-3B-Instruct-2512"
    "hermes-3-8b|NousResearch/Hermes-3-Llama-3.1-8B|hermes||NousResearch/Hermes-3-Llama-3.1-8B"
    "ax-light|skt/A.X-4.0-Light|hermes|--max-model-len 16384|skt/A.X-4.0-Light"
    "dragon-qwen-fin|DragonLLM/Qwen-Open-Finance-R-8B|qwen3_xml|--reasoning-parser qwen3|DragonLLM/Qwen-Open-Finance-R-8B"
)

# Server 2 — TP=4 (gpt-oss-120b, 4 GPUs)
GROUP_S2_TP4=(
    "gpt-oss-120b|openai/gpt-oss-120b|openai|--tensor-parallel-size 4 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager --reasoning-parser openai_gptoss|openai/gpt-oss-120b"
)

# Server 2 — TP=2 (3 pair 병렬, 각 70B+)
GROUP_S2_TP2_A=(
    "llama-3.3-70b|meta-llama/Llama-3.3-70B-Instruct|llama3_json|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager|meta-llama/Llama-3.3-70B-Instruct"
)
GROUP_S2_TP2_B=(
    "xlam-70b|Salesforce/Llama-xLAM-2-70b-fc-r|xlam|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager|Salesforce/Llama-xLAM-2-70b-fc-r"
)
GROUP_S2_TP2_C=(
    "ax-4.0|skt/A.X-4.0|hermes|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager|skt/A.X-4.0"
)

# Server 2 — Single-GPU Large (9 모델 → 3 lanes × 3 모델)
GROUP_S2_LARGE_L1=(
    "qwen35-27b|Qwen/Qwen3.5-27B|qwen3_coder|--reasoning-parser qwen3 --enforce-eager|Qwen/Qwen3.5-27B"
    "qwen36-27b|Qwen/Qwen3.6-27B|qwen3_xml||Qwen/Qwen3.6-27B"
    "qwen36-35b-a3b|Qwen/Qwen3.6-35B-A3B|qwen3_xml|--max-model-len 32768|Qwen/Qwen3.6-35B-A3B"
)
GROUP_S2_LARGE_L2=(
    "gemma-4-31b|google/gemma-4-31B-it|gemma4||google/gemma-4-31B-it"
    "mistral-small|mistralai/Mistral-Small-3.2-24B-Instruct-2506|mistral||mistralai/Mistral-Small-3.2-24B-Instruct-2506"
    "exaone-32b|LGAI-EXAONE/EXAONE-4.0-32B|hermes|--trust-remote-code|LGAI-EXAONE/EXAONE-4.0-32B"
)
GROUP_S2_LARGE_L3=(
    "gpt-oss-20b|openai/gpt-oss-20b|openai|--reasoning-parser openai_gptoss|openai/gpt-oss-20b"
    "kanana-2-inst|kakaocorp/kanana-2-30b-a3b-instruct|functionary_v3_llama_31||kakaocorp/kanana-2-30b-a3b-instruct"
    "kanana-2-think|kakaocorp/kanana-2-30b-a3b-thinking-2601|functionary_v3_llama_31||kakaocorp/kanana-2-30b-a3b-thinking-2601"
)

# ===========================================================================
# 보조 그룹
# ===========================================================================

# SMOKE: 파이프라인 검증용 (가장 작은 2개 모델, 일반 검증)
GROUP_SMOKE=(
    "qwen35-4b|Qwen/Qwen3.5-4B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-4B"
    "exaone-1.2b|LGAI-EXAONE/EXAONE-4.0-1.2B|hermes|--trust-remote-code|LGAI-EXAONE/EXAONE-4.0-1.2B"
)

# RQ2_REPS: 4-way 2x2 (KR-KR/EN-KR/KR-EN/EN-EN) ablation 6 representatives
# 모두 Server 2 large/TP=2 엔트리 — Server 2에서 --tools-lang en 으로 KR-EN/EN-EN 추가 실행
# KR-KR (default, kr mode): master S2 baseline에 자동 포함
# EN-KR (default, en mode): master S2 baseline에 자동 포함
# KR-EN: bash run_benchmark.sh --gpu ... --group RQ2_REPS --mode kr --tools-lang en
# EN-EN: bash run_benchmark.sh --gpu ... --group RQ2_REPS --mode en --tools-lang en
GROUP_RQ2_REPS=(
    "qwen35-27b|Qwen/Qwen3.5-27B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-27B"
    "qwen36-27b|Qwen/Qwen3.6-27B|qwen3_xml||Qwen/Qwen3.6-27B"
    "llama-3.3-70b|meta-llama/Llama-3.3-70B-Instruct|llama3_json|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95|meta-llama/Llama-3.3-70B-Instruct"
    "gemma-4-31b|google/gemma-4-31B-it|gemma4||google/gemma-4-31B-it"
    "exaone-32b|LGAI-EXAONE/EXAONE-4.0-32B|hermes|--trust-remote-code|LGAI-EXAONE/EXAONE-4.0-32B"
    "ax-4.0|skt/A.X-4.0|hermes|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95|skt/A.X-4.0"
)

# S1_RQ2_RECOVERY_QWEN: 누락 KR-EN Qwen3.5-27B (think+nothink)
# 단일 GPU + max-model-len 32768 (long context cases 처리)
GROUP_S1_RQ2_RECOVERY_QWEN=(
    "qwen35-27b|Qwen/Qwen3.5-27B|qwen3_coder|--max-model-len 32768 --reasoning-parser qwen3|Qwen/Qwen3.5-27B"
)

# S1_RQ2_RECOVERY_EXAONE: 누락 KR-EN EXAONE-32B
GROUP_S1_RQ2_RECOVERY_EXAONE=(
    "exaone-32b|LGAI-EXAONE/EXAONE-4.0-32B|hermes|--max-model-len 32768 --trust-remote-code|LGAI-EXAONE/EXAONE-4.0-32B"
)

# S1_RQ2_RECOVERY_GEMMA: 누락 EN-EN Gemma-4-31B-it
# concurrency=2 + --enforce-eager로 vLLM scheduler hang 회피
GROUP_S1_RQ2_RECOVERY_GEMMA=(
    "gemma-4-31b|google/gemma-4-31B-it|gemma4|--max-model-len 32768 --enforce-eager|google/gemma-4-31B-it"
)

# S1_RQ2_RECOVERY_GEMMA_TP2: 양 GPU 활용 가속 (Lane A 종료 후 사용)
GROUP_S1_RQ2_RECOVERY_GEMMA_TP2=(
    "gemma-4-31b|google/gemma-4-31B-it|gemma4|--tensor-parallel-size 2 --max-model-len 32768 --gpu-memory-utilization 0.9 --enforce-eager|google/gemma-4-31B-it"
)

# BFCL ↔ AML 매칭 확장: BFCL에 평가됐으나 AML 미평가인 7 모델을 KR로 평가
# Lane 0 (GPU 0, port 11434): 4 Qwen 모델 (단일 GPU 30B 이하)
GROUP_BFCL_AML_LANE0=(
    "qwen3-30b-a3b-inst|Qwen/Qwen3-30B-A3B-Instruct-2507|qwen3_xml|--max-model-len 32768|Qwen/Qwen3-30B-A3B-Instruct-2507"
    "qwen3-8b|Qwen/Qwen3-8B|qwen3_xml||Qwen/Qwen3-8B"
    "qwen3-4b-inst|Qwen/Qwen3-4B-Instruct-2507|qwen3_xml||Qwen/Qwen3-4B-Instruct-2507"
    "qwen35-9b|Qwen/Qwen3.5-9B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-9B"
)
# Lane 1 (GPU 1, port 11435): 2 xLAM 모델 (단일 GPU)
GROUP_BFCL_AML_LANE1=(
    "xlam-2-1b|Salesforce/xLAM-2-1b-fc-r|xlam||Salesforce/xLAM-2-1b-fc-r"
    "xlam-2-8b|Salesforce/Llama-xLAM-2-8b-fc-r|xlam||Salesforce/Llama-xLAM-2-8b-fc-r"
)
# Lane 1B (GPU 1, port 11435): Lane 0 가속용 (Qwen3-4B/3.5-9B). Lane 0이 도달 시 --resume으로 skip
GROUP_BFCL_AML_LANE1B=(
    "qwen3-4b-inst|Qwen/Qwen3-4B-Instruct-2507|qwen3_xml||Qwen/Qwen3-4B-Instruct-2507"
    "qwen35-9b|Qwen/Qwen3.5-9B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-9B"
)
# TP=2 (양 GPU 활용): xLAM-2-32B
GROUP_BFCL_AML_TP2=(
    "xlam-2-32b|Salesforce/xLAM-2-32b-fc-r|xlam|--tensor-parallel-size 2 --max-model-len 32768 --gpu-memory-utilization 0.9 --enforce-eager|Salesforce/xLAM-2-32b-fc-r"
)

# ===========================================================================
# RERUN_REASONING (2026-05-08): T/NT 토글 정정 재실험
# - gpt-oss: chat_template_kwargs.enable_thinking 무시 → reasoning_effort high/low 사용
# - kanana-2-thinking-2601: 토글 미지원 → instruct-2601 신규 모델로 NT 비교
# 같은 그룹 정의이지만 단일 GPU(20b) / TP=4(120b) / 30B-A3B 별도 그룹으로 분리
# ===========================================================================
GROUP_RERUN_GPT_OSS_20B=(
    "gpt-oss-20b|openai/gpt-oss-20b|openai|--reasoning-parser openai_gptoss|openai/gpt-oss-20b"
)
GROUP_RERUN_GPT_OSS_120B=(
    "gpt-oss-120b|openai/gpt-oss-120b|openai|--tensor-parallel-size 4 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager --reasoning-parser openai_gptoss|openai/gpt-oss-120b"
)
GROUP_RERUN_KANANA_INST_2601=(
    "kanana-2-inst-2601|kakaocorp/kanana-2-30b-a3b-instruct-2601|hermes||kakaocorp/kanana-2-30b-a3b-instruct-2601"
)

case "$GROUP" in
    # Server 1
    S1_A) MODELS=("${GROUP_S1_A[@]}") ;;
    S1_B) MODELS=("${GROUP_S1_B[@]}") ;;
    # Server 2
    S2_TP4) MODELS=("${GROUP_S2_TP4[@]}") ;;
    S2_TP2_A) MODELS=("${GROUP_S2_TP2_A[@]}") ;;
    S2_TP2_B) MODELS=("${GROUP_S2_TP2_B[@]}") ;;
    S2_TP2_C) MODELS=("${GROUP_S2_TP2_C[@]}") ;;
    S2_LARGE_L1) MODELS=("${GROUP_S2_LARGE_L1[@]}") ;;
    S2_LARGE_L2) MODELS=("${GROUP_S2_LARGE_L2[@]}") ;;
    S2_LARGE_L3) MODELS=("${GROUP_S2_LARGE_L3[@]}") ;;
    # 보조
    SMOKE) MODELS=("${GROUP_SMOKE[@]}") ;;
    RQ2_REPS) MODELS=("${GROUP_RQ2_REPS[@]}") ;;
    S1_RQ2_RECOVERY_QWEN) MODELS=("${GROUP_S1_RQ2_RECOVERY_QWEN[@]}") ;;
    S1_RQ2_RECOVERY_EXAONE) MODELS=("${GROUP_S1_RQ2_RECOVERY_EXAONE[@]}") ;;
    S1_RQ2_RECOVERY_GEMMA) MODELS=("${GROUP_S1_RQ2_RECOVERY_GEMMA[@]}") ;;
    S1_RQ2_RECOVERY_GEMMA_TP2) MODELS=("${GROUP_S1_RQ2_RECOVERY_GEMMA_TP2[@]}") ;;
    BFCL_AML_LANE0) MODELS=("${GROUP_BFCL_AML_LANE0[@]}") ;;
    BFCL_AML_LANE1) MODELS=("${GROUP_BFCL_AML_LANE1[@]}") ;;
    BFCL_AML_LANE1B) MODELS=("${GROUP_BFCL_AML_LANE1B[@]}") ;;
    BFCL_AML_TP2) MODELS=("${GROUP_BFCL_AML_TP2[@]}") ;;
    # 2026-05-08 T/NT 정정 재실험
    RERUN_GPT_OSS_20B) MODELS=("${GROUP_RERUN_GPT_OSS_20B[@]}") ;;
    RERUN_GPT_OSS_120B) MODELS=("${GROUP_RERUN_GPT_OSS_120B[@]}") ;;
    RERUN_KANANA_INST_2601) MODELS=("${GROUP_RERUN_KANANA_INST_2601[@]}") ;;
    *)     echo "Unknown group: $GROUP"; exit 1 ;;
esac

# Mode → output/cases 결정
case "$MODE" in
    kr) OUTPUT_DIR="$RESULT_KR";       BENCH_MODULE="_experiments.scripts.benchmark";          BENCH_EXTRA="--checkpoint --resume" ;;
    en) OUTPUT_DIR="$RESULT_EN";       BENCH_MODULE="_experiments.scripts.benchmark";          BENCH_EXTRA="--cases-dir $CASES_EN --checkpoint --resume" ;;
    mt) OUTPUT_DIR="$RESULT_MT";       BENCH_MODULE="_experiments.scripts.benchmark_multiturn"; BENCH_EXTRA="--checkpoint --resume" ;;
    *)  echo "Unknown mode: $MODE (kr, en, mt)"; exit 1 ;;
esac

# RQ2 4-way ablation: --tools-lang en일 때 별도 디렉토리/플래그 (kr+en/en+en만 별도 보관, kr/en 기본 결과와 분리)
if [[ "$TOOLS_LANG" == "en" ]]; then
    OUTPUT_DIR="${OUTPUT_DIR}_tools_en"
    BENCH_EXTRA="$BENCH_EXTRA --tools-lang en"
fi

# 부분 재실험: --case-ids-file / --force-rerun 패스스루
# CRITICAL: --resume은 모델 단위 skip을 트리거하므로 부분 재실험 모드에서는 자동 제거
if [[ -n "$CASE_IDS_FILE" ]] || [[ -n "$FORCE_RERUN" ]]; then
    BENCH_EXTRA="${BENCH_EXTRA// --resume/}"
fi
if [[ -n "$CASE_IDS_FILE" ]]; then
    BENCH_EXTRA="$BENCH_EXTRA --case-ids-file $CASE_IDS_FILE"
fi
if [[ -n "$FORCE_RERUN" ]]; then
    BENCH_EXTRA="$BENCH_EXTRA --force-rerun"
fi

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
    local extra_env=""
    [ -n "$MAX_TOTAL" ] && extra_env="$extra_env BENCH_MAX_TOTAL=$MAX_TOTAL"
    [ "${BENCH_SKIP_THINK:-0}" = "1" ] && extra_env="$extra_env BENCH_SKIP_THINK=1"
    ts "  벤치마크: $extra_env PYTHONPATH=$PROJECT_ROOT/_paper python -m $BENCH_MODULE --models $model_names --output $OUTPUT_DIR $BENCH_EXTRA"
    env $extra_env PYTHONPATH="$PROJECT_ROOT/_paper:${PYTHONPATH:-}" python -m "$BENCH_MODULE" --models $model_names --output "$OUTPUT_DIR" $BENCH_EXTRA
}

# 메인 루프
ts "============================================================"
ts "벤치마크 시작: GROUP=$GROUP MODE=$MODE GPU=$GPU_ID PORT=$PORT"
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
    eval "$vllm_cmd" > "$LOG_DIR/vllm_${MODE}_${alias}.log" 2>&1 &

    if ! wait_for_server "$PORT" 600; then
        ts "  [SKIP] $alias 서버 기동 실패"
        tail -50 "$LOG_DIR/vllm_${MODE}_${alias}.log" 2>/dev/null || true
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
