#!/usr/bin/env python
"""OpenRouter(OpenAI 호환) 경유 STAR-Bench 싱글턴 벤치마크.

기존 ``benchmark.py``의 평가·집계·저장 파이프라인을 그대로 import해 재사용하고,
모델 호출만 OpenRouter API(OpenAI 호환)로 수행한다. ``benchmark.py``는 수정하지 않는다.

기존 ``benchmark.py``와의 차이는 단 하나 — 모델을 고정 레지스트리(MODELS)에서 고르는
대신, OpenRouter 모델 ID를 ``--models``로 자유 지정한다(provider="openrouter",
base_url=OpenRouter). thinking 토글(chat_template_kwargs)은 OpenRouter에서 지원되지
않으므로 think=None(plain tool calling)으로 호출한다.

사용 예:
    PYTHONPATH=. python -m _experiments.scripts.benchmark_openrouter \
        --models openai/gpt-4o-mini anthropic/claude-3.5-haiku \
        --output _experiments/results_openrouter/ --checkpoint --resume

    # 영문 도구 정의 / 영문 케이스 (도구 정의 언어 ablation)
    PYTHONPATH=. python -m _experiments.scripts.benchmark_openrouter \
        --models openai/gpt-4o-mini --tools-lang en \
        --cases-dir benchmarks_en/ --output _experiments/results_openrouter_en/ --checkpoint

환경변수:
    OPENROUTER_API_KEY — ``star-bench/.env``에서 자동 로드(이미 export돼 있으면 유지).
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

_THIS = Path(__file__).resolve()
_STARBENCH_ROOT = _THIS.parent.parent.parent              # star-bench/
sys.path.insert(0, str(_STARBENCH_ROOT))                  # PYTHONPATH 보강
# 이 스크립트는 웹 플랫폼 패키지(src.features.agent)에 의존한다(cross-repo).
# 디렉터리명을 하드코딩하지 않고 리졸버로 찾는다 — _platform 참조.
from _experiments.scripts._platform import ensure_platform_on_path  # noqa: E402

ensure_platform_on_path()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _load_dotenv(path: Path) -> None:
    """경량 .env 파서 — 이미 설정된 환경변수는 덮어쓰지 않는다."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


# benchmark.py import 전에 .env 로드(API 키 확보)
_load_dotenv(_STARBENCH_ROOT / ".env")

import _experiments.scripts.benchmark as bench  # noqa: E402


def _make_model(model_id: str) -> dict:
    """OpenRouter 모델 설정 dict. benchmark.py의 dispatch는 provider!=anthropic을
    OpenAI 호환 경로(chat_with_model, base_url 사용)로 보내므로 그대로 동작한다."""
    return {
        "name": model_id,
        "provider": "openrouter",
        "base_url": OPENROUTER_BASE_URL,
        "api_key_env": "OPENROUTER_API_KEY",
        "think": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OpenRouter 경유 STAR-Bench 싱글턴 벤치마크",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--models", nargs="+", required=True,
                        help="OpenRouter 모델 ID (예: openai/gpt-4o-mini "
                             "anthropic/claude-3.5-haiku google/gemini-2.0-flash-001)")
    parser.add_argument("--output", required=True, help="결과 저장 디렉토리")
    parser.add_argument("--cases-dir", default=str(_STARBENCH_ROOT / "benchmarks"),
                        help="벤치마크 케이스 디렉토리 (기본: star-bench/benchmarks, KR)")
    parser.add_argument("--tools-lang", choices=["kr", "en"], default="kr",
                        help="도구 정의 언어 (en이면 영문 도구 + 영문 시스템 프롬프트)")
    parser.add_argument("--checkpoint", action="store_true",
                        help="케이스 단위 체크포인트 저장 및 resume")
    parser.add_argument("--resume", action="store_true",
                        help="이미 결과가 있는 모델은 건너뜀")
    parser.add_argument("--max-tokens", type=int, default=4096,
                        help="응답 최대 토큰 (기본 4096)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--debug-chat", action="store_true",
                        help="모델-도구 대화 흐름 로그 출력")
    args = parser.parse_args()

    if not os.environ.get("OPENROUTER_API_KEY"):
        print("[오류] OPENROUTER_API_KEY 미설정 — star-bench/.env 또는 환경변수를 확인하세요.")
        sys.exit(1)

    # OpenRouter 경로가 VLLM_BASE_URL로 가로채이지 않도록 제거(벤치 dispatch가 우선 사용함)
    os.environ.pop("VLLM_BASE_URL", None)

    # ── benchmark.py 모듈 전역 주입(파이프라인 재사용) ──────────────────────
    if args.tools_lang == "en":
        from _experiments.scripts.tools_en import TOOLS_EN, SYSTEM_PROMPT_EN
        bench.TOOLS = TOOLS_EN
        bench.SYSTEM_PROMPT = SYSTEM_PROMPT_EN
        bench._TOOLS_LANG_EN = True
        bench._ts_print("도구 정의 언어: EN")

    cases_dir = Path(args.cases_dir)
    if not cases_dir.is_absolute():
        cases_dir = (Path.cwd() / cases_dir).resolve()
    bench._DATASET_DIR = cases_dir
    bench._DATASET_FILES = {k: cases_dir / v.name for k, v in bench._DATASET_FILES.items()}
    bench._MAX_TOKENS = args.max_tokens
    bench._CASE_ID_FILTER = None
    bench._FORCE_RERUN = False
    bench._ts_print(f"케이스 디렉토리: {cases_dir}")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    selected = [_make_model(m) for m in args.models]

    existing = bench.load_existing_results(output_dir) if args.resume else {}
    if existing:
        bench._ts_print(f"기존 결과 발견: {list(existing.keys())}")

    bench._ts_print("DuckDB in-memory 연결 설정 중...")
    conn, original_conn, db_module = bench._setup_db()
    all_results = dict(existing)
    try:
        for model in selected:
            mid = bench._model_key(model)
            if mid in existing:
                bench._ts_print(f"\n[건너뜀] {mid} — 기존 결과 사용")
                continue
            bench._ts_print(f"\n{'='*60}\n  OpenRouter 모델: {mid}\n{'='*60}")
            result = bench.run_model_benchmark(
                model,
                output_dir=output_dir,
                use_checkpoint=args.checkpoint,
                verbose=args.verbose,
                debug_chat=args.debug_chat,
            )
            bench.save_model_result(result, output_dir)
            all_results[mid] = result

        # 비교 리포트
        if len(all_results) >= 2:
            comparison = bench.build_comparison(all_results)
            bench.print_comparison_summary(comparison)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_path = output_dir / f"comparison_{ts}.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(comparison, f, ensure_ascii=False, indent=2)
            bench._ts_print(f"비교 JSON 저장: {json_path}")
            bench.export_comparison_excel(comparison, output_dir / f"comparison_{ts}.xlsx")
        elif len(all_results) == 1:
            r = next(iter(all_results.values()))
            ov = r.get("overall", {})
            bench._ts_print(f"\n단일 모델 결과: {list(all_results)[0]}")
            bench._ts_print(f"  종합점수:     {ov.get('avg_score', 0):.4f}")
            bench._ts_print(f"  함수정확도:   {ov.get('primary_tool_hit_rate', 0):.4f}")
            bench._ts_print(f"  파라미터정확도: {ov.get('avg_param_accuracy', 0):.4f}")
        else:
            bench._ts_print("\n실행된 모델이 없습니다.")
    finally:
        conn.close()
        db_module._conn = original_conn


if __name__ == "__main__":
    main()
