#!/bin/bash
# ============================================================================
# 누락 케이스 보충 (sequential, GPU 0, BENCH_CONCURRENCY 적용)
#
# 원인: 본 master 실행에서 _CONN_ERROR_THRESHOLD 도달로 _server_dead 트리거
#       → 일부 모델의 나머지 케이스 스킵 → eval JSON total_cases < 1258
#
# 동작: KR과 EN 각 mode별로
#  1) 해당 모델의 기존 eval JSON 삭제 (--resume 모델 스킵 회피)
#  2) checkpoint 보존 (이미 완료된 케이스 set 유지)
#  3) BENCH_CONCURRENCY=4로 vLLM에 동시 요청 → 누락 케이스만 처리
#  4) 새 eval JSON 생성 (1258 cases, KR/EN 모두)
#
# DragonLLM/Llama-Open-Finance-8B는 parallel TC 미지원 (모델 한계)이라 제외.
#
# 사용:
#   bash recovery_missing.sh                # KR + EN 모두 처리
#   bash recovery_missing.sh kr             # KR만
#   bash recovery_missing.sh en             # EN만
# ============================================================================

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$PROJECT_ROOT/_paper/_experiments/logs"
PORT=11437
GPU=0
CONCURRENCY="${BENCH_CONCURRENCY:-4}"

MODES="${1:-kr,en}"

# .env에서 HF_TOKEN 로드
HF_TOKEN_VAL=""
if [ -f "$PROJECT_ROOT/.env" ]; then
    HF_TOKEN_VAL=$(grep "^HF_TOKEN" "$PROJECT_ROOT/.env" | sed 's/^[^:=]*[: ]*=//' | tr -d ' "'"'"'')
fi

# flash_attn 스텁 (run_benchmark.sh 패턴)
FLASH_ATTN_STUB="/tmp/fake_flash_attn"

# 보충 대상 (alias|hf_model|parser|extra_args)
RECOVERY_MODELS=(
    "llama-3.2-3b|meta-llama/Llama-3.2-3B-Instruct|llama3_json|"
    "ministral-3b|mistralai/Ministral-3-3B-Instruct-2512|mistral|"
    "qwen35-4b|Qwen/Qwen3.5-4B|qwen3_coder|--reasoning-parser qwen3"
    "exaone-1.2b|LGAI-EXAONE/EXAONE-4.0-1.2B|hermes|--trust-remote-code"
)

ts() { echo "$(date '+%Y-%m-%d %H:%M:%S') [RECOVERY] $*"; }

stop_server() {
    pkill -f "vllm.entrypoints.openai.api_server.*--port $PORT" 2>/dev/null || true
    sleep 5
    pkill -9 -f "vllm.entrypoints.openai.api_server.*--port $PORT" 2>/dev/null || true
    sleep 3
}

wait_for_server() {
    local max_wait=${1:-300}
    for ((i=1; i<=max_wait/5; i++)); do
        if python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:$PORT/v1/models', timeout=3)" 2>/dev/null; then
            return 0
        fi
        sleep 5
    done
    return 1
}

run_one() {
    local mode=$1
    local alias=$2
    local hf_model=$3
    local parser=$4
    local extra_args=$5

    local output_dir cases_arg sanitized
    case "$mode" in
        kr) output_dir="$PROJECT_ROOT/_paper/_experiments/results_kr"; cases_arg="" ;;
        en) output_dir="$PROJECT_ROOT/_paper/_experiments/results_en"; cases_arg="--cases-dir $PROJECT_ROOT/_paper/benchmarks_en" ;;
        *) ts "Unknown mode: $mode"; return 1 ;;
    esac

    sanitized=$(echo "$hf_model" | tr '/.:' '___')

    ts "════════════════════════════════════════════════════════════"
    ts "[$mode] $alias ($hf_model)"
    ts "════════════════════════════════════════════════════════════"

    # eval JSON 삭제 (think+nothink 변형 모두) — checkpoint은 보존
    local removed=0
    for f in "$output_dir"/eval/eval_${sanitized}_*.json "$output_dir"/eval/eval_${sanitized}__*.json; do
        if [ -f "$f" ]; then
            rm -f "$f"
            ts "  eval 삭제: $(basename $f)"
            removed=$((removed+1))
        fi
    done
    [ "$removed" -eq 0 ] && ts "  (기존 eval 없음)"

    # vLLM 시작
    stop_server
    ts "  vLLM 시작 (CUDA=$GPU port=$PORT)"
    eval "CUDA_VISIBLE_DEVICES=$GPU PYTHONPATH=$FLASH_ATTN_STUB:\${PYTHONPATH:-} HF_TOKEN=$HF_TOKEN_VAL python -m vllm.entrypoints.openai.api_server --model $hf_model --port $PORT --max-model-len 32768 --gpu-memory-utilization 0.95 --tool-call-parser $parser --enable-auto-tool-choice $extra_args" \
        > "$LOG_DIR/recovery_vllm_${mode}_${alias}.log" 2>&1 &

    if ! wait_for_server 600; then
        ts "  [SKIP] vLLM 부팅 실패"
        tail -30 "$LOG_DIR/recovery_vllm_${mode}_${alias}.log" 2>/dev/null || true
        stop_server
        return 1
    fi
    ts "  vLLM 준비 완료"

    # benchmark 실행 (--checkpoint --resume + BENCH_CONCURRENCY)
    ts "  benchmark 실행 (BENCH_CONCURRENCY=$CONCURRENCY)"
    BENCH_CONCURRENCY=$CONCURRENCY \
    PYTHONPATH="$PROJECT_ROOT/_paper:${PYTHONPATH:-}" \
    VLLM_BASE_URL="http://localhost:$PORT/v1" \
    python -m _experiments.scripts.benchmark \
        --models "$hf_model" \
        --output "$output_dir" \
        $cases_arg \
        --checkpoint --resume \
        > "$LOG_DIR/recovery_bench_${mode}_${alias}.log" 2>&1 || true

    stop_server
    ts "  완료"
}

ts "재실험 시작: MODES=$MODES, CONCURRENCY=$CONCURRENCY"
START_TS=$(date +%s)

IFS=',' read -ra MODE_LIST <<< "$MODES"
for mode in "${MODE_LIST[@]}"; do
    for entry in "${RECOVERY_MODELS[@]}"; do
        IFS='|' read -r alias hf_model parser extra_args <<< "$entry"
        run_one "$mode" "$alias" "$hf_model" "$parser" "$extra_args"
    done
done

END_TS=$(date +%s)
ELAPSED=$((END_TS - START_TS))
ts "════════════════════════════════════════════════════════════"
ts "전체 완료. 소요 시간: $((ELAPSED/3600))시간 $((ELAPSED%3600/60))분"
ts "════════════════════════════════════════════════════════════"
