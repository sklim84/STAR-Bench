"""벤치마크 평가 로직: tool_events vs. 기대값(ground truth) 비교.

각 케이스에 대해 다음 지표를 계산한다:
- primary_tool_hit: 예상 주도구가 실제 호출되었는지 (bool)
- tool_recall: 기대 도구 집합 중 실제 호출된 비율 (0~1)
- tool_precision: 실제 호출 도구 중 기대 도구 집합에 속하는 비율 (0~1)
- param_accuracy: param_checks 항목 중 통과한 비율 (0~1, 검사 없으면 1.0)
- order_score: tool_order 준수율 (0~1, 미지정이면 1.0)
- score: 가중 종합 점수 (0~1)
- hallucinated_param_count: GT에 없는 파라미터 키를 모델이 생성한 총 수 (int)
- error_type: 실패 원인 분류 (correct/wrong_func/missing_param/wrong_value/hallucinated_call/parse_fail/other)
  parse_fail은 호출자가 설정하며, set 시 normalize_parse_fail_result()로 점수를 0으로 정규화한다.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 가중치 설정
# ---------------------------------------------------------------------------

_WEIGHTS = {
    "primary_tool_hit": 0.30,
    "tool_recall":      0.25,
    "tool_precision":   0.10,
    "param_accuracy":   0.25,
    "order_score":      0.10,
}

# param_checks에서 실제 argument 키가 아닌 메타 체크 키
_SPECIAL_CHECKS = frozenset({"sql_contains", "sql_valid"})
_RANGE_CHECKS = frozenset({"hops_min", "hops_max"})
# 실행 결과(result) 검증용 메타 체크 키
_RESULT_CHECKS = frozenset({"result_contains", "result_row_count_min", "result_row_count_max"})


# ---------------------------------------------------------------------------
# 공개 인터페이스
# ---------------------------------------------------------------------------


def evaluate_case(case: dict, tool_events: list[dict]) -> dict:
    """단일 케이스를 평가하고 지표 딕셔너리를 반환한다.

    Args:
        case: dataset JSON의 케이스 항목
            {
              "id": str,
              "question": str,
              "expected": {
                "primary_tool": str,
                "tools_must_include": [str, ...],
                "tool_order": [str, ...],          # optional
                "param_checks": {tool_name: {...}}  # optional
              },
              "difficulty": str
            }
        tool_events: chat()가 반환한 tool_events
            [{name: str, arguments: dict, result: str}, ...]

    Returns:
        {
          "id": str,
          "difficulty": str,
          "primary_tool_hit": bool,
          "tool_recall": float,
          "tool_precision": float,
          "param_accuracy": float,      # Argument F1 대응: 값까지 일치한 비율
          "param_key_accuracy": float,  # Key F1 대응: 파라미터 키 존재 비율
          "order_score": float,
          "score": float,
          "hallucinated_param_count": int,
          "error_type": str,
          "called_tools": [str, ...],
          "param_check_details": [{"tool": str, "check": str, "passed": bool}, ...]
        }
    """
    expected = case.get("expected", {})
    primary_tool = expected.get("primary_tool", "")
    tools_must_include = expected.get("tools_must_include", [])
    tool_order = expected.get("tool_order", [])
    param_checks = expected.get("param_checks", {})

    # 실제 호출된 도구 목록 (순서 유지)
    called_tools = [ev["name"] for ev in tool_events]
    called_tools_set = set(called_tools)

    # 1. primary_tool_hit
    # Abstain/irrelevance 케이스(primary_tool==""): 도구를 호출하지 않아야 정답
    # 그 외 케이스: 정답 주도구가 실제 호출되었는지
    if primary_tool:
        primary_tool_hit = primary_tool in called_tools_set
    else:
        primary_tool_hit = len(called_tools_set) == 0

    # 2. tool_recall
    if tools_must_include:
        hits = sum(1 for t in tools_must_include if t in called_tools_set)
        tool_recall = hits / len(tools_must_include)
    else:
        tool_recall = 1.0

    # 3. tool_precision
    # Irrelevance 케이스 (primary_tool=="", tools_must_include==[]):
    #   도구를 호출하면 0점, 호출 안 하면 만점
    if called_tools_set and tools_must_include:
        expected_set = set(tools_must_include)
        precision_hits = sum(1 for t in called_tools_set if t in expected_set)
        tool_precision = precision_hits / len(called_tools_set)
    elif not tools_must_include and not primary_tool:
        tool_precision = 0.0 if called_tools_set else 1.0
    else:
        tool_precision = 1.0

    # 4. param_accuracy (Arg F1) + param_key_accuracy (Key F1) + hallucinated_param_count
    param_accuracy, param_key_accuracy, param_details, hallucinated_param_count = _evaluate_params(
        param_checks, tool_events
    )

    # 5. order_score
    order_score = _evaluate_order(tool_order, called_tools) if tool_order else 1.0

    # 6. weighted score
    score = round(
        _WEIGHTS["primary_tool_hit"] * float(primary_tool_hit)
        + _WEIGHTS["tool_recall"] * tool_recall
        + _WEIGHTS["tool_precision"] * tool_precision
        + _WEIGHTS["param_accuracy"] * param_accuracy
        + _WEIGHTS["order_score"] * order_score,
        4,
    )

    # 7. error_type 분류
    error_type = _determine_error_type(
        score=score,
        primary_tool=primary_tool,
        primary_tool_hit=primary_tool_hit,
        tool_recall=tool_recall,
        param_accuracy=param_accuracy,
        called_tools=called_tools,
    )

    return {
        "id": case.get("id", ""),
        "difficulty": case.get("difficulty", ""),
        "primary_tool_hit": primary_tool_hit,
        "tool_recall": round(tool_recall, 4),
        "tool_precision": round(tool_precision, 4),
        "param_accuracy": round(param_accuracy, 4),
        "param_key_accuracy": round(param_key_accuracy, 4),
        "order_score": round(order_score, 4),
        "score": score,
        "hallucinated_param_count": hallucinated_param_count,
        "error_type": error_type,
        "called_tools": called_tools,
        "param_check_details": param_details,
    }


def normalize_parse_fail_result(result: dict) -> dict:
    """파싱 실패 결과를 0점 기준으로 정규화한다.

    parse_fail은 평가 로직이 정상 수행되지 못한 시스템 실패이므로
    도구 미호출 정답(irrelevance/missing-params)처럼 우연히 고득점이
    나오는 것을 방지하기 위해 핵심 지표를 모두 0으로 강제한다.

    Args:
        result: evaluate_case()가 반환한 결과 dict

    Returns:
        parse_fail 기준으로 보정된 결과 dict
    """
    normalized = dict(result)
    normalized.update({
        "primary_tool_hit": False,
        "tool_recall": 0.0,
        "tool_precision": 0.0,
        "param_accuracy": 0.0,
        "param_key_accuracy": 0.0,
        "order_score": 0.0,
        "score": 0.0,
        "error_type": "parse_fail",
        "called_tools": [],
    })
    return normalized


def classify_exception_error_type(exc: Exception) -> str:
    """실행 예외를 벤치마크 error_type으로 분류한다."""
    text = f"{type(exc).__name__} {exc}".lower()

    parse_keywords = [
        "jsondecode", "parser", "parse", "tool call", "tool_call",
        "couldn't extract tool call", "expecting property name",
        "invalid json", "malformed json",
    ]
    if any(k in text for k in parse_keywords):
        return "parse_fail"

    timeout_keywords = ["timeout", "timed out", "deadline exceeded"]
    if any(k in text for k in timeout_keywords):
        return "timeout_error"

    connection_keywords = [
        "connection", "connect", "refused", "reset by peer",
        "broken pipe", "name or service not known", "unreachable",
    ]
    if any(k in text for k in connection_keywords):
        return "connection_error"

    api_keywords = [
        "rate limit", "429", "unauthorized", "401", "forbidden", "403",
        "bad request", "400", "api error", "server error", "internal server error",
        "500", "502", "503", "504",
    ]
    if any(k in text for k in api_keywords):
        return "api_error"

    return "other"


def normalize_exception_result(result: dict, exc: Exception) -> dict:
    """실행 실패 결과를 시스템 오류 기준으로 정규화한다."""
    err = classify_exception_error_type(exc)
    if err == "parse_fail":
        return normalize_parse_fail_result(result)

    normalized = dict(result)
    normalized.update({
        "primary_tool_hit": False,
        "tool_recall": 0.0,
        "tool_precision": 0.0,
        "param_accuracy": 0.0,
        "param_key_accuracy": 0.0,
        "order_score": 0.0,
        "score": 0.0,
        "error_type": err,
        "called_tools": [],
    })
    return normalized


# ---------------------------------------------------------------------------
# 내부 평가 헬퍼
# ---------------------------------------------------------------------------


def _get_expected_arg_keys(checks: dict) -> set[str]:
    """param_checks 키로부터 기대 argument 키 집합을 유도한다.

    - sql_contains / sql_valid → 실제 argument 키는 "sql"
    - hops_min / hops_max     → 실제 argument 키는 "hops"
    - result_*                → argument와 무관 (실행 결과 검증)
    - 나머지 키               → 그대로 argument 키로 사용
    """
    expected: set[str] = set()
    if "sql_contains" in checks or "sql_valid" in checks:
        expected.add("sql")
    if "hops_min" in checks or "hops_max" in checks:
        expected.add("hops")
    for k in checks:
        if k not in _SPECIAL_CHECKS and k not in _RANGE_CHECKS and k not in _RESULT_CHECKS:
            expected.add(k)
    return expected


def _evaluate_params(
    param_checks: dict[str, dict],
    tool_events: list[dict],
) -> tuple[float, float, list[dict], int]:
    """param_checks 항목을 검사하고 (arg_accuracy, key_accuracy, 상세 결과, 할루시네이션 수)를 반환한다.

    param_checks 지원 키:
    - sql_contains: [str, ...]  — SQL 문자열에 모든 키워드가 포함되어야 함
    - sql_valid: bool           — DuckDB 실행 결과에 "error" 키가 없어야 함
    - account_id: int           — arguments["account_id"] == value
    - hops_min: int             — arguments["hops"] >= value
    - hops_max: int             — arguments["hops"] <= value
    - pattern_type: str         — arguments["pattern_type"] == value
    - account_a: int            — arguments["account_a"] == value
    - account_b: int            — arguments["account_b"] == value
    - <기타 파라미터>: any      — arguments[key] == value (exact match)

    Returns:
        (arg_accuracy, key_accuracy, param_check_details, hallucinated_param_count)

        arg_accuracy  (Argument F1 대응): param_checks 항목 중 값까지 일치한 비율 (0~1)
        key_accuracy  (Key F1 대응):      실제 argument 파라미터 키가 존재하는 비율 (0~1).
                      sql_contains / sql_valid 같은 메타 체크 키는 제외하고 집계.
                      도구가 미호출된 경우 0.0.

    주의: hallucinated_param_count는 param_checks에 명시된 도구에 한해서만 집계된다.
          param_checks에 없는 도구의 인자는 검사 대상이 아니다.
    """
    if not param_checks:
        return 1.0, 1.0, [], 0

    # tool_name → [event, ...] 매핑 (같은 도구가 여러 번 호출될 수 있음)
    events_by_tool: dict[str, list[dict]] = {}
    for ev in tool_events:
        events_by_tool.setdefault(ev["name"], []).append(ev)

    total_checks = 0
    passed_checks = 0
    key_total = 0
    key_present = 0
    details: list[dict] = []
    hallucinated_total = 0

    for tool_name, checks in param_checks.items():
        tool_event_list = events_by_tool.get(tool_name, [])
        expected_arg_keys = _get_expected_arg_keys(checks)

        if not tool_event_list:
            # 도구가 전혀 호출되지 않음 — 모든 param_check 실패
            for check_key in checks:
                total_checks += 1
                details.append({"tool": tool_name, "check": check_key, "passed": False,
                                 "reason": "도구 미호출"})
            # key_accuracy도 0으로 카운트 (실제 인자 키가 없으므로)
            actual_arg_keys = {
                k for k in checks
                if k not in _SPECIAL_CHECKS and k not in _RANGE_CHECKS and k not in _RESULT_CHECKS
            }
            key_total += len(actual_arg_keys)
            continue

        # 할루시네이션 파라미터 집계: GT에 없는 argument 키
        for ev in tool_event_list:
            args = ev.get("arguments", {})
            for k in args:
                if k not in expected_arg_keys:
                    hallucinated_total += 1

        # Key F1: 실제 파라미터 키(메타 체크 제외) 존재 여부 집계
        raw_arg_keys = {
            k for k in checks
            if k not in _SPECIAL_CHECKS and k not in _RANGE_CHECKS and k not in _RESULT_CHECKS
        }
        for key in raw_arg_keys:
            key_total += 1
            # 최소 하나의 event에서 해당 키가 존재하면 present
            if any(key in ev.get("arguments", {}) for ev in tool_event_list):
                key_present += 1

        # 각 check를 최소 하나의 event가 통과하면 passed
        for check_key, expected_val in checks.items():
            total_checks += 1
            passed = False
            reason = ""

            for ev in tool_event_list:
                args = ev.get("arguments", {})
                result_str = ev.get("result", "")

                if check_key == "sql_contains":
                    sql = args.get("sql", "")
                    keywords = expected_val if isinstance(expected_val, list) else [expected_val]
                    if all(kw.upper() in sql.upper() for kw in keywords):
                        passed = True
                        break
                    else:
                        missing = [kw for kw in keywords if kw.upper() not in sql.upper()]
                        reason = f"SQL에 누락된 키워드: {missing}"

                elif check_key == "sql_valid":
                    try:
                        result_obj = json.loads(result_str) if result_str else {}
                    except (json.JSONDecodeError, TypeError):
                        result_obj = {}
                    has_error = "error" in result_obj
                    if expected_val and not has_error:
                        passed = True
                        break
                    elif not expected_val and has_error:
                        passed = True
                        break
                    else:
                        reason = f"sql_valid={expected_val} 기대, error={'있음' if has_error else '없음'}"

                elif check_key == "hops_min":
                    hops = args.get("hops", args.get("hops_min", None))
                    if hops is not None and int(hops) >= int(expected_val):
                        passed = True
                        break
                    else:
                        reason = f"hops({hops}) < hops_min({expected_val})"

                elif check_key == "hops_max":
                    hops = args.get("hops", args.get("hops_max", None))
                    if hops is not None and int(hops) <= int(expected_val):
                        passed = True
                        break
                    else:
                        reason = f"hops({hops}) > hops_max({expected_val})"

                elif check_key == "result_contains":
                    keywords = expected_val if isinstance(expected_val, list) else [expected_val]
                    if all(kw in result_str for kw in keywords):
                        passed = True
                        break
                    else:
                        missing = [kw for kw in keywords if kw not in result_str]
                        reason = f"결과에 누락된 키워드: {missing}"

                elif check_key == "result_row_count_min":
                    try:
                        result_obj = json.loads(result_str) if result_str else {}
                    except (json.JSONDecodeError, TypeError):
                        result_obj = {}
                    row_count = 0
                    if "결과" in result_obj:
                        row_count = len(result_obj["결과"]) if isinstance(result_obj["결과"], list) else 0
                    elif "총건수" in result_obj:
                        row_count = int(result_obj["총건수"]) if result_obj["총건수"] is not None else 0
                    if row_count >= int(expected_val):
                        passed = True
                        break
                    else:
                        reason = f"결과 행 수({row_count}) < result_row_count_min({expected_val})"

                elif check_key == "result_row_count_max":
                    try:
                        result_obj = json.loads(result_str) if result_str else {}
                    except (json.JSONDecodeError, TypeError):
                        result_obj = {}
                    row_count = 0
                    if "결과" in result_obj:
                        row_count = len(result_obj["결과"]) if isinstance(result_obj["결과"], list) else 0
                    elif "총건수" in result_obj:
                        row_count = int(result_obj["총건수"]) if result_obj["총건수"] is not None else 0
                    if row_count <= int(expected_val):
                        passed = True
                        break
                    else:
                        reason = f"결과 행 수({row_count}) > result_row_count_max({expected_val})"

                else:
                    # exact match (account_id, pattern_type, account_a/b, 파라미터명)
                    actual = args.get(check_key)
                    if actual is not None and _values_equal(actual, expected_val):
                        passed = True
                        break
                    else:
                        reason = f"{check_key}: 기대={expected_val!r}, 실제={actual!r}"

            if passed:
                passed_checks += 1
            details.append({
                "tool": tool_name,
                "check": check_key,
                "passed": passed,
                "reason": reason if not passed else "",
            })

    arg_accuracy = passed_checks / total_checks if total_checks > 0 else 1.0
    key_accuracy = key_present / key_total if key_total > 0 else 1.0
    return arg_accuracy, key_accuracy, details, hallucinated_total


def _determine_error_type(
    score: float,
    primary_tool: str,
    primary_tool_hit: bool,
    tool_recall: float,
    param_accuracy: float,
    called_tools: list[str],
) -> str:
    """실패 원인을 6-분류 error_type으로 결정한다.

    분류:
    - correct:           score == 1.0 (완전 정답)
    - hallucinated_call: irrelevance 케이스에서 불필요 도구 호출
    - wrong_func:        주 도구를 호출하지 않음
    - missing_param:     주 도구는 호출했지만 필수 도구 일부 미호출 (tool_recall < 1.0)
    - wrong_value:       도구는 모두 호출했지만 파라미터 값 오류
    - parse_fail:        chat() 예외 발생 — 호출자가 직접 오버라이드 (이 함수에서 미처리)
    - other:             기타 (복합적 실패)
    """
    if score == 1.0:
        return "correct"
    # Irrelevance 케이스: primary_tool 없고 도구를 호출한 경우
    if not primary_tool and called_tools:
        return "hallucinated_call"
    if not primary_tool_hit:
        return "wrong_func"
    if tool_recall < 1.0:
        return "missing_param"
    if param_accuracy < 1.0:
        return "wrong_value"
    return "other"


def _evaluate_order(tool_order: list[str], called_tools: list[str]) -> float:
    """tool_order와 called_tools 간의 순서 일치도를 계산한다.

    tool_order에 지정된 도구들이 called_tools에서도 같은 상대적 순서로
    등장하는 비율을 반환한다 (Longest Common Subsequence 기반).
    """
    if not tool_order:
        return 1.0

    # called_tools에서 tool_order에 있는 도구만 필터
    filtered = [t for t in called_tools if t in set(tool_order)]

    if not filtered:
        return 0.0

    # LCS 길이 계산
    lcs_len = _lcs_length(tool_order, filtered)
    return lcs_len / len(tool_order)


def _lcs_length(a: list[str], b: list[str]) -> int:
    """두 리스트의 LCS(최장 공통 부분 수열) 길이를 반환한다."""
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[m][n]


def _values_equal(actual: Any, expected: Any) -> bool:
    """타입 유연하게 두 값을 비교한다 (str/int 혼용 허용)."""
    if actual == expected:
        return True
    try:
        return int(actual) == int(expected)
    except (TypeError, ValueError):
        pass
    try:
        return str(actual).strip() == str(expected).strip()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 집계 유틸리티
# ---------------------------------------------------------------------------


def aggregate_results(results: list[dict]) -> dict:
    """evaluate_case 결과 목록을 집계하여 요약 통계를 반환한다.

    Returns:
        {
          "total": int,
          "avg_score": float,
          "primary_tool_hit_rate": float,
          "avg_tool_recall": float,
          "avg_tool_precision": float,
          "avg_param_accuracy": float,      # Argument F1 대응 (값 정확도)
          "avg_param_key_accuracy": float,  # Key F1 대응 (키 존재 여부)
          "avg_order_score": float,
          "total_hallucinated_params": int,
          "by_difficulty": {easy/medium/hard: {count, avg_score}},
          "by_error_type": {correct/wrong_func/...: count},
        }
    """
    if not results:
        return {}

    n = len(results)
    by_difficulty: dict[str, list[float]] = {}
    by_error_type: dict[str, int] = {}

    totals = {k: 0.0 for k in ["score", "tool_recall", "tool_precision",
                                 "param_accuracy", "param_key_accuracy", "order_score"]}
    primary_hits = 0
    total_hallucinated = 0

    for r in results:
        totals["score"] += r.get("score", 0.0)
        totals["tool_recall"] += r.get("tool_recall", 0.0)
        totals["tool_precision"] += r.get("tool_precision", 0.0)
        totals["param_accuracy"] += r.get("param_accuracy", 0.0)
        totals["param_key_accuracy"] += r.get("param_key_accuracy", 0.0)
        totals["order_score"] += r.get("order_score", 0.0)
        if r.get("primary_tool_hit"):
            primary_hits += 1
        total_hallucinated += r.get("hallucinated_param_count", 0)

        diff = r.get("difficulty", "unknown")
        by_difficulty.setdefault(diff, []).append(r.get("score", 0.0))

        et = r.get("error_type")
        if et is not None:
            by_error_type[et] = by_error_type.get(et, 0) + 1

    return {
        "total": n,
        "avg_score": round(totals["score"] / n, 4),
        "primary_tool_hit_rate": round(primary_hits / n, 4),
        "avg_tool_recall": round(totals["tool_recall"] / n, 4),
        "avg_tool_precision": round(totals["tool_precision"] / n, 4),
        "avg_param_accuracy": round(totals["param_accuracy"] / n, 4),
        "avg_param_key_accuracy": round(totals["param_key_accuracy"] / n, 4),
        "avg_order_score": round(totals["order_score"] / n, 4),
        "total_hallucinated_params": total_hallucinated,
        "by_difficulty": {
            diff: {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 4),
            }
            for diff, scores in by_difficulty.items()
        },
        "by_error_type": by_error_type,
    }
