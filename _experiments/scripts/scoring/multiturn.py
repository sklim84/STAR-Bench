"""Multi-turn scoring: one scenario against the run records of its turns.

Oracle and end-to-end differ in one place only: where a ``context_ref`` value
comes from. Oracle reads it from the gold ``tool_result`` that was injected into
the history; end-to-end reads it from the run's OWN executed result for the
source turn, and marks the reference not-applicable when that turn produced no
usable result. Everything else uses the single-turn comparison module.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .compare import EXCLUDED_ARGS, SQL_CHECKS, ScoringContext, match_specs
from .metrics import param_accuracy, tool_metrics
from .records import Call, RunView, answer_text_ok, is_unparsed_tool_call, view_record
from .single import Candidate, _error_type, _rank
from .sql import literal_equal, result_is_error

SQL_PARAMS = {"sql", "sql_contains", "sql_conditions"}
_PATH = re.compile(r"\[(\d+)\]|([^.\[\]]+)")


def resolve_path(obj: Any, key: str) -> tuple[Any, bool]:
    """Resolve 'a.b[0].c' (or a literal top-level key) inside a tool result."""
    if isinstance(obj, dict) and key in obj:
        return obj[key], True
    cur = obj
    for idx, name in _PATH.findall(key):
        if idx:
            if not isinstance(cur, list) or int(idx) >= len(cur):
                return None, False
            cur = cur[int(idx)]
        else:
            if isinstance(cur, dict) and name in cur:
                cur = cur[name]
            elif isinstance(cur, dict) and isinstance(cur.get("result"), list):
                return resolve_path(cur["result"], key)  # query_transactions wraps rows in "result"
            elif isinstance(cur, list) and name == "result":
                continue
            else:
                return None, False
    return cur, True


def _parse_result(text: Any) -> Any:
    if isinstance(text, str):
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return None
    return text


def _resolve_from_run(source_view: RunView, key: str, gold_tools: list[str]) -> tuple[Any, bool, str]:
    done = [(c.name, c.executed) for c in source_view.calls if c.executed]
    if not done:
        return None, False, "source turn executed no tool"
    ordered = ([e for name, e in done if name in gold_tools] + [e for name, e in done if name not in gold_tools])
    for ex in ordered:
        if ex.get("error") is not None:
            continue
        obj = _parse_result(ex.get("result"))
        if obj is None or result_is_error(ex.get("result")):
            continue
        value, ok = resolve_path(obj, key)
        if ok and value is not None:
            return value, True, ""
    return None, False, f"no executed result carries {key!r}"


def turn_candidates(turn: dict) -> list[Candidate]:
    out: list[Candidate] = []
    if turn.get("expect_clarification"):
        out.append(Candidate("primary", "clarification", [], [], []))
    elif not turn.get("tool_calls"):
        out.append(Candidate("primary", "abstain", [], [], []))
    else:
        out.append(_calls_candidate("primary", turn.get("tool_calls") or []))
    if turn.get("tool_calls_alt"):
        out.append(_calls_candidate("alternative:0", turn["tool_calls_alt"]))
    for i, alt in enumerate(turn.get("alternatives") or []):
        if alt.get("expect_clarification"):
            out.append(Candidate(f"alternative:{i+1}", "clarification", [], [], []))
        elif alt.get("tool_calls"):
            out.append(_calls_candidate(f"alternative:{i+1}", alt["tool_calls"]))
    return out


def _calls_candidate(label: str, tool_calls: list[dict]) -> Candidate:
    specs = [(tc.get("name", ""), dict(tc.get("arguments") or {})) for tc in tool_calls]
    tools = list(dict.fromkeys(name for name, _ in specs))
    return Candidate(label=label, kind="tools", tools=tools, specs=specs, tool_order=[])


def _spec_index_for(cand: Candidate, to_param: str) -> int | None:
    for i, (tool, checks) in enumerate(cand.specs):
        if to_param in checks:
            return i
        if to_param in SQL_PARAMS and (set(checks) & SQL_CHECKS):
            return i
    return None


def _substitute_sql_expected(expected: Any, gold_value: Any, new_value: Any) -> Any:
    if isinstance(expected, list) and expected and isinstance(expected[0], dict):
        return [dict(c, value=new_value) if literal_equal(c.get("value"), gold_value) else c for c in expected]
    if isinstance(expected, list):  # legacy sql_contains keyword list
        return [str(new_value) if str(k) == str(gold_value) else k for k in expected]
    return expected


def _context_plan(turn: dict, cand: Candidate, scenario_turns: dict, setting: str,
                  views: dict[int, RunView]) -> dict:
    """What the context reference expects, and how it changes the parameter checks."""
    ref = turn.get("context_ref") or {}
    plan = {"applicable": False, "reason": "", "expected": None, "spec": None,
            "to_param": ref.get("to_param"), "overrides": {}}
    if not ref:
        return plan
    to_param = ref.get("to_param")
    idx = _spec_index_for(cand, to_param) if to_param else None
    if idx is None:
        plan["reason"] = f"no gold call takes {to_param!r}"
        return plan
    tool = cand.specs[idx][0]
    if to_param in EXCLUDED_ARGS.get(tool, set()):
        plan["reason"] = f"{tool}.{to_param} is excluded from parameter scoring"
        return plan
    source_turn = scenario_turns.get(ref.get("from_turn"))
    gold_value, gold_ok = (None, False)
    if source_turn is not None:
        gold_value, gold_ok = resolve_path(source_turn.get("tool_result") or {}, ref.get("key", ""))
    plan["spec"] = idx
    plan["gold_value"] = gold_value
    if setting == "e2e":
        source_view = views.get(ref.get("from_turn"))
        if source_view is None:
            plan["reason"] = f"turn {ref.get('from_turn')} has no run record"
            return plan
        value, ok, why = _resolve_from_run(source_view, ref.get("key", ""), _gold_tools(source_turn))
        if not ok:
            plan["reason"] = why
            plan["overrides"] = {idx: {k: {"applicable": False, "reason": f"E2E context unresolved: {why}"}
                                       for k in _context_check_keys(cand.specs[idx], to_param)}}
            return plan
        plan.update(applicable=True, expected=value)
        checks = cand.specs[idx][1]
        if to_param in SQL_PARAMS:
            plan["overrides"] = {idx: {k: {"expected": _substitute_sql_expected(checks[k], gold_value, value)}
                                       for k in set(checks) & SQL_CHECKS if k != "sql_valid"}}
        else:
            plan["overrides"] = {idx: {to_param: {"expected": value}}}
        return plan
    if not gold_ok or gold_value is None:
        plan["reason"] = f"gold tool_result of turn {ref.get('from_turn')} has no {ref.get('key')!r}"
        return plan
    plan.update(applicable=True, expected=gold_value)
    return plan


def _context_check_keys(spec: tuple[str, dict], to_param: str) -> list[str]:
    tool, checks = spec
    if to_param in SQL_PARAMS:
        return [k for k in checks if k in SQL_CHECKS and k != "sql_valid"]
    return [to_param] if to_param in checks else []


def _gold_tools(turn: dict | None) -> list[str]:
    if not turn:
        return []
    return list(dict.fromkeys(tc.get("name", "") for tc in (turn.get("tool_calls") or [])))


def _context_hit(plan: dict, cand: Candidate, matches, ctx: ScoringContext) -> bool | None:
    if not plan.get("applicable"):
        return None
    idx = plan["spec"]
    call: Call | None = matches[idx].call
    if call is None or not call.args_ok:
        return False
    to_param = plan["to_param"]
    expected = plan["expected"]
    if to_param in SQL_PARAMS:
        sql = call.args.get("sql")
        if not isinstance(sql, str):
            return False
        pattern = r"(?<![\w.])" + re.escape(str(expected)) + r"(?![\w.])"
        return bool(re.search(pattern, sql))
    from .compare import compare_value, fill_defaults  # noqa: PLC0415

    schema = ctx.schemas.get(call.name)
    args = fill_defaults(call.args, schema)
    if to_param not in args:
        return False
    score, _ = compare_value(args[to_param], expected, schema.prop(to_param) if schema else {})
    return score == 1.0


def score_turn(turn: dict, record: dict | None, ctx: ScoringContext, *, setting: str,
               scenario_turns: dict, views: dict[int, RunView]) -> dict:
    view = view_record(record or {"rounds": [], "final_text": "",
                                  "error": {"type": "missing_record", "message": "no run record"},
                                  "stop_reason": "error"})
    best = None
    for cand in turn_candidates(turn):
        plan = _context_plan(turn, cand, scenario_turns, setting, views)
        if cand.kind in ("abstain", "clarification"):
            answered = not view.calls and (view.text_unavailable or answer_text_ok(view.final_text))
            ok = 1 if answered else 0
            scored = tool_metrics([], view.calls)
            scored.update(h=ok, a=None, n_checks=0, o=None, checks=[], matches=[],
                          abstain_ok=bool(ok) if cand.kind == "abstain" else None,
                          clarification_ok=bool(ok) if cand.kind == "clarification" else None)
        else:
            matches = match_specs(cand.specs, view.calls, ctx, plan.get("overrides"))
            a, n_checks = param_accuracy(matches)
            scored = tool_metrics(cand.tools, view.calls)
            scored.update(a=a, n_checks=n_checks, o=None, matches=matches,
                          checks=[{"tool": m.tool, "call": m.call.order if m.call else None, "results": m.checks}
                                  for m in matches],
                          abstain_ok=None, clarification_ok=None)
        if best is None or _rank(scored) > _rank(best[1]):
            best = (cand, scored, plan)
    cand, scored, plan = best
    context_hit = _context_hit(plan, cand, scored.get("matches") or [], ctx) if cand.kind == "tools" else None
    return {
        "turn": turn.get("turn"),
        "matched": cand.label,
        "gold_tools": cand.tools,
        "h": scored["h"],
        "r": scored["r"],
        "p": scored["p"],
        "a": None if scored["a"] is None else round(scored["a"], 6),
        "f1_tools": round(scored["f1_tools"], 6),
        "n_checks": scored["n_checks"],
        "n_calls": scored["n_calls"],
        "n_gold_calls": scored["n_gold_calls"],
        "called_tools": scored["called_tools"],
        "extra_tools": scored["extra_tools"],
        "abstain_ok": scored["abstain_ok"],
        "clarification_ok": scored["clarification_ok"],
        "context_hit": context_hit,
        "context_expected": plan.get("expected"),
        "context_reason": plan.get("reason"),
        "turn_error": view.error,
        "error_flag": view.error_flag,
        "error_type": _error_type(cand, scored, view),
        "parser_artifacts": view.name_artifacts,
        "final_text_ok": answer_text_ok(view.final_text),
        "unparsed_tool_call_text": is_unparsed_tool_call(view.final_text),
        "checks": scored["checks"],
        "missing_record": record is None,
    }


def score_scenario(scenario: dict, records: dict[int, dict], ctx: ScoringContext, *,
                   setting: str = "oracle") -> dict:
    gold_turns = {t.get("turn"): t for t in scenario.get("turns") or []}
    views = {n: view_record(rec) for n, rec in records.items()}
    turn_results = []
    for number in sorted(gold_turns):
        turn_results.append(score_turn(gold_turns[number], records.get(number), ctx,
                                       setting=setting, scenario_turns=gold_turns, views=views))
    checked = [t for t in turn_results if t["n_checks"]]
    ctx_turns = [t for t in turn_results if t["context_hit"] is not None]
    run_ids = {r.get("run_id") for r in records.values() if r.get("run_id")}
    return {
        "case_id": scenario.get("id", ""),
        "run_id": next(iter(run_ids), None),
        "setting": setting,
        "sub_category": scenario.get("sub_category", ""),
        "n_turns": len(turn_results),
        "c": 1 if turn_results and all(t["h"] == 1 for t in turn_results) else 0,
        "h_mean": round(sum(t["h"] for t in turn_results) / len(turn_results), 6) if turn_results else None,
        "a_mean": round(sum(t["a"] for t in checked) / len(checked), 6) if checked else None,
        "n_turns_with_checks": len(checked),
        "context_accuracy": round(sum(1 for t in ctx_turns if t["context_hit"]) / len(ctx_turns), 6) if ctx_turns else None,
        "n_context_turns": len(ctx_turns),
        "error_flag": any(t["error_flag"] for t in turn_results),
        "missing_turns": [t["turn"] for t in turn_results if t["missing_record"]],
        "turns": turn_results,
    }
