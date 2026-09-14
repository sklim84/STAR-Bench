#!/bin/bash
# 1단계에 남은 마지막 모델. 다운로드 워커가 대형 모델에 밀려 시작하지 못했다.
R=/home/mlp/hgyoo/bubble/codex/star-bench
export HF_HOME=$R/hf_cache
log(){ echo "[$(date +%H:%M:%S)] $*"; }
log "gemma-4-31B-it 다운로드 시작"
S=$(date +%s)
$R/.venv312/bin/python - <<'PYEOF' 2>&1 | tail -2
from huggingface_hub import snapshot_download
try:
    print("  OK", snapshot_download("google/gemma-4-31B-it", max_workers=8))
except Exception as e:
    print("  FAIL", type(e).__name__, str(e)[:200])
PYEOF
log "완료 ($(( $(date +%s)-S ))초 · 캐시 $(du -sh $HF_HOME|cut -f1))"
