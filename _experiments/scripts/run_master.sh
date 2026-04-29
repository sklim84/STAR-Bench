#!/bin/bash
# ============================================================================
# 마스터 오케스트레이터 (MODELS.md 24-model + 서버 분담)
#
# 24 모델 × 3 차원 (KR/EN/MT) × 1 round
#   Server 1 (2× H100): 11 모델 (S1_A 6 + S1_B 5 단일-GPU)
#   Server 2 (6× H100): 13 모델 (TP=4 1 + TP=2 3 + Single-GPU Large 9)
#
# 사용법:
#   nohup bash run_master.sh --server 1 > master_s1.log 2>&1 &
#   nohup bash run_master.sh --server 2 > master_s2.log 2>&1 &
#   bash run_master.sh --server 1 --modes kr        # KR phase만
#   bash run_master.sh --server 2 --skip-tp4        # TP=4 (gpt-oss-120b) 스킵
#   bash run_master.sh --server 1 --skip-thinking   # think=True 변형 제외
# ============================================================================

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$PROJECT_ROOT/_paper/_experiments/logs"
RUN_SCRIPT="$SCRIPT_DIR/run_benchmark.sh"

SERVER=""
MODES="kr,en,mt"
SKIP_TP2=false
SKIP_TP4=false
SKIP_THINKING=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --server) SERVER="$2"; shift 2 ;;
        --modes) MODES="$2"; shift 2 ;;
        --skip-tp2) SKIP_TP2=true; shift ;;
        --skip-tp4) SKIP_TP4=true; shift ;;
        --skip-thinking) SKIP_THINKING=true; shift ;;
        *) echo "Unknown: $1"; exit 1 ;;
    esac
done

if [[ -z "$SERVER" ]]; then
    echo "ERROR: --server <1|2> 필수"
    echo "사용 예: bash $0 --server 1 --modes kr,en,mt"
    exit 1
fi

# benchmark.py가 think=True 변형을 제외하도록 환경변수 export
if $SKIP_THINKING; then
    export BENCH_SKIP_THINK=1
fi

mkdir -p "$LOG_DIR"

ts() { echo "$(date '+%Y-%m-%d %H:%M:%S') [MASTER-S$SERVER] $*" | tee -a "$LOG_DIR/master_s${SERVER}.log"; }

# ============================================================================
# Server 1 (2× H100) — S1_A (GPU 0) + S1_B (GPU 1) 병렬
# ============================================================================
run_phase_s1() {
    local mode=$1
    ts "════════════════════════════════════════════════════════════"
    ts "[S1] Phase: MODE=$mode"
    ts "════════════════════════════════════════════════════════════"

    ts "S1_A (GPU 0) + S1_B (GPU 1) 병렬 실행"
    nohup bash "$RUN_SCRIPT" --gpu 0 --port 11434 --group S1_A --mode "$mode" \
        > "$LOG_DIR/s1_${mode}_groupA.log" 2>&1 &
    PID_A=$!
    nohup bash "$RUN_SCRIPT" --gpu 1 --port 11435 --group S1_B --mode "$mode" \
        > "$LOG_DIR/s1_${mode}_groupB.log" 2>&1 &
    PID_B=$!
    ts "  PIDs: A=$PID_A, B=$PID_B"
    wait "$PID_A" || ts "  S1_A 종료 (rc=$?)"
    wait "$PID_B" || ts "  S1_B 종료 (rc=$?)"
    ts "[S1] Phase $mode 완료"
}

# ============================================================================
# Server 2 (6× H100) — Phase α (TP=4 + 2 single 병렬) → β (3 TP=2 병렬) → γ (3 lanes 병렬)
# ============================================================================
run_phase_s2() {
    local mode=$1
    ts "════════════════════════════════════════════════════════════"
    ts "[S2] Phase: MODE=$mode"
    ts "════════════════════════════════════════════════════════════"

    # ── α: TP=4 (gpt-oss-120b on GPU 0-3) + Single L1 (GPU 4) + Single L2 (GPU 5) 병렬 ──
    if ! $SKIP_TP4; then
        ts "[α] TP=4 (GPU 0-3 gpt-oss-120b) + L1 (GPU 4) + L2 (GPU 5) 병렬"
        nohup bash "$RUN_SCRIPT" --gpu 0,1,2,3 --port 11434 --group S2_TP4 --mode "$mode" \
            > "$LOG_DIR/s2_${mode}_tp4.log" 2>&1 &
        PID_TP4=$!
        nohup bash "$RUN_SCRIPT" --gpu 4 --port 11438 --group S2_LARGE_L1 --mode "$mode" \
            > "$LOG_DIR/s2_${mode}_L1.log" 2>&1 &
        PID_L1=$!
        nohup bash "$RUN_SCRIPT" --gpu 5 --port 11439 --group S2_LARGE_L2 --mode "$mode" \
            > "$LOG_DIR/s2_${mode}_L2.log" 2>&1 &
        PID_L2=$!
        ts "  PIDs: TP4=$PID_TP4, L1=$PID_L1, L2=$PID_L2"
        wait "$PID_TP4" || ts "  TP4 종료 (rc=$?)"
        wait "$PID_L1" || ts "  L1 종료 (rc=$?)"
        wait "$PID_L2" || ts "  L2 종료 (rc=$?)"
        ts "[α] 완료"
    else
        ts "[α] TP=4 스킵 (--skip-tp4) → L1+L2+L3 6 GPU 활용 모드로 진행"
        nohup bash "$RUN_SCRIPT" --gpu 0 --port 11434 --group S2_LARGE_L1 --mode "$mode" \
            > "$LOG_DIR/s2_${mode}_L1.log" 2>&1 &
        PID_L1=$!
        nohup bash "$RUN_SCRIPT" --gpu 1 --port 11435 --group S2_LARGE_L2 --mode "$mode" \
            > "$LOG_DIR/s2_${mode}_L2.log" 2>&1 &
        PID_L2=$!
        nohup bash "$RUN_SCRIPT" --gpu 2 --port 11436 --group S2_LARGE_L3 --mode "$mode" \
            > "$LOG_DIR/s2_${mode}_L3.log" 2>&1 &
        PID_L3=$!
        ts "  PIDs: L1=$PID_L1, L2=$PID_L2, L3=$PID_L3"
        wait "$PID_L1" || ts "  L1 종료 (rc=$?)"
        wait "$PID_L2" || ts "  L2 종료 (rc=$?)"
        wait "$PID_L3" || ts "  L3 종료 (rc=$?)"
        ts "[α-alt] 완료"
    fi

    # ── β: TP=2 3 pair 병렬 (GPU 0-1, 2-3, 4-5) ──
    if ! $SKIP_TP2; then
        ts "[β] TP=2 3 pair 병렬 (Llama-70B + xLAM-70B + A.X-4.0)"
        nohup bash "$RUN_SCRIPT" --gpu 0,1 --port 11434 --group S2_TP2_A --mode "$mode" \
            > "$LOG_DIR/s2_${mode}_tp2A.log" 2>&1 &
        PID_TP2_A=$!
        nohup bash "$RUN_SCRIPT" --gpu 2,3 --port 11436 --group S2_TP2_B --mode "$mode" \
            > "$LOG_DIR/s2_${mode}_tp2B.log" 2>&1 &
        PID_TP2_B=$!
        nohup bash "$RUN_SCRIPT" --gpu 4,5 --port 11438 --group S2_TP2_C --mode "$mode" \
            > "$LOG_DIR/s2_${mode}_tp2C.log" 2>&1 &
        PID_TP2_C=$!
        ts "  PIDs: TP2_A=$PID_TP2_A, TP2_B=$PID_TP2_B, TP2_C=$PID_TP2_C"
        wait "$PID_TP2_A" || ts "  TP2_A 종료 (rc=$?)"
        wait "$PID_TP2_B" || ts "  TP2_B 종료 (rc=$?)"
        wait "$PID_TP2_C" || ts "  TP2_C 종료 (rc=$?)"
        ts "[β] 완료"
    else
        ts "[β] TP=2 스킵 (--skip-tp2)"
    fi

    # ── γ: 남은 Single-GPU Large (α에서 안 돌은 그룹 처리, 남은 모델만) ──
    # α에서 SKIP_TP4=false 였으면 L1+L2 처리됨, L3만 남음
    # α에서 SKIP_TP4=true 였으면 L1+L2+L3 모두 처리됨
    if ! $SKIP_TP4; then
        ts "[γ] L3 처리 (3 lanes에 분산)"
        nohup bash "$RUN_SCRIPT" --gpu 0 --port 11434 --group S2_LARGE_L3 --mode "$mode" \
            > "$LOG_DIR/s2_${mode}_L3.log" 2>&1 &
        PID_L3=$!
        wait "$PID_L3" || ts "  L3 종료 (rc=$?)"
        ts "[γ] 완료"
    fi

    ts "[S2] Phase $mode 완료"
}

# 메인
ts "마스터 시작: SERVER=$SERVER MODES=$MODES SKIP_TP2=$SKIP_TP2 SKIP_TP4=$SKIP_TP4 SKIP_THINKING=$SKIP_THINKING"
START_TIME=$(date +%s)

IFS=',' read -ra MODE_LIST <<< "$MODES"
for mode in "${MODE_LIST[@]}"; do
    case "$mode" in
        kr|en|mt)
            if [[ "$SERVER" == "1" ]]; then
                run_phase_s1 "$mode"
            elif [[ "$SERVER" == "2" ]]; then
                run_phase_s2 "$mode"
            else
                ts "Unknown server: $SERVER (1 or 2)"
                exit 1
            fi
            ;;
        *)
            ts "Unknown mode: $mode (kr|en|mt)"
            ;;
    esac
done

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
ts "════════════════════════════════════════════════════════════"
ts "전체 완료. 소요 시간: $((ELAPSED/3600))시간 $((ELAPSED%3600/60))분"
ts "════════════════════════════════════════════════════════════"
