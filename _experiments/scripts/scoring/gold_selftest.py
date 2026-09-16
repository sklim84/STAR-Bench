"""Gold self-test: render the gold calls as run records and score them.

A case whose gold is internally consistent must score perfectly against itself.
Whatever does not is a data defect, not a scoring defect, so the report lists
those cases for the data owners. Runs against any benchmark directory:

    python -m _experiments.scripts.scoring.gold_selftest --benchmark benchmarks \
        --out /tmp/gold_selftest_benchmarks.json

Pre-flight gate 4 runs the same self-test on all four directories and compares
the counts with `_experiments/scripts/preflight/gold_selftest_expected.json`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.scoring"

from .compare import RANGE_CHECKS, RESULT_CHECKS, SQL_CHECKS, ScoringContext
from .gold import load_benchmark
from .multiturn import score_scenario
from .single import candidates, score_case

GOLD_TEXT = "Reference answer produced from the gold annotation."


def _reference_sql(case: dict, tool: str) -> str | None:
    ref = ((case.get("expected") or {}).get("reference_calls") or {}).get(tool) or {}
    sql = ref.get("sql") or ref.get("reference_sql")
    return sql if isinstance(sql, str) and sql.strip() else None


def render_arguments(tool: str, checks: dict, *, reference_sql: str | None = None) -> tuple[dict, list[dict]]:
    """Arguments a perfect model would send, and the reasons it cannot be rendered."""
    args: dict = {}
    problems: list[dict] = []
    for key, value in checks.items():
        if key in SQL_CHECKS:
            if reference_sql is None:
                problems.append({"kind": "needs_reference_sql", "blocking": True,
                                 "detail": f"{tool}.{key} needs expected.reference_calls.{tool}.sql"})
            else:
                args["sql"] = reference_sql
        elif key in RANGE_CHECKS:
            args.setdefault("hops", value if key == "hops_min" else value)
            if key == "hops_min":
                args["hops"] = value
        elif key in RESULT_CHECKS:
            continue
        else:
            args[key] = value
    return args, problems


def _schema_problems(ctx: ScoringContext, tool: str, args: dict) -> list[dict]:
    schema = ctx.schemas.get(tool)
    if schema is None:
        return [{"kind": "unknown_tool", "blocking": True, "detail": f"{tool} is not in the tool schema"}]
    out = [{"kind": "not_a_schema_property", "blocking": True,
            "detail": f"{tool}.{k} is not a schema property"} for k in args if k not in schema.properties]
    missing = [k for k in schema.required if k not in args]
    if missing:
        out.append({"kind": "missing_required_arg", "blocking": False,
                    "detail": f"{tool} gold call omits required {missing}, so the gold call is not executable as-is"})
    return out


def _executed(ctx: ScoringContext, tool: str, args: dict, call_id: str) -> dict | None:
    if tool == "query_transactions" and isinstance(args.get("sql"), str) and ctx.executor is not None:
        return {"tool_call_id": call_id, "name": tool, "arguments": args,
                "result": ctx.executor.run(args["sql"]), "error": None}
    return None


def render_single_record(case: dict, ctx: ScoringContext) -> tuple[dict, list[dict]]:
    cand = candidates(case)[0]
    problems: list[dict] = []
    calls, executed = [], []
    for i, (tool, checks) in enumerate(cand.specs):
        args, why = render_arguments(tool, checks, reference_sql=_reference_sql(case, tool))
        problems += why + _schema_problems(ctx, tool, args)
        call_id = f"gold{i}"
        calls.append({"id": call_id, "name": tool, "arguments": args,
                      "arguments_raw": json.dumps(args, ensure_ascii=False), "source": "native", "valid_json": True})
        ex = _executed(ctx, tool, args, call_id)
        if ex is not None:
            executed.append(ex)
    record = {
        "run_id": "gold", "case_id": case.get("id"), "setting": "single",
        "rounds": [{"idx": 0, "finish_reason": "tool_calls", "content": "", "tool_calls": calls, "executed": executed,
                    "error": None}] if calls else [],
        "final_text": GOLD_TEXT, "stop_reason": "no_tool_call", "error": None,
    }
    return record, problems


def render_multiturn_records(scenario: dict, ctx: ScoringContext, setting: str) -> tuple[dict[int, dict], list[dict]]:
    records: dict[int, dict] = {}
    problems: list[dict] = []
    for turn in scenario.get("turns") or []:
        number = turn.get("turn")
        calls, executed = [], []
        for i, tc in enumerate(turn.get("tool_calls") or []):
            tool = tc.get("name", "")
            checks = dict(tc.get("arguments") or {})
            args, why = render_arguments(tool, checks, reference_sql=tc.get("reference_sql") or turn.get("reference_sql"))
            problems += [dict(w, turn=number) for w in why + _schema_problems(ctx, tool, args)]
            call_id = f"gold{number}_{i}"
            calls.append({"id": call_id, "name": tool, "arguments": args,
                          "arguments_raw": json.dumps(args, ensure_ascii=False), "source": "native", "valid_json": True})
            if setting == "e2e" and turn.get("tool_result") is not None:
                executed.append({"tool_call_id": call_id, "name": tool, "arguments": args,
                                 "result": json.dumps(turn["tool_result"], ensure_ascii=False), "error": None})
            else:
                ex = _executed(ctx, tool, args, call_id)
                if ex is not None:
                    executed.append(ex)
        records[number] = {
            "run_id": "gold", "case_id": scenario.get("id"), "turn": number, "setting": setting,
            "rounds": [{"idx": 0, "content": "", "tool_calls": calls, "executed": executed, "error": None}] if calls else [],
            "final_text": GOLD_TEXT, "stop_reason": "no_tool_call", "error": None,
        }
    return records, problems


def _catalog_problems(checks: list[dict]) -> list[dict]:
    """Gold free-string values that select no catalog row at all."""
    out = []
    for group in checks:
        for res in group["results"]:
            if res.get("gold_empty_result"):
                out.append({"kind": "gold_value_returns_no_catalog_rows", "blocking": False,
                            "detail": f"{group['tool']}.{res['check']} = {res['expected']!r} finds nothing"})
    return out


def _failed_checks(checks: list[dict]) -> list[dict]:
    out = []
    for group in checks:
        for res in group["results"]:
            if res["applicable"] and not res["passed"]:
                out.append({"tool": group["tool"], "check": res["check"], "reason": res["reason"]})
    return out


def run_single(bench, ctx: ScoringContext) -> dict:
    rows = []
    for case_id, case in bench.cases.items():
        record, problems = render_single_record(case, ctx)
        result = score_case(case, record, ctx, category=bench.category_of(case_id))
        problems = problems + _catalog_problems(result["checks"])
        blocking = [p for p in problems if p["blocking"]]
        perfect = (result["error_type"] == "correct" and not blocking)
        rows.append({
            "case_id": case_id, "category": result["category"], "perfect": perfect,
            "h": result["h"], "a": result["a"], "o": result["o"], "p": result["p"],
            "error_type": result["error_type"], "render_problems": problems,
            "failed_checks": _failed_checks(result["checks"]),
        })
    return {"n": len(rows), "n_perfect": sum(r["perfect"] for r in rows),
            "defects": [r for r in rows if not r["perfect"]],
            "advisories": [r for r in rows if r["perfect"] and r["render_problems"]]}


def run_multiturn(bench, ctx: ScoringContext, setting: str) -> dict:
    rows = []
    for case_id, scenario in bench.cases.items():
        records, problems = render_multiturn_records(scenario, ctx, setting)
        result = score_scenario(scenario, records, ctx, setting=setting)
        for t in result["turns"]:
            problems += [dict(p, turn=t["turn"]) for p in _catalog_problems(t["checks"])]
        bad_turns = []
        for turn in result["turns"]:
            failed = _failed_checks(turn["checks"])
            if turn["h"] != 1 or failed or turn["context_hit"] is False or turn["context_reason"]:
                bad_turns.append({"turn": turn["turn"], "h": turn["h"], "a": turn["a"],
                                  "context_hit": turn["context_hit"], "context_reason": turn["context_reason"],
                                  "failed_checks": failed})
        blocking = [p for p in problems if p["blocking"]]
        perfect = not bad_turns and not blocking and result["c"] == 1
        rows.append({"case_id": case_id, "sub_category": result["sub_category"], "perfect": perfect,
                     "c": result["c"], "h_mean": result["h_mean"], "a_mean": result["a_mean"],
                     "context_accuracy": result["context_accuracy"],
                     "render_problems": problems, "bad_turns": bad_turns})
    return {"n": len(rows), "n_perfect": sum(r["perfect"] for r in rows),
            "defects": [r for r in rows if not r["perfect"]],
            "advisories": [r for r in rows if r["perfect"] and r["render_problems"]]}


def main(argv: list[str] | None = None) -> int:
    from .score_runs import build_context  # noqa: PLC0415

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--benchmark", required=True)
    ap.add_argument("--out", help="write the full report here")
    ap.add_argument("--setting", choices=["oracle", "e2e", "both"], default="both",
                    help="multi-turn only")
    ap.add_argument("--no-sql-exec", action="store_true")
    ap.add_argument("--tools-schema")
    args = ap.parse_args(argv)

    bench = load_benchmark(args.benchmark)
    ctx = build_context(args.tools_schema, execute_sql=not args.no_sql_exec)
    report = {"benchmark": str(bench.root), "benchmark_sha256": bench.sha256, "kind": bench.kind,
              "tool_schema_source": ctx.schemas.source}
    if bench.kind == "single":
        report["single"] = run_single(bench, ctx)
        block = report["single"]
        print(f"single-turn gold self-test: {block['n_perfect']}/{block['n']} perfect")
    else:
        settings = ["oracle", "e2e"] if args.setting == "both" else [args.setting]
        for setting in settings:
            report[setting] = run_multiturn(bench, ctx, setting)
            block = report[setting]
            print(f"multi-turn gold self-test ({setting}): {block['n_perfect']}/{block['n']} perfect")
    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
