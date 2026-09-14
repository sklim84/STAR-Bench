#!/bin/bash
# 남은 모델을 3개 워커로 병렬 다운로드한다. 순차로 받으면 큰 모델 하나에 20~50분이 걸려
# 그동안 GPU 워커가 굶는다. 회선(45MB/s)은 나눠 쓰지만 작은 모델이 먼저 도착해 공급이 끊기지 않는다.
# 이미 완비된 모델은 건너뛴다(snapshot_download 는 .incomplete 를 이어받는다).
R=/home/mlp/hgyoo/bubble/codex/star-bench
export HF_HOME=$R/hf_cache
V=$R/.venv312/bin/python
CLAIM=$R/.dl_claims; mkdir -p $CLAIM
log(){ echo "[$(date +%H:%M:%S)] $*"; }

# DragonLLM(→OVHaiLLM) 2종과 meta-llama 2종은 gated 라 토큰이 필요하다.
# 토큰 파일은 이 스크립트가 끝나면 정상·비정상 종료 어느 쪽이든 파기한다.
TF=$R/.hf_token
shred_token(){ [ -f "$TF" ] && { shred -u -z "$TF" 2>/dev/null || rm -f "$TF"; log "토큰 파기됨"; }; }
trap shred_token EXIT INT TERM
[ -f "$TF" ] && export HF_TOKEN="$(cat $TF)" && log "토큰 로드 (${#HF_TOKEN}자)"

MODELS=(
  openai/gpt-oss-20b
  skt/A.X-4.0-Light
  NousResearch/Hermes-3-Llama-3.1-8B
  DragonLLM/Llama-Open-Finance-8B
  DragonLLM/Qwen-Open-Finance-R-8B
  mistralai/Mistral-Small-3.2-24B-Instruct-2506
  Qwen/Qwen3.5-27B
  Qwen/Qwen3.6-27B
  LGAI-EXAONE/EXAONE-4.0-32B
  openai/gpt-oss-120b
  Qwen/Qwen3.6-35B-A3B
  kakaocorp/kanana-2-30b-a3b-instruct
  kakaocorp/kanana-2-30b-a3b-thinking-2601
  Salesforce/Llama-xLAM-2-70b-fc-r
  skt/A.X-4.0
)

complete(){ local hf=$1 d="$HF_HOME/hub/models--${hf//\//--}"
  [ -d "$d" ] || return 1
  ls "$d"/snapshots/*/config.json >/dev/null 2>&1 || return 1
  ls "$d"/snapshots/*/*.safetensors >/dev/null 2>&1 || return 1
  ls "$d"/blobs/*.incomplete >/dev/null 2>&1 && return 1
  return 0; }

worker(){
  local w=$1 m safe
  for m in "${MODELS[@]}"; do
    safe=${m//\//__}
    [ -d "$CLAIM/$safe" ] && continue
    complete "$m" && { mkdir -p "$CLAIM/$safe"; echo done > "$CLAIM/$safe/s"; continue; }
    mkdir "$CLAIM/$safe" 2>/dev/null || continue
    log "[w$w] 시작 $m"
    local S=$(date +%s)
    $V - "$m" <<'PYEOF' 2>&1 | tail -1
import os, sys
from huggingface_hub import snapshot_download
try:
    snapshot_download(sys.argv[1], max_workers=4, token=os.environ.get("HF_TOKEN"))
    print("  OK", sys.argv[1])
except Exception as e:
    print("  FAIL", sys.argv[1], type(e).__name__, str(e)[:160])
PYEOF
    if complete "$m"; then echo done > "$CLAIM/$safe/s"; else echo fail > "$CLAIM/$safe/s"; fi
    log "[w$w] 완료 $m ($(( $(date +%s)-S ))초 · $(cat $CLAIM/$safe/s) · 캐시 $(du -sh $HF_HOME 2>/dev/null|cut -f1))"
  done
  log "[w$w] 큐 소진"
}

log "병렬 다운로드 시작 — 워커 3"
for w in 1 2 3; do worker $w & sleep 2; done
wait
log "DL_PAR_DONE · 캐시 $(du -sh $HF_HOME 2>/dev/null|cut -f1) · 여유 $(df -h /|tail -1|awk '{print $4}')"
