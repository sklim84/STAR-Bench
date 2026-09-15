"""Shared fixtures for the scoring tests. No model, no API, no GPU."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from _experiments.scripts.scoring.score_runs import build_context  # noqa: E402


@pytest.fixture(scope="session")
def ctx():
    """Scoring context with the platform tool schema, catalog and SQL executor."""
    return build_context()


@pytest.fixture(scope="session")
def ctx_no_exec():
    return build_context(execute_sql=False)


@pytest.fixture(scope="session")
def sql_execution(ctx):
    """Whether the platform query database can actually run SQL here."""
    from _experiments.scripts.scoring.sql import result_is_error

    try:
        return not result_is_error(ctx.executor.run("SELECT 1 AS n"))
    except Exception:
        return False


def call(name, arguments=None, *, call_id=None, result=None, error=None, source="native",
         valid_json=True, raw=None):
    """One Contract 2 tool call, optionally with its executed result."""
    call_id = call_id or f"c{abs(hash((name, json.dumps(arguments, default=str, sort_keys=True)))) % 10000}"
    tc = {"id": call_id, "name": name, "arguments": arguments,
          "arguments_raw": raw if raw is not None else json.dumps(arguments, ensure_ascii=False, default=str),
          "source": source, "valid_json": valid_json}
    ex = None
    if result is not None or error is not None:
        ex = {"tool_call_id": call_id, "name": name, "arguments": arguments,
              "result": result if isinstance(result, str) or result is None else json.dumps(result, ensure_ascii=False),
              "error": error}
    return tc, ex


def record(calls=(), *, final_text="Here is the answer.", case_id="case", run_id="run",
           rounds=None, error=None, stop_reason=None, setting="single", turn=None):
    """Contract 2 run record. ``calls`` is a list of ``call()`` results or a list of such lists (one per round)."""
    if rounds is None:
        groups = calls if calls and isinstance(calls[0], list) else [list(calls)]
        rounds = []
        for idx, group in enumerate(groups):
            tool_calls = [tc for tc, _ in group]
            executed = [ex for _, ex in group if ex is not None]
            rounds.append({"idx": idx, "finish_reason": "tool_calls" if tool_calls else "stop",
                           "content": "", "tool_calls": tool_calls, "executed": executed, "error": None})
    rec = {"run_id": run_id, "case_id": case_id, "setting": setting, "rounds": rounds,
           "final_text": final_text, "stop_reason": stop_reason, "error": error}
    if turn is not None:
        rec["turn"] = turn
    return rec


def case(primary, tools=None, checks=None, order=None, *, case_id="case", alternatives=None,
         clarification=False, reference_sql=None):
    """Contract 1 single-turn case."""
    expected = {"primary_tool": primary or "", "tools_must_include": list(tools or ([primary] if primary else []))}
    if checks:
        expected["param_checks"] = checks
    if order:
        expected["tool_order"] = order
    if alternatives:
        expected["alternatives"] = alternatives
    if clarification:
        expected["expect_clarification"] = True
    if reference_sql:
        expected["reference_calls"] = {"query_transactions": {"sql": reference_sql}}
    return {"id": case_id, "question": "q", "expected": expected, "difficulty": "easy"}


def turn(number, tool_calls=None, *, context_ref=None, tool_result=None, clarification=False, alt=None):
    """Multi-turn gold turn."""
    out = {"turn": number, "content": "u", "tool_calls": list(tool_calls or []), "tool_result": tool_result}
    if context_ref:
        out["context_ref"] = context_ref
    if clarification:
        out["expect_clarification"] = True
    if alt:
        out["tool_calls_alt"] = alt
    return out
