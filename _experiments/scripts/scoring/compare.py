"""Argument comparison shared by single-turn and multi-turn scoring (L4-018).

A gold call spec is ``(tool, checks)`` where ``checks`` maps an argument name or
a special check key to the expected value. Every check of one spec is evaluated
on the SAME model call; the call that satisfies the most checks is chosen, and
two specs for the same tool never share a call (L4-008).
"""

from __future__ import annotations

import itertools
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any

from .catalog import RESULT_SET_ARGS, Catalog, compare_result_set
from .records import Call
from .schema import SchemaSet, ToolSchema
from .sql import SqlExecutor, check_sql_conditions, check_sql_contains_legacy, result_is_error

SQL_CHECKS = {"sql_conditions", "sql_valid", "sql_contains"}
RANGE_CHECKS = {"hops_min": "hops", "hops_max": "hops"}
RESULT_CHECKS = {"result_contains", "result_row_count_min", "result_row_count_max"}
SPECIAL_CHECKS = SQL_CHECKS | set(RANGE_CHECKS) | RESULT_CHECKS

# Arguments that are never compared: free narrative and values the data cannot
# determine (the STR summary and a probability the tools do not return).
EXCLUDED_ARGS = {"generate_str": {"summary", "fraud_probability"}}


@dataclass
class ScoringContext:
    schemas: SchemaSet
    catalog: Catalog | None = None
    executor: SqlExecutor | None = None


@dataclass
class SpecMatch:
    tool: str
    call: Call | None
    checks: list[dict] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(1 for c in self.checks if c["applicable"])

    @property
    def earned(self) -> float:
        return sum(c["score"] for c in self.checks if c["applicable"])


def checked_keys(tool: str, checks: dict) -> list[str]:
    excluded = EXCLUDED_ARGS.get(tool, set())
    return [k for k in checks if k not in excluded]


def spec_arg_keys(checks: dict) -> set[str]:
    keys = set()
    for k in checks:
        if k in SQL_CHECKS:
            keys.add("sql")
        elif k in RANGE_CHECKS:
            keys.add(RANGE_CHECKS[k])
        elif k not in RESULT_CHECKS:
            keys.add(k)
    return keys


# ---------------------------------------------------------------------------
# Value equality
# ---------------------------------------------------------------------------

def _as_number(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(float(v)) else None
    if isinstance(v, str):
        text = v.strip()
        if re.fullmatch(r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?", text):
            return float(text)
    return None


def _scalar_equal(actual: Any, expected: Any, prop: dict) -> bool:
    ptype = prop.get("type")
    if isinstance(expected, bool) or ptype == "boolean":
        if isinstance(actual, str) and ptype == "boolean":
            actual = {"true": True, "false": False}.get(actual.strip().lower(), actual)
        return isinstance(actual, bool) and isinstance(expected, bool) and actual == expected
    if isinstance(actual, bool):
        return False
    if isinstance(expected, (int, float)) or ptype in ("integer", "number"):
        a, e = _as_number(actual), _as_number(expected)
        if a is not None and e is not None:
            return a == e
        if not (isinstance(actual, str) and isinstance(expected, str)):
            return False
    if isinstance(expected, str):
        if not isinstance(actual, str):
            return False
        if "enum" in prop:
            return actual.strip().casefold() == expected.strip().casefold()
        return actual.strip() == expected.strip()
    if expected is None:
        return actual is None
    if isinstance(expected, dict):
        return deep_equal(actual, expected, prop)
    return actual == expected


def deep_equal(actual: Any, expected: Any, prop: dict | None = None) -> bool:
    prop = prop or {}
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            return False
        sub = prop.get("properties") or {}
        return all(deep_equal(actual[k], v, sub.get(k)) for k, v in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return False
        item = prop.get("items") or {}
        return all(deep_equal(a, e, item) for a, e in zip(actual, expected))
    return _scalar_equal(actual, expected, prop)


def compare_value(actual: Any, expected: Any, prop: dict | None = None) -> tuple[float, str]:
    """Score in [0, 1] and a reason. Lists score as set recall of the gold items."""
    prop = prop or {}
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return 0.0, f"expected a list, got {actual!r}"
        if not expected:
            return 1.0, ""
        item = prop.get("items") or {}
        hit = sum(1 for e in expected if any(deep_equal(a, e, item) for a in actual))
        recall = hit / len(expected)
        return recall, "" if recall == 1.0 else f"set recall {hit}/{len(expected)}"
    if deep_equal(actual, expected, prop):
        return 1.0, ""
    return 0.0, f"expected {expected!r}, got {actual!r}"


# ---------------------------------------------------------------------------
# One call against one spec
# ---------------------------------------------------------------------------

def fill_defaults(args: dict, schema: ToolSchema | None) -> dict:
    filled = dict(args)
    if schema is None:
        return filled
    for key, default in schema.defaults().items():
        if filled.get(key) is None:
            filled[key] = default
    return filled


def _executed_result(call: Call, ctx: ScoringContext, sql: str | None) -> tuple[str | None, str]:
    ex = call.executed
    if ex is not None and ("result" in ex or ex.get("error") is not None):
        if ex.get("error") is not None:
            return json.dumps({"error": ex["error"]}, ensure_ascii=False, default=str), "recorded"
        result = ex.get("result")
        return (result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)), "recorded"
    if call.name == "query_transactions" and isinstance(sql, str) and ctx.executor is not None:
        return ctx.executor.run(sql), "executed_by_scorer"
    return None, "unavailable"


def _row_count(result_text: str) -> int | None:
    try:
        obj = json.loads(result_text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if isinstance(obj, list):
        return len(obj)
    if isinstance(obj, dict):
        if isinstance(obj.get("total_count"), int):
            return obj["total_count"]
        if isinstance(obj.get("result"), list):
            return len(obj["result"])
    return None


def _check(key: str, expected: Any, call: Call, args: dict, schema: ToolSchema | None,
           ctx: ScoringContext) -> dict:
    out = {"check": key, "expected": expected, "applicable": True}

    def done(passed: bool | float, reason: str = "", **extra) -> dict:
        score = float(passed)
        out.update(score=score, passed=score == 1.0, reason="" if score == 1.0 else reason, **extra)
        return out

    sql = args.get("sql")
    if key == "sql_conditions":
        res = check_sql_conditions(sql, expected)
        return done(res["passed"], res["reason"], parser=res.get("parser"), conditions=res["conditions"])
    if key == "sql_contains":
        res = check_sql_contains_legacy(sql, expected)
        return done(res["passed"], res["reason"], legacy=True)
    if key == "sql_valid":
        if not isinstance(sql, str) or not sql.strip():
            return done(False, "sql argument missing or not a string")
        result, how = _executed_result(call, ctx, sql)
        if result is None:
            return done(False, "SQL was not executed and no executor is available", evidence=how)
        is_error = result_is_error(result)
        return done(is_error != bool(expected), f"expected valid={bool(expected)}, error={is_error}", evidence=how)
    if key in RANGE_CHECKS:
        value = _as_number(args.get(RANGE_CHECKS[key]))
        bound = _as_number(expected)
        if value is None or bound is None or not float(value).is_integer():
            return done(False, f"hops={args.get('hops')!r} is not an integer")
        ok = value >= bound if key == "hops_min" else value <= bound
        return done(ok, f"hops={value:g} violates {key}={expected}")
    if key in RESULT_CHECKS:
        result, how = _executed_result(call, ctx, sql)
        if result is None:
            return done(False, "no tool result available", evidence=how)
        if key == "result_contains":
            kws = expected if isinstance(expected, list) else [expected]
            missing = [k for k in kws if str(k) not in result]
            return done(not missing, f"result lacks {missing}", evidence=how)
        count = _row_count(result)
        if count is None:
            return done(False, "result has no row list or total_count", evidence=how)
        ok = count >= expected if key == "result_row_count_min" else count <= expected
        return done(ok, f"row count {count} vs {key}={expected}", evidence=how)

    if key not in args:
        return done(False, f"argument {key!r} missing")
    actual = args[key]
    if key in RESULT_SET_ARGS.get(call.name, ()) and ctx.catalog is not None:
        res = compare_result_set(ctx.catalog, call.name, actual, expected)
        extra = {k: v for k, v in res.items() if k not in ("passed", "reason")}
        return done(res["passed"], res["reason"], actual=actual, **extra)
    score, reason = compare_value(actual, expected, schema.prop(key) if schema else {})
    return done(score, reason, actual=actual)


def score_call(tool: str, checks: dict, call: Call | None, ctx: ScoringContext,
               overrides: dict | None = None) -> SpecMatch:
    """``overrides`` maps a check key to {"expected": value} or {"applicable": False, "reason": ...}."""
    overrides = overrides or {}
    schema = ctx.schemas.get(tool)
    match = SpecMatch(tool=tool, call=call)
    for key in checked_keys(tool, checks):
        expected = checks[key]
        ov = overrides.get(key, {})
        if ov.get("applicable") is False:
            match.checks.append({"check": key, "expected": expected, "applicable": False,
                                 "score": 0.0, "passed": False, "reason": ov.get("reason", "not applicable")})
            continue
        expected = ov.get("expected", expected)
        if call is None:
            match.checks.append({"check": key, "expected": expected, "applicable": True,
                                 "score": 0.0, "passed": False, "reason": "tool not called"})
        elif not call.args_ok:
            match.checks.append({"check": key, "expected": expected, "applicable": True, "score": 0.0,
                                 "passed": False, "reason": f"arguments are not a JSON object: {call.arguments!r}"[:300]})
        else:
            match.checks.append(_check(key, expected, call, fill_defaults(call.args, schema), schema, ctx))
    return match


def match_specs(specs: list[tuple[str, dict]], calls: list[Call], ctx: ScoringContext,
                overrides: dict[int, dict] | None = None) -> list[SpecMatch]:
    """Best one-to-one assignment of model calls to gold specs, per tool name."""
    overrides = overrides or {}
    result: list[SpecMatch | None] = [None] * len(specs)
    by_tool: dict[str, list[int]] = {}
    for i, (tool, _) in enumerate(specs):
        by_tool.setdefault(tool, []).append(i)
    for tool, spec_ids in by_tool.items():
        cands = [c for c in calls if c.name == tool]
        table = {(i, c.order): score_call(tool, specs[i][1], c, ctx, overrides.get(i)) for i in spec_ids for c in cands}
        if len(cands) > 8:  # keep the assignment search small when a model spams one tool
            best_of = {c.order: max(table[(i, c.order)].earned for i in spec_ids) for c in cands}
            cands = sorted(sorted(cands, key=lambda c: c.order), key=lambda c: -best_of[c.order])[:8]
        slots = cands + [None] * len(spec_ids)
        best, best_key = None, None
        for perm in itertools.permutations(range(len(slots)), len(spec_ids)):
            chosen = [slots[p] for p in perm]
            if any(a is not None and b is not None and a.order == b.order
                   for a, b in itertools.combinations(chosen, 2)):
                continue
            earned = sum(table[(i, c.order)].earned for i, c in zip(spec_ids, chosen) if c is not None)
            n_called = sum(c is not None for c in chosen)
            first = tuple(c.order if c is not None else math.inf for c in chosen)
            key = (earned, n_called, tuple(-x for x in first))
            if best_key is None or key > best_key:
                best, best_key = chosen, key
        for i, c in zip(spec_ids, best):
            result[i] = table[(i, c.order)] if c is not None else score_call(tool, specs[i][1], None, ctx, overrides.get(i))
    return result  # type: ignore[return-value]


def hallucinated_params(calls: list[Call], schemas: SchemaSet) -> list[dict]:
    out = []
    for c in calls:
        schema = schemas.get(c.name)
        if schema is None or not c.args_ok:
            continue
        for k in c.args:
            if k not in schema.properties:
                out.append({"call": c.order, "tool": c.name, "param": k})
    return out
