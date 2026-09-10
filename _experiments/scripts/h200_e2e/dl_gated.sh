#!/bin/bash
# gated=manual 인 meta-llama 2종을 받는다. 토큰 파일은 이 스크립트가 끝나면
# 정상·비정상 종료 어느 쪽이든 즉시 파기한다(trap).
R=/home/mlp/hgyoo/bubble/codex/star-bench
export HF_HOME=$R/hf_cache
V=$R/.venv312/bin/python
TF=$R/.hf_token
log(){ echo "[$(date +%H:%M:%S)] $*"; }

shred_token(){
  if [ -f "$TF" ]; then
    shred -u -z "$TF" 2>/dev/null || rm -f "$TF"
    log "토큰 파일 파기됨"
  fi
}
trap shred_token EXIT INT TERM

[ -f "$TF" ] || { log "토큰 파일 없음 — 중단"; exit 1; }
export HF_TOKEN="$(cat $TF)"
log "토큰 로드 (${#HF_TOKEN}자)"

for m in meta-llama/Llama-3.2-3B-Instruct meta-llama/Llama-3.3-70B-Instruct; do
  log "받는 중: $m"
  S=$(date +%s)
  $V - "$m" <<'PYEOF' 2>&1 | tail -2
import os, sys
from huggingface_hub import snapshot_download
try:
    p = snapshot_download(sys.argv[1], token=os.environ["HF_TOKEN"], max_workers=8)
    print("  OK", p)
except Exception as e:
    print("  FAIL", type(e).__name__, str(e)[:200])
PYEOF
  log "  $(( $(date +%s) - S ))초 · 여유 $(df -h / | tail -1 | awk '{print $4}')"
done
unset HF_TOKEN
shred_token
log "GATED_DL_DONE"
