#!/usr/bin/env bash
# Runs every configuration a host can serve, one column at a time.
#
#   bash _experiments/scripts/run_master.sh --host-gpus 4 \
#        --columns single,oracle,e2e --tools-lang kr \
#        --out-root _experiments/runs
#
#   --host-gpus     cards on this host; a configuration that needs more is listed
#                   as not runnable here and does not silently disappear
#   --host-profile  48g | 80g   (which tensor-parallel plan to use)
#   --columns       single, oracle, e2e (comma separated)
#   --tools-lang    kr | en
#   --query-lang    kr | en
#   --only          comma-separated configuration ids, instead of all of them
#   --out-root      parent directory for the fresh output directories
#   --agreement     also run the batching-agreement measurement from run_plan.json
#   --agreement-only  run only that measurement
#
# The batching-agreement run is what makes the concurrency deviation from D07
# measurable: one small configuration on the full single-turn benchmark twice at
# the registry default and once at 1, into three separate output directories, so
# the agreement rate between two batched runs and between batched and serial can
# be computed before any headline number is quoted.
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
AGREEMENT=""
AGREEMENT_ONLY=""
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
        --agreement)     AGREEMENT="1"; shift ;;
        --agreement-only) AGREEMENT="1"; AGREEMENT_ONLY="1"; shift ;;
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

if [[ -z "$AGREEMENT_ONLY" ]]; then
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
fi

# --- batching agreement (the D07 concurrency deviation) ----------------------
if [[ -n "$AGREEMENT" ]]; then
    mapfile -t AGREE < <(python - <<'PYEOF'
import json, pathlib
plan = json.loads(pathlib.Path("_experiments/scripts/preflight/run_plan.json").read_text(encoding="utf-8"))
block = plan.get("concurrency") or {}
run = block.get("agreement_run") or {}
for entry in run.get("runs", []):
    print("\t".join([str(run.get("config_id")), str(run.get("column")),
                     str(run.get("tools_lang")), str(run.get("query_lang")),
                     str(entry.get("label")), str(entry.get("concurrency"))]))
PYEOF
)
    if [[ ${#AGREE[@]} -eq 0 ]]; then
        ts "run_plan.json holds no batching-agreement run"
        exit 2
    fi
    for line in "${AGREE[@]}"; do
        IFS=$'\t' read -r acfg acol atl aql alabel aconc <<< "$line"
        agpu=""
        for pline in "${PLAN[@]}"; do
            IFS=$'\t' read -r pcfg ptp pgpu preason <<< "$pline"
            [[ "$pcfg" == "$acfg" ]] && agpu="$pgpu"
        done
        if [[ -z "$agpu" || "$agpu" == "-" ]]; then
            SKIPPED+=("agreement/$acfg: not runnable on this host")
            continue
        fi
        ts "=== batching agreement / $acfg / $alabel (concurrency $aconc) ==="
        if bash "$RUN_ONE" --config "$acfg" --gpu "$agpu" --mode "$acol" \
                --tools-lang "$atl" --query-lang "$aql" \
                --host-profile "$HOST_PROFILE" --port "$PORT" \
                --out-root "$OUT_ROOT/batching_agreement/$alabel" \
                -- --concurrency "$aconc" "${EXTRA[@]}"; then
            DONE+=("agreement/$acfg/$alabel")
        else
            FAILED+=("agreement/$acfg/$alabel (rc=$?)")
            ts "FAILED: agreement/$acfg/$alabel"
        fi
    done
fi

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
