#!/bin/bash
# or_extra 가 잉여인 en_tools_kr 팔로 넘어가면 즉시 세운다.
# 주 표는 한국어 질의만 쓰므로 추가 6설정의 영어 축은 필요 없다.
# 패턴 매칭으로 프로세스를 찾지 않는다. 감시자 자신이 그 패턴에 걸려 스스로를 종료시키기 때문이다.
set -u
# The driver's log and pid file live wherever the driver was started from; both
# come from the environment so no machine path is baked in.
RUN_DIR="${OR_RUN_DIR:-${TMPDIR:-/tmp}}"
LOG="${OR_LOG:-$RUN_DIR/or_extra.log}"
PIDF="${OR_PIDFILE:-$RUN_DIR/or_extra.pid}"
DEADLINE=$(( $(date +%s) + 8*3600 ))

ts(){ echo "[$(date +%H:%M:%S)] $*"; }
ts "감시 시작 — 조건: '팔 en_tools_kr' 출현"

while true; do
  DRV=$(cat "$PIDF" 2>/dev/null || echo "")
  if [ -z "$DRV" ] || ! ps -p "$DRV" >/dev/null 2>&1; then
    ts "드라이버가 이미 종료됨 — 감시 종료"; exit 0
  fi
  if grep -q '팔 en_tools_kr' "$LOG" 2>/dev/null; then
    ts "잉여 팔 진입 감지 — 종료 절차 시작"
    KIDS=$(pgrep -P "$DRV" 2>/dev/null || true)
    ts "  드라이버 $DRV · 자식 [$KIDS]"
    kill "$DRV" 2>/dev/null
    for k in $KIDS; do kill "$k" 2>/dev/null; done
    sleep 5
    for k in $KIDS; do ps -p "$k" >/dev/null 2>&1 && kill -9 "$k" 2>/dev/null; done
    ps -p "$DRV" >/dev/null 2>&1 && kill -9 "$DRV" 2>/dev/null
    sleep 2
    if ps -p "$DRV" >/dev/null 2>&1; then ts "  !! 드라이버가 남아 있음"; else ts "  종료 확인"; fi
    ts "KR 팔까지의 결과는 체크포인트에 그대로 남아 있다"
    exit 0
  fi
  [ "$(date +%s)" -gt "$DEADLINE" ] && { ts "8시간 초과 — 감시만 종료(실행은 그대로)"; exit 0; }
  sleep 60
done
