#!/bin/bash
# tensor-parallel 이 NCCL 초기화에서 죽는다:
#   NCCL WARN Cuda failure 'CUDA driver version is insufficient for CUDA runtime version'
# 원인: nvidia-nccl-cu12(2.28.9) 와 nvidia-nccl-cu13(2.31.2) 이 같은 경로
# (nvidia/nccl/lib/libnccl.so.2) 를 공유하는데 cu13 이 덮어써서 CUDA 13 빌드가 로드된다.
# 드라이버는 12.8 이라 major 차이로 실행되지 않는다. cu13 을 걷어내고 cu12 를 복원한다.
R=/home/mlp/hgyoo/bubble/codex/star-bench
export UV_CACHE_DIR=$R/.uvcache
UV=$R/.venv/bin/uv; V=$R/.venv312/bin/python
log(){ echo "[$(date +%H:%M:%S)] $*"; }

log "현재 libnccl 심볼릭/실체"
ls -la $R/.venv312/lib/python3.12/site-packages/nvidia/nccl/lib/ | sed 's/^/  /'

log "nvidia-nccl-cu13 제거"
$UV pip uninstall --python $V nvidia-nccl-cu13 2>&1 | tail -3

log "nvidia-nccl-cu12 재설치 (덮어써진 .so 복원)"
$UV pip install --python $V --reinstall-package nvidia-nccl-cu12 nvidia-nccl-cu12==2.28.9 2>&1 | tail -4

log "복원 후"
ls -la $R/.venv312/lib/python3.12/site-packages/nvidia/nccl/lib/ | sed 's/^/  /'
$V -c "import torch; print('  torch', torch.__version__, '| nccl', torch.cuda.nccl.version())"

log "NCCL 재시험 (GPU 0,1)"
CUDA_VISIBLE_DEVICES=0,1 NCCL_DEBUG=WARN timeout 200 $V $R/nccl_test.py 2>&1 | grep -E "RESULT|all_reduce|NCCL WARN" | head -4
log "FIX_NCCL_DONE"
