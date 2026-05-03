#!/bin/bash
# ============================================================================
# kr_tools_en + en_tools_en 부분 재실험 chain (S1 GPU 0/1, RQ4 7 모델)
#
# 33 case_ids 부분 재실험 (--force-rerun + --case-ids-file)
# 두 GPU 병렬, single-GPU 모델 + TP=2 모델 순차
#
# 모델 7개 (RQ4 4-way ablation cohort):
#   Single-GPU:  Qwen3.5-27B (NT/T), Qwen3.6-27B, Gemma-4-31B, EXAONE-4.0-32B
#   TP=2:        Llama-3.3-70B, A.X-4.0
# ============================================================================

set -uo pipefail

PROJECT_ROOT="/home/work/kftc_sklim/KA-001-AML-Assistant"
RUNNER="$PROJECT_ROOT/_paper/_experiments/scripts/run_benchmark.sh"
CASE_KR="$PROJECT_ROOT/_paper/_experiments/analysis/case_ids_kr_singleturn.txt"
CASE_EN="$PROJECT_ROOT/_paper/_experiments/analysis/case_ids_en_singleturn.txt"
LOG_DIR="$PROJECT_ROOT/_paper/_experiments/logs"
mkdir -p "$LOG_DIR"

ts() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }

wait_pid() {
    local pid="$1" label="$2"
    [[ -z "$pid" ]] && return 0
    ts "  $label PID=$pid 대기..."
    while kill -0 "$pid" 2>/dev/null; do sleep 30; done
    ts "  $label PID=$pid 종료"
}

ts "============================================================"
ts "RQ4 tools_en 부분 재실험 chain 시작 (7 모델 × 2 모드)"
ts "============================================================"

# Phase 1: Single-GPU 모델 5종 KR mode (kr_tools_en)
ts "[Phase 1] Single-GPU kr_tools_en (S2_LARGE_L1 + L2 그룹)"
nohup bash "$RUNNER" \
    --gpu 0 --port 11434 --group S2_LARGE_L1 --mode kr --tools-lang en \
    --case-ids-file "$CASE_KR" --force-rerun \
    > "$LOG_DIR/s1g0_l1_kr_tools_en.log" 2>&1 &
P1A=$!
nohup bash "$RUNNER" \
    --gpu 1 --port 11435 --group S2_LARGE_L2 --mode kr --tools-lang en \
    --case-ids-file "$CASE_KR" --force-rerun \
    > "$LOG_DIR/s1g1_l2_kr_tools_en.log" 2>&1 &
P1B=$!
ts "  L1 kr_tools_en PID=$P1A, L2 kr_tools_en PID=$P1B"
wait_pid "$P1A" "L1-kr"
wait_pid "$P1B" "L2-kr"

# Phase 2: Single-GPU 모델 5종 EN mode (en_tools_en)
ts "[Phase 2] Single-GPU en_tools_en"
nohup bash "$RUNNER" \
    --gpu 0 --port 11434 --group S2_LARGE_L1 --mode en --tools-lang en \
    --case-ids-file "$CASE_EN" --force-rerun \
    > "$LOG_DIR/s1g0_l1_en_tools_en.log" 2>&1 &
P2A=$!
nohup bash "$RUNNER" \
    --gpu 1 --port 11435 --group S2_LARGE_L2 --mode en --tools-lang en \
    --case-ids-file "$CASE_EN" --force-rerun \
    > "$LOG_DIR/s1g1_l2_en_tools_en.log" 2>&1 &
P2B=$!
ts "  L1 en_tools_en PID=$P2A, L2 en_tools_en PID=$P2B"
wait_pid "$P2A" "L1-en"
wait_pid "$P2B" "L2-en"

# Phase 3: TP=2 Llama-3.3-70B (S2_TP2_A) — kr_tools_en + en_tools_en
ts "[Phase 3] TP=2 Llama-3.3-70B kr_tools_en + en_tools_en"
bash "$RUNNER" \
    --gpu 0,1 --port 11434 --group S2_TP2_A --mode kr --tools-lang en \
    --case-ids-file "$CASE_KR" --force-rerun \
    > "$LOG_DIR/s1tp2_llama70_kr_tools_en.log" 2>&1
bash "$RUNNER" \
    --gpu 0,1 --port 11434 --group S2_TP2_A --mode en --tools-lang en \
    --case-ids-file "$CASE_EN" --force-rerun \
    > "$LOG_DIR/s1tp2_llama70_en_tools_en.log" 2>&1

# Phase 4: TP=2 A.X-4.0 (S2_TP2_C) — kr_tools_en + en_tools_en
ts "[Phase 4] TP=2 A.X-4.0 kr_tools_en + en_tools_en"
bash "$RUNNER" \
    --gpu 0,1 --port 11434 --group S2_TP2_C --mode kr --tools-lang en \
    --case-ids-file "$CASE_KR" --force-rerun \
    > "$LOG_DIR/s1tp2_ax_kr_tools_en.log" 2>&1
bash "$RUNNER" \
    --gpu 0,1 --port 11434 --group S2_TP2_C --mode en --tools-lang en \
    --case-ids-file "$CASE_EN" --force-rerun \
    > "$LOG_DIR/s1tp2_ax_en_tools_en.log" 2>&1

ts "============================================================"
ts "RQ4 tools_en chain 완료"
ts "============================================================"
ts "후처리:"
ts "  1. merge_partial_results.py로 kr_tools_en + en_tools_en 머지"
ts "  2. 부수 모델 (Qwen3.6-35B-A3B, Mistral-Small-24B) eval 삭제 (RQ4 cohort 외)"
ts "  3. RQ4_query_tool_language_ablation.py 재실행 + paper §4.5 갱신"
