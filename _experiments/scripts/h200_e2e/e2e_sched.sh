#!/bin/bash
# 다운로드가 끝난 모델부터 순차로 E2E(oracle+real)를 돌린다.
# GPU 4장에 워커를 하나씩 두고, 각 워커가 "준비됐고 아직 아무도 안 집은" 모델을
# mkdir 로 원자적으로 집어간다. 대형(tensor-parallel) 모델은 2단계에서 순차 처리한다.
R=/home/mlp/hgyoo/bubble/codex/star-bench
SBR=$R/STAR-Bench; WEB=$R/STAR-Bench-Web; V=$R/.venv312/bin/python
export HF_HOME=$R/hf_cache
export NUMEXPR_MAX_THREADS=32
ORACLE_OUT=$SBR/_experiments/results_mt_oracle/
REAL_OUT=$SBR/_experiments/results_mt_real/
LOG=$R/logs; mkdir -p $LOG
CLAIM=$R/.e2e_claims; mkdir -p $CLAIM
KPLUG=$SBR/_experiments/scripts/kanana_tool_calls/kanana_tool_calls/functionary_kanana_tool_parser.py
KTMPL=$SBR/_experiments/scripts/kanana_tool_calls/kanana_tool_calls/lmalign_v1.jinja
PHI_TMPL=$SBR/_experiments/scripts/tool_chat_template_phi4_mini.jinja

ts(){ echo "[$(date +%H:%M:%S)] [$1] ${*:2}"; }
kill_tree(){ local p=$1 c; for c in $(pgrep -P "$p" 2>/dev/null); do kill_tree "$c"; done; kill -9 "$p" 2>/dev/null||true; }
free_gpu(){ local g u i; for g in ${1//,/ }; do
    for i in $(seq 1 40); do
      u=$(nvidia-smi -i "$g" --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null|tr -d ' ')
      [ -n "$u" ] && [ "$u" -lt 5000 ] && break
      sleep 3
    done; done; }

# 가중치가 완전히 받아졌는가: 스냅샷에 config.json 과 safetensors 가 있고 .incomplete 가 없다
ready(){ local hf=$1 d="$HF_HOME/hub/models--${hf//\//--}"
  [ -d "$d" ] || return 1
  ls "$d"/snapshots/*/config.json >/dev/null 2>&1 || return 1
  ls "$d"/snapshots/*/*.safetensors >/dev/null 2>&1 || return 1
  ls "$d"/blobs/*.incomplete >/dev/null 2>&1 && return 1
  return 0; }

# 이미 결과가 있는가 (oracle+real 둘 다)
done_already(){ local hf=$1 s="${hf//\//_}"; s="${s//./_}"
  [ -f "$ORACLE_OUT/eval/multiturn_${s}.json" ] && [ -f "$REAL_OUT/eval/multiturn_${s}.json" ]; }

run_one(){
  local alias=$1 hf=$2 parser=$3 gpu=$4 port=$5 extra=$6 kanana=$7
  local vlog=$LOG/e2e_vllm_${alias}.log kopt=""
  [ "$kanana" = "1" ] && kopt="--tool-parser-plugin $KPLUG --chat-template $KTMPL"
  lsof -ti:"$port" 2>/dev/null | xargs -r kill -9 2>/dev/null; sleep 1
  ts "$alias" "vLLM 기동 GPU=$gpu PORT=$port"
  # HF_HUB_OFFLINE: gated repo 의 선택적 파일(tokenizer.model 등)을 허브에서 찾다가
  # 401 을 받고 죽는 것을 막는다. 가중치는 ready() 가 이미 완비를 확인했다.
  CUDA_VISIBLE_DEVICES="$gpu" HF_HOME=$R/hf_cache HF_HUB_OFFLINE=1 \
    $V -m vllm.entrypoints.openai.api_server \
    --model "$hf" --port "$port" --tool-call-parser "$parser" \
    --enable-auto-tool-choice $kopt $extra > "$vlog" 2>&1 &
  local spid=$! up=0 i
  for i in $(seq 1 240); do
    sleep 5
    curl -s -m 3 "http://localhost:$port/v1/models" >/dev/null 2>&1 && { up=1; break; }
    kill -0 $spid 2>/dev/null || break
  done
  if [ "$up" != 1 ]; then
    ts "$alias" "[FAIL] 기동 실패"; tail -15 "$vlog"
    kill_tree $spid; free_gpu "$gpu"; echo fail > $CLAIM/$alias/status; return 1
  fi
  ts "$alias" "서버 준비"
  local setting out rc=0
  for setting in oracle real; do
    out=$ORACLE_OUT; [ "$setting" = real ] && out=$REAL_OUT
    ( cd $SBR && VLLM_BASE_URL="http://localhost:$port/v1" PYTHONPATH="$SBR:$WEB" \
      $V -m _experiments.scripts.benchmark_multiturn \
      --models "$hf" --setting "$setting" --output "$out" --checkpoint --resume \
      > $LOG/e2e_mt_${setting}_${alias}.log 2>&1 ) \
      && ts "$alias" "$setting 완료" \
      || { ts "$alias" "$setting 실패"; tail -10 $LOG/e2e_mt_${setting}_${alias}.log; rc=1; }
  done
  kill_tree $spid; lsof -ti:"$port" 2>/dev/null | xargs -r kill -9 2>/dev/null; free_gpu "$gpu"
  echo $([ $rc = 0 ] && echo ok || echo partial) > $CLAIM/$alias/status
  ts "$alias" "종료"
}

# alias|hf|parser|extra|kanana   — 단일 GPU 모델 20개(다운로드 순서와 같게 작은 것부터)
SINGLE=(
  "exaone-1.2b|LGAI-EXAONE/EXAONE-4.0-1.2B|hermes|--trust-remote-code|0"
  "xlam-3b|Salesforce/xLAM-2-3b-fc-r|xlam||0"
  "ministral-3b|mistralai/Ministral-3-3B-Instruct-2512|mistral||0"
  "phi-4-mini|microsoft/Phi-4-mini-instruct|phi4_mini_json|--chat-template @PHI@ --max-model-len 12288|0"
  "qwen35-4b|Qwen/Qwen3.5-4B|qwen3_coder|--reasoning-parser qwen3|0"
  "gemma-4-e4b|google/gemma-4-E4B-it|gemma4||0"
  "gpt-oss-20b|openai/gpt-oss-20b|openai|--reasoning-parser openai_gptoss|0"
  "ax-light|skt/A.X-4.0-Light|hermes|--max-model-len 16384|0"
  "hermes-3-8b|NousResearch/Hermes-3-Llama-3.1-8B|hermes||0"
  "llama-3.2-3b|meta-llama/Llama-3.2-3B-Instruct|llama3_json||0"
  "dragon-llama-fin|DragonLLM/Llama-Open-Finance-8B|llama3_json||0"
  "dragon-qwen-fin|DragonLLM/Qwen-Open-Finance-R-8B|qwen3_xml|--reasoning-parser qwen3|0"
  "mistral-small|mistralai/Mistral-Small-3.2-24B-Instruct-2506|mistral||0"
  "qwen35-27b|Qwen/Qwen3.5-27B|qwen3_coder|--reasoning-parser qwen3 --enforce-eager|0"
  "qwen36-27b|Qwen/Qwen3.6-27B|qwen3_xml||0"
  "gemma-4-31b|google/gemma-4-31B-it|gemma4||0"
  "exaone-32b|LGAI-EXAONE/EXAONE-4.0-32B|hermes|--trust-remote-code|0"
  "qwen36-35b-a3b|Qwen/Qwen3.6-35B-A3B|qwen3_xml|--max-model-len 32768|0"
  "kanana-2-inst|kakaocorp/kanana-2-30b-a3b-instruct|functionary_v3_llama_31||1"
  "kanana-2-think|kakaocorp/kanana-2-30b-a3b-thinking-2601|functionary_v3_llama_31||1"
)
# GPU 여러 장을 쓰는 대형 모델 — 1단계가 끝난 뒤 순차
MULTI=(
  "gpt-oss-120b|openai/gpt-oss-120b|openai|--tensor-parallel-size 4 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager --reasoning-parser openai_gptoss|0|0,1,2,3"
  "llama-3.3-70b|meta-llama/Llama-3.3-70B-Instruct|llama3_json|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager|0|0,1"
  "xlam-70b|Salesforce/Llama-xLAM-2-70b-fc-r|xlam|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager|0|0,1"
  "ax-4.0|skt/A.X-4.0|hermes|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager|0|0,1"
)

# 다운로더 이름이 바뀌어도 워커가 조기 종료하지 않도록 세 종류를 모두 본다.
# dl_models.sh(순차, 폐기) / dl_gated.sh(gated 전용) / dl_par.sh(병렬, 현행)
dl_running(){ pgrep -f "dl_models\.sh|dl_gated\.sh|dl_par\.sh" > /dev/null; }

# 워커: 자기 GPU 에서 "준비됐고 아직 안 집힌" 모델을 하나씩 처리한다.
worker(){
  local gpu=$1 port=$((11480 + $1)) spec alias hf parser extra kanana picked
  while true; do
    picked=0
    for spec in "${SINGLE[@]}"; do
      IFS='|' read -r alias hf parser extra kanana <<< "$spec"
      [ -d "$CLAIM/$alias" ] && continue
      done_already "$hf" && { mkdir -p "$CLAIM/$alias"; echo skip-done > "$CLAIM/$alias/status"; continue; }
      ready "$hf" || continue
      mkdir "$CLAIM/$alias" 2>/dev/null || continue      # 원자적 선점
      extra=${extra//@PHI@/$PHI_TMPL}
      ts "GPU$gpu" "선점 → $alias"
      run_one "$alias" "$hf" "$parser" "$gpu" "$port" "$extra" "$kanana"
      picked=1; break
    done
    if [ $picked = 0 ]; then
      dl_running || { ts "GPU$gpu" "남은 준비 모델 없음 · 다운로드도 종료 → 워커 종료"; return 0; }
      sleep 60
    fi
  done
}

ts MAIN "=== 1단계: 단일 GPU 모델 ${#SINGLE[@]}개 · 워커 4 ==="
for g in 0 1 2 3; do worker $g > $LOG/e2e_worker_$g.log 2>&1 & done
wait
ts MAIN "1단계 완료 — 결과: $(ls $CLAIM 2>/dev/null | wc -l)개 처리"

ts MAIN "=== 2단계: 대형 모델 ${#MULTI[@]}개 순차 ==="
for spec in "${MULTI[@]}"; do
  IFS='|' read -r alias hf parser extra kanana gpus <<< "$spec"
  [ -d "$CLAIM/$alias" ] && { ts MAIN "$alias 이미 처리됨"; continue; }
  while ! ready "$hf"; do
    dl_running || { ts MAIN "[SKIP] $alias 미다운로드 · 다운로드 종료됨"; break; }
    sleep 120
  done
  ready "$hf" || continue
  mkdir -p "$CLAIM/$alias"
  run_one "$alias" "$hf" "$parser" "$gpus" 11500 "$extra" "$kanana"
done
ts MAIN "E2E_ALL_DONE"
for a in $(ls $CLAIM 2>/dev/null); do printf "  %-18s %s\n" "$a" "$(cat $CLAIM/$a/status 2>/dev/null)"; done
