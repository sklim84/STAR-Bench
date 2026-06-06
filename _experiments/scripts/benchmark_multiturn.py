"""멀티턴 STR 워크플로우 벤치마크 러너.

STR 작성 과정의 멀티턴 시나리오(50건)를 대상으로
LLM 모델의 멀티턴 에이전트 행위능력을 평가한다.

싱글턴 benchmark.py와 동일한 모델 레지스트리·API 클라이언트를 사용하되,
**scripted evaluation** 방식으로 동작한다:
  1. 시스템 프롬프트 + 도구 정의 전송
  2. 턴별 user content → 모델 응답 (1라운드만)
  3. 모델의 tool_calls 평가 (기대 도구·파라미터 비교)
  4. 정답 tool_result를 대화 이력에 주입
  5. 다음 턴으로 반복

사용법:
    # 샘플 3건 스모크 테스트
    python _experiments/scripts/benchmark_multiturn.py --models Qwen/Qwen3.5-4B --debug

    # 특정 모델 실행
    python _experiments/scripts/benchmark_multiturn.py --models Qwen/Qwen3.5-9B

    # vLLM 기본 URL 오버라이드
    VLLM_BASE_URL=http://localhost:11434/v1 python _experiments/scripts/benchmark_multiturn.py --models Qwen/Qwen3.5-4B

환경 변수:
    OPENAI_API_KEY:     OpenAI API 키
    ANTHROPIC_API_KEY:  Anthropic API 키
    VLLM_BASE_URL:      vLLM 서버 URL 오버라이드
    BENCH_TIMEOUT:      API 호출 타임아웃 초 (기본: 300)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import anthropic
from openai import OpenAI

# 프로젝트 루트를 sys.path에 추가
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.features.agent import (  # noqa: E402
    SYSTEM_PROMPT,
    TOOLS,
    _message_to_dict,
)

# benchmark.py에서 공유 유틸리티 import
from _experiments.scripts.benchmark import (  # noqa: E402
    MODELS,
    _model_key,
    _ts_print,
    _API_TIMEOUT,
    _convert_tools_to_anthropic,
    _revert_args_keys,
    _parse_tool_calls_from_content,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 데이터 경로
# ---------------------------------------------------------------------------

_MULTITURN_DIR = _PROJECT_ROOT / "benchmarks_multiturn"


def _load_multiturn_cases() -> list[dict]:
    """멀티턴 벤치마크 케이스를 로드한다."""
    path = _MULTITURN_DIR / "cases_str_workflow.json"
    if not path.exists():
        logger.error("멀티턴 데이터셋 없음: %s", path)
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1-라운드 모델 호출 (도구 실행 없이 tool_calls만 수집)
# ---------------------------------------------------------------------------


def _call_model_single_round(
    messages: list[dict],
    *,
    model_name: str,
    base_url: str | None = None,
    api_key: str = "ollama",
    think: bool | None = None,
    debug: bool = False,
) -> list[dict]:
    """모델에 1회 API 호출하고, tool_calls를 파싱하여 반환한다.

    도구를 실행하지 않는다 (scripted evaluation).

    Returns:
        tool_calls: [{"name": str, "arguments": dict}, ...]
        빈 리스트면 도구 호출 없음 (되묻기 등)
    """
    if base_url:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=_API_TIMEOUT)
    else:
        client = OpenAI(api_key=api_key, timeout=_API_TIMEOUT)

    create_kwargs = dict(
        model=model_name,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        max_completion_tokens=int(os.environ.get("BENCH_MT_MAX_TOKENS", "4096")),
    )
    if not model_name.startswith(("o1", "o3", "o4", "gpt-5")):
        create_kwargs["temperature"] = 0
    if think is not None:
        create_kwargs["extra_body"] = {
            "chat_template_kwargs": {"enable_thinking": think},
        }

    response = client.chat.completions.create(**create_kwargs)
    msg = response.choices[0].message

    # 네이티브 tool_calls
    native_tool_calls = getattr(msg, "tool_calls", None)
    if native_tool_calls:
        result = []
        for tc in native_tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            result.append({"name": tc.function.name, "arguments": args, "_id": tc.id})
        if debug:
            _ts_print(f"        → tool_calls: {[r['name'] for r in result]}")
        return result

    # 폴백: content에서 파싱
    content = getattr(msg, "content", "") or ""
    parsed = _parse_tool_calls_from_content(content)
    if parsed:
        for i, p in enumerate(parsed):
            p["_id"] = f"parsed_{i:03d}"
        if debug:
            _ts_print(f"        → parsed tool_calls: {[p['name'] for p in parsed]}")
        return parsed

    if debug:
        _ts_print("        → no tool_calls (text response)")
    return []


def _call_anthropic_single_round(
    messages: list[dict],
    *,
    model_name: str,
    api_key: str,
    debug: bool = False,
) -> list[dict]:
    """Anthropic API로 1회 호출, tool_calls 반환."""
    client = anthropic.Anthropic(api_key=api_key, timeout=_API_TIMEOUT)
    anthropic_tools = _convert_tools_to_anthropic(TOOLS)

    # Anthropic은 system을 별도 파라미터로
    api_messages = [m for m in messages if m["role"] != "system"]

    response = client.messages.create(
        model=model_name,
        system=SYSTEM_PROMPT,
        messages=api_messages,
        tools=anthropic_tools,
        max_tokens=4096,
        temperature=0,
    )

    tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
    if not tool_use_blocks:
        if debug:
            _ts_print("        → no tool_calls (text response)")
        return []

    result = []
    for block in tool_use_blocks:
        args = block.input if isinstance(block.input, dict) else {}
        args = _revert_args_keys(args)
        result.append({"name": block.name, "arguments": args, "_id": block.id})

    if debug:
        _ts_print(f"        → tool_calls: {[r['name'] for r in result]}")
    return result


# ---------------------------------------------------------------------------
# 턴별 평가
# ---------------------------------------------------------------------------


def _evaluate_turn(expected_turn: dict, actual_tool_calls: list[dict]) -> dict:
    """단일 턴의 tool_calls를 평가한다.

    Returns:
        {
            "turn": int,
            "tool_hit": float,    # 기대 도구를 호출했는지 (0 or 1)
            "param_accuracy": float,  # 파라미터 일치율
            "score": float,       # 가중 합산 점수
            "context_hit": bool | None,  # context_ref 평가 결과
            "clarification_hit": bool | None,  # 되묻기 평가 결과
        }
    """
    expected_calls = expected_turn.get("tool_calls", [])
    expect_clarification = expected_turn.get("expect_clarification", False)
    context_ref = expected_turn.get("context_ref")

    # ── 되묻기 턴 평가 ──
    if expect_clarification:
        # 도구를 호출하지 않아야 정답
        hit = 1.0 if len(actual_tool_calls) == 0 else 0.0
        return {
            "turn": expected_turn["turn"],
            "tool_hit": hit,
            "param_accuracy": hit,
            "score": hit,
            "context_hit": None,
            "clarification_hit": hit == 1.0,
        }

    # ── 도구 호출 턴 평가 ──
    # 복수 정답 지원: tool_calls_alt가 있으면 두 정답 중 높은 점수 채택
    alt_calls = expected_turn.get("tool_calls_alt")
    if alt_calls and expected_calls:
        # 두 정답 후보로 각각 평가하여 높은 쪽 선택
        result_primary = _evaluate_tool_calls(expected_turn, expected_calls, actual_tool_calls, context_ref)
        result_alt = _evaluate_tool_calls(expected_turn, alt_calls, actual_tool_calls, context_ref)
        return result_primary if result_primary["score"] >= result_alt["score"] else result_alt

    if not expected_calls:
        return {
            "turn": expected_turn["turn"],
            "tool_hit": 1.0 if len(actual_tool_calls) == 0 else 0.0,
            "param_accuracy": 1.0,
            "score": 1.0 if len(actual_tool_calls) == 0 else 0.0,
            "context_hit": None,
            "clarification_hit": None,
        }

    return _evaluate_tool_calls(expected_turn, expected_calls, actual_tool_calls, context_ref)


def _evaluate_tool_calls(
    expected_turn: dict,
    expected_calls: list[dict],
    actual_tool_calls: list[dict],
    context_ref: dict | None,
) -> dict:
    """기대 tool_calls와 실제 tool_calls를 비교 평가한다."""
    # 기대 도구 이름 집합
    expected_names = {tc["name"] for tc in expected_calls}
    actual_names = {tc["name"] for tc in actual_tool_calls}

    # tool_hit: 기대 도구를 모두 호출했는지
    if expected_names:
        tool_hit = len(expected_names & actual_names) / len(expected_names)
    else:
        tool_hit = 1.0

    # param_accuracy: 매칭된 도구의 파라미터 정확도
    param_scores = []
    for exp_tc in expected_calls:
        # 같은 이름의 actual tool_call 찾기
        matched = [a for a in actual_tool_calls if a["name"] == exp_tc["name"]]
        if not matched:
            param_scores.append(0.0)
            continue

        actual_args = matched[0]["arguments"]
        exp_args = exp_tc.get("arguments", {})

        if not exp_args:
            param_scores.append(1.0)
            continue

        # sql_contains 특수 처리
        if "sql_contains" in exp_args:
            sql_keywords = exp_args["sql_contains"]
            # actual에서 SQL 관련 파라미터 찾기
            actual_sql = actual_args.get("sql", actual_args.get("query", ""))
            if isinstance(actual_sql, str) and sql_keywords:
                matches = sum(1 for kw in sql_keywords if kw in actual_sql)
                param_scores.append(matches / len(sql_keywords))
            else:
                param_scores.append(0.0)
            continue

        # 일반 파라미터 비교
        match_count = 0
        total_keys = 0
        for key, expected_val in exp_args.items():
            if key in ("sql_valid",):  # 메타 키 스킵
                continue
            total_keys += 1
            actual_val = actual_args.get(key)
            if actual_val is not None and _values_match(expected_val, actual_val):
                match_count += 1

        if total_keys > 0:
            param_scores.append(match_count / total_keys)
        else:
            param_scores.append(1.0)

    param_accuracy = sum(param_scores) / len(param_scores) if param_scores else 0.0

    # context_ref 평가
    context_hit = None
    if context_ref:
        to_param = context_ref.get("to_param", "")
        expected_val = None
        for exp_tc in expected_calls:
            expected_val = exp_tc.get("arguments", {}).get(to_param)
            if expected_val is not None:
                break

        if expected_val is not None:
            # actual에서 해당 파라미터 값 확인
            actual_val = None
            for a_tc in actual_tool_calls:
                actual_val = a_tc.get("arguments", {}).get(to_param)
                if actual_val is not None:
                    break
            context_hit = _values_match(expected_val, actual_val) if actual_val is not None else False

    # 종합 점수 (싱글턴과 유사한 가중합)
    score = 0.50 * tool_hit + 0.50 * param_accuracy

    return {
        "turn": expected_turn["turn"],
        "tool_hit": round(tool_hit, 4),
        "param_accuracy": round(param_accuracy, 4),
        "score": round(score, 4),
        "context_hit": context_hit,
        "clarification_hit": None,
    }


def _values_match(expected, actual) -> bool:
    """두 값이 일치하는지 유연하게 비교한다."""
    if expected == actual:
        return True
    # 숫자 비교 (int/float 호환)
    try:
        if abs(float(expected) - float(actual)) < 0.01:
            return True
    except (TypeError, ValueError):
        pass
    # 문자열 비교 (strip)
    if str(expected).strip() == str(actual).strip():
        return True
    return False


# ---------------------------------------------------------------------------
# 시나리오 실행
# ---------------------------------------------------------------------------


def run_multiturn_scenario(
    scenario: dict,
    model: dict,
    *,
    debug: bool = False,
) -> dict:
    """단일 멀티턴 시나리오를 실행하고 평가한다.

    Returns:
        {
            "id": str,
            "scenario": str,
            "sub_category": str,
            "turns": [turn_result, ...],
            "avg_score": float,
            "avg_tool_hit": float,
            "avg_param_accuracy": float,
            "context_accuracy": float | null,
            "scenario_complete": bool,
            "elapsed_sec": float,
        }
    """
    model_name = model["name"]
    api_key = os.environ.get(model["api_key_env"], "ollama") if model["api_key_env"] else "ollama"
    is_anthropic = model["provider"] == "anthropic"

    if debug:
        _ts_print(f"    시나리오: {scenario['id']} ({scenario['sub_category']}) - {len(scenario['turns'])}턴")

    # 대화 이력 초기화
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    turn_results = []
    start = time.time()

    for turn in scenario["turns"]:
        turn_num = turn["turn"]
        user_content = turn["content"]

        if debug:
            _ts_print(f"      턴{turn_num}: \"{user_content[:50]}...\"")

        # 사용자 메시지 추가
        messages.append({"role": "user", "content": user_content})

        # 모델 호출 (1라운드)
        try:
            if is_anthropic:
                actual_tool_calls = _call_anthropic_single_round(
                    messages,
                    model_name=model_name,
                    api_key=api_key,
                    debug=debug,
                )
            else:
                actual_tool_calls = _call_model_single_round(
                    messages,
                    model_name=model_name,
                    base_url=os.environ.get("VLLM_BASE_URL") or model.get("base_url"),
                    api_key=api_key,
                    think=model.get("think"),
                    debug=debug,
                )
        except Exception as exc:
            logger.warning("턴%d 실행 오류 (%s): %s", turn_num, model_name, exc)
            actual_tool_calls = []

        # 평가
        turn_result = _evaluate_turn(turn, actual_tool_calls)
        # STR 생성 품질 분석(필드 충족/할루시네이션/grounding)용 원본 보존:
        # 모델이 실제 생성한 tool_calls(특히 generate_str의 summary 등 arguments)를 기록한다.
        # 평가 점수만 저장하던 기존 동작은 그대로 유지하고, 분석용 raw 필드만 추가.
        turn_result["actual_tool_calls"] = actual_tool_calls
        turn_results.append(turn_result)

        # 대화 이력에 scripted 응답 주입
        _inject_scripted_response(messages, turn, actual_tool_calls)

    elapsed = time.time() - start

    # 시나리오 종합 메트릭
    scores = [t["score"] for t in turn_results]
    tool_hits = [t["tool_hit"] for t in turn_results]
    param_accs = [t["param_accuracy"] for t in turn_results]
    context_hits = [t["context_hit"] for t in turn_results if t["context_hit"] is not None]

    result = {
        "id": scenario["id"],
        "scenario": scenario["scenario"],
        "sub_category": scenario["sub_category"],
        "fraud_type": scenario.get("fraud_type"),
        "num_turns": len(scenario["turns"]),
        "turns": turn_results,
        "avg_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "avg_tool_hit": round(sum(tool_hits) / len(tool_hits), 4) if tool_hits else 0.0,
        "avg_param_accuracy": round(sum(param_accs) / len(param_accs), 4) if param_accs else 0.0,
        "context_accuracy": round(sum(1 for c in context_hits if c) / len(context_hits), 4) if context_hits else None,
        "scenario_complete": all(s > 0.5 for s in scores),
        "elapsed_sec": round(elapsed, 2),
    }

    if debug:
        _ts_print(f"      → avg_s={result['avg_score']:.3f}, ctx={result['context_accuracy']}, complete={result['scenario_complete']}")

    return result


def _inject_scripted_response(
    messages: list[dict],
    turn: dict,
    actual_tool_calls: list[dict],
) -> None:
    """대화 이력에 scripted tool_result를 주입한다.

    모델이 실제로 어떤 도구를 호출했든, 정답 tool_result를 주입하여
    다음 턴이 올바른 문맥에서 진행되도록 한다.
    """
    expected_calls = turn.get("tool_calls", [])
    tool_result = turn.get("tool_result")

    if not expected_calls or tool_result is None:
        # 되묻기 턴: assistant text 응답 주입
        messages.append({
            "role": "assistant",
            "content": turn.get("note", "추가 정보가 필요합니다."),
        })
        return

    # assistant tool_calls 메시지
    tc_list = []
    for i, exp_tc in enumerate(expected_calls):
        tc_id = f"scripted_{turn['turn']}_{i:03d}"
        tc_list.append({
            "id": tc_id,
            "type": "function",
            "function": {
                "name": exp_tc["name"],
                "arguments": json.dumps(exp_tc.get("arguments", {}), ensure_ascii=False),
            },
        })

    messages.append({
        "role": "assistant",
        "content": "",
        "tool_calls": tc_list,
    })

    # tool result 메시지 (각 tool_call에 대해)
    result_str = json.dumps(tool_result, ensure_ascii=False)
    for i, _ in enumerate(expected_calls):
        tc_id = f"scripted_{turn['turn']}_{i:03d}"
        messages.append({
            "role": "tool",
            "tool_call_id": tc_id,
            "content": result_str,
        })


# ---------------------------------------------------------------------------
# 전체 실행
# ---------------------------------------------------------------------------


def _multiturn_result_path(model_id: str, output_dir: Path) -> Path:
    """모델별 최종 결과 JSON 경로 (output_dir/eval/multiturn_<model>.json).

    benchmark.py 싱글턴 결과(`eval/eval_<model>_<ts>.json`)와 일관되게 eval/ 하위에 저장한다.
    """
    sanitized = model_id.replace("/", "_").replace(".", "_")
    eval_dir = output_dir / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    return eval_dir / f"multiturn_{sanitized}.json"


def _multiturn_checkpoint_path(model_id: str, output_dir: Path) -> Path:
    """모델별 시나리오 단위 checkpoint jsonl 경로."""
    sanitized = model_id.replace("/", "_").replace(".", "_")
    cp_dir = output_dir / "checkpoint"
    cp_dir.mkdir(parents=True, exist_ok=True)
    return cp_dir / f"checkpoint_{sanitized}.jsonl"


def _load_multiturn_checkpoint(cp_path: Path) -> tuple[set[str], list[dict]]:
    """checkpoint jsonl 로드 → (완료 시나리오 ID set, 결과 list)."""
    completed_ids: set[str] = set()
    cached_results: list[dict] = []
    if not cp_path.exists():
        return completed_ids, cached_results
    with open(cp_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            sid = rec.get("id")
            if sid and sid not in completed_ids:
                completed_ids.add(sid)
                cached_results.append(rec)
    return completed_ids, cached_results


def _append_multiturn_checkpoint(cp_path: Path, record: dict) -> None:
    """시나리오 결과 한 건을 checkpoint jsonl에 append."""
    cp_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cp_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_multiturn_benchmark(
    model: dict,
    output_dir: Path,
    *,
    debug: bool = False,
    use_checkpoint: bool = False,
    resume: bool = False,
    force_rerun: bool = False,
) -> dict:
    """단일 모델에 대해 전체 멀티턴 시나리오를 실행한다.

    Args:
        use_checkpoint: True면 시나리오 단위 jsonl 저장 + 끊긴 시점부터 재개.
        resume: True면 이미 multiturn_<model>.json이 존재할 때 통째 스킵.
        force_rerun: True면 모델/시나리오 cache 모두 우회하고 재실행.
    """
    model_id = _model_key(model)
    think_label = ""
    if model.get("think") is True:
        think_label = " [think=ON]"
    elif model.get("think") is False:
        think_label = " [think=OFF]"

    _ts_print(f"\n{'='*60}")
    _ts_print(f"  [멀티턴] 모델: {model['name']} ({model['provider']}){think_label}")
    _ts_print(f"{'='*60}")

    # 모델 레벨 resume: 최종 결과 JSON 존재 시 스킵
    result_path = _multiturn_result_path(model_id, output_dir)
    if resume and result_path.exists():
        _ts_print(f"  [건너뜀] {model_id} — 기존 결과 사용 ({result_path.name})")
        try:
            with open(result_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    cases = _load_multiturn_cases()
    if not cases:
        _ts_print("  ⚠ 멀티턴 케이스 없음")
        return {}

    # 시나리오 레벨 checkpoint 로드
    cp_path: Path | None = None
    completed_ids: set[str] = set()
    scenario_results: list[dict] = []
    if use_checkpoint:
        cp_path = _multiturn_checkpoint_path(model_id, output_dir)
        completed_ids, scenario_results = _load_multiturn_checkpoint(cp_path)
        if force_rerun and completed_ids:
            _ts_print(f"  [force-rerun] checkpoint {len(completed_ids)}건 무시")
            completed_ids = set()
            scenario_results = []
        elif completed_ids:
            _ts_print(f"  [재개] checkpoint에서 완료 {len(completed_ids)}건 로드")

    _ts_print(f"  시나리오: {len(cases)}건 (남은: {len(cases) - len(completed_ids)}건)")

    total_start = time.time()

    for i, scenario in enumerate(cases):
        sid = scenario.get("id", "")
        if sid in completed_ids:
            continue
        result = run_multiturn_scenario(scenario, model, debug=debug)
        scenario_results.append(result)
        if cp_path is not None:
            _append_multiturn_checkpoint(cp_path, result)
        _ts_print(
            f"  [{i+1}/{len(cases)}] {scenario['id']}: "
            f"s={result['avg_score']:.3f} h={result['avg_tool_hit']:.3f} "
            f"a={result['avg_param_accuracy']:.3f} "
            f"ctx={result['context_accuracy']} "
            f"({result['elapsed_sec']:.1f}s)"
        )

    total_elapsed = time.time() - total_start

    # 전체 종합
    all_scores = [r["avg_score"] for r in scenario_results]
    all_hits = [r["avg_tool_hit"] for r in scenario_results]
    all_params = [r["avg_param_accuracy"] for r in scenario_results]
    ctx_vals = [r["context_accuracy"] for r in scenario_results if r["context_accuracy"] is not None]
    complete_count = sum(1 for r in scenario_results if r["scenario_complete"])

    overall = {
        "model": model["name"],
        "model_id": model_id,
        "provider": model["provider"],
        "think": model.get("think"),
        "timestamp": datetime.now().isoformat(),
        "total_scenarios": len(cases),
        "total_elapsed_sec": round(total_elapsed, 2),
        "overall": {
            "avg_score": round(sum(all_scores) / len(all_scores), 4) if all_scores else 0.0,
            "avg_tool_hit": round(sum(all_hits) / len(all_hits), 4) if all_hits else 0.0,
            "avg_param_accuracy": round(sum(all_params) / len(all_params), 4) if all_params else 0.0,
            "context_accuracy": round(sum(ctx_vals) / len(ctx_vals), 4) if ctx_vals else None,
            "scenario_complete_rate": round(complete_count / len(cases), 4) if cases else 0.0,
        },
        "by_sub_category": _aggregate_by_subcategory(scenario_results),
        "scenarios": scenario_results,
    }

    # 결과 저장
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = result_path  # 위에서 _multiturn_result_path()로 미리 산출
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(overall, f, ensure_ascii=False, indent=2)

    _ts_print(f"\n  종합: avg_s={overall['overall']['avg_score']:.3f}, "
              f"ctx={overall['overall']['context_accuracy']}, "
              f"complete={complete_count}/{len(cases)}")
    _ts_print(f"  결과 저장: {out_path}")

    return overall


def _aggregate_by_subcategory(results: list[dict]) -> dict:
    """sub_category별 집계."""
    cats: dict[str, list[dict]] = {}
    for r in results:
        cat = r["sub_category"]
        cats.setdefault(cat, []).append(r)

    agg = {}
    for cat, items in cats.items():
        scores = [r["avg_score"] for r in items]
        agg[cat] = {
            "count": len(items),
            "avg_score": round(sum(scores) / len(scores), 4),
            "complete_rate": round(sum(1 for r in items if r["scenario_complete"]) / len(items), 4),
        }
    return agg


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="멀티턴 STR 워크플로우 벤치마크")
    parser.add_argument("--models", nargs="+", help="실행할 모델 이름 (MODELS 레지스트리 기준)")
    parser.add_argument("--output", type=str, default="_experiments/results_mt/",
                        help="결과 저장 디렉토리")
    parser.add_argument("--cases-dir", type=str, default=None,
                        help="멀티턴 케이스 디렉토리 오버라이드(cases_str_workflow.json 포함). "
                             "한/영 ablation 예: --cases-dir benchmarks_multiturn_en "
                             "(이 경우 --output _experiments/results_mt_en/ 권장)")
    parser.add_argument("--debug", action="store_true", help="턴별 상세 로그")
    parser.add_argument("--checkpoint", action="store_true",
                        help="시나리오 단위 checkpoint jsonl 저장 + 중단 시 재개")
    parser.add_argument("--resume", action="store_true",
                        help="이미 multiturn_<model>.json 결과가 있는 모델은 건너뛰기")
    parser.add_argument("--force-rerun", action="store_true",
                        help="--checkpoint 모드에서 이미 완료된 시나리오도 재실행. "
                             "--resume 모델 단위 skip도 우회.")
    args = parser.parse_args()

    # --cases-dir: 멀티턴 케이스 디렉토리 오버라이드 (한/영 ablation). 싱글턴 benchmark.py와 동일 패턴.
    if args.cases_dir:
        global _MULTITURN_DIR
        _MULTITURN_DIR = Path(args.cases_dir)
        _ts_print(f"멀티턴 케이스 디렉토리 오버라이드: {_MULTITURN_DIR}")

    output_dir = Path(args.output)

    # 모델 필터링
    if args.models:
        selected = []
        for m in MODELS:
            if m["name"] in args.models or _model_key(m) in args.models:
                selected.append(m)
        if not selected:
            print(f"일치하는 모델 없음: {args.models}")
            print(f"사용 가능: {[m['name'] for m in MODELS[:10]]}...")
            return
    else:
        selected = MODELS

    _ts_print(f"멀티턴 벤치마크 시작: {len(selected)}개 모델")

    for model in selected:
        try:
            run_multiturn_benchmark(
                model,
                output_dir,
                debug=args.debug,
                use_checkpoint=args.checkpoint,
                resume=args.resume and not args.force_rerun,
                force_rerun=args.force_rerun,
            )
        except Exception as exc:
            _ts_print(f"  ⚠ 모델 {model['name']} 실행 실패: {exc}")
            logger.exception("모델 %s 실패", model["name"])


if __name__ == "__main__":
    main()
