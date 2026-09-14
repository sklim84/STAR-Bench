#!/bin/bash
# 논문 핀(vllm 0.20.1 / torch 2.11.0 / transformers 5.7.0)을 Python 3.12에 설치한다.
# torch 는 드라이버(CUDA 12.8, 570.86.10)에 맞춰 cu128 인덱스에서 받는다 — 기본 휠은 cu13이라 기동 실패한다.
R=/home/mlp/hgyoo/bubble/codex/star-bench
export UV_CACHE_DIR=$R/.uvcache
UV=$R/.venv/bin/uv
V=$R/.venv312
log(){ echo "[$(date +%H:%M:%S)] $*"; }

log "1) torch 2.11.0 (cu128)"
$UV pip install --python $V/bin/python --index-url https://download.pytorch.org/whl/cu128 \
   torch==2.11.0 2>&1 | tail -4

log "2) vllm 0.20.1 (torch 재설치 금지)"
$UV pip install --python $V/bin/python "vllm==0.20.1" 2>&1 | tail -5

log "3) torch 실제 버전 확인"
$V/bin/python -c "import torch; print(torch.__version__, torch.version.cuda)"

log "4) 논문 requirements"
$UV pip install --python $V/bin/python -r $R/STAR-Bench/requirements.txt 2>&1 | tail -6

log "5) 도구 계층 requirements"
$UV pip install --python $V/bin/python -r $R/STAR-Bench-Web/requirements-tools.txt 2>&1 | tail -4

log "6) 최종 검증"
$V/bin/python - <<PYEOF
import importlib
mods = ["vllm","torch","transformers","duckdb","pyarrow","xgboost","sklearn","joblib",
        "openai","anthropic","openpyxl","scipy","pandas","networkx","dotenv"]
for m in mods:
    try:
        mod = importlib.import_module(m)
        v = getattr(mod, "__version__", "?")
        print("  OK   %-14s %s" % (m, v))
    except Exception as e:
        print("  FAIL %-14s %s" % (m, type(e).__name__))
import torch
print("  CUDA available:", torch.cuda.is_available(), "| torch cuda:", torch.version.cuda)
PYEOF
log "SETUP312_DONE"
