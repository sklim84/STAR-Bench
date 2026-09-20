#!/usr/bin/env bash
# Serve one registry configuration and run one benchmark column against it.
#
#   bash _experiments/scripts/run_benchmark.sh --config qwen35-27b-t --gpu 0,1 \
#        --mode single --tools-lang kr --out-root _experiments/runs
#
#   --config      serving configuration id (_experiments/scripts/runner/registry.py)
#   --gpu         CUDA devices for this server; the count must match the
#                 configuration's tensor-parallel size, on the chosen host profile
#   --mode        single | oracle | e2e
#   --tools-lang  kr | en   (no default: the old default was documented as Korean
#                 and was in fact the English platform schema, C2-015)
#   --query-lang  kr | en   (default kr; picks benchmarks/ or benchmarks_en/)
#   --host-profile 48g | 80g
#   --out-root    parent of the output directory; each run gets a fresh one
#
# Every configuration is served alone, one request at a time, from the pinned
# registry entry. The script stops with a non-zero status when the server does
# not come up: the old one printed "[SKIP] ... 서버 기동 실패" and still exited 0,
# so a row could be missing from a "complete" group (L5-017).

set -euo pipefail

CONFIG=""
GPU=""
MODE="single"
TOOLS_LANG=""
QUERY_LANG="kr"
HOST_PROFILE="48g"
OUT_ROOT=""
PORT="11434"
EXTRA=()
ALLOW_UNPINNED=""

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOG_DIR="$PROJECT_ROOT/_experiments/logs"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)        CONFIG="$2"; shift 2 ;;
        --gpu)           GPU="$2"; shift 2 ;;
        --mode)          MODE="$2"; shift 2 ;;
        --tools-lang)    TOOLS_LANG="$2"; shift 2 ;;
        --query-lang)    QUERY_LANG="$2"; shift 2 ;;
        --host-profile)  HOST_PROFILE="$2"; shift 2 ;;
        --out-root)      OUT_ROOT="$2"; shift 2 ;;
        --port)          PORT="$2"; shift 2 ;;
        --allow-unpinned-revision) ALLOW_UNPINNED="--allow-unpinned-revision"; shift ;;
        --)              shift; EXTRA=("$@"); break ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

for required in CONFIG GPU TOOLS_LANG OUT_ROOT; do
    if [[ -z "${!required}" ]]; then
        echo "--${required,,} is required" >&2
        exit 2
    fi
done
case "$TOOLS_LANG" in kr|en) ;; *) echo "--tools-lang must be kr or en" >&2; exit 2 ;; esac
case "$QUERY_LANG" in kr|en) ;; *) echo "--query-lang must be kr or en" >&2; exit 2 ;; esac

case "$MODE" in
    single)
        MODULE="_experiments.scripts.benchmark"
        [[ "$QUERY_LANG" == "en" ]] && CASES="$PROJECT_ROOT/benchmarks_en" \
                                    || CASES="$PROJECT_ROOT/benchmarks"
        MODE_ARGS=()
        ;;
    oracle|e2e)
        MODULE="_experiments.scripts.benchmark_multiturn"
        [[ "$QUERY_LANG" == "en" ]] && CASES="$PROJECT_ROOT/benchmarks_multiturn_en" \
                                    || CASES="$PROJECT_ROOT/benchmarks_multiturn"
        MODE_ARGS=(--setting "$MODE")
        ;;
    *) echo "--mode must be single, oracle or e2e" >&2; exit 2 ;;
esac

# The output directory names the column, so two columns can never land in one
# directory and a rerun of a column starts from an empty one.
OUT="$OUT_ROOT/${MODE}_${QUERY_LANG}q_${TOOLS_LANG}t/$CONFIG"
mkdir -p "$OUT" "$LOG_DIR"

ts() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }

SERVER_LOG="$LOG_DIR/serve_${CONFIG}_${MODE}_${QUERY_LANG}q_${TOOLS_LANG}t_$(date +%Y%m%dT%H%M%S).log"
SERVER_PID=""

cleanup() {
    if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
        ts "stopping the server (pid $SERVER_PID)"
        kill "$SERVER_PID" 2>/dev/null || true
        for _ in $(seq 1 12); do
            kill -0 "$SERVER_PID" 2>/dev/null || break
            sleep 5
        done
        kill -9 "$SERVER_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

ts "config=$CONFIG gpu=$GPU mode=$MODE tools=$TOOLS_LANG query=$QUERY_LANG profile=$HOST_PROFILE"
ts "out=$OUT"
ts "server log: $SERVER_LOG"

cd "$PROJECT_ROOT"
python -m _experiments.scripts.serve --config "$CONFIG" --gpu "$GPU" --port "$PORT" \
    --setting "$MODE" --host-profile "$HOST_PROFILE" --log "$SERVER_LOG" $ALLOW_UNPINNED &
SERVER_PID=$!

# serve.py exits non-zero when the server does not answer /health; wait for either.
for _ in $(seq 1 240); do
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        wait "$SERVER_PID" && rc=0 || rc=$?
        ts "the server exited before it was ready (rc=$rc)"
        tail -50 "$SERVER_LOG" 2>/dev/null || true
        exit "${rc:-1}"
    fi
    if python -c "
import sys, urllib.request
try:
    urllib.request.urlopen('http://127.0.0.1:$PORT/health', timeout=3)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        break
    fi
    sleep 5
done

ts "running the benchmark"
VLLM_BASE_URL="http://127.0.0.1:$PORT/v1" python -m "$MODULE" \
    --config "$CONFIG" --tools-lang "$TOOLS_LANG" --query-lang "$QUERY_LANG" \
    --cases-dir "$CASES" --out "$OUT" $ALLOW_UNPINNED "${MODE_ARGS[@]}" "${EXTRA[@]}"
rc=$?
ts "benchmark finished (rc=$rc)"
exit $rc
