#!/bin/bash
# ============================================================================
# Per-GPU 벤치마크 실행기 (HOFINET 정정본, 24-model 분담)
#
# 24개 모델 × 3 차원(KR single_turn, EN single_turn, multi-turn STR)
# 결과 저장: _paper/_experiments/results_{kr,en,mt}/eval/
#
# 사용법:
#   bash _experiments/scripts/run_benchmark.sh --gpu 0 --port 11434 --group S1_A --mode kr
#   bash _experiments/scripts/run_benchmark.sh --gpu 1 --port 11435 --group S1_B --mode kr
#   bash _experiments/scripts/run_benchmark.sh --gpu 0,1 --port 11434 --group S2_TP2_A --mode kr
#
# group: S1_A/S1_B (서버1 단일-GPU), S2_TP4/S2_TP2_*/S2_LARGE_* (서버2)
#        SMOKE_*, RECOVERY 등은 ad-hoc 검증용
# mode:  kr (KR single_turn), en (EN single_turn), mt (multi-turn STR)
# ============================================================================

set -uo pipefail

GPU_ID="0"
PORT="11434"
GROUP="A"
MODE="kr"
TOOLS_LANG=""           # "" (default = KR tools), "en" (RQ2 ablation)
HF_TOKEN="${HF_TOKEN:-}"
PROJECT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

# 결과 디렉토리 (mode별)
RESULT_KR="$PROJECT_ROOT/_paper/_experiments/results_kr"
RESULT_EN="$PROJECT_ROOT/_paper/_experiments/results_en"
RESULT_MT="$PROJECT_ROOT/_paper/_experiments/results_mt"
CASES_KR="$PROJECT_ROOT/_paper/benchmarks"
CASES_EN="$PROJECT_ROOT/_paper/benchmarks_en"
LOG_DIR="$PROJECT_ROOT/_paper/_experiments/logs"
MAX_TOTAL="${BENCH_MAX_TOTAL:-}"

# CLI 파싱
while [[ $# -gt 0 ]]; do
    case "$1" in
        --gpu)        GPU_ID="$2"; shift 2 ;;
        --port)       PORT="$2"; shift 2 ;;
        --group)      GROUP="$2"; shift 2 ;;
        --mode)       MODE="$2"; shift 2 ;;
        --tools-lang) TOOLS_LANG="$2"; shift 2 ;;
        *) echo "Unknown: $1"; exit 1 ;;
    esac
done

# .env 토큰 로드
if [ -z "$HF_TOKEN" ] && [ -f "$PROJECT_ROOT/.env" ]; then
    HF_TOKEN_VAL=$(grep "^HF_TOKEN" "$PROJECT_ROOT/.env" | sed 's/^[^:=]*[: ]*=//' | sed 's/^[^:=]*: *//' | tr -d ' "'"'"'')
    [ -n "$HF_TOKEN_VAL" ] && HF_TOKEN="$HF_TOKEN_VAL"
fi

# flash_attn 스텁
FLASH_ATTN_STUB="/tmp/fake_flash_attn"
if [ ! -f "$FLASH_ATTN_STUB/flash_attn/__init__.py" ]; then
    mkdir -p "$FLASH_ATTN_STUB/flash_attn/ops/triton"
    echo "pass" > "$FLASH_ATTN_STUB/flash_attn/__init__.py"
    cat > "$FLASH_ATTN_STUB/flash_attn/flash_attn_interface.py" << 'PYEOF'
def flash_attn_varlen_func(*args, **kwargs):
    raise NotImplementedError("flash_attn stub")
PYEOF
    echo "pass" > "$FLASH_ATTN_STUB/flash_attn/ops/__init__.py"
    echo "pass" > "$FLASH_ATTN_STUB/flash_attn/ops/triton/__init__.py"
    cat > "$FLASH_ATTN_STUB/flash_attn/ops/triton/rotary.py" << 'PYEOF'
def apply_rotary(*args, **kwargs):
    raise NotImplementedError("flash_attn rotary stub")
PYEOF
fi

# Kanana 커스텀 파서
KANANA_PARSER_PLUGIN="$PROJECT_ROOT/_paper/_experiments/scripts/kanana_tool_calls/kanana_tool_calls/functionary_kanana_tool_parser.py"
KANANA_CHAT_TEMPLATE="$PROJECT_ROOT/_paper/_experiments/scripts/kanana_tool_calls/kanana_tool_calls/lmalign_v1.jinja"

# ── 모델 정의 (44 모델 = 11 + 11 + 10 + 3 entries, think/nothink 확장 포함) ──
GROUP_A=(
    "qwen35-0.8b|Qwen/Qwen3.5-0.8B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-0.8B"
    "qwen35-2b|Qwen/Qwen3.5-2B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-2B"
    "qwen35-4b|Qwen/Qwen3.5-4B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-4B"
    "qwen35-9b|Qwen/Qwen3.5-9B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-9B"
    "qwen3-4b|Qwen/Qwen3-4B-Instruct-2507|qwen3_xml||Qwen/Qwen3-4B-Instruct-2507"
    "qwen25-1.5b|Qwen/Qwen2.5-1.5B-Instruct|hermes||Qwen/Qwen2.5-1.5B-Instruct"
    "qwen3-8b|Qwen/Qwen3-8B|qwen3_xml||Qwen/Qwen3-8B"
    "exaone-4.0-1.2b|LGAI-EXAONE/EXAONE-4.0-1.2B|hermes|--trust-remote-code|LGAI-EXAONE/EXAONE-4.0-1.2B"
    "glm-4.7-flash|zai-org/GLM-4.7-Flash|glm47|--trust-remote-code|zai-org/GLM-4.7-Flash"
    "hermes-3-8b|NousResearch/Hermes-3-Llama-3.1-8B|hermes||NousResearch/Hermes-3-Llama-3.1-8B"
    "ax-light|skt/A.X-4.0-Light|hermes||skt/A.X-4.0-Light"
)
# qwen3-4b-think를 GROUP_B 끝에 배치 (thinking 모드 9h+ 소요로 GPU 1을 마지막에 점유,
# GPU 0의 Group A가 먼저 끝나면 idle 발생 — 추후 A_OFFLOAD 패턴으로 보완 가능)
GROUP_B=(
    "xlam-1b|Salesforce/xLAM-2-1b-fc-r|xlam||Salesforce/xLAM-2-1b-fc-r"
    "xlam-3b|Salesforce/xLAM-2-3b-fc-r|xlam||Salesforce/xLAM-2-3b-fc-r"
    "xlam-8b|Salesforce/Llama-xLAM-2-8b-fc-r|xlam||Salesforce/Llama-xLAM-2-8b-fc-r"
    "llama-3.2-1b|meta-llama/Llama-3.2-1B-Instruct|llama3_json||meta-llama/Llama-3.2-1B-Instruct"
    "llama-3.2-3b|meta-llama/Llama-3.2-3B-Instruct|llama3_json||meta-llama/Llama-3.2-3B-Instruct"
    "llama-3.1-8b|meta-llama/Llama-3.1-8B-Instruct|llama3_json||meta-llama/Llama-3.1-8B-Instruct"
    "ministral-3b|mistralai/Ministral-3-3B-Instruct-2512|mistral||mistralai/Ministral-3-3B-Instruct-2512"
    "ministral-8b|mistralai/Ministral-3-8B-Instruct-2512|mistral||mistralai/Ministral-3-8B-Instruct-2512"
    "ministral-14b|mistralai/Ministral-3-14B-Instruct-2512|mistral||mistralai/Ministral-3-14B-Instruct-2512"
    "mistral-nemo|mistralai/Mistral-Nemo-Instruct-2407|mistral||mistralai/Mistral-Nemo-Instruct-2407"
    "qwen3-4b-think|Qwen/Qwen3-4B-Thinking-2507|qwen3_xml|--reasoning-parser qwen3|Qwen/Qwen3-4B-Thinking-2507"
)
GROUP_C=(
    "qwen35-27b|Qwen/Qwen3.5-27B|qwen3_coder|--reasoning-parser qwen3 --enforce-eager|Qwen/Qwen3.5-27B"
    "qwen3-30b|Qwen/Qwen3-30B-A3B-Instruct-2507|qwen3_xml|--max-model-len 32768|Qwen/Qwen3-30B-A3B-Instruct-2507"
    "qwen3-30b-think|Qwen/Qwen3-30B-A3B-Thinking-2507|qwen3_xml|--max-model-len 32768 --reasoning-parser qwen3|Qwen/Qwen3-30B-A3B-Thinking-2507"
    "qwen3-coder-30b|Qwen/Qwen3-Coder-30B-A3B-Instruct|qwen3_xml|--max-model-len 32768|Qwen/Qwen3-Coder-30B-A3B-Instruct"
    "exaone-4.0-32b|LGAI-EXAONE/EXAONE-4.0-32B|hermes|--trust-remote-code|LGAI-EXAONE/EXAONE-4.0-32B"
    "xlam-32b|Salesforce/xLAM-2-32b-fc-r|xlam||Salesforce/xLAM-2-32b-fc-r"
    "mistral-small|mistralai/Mistral-Small-3.2-24B-Instruct-2506|mistral||mistralai/Mistral-Small-3.2-24B-Instruct-2506"
    "gpt-oss-20b|openai/gpt-oss-20b|openai|--reasoning-parser openai_gptoss|openai/gpt-oss-20b"
    "kanana-2-inst|kakaocorp/kanana-2-30b-a3b-instruct|hermes||kakaocorp/kanana-2-30b-a3b-instruct"
    "kanana-2-think|kakaocorp/kanana-2-30b-a3b-thinking-2601|hermes|--reasoning-parser deepseek_r1|kakaocorp/kanana-2-30b-a3b-thinking-2601"
)
GROUP_TP2=(
    "llama-3.3-70b|meta-llama/Llama-3.3-70B-Instruct|llama3_json|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager|meta-llama/Llama-3.3-70B-Instruct"
    "xlam-70b|Salesforce/Llama-xLAM-2-70b-fc-r|xlam|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager|Salesforce/Llama-xLAM-2-70b-fc-r"
    "ax-4.0|skt/A.X-4.0|hermes|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager|skt/A.X-4.0"
)

# Group C 분할 (GPU 0/1 병렬, 변형 수 균형)
GROUP_C1=(
    "${GROUP_C[0]}"  # qwen35-27b (think/nothink, 2변형)
    "${GROUP_C[3]}"  # qwen3-coder-30b
    "${GROUP_C[5]}"  # xlam-32b
    "${GROUP_C[7]}"  # gpt-oss-20b (think/nothink, 2변형)
    "${GROUP_C[6]}"  # mistral-small
)
GROUP_C2=(
    "${GROUP_C[1]}"  # qwen3-30b
    "${GROUP_C[2]}"  # qwen3-30b-think (2변형)
    "${GROUP_C[4]}"  # exaone-4.0-32b
    "${GROUP_C[8]}"  # kanana-2-inst
    "${GROUP_C[9]}"  # kanana-2-think (2변형)
)

# ===========================================================================
# 서버별 GROUP (MODELS.md 24-model 기준, 2026-04-29)
# ===========================================================================
# Server 1 (2× H100 80GB) — 11 모델: small/medium 단일-GPU
# Server 2 (6× H100 80GB) — 13 모델: large + TP=2 + TP=4
# ===========================================================================

# Server 1 GPU 0 (6 모델)
# - Gemma-4-E4B-it: 공식 multimodal + gemma4 parser (vLLM 0.19 + transformers 5.7.0 필수)
# - Phi-4-mini: phi4_mini_json + vLLM 공식 jinja chat template (functools[...] 형식 강제)
# - DragonLLM/Llama-Open-Finance-8B: A안 swap (Llama-Fin-8b 0/5 대체, smoke 3/5 score 0.78)
GROUP_S1_A=(
    "qwen35-4b|Qwen/Qwen3.5-4B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-4B"
    "gemma-4-e4b|google/gemma-4-E4B-it|gemma4||google/gemma-4-E4B-it"
    "phi-4-mini|microsoft/Phi-4-mini-instruct|phi4_mini_json|--chat-template $PROJECT_ROOT/_paper/_experiments/scripts/tool_chat_template_phi4_mini.jinja|microsoft/Phi-4-mini-instruct"
    "xlam-3b|Salesforce/xLAM-2-3b-fc-r|xlam||Salesforce/xLAM-2-3b-fc-r"
    "exaone-1.2b|LGAI-EXAONE/EXAONE-4.0-1.2B|hermes|--trust-remote-code|LGAI-EXAONE/EXAONE-4.0-1.2B"
    "dragon-llama-fin|DragonLLM/Llama-Open-Finance-8B|llama3_json||DragonLLM/Llama-Open-Finance-8B"
)

# Server 1 GPU 1 (5 모델)
# - DragonLLM/Qwen-Open-Finance-R-8B: A안 swap (Fino1-8B 0/5 대체, smoke 3/5 score 0.73)
GROUP_S1_B=(
    "llama-3.2-3b|meta-llama/Llama-3.2-3B-Instruct|llama3_json||meta-llama/Llama-3.2-3B-Instruct"
    "ministral-3b|mistralai/Ministral-3-3B-Instruct-2512|mistral||mistralai/Ministral-3-3B-Instruct-2512"
    "hermes-3-8b|NousResearch/Hermes-3-Llama-3.1-8B|hermes||NousResearch/Hermes-3-Llama-3.1-8B"
    "ax-light|skt/A.X-4.0-Light|hermes||skt/A.X-4.0-Light"
    "dragon-qwen-fin|DragonLLM/Qwen-Open-Finance-R-8B|qwen3_xml|--reasoning-parser qwen3|DragonLLM/Qwen-Open-Finance-R-8B"
)

# Server 2 — TP=4 (gpt-oss-120b, 4 GPUs)
GROUP_S2_TP4=(
    "gpt-oss-120b|openai/gpt-oss-120b|openai|--tensor-parallel-size 4 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager --reasoning-parser openai_gptoss|openai/gpt-oss-120b"
)

# Server 2 — TP=2 (3 pair 병렬, 각 70B+)
GROUP_S2_TP2_A=(
    "llama-3.3-70b|meta-llama/Llama-3.3-70B-Instruct|llama3_json|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager|meta-llama/Llama-3.3-70B-Instruct"
)
GROUP_S2_TP2_B=(
    "xlam-70b|Salesforce/Llama-xLAM-2-70b-fc-r|xlam|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager|Salesforce/Llama-xLAM-2-70b-fc-r"
)
GROUP_S2_TP2_C=(
    "ax-4.0|skt/A.X-4.0|hermes|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager|skt/A.X-4.0"
)

# Server 2 — Single-GPU Large (9 모델 → 3 lanes × 3 모델)
GROUP_S2_LARGE_L1=(
    "qwen35-27b|Qwen/Qwen3.5-27B|qwen3_coder|--reasoning-parser qwen3 --enforce-eager|Qwen/Qwen3.5-27B"
    "qwen36-27b|Qwen/Qwen3.6-27B|qwen3_xml||Qwen/Qwen3.6-27B"
    "qwen36-35b-a3b|Qwen/Qwen3.6-35B-A3B|qwen3_xml|--max-model-len 32768|Qwen/Qwen3.6-35B-A3B"
)
GROUP_S2_LARGE_L2=(
    "gemma-4-31b|google/gemma-4-31B-it|hermes||google/gemma-4-31B-it"
    "mistral-small|mistralai/Mistral-Small-3.2-24B-Instruct-2506|mistral||mistralai/Mistral-Small-3.2-24B-Instruct-2506"
    "exaone-32b|LGAI-EXAONE/EXAONE-4.0-32B|hermes|--trust-remote-code|LGAI-EXAONE/EXAONE-4.0-32B"
)
GROUP_S2_LARGE_L3=(
    "gpt-oss-20b|openai/gpt-oss-20b|openai|--reasoning-parser openai_gptoss|openai/gpt-oss-20b"
    "kanana-2-inst|kakaocorp/kanana-2-30b-a3b-instruct|hermes||kakaocorp/kanana-2-30b-a3b-instruct"
    "kanana-2-think|kakaocorp/kanana-2-30b-a3b-thinking-2601|hermes|--reasoning-parser deepseek_r1|kakaocorp/kanana-2-30b-a3b-thinking-2601"
)

# ===========================================================================
# Legacy / ad-hoc GROUPS
# ===========================================================================

# SMOKE: 파이프라인 검증용 (가장 작은 2개 모델)
GROUP_SMOKE=(
    "qwen35-0.8b|Qwen/Qwen3.5-0.8B|qwen3_coder|--reasoning-parser qwen3|Qwen/Qwen3.5-0.8B"
    "qwen25-1.5b|Qwen/Qwen2.5-1.5B-Instruct|hermes||Qwen/Qwen2.5-1.5B-Instruct"
)

# SMOKE_ARCH: 새 architecture (Gemma-4, Qwen3.6) transformers 5.7.0 업그레이드 후 검증
# vLLM 0.19에 모델 전용 parser 존재: gemma4, phi4_mini_json
# Gemma-4 E4B-it 공식 multimodal 재시도 (vLLM 0.19 + gemma4 parser)
GROUP_SMOKE_ARCH=(
    "phi-4-mini|microsoft/Phi-4-mini-instruct|phi4_mini_json||microsoft/Phi-4-mini-instruct"
    "gemma-4-e4b|google/gemma-4-E4B-it|gemma4||google/gemma-4-E4B-it"
    "gemma-4-31b|google/gemma-4-31B-it|gemma4||google/gemma-4-31B-it"
    "qwen36-27b|Qwen/Qwen3.6-27B|qwen3_xml||Qwen/Qwen3.6-27B"
    "qwen36-35b-a3b|Qwen/Qwen3.6-35B-A3B|qwen3_xml|--max-model-len 32768|Qwen/Qwen3.6-35B-A3B"
)

# SMOKE_PHI4: Phi-4-mini-instruct alternative parser 검증
# phi4_mini_json (dedicated) 0/5 실패 → pythonic, hermes, openai 시도
# alias 뒤에 parser 식별자 붙여 결과 디렉토리 분리
GROUP_SMOKE_PHI4=(
    "phi-4-mini-pyt|microsoft/Phi-4-mini-instruct|pythonic||microsoft/Phi-4-mini-instruct"
    "phi-4-mini-hermes|microsoft/Phi-4-mini-instruct|hermes||microsoft/Phi-4-mini-instruct"
    "phi-4-mini-llama3|microsoft/Phi-4-mini-instruct|llama3_json||microsoft/Phi-4-mini-instruct"
)

# SMOKE_PHI4_TEMPLATE: Phi-4-mini-instruct + 공식 vLLM chat template
# 원인 진단: Microsoft 기본 chat template(<|tool|>/<|tool_calls|>)과 vLLM phi4_mini_json parser
# (functools[...] regex)의 형식 불일치로 0/5 실패. vLLM examples의 tool_chat_template_phi4_mini.jinja는
# 모델이 functools[...] 형식으로 출력하도록 system 지시 → parser 매칭됨.
GROUP_SMOKE_PHI4_TEMPLATE=(
    "phi-4-mini-tmpl|microsoft/Phi-4-mini-instruct|phi4_mini_json|--chat-template $PROJECT_ROOT/_paper/_experiments/scripts/tool_chat_template_phi4_mini.jinja|microsoft/Phi-4-mini-instruct"
)

# SMOKE_DRAGONLLM: DragonLLM (LLM Open Finance) 8B 2종, FC 보존 의도된 finance 모델
# Llama-Open-Finance-8B: Llama-3.1 base → llama3_json
# Qwen-Open-Finance-R-8B: Qwen 3 base → qwen3_xml (R = reasoning preserved)
GROUP_SMOKE_DRAGONLLM=(
    "dragon-llama-fin|DragonLLM/Llama-Open-Finance-8B|llama3_json||DragonLLM/Llama-Open-Finance-8B"
    "dragon-qwen-fin|DragonLLM/Qwen-Open-Finance-R-8B|qwen3_xml|--reasoning-parser qwen3|DragonLLM/Qwen-Open-Finance-R-8B"
)

# RECOVERY: Group B 비정상 종료로 누락된 mistral-nemo 단독 실행
GROUP_RECOVERY=(
    "mistral-nemo|mistralai/Mistral-Nemo-Instruct-2407|mistral||mistralai/Mistral-Nemo-Instruct-2407"
)

# A_OFFLOAD: Group A 후반부 5 entries를 GPU 1 idle 시간에 병렬 처리 (master Group A는 자체 흐름 유지)
# Master Group A가 [7/11]~[11/11] 도달 시점에 이미 결과 존재 → --resume으로 즉시 skip
GROUP_A_OFFLOAD=(
    "exaone-4.0-1.2b|LGAI-EXAONE/EXAONE-4.0-1.2B|hermes|--trust-remote-code|LGAI-EXAONE/EXAONE-4.0-1.2B"
    "qwen3-8b|Qwen/Qwen3-8B|qwen3_xml||Qwen/Qwen3-8B"
    "ax-light|skt/A.X-4.0-Light|hermes||skt/A.X-4.0-Light"
    "hermes-3-8b|NousResearch/Hermes-3-Llama-3.1-8B|hermes||NousResearch/Hermes-3-Llama-3.1-8B"
    "glm-4.7-flash|zai-org/GLM-4.7-Flash|glm47|--trust-remote-code|zai-org/GLM-4.7-Flash"
)

# RQ2_REPS: 4-way 2x2 (KR-KR/EN-KR/KR-EN/EN-EN) ablation 6 representatives
# 모두 Server 2 large/TP=2 엔트리 — Server 2에서 --tools-lang en 으로 KR-EN/EN-EN 추가 실행
# KR-KR (default, kr mode): master S2 baseline에 자동 포함
# EN-KR (default, en mode): master S2 baseline에 자동 포함
# KR-EN: bash run_benchmark.sh --gpu ... --group RQ2_REPS --mode kr --tools-lang en
# EN-EN: bash run_benchmark.sh --gpu ... --group RQ2_REPS --mode en --tools-lang en
GROUP_RQ2_REPS=(
    "qwen35-27b|Qwen/Qwen3.5-27B|qwen3_coder|--reasoning-parser qwen3 --enforce-eager|Qwen/Qwen3.5-27B"
    "qwen36-27b|Qwen/Qwen3.6-27B|qwen3_xml||Qwen/Qwen3.6-27B"
    "llama-3.3-70b|meta-llama/Llama-3.3-70B-Instruct|llama3_json|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager|meta-llama/Llama-3.3-70B-Instruct"
    "gemma-4-31b|google/gemma-4-31B-it|gemma4||google/gemma-4-31B-it"
    "exaone-32b|LGAI-EXAONE/EXAONE-4.0-32B|hermes|--trust-remote-code|LGAI-EXAONE/EXAONE-4.0-32B"
    "ax-4.0|skt/A.X-4.0|hermes|--tensor-parallel-size 2 --max-model-len 16384 --gpu-memory-utilization 0.95 --enforce-eager|skt/A.X-4.0"
)

case "$GROUP" in
    A)     MODELS=("${GROUP_A[@]}") ;;
    B)     MODELS=("${GROUP_B[@]}") ;;
    C)     MODELS=("${GROUP_C[@]}") ;;
    C1)    MODELS=("${GROUP_C1[@]}") ;;
    C2)    MODELS=("${GROUP_C2[@]}") ;;
    TP2)   MODELS=("${GROUP_TP2[@]}") ;;
    SMOKE) MODELS=("${GROUP_SMOKE[@]}") ;;
    SMOKE_ARCH) MODELS=("${GROUP_SMOKE_ARCH[@]}") ;;
    SMOKE_PHI4) MODELS=("${GROUP_SMOKE_PHI4[@]}") ;;
    SMOKE_PHI4_TEMPLATE) MODELS=("${GROUP_SMOKE_PHI4_TEMPLATE[@]}") ;;
    SMOKE_DRAGONLLM) MODELS=("${GROUP_SMOKE_DRAGONLLM[@]}") ;;
    RECOVERY) MODELS=("${GROUP_RECOVERY[@]}") ;;
    A_OFFLOAD) MODELS=("${GROUP_A_OFFLOAD[@]}") ;;
    # Server 1
    S1_A) MODELS=("${GROUP_S1_A[@]}") ;;
    S1_B) MODELS=("${GROUP_S1_B[@]}") ;;
    # Server 2
    S2_TP4) MODELS=("${GROUP_S2_TP4[@]}") ;;
    S2_TP2_A) MODELS=("${GROUP_S2_TP2_A[@]}") ;;
    S2_TP2_B) MODELS=("${GROUP_S2_TP2_B[@]}") ;;
    S2_TP2_C) MODELS=("${GROUP_S2_TP2_C[@]}") ;;
    S2_LARGE_L1) MODELS=("${GROUP_S2_LARGE_L1[@]}") ;;
    S2_LARGE_L2) MODELS=("${GROUP_S2_LARGE_L2[@]}") ;;
    S2_LARGE_L3) MODELS=("${GROUP_S2_LARGE_L3[@]}") ;;
    # RQ2 4-way ablation
    RQ2_REPS) MODELS=("${GROUP_RQ2_REPS[@]}") ;;
    *)     echo "Unknown group: $GROUP"; exit 1 ;;
esac

# Mode → output/cases 결정
case "$MODE" in
    kr) OUTPUT_DIR="$RESULT_KR";       BENCH_MODULE="_experiments.scripts.benchmark";          BENCH_EXTRA="--checkpoint --resume" ;;
    en) OUTPUT_DIR="$RESULT_EN";       BENCH_MODULE="_experiments.scripts.benchmark";          BENCH_EXTRA="--cases-dir $CASES_EN --checkpoint --resume" ;;
    mt) OUTPUT_DIR="$RESULT_MT";       BENCH_MODULE="_experiments.scripts.benchmark_multiturn"; BENCH_EXTRA="" ;;
    *)  echo "Unknown mode: $MODE (kr, en, mt)"; exit 1 ;;
esac

# RQ2 4-way ablation: --tools-lang en일 때 별도 디렉토리/플래그 (kr+en/en+en만 별도 보관, kr/en 기본 결과와 분리)
if [[ "$TOOLS_LANG" == "en" ]]; then
    OUTPUT_DIR="${OUTPUT_DIR}_tools_en"
    BENCH_EXTRA="$BENCH_EXTRA --tools-lang en"
fi

mkdir -p "$OUTPUT_DIR/eval" "$OUTPUT_DIR/checkpoint" "$LOG_DIR"

# 유틸리티
ts() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }

wait_for_server() {
    local port=$1 max_wait=${2:-600}
    ts "  서버 기동 대기 (port $port, max ${max_wait}s)..."
    for ((i=1; i<=max_wait/5; i++)); do
        if python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:$port/health', timeout=3)" 2>/dev/null; then
            ts "  서버 준비 완료 (${i}*5초)"
            return 0
        fi
        sleep 5
    done
    ts "  [ERROR] 서버 기동 타임아웃!"
    return 1
}

stop_server() {
    local port=$1
    local pids=$(lsof -ti:$port 2>/dev/null)
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill 2>/dev/null || true
        sleep 5
        echo "$pids" | xargs kill -9 2>/dev/null || true
        ts "  vLLM 서버 종료 (port=$port)"
    fi
    pkill -9 -f "vllm.*--port $port" 2>/dev/null || true
    sleep 2
}

run_benchmark() {
    local model_names=$1
    local extra_env=""
    [ -n "$MAX_TOTAL" ] && extra_env="$extra_env BENCH_MAX_TOTAL=$MAX_TOTAL"
    [ "${BENCH_SKIP_THINK:-0}" = "1" ] && extra_env="$extra_env BENCH_SKIP_THINK=1"
    ts "  벤치마크: $extra_env PYTHONPATH=$PROJECT_ROOT/_paper python -m $BENCH_MODULE --models $model_names --output $OUTPUT_DIR $BENCH_EXTRA"
    env $extra_env PYTHONPATH="$PROJECT_ROOT/_paper:${PYTHONPATH:-}" python -m "$BENCH_MODULE" --models $model_names --output "$OUTPUT_DIR" $BENCH_EXTRA
}

# 메인 루프
ts "============================================================"
ts "벤치마크 시작: GROUP=$GROUP MODE=$MODE GPU=$GPU_ID PORT=$PORT"
ts "OUTPUT: $OUTPUT_DIR"
ts "총 ${#MODELS[@]}개 모델 (think/nothink 변형 포함)"
ts "============================================================"

cd "$PROJECT_ROOT"

for ((idx=0; idx<${#MODELS[@]}; idx++)); do
    IFS='|' read -r alias hf_model parser extra_args bench_models <<< "${MODELS[$idx]}"

    ts ""
    ts "━━━ [$((idx+1))/${#MODELS[@]}] $alias ($hf_model) [$MODE] ━━━"

    stop_server "$PORT"

    # GPU 할당 (TP=2 vs 단일)
    if echo "$extra_args" | grep -q "tensor-parallel-size 2"; then
        CUDA_DEVICES="0,1"
    else
        CUDA_DEVICES="$GPU_ID"
    fi

    # Kanana 커스텀 파서 옵션
    KANANA_OPTS=""
    if [[ "$alias" == kanana-2-* ]]; then
        KANANA_OPTS="--tool-parser-plugin $KANANA_PARSER_PLUGIN --chat-template $KANANA_CHAT_TEMPLATE"
    fi

    vllm_cmd="CUDA_VISIBLE_DEVICES=$CUDA_DEVICES PYTHONPATH=$FLASH_ATTN_STUB:\${PYTHONPATH:-} HF_TOKEN=$HF_TOKEN python -m vllm.entrypoints.openai.api_server --model $hf_model --port $PORT --max-model-len 32768 --gpu-memory-utilization 0.95 --tool-call-parser $parser --enable-auto-tool-choice $extra_args $KANANA_OPTS"
    ts "  vLLM 시작 (CUDA=$CUDA_DEVICES)"
    eval "$vllm_cmd" > "$LOG_DIR/vllm_${MODE}_${alias}.log" 2>&1 &

    if ! wait_for_server "$PORT" 600; then
        ts "  [SKIP] $alias 서버 기동 실패"
        tail -50 "$LOG_DIR/vllm_${MODE}_${alias}.log" 2>/dev/null || true
        stop_server "$PORT"
        continue
    fi

    # bench_models 공백 분리
    bench_models_spaced=$(echo "$bench_models" | tr ',' ' ')

    # SMOKE_PHI4*: 동일 HF model을 다른 parser/template로 반복 검증하므로 매 회 checkpoint + eval JSON 모두 clear
    # (--resume이 eval_*.json 존재 시 모델 skip하므로 eval도 삭제)
    if [[ "$GROUP" == SMOKE_PHI4* ]]; then
        for bm in $bench_models_spaced; do
            safe=$(echo "$bm" | tr ':/.' '___')
            cp_file="$OUTPUT_DIR/checkpoint/checkpoint_${safe}.jsonl"
            [ -f "$cp_file" ] && rm -f "$cp_file" && ts "  checkpoint 삭제: $cp_file"
            for ev in "$OUTPUT_DIR"/eval/eval_${safe}_*.json; do
                [ -f "$ev" ] && rm -f "$ev" && ts "  eval 삭제: $ev"
            done
        done
    fi

    VLLM_BASE_URL="http://localhost:$PORT/v1" run_benchmark "$bench_models_spaced" || true

    stop_server "$PORT"
    ts "  $alias 완료"
done

ts ""
ts "============================================================"
ts "Group $GROUP / Mode $MODE 전체 완료!"
ts "============================================================"
