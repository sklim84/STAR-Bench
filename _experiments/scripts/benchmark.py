"""다중 모델 벤치마크 실험 러너.

v6 벤치마크 데이터셋(1,258건, 24개 카테고리)을 대상으로
여러 LLM 모델의 에이전트 행위능력을 평가한다.

대상 모델:
    - gpt-4o-mini               (OpenAI API)
    - claude-haiku-4-5-20251001 (Anthropic API)
    - claude-sonnet-4-5-20250929(Anthropic API, 선택적)
    - qwen2.5:1.5b              (Ollama)
    - qwen2.5:0.5b              (Ollama)
    - qwen3:0.6b                (Ollama)

사용법:
    # 테스트 (모델당 2건만)
    BENCH_MAX_CASES=2 python _experiments/scripts/benchmark.py --output _experiments/results/

    # gpt-4o-mini만 실행
    python _experiments/scripts/benchmark.py --models gpt-4o-mini --output _experiments/results/

    # Claude 모델 실행
    python _experiments/scripts/benchmark.py --models claude-haiku-4-5-20251001 --output _experiments/results/

    # 전체 실행
    python _experiments/scripts/benchmark.py --output _experiments/results/

    # 특정 모델 재개
    python _experiments/scripts/benchmark.py --models qwen2.5:1.5b --output _experiments/results/

    # 케이스 단위 체크포인트 + 재실행 시 완료 케이스 skip (진짜 resume)
    python _experiments/scripts/benchmark.py --models qwen2.5:0.5b --checkpoint --output _experiments/results/

    # 백그라운드 실행용 로그 파일 (nohup과 함께 사용)
    nohup python _experiments/scripts/benchmark.py --models qwen2.5:0.5b --checkpoint --log-file bench.log &

    # 상세 로그 (케이스별 score, elapsed, error_type)
    python _experiments/scripts/benchmark.py --models qwen2.5:0.5b --checkpoint -v --log-file bench.log

    # 대화 흐름 디버그 (API 호출/도구 실행 라운드별)
    python _experiments/scripts/benchmark.py --models qwen2.5:0.5b --checkpoint --debug-chat --log-file bench.log

환경 변수:
    OPENAI_API_KEY:     OpenAI API 키 (gpt-4o-mini 실행 시 필요)
    ANTHROPIC_API_KEY:  Anthropic API 키 (Claude 모델 실행 시 필요)
    BENCH_MAX_CASES:    카테고리당 최대 케이스 수 (기본: 전체)
    BENCH_TIMEOUT:      API 호출 타임아웃 초 (기본: 300, Ollama 소형 모델 대비)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# Streamlit "No runtime found" 경고 억제 (가능한 한 먼저 실행)
for _name in ("streamlit", "streamlit.runtime", "streamlit.runtime.caching", "streamlit.runtime.caching.cache_data_api"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.CRITICAL)
    _log.propagate = False
    _log.handlers = []

import anthropic
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openai import OpenAI

# 프로젝트 루트를 sys.path에 추가
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# 실행 가능한 AML 도구(src.features.agent)는 동반 저장소 STAR-Bench-Web에 있다.
# 사본을 두지 않고 그 체크아웃을 찾아 path에 올린다 — 자세한 규칙은 _platform 참조.
from _experiments.scripts._platform import ensure_platform_on_path  # noqa: E402

ensure_platform_on_path()

from src.features.agent import (  # noqa: E402
    SYSTEM_PROMPT,
    TOOLS,
    MAX_TOOL_ROUNDS,
    _execute_tool,
    _message_to_dict,
)
from _experiments.scripts.evaluator import (  # noqa: E402
    evaluate_case,
    aggregate_results,
    normalize_parse_fail_result,
    normalize_exception_result,
)

logger = logging.getLogger(__name__)

# --tools-lang en 활성화 플래그 (main에서 설정)
_TOOLS_LANG_EN: bool = False
_MAX_TOKENS: int = 4096  # --max-tokens CLI 옵션으로 덮어쓰기 가능 (입력 토큰 오버플로우 완화용)
_CASE_ID_FILTER = None  # --case-ids / --case-ids-file: 부분 재실험 시 특정 ID set
_FORCE_RERUN: bool = False  # --force-rerun: 체크포인트 캐시 무시 (--case-ids와 함께 사용)


def _ts_print(msg: str = "", *, end: str = "\n", flush: bool = True) -> None:
    """타임스탬프를 붙여 print한다 (벤치마크 로그용)."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ts} {msg}", end=end, flush=flush)


def _model_key(model: dict) -> str:
    """모델 설정의 고유 식별자. think 상태를 포함하여 동일 모델의 think on/off를 구분한다."""
    name = model["name"]
    think = model.get("think")
    if think is True:
        return f"{name}__think"
    elif think is False:
        return f"{name}__nothink"
    return name


# API 타임아웃 (초). BENCH_TIMEOUT 환경변수, 기본 300 (Ollama 소형 모델 대비)
_API_TIMEOUT = int(os.environ.get("BENCH_TIMEOUT", "300"))

# ---------------------------------------------------------------------------
# 모델 레지스트리
# ---------------------------------------------------------------------------

MODELS = [
    # ── Cloud API 모델 ──────────────────────────────────────────────
    {
        "name": "gpt-4o-mini",
        "provider": "openai",
        "base_url": None,
        "api_key_env": "OPENAI_API_KEY",
        "think": None,
    },
    {
        "name": "gpt-5-mini",
        "provider": "openai",
        "base_url": None,
        "api_key_env": "OPENAI_API_KEY",
        "think": None,
    },
    {
        "name": "claude-haiku-4-5-20251001",
        "provider": "anthropic",
        "base_url": None,
        "api_key_env": "ANTHROPIC_API_KEY",
        "think": None,
    },
    {
        "name": "claude-sonnet-4-5-20250929",
        "provider": "anthropic",
        "base_url": None,
        "api_key_env": "ANTHROPIC_API_KEY",
        "think": None,
    },
    # ── vLLM 로컬 모델 (think=None: 추론 미지원, False: 추론 끔, True: 추론 켬) ──
    # Mistral
    {
        "name": "mistralai/Mistral-Small-3.2-24B-Instruct-2506",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "mistralai/Ministral-3-3B-Instruct-2512",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "mistralai/Ministral-3-8B-Instruct-2512",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "mistralai/Ministral-3-14B-Instruct-2512",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # Kanana (Kakao)
    {
        "name": "kakaocorp/kanana-1.5-15.7b-a3b-instruct",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "kakaocorp/kanana-1.5-8b-instruct-2505",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "kakaocorp/kanana-1.5-2.1b-instruct-2505",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # Kanana 2 (Kakao, 2025.12, 에이전트 특화)
    {
        "name": "kakaocorp/kanana-2-30b-a3b-instruct",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # NT 비교군 (-2601 vintage instruct, 2026-05-08 추가). thinking-2601과 같은 base/시점
    {
        "name": "kakaocorp/kanana-2-30b-a3b-instruct-2601",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # always-thinking 모델: enable_thinking 토글 미지원. 단일 entry로 등록
    # NT 비교는 sibling-variant kanana-2-30b-a3b-instruct-2601과 직접 비교
    {
        "name": "kakaocorp/kanana-2-30b-a3b-thinking-2601",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # SKT A.X (SKT, 2025, 한국어 SOTA)
    {
        "name": "skt/A.X-4.0",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "skt/A.X-4.0-Light",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # Qwen3 30B-A3B
    {
        "name": "Qwen/Qwen3-30B-A3B-Instruct-2507",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # always-thinking 모델: enable_thinking 토글 미지원. 단일 entry. NT 비교는 -Instruct-2507
    {
        "name": "Qwen/Qwen3-30B-A3B-Thinking-2507",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # Qwen3 8B
    {
        "name": "Qwen/Qwen3-8B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # Qwen3 4B
    {
        "name": "Qwen/Qwen3-4B-Instruct-2507",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # always-thinking 모델: enable_thinking 토글 미지원. 단일 entry. NT 비교는 -Instruct-2507
    {
        "name": "Qwen/Qwen3-4B-Thinking-2507",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # microsoft/Phi-4-mini-instruct: 제외 — tool call 거의 미생성 (1/1258건, 0.3253)
    # microsoft/Phi-4-mini-reasoning: 제외 — 추론 특화 모델, tool call 미생성 (0.3248)

    # GPT-OSS (OpenAI open-weight)
    {
        "name": "openai/gpt-oss-120b",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": False,
    },
    {
        "name": "openai/gpt-oss-120b",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": True,
    },
    {
        "name": "openai/gpt-oss-20b",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": False,
    },
    {
        "name": "openai/gpt-oss-20b",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": True,
    },
    # ── Llama (Meta) ─────────────────────────────────────────────────
    {
        "name": "meta-llama/Llama-3.1-8B-Instruct",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "meta-llama/Llama-3.3-70B-Instruct",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "meta-llama/Llama-4-Scout-17B-16E-Instruct",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # ── EXAONE (LG AI Research, 한국어) ────────────────────────────────
    # LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct: 제외 — tool call 미생성 (0/1258건, 0.3248)
    # LGAI-EXAONE/EXAONE-3.5-32B-Instruct: 제외 — tool call 미생성 (0/1258건, 0.3248)
    # ── EXAONE 4.0 (LG AI연구원, 2025.07) ──────────────────────────────
    {
        "name": "LGAI-EXAONE/EXAONE-4.0-32B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "LGAI-EXAONE/EXAONE-4.0-1.2B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # EXAONE Deep-32B/7.8B: 추론 특화 모델로 tool calling 미지원 (전건 wrong_func)
    # ── HyperCLOVA X SEED (네이버, 2026.01) ─────────────────────────
    {
        "name": "naver-hyperclovax/HyperCLOVAX-SEED-Think-32B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "naver-hyperclovax/HyperCLOVAX-SEED-Think-14B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # ── GLM-4.7 (Zhipu AI, 2026.01) ─────────────────────────────────
    {
        "name": "zai-org/GLM-4.7-Flash",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # ── Gemma 3 (Google) ───────────────────────────────────────────────
    # google/gemma-3-4b-it: vLLM v0.16.0 미지원 (Gemma3ForConditionalGeneration)
    # google/gemma-3-12b-it, 27b-it: 제외 — tool-calling 미지원 모델, tool call 미생성 (0.3248)

    # ibm-granite/granite-3.1-8b-instruct: 제외 — tool call 거의 미생성 (2/1258건, 0.3258)
    # EXAONE-Deep-7.8B, 32B: 제외 — 추론 특화 모델, tool-calling 미지원, tool call 미생성 (0.3248)

    # ── Qwen3.5 (Thinking 모델) ──────────────────────────────────────
    {
        "name": "Qwen/Qwen3.5-0.8B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": False,
    },
    {
        "name": "Qwen/Qwen3.5-0.8B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": True,
    },
    {
        "name": "Qwen/Qwen3.5-2B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": False,
    },
    {
        "name": "Qwen/Qwen3.5-2B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": True,
    },
    {
        "name": "Qwen/Qwen3.5-4B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": False,
    },
    {
        "name": "Qwen/Qwen3.5-4B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": True,
    },
    {
        "name": "Qwen/Qwen3.5-9B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": False,
    },
    {
        "name": "Qwen/Qwen3.5-9B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": True,
    },
    {
        "name": "Qwen/Qwen3.5-27B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": False,
    },
    {
        "name": "Qwen/Qwen3.5-27B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": True,
    },
    # ── xLAM (Salesforce, 도구 호출 특화) ────────────────────────────
    {
        "name": "Salesforce/xLAM-2-1b-fc-r",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "Salesforce/xLAM-2-3b-fc-r",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "Salesforce/Llama-xLAM-2-8b-fc-r",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "Salesforce/xLAM-2-32b-fc-r",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "Salesforce/Llama-xLAM-2-70b-fc-r",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # ── Llama 3.2 (Meta, 소형) ──────────────────────────────────────
    {
        "name": "meta-llama/Llama-3.2-1B-Instruct",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "meta-llama/Llama-3.2-3B-Instruct",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # Qwen/Qwen3-14B-Instruct-2507: 제외 — HF에 미공개 모델
    # Qwen/Qwen3-32B-Instruct-2507: 제외 — HF에 미공개 모델
    # ── Tencent Hunyuan (80B/13B MoE) ──────────────────────────────────
    {
        "name": "tencent/Hunyuan-A13B-Instruct",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # ── OLMo 3 (Allen AI, 7B dense) ───────────────────────────────────
    {
        "name": "allenai/OLMo-3-7B-Instruct",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # ── DeepSeek R1 distill (8B dense) ─────────────────────────────────
    {
        "name": "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # ── GLM-4.5-Air (106B/12B MoE) ────────────────────────────────────
    {
        "name": "zai-org/GLM-4.5-Air",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # ── Granite 3.2 (IBM, 8B dense) ───────────────────────────────────
    {
        "name": "ibm-granite/granite-3.2-8b-instruct",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # ── Hermes 3 (NousResearch) ─────────────────────────────────────
    {
        "name": "NousResearch/Hermes-3-Llama-3.1-8B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # internlm/internlm3-8b-instruct: 제외 — tool call 미생성 (0/1258건, 0.3211)
    # ── Mistral Nemo (12B dense) ──────────────────────────────────────
    {
        "name": "mistralai/Mistral-Nemo-Instruct-2407",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # microsoft/Phi-4 (14B): 제외 — tool call 미생성 (0/1258건, 0.3248)
    # ── Command R7B (Cohere) ──────────────────────────────────────────
    {
        "name": "CohereForAI/c4ai-command-r7b-12-2024",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # ── Qwen3 Coder (30B MoE, A3B active) ────────────────────────────
    {
        "name": "Qwen/Qwen3-Coder-30B-A3B-Instruct",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # gemma3:12b-cloud
    {
        "name": "gemma4:31b-cloud",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # ── 이전 모델 (참고용, Ollama/vLLM) ──────────────────────────────
    {
        "name": "Qwen/Qwen2.5-1.5B-Instruct",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    # ── NEW 모델 (2026-04-29 추가, 스모크 테스트 대상) ──
    {
        "name": "Qwen/Qwen3.6-27B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "Qwen/Qwen3.6-35B-A3B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "google/gemma-4-E4B-it",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "google/gemma-4-31B-it",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "microsoft/Phi-4-mini-instruct",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "DragonLLM/Llama-Open-Finance-8B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
    {
        "name": "DragonLLM/Qwen-Open-Finance-R-8B",
        "provider": "vllm",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,
        "think": None,
    },
]

# ---------------------------------------------------------------------------
# 데이터셋 / 임계값 (bench_agent_behavior.py에서 동일 사용)
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # star-bench/
_DATASET_DIR = _PROJECT_ROOT / "benchmarks"

_DATASET_FILES = {
    "get_statistics":          _DATASET_DIR / "cases_get_statistics.json",
    "query_transactions":      _DATASET_DIR / "cases_query_transactions.json",
    "analyze_network":         _DATASET_DIR / "cases_analyze_network.json",
    "predict_fraud":           _DATASET_DIR / "cases_predict_fraud.json",
    "detect_aml_patterns":     _DATASET_DIR / "cases_detect_aml_patterns.json",
    "multi_tool":              _DATASET_DIR / "cases_multi_tool.json",
    "get_account_profile":     _DATASET_DIR / "cases_get_account_profile.json",
    "get_fraud_type_summary":  _DATASET_DIR / "cases_get_fraud_type_summary.json",
    "compare_periods":         _DATASET_DIR / "cases_compare_periods.json",
    "get_institution_report":  _DATASET_DIR / "cases_get_institution_report.json",
    "rank_risky_transactions": _DATASET_DIR / "cases_rank_risky_transactions.json",
    "detect_ctr_candidates":   _DATASET_DIR / "cases_detect_ctr_candidates.json",
    "score_account_risk":      _DATASET_DIR / "cases_score_account_risk.json",
    "detect_monitoring_alerts": _DATASET_DIR / "cases_detect_monitoring_alerts.json",
    "detect_dormant_reactivation": _DATASET_DIR / "cases_detect_dormant_reactivation.json",
    "detect_smurfing_network": _DATASET_DIR / "cases_detect_smurfing_network.json",
    "get_trend_analysis":      _DATASET_DIR / "cases_get_trend_analysis.json",
    "analyze_channel_risk":    _DATASET_DIR / "cases_analyze_channel_risk.json",
    "get_receiving_account_profile": _DATASET_DIR / "cases_get_receiving_account_profile.json",
    "analyze_cross_institution_flow": _DATASET_DIR / "cases_analyze_cross_institution_flow.json",
    "missing_parameters": _DATASET_DIR / "cases_missing_parameters.json",
    "lookup_fiu_reference_types": _DATASET_DIR / "cases_lookup_fiu_reference_types.json",
    "validate_str_fields": _DATASET_DIR / "cases_validate_str_fields.json",
    "get_aml_glossary": _DATASET_DIR / "cases_get_aml_glossary.json",
}

_THRESHOLDS = {
    "get_statistics":          0.85,
    "query_transactions":      0.75,
    "analyze_network":         0.75,
    "predict_fraud":           0.80,
    "detect_aml_patterns":     0.75,
    "multi_tool":              0.65,
    "get_account_profile":     0.80,
    "get_fraud_type_summary":  0.80,
    "compare_periods":         0.80,
    "get_institution_report":  0.80,
    "rank_risky_transactions": 0.75,
    "detect_ctr_candidates":   0.80,
    "score_account_risk":      0.80,
    "detect_monitoring_alerts": 0.75,
    "detect_dormant_reactivation": 0.75,
    "detect_smurfing_network": 0.75,
    "get_trend_analysis":      0.80,
    "analyze_channel_risk":    0.75,
    "get_receiving_account_profile": 0.80,
    "analyze_cross_institution_flow": 0.75,
    "missing_parameters": 0.90,
    "lookup_fiu_reference_types": 0.85,
    "validate_str_fields": 0.85,
    "get_aml_glossary": 0.90,
}

# ---------------------------------------------------------------------------
# Excel 색상 팔레트
# ---------------------------------------------------------------------------

_COLOR_HEADER_DARK = "1F3864"
_COLOR_HEADER_BLUE = "2E75B6"
_COLOR_PASS = "E2EFDA"
_COLOR_FAIL = "FCE4D6"
_COLOR_ALT_ROW = "F5F5F5"
_COLOR_MODEL_COLORS = {
    "gpt-4o-mini":               "DAEEF3",
    "gpt-5-mini":                "C5E0F0",
    "claude-haiku-4-5-20251001": "F3E5D8",
    "claude-sonnet-4-5-20250929":"F0E0D0",
    "qwen2.5:1.5b":              "FFF2CC",
    "qwen2.5:0.5b":              "FCE4D6",
    "qwen3:0.6b":                "EDE7F6",
}


def _thin_border() -> Border:
    thin = Side(style="thin", color="BDBDBD")
    return Border(left=thin, right=thin, top=thin, bottom=thin)


def _header_font(bold: bool = True, color: str = "FFFFFF", size: int = 10) -> Font:
    return Font(bold=bold, color=color, name="맑은 고딕", size=size)


def _body_font(bold: bool = False, color: str = "000000", size: int = 9) -> Font:
    return Font(bold=bold, color=color, name="맑은 고딕", size=size)


def _fill(hex_color: str) -> PatternFill:
    return PatternFill(fill_type="solid", fgColor=hex_color)


def _set_col_width(ws, col_letter: str, width: float):
    ws.column_dimensions[col_letter].width = width


# ---------------------------------------------------------------------------
# Anthropic API 지원
# ---------------------------------------------------------------------------


# -- Anthropic 스키마 한글 키 → 영문 키 매핑 --------------------------------
# Anthropic API는 property key가 ^[a-zA-Z0-9_.-]{1,64}$ 패턴을 요구하므로
# predict_fraud / generate_str 등의 한글 파라미터를 영문으로 변환한다.
_KO_EN_KEY_MAP: dict[str, str] = {
    "거래일자": "transaction_date",
    "거래시간대": "transaction_time_zone",
    "출금금융회사일련번호": "sender_bank_id",
    "출금계좌일련번호": "sender_account_id",
    "입금금융회사일련번호": "receiver_bank_id",
    "입금계좌일련번호": "receiver_account_id",
    "자금구분": "fund_type",
    "매체구분": "channel_type",
    "거래금액": "transaction_amount",
    "이상거래유형": "fraud_type_code",
}
_EN_KO_KEY_MAP: dict[str, str] = {v: k for k, v in _KO_EN_KEY_MAP.items()}


def _rename_schema_keys(schema: dict) -> dict:
    """JSON schema의 한글 property key를 영문으로 재귀 변환한다."""
    import copy
    schema = copy.deepcopy(schema)

    if "properties" in schema:
        new_props = {}
        for key, val in schema["properties"].items():
            new_key = _KO_EN_KEY_MAP.get(key, key)
            new_props[new_key] = _rename_schema_keys(val)
        schema["properties"] = new_props

    if "required" in schema:
        schema["required"] = [_KO_EN_KEY_MAP.get(k, k) for k in schema["required"]]

    if "items" in schema and isinstance(schema["items"], dict):
        schema["items"] = _rename_schema_keys(schema["items"])

    return schema


def _revert_args_keys(args: dict) -> dict:
    """Anthropic 모델이 반환한 영문 argument key를 원래 한글로 복원한다."""
    result = {}
    for k, v in args.items():
        ko_key = _EN_KO_KEY_MAP.get(k, k)
        if isinstance(v, list):
            result[ko_key] = [
                _revert_args_keys(item) if isinstance(item, dict) else item
                for item in v
            ]
        elif isinstance(v, dict):
            result[ko_key] = _revert_args_keys(v)
        else:
            result[ko_key] = v
    return result


def _convert_tools_to_anthropic(openai_tools: list[dict]) -> list[dict]:
    """OpenAI tool 스키마를 Anthropic 형식으로 변환한다.

    OpenAI: {"type":"function","function":{"name":...,"description":...,"parameters":...}}
    Anthropic: {"name":...,"description":...,"input_schema":...}

    한글 property key는 영문으로 변환된다 (_KO_EN_KEY_MAP 참조).
    """
    anthropic_tools = []
    for tool in openai_tools:
        func = tool["function"]
        input_schema = func.get("parameters", {"type": "object", "properties": {}})
        input_schema = _rename_schema_keys(input_schema)
        anthropic_tools.append({
            "name": func["name"],
            "description": func.get("description", ""),
            "input_schema": input_schema,
        })
    return anthropic_tools


def chat_with_anthropic_model(
    question: str,
    *,
    model_name: str,
    api_key: str,
    debug_chat: bool = False,
) -> list[dict]:
    """Anthropic API로 tool calling 대화를 수행한다.

    Returns:
        tool_events: [{name, arguments, result}, ...]
    """
    client = anthropic.Anthropic(api_key=api_key, timeout=_API_TIMEOUT)
    anthropic_tools = _convert_tools_to_anthropic(TOOLS)

    messages = [{"role": "user", "content": question}]
    tool_events: list[dict] = []

    for round_idx in range(MAX_TOOL_ROUNDS):
        if debug_chat:
            _ts_print(f"      [chat] round {round_idx+1}: API 호출 중...", flush=True)
        round_start = time.time()
        response = client.messages.create(
            model=model_name,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=anthropic_tools,
            max_tokens=_MAX_TOKENS,
            temperature=0,
        )
        round_elapsed = time.time() - round_start

        # 응답 content 블록 처리
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        if debug_chat:
            _ts_print(f"      [chat] round {round_idx+1}: 응답 {round_elapsed:.1f}s, tool_use={len(tool_use_blocks)}개", flush=True)

        if not tool_use_blocks:
            # 도구 호출 없이 최종 응답
            if debug_chat:
                _ts_print(f"      [chat] round {round_idx+1}: 최종 응답 (도구 없음), 종료", flush=True)
            break

        # assistant 메시지 추가 (전체 content 블록 포함)
        messages.append({"role": "assistant", "content": response.content})

        # tool_result 메시지 구성
        tool_results = []
        for block in tool_use_blocks:
            tool_name = block.name
            tool_args_en = block.input if isinstance(block.input, dict) else {}
            # 영문 키를 한글로 복원하여 실행 및 평가에 사용
            tool_args = _revert_args_keys(tool_args_en)

            if debug_chat:
                _ts_print(f"      [chat] round {round_idx+1}: 도구 실행 {tool_name}(...)", flush=True)
            t0 = time.time()
            result = _execute_tool(tool_name, tool_args)
            if debug_chat:
                _ts_print(f"      [chat] round {round_idx+1}: 도구 완료 {tool_name} ({time.time()-t0:.1f}s, {len(str(result))} chars)", flush=True)
            tool_events.append({
                "name": tool_name,
                "arguments": tool_args,
                "result": result,
            })

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })

        messages.append({"role": "user", "content": tool_results})

        # stop_reason이 end_turn이면 종료
        if response.stop_reason == "end_turn":
            if debug_chat:
                _ts_print(f"      [chat] round {round_idx+1}: end_turn, 종료", flush=True)
            break

    if debug_chat:
        _ts_print(f"      [chat] 총 {len(tool_events)}개 도구 호출 완료", flush=True)
    return tool_events


# ---------------------------------------------------------------------------
# Ollama 폴백 파싱 (3단계)
# ---------------------------------------------------------------------------


def _parse_tool_calls_from_content(content: str) -> list[dict] | None:
    """content 문자열에서 tool_calls를 추출한다 (3단계 폴백).

    1. ```json``` 코드 블록 내 배열/객체
    2. {"name": ..., "arguments": ...} 패턴
    3. 파싱 불가 시 None 반환

    Returns:
        [{"name": str, "arguments": dict}, ...] 또는 None
    """
    if not content:
        return None

    # Step 1: ```json ... ``` 코드 블록 추출
    json_blocks = re.findall(r"```json\s*([\s\S]*?)```", content, re.IGNORECASE)
    for block in json_blocks:
        parsed = _try_parse_tool_json(block.strip())
        if parsed:
            return parsed

    # Step 2: {..."name"... "arguments"...} 패턴 직접 추출
    # 중첩 JSON도 처리하기 위해 brace matching 사용
    candidates = _extract_json_objects(content)
    for candidate in candidates:
        parsed = _try_parse_tool_json(candidate)
        if parsed:
            return parsed

    return None


def _try_parse_tool_json(text: str) -> list[dict] | None:
    """JSON 텍스트를 tool call 형식으로 파싱 시도."""
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None

    # 단일 tool call 객체
    if isinstance(obj, dict):
        if "name" in obj:
            args = obj.get("arguments", obj.get("parameters", {}))
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            return [{"name": obj["name"], "arguments": args}]
        # OpenAI tool_calls 형식 (function.name, function.arguments)
        if "function" in obj and isinstance(obj["function"], dict):
            func = obj["function"]
            args = func.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            return [{"name": func["name"], "arguments": args}]

    # 배열 형태
    if isinstance(obj, list):
        results = []
        for item in obj:
            if isinstance(item, dict) and "name" in item:
                args = item.get("arguments", item.get("parameters", {}))
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                results.append({"name": item["name"], "arguments": args})
        if results:
            return results

    return None


def _extract_json_objects(text: str) -> list[str]:
    """텍스트에서 최상위 JSON 객체들을 brace matching으로 추출한다."""
    results = []
    i = 0
    while i < len(text):
        if text[i] == '{':
            depth = 0
            start = i
            in_string = False
            escape = False
            while i < len(text):
                ch = text[i]
                if escape:
                    escape = False
                elif ch == '\\' and in_string:
                    escape = True
                elif ch == '"' and not escape:
                    in_string = not in_string
                elif not in_string:
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            results.append(text[start:i + 1])
                            break
                i += 1
        i += 1
    return results


# ---------------------------------------------------------------------------
# 모델 교체 가능한 chat 함수
# ---------------------------------------------------------------------------


def chat_with_model(
    question: str,
    *,
    model_name: str,
    base_url: str | None = None,
    api_key: str = "ollama",
    think: bool | None = None,
    debug_chat: bool = False,
) -> list[dict]:
    """agent.chat()와 동일 로직으로 대화를 수행하되, 모델/클라이언트를 교체한다.

    Args:
        think: None=추론 미지원 모델, True=추론 켬, False=추론 끔.
               vLLM에서 chat_template_kwargs로 enable_thinking을 제어한다.

    Returns:
        tool_events: [{name, arguments, result}, ...]
    """
    if base_url:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=_API_TIMEOUT)
    else:
        client = OpenAI(api_key=api_key, timeout=_API_TIMEOUT)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    tool_events: list[dict] = []

    for round_idx in range(MAX_TOOL_ROUNDS):
        if debug_chat:
            _ts_print(f"      [chat] round {round_idx+1}: API 호출 중...", flush=True)
        round_start = time.time()
        # gpt-5 계열 등 추론 모델은 temperature=0 미지원
        create_kwargs = dict(
            model=model_name,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            max_completion_tokens=_MAX_TOKENS,
        )
        if not model_name.startswith(("o1", "o3", "o4", "gpt-5")):
            create_kwargs["temperature"] = 0
        # 추론 모드 제어 — 모델 패밀리별 메커니즘 분기
        # 1) gpt-oss: Harmony 포맷, reasoning_effort 파라미터 사용 (low/medium/high).
        #    chat_template_kwargs.enable_thinking 무시됨 (vLLM이 apply_chat_template 미사용).
        #    완전 비활성 불가, T=high / NT=low 의 effort-level ablation으로 해석.
        # 2) Qwen3.5/3.6 등: chat_template_kwargs.enable_thinking 토글 (vLLM 공식).
        # 3) always-thinking 모델 (Qwen3-*-Thinking-2507, kanana-2-thinking-2601):
        #    토글 미지원. think=None으로 등록되어 이 분기 진입하지 않음.
        if think is not None:
            if "gpt-oss" in model_name:
                create_kwargs["reasoning_effort"] = "high" if think else "low"
            else:
                create_kwargs["extra_body"] = {
                    "chat_template_kwargs": {"enable_thinking": think},
                }
        response = client.chat.completions.create(**create_kwargs)
        round_elapsed = time.time() - round_start

        msg = response.choices[0].message

        # 네이티브 tool_calls 확인
        native_tool_calls = getattr(msg, "tool_calls", None)

        if native_tool_calls:
            if debug_chat:
                _ts_print(f"      [chat] round {round_idx+1}: 응답 {round_elapsed:.1f}s, tool_calls={len(native_tool_calls)}개", flush=True)
            # 네이티브 tool_calls 처리
            assistant_dict = _message_to_dict(msg)
            messages.append(assistant_dict)

            for tool_call in native_tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                if debug_chat:
                    _ts_print(f"      [chat] round {round_idx+1}: 도구 실행 {tool_name}(...)", flush=True)
                t0 = time.time()
                result = _execute_tool(tool_name, tool_args)
                if debug_chat:
                    _ts_print(f"      [chat] round {round_idx+1}: 도구 완료 {tool_name} ({time.time()-t0:.1f}s, {len(str(result))} chars)", flush=True)
                tool_events.append({
                    "name": tool_name,
                    "arguments": tool_args,
                    "result": result,
                })

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })
        else:
            # Ollama 폴백: content에서 tool_calls 파싱 시도
            content = getattr(msg, "content", "") or ""
            parsed_calls = _parse_tool_calls_from_content(content)

            if debug_chat:
                _ts_print(f"      [chat] round {round_idx+1}: 응답 {round_elapsed:.1f}s, content 파싱 → tool_calls={len(parsed_calls) if parsed_calls else 0}개", flush=True)

            if parsed_calls:
                # 파싱 성공: tool call로 처리
                # assistant 메시지에 tool_calls를 재구성
                fake_tool_calls = []
                for i, pc in enumerate(parsed_calls):
                    fake_tool_calls.append({
                        "id": f"fallback_{i:03d}",
                        "type": "function",
                        "function": {
                            "name": pc["name"],
                            "arguments": json.dumps(pc["arguments"], ensure_ascii=False),
                        },
                    })

                messages.append({
                    "role": "assistant",
                    "content": "",
                    "tool_calls": fake_tool_calls,
                })

                for i, pc in enumerate(parsed_calls):
                    if debug_chat:
                        _ts_print(f"      [chat] round {round_idx+1}: 도구 실행 {pc['name']}(...)", flush=True)
                    t0 = time.time()
                    result = _execute_tool(pc["name"], pc["arguments"])
                    if debug_chat:
                        _ts_print(f"      [chat] round {round_idx+1}: 도구 완료 {pc['name']} ({time.time()-t0:.1f}s, {len(str(result))} chars)", flush=True)
                    tool_events.append({
                        "name": pc["name"],
                        "arguments": pc["arguments"],
                        "result": result,
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": f"fallback_{i:03d}",
                        "content": result,
                    })
            else:
                # 도구 호출 없이 최종 응답
                if debug_chat:
                    _ts_print(f"      [chat] round {round_idx+1}: 최종 응답 (도구 없음), 종료", flush=True)
                break

    if debug_chat:
        _ts_print(f"      [chat] 총 {len(tool_events)}개 도구 호출 완료", flush=True)
    return tool_events


# ---------------------------------------------------------------------------
# 케이스 로드 / 실행
# ---------------------------------------------------------------------------


def _load_cases(tool_name: str) -> list[dict]:
    """데이터셋 JSON에서 케이스를 로드한다."""
    path = _DATASET_FILES[tool_name]
    if not path.exists():
        logger.warning("데이터셋 파일 없음: %s", path)
        return []
    with open(path, encoding="utf-8") as f:
        cases = json.load(f)

    max_cases = os.environ.get("BENCH_MAX_CASES")
    if max_cases:
        cases = cases[:int(max_cases)]

    return cases


def _run_case_chat(case: dict, model: dict, *, debug_chat: bool = False) -> tuple[list, float, Exception | None]:
    """단일 케이스의 HTTP 호출만 수행 (thread-safe). (tool_events, elapsed, run_exc) 반환."""
    question = case["question"]
    api_key = os.environ.get(model["api_key_env"], "ollama") if model["api_key_env"] else "ollama"
    start = time.time()
    run_exc = None
    try:
        if model["provider"] == "anthropic":
            tool_events = chat_with_anthropic_model(
                question,
                model_name=model["name"],
                api_key=api_key,
                debug_chat=debug_chat,
            )
        else:
            tool_events = chat_with_model(
                question,
                model_name=model["name"],
                base_url=os.environ.get("VLLM_BASE_URL") or model["base_url"],
                api_key=api_key,
                think=model.get("think"),
                debug_chat=debug_chat,
            )
    except Exception as exc:
        logger.warning("케이스 %s 실행 오류 (%s): %s", case.get("id"), model["name"], exc)
        tool_events = []
        run_exc = exc
    elapsed = time.time() - start
    # --tools-lang en: 모델이 영문 파라미터명으로 응답 → 평가 전에 KR로 역변환
    if _TOOLS_LANG_EN:
        from _experiments.scripts.tools_en import EN_KO_PARAM_MAP
        for evt in tool_events:
            args = evt.get("arguments", {})
            evt["arguments"] = {EN_KO_PARAM_MAP.get(k, k): v for k, v in args.items()}
    return tool_events, elapsed, run_exc


def _evaluate_case_result(case: dict, tool_events: list, elapsed: float, run_exc: Exception | None) -> dict:
    """평가 로직 전담 (DuckDB 접근을 포함하므로 단일 스레드에서만 호출)."""
    result = evaluate_case(case, tool_events)
    if run_exc is not None:
        result = normalize_exception_result(result, run_exc)
    result["elapsed_sec"] = round(elapsed, 2)
    return result


def _run_case(case: dict, model: dict, *, debug_chat: bool = False) -> dict:
    """단일 케이스를 실행하고 평가 결과를 반환한다 (단일 스레드 전용)."""
    tool_events, elapsed, run_exc = _run_case_chat(case, model, debug_chat=debug_chat)
    return _evaluate_case_result(case, tool_events, elapsed, run_exc)


# ---------------------------------------------------------------------------
# 모델별 전체 실행
# ---------------------------------------------------------------------------


def run_model_benchmark(
    model: dict,
    output_dir: Path | None = None,
    use_checkpoint: bool = False,
    verbose: bool = False,
    debug_chat: bool = False,
) -> dict:
    """단일 모델에 대해 전체 카테고리를 실행하고 결과를 반환한다.

    Args:
        model: 모델 설정
        output_dir: 결과 저장 디렉토리 (checkpoint 사용 시 필수)
        use_checkpoint: True면 케이스 단위 체크포인트 저장 및 resume
        verbose: True면 케이스별 상세 로그 출력
        debug_chat: True면 모델-도구 대화 흐름 로그 출력

    Returns:
        {
            "model": str,
            "provider": str,
            "timestamp": str,
            "total_cases": int,
            "total_elapsed_sec": float,
            "by_category": {category: {aggregated, per_case}},
            "overall": {aggregated metrics}
        }
    """
    model_id = _model_key(model)
    think_label = ""
    if model.get("think") is True:
        think_label = " [think=ON]"
    elif model.get("think") is False:
        think_label = " [think=OFF]"
    _ts_print(f"\n{'='*60}")
    _ts_print(f"  모델: {model['name']} ({model['provider']}){think_label}")
    _ts_print(f"{'='*60}")

    checkpoint_path = None
    completed: set[tuple[str, str]] = set()
    result_cache: dict[tuple[str, str], dict] = {}
    if use_checkpoint and output_dir:
        checkpoint_path = _get_checkpoint_path(model_id, output_dir)
        completed, result_cache = _load_checkpoint(checkpoint_path)
        if completed:
            _ts_print(f"  [resume] 체크포인트에서 {len(completed)}건 로드")

    all_results = []
    by_category = {}
    total_start = time.time()

    # BENCH_MAX_TOTAL: 모델당 전체 실행 케이스 수 제한 (스모크 테스트용)
    max_total = int(os.environ.get("BENCH_MAX_TOTAL", "0")) or None
    total_executed = 0
    _consecutive_conn_errors = 0
    _CONN_ERROR_THRESHOLD = 10  # 연속 connection error 시 조기 중단

    for cat_name, json_path in _DATASET_FILES.items():
        if max_total and total_executed >= max_total:
            break

        cases = _load_cases(cat_name)
        if not cases:
            _ts_print(f"  [{cat_name}] 데이터셋 없음, 건너뜀")
            continue

        # --case-ids 필터: 지정된 ID만 통과
        if _CASE_ID_FILTER is not None:
            cases = [c for c in cases if c.get("id") in _CASE_ID_FILTER]
            if not cases:
                continue
            _ts_print(f"  [{cat_name}] case-ids 필터 적용: {len(cases)}건")

        if max_total:
            remaining = max_total - total_executed
            cases = cases[:remaining]

        _ts_print(f"  [{cat_name}] {len(cases)}건 실행 중...", flush=True)
        cat_start = time.time()

        concurrency = int(os.environ.get("BENCH_CONCURRENCY", "1") or "1")
        case_results = []
        _server_dead = [False]
        _lock = threading.Lock()
        _err_counter = [0]

        # Thread에서는 HTTP만 (tool_events), 메인 스레드에서 DuckDB 기반 evaluate 수행.
        def _chat_case(idx: int, case: dict):
            case_id_local = case.get("id", f"case_{idx}")
            if _server_dead[0]:
                return {"idx": idx, "case_id": case_id_local, "case": case,
                        "status": "dead", "tool_events": None,
                        "elapsed": 0.0, "run_exc": None}
            key_local = (cat_name, case_id_local)
            if key_local in completed and result_cache and not _FORCE_RERUN:
                return {"idx": idx, "case_id": case_id_local, "case": case,
                        "status": "cached", "cached_result": result_cache[key_local]}
            te, el, exc = _run_case_chat(case, model, debug_chat=debug_chat)
            return {"idx": idx, "case_id": case_id_local, "case": case,
                    "status": "run", "tool_events": te,
                    "elapsed": el, "run_exc": exc}

        def _handle_chat_result(entry: dict) -> None:
            nonlocal total_executed
            cid = entry["case_id"]
            if entry["status"] == "cached":
                result = entry["cached_result"]
                case_results.append(result)
                marker_c = "." if result.get("score", 0) >= 0.5 else "x"
                if verbose:
                    _ts_print(f"    [{cid}] skip (캐시) {marker_c}", flush=True)
                else:
                    print(marker_c, end="", flush=True)
                return
            if entry["status"] == "dead":
                _ts_print(f"    [{cid}] skip (서버 사망)", flush=True)
                return
            # status == "run": evaluate in main thread
            result = _evaluate_case_result(entry["case"], entry["tool_events"],
                                           entry["elapsed"], entry["run_exc"])
            total_executed += 1
            # 서버 사망 신호: connection_error / timeout_error만 카운트
            # api_error (400 BadRequest 포함)는 모델/요청 측 문제이므로 case-level fail로만 기록
            # (이전 로직은 parallel TC 미지원 모델의 400 reject도 합산해 _server_dead 오트리거함)
            if result.get("error_type") in ("connection_error", "timeout_error"):
                _err_counter[0] += 1
                if _err_counter[0] >= _CONN_ERROR_THRESHOLD:
                    _ts_print(
                        f"\n    ⚠️  연속 {_err_counter[0]}건 connection/timeout error — "
                        f"서버 사망으로 판단, 나머지 케이스 스킵",
                        flush=True,
                    )
                    _server_dead[0] = True
                return
            _err_counter[0] = 0
            case_results.append(result)
            if checkpoint_path:
                rec = {
                    "model": model_id,
                    "category": cat_name,
                    "case_id": cid,
                    **result,
                }
                _append_checkpoint(checkpoint_path, rec)
            marker_c = "." if result.get("score", 0) >= 0.5 else "x"
            err_t = result.get("error_type", "")
            if verbose:
                _ts_print(
                    f"    [{cid}] 완료: score={result.get('score', 0):.2f}, "
                    f"{entry['elapsed']:.1f}s, {err_t or 'ok'} {marker_c}",
                    flush=True,
                )
            else:
                _ts_print(f"    [{cid}] 완료: {entry['elapsed']:.1f}s {marker_c}", flush=True)

        if concurrency > 1:
            with ThreadPoolExecutor(max_workers=concurrency) as ex:
                futures = [ex.submit(_chat_case, i, c) for i, c in enumerate(cases)]
                for fut in as_completed(futures):
                    try:
                        entry = fut.result()
                    except Exception as exc:
                        logger.warning("concurrent case 실패: %s", exc)
                        continue
                    _handle_chat_result(entry)
        else:
            for i, case in enumerate(cases):
                entry = _chat_case(i, case)
                _handle_chat_result(entry)

        cat_elapsed = time.time() - cat_start
        agg = aggregate_results(case_results)
        by_category[cat_name] = {
            "aggregated": agg,
            "per_case": case_results,
            "elapsed_sec": round(cat_elapsed, 2),
        }
        all_results.extend(case_results)

        score = agg.get("avg_score", 0)
        threshold = _THRESHOLDS.get(cat_name, 0.75)
        status = "PASS" if score >= threshold else "FAIL"
        _ts_print(f" [{status}] avg={score:.3f} ({cat_elapsed:.1f}s)")

    total_elapsed = time.time() - total_start
    overall = aggregate_results(all_results)

    return {
        "model": model_id,
        "provider": model["provider"],
        "think": model.get("think"),
        "timestamp": datetime.now().isoformat(),
        "total_cases": len(all_results),
        "total_elapsed_sec": round(total_elapsed, 2),
        "by_category": by_category,
        "overall": overall,
    }


# ---------------------------------------------------------------------------
# 케이스 단위 체크포인트 (JSONL append + resume)
# ---------------------------------------------------------------------------


def _get_checkpoint_path(model_name: str, output_dir: Path) -> Path:
    """모델별 체크포인트 JSONL 파일 경로."""
    safe_name = _sanitize_model_name(model_name)
    checkpoint_dir = output_dir / "checkpoint"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    return checkpoint_dir / f"checkpoint_{safe_name}.jsonl"


def _load_checkpoint(checkpoint_path: Path) -> tuple[set[tuple[str, str]], dict[tuple[str, str], dict]]:
    """체크포인트 JSONL을 읽어 완료된 (category, case_id) 집합과 결과 캐시를 반환한다.

    Returns:
        (completed_set, result_cache)
        completed_set: {(category, case_id), ...}
        result_cache: {(category, case_id): result_dict, ...}
    """
    completed = set()
    cache = {}
    if not checkpoint_path.exists():
        return completed, cache

    with open(checkpoint_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                cat = rec.get("category", "")
                case_id = rec.get("case_id", "")
                if not cat or not case_id:
                    continue
                if rec.get("error_type") == "parse_fail":
                    rec = normalize_parse_fail_result(rec)
                key = (cat, case_id)
                completed.add(key)
                # record = {model, category, case_id, **result} → result만 추출
                cache[key] = {
                    k: v for k, v in rec.items()
                    if k not in ("model", "category", "case_id")
                }
            except json.JSONDecodeError:
                continue

    return completed, cache


def _append_checkpoint(checkpoint_path: Path, record: dict) -> None:
    """체크포인트 파일에 JSONL 한 줄 append 후 flush."""
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with open(checkpoint_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()


# ---------------------------------------------------------------------------
# 중간 저장 / 로드
# ---------------------------------------------------------------------------


def _sanitize_model_name(name: str) -> str:
    """모델명을 파일명으로 사용 가능한 형태로 변환한다."""
    return name.replace(":", "_").replace("/", "_").replace(".", "_")


def save_model_result(result: dict, output_dir: Path) -> Path:
    """모델별 결과를 JSON으로 저장한다."""
    eval_dir = output_dir / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _sanitize_model_name(result["model"])
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = eval_dir / f"eval_{safe_name}_{timestamp}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    _ts_print(f"  결과 저장: {path}")
    return path


def load_existing_results(output_dir: Path) -> dict[str, dict]:
    """output_dir에서 가장 최신 모델별 결과를 로드한다.

    Returns:
        {model_name: result_dict}
    """
    existing = {}
    if not output_dir.exists():
        return existing

    eval_dir = output_dir / "eval"
    if not eval_dir.exists():
        eval_dir = output_dir  # fallback for legacy layout
    for path in sorted(eval_dir.glob("eval_*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            model_name = data.get("model", "")
            if model_name:
                existing[model_name] = data
        except (json.JSONDecodeError, KeyError):
            continue

    return existing


# ---------------------------------------------------------------------------
# 비교 리포트 생성
# ---------------------------------------------------------------------------


def build_comparison(results: dict[str, dict]) -> dict:
    """모델별 결과를 비교 리포트로 집계한다.

    Args:
        results: {model_name: run_model_benchmark() 반환값}

    Returns:
        비교 데이터 딕셔너리
    """
    timestamp = datetime.now().isoformat()

    model_summaries = []
    for model_name, result in results.items():
        overall = result.get("overall", {})
        model_summaries.append({
            "model": model_name,
            "provider": result.get("provider", ""),
            "total_cases": result.get("total_cases", 0),
            "avg_score": overall.get("avg_score", 0),
            "primary_tool_hit_rate": overall.get("primary_tool_hit_rate", 0),
            "avg_tool_recall": overall.get("avg_tool_recall", 0),
            "avg_tool_precision": overall.get("avg_tool_precision", 0),
            "avg_param_accuracy": overall.get("avg_param_accuracy", 0),
            "avg_param_key_accuracy": overall.get("avg_param_key_accuracy", 0),
            "total_hallucinated_params": overall.get("total_hallucinated_params", 0),
            "total_elapsed_sec": result.get("total_elapsed_sec", 0),
            "by_error_type": overall.get("by_error_type", {}),
            "by_difficulty": overall.get("by_difficulty", {}),
        })

    # 카테고리별 비교
    all_categories = set()
    for result in results.values():
        all_categories.update(result.get("by_category", {}).keys())
    all_categories = sorted(all_categories)

    category_comparison = {}
    for cat in all_categories:
        cat_data = {}
        for model_name, result in results.items():
            cat_result = result.get("by_category", {}).get(cat, {})
            agg = cat_result.get("aggregated", {})
            cat_data[model_name] = {
                "avg_score": agg.get("avg_score", 0),
                "primary_tool_hit_rate": agg.get("primary_tool_hit_rate", 0),
                "avg_param_accuracy": agg.get("avg_param_accuracy", 0),
                "total": agg.get("total", 0),
                "elapsed_sec": cat_result.get("elapsed_sec", 0),
            }
        category_comparison[cat] = cat_data

    return {
        "timestamp": timestamp,
        "models": list(results.keys()),
        "model_summaries": model_summaries,
        "category_comparison": category_comparison,
    }


# ---------------------------------------------------------------------------
# Excel 비교 리포트
# ---------------------------------------------------------------------------


def _write_model_summary_sheet(ws, comparison: dict) -> None:
    """시트 1: 모델별 요약."""
    ws.title = "모델별 요약"

    # 타이틀
    ws.merge_cells("A1:J1")
    cell = ws["A1"]
    cell.value = "AML 에이전트 다중 모델 벤치마크 비교 결과"
    cell.font = Font(bold=True, size=14, name="맑은 고딕", color="FFFFFF")
    cell.fill = _fill(_COLOR_HEADER_DARK)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    # 메타
    ws.merge_cells("A2:J2")
    ws["A2"].value = f"실행 시각: {comparison['timestamp'][:19]}   |   모델 수: {len(comparison['models'])}개"
    ws["A2"].font = _body_font(size=9)
    ws["A2"].fill = _fill("DAEEF3")
    ws["A2"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 18

    ws.append([])

    # 헤더
    headers = [
        "모델", "Provider", "케이스 수",
        "함수정확도", "파라미터정확도", "종합점수",
        "Tool Recall", "Tool Precision",
        "환각 파라미터", "처리시간(초)",
    ]
    ws.append(headers)
    hdr_row = ws.max_row
    for col_idx in range(1, len(headers) + 1):
        c = ws.cell(row=hdr_row, column=col_idx)
        c.font = _header_font()
        c.fill = _fill(_COLOR_HEADER_BLUE)
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = _thin_border()
    ws.row_dimensions[hdr_row].height = 18

    # 데이터
    for ms in comparison["model_summaries"]:
        row = [
            ms["model"],
            ms["provider"],
            ms["total_cases"],
            ms["primary_tool_hit_rate"],
            ms["avg_param_accuracy"],
            ms["avg_score"],
            ms["avg_tool_recall"],
            ms["avg_tool_precision"],
            ms["total_hallucinated_params"],
            ms["total_elapsed_sec"],
        ]
        ws.append(row)
        r = ws.max_row
        model_color = _COLOR_MODEL_COLORS.get(ms["model"], "FFFFFF")
        for col_idx in range(1, len(row) + 1):
            c = ws.cell(row=r, column=col_idx)
            c.font = _body_font()
            c.fill = _fill(model_color)
            c.border = _thin_border()
            c.alignment = Alignment(horizontal="center", vertical="center")
            if col_idx in (4, 5, 6, 7, 8):
                c.number_format = "0.00%"
        ws.row_dimensions[r].height = 16

    widths = [18, 10, 10, 14, 14, 12, 12, 14, 14, 14]
    for i, w in enumerate(widths, start=1):
        _set_col_width(ws, get_column_letter(i), w)


def _write_category_sheet(ws, comparison: dict) -> None:
    """시트 2: 카테고리별 상세."""
    ws.title = "카테고리별 상세"

    ws.merge_cells("A1:F1")
    ws["A1"].value = "카테고리별 모델 성능 비교"
    ws["A1"].font = Font(bold=True, size=13, name="맑은 고딕", color="FFFFFF")
    ws["A1"].fill = _fill(_COLOR_HEADER_DARK)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 26

    ws.append([])

    models = comparison["models"]
    cat_comp = comparison["category_comparison"]

    # 헤더: 카테고리 | 임계값 | model1_score | model2_score | ...
    headers = ["카테고리", "임계값"] + models
    ws.append(headers)
    hdr_row = ws.max_row
    for col_idx in range(1, len(headers) + 1):
        c = ws.cell(row=hdr_row, column=col_idx)
        c.font = _header_font()
        c.fill = _fill(_COLOR_HEADER_BLUE)
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = _thin_border()
    ws.row_dimensions[hdr_row].height = 18

    for cat_name in sorted(cat_comp.keys()):
        cat_data = cat_comp[cat_name]
        threshold = _THRESHOLDS.get(cat_name, 0.75)
        row = [cat_name, threshold]
        for m in models:
            score = cat_data.get(m, {}).get("avg_score", 0)
            row.append(score)
        ws.append(row)
        r = ws.max_row
        for col_idx in range(1, len(row) + 1):
            c = ws.cell(row=r, column=col_idx)
            c.font = _body_font()
            c.border = _thin_border()
            c.alignment = Alignment(horizontal="center", vertical="center")
            if col_idx >= 2:
                c.number_format = "0.0000"
            if col_idx >= 3:
                val = c.value
                if isinstance(val, (int, float)) and val >= threshold:
                    c.fill = _fill(_COLOR_PASS)
                elif isinstance(val, (int, float)):
                    c.fill = _fill(_COLOR_FAIL)
        ws.row_dimensions[r].height = 16

    widths = [24, 10] + [14] * len(models)
    for i, w in enumerate(widths, start=1):
        _set_col_width(ws, get_column_letter(i), w)


def _write_difficulty_sheet(ws, comparison: dict) -> None:
    """시트 3: 난이도별 분석."""
    ws.title = "난이도별 분석"

    ws.merge_cells("A1:F1")
    ws["A1"].value = "난이도별 모델 성능 비교"
    ws["A1"].font = Font(bold=True, size=13, name="맑은 고딕", color="FFFFFF")
    ws["A1"].fill = _fill(_COLOR_HEADER_DARK)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 26

    ws.append([])

    models = comparison["models"]

    # 헤더
    headers = ["난이도"] + models
    ws.append(headers)
    hdr_row = ws.max_row
    for col_idx in range(1, len(headers) + 1):
        c = ws.cell(row=hdr_row, column=col_idx)
        c.font = _header_font()
        c.fill = _fill(_COLOR_HEADER_BLUE)
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = _thin_border()
    ws.row_dimensions[hdr_row].height = 18

    difficulties = ["easy", "medium", "hard"]
    for diff in difficulties:
        row = [diff]
        for ms in comparison["model_summaries"]:
            by_diff = ms.get("by_difficulty", {})
            diff_data = by_diff.get(diff, {})
            row.append(diff_data.get("avg_score", 0))
        ws.append(row)
        r = ws.max_row
        for col_idx in range(1, len(row) + 1):
            c = ws.cell(row=r, column=col_idx)
            c.font = _body_font()
            c.border = _thin_border()
            c.alignment = Alignment(horizontal="center", vertical="center")
            if col_idx >= 2:
                c.number_format = "0.0000"
        ws.row_dimensions[r].height = 16

    widths = [14] + [14] * len(models)
    for i, w in enumerate(widths, start=1):
        _set_col_width(ws, get_column_letter(i), w)


def _write_error_type_sheet(ws, comparison: dict) -> None:
    """시트 4: 오류 유형 분포."""
    ws.title = "오류 유형 분포"

    ws.merge_cells("A1:F1")
    ws["A1"].value = "오류 유형별 모델 비교"
    ws["A1"].font = Font(bold=True, size=13, name="맑은 고딕", color="FFFFFF")
    ws["A1"].fill = _fill(_COLOR_HEADER_DARK)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 26

    ws.append([])

    models = comparison["models"]
    base_error_types = [
        "correct", "wrong_func", "wrong_value",
        "missing_param", "hallucinated_call",
        "parse_fail", "timeout_error", "connection_error", "api_error", "other",
    ]
    seen = set()
    for ms in comparison["model_summaries"]:
        seen.update(ms.get("by_error_type", {}).keys())
    extra = sorted(et for et in seen if et not in base_error_types)
    error_types = base_error_types + extra

    headers = ["오류 유형"] + models
    ws.append(headers)
    hdr_row = ws.max_row
    for col_idx in range(1, len(headers) + 1):
        c = ws.cell(row=hdr_row, column=col_idx)
        c.font = _header_font()
        c.fill = _fill(_COLOR_HEADER_BLUE)
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = _thin_border()
    ws.row_dimensions[hdr_row].height = 18

    for et in error_types:
        row = [et]
        for ms in comparison["model_summaries"]:
            count = ms.get("by_error_type", {}).get(et, 0)
            row.append(count)
        ws.append(row)
        r = ws.max_row
        for col_idx in range(1, len(row) + 1):
            c = ws.cell(row=r, column=col_idx)
            c.font = _body_font()
            c.border = _thin_border()
            c.alignment = Alignment(horizontal="center", vertical="center")
            if col_idx == 1:
                pass
            elif et == "correct" and col_idx >= 2:
                c.fill = _fill(_COLOR_PASS)
            elif c.value and int(c.value) > 0 and et != "correct":
                c.fill = _fill(_COLOR_FAIL)
        ws.row_dimensions[r].height = 16

    widths = [20] + [14] * len(models)
    for i, w in enumerate(widths, start=1):
        _set_col_width(ws, get_column_letter(i), w)


def export_comparison_excel(comparison: dict, output_path: Path) -> None:
    """비교 리포트를 4-시트 Excel 파일로 내보낸다."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    ws1 = wb.create_sheet()
    ws2 = wb.create_sheet()
    ws3 = wb.create_sheet()
    ws4 = wb.create_sheet()

    _write_model_summary_sheet(ws1, comparison)
    _write_category_sheet(ws2, comparison)
    _write_difficulty_sheet(ws3, comparison)
    _write_error_type_sheet(ws4, comparison)

    for ws in wb.worksheets:
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToPage = True
        ws.page_setup.fitToWidth = 1

    wb.save(output_path)
    _ts_print(f"비교 Excel 저장: {output_path}")


# ---------------------------------------------------------------------------
# DuckDB 설정
# ---------------------------------------------------------------------------


def _setup_db():
    """DuckDB in-memory 패치를 적용한다."""
    import duckdb
    import config
    import src.data.db as db_module

    conn = duckdb.connect(":memory:")
    conn.execute(f"SET threads TO {config.DUCKDB_THREADS}")
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS hofinet AS
        SELECT * FROM read_parquet('{config.PARQUET_PATH.as_posix()}')
    """)
    original_conn = db_module._conn
    db_module._conn = conn
    return conn, original_conn, db_module


# ---------------------------------------------------------------------------
# 콘솔 출력
# ---------------------------------------------------------------------------


def print_comparison_summary(comparison: dict) -> None:
    """비교 결과를 콘솔에 출력한다."""
    _ts_print("\n" + "=" * 70)
    _ts_print("  다중 모델 벤치마크 비교 결과")
    _ts_print("=" * 70)

    _ts_print(f"\n{'모델':<18} {'함수정확도':>10} {'파라미터':>10} {'종합점수':>10} {'환각':>6} {'시간(초)':>10}")
    _ts_print("-" * 70)
    for ms in comparison["model_summaries"]:
        elapsed = ms.get('total_elapsed_sec') or 0.0
        hall = ms.get('total_hallucinated_params') or 0
        _ts_print(
            f"{ms['model']:<18} "
            f"{ms['primary_tool_hit_rate']:>10.1%} "
            f"{ms['avg_param_accuracy']:>10.1%} "
            f"{ms['avg_score']:>10.1%} "
            f"{hall:>6d} "
            f"{elapsed:>10.1f}"
        )
    _ts_print("=" * 70)

    # 카테고리별 요약
    cat_comp = comparison["category_comparison"]
    models = comparison["models"]
    _ts_print(f"\n카테고리별 종합점수:")
    print(f"{'카테고리':<24}", end="")
    for m in models:
        print(f" {m:>14}", end="")
    print()
    _ts_print("-" * (24 + 15 * len(models)))
    for cat in sorted(cat_comp.keys()):
        print(f"{cat:<24}", end="")
        for m in models:
            score = cat_comp[cat].get(m, {}).get("avg_score", 0)
            print(f" {score:>13.1%}", end="")
        print()
    _ts_print("")


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="AML 에이전트 다중 모델 벤치마크 실험"
    )
    parser.add_argument(
        "--output",
        default="_experiments/results/",
        help="결과 저장 디렉토리 (기본: _experiments/results/)",
    )
    parser.add_argument(
        "--models",
        nargs="*",
        default=None,
        help="실행할 모델 이름 (기본: 전체). 예: --models gpt-4o-mini qwen2.5:1.5b",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="이미 결과가 있는 모델은 건너뛰기",
    )
    parser.add_argument(
        "--comparison-only",
        action="store_true",
        help="기존 결과로 비교 리포트만 생성 (모델 실행 안 함)",
    )
    parser.add_argument(
        "--checkpoint",
        action="store_true",
        help="케이스 단위 체크포인트 JSONL 저장. 재실행 시 완료 케이스 skip (진짜 resume)",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        metavar="PATH",
        help="stdout/stderr를 해당 파일로 리다이렉트 (백그라운드 실행용)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="케이스별 상세 로그 (case_id, score, elapsed, error_type)",
    )
    parser.add_argument(
        "--debug-chat",
        action="store_true",
        help="모델-도구 대화 흐름 로그 (API 호출, 도구 실행, 라운드별 진행)",
    )
    parser.add_argument(
        "--cases-dir",
        default=None,
        metavar="PATH",
        help="벤치마크 케이스 디렉토리 (기본: benchmarks/). 한/영 ablation용",
    )
    parser.add_argument(
        "--tools-lang",
        default=None,
        choices=["en"],
        help="도구 정의 언어 변경. 'en'=영문 도구 정의 + 영문 시스템 프롬프트 (도구 정의 언어 ablation용)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="모델 응답 최대 토큰 (기본 4096). 입력 토큰이 서버 max-model-len에 근접하는 케이스에서는 2048로 낮춰 오버플로우 방지.",
    )
    parser.add_argument(
        "--case-ids",
        default=None,
        metavar="ID1,ID2,...",
        help="특정 case ID만 실행 (콤마 구분). HOFINET 정정 등 부분 재실험용. "
             "예: --case-ids mt_006,mt_008,pf_001",
    )
    parser.add_argument(
        "--case-ids-file",
        default=None,
        metavar="PATH",
        help="case ID 목록을 담은 텍스트 파일 (한 줄에 하나) 또는 JSON 배열. "
             "--case-ids보다 우선. 대량 ID 지정용.",
    )
    parser.add_argument(
        "--force-rerun",
        action="store_true",
        help="--checkpoint 모드에서 이미 완료된 case도 재실행 (--case-ids와 함께 사용).",
    )
    args = parser.parse_args()

    # 백그라운드 실행용 로그 리다이렉트
    if args.log_file:
        log_path = Path(args.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_f = open(log_path, "w", encoding="utf-8")
        sys.stdout = log_f
        sys.stderr = log_f

    # --tools-lang: 도구 정의 언어 오버라이드 (도구 정의 언어 ablation)
    if args.tools_lang == "en":
        from _experiments.scripts.tools_en import TOOLS_EN, SYSTEM_PROMPT_EN
        global TOOLS, SYSTEM_PROMPT, _TOOLS_LANG_EN
        TOOLS = TOOLS_EN
        SYSTEM_PROMPT = SYSTEM_PROMPT_EN
        _TOOLS_LANG_EN = True
        _ts_print(f"도구 정의 언어 오버라이드: EN (23개 도구 + 시스템 프롬프트 영문)")

    # --max-tokens: 응답 최대 토큰 오버라이드
    if args.max_tokens != 4096:
        global _MAX_TOKENS
        _MAX_TOKENS = args.max_tokens
        _ts_print(f"max_tokens 오버라이드: {_MAX_TOKENS}")

    # --cases-dir: 벤치마크 케이스 디렉토리 오버라이드 (한/영 ablation)
    if args.cases_dir:
        global _DATASET_DIR, _DATASET_FILES
        _DATASET_DIR = Path(args.cases_dir)
        _DATASET_FILES = {k: _DATASET_DIR / v.name for k, v in _DATASET_FILES.items()}
        _ts_print(f"케이스 디렉토리 오버라이드: {_DATASET_DIR}")

    # --case-ids / --case-ids-file: 특정 ID만 실행 (부분 재실험)
    global _CASE_ID_FILTER, _FORCE_RERUN
    _CASE_ID_FILTER = None
    _FORCE_RERUN = bool(args.force_rerun)
    if args.case_ids_file:
        p = Path(args.case_ids_file)
        raw = p.read_text(encoding="utf-8").strip()
        if raw.startswith("["):
            ids = json.loads(raw)
        else:
            ids = [x.strip() for x in raw.splitlines() if x.strip() and not x.startswith("#")]
        _CASE_ID_FILTER = set(ids)
    elif args.case_ids:
        _CASE_ID_FILTER = {x.strip() for x in args.case_ids.split(",") if x.strip()}
    if _CASE_ID_FILTER:
        _ts_print(f"Case ID 필터: {len(_CASE_ID_FILTER)}건 (force_rerun={_FORCE_RERUN})")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 비교 리포트만 생성
    if args.comparison_only:
        existing = load_existing_results(output_dir)
        if not existing:
            _ts_print("기존 결과 파일이 없습니다.")
            sys.exit(1)
        comparison = build_comparison(existing)
        print_comparison_summary(comparison)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = output_dir / f"comparison_{timestamp}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(comparison, f, ensure_ascii=False, indent=2)
        _ts_print(f"비교 JSON 저장: {json_path}")

        xlsx_path = output_dir / f"comparison_{timestamp}.xlsx"
        export_comparison_excel(comparison, xlsx_path)
        sys.exit(0)

    # 모델 선택: --models로 이름 또는 _model_key 매칭
    if args.models:
        requested = set(args.models)
        selected = [
            m for m in MODELS
            if m["name"] in requested or _model_key(m) in requested
        ]
        if not selected:
            _ts_print(f"유효한 모델 없음. 사용 가능:")
            for m in MODELS:
                _ts_print(f"  {_model_key(m)}")
            sys.exit(1)
    else:
        selected = MODELS

    # BENCH_SKIP_THINK=1: think=True 변형 제외 (thinking ablation 별도 진행 시)
    if os.environ.get("BENCH_SKIP_THINK") == "1":
        before = len(selected)
        selected = [m for m in selected if m.get("think") is not True]
        skipped = before - len(selected)
        if skipped:
            _ts_print(f"[BENCH_SKIP_THINK=1] think=True 변형 {skipped}개 제외")

    # 이미 실행된 모델 건너뛰기
    existing = load_existing_results(output_dir) if args.resume else {}
    if existing:
        _ts_print(f"기존 결과 발견: {list(existing.keys())}")

    # DuckDB 설정
    _ts_print("DuckDB in-memory 연결 설정 중...")
    conn, original_conn, db_module = _setup_db()

    all_results = dict(existing)

    try:
        for model in selected:
            mid = _model_key(model)
            if mid in existing:
                _ts_print(f"\n[건너뜀] {mid} — 기존 결과 사용")
                continue

            # API 키 확인
            if model["api_key_env"]:
                api_key = os.environ.get(model["api_key_env"], "")
                if not api_key:
                    _ts_print(f"\n[건너뜀] {mid} — {model['api_key_env']} 미설정")
                    continue

            result = run_model_benchmark(
                model,
                output_dir=output_dir,
                use_checkpoint=args.checkpoint,
                verbose=args.verbose,
                debug_chat=args.debug_chat,
            )
            save_model_result(result, output_dir)
            all_results[mid] = result

        # 비교 리포트 생성
        if len(all_results) >= 2:
            comparison = build_comparison(all_results)
            print_comparison_summary(comparison)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_path = output_dir / f"comparison_{timestamp}.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(comparison, f, ensure_ascii=False, indent=2)
            _ts_print(f"비교 JSON 저장: {json_path}")

            xlsx_path = output_dir / f"comparison_{timestamp}.xlsx"
            export_comparison_excel(comparison, xlsx_path)
        elif len(all_results) == 1:
            model_name = list(all_results.keys())[0]
            result = all_results[model_name]
            overall = result.get("overall", {})
            _ts_print(f"\n단일 모델 결과: {model_name}")
            _ts_print(f"  종합점수: {overall.get('avg_score', 0):.4f}")
            _ts_print(f"  함수정확도: {overall.get('primary_tool_hit_rate', 0):.4f}")
            _ts_print(f"  파라미터정확도: {overall.get('avg_param_accuracy', 0):.4f}")
        else:
            _ts_print("\n실행된 모델이 없습니다.")

    finally:
        conn.close()
        db_module._conn = original_conn


if __name__ == "__main__":
    main()
