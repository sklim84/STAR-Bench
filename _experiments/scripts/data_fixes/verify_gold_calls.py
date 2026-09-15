"""Execute the gold calls of a benchmark directory and report the ones that answer nothing.

A gold call that returns an error, a "no transaction history" notice or an empty
result set cannot be the reference answer to the question that asks for it
(L3-007). The check runs the platform's own tool layer, so it sees exactly what
a model would see.

    python -m _experiments.scripts.data_fixes.verify_gold_calls --benchmark benchmarks
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, dump_json

SPECIAL = {"sql_contains", "sql_conditions", "sql_valid", "hops_min", "hops_max",
           "result_contains", "result_row_count_min", "result_row_count_max"}
EMPTY_MARKERS = ("No transaction history", "not found", "No ring pattern", "No layering",
                 "no funnel", "No transfer path")


def render(case: dict, tool: str, checks: dict) -> dict | None:
    """The arguments a perfect model would send for one gold spec."""
    args = {k: v for k, v in checks.items() if k not in SPECIAL}
    if "hops_min" in checks:
        args["hops"] = checks["hops_min"]
    elif "hops_max" in checks:
        args["hops"] = checks["hops_max"]
    reference = ((case.get("expected") or {}).get("reference_calls") or {}).get(tool) or {}
    if reference.get("sql"):
        args["sql"] = reference["sql"]
    return args


def verdict(tool: str, result: str) -> tuple[str, str]:
    try:
        payload = json.loads(result)
    except (json.JSONDecodeError, ValueError):
        return ("ok", "") if result.strip() else ("empty", "empty text")
    if isinstance(payload, dict):
        if payload.get("error"):
            return "error", str(payload["error"])[:200]
        if payload.get("notice") and any(m.lower() in str(payload["notice"]).lower() for m in EMPTY_MARKERS):
            return "empty", str(payload["notice"])[:200]
        for key in ("result", "results", "path", "candidates"):
            value = payload.get(key)
            if isinstance(value, list) and not value:
                return "empty", f"{key} is empty"
        if payload.get("total_count") == 0:
            return "empty", "total_count is 0"
    if isinstance(payload, list) and not payload:
        return "empty", "empty list"
    return "ok", ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--benchmark", default="benchmarks")
    ap.add_argument("--out")
    ap.add_argument("--only-account-calls", action="store_true",
                    help="report only calls that carry an account argument")
    args = ap.parse_args(argv)

    from _experiments.scripts._platform import ensure_platform_on_path  # noqa: PLC0415

    ensure_platform_on_path()
    from src.features.agent import _execute_tool  # noqa: PLC0415

    bench = Bench.load(args.benchmark, "kr")
    rows, problems = [], []
    for _, case in bench.cases():
        for tool, checks in (case["expected"].get("param_checks") or {}).items():
            if not isinstance(checks, dict):
                continue
            call = render(case, tool, checks)
            has_account = any(k in checks for k in ("account_id", "account_a", "account_b"))
            if args.only_account_calls and not has_account:
                continue
            try:
                result = _execute_tool(tool, dict(call))
            except Exception as exc:  # a gold call must never raise
                result = json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False)
            state, reason = verdict(tool, result)
            row = {"case_id": case["id"], "tool": tool, "arguments": call, "state": state,
                   "reason": reason, "has_account": has_account, "excerpt": result[:200]}
            rows.append(row)
            if state != "ok":
                problems.append(row)
    summary = {"benchmark": args.benchmark, "n_calls": len(rows), "n_problems": len(problems),
               "n_account_problems": sum(1 for p in problems if p["has_account"]),
               "problems": problems}
    if args.out:
        dump_json(args.out, summary)
    print(f"{len(rows)} gold calls executed, {len(problems)} answer nothing "
          f"({summary['n_account_problems']} of them carry an account)")
    for row in problems[:40]:
        print(f"  {row['case_id']} {row['tool']} [{row['state']}] {row['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
