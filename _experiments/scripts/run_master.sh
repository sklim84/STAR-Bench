#!/usr/bin/env bash
# Runs every configuration a host can serve, one column at a time.
#
#   bash _experiments/scripts/run_master.sh --host-gpus 4 \
#        --columns single,oracle,e2e --tools-lang kr \
#        --out-root _experiments/results_2026rerun
#
#   --host-gpus     cards on this host; a configuration that needs more is listed
#                   as not runnable here and does not silently disappear
#   --host-profile  48g | 80g   (which tensor-parallel plan to use)
#   --columns       single, oracle, e2e (comma separated)
#   --tools-lang    kr | en
#   --query-lang    kr | en
#   --only          comma-separated configuration ids, instead of all of them
#   --out-root      parent directory for the fresh output directories
#
# Every job runs alone on the cards the plan assigns. A job that fails is
# reported at the end and the script exits non-zero; the old orchestrator
# skipped a model whose server did not start and still said "전체 완료 rc=0"
# (L5-017).

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_ONE="$SCRIPT_DIR/run_benchmark.sh"

HOST_GPUS=""
HOST_PROFILE="48g"
COLUMNS="single"
TOOLS_LANG=""
QUERY_LANG="kr"
ONLY=""
OUT_ROOT=""
PORT="11434"
EXTRA=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host-gpus)     HOST_GPUS="$2"; shift 2 ;;
        --host-profile)  HOST_PROFILE="$2"; shift 2 ;;
        --columns)       COLUMNS="$2"; shift 2 ;;
        --tools-lang)    TOOLS_LANG="$2"; shift 2 ;;
        --query-lang)    QUERY_LANG="$2"; shift 2 ;;
        --only)          ONLY="$2"; shift 2 ;;
        --out-root)      OUT_ROOT="$2"; shift 2 ;;
        --port)          PORT="$2"; shift 2 ;;
        --)              shift; EXTRA=("$@"); break ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

for required in HOST_GPUS TOOLS_LANG OUT_ROOT; do
    if [[ -z "${!required}" ]]; then
        echo "--${required,,} is required" >&2
        exit 2
    fi
done

cd "$PROJECT_ROOT"

ts() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }

mapfile -t PLAN < <(python -m _experiments.scripts.runner.plan \
    --host-gpus "$HOST_GPUS" --host-profile "$HOST_PROFILE")

declare -a SKIPPED=()
declare -a FAILED=()
declare -a DONE=()

for column in ${COLUMNS//,/ }; do
    for line in "${PLAN[@]}"; do
        IFS=$'\t' read -r config tp gpu reason <<< "$line"
        if [[ -n "$ONLY" ]] && [[ ",$ONLY," != *",$config,"* ]]; then
            continue
        fi
        if [[ "$gpu" == "-" ]]; then
            SKIPPED+=("$column/$config: $reason")
            continue
        fi
        ts "=== $column / $config (tp=$tp, gpu=$gpu) ==="
        if bash "$RUN_ONE" --config "$config" --gpu "$gpu" --mode "$column" \
                --tools-lang "$TOOLS_LANG" --query-lang "$QUERY_LANG" \
                --host-profile "$HOST_PROFILE" --out-root "$OUT_ROOT" --port "$PORT" \
                -- "${EXTRA[@]}"; then
            DONE+=("$column/$config")
        else
            FAILED+=("$column/$config (rc=$?)")
            ts "FAILED: $column/$config"
        fi
    done
done

echo
ts "finished: ${#DONE[@]} run(s)"
if [[ ${#SKIPPED[@]} -gt 0 ]]; then
    ts "not runnable on this host (${#SKIPPED[@]}):"
    printf '  %s\n' "${SKIPPED[@]}"
fi
if [[ ${#FAILED[@]} -gt 0 ]]; then
    ts "failed (${#FAILED[@]}):"
    printf '  %s\n' "${FAILED[@]}"
    exit 1
fi
exit 0
