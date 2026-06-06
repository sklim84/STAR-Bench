#!/usr/bin/env bash
# Oracle vs. real end-to-end multi-turn STR experiment (3 cohort models, PARALLEL).
#
# Each model runs on its OWN idle GPU + port concurrently. For each model:
#   serve via vLLM, run benchmark_multiturn under BOTH settings on that same serving
#     oracle -> _experiments/results_mt_oracle3/   (ground-truth call+result injected)
#     real   -> _experiments/results_mt_real/      (model's OWN calls run on HOFINET)
#   then stop the server (kill the launched process tree, wait for GPU release).
#
# real mode needs star-bench-web (src.features.agent._execute_tool) + HOFINET data,
# so PYTHONPATH bundles star-bench, star-bench-web, and the ambient ~/.local site
# (overriding PYTHONPATH would drop ~/.local where vllm/openai/streamlit live).
# Caches (HF_HOME, VLLM_CACHE_ROOT, ...) come from the ambient env -> kftc_model/.cache.
#
# Per-model output files (multiturn_<model>.json) and checkpoints never collide, so
# concurrent writes to the two shared output dirs are safe.
#
# Usage:  bash _experiments/scripts/run_oracle_vs_real.sh
set -uo pipefail

SB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"          # star-bench root
WS="$(cd "$SB/.." && pwd)"                                         # umbrella root
WEB="$WS/star-bench-web"
PYPATH="$SB:$WEB:${PYTHONPATH:-}"                                  # APPEND (never replace)

ORACLE_OUT="_experiments/results_mt_oracle/"
REAL_OUT="_experiments/results_mt_real/"
LOG_DIR="$SB/_experiments/logs"; mkdir -p "$LOG_DIR"

export NUMEXPR_MAX_THREADS=64

# HF token (gated models)
HF_TOKEN="${HF_TOKEN:-}"
if [ -z "$HF_TOKEN" ] && [ -f "$SB/.env" ]; then
    HF_TOKEN=$(grep "^HF_TOKEN" "$SB/.env" | sed 's/^[^=]*=//' | tr -d ' "'"'"'')
fi
export HF_TOKEN

# flash_attn stub (Gemma/Kanana paths import it lazily)
FLASH_ATTN_STUB="/tmp/fake_flash_attn"
if [ ! -f "$FLASH_ATTN_STUB/flash_attn/__init__.py" ]; then
    mkdir -p "$FLASH_ATTN_STUB/flash_attn/ops/triton"
    echo "pass" > "$FLASH_ATTN_STUB/flash_attn/__init__.py"
    printf 'def flash_attn_varlen_func(*a,**k):\n raise NotImplementedError\n' \
        > "$FLASH_ATTN_STUB/flash_attn/flash_attn_interface.py"
    echo "pass" > "$FLASH_ATTN_STUB/flash_attn/ops/__init__.py"
    echo "pass" > "$FLASH_ATTN_STUB/flash_attn/ops/triton/__init__.py"
    printf 'def apply_rotary(*a,**k):\n raise NotImplementedError\n' \
        > "$FLASH_ATTN_STUB/flash_attn/ops/triton/rotary.py"
fi

KANANA_PARSER_PLUGIN="$SB/_experiments/scripts/kanana_tool_calls/kanana_tool_calls/functionary_kanana_tool_parser.py"
KANANA_CHAT_TEMPLATE="$SB/_experiments/scripts/kanana_tool_calls/kanana_tool_calls/lmalign_v1.jinja"

ts(){ echo "[$(TZ=Asia/Seoul date '+%H:%M:%S')] [$1] ${*:2}"; }

# Recursively kill a PID and all descendants. vLLM's VLLM::EngineCore child survives a
# port/parent kill and holds the GPU; killing the launched tree (and only that tree)
# reclaims the GPU without touching other users' engines on other GPUs.
kill_tree(){ local pid=$1 c; for c in $(pgrep -P "$pid" 2>/dev/null); do kill_tree "$c"; done; kill -9 "$pid" 2>/dev/null||true; }

wait_gpu_free(){ local tag=$1 g=$2 i used;
    for ((i=1;i<=60;i++)); do
        used=$(nvidia-smi -i "$g" --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null|tr -d ' ')
        [ -n "$used" ] && [ "$used" -lt 5000 ] && { ts "$tag" "GPU$g 해제됨 (${used}MiB)"; return 0; }
        sleep 3
    done; ts "$tag" "[WARN] GPU$g 메모리 미해제"; return 0; }

# run_one: serve one model on (gpu, port), run oracle+real, stop. Self-contained (locals).
run_one(){
    local alias=$1 hf=$2 parser=$3 kanana=$4 gpu=$5 port=$6 extra=${7:-}
    local vllm_log="$LOG_DIR/vllm_ovr_${alias}.log"
    local server_pid="" kopts=""
    [ "$kanana" = "1" ] && kopts="--tool-parser-plugin $KANANA_PARSER_PLUGIN --chat-template $KANANA_CHAT_TEMPLATE"

    # clear any stale listener on this port
    lsof -ti:"$port" 2>/dev/null | xargs -r kill -9 2>/dev/null || true; sleep 1

    ts "$alias" "vLLM 시작 (GPU=$gpu PORT=$port) → $vllm_log"
    CUDA_VISIBLE_DEVICES="$gpu" PYTHONPATH="$FLASH_ATTN_STUB:${PYTHONPATH:-}" HF_TOKEN="$HF_TOKEN" \
        python -m vllm.entrypoints.openai.api_server \
        --model "$hf" --port "$port" --max-model-len 32768 \
        --gpu-memory-utilization 0.95 --tool-call-parser "$parser" \
        --enable-auto-tool-choice $kopts $extra > "$vllm_log" 2>&1 &
    server_pid=$!

    # wait for health (max 900s)
    local up=0 i
    for ((i=1;i<=180;i++)); do
        if python3 -c "import urllib.request;urllib.request.urlopen('http://localhost:$port/health',timeout=3)" 2>/dev/null; then up=1; break; fi
        sleep 5
    done
    if [ "$up" != "1" ]; then
        ts "$alias" "[SKIP] 서버 기동 실패"; tail -40 "$vllm_log"
        kill_tree "$server_pid"; wait_gpu_free "$alias" "$gpu"; return 1
    fi
    ts "$alias" "서버 준비 완료"

    local setting out
    for setting in oracle real; do
        out="$ORACLE_OUT"; [ "$setting" = "real" ] && out="$REAL_OUT"
        ts "$alias" "── [$setting] benchmark_multiturn → $out"
        VLLM_BASE_URL="http://localhost:$port/v1" NUMEXPR_MAX_THREADS=64 \
            PYTHONPATH="$PYPATH" HF_TOKEN="$HF_TOKEN" \
            python -m _experiments.scripts.benchmark_multiturn \
            --models "$hf" --setting "$setting" --output "$out" \
            --checkpoint --resume \
            > "$LOG_DIR/mt_${setting}_${alias}.log" 2>&1 \
            && ts "$alias" "── [$setting] 완료" \
            || { ts "$alias" "── [$setting] 실패"; tail -25 "$LOG_DIR/mt_${setting}_${alias}.log"; }
    done

    kill_tree "$server_pid"
    lsof -ti:"$port" 2>/dev/null | xargs -r kill -9 2>/dev/null || true
    wait_gpu_free "$alias" "$gpu"
    ts "$alias" "완료 (서버 종료)"
}

# alias | hf_model | parser | kanana(0/1) | gpu | port  — one idle GPU each, run concurrently
MODELS=(
    "qwen36-27b|Qwen/Qwen3.6-27B|qwen3_xml|0|4|11441|"
    "xlam-70b|Salesforce/Llama-xLAM-2-70b-fc-r|xlam|0|7,2|11442|--tensor-parallel-size 2 --enforce-eager"
)

ts MAIN "============================================================"
ts MAIN "Oracle-vs-Real LAST (Qwen3.6-27B GPU4 / xLAM-2-70B TP=2 GPU7,2)"
ts MAIN "  oracle -> $ORACLE_OUT   real -> $REAL_OUT"
ts MAIN "  PYTHONPATH=$PYPATH"
ts MAIN "============================================================"

cd "$SB"
pids=()
for spec in "${MODELS[@]}"; do
    IFS='|' read -r alias hf parser kanana gpu port extra <<< "$spec"
    run_one "$alias" "$hf" "$parser" "$kanana" "$gpu" "$port" "$extra" &
    pids+=($!)
    ts MAIN "launched $alias on GPU $gpu / port $port (pid $!)"
    sleep 3   # stagger launches slightly
done

ts MAIN "3개 모델 병렬 실행 중 — 완료 대기..."
fail=0
for pid in "${pids[@]}"; do wait "$pid" || fail=1; done

ts MAIN ""
ts MAIN "============================================================"
ts MAIN "전체 완료 (fail=$fail). 분석:"
ts MAIN "  PYTHONPATH=$SB python _experiments/scripts/RQ_oracle_vs_real.py \\"
ts MAIN "      --oracle ${ORACLE_OUT}eval --real ${REAL_OUT}eval"
ts MAIN "  PYTHONPATH=$SB python _experiments/scripts/RQ_str_generation_quality.py"
ts MAIN "============================================================"
