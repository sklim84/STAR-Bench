"""The tool-calling loops that produce Contract 2 records.

`run_case` is the single-turn loop and `run_scenario` the multi-turn one. Both
call the model through `client.ModelClient`, so the reasoning mode, the budgets,
the guards and the fallback parser are the same in both, and both write the same
record shape.

What the loops guarantee, whatever goes wrong:

  * every call the model made before an error is in the record, with its
    arguments and, when it ran, its result (D21, L5-005);
  * an argument that is not a JSON object is recorded and flagged, not dropped
    and not turned into an exception (C2-017);
  * the round count and the reason the loop stopped are recorded (L5-024);
  * the model's own text stays in the history and in the record (C2-010).
"""

from __future__ import annotations

import json
import time
from typing import Callable, Iterable

from .client import ModelClient
from .preflight import TOOL_RESULT_TOKENS, truncate
from .records import CallRecord, ExecutedRecord, RoundRecord, RunRecord

__all__ = ["ToolExecutor", "platform_executor", "run_case", "run_scenario",
           "failed_record", "expected_keys", "MAX_ROUNDS", "MAX_CALLS_PER_ROUND"]

MAX_ROUNDS = 5
MAX_CALLS_PER_ROUND = 8   # L5-024: one case reached 318 calls with no ceiling


ToolExecutor = Callable[[str, dict], str]


def platform_executor() -> ToolExecutor:
    from _experiments.scripts._platform import ensure_platform_on_path
    ensure_platform_on_path()
    from src.features.agent import _execute_tool
    return _execute_tool


def _execute(executor: ToolExecutor, call: CallRecord) -> ExecutedRecord:
    """Runs one call, or records why it could not run."""
    if not isinstance(call.name, str) or not call.name:
        return ExecutedRecord(call.id, call.name, call.arguments, None,
                              {"type": "bad_tool_name", "message": f"{call.name!r}"})
    if not call.args_is_object:
        # A list, a string or null where the schema wants an object. The old code
        # called json.loads(None) and the TypeError took the whole case down.
        return ExecutedRecord(
            call.id, call.name, call.arguments, None,
            {"type": "arguments_not_object",
             "message": f"arguments are {type(call.arguments).__name__}, not an object: "
                        f"{call.arguments_raw[:200]}"})
    try:
        result = executor(call.name, call.arguments)
    except Exception as exc:
        return ExecutedRecord(call.id, call.name, call.arguments, None,
                              {"type": type(exc).__name__, "message": str(exc)[:2000]})
    return ExecutedRecord(call.id, call.name, call.arguments, result, None)


def _tool_content(executed: ExecutedRecord, *, max_tokens: int = TOOL_RESULT_TOKENS) -> str:
    """What the model reads back. The record keeps the full result (L5-012)."""
    if executed.error is not None:
        return json.dumps({"error": executed.error["message"]}, ensure_ascii=False)
    result = executed.result
    text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False,
                                                             default=str)
    text, cut = truncate(text, max_tokens)
    if cut:
        executed.error = {"type": "result_truncated",
                          "message": f"sent to the model truncated to about {max_tokens} tokens"}
    return text


def _round_record(idx: int, result, calls: list[CallRecord],
                  executed: list[ExecutedRecord]) -> RoundRecord:
    return RoundRecord(
        idx=idx, finish_reason=result.finish_reason, content=result.content,
        reasoning_chars=result.reasoning_chars, usage=result.usage,
        tool_calls=calls, executed=executed, error=result.error,
        attempts=result.attempts, elapsed_s=result.elapsed_s,
        provider=result.provider, served_model=result.served_model)


# ---------------------------------------------------------------------------
# Single turn
# ---------------------------------------------------------------------------

def run_case(case: dict, *, client: ModelClient, arm, executor: ToolExecutor,
             run_id: str, config: dict, provenance: dict, query_lang: str,
             max_rounds: int = MAX_ROUNDS,
             max_calls_per_round: int = MAX_CALLS_PER_ROUND) -> RunRecord:
    messages = [{"role": "system", "content": arm.system_prompt},
                {"role": "user", "content": case["question"]}]
    record = RunRecord(run_id=run_id, case_id=case.get("id", ""), setting="single",
                       tools_lang=arm.lang, query_lang=query_lang, config=config,
                       provenance=provenance)
    started = time.time()
    final_text = ""
    stop_reason = "max_rounds"

    for idx in range(max_rounds):
        result = client.round(messages, arm.tools, round_idx=idx)
        calls = list(result.tool_calls)
        capped = False
        if len(calls) > max_calls_per_round:
            calls = calls[:max_calls_per_round]
            capped = True
        executed = [_execute(executor, call) for call in calls]
        round_rec = _round_record(idx, result, calls, executed)
        if capped:
            round_rec.error = round_rec.error or {
                "type": "call_limit", "status": None,
                "message": f"{len(result.tool_calls)} calls in one round; "
                           f"{max_calls_per_round} executed"}
        record.rounds.append(round_rec)

        if result.error is not None and not calls:
            record.error = dict(result.error, round=idx)
            stop_reason = "error"
            break
        if result.content:
            final_text = result.content
        if not calls:
            stop_reason = "length" if result.finish_reason == "length" else "no_tool_call"
            break
        if capped:
            stop_reason = "max_calls"
            record.error = {"type": "call_limit", "message": round_rec.error["message"],
                            "round": idx}
            break
        results = {e.tool_call_id: _tool_content(e) for e in executed}
        messages.extend(client.history_turns(result.assistant_message, calls, results))
    record.final_text = final_text
    record.stop_reason = stop_reason
    record.elapsed_s = time.time() - started
    return record


# ---------------------------------------------------------------------------
# Multi turn
# ---------------------------------------------------------------------------

CLARIFICATION_REPLY = "확인이 필요합니다. 추가 정보를 알려주세요."


def _oracle_turns(turn: dict, turn_no: int) -> list[dict]:
    """Assistant turn plus tool results, built from the gold call of this turn."""
    calls = turn.get("tool_calls") or []
    result = turn.get("tool_result")
    if not calls or result is None:
        # A clarification turn. The history gets a neutral reply, not the gold
        # annotation note, which used to leak the expected behaviour into the
        # conversation (C2-010).
        return [{"role": "assistant", "content": CLARIFICATION_REPLY}]
    payload = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False,
                                                                default=str)
    ids = [_scripted_id(turn_no, i) for i in range(len(calls))]
    assistant = {"role": "assistant", "content": "",
                 "tool_calls": [{"id": ids[i], "type": "function",
                                 "function": {"name": c["name"],
                                              "arguments": json.dumps(c.get("arguments", {}),
                                                                      ensure_ascii=False)}}
                                for i, c in enumerate(calls)]}
    return [assistant] + [{"role": "tool", "tool_call_id": ids[i], "content": payload}
                          for i in range(len(calls))]


def _scripted_id(turn_no: int, index: int) -> str:
    return f"S{int(turn_no):02d}{int(index):02d}".ljust(9, "0")[:9]


def run_scenario(scenario: dict, *, client: ModelClient, arm, executor: ToolExecutor,
                 run_id: str, config: dict, provenance: dict, query_lang: str,
                 setting: str = "oracle",
                 max_calls_per_round: int = MAX_CALLS_PER_ROUND) -> list[RunRecord]:
    """One record per turn. `setting` is 'oracle' (scripted results) or 'e2e'."""
    messages = [{"role": "system", "content": arm.system_prompt}]
    records: list[RunRecord] = []

    for turn in scenario.get("turns", []):
        turn_no = turn.get("turn")
        messages.append({"role": "user", "content": turn["content"]})
        started = time.time()
        record = RunRecord(run_id=run_id, case_id=scenario.get("id", ""), setting=setting,
                           tools_lang=arm.lang, query_lang=query_lang, config=config,
                           provenance=provenance, turn=turn_no)
        result = client.round(messages, arm.tools, round_idx=0)
        calls = list(result.tool_calls)[:max_calls_per_round]
        executed = [_execute(executor, c) for c in calls] if setting == "e2e" else []
        record.rounds.append(_round_record(0, result, calls, executed))
        record.final_text = result.content or ""
        if result.error is not None and not calls:
            record.error = dict(result.error, round=0)
            record.stop_reason = "error"
        elif not calls:
            record.stop_reason = "length" if result.finish_reason == "length" else "no_tool_call"
        else:
            record.stop_reason = "tool_call"
        record.elapsed_s = time.time() - started
        records.append(record)

        if setting == "e2e":
            if calls:
                results = {e.tool_call_id: _tool_content(e) for e in executed}
                messages.extend(client.history_turns(result.assistant_message, calls, results))
            else:
                # The model answered in text. Its own answer goes into the history,
                # not a '(no tool call)' placeholder (C2-010).
                messages.append({"role": "assistant",
                                 "content": result.content or CLARIFICATION_REPLY})
        else:
            messages.extend(_oracle_turns(turn, turn_no))
    return records


def failed_record(case_id: str, error: BaseException, *, run_id: str, setting: str,
                  tools_lang: str, query_lang: str, config: dict, provenance: dict,
                  turn: int | None = None) -> RunRecord:
    """A record for a case whose worker raised before it could build its own.

    A worker failure belongs to its own case: the case still gets a line, with the
    exception on it, and no other worker's record is touched (L5-019).
    """
    return RunRecord(
        run_id=run_id, case_id=case_id, setting=setting, tools_lang=tools_lang,
        query_lang=query_lang, config=config, provenance=provenance, turn=turn,
        rounds=[], final_text="", stop_reason="error",
        error={"type": type(error).__name__, "message": str(error)[:2000], "round": None})


def expected_keys(cases: Iterable[dict], *, multiturn: bool) -> list[str]:
    """The record keys a complete run of these cases produces."""
    keys = []
    for case in cases:
        if multiturn:
            keys.extend(f"{case['id']}#{t.get('turn')}" for t in case.get("turns", []))
        else:
            keys.append(case["id"])
    return keys
