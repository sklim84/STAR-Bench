#!/bin/bash
# ============================================================================
# S1 멀티턴 4 모델 (Gemma-4-31B + Kanana 3종) parser-fix 재실험 chain
#
# May 3 09:11-09:18 broken eval (h̄=0.085) 정정 재실행.
# Root cause: run_benchmark.sh의 parser 미스매치 (hermes 지정 → 실제 gemma4 /
# functionary_v3_llama_31 필요). 해당 그룹의 parser 정의는 fix됨.
#
# 실행: 두 GPU 병렬
#   GPU 0: Gemma-4-31B
#   GPU 1: Kanana-Instruct → Kanana-Think (NT/T)
# 사용법:
#   nohup bash run_chain_mt_fix_s1.sh > _paper/_experiments/logs/chain_mt_fix_s1.log 2>&1 &
# ============================================================================

set -uo pipefail

PROJECT_ROOT="/home/work/kftc_sklim/KA-001-AML-Assistant"
RUNNER="$PROJECT_ROOT/_paper/_experiments/scripts/run_benchmark.sh"
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
ts "S1 MT 4 모델 parser-fix 재실험 chain 시작"
ts "  Gemma-4-31B (parser=gemma4) on GPU 0"
ts "  Kanana 3종 (parser=functionary_v3_llama_31) on GPU 1"
ts "============================================================"

# GPU 0: Gemma-4-31B (single model)
nohup bash "$RUNNER" \
    --gpu 0 --port 11434 --group S1_MT_FIX_A --mode mt --force-rerun \
    > "$LOG_DIR/s1_mt_fix_gemma.log" 2>&1 &
PA=$!
ts "  S1_MT_FIX_A (Gemma) PID=$PA"

# GPU 1: Kanana-Instruct + Kanana-Think (sequential within group)
nohup bash "$RUNNER" \
    --gpu 1 --port 11435 --group S1_MT_FIX_B --mode mt --force-rerun \
    > "$LOG_DIR/s1_mt_fix_kanana.log" 2>&1 &
PB=$!
ts "  S1_MT_FIX_B (Kanana) PID=$PB"

wait_pid "$PA" "Gemma"
wait_pid "$PB" "Kanana"

ts "============================================================"
ts "S1 MT fix chain 완료"
ts "============================================================"
ts "후처리:"
ts "  1. 4 모델 multiturn_*.json 검증 (h̄ > 0.5 정상값 확인)"
ts "  2. results_mt comparison 재생성"
ts "  3. main.tex tab:overall + tab:full_models MT 4 모델 값 갱신 (‡ 표시 제거)"
ts "  4. 양 repo push"
