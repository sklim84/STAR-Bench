#!/bin/bash
# 2단계 재실행. 앞선 실패 원인은 nvidia-nccl-cu13 이 cu12 의 libnccl.so.2 를 덮어써
# CUDA 13 빌드가 12.8 드라이버에서 로드된 것이었다(2026-09-10 07:26 교체·검증 완료).
# gemma-4-31b 는 1단계 모델이나 스케줄러 종료 후 다운로드가 끝나 여기서 함께 처리한다.
R=/home/mlp/hgyoo/bubble/codex/star-bench
SBR=$R/STAR-Bench; WEB=$R/STAR-Bench-Web; V=$R/.venv312/bin/python
export HF_HOME=$R/hf_cache NUMEXPR_MAX_THREADS=32
ORACLE_OUT=$SBR/_experiments/results_mt_oracle/
REAL_OUT=$SBR/_experiments/results_mt_real/
EVD_O=$ORACLE_OUT/eval; EVD_R=$REAL_OUT/eval
LOG=$R/logs; CLAIM=$R/.e2e_claims
PORT=11500
ts(){ echo "[$(date +%H:%M:%S)] [$1] ${*:2}"; }
kill_tree(){ local p=$1 c; for c in $(pgrep -P "$p" 2>/dev/null); do kill_tree "$c"; done; kill -9 "$p" 2>/dev/null||true; }
# VLLM::EngineCore 는 부모가 죽어도 살아남아 GPU 를 131GB 씩 붙잡는다(2026-09-10 08:07 사례).
# 프로세스 트리를 죽인 뒤, 우리 계정이 소유한 잔존 GPU 프로세스를 한 번 더 걷어낸다.
# $1 이 주어지면 그 PID 의 자손은 살려 둔다. 인자 없이 부르면 전부 걷어낸다.
reap_gpu(){ local keep=${1:-} p u protected=""
  if [ -n "$keep" ]; then
    protected=$(pstree -p "$keep" 2>/dev/null | grep -oP "\(\K\d+" | tr "\n" " ")
    [ -z "$protected" ] && protected="$keep"
  fi
  for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do
    u=$(ps -o user= -p "$p" 2>/dev/null | tr -d " ")
    [ "$u" = "$(id -un)" ] || continue
    case " $protected " in *" $p "*) continue;; esac
    kill -9 "$p" 2>/dev/null
  done; sleep 8; }
free_gpu(){ local g u i; for g in ${1//,/ }; do
  for i in $(seq 1 40); do
    u=$(nvidia-smi -i "$g" --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null|tr -d ' ')
    [ -n "$u" ] && [ "$u" -lt 5000 ] && break; sleep 3
  done; done; }
# 파일명은 multiturn_<safe>.json 또는 think 변형 multiturn_<safe>__think.json 이다.
# 와일드카드를 쓰면 skt_A_X-4_0 이 skt_A_X-4_0-Light 를 잡아 오검출하므로 정확히 대조한다.
done_already(){ local s f; s="${1//\//_}"; s="${s//./_}"
  for f in "$s.json" "${s}__think.json" "${s}__nothink.json"; do
    [ -f "$EVD_O/multiturn_$f" ] && [ -f "$EVD_R/multiturn_$f" ] && return 0
  done
  return 1; }

# 가중치 완비 여부. gemma-4-31b 는 아직 받는 중이라 완료를 기다렸다 착수한다.
ready(){ local hf=$1 d="$HF_HOME/hub/models--${hf//\//--}"
  [ -d "$d" ] || return 1
  ls "$d"/snapshots/*/config.json >/dev/null 2>&1 || return 1
  ls "$d"/snapshots/*/*.safetensors >/dev/null 2>&1 || return 1
  ls "$d"/blobs/*.incomplete >/dev/null 2>&1 && return 1
  return 0; }
wait_ready(){ local hf=$1 i
  for i in $(seq 1 120); do            # 최대 2시간
    ready "$hf" && return 0
    pgrep -f dl_gemma.sh >/dev/null || { ready "$hf" && return 0; return 1; }
    sleep 60
  done; return 1; }

run_one(){
  local alias=$1 hf=$2 parser=$3 gpus=$4 extra=$5
  local vlog=$LOG/p2_vllm_${alias}.log
  lsof -ti:$PORT 2>/dev/null | xargs -r kill -9 2>/dev/null; sleep 2
  # 이전 실패가 남긴 체크포인트를 --resume 이 재사용하면 결과가 오염된다. 깨끗이 시작한다.
  local safe="${hf//\//_}"; safe="${safe//./_}"
  rm -f $ORACLE_OUT/checkpoint/checkpoint_${safe}*.jsonl $REAL_OUT/checkpoint/checkpoint_${safe}*.jsonl 2>/dev/null
  ts "$alias" "vLLM 기동 GPU=$gpus"
  CUDA_VISIBLE_DEVICES="$gpus" HF_HOME=$R/hf_cache HF_HUB_OFFLINE=1 \
    $V -m vllm.entrypoints.openai.api_server \
    --model "$hf" --port $PORT --tool-call-parser "$parser" \
    --enable-auto-tool-choice $extra > "$vlog" 2>&1 &
  local spid=$! up=0 i
  for i in $(seq 1 300); do
    sleep 5
    curl -s -m 3 http://localhost:$PORT/v1/models >/dev/null 2>&1 && { up=1; break; }
    kill -0 $spid 2>/dev/null || break
  done
  if [ "$up" != 1 ]; then
    ts "$alias" "[FAIL] 기동 실패"; grep -iE "error|Error" "$vlog" | tail -5 | cut -c1-160
    kill_tree $spid; reap_gpu; free_gpu "$gpus"; mkdir -p $CLAIM/$alias; echo fail > $CLAIM/$alias/status; return 1
  fi
  ts "$alias" "서버 준비"
  local setting out rc=0
  for setting in oracle real; do
    out=$ORACLE_OUT; [ "$setting" = real ] && out=$REAL_OUT
    ( cd $SBR && VLLM_BASE_URL="http://localhost:$PORT/v1" PYTHONPATH="$SBR:$WEB" \
      $V -m _experiments.scripts.benchmark_multiturn \
      --models "$hf" --setting "$setting" --output "$out" --checkpoint --resume \
      > $LOG/p2_mt_${setting}_${alias}.log 2>&1 ) \
      && ts "$alias" "$setting 완료" || { ts "$alias" "$setting 실패"; tail -8 $LOG/p2_mt_${setting}_${alias}.log; rc=1; }
    # 엔진이 죽으면 이후 턴이 전부 Connection error 가 되어 결과가 오염된다. 조기 중단한다.
    if ! curl -s -m 5 http://localhost:$PORT/v1/models >/dev/null 2>&1; then
      ts "$alias" "[중단] $setting 이후 서버 사망 — 남은 설정 건너뜀"
      grep -c "Connection error" $LOG/p2_mt_${setting}_${alias}.log 2>/dev/null | sed "s/^/    연결오류 /"
      rc=1; break
    fi
  done
  kill_tree $spid; lsof -ti:$PORT 2>/dev/null | xargs -r kill -9 2>/dev/null; reap_gpu; free_gpu "$gpus"
  mkdir -p $CLAIM/$alias; echo $([ $rc = 0 ] && echo ok || echo partial) > $CLAIM/$alias/status
  ts "$alias" "종료"
}

# alias|hf|parser|gpus|extra   — 작은 것부터
# gpt-oss-120b 는 TP4 로 두 번 모두 30~40번대 시나리오에서 워커가 죽었다
# (2026-09-10 10:39, 11:56 — Worker proc died unexpectedly). MXFP4 라 가중치가 약 65GB 여서
# H200 143GB 두 장이면 충분하므로 TP2 로 낮춰 랭크 수와 실패 표면을 줄인다.
MODELS=(
  "gpt-oss-120b|openai/gpt-oss-120b|openai|0,1|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.85 --enforce-eager --reasoning-parser openai_gptoss"
)
reap_gpu
ts MAIN "=== 2단계 재실행 (${#MODELS[@]}개 순차) ==="
for spec in "${MODELS[@]}"; do
  IFS='|' read -r alias hf parser gpus extra <<< "$spec"
  if done_already "$hf"; then ts MAIN "$alias 이미 완료 — 건너뜀"; continue; fi
  if ! ready "$hf"; then
    ts MAIN "$alias 다운로드 대기"
    wait_ready "$hf" || { ts MAIN "[SKIP] $alias 가중치 미완비"; continue; }
    ts MAIN "$alias 가중치 완비"
  fi
  rm -rf $CLAIM/$alias
  run_one "$alias" "$hf" "$parser" "$gpus" "$extra"
done
ts MAIN "PHASE2_DONE"
for a in gemma-4-31b xlam-70b ax-4.0 llama-3.3-70b gpt-oss-120b; do
  printf "  %-16s %s\n" "$a" "$(cat $CLAIM/$a/status 2>/dev/null || echo -)"
done
