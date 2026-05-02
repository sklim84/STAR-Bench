#!/bin/bash
# ============================================================================
# S1 phase chain: KR singleton (이미 진행 중) → EN singleton → MT KR
#
# 현재 진행 중인 S1_A/S1_B (KR singleton) PID를 받아서, 종료 시점에
# EN singleton → MT KR을 자동으로 trigger한다.
#
# 사용법:
#   nohup bash run_chain_s1.sh <S1A_PID> <S1B_PID> > _paper/_experiments/logs/chain_s1.log 2>&1 &
#
# 동작:
#   1. S1A/S1B PID polling (이미 nohup 으로 떠있으므로 wait 불가, kill -0 polling)
#   2. KR 완료 → EN singleton 두 GPU 병렬 trigger → 두 새 PID polling
#   3. EN 완료 → MT KR 두 GPU 병렬 trigger → 두 새 PID polling
#   4. MT 완료 → 종료
# ============================================================================

set -uo pipefail

S1A_PID="${1:-}"
S1B_PID="${2:-}"

PROJECT_ROOT="/home/work/kftc_sklim/KA-001-AML-Assistant"
RUNNER="$PROJECT_ROOT/_paper/_experiments/scripts/run_benchmark.sh"
CASE_KR="$PROJECT_ROOT/_paper/_experiments/analysis/case_ids_kr_singleturn.txt"
CASE_EN="$PROJECT_ROOT/_paper/_experiments/analysis/case_ids_en_singleturn.txt"
LOG_DIR="$PROJECT_ROOT/_paper/_experiments/logs"
mkdir -p "$LOG_DIR"

ts() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }

wait_pid() {
    local pid="$1" label="$2"
    if [[ -z "$pid" ]]; then
        ts "  $label: PID 미지정, 즉시 진행"
        return 0
    fi
    ts "  $label PID=$pid 종료 대기..."
    while kill -0 "$pid" 2>/dev/null; do
        sleep 30
    done
    ts "  $label PID=$pid 종료 확인"
}

ts "============================================================"
ts "S1 chain 시작 — phases: KR(running) → EN → MT"
ts "S1A_PID=$S1A_PID  S1B_PID=$S1B_PID"
ts "============================================================"

# Phase 1: 이미 진행 중인 KR singleton 종료 대기
ts ""
ts "[Phase 1] KR singleton 부분 재실험 종료 대기"
wait_pid "$S1A_PID" "S1_A KR"
wait_pid "$S1B_PID" "S1_B KR"
ts "Phase 1 완료. EN phase trigger."

# Phase 2: EN singleton 부분 재실험 (병렬)
ts ""
ts "[Phase 2] EN singleton 부분 재실험 시작"

nohup bash "$RUNNER" \
    --gpu 0 --port 11434 --group S1_A --mode en \
    --case-ids-file "$CASE_EN" --force-rerun \
    > "$LOG_DIR/s1a_en_partial.log" 2>&1 &
EN_A_PID=$!
ts "  S1_A EN PID=$EN_A_PID"

nohup bash "$RUNNER" \
    --gpu 1 --port 11435 --group S1_B --mode en \
    --case-ids-file "$CASE_EN" --force-rerun \
    > "$LOG_DIR/s1b_en_partial.log" 2>&1 &
EN_B_PID=$!
ts "  S1_B EN PID=$EN_B_PID"

wait_pid "$EN_A_PID" "S1_A EN"
wait_pid "$EN_B_PID" "S1_B EN"
ts "Phase 2 완료. MT phase trigger."

# Phase 3: 멀티턴 KR (50 scenario 전체, --case-ids 미지원, --force-rerun으로 cache 우회)
ts ""
ts "[Phase 3] 멀티턴 KR 재실험 시작 (50 시나리오 전체, force-rerun)"

nohup bash "$RUNNER" \
    --gpu 0 --port 11434 --group S1_A --mode mt --force-rerun \
    > "$LOG_DIR/s1a_mt.log" 2>&1 &
MT_A_PID=$!
ts "  S1_A MT PID=$MT_A_PID"

nohup bash "$RUNNER" \
    --gpu 1 --port 11435 --group S1_B --mode mt --force-rerun \
    > "$LOG_DIR/s1b_mt.log" 2>&1 &
MT_B_PID=$!
ts "  S1_B MT PID=$MT_B_PID"

wait_pid "$MT_A_PID" "S1_A MT"
wait_pid "$MT_B_PID" "S1_B MT"
ts "Phase 3 완료. 모든 S1 재실험 종료."
ts "============================================================"
ts "S1 chain 완료"
ts "============================================================"
