#!/bin/bash
# ============================================================================
# Round 1 마스터 오케스트레이터 (HOFINET 정정 후)
#
# 44개 모델 × 3 차원(KR single_turn, EN single_turn, multi-turn STR) × 1 round
# 양 GPU 병렬 + TP=2 순차 실행
#
# 사용법:
#   nohup bash run_round1_master.sh > round1_master.log 2>&1 &
#   bash run_round1_master.sh --modes kr,en,mt              # 기본
#   bash run_round1_master.sh --modes kr                    # KR만
#   bash run_round1_master.sh --skip-tp2                    # TP=2 단계 스킵 (테스트용)
# ============================================================================

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$PROJECT_ROOT/_paper/_experiments/logs"
RUN_SCRIPT="$SCRIPT_DIR/run_round1.sh"

MODES="kr,en,mt"
SKIP_TP2=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --modes) MODES="$2"; shift 2 ;;
        --skip-tp2) SKIP_TP2=true; shift ;;
        *) echo "Unknown: $1"; exit 1 ;;
    esac
done

mkdir -p "$LOG_DIR"

ts() { echo "$(date '+%Y-%m-%d %H:%M:%S') [MASTER] $*" | tee -a "$LOG_DIR/round1_master.log"; }

run_phase() {
    local mode=$1
    ts "════════════════════════════════════════════════════════════"
    ts "Phase: MODE=$mode"
    ts "════════════════════════════════════════════════════════════"

    # ── 1) Group A (GPU 0) + Group B (GPU 1) 병렬 ──
    ts "Group A (GPU 0) + Group B (GPU 1) 병렬 실행"
    nohup bash "$RUN_SCRIPT" --gpu 0 --port 11434 --group A --mode "$mode" \
        > "$LOG_DIR/round1_${mode}_groupA.log" 2>&1 &
    PID_A=$!
    nohup bash "$RUN_SCRIPT" --gpu 1 --port 11435 --group B --mode "$mode" \
        > "$LOG_DIR/round1_${mode}_groupB.log" 2>&1 &
    PID_B=$!
    ts "  PIDs: A=$PID_A, B=$PID_B"
    wait "$PID_A" || ts "  Group A 종료 (rc=$?)"
    wait "$PID_B" || ts "  Group B 종료 (rc=$?)"
    ts "Group A+B 완료"

    # ── 2) Group C (medium 20-32B) 분할: 절반 GPU 0, 절반 GPU 1 ──
    # GROUP_C 10 entries → 5+5 split via custom invocation
    # run_round1.sh는 GROUP 단위로만 실행하므로 임시 wrapper로 분할
    ts "Group C 분할 실행: GPU 0 절반 (C1) + GPU 1 절반 (C2)"
    nohup bash "$RUN_SCRIPT" --gpu 0 --port 11434 --group C1 --mode "$mode" \
        > "$LOG_DIR/round1_${mode}_groupC1.log" 2>&1 &
    PID_C1=$!
    nohup bash "$RUN_SCRIPT" --gpu 1 --port 11435 --group C2 --mode "$mode" \
        > "$LOG_DIR/round1_${mode}_groupC2.log" 2>&1 &
    PID_C2=$!
    ts "  PIDs: C1=$PID_C1, C2=$PID_C2"
    wait "$PID_C1" || ts "  Group C1 종료 (rc=$?)"
    wait "$PID_C2" || ts "  Group C2 종료 (rc=$?)"
    ts "Group C1+C2 완료"

    # ── 3) Group TP2 (70B+, 양 GPU 사용, 순차) ──
    if ! $SKIP_TP2; then
        ts "Group TP2 (70B+ 순차 실행, 양 GPU 사용)"
        bash "$RUN_SCRIPT" --gpu 0,1 --port 11434 --group TP2 --mode "$mode" \
            > "$LOG_DIR/round1_${mode}_groupTP2.log" 2>&1
        ts "Group TP2 완료"
    else
        ts "Group TP2 스킵 (--skip-tp2)"
    fi

    ts "Phase $mode 완료"
}

# 메인
ts "Round 1 마스터 시작: MODES=$MODES SKIP_TP2=$SKIP_TP2"
START_TIME=$(date +%s)

IFS=',' read -ra MODE_LIST <<< "$MODES"
for mode in "${MODE_LIST[@]}"; do
    case "$mode" in
        kr|en|mt)
            run_phase "$mode"
            ;;
        *)
            ts "Unknown mode: $mode (kr|en|mt)"
            ;;
    esac
done

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
ts "════════════════════════════════════════════════════════════"
ts "Round 1 전체 완료. 소요 시간: $((ELAPSED/3600))시간 $((ELAPSED%3600/60))분"
ts "════════════════════════════════════════════════════════════"
