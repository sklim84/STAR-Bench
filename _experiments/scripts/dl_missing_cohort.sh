#!/usr/bin/env bash
# tex 최종 코호트 미캐시 12개 순차 다운로드 (작은 것부터). 캐시=kftc_model/.cache.
set -uo pipefail
export HF_TOKEN HF_HUB_ENABLE_HXET=1
LOG=_experiments/logs/dl
ts(){ echo "[$(TZ=Asia/Seoul date '+%H:%M:%S')] $*"; }
REPOS=(
  meta-llama/Llama-3.2-3B-Instruct
  Salesforce/xLAM-2-3b-fc-r
  Qwen/Qwen3.5-4B
  microsoft/Phi-4-mini-instruct
  google/gemma-4-E4B-it
  skt/A.X-4.0-Light
  NousResearch/Hermes-3-Llama-3.1-8B
  Qwen/Qwen3.5-27B
  Qwen/Qwen3.6-35B-A3B
  skt/A.X-4.0
  meta-llama/Llama-3.3-70B-Instruct
  Salesforce/Llama-xLAM-2-70b-fc-r
)
for r in "${REPOS[@]}"; do
  safe=$(echo "$r" | tr '/' '_')
  ts "다운로드 시작: $r"
  hf download "$r" > "$LOG/${safe}.log" 2>&1 \
    && ts "완료: $r" || ts "실패: $r (로그 $LOG/${safe}.log)"
done
ts "전체 미캐시 코호트 다운로드 종료"
