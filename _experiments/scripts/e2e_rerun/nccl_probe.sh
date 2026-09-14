#!/bin/bash
R=/home/mlp/hgyoo/bubble/codex/star-bench
V=$R/.venv312/bin/python
log(){ echo "[$(date +%H:%M:%S)] $*"; }
probe(){ local tag="$1"; shift
  log "── $tag"
  env "$@" CUDA_VISIBLE_DEVICES=0,1 timeout 200 $V $R/nccl_test.py 2>&1 | grep -E "RESULT|all_reduce|NCCL WARN|Error" | head -4
}
probe "기본"              NCCL_DEBUG=WARN
probe "P2P 끄기"          NCCL_DEBUG=WARN NCCL_P2P_DISABLE=1
probe "P2P+SHM 끄기"      NCCL_DEBUG=WARN NCCL_P2P_DISABLE=1 NCCL_SHM_DISABLE=1
probe "IB 끄기 + P2P/SHM" NCCL_DEBUG=WARN NCCL_P2P_DISABLE=1 NCCL_SHM_DISABLE=1 NCCL_IB_DISABLE=1
log "PROBE_DONE"
