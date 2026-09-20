"""CLI: score run records against a gold benchmark directory.

    python -m _experiments.scripts.scoring.score_runs \
        --runs _experiments/results_kr_v2/records --benchmark benchmarks --out _experiments/results_kr_v2/eval

One eval file per run id, each with per-case (or per-scenario) results and
aggregates that carry n for every metric.

Every record says which benchmark files the run was asked about
(`provenance.benchmark_sha256`). The scorer compares that with the directory it
was given and refuses a mismatch: scoring a Korean run against `benchmarks_en`
would otherwise succeed silently and write an eval whose provenance hash and
whose gold came from different data. `--allow-benchmark-mismatch` scores it
anyway and records the override, the two hashes and the reason in every eval
file it writes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):  # allow "python score_runs.py"
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.scoring"

from .aggregate import aggregate_multiturn, aggregate_single
from .catalog import Catalog
from .compare import ScoringContext
from .gold import Benchmark, load_benchmark
from .records import iter_records, record_files
from .multiturn import score_scenario
from .schema import load_tool_schemas
from .single import score_case
from .sql import SqlExecutor, sqlglot_version


def build_context(tools_schema: str | None = None, *, execute_sql: bool = True,
                  use_catalog: bool = True, sql_timeout: float = 60.0) -> ScoringContext:
    return ScoringContext(
        schemas=load_tool_schemas(tools_schema),
        catalog=Catalog() if use_catalog else None,
        executor=SqlExecutor(sql_timeout) if execute_sql else None,
    )


def _repo_commit() -> str | None:
    root = Path(__file__).resolve().parents[3]
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None
    except Exception:
        return None


def score_single_run(records: list[dict], bench: Benchmark, ctx: ScoringContext, *,
                     score_missing: bool = True) -> tuple[list[dict], dict]:
    by_case: dict[str, dict] = {}
    duplicates = []
    for rec in records:
        case_id = rec.get("case_id")
        if case_id in by_case:
            duplicates.append(case_id)
        by_case[case_id] = rec
    unknown = sorted(cid for cid in by_case if cid not in bench.cases)
    missing = sorted(cid for cid in bench.cases if cid not in by_case)
    results = []
    for case_id, case in bench.cases.items():
        record = by_case.get(case_id)
        if record is None and not score_missing:
            continue
        results.append(score_case(case, record, ctx, category=bench.category_of(case_id)))
    info = {"n_records": len(records), "n_cases_gold": len(bench.cases),
            "missing_case_ids": missing, "unknown_case_ids": unknown,
            "duplicate_case_ids": sorted(set(duplicates)), "complete": not missing and not unknown}
    return results, info


def score_multiturn_run(records: list[dict], bench: Benchmark, ctx: ScoringContext, *,
                        setting: str | None = None, score_missing: bool = True) -> tuple[list[dict], dict]:
    by_case: dict[str, dict[int, dict]] = defaultdict(dict)
    for rec in records:
        by_case[rec.get("case_id")][rec.get("turn")] = rec
    unknown = sorted(cid for cid in by_case if cid not in bench.cases)
    missing = sorted(cid for cid in bench.cases if cid not in by_case)
    results = []
    for case_id, scenario in bench.cases.items():
        turns = by_case.get(case_id, {})
        if not turns and not score_missing:
            continue
        run_setting = setting or next((r.get("setting") for r in turns.values() if r.get("setting")), "oracle")
        results.append(score_scenario(scenario, turns, ctx, setting=run_setting))
    info = {"n_records": len(records), "n_cases_gold": len(bench.cases),
            "missing_case_ids": missing, "unknown_case_ids": unknown,
            "complete": not missing and not unknown}
    return results, info


def benchmark_agreement(records: list[dict], bench: Benchmark) -> dict:
    """What the records say they were run on, against the gold being scored.

    `status` is `match`, `mismatch` (at least one record names other data) or
    `not_recorded` (records from before the digest existed; nothing to compare).
    """
    recorded: dict[tuple, int] = {}
    for rec in records:
        prov = rec.get("provenance") or {}
        key = (prov.get("benchmark_dir"), prov.get("benchmark_sha256"))
        recorded[key] = recorded.get(key, 0) + 1
    hashes = {sha for _dir, sha in recorded if sha}
    if not hashes:
        status = "not_recorded"
    elif hashes == {bench.sha256} and len(recorded) == 1:
        status = "match"
    else:
        status = "mismatch"
    return {
        "status": status,
        "benchmark_root": str(bench.root),
        "benchmark_sha256": bench.sha256,
        "records": [{"benchmark_dir": d, "benchmark_sha256": s, "n_records": n}
                    for (d, s), n in sorted(recorded.items(), key=lambda kv: -kv[1])],
    }


def _agreement_problem(run_id: str, agreement: dict) -> str:
    named = ", ".join(f"{r['n_records']} record(s) from {r['benchmark_dir']} "
                      f"{(r['benchmark_sha256'] or 'no hash')[:12]}" for r in agreement["records"])
    return (f"{run_id}: the records were not run on {Path(agreement['benchmark_root']).name} "
            f"{agreement['benchmark_sha256'][:12]}: {named}")


def _meta(records: list[dict], bench: Benchmark, ctx: ScoringContext, run_id: str) -> dict:
    head = records[0] if records else {}
    return {
        "run_id": run_id,
        "setting": head.get("setting"),
        "tools_lang": head.get("tools_lang"),
        "query_lang": head.get("query_lang"),
        "config": head.get("config"),
        "provenance": head.get("provenance"),
        "scorer": {
            "star_bench_commit": _repo_commit(),
            "benchmark_root": str(bench.root),
            "benchmark_sha256": bench.sha256,
            "benchmark_kind": bench.kind,
            "tool_schema_source": ctx.schemas.source,
            "tool_schema_sha256": ctx.schemas.sha256,
            "benchmark_check": benchmark_agreement(records, bench),
            "sqlglot": sqlglot_version(),
            "sql_execution": ctx.executor is not None,
            "catalog_comparison": ctx.catalog is not None,
            "scored_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", required=True, help="directory (or file) of JSONL run records")
    ap.add_argument("--benchmark", required=True, help="benchmark directory with cases_*.json")
    ap.add_argument("--out", required=True, help="directory for the eval files")
    ap.add_argument("--setting", choices=["oracle", "e2e"], help="multi-turn setting override")
    ap.add_argument("--tools-schema", help="JSON file with the tool schema list (default: platform agent.TOOLS)")
    ap.add_argument("--no-sql-exec", action="store_true", help="never run SQL; use recorded results only")
    ap.add_argument("--no-catalog", action="store_true", help="compare FIU/glossary arguments as strings")
    ap.add_argument("--sql-timeout", type=float, default=60.0)
    ap.add_argument("--skip-missing", action="store_true",
                    help="leave cases without a run record out of the aggregates (default: score them as failures)")
    ap.add_argument("--allow-benchmark-mismatch", action="store_true",
                    help="score records whose provenance.benchmark_sha256 is not this benchmark "
                         "directory's; the override and both hashes are recorded in every eval file")
    args = ap.parse_args(argv)

    if sqlglot_version() is None:
        print("warning: sqlglot is not installed, so SQL conditions fall back to the regex reader; "
              "install the pin in _experiments/scripts/scoring/requirements.txt", file=sys.stderr)
    bench = load_benchmark(args.benchmark)
    ctx = build_context(args.tools_schema, execute_sql=not args.no_sql_exec,
                        use_catalog=not args.no_catalog, sql_timeout=args.sql_timeout)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    runs: dict[str, list[dict]] = defaultdict(list)
    for path in record_files(Path(args.runs)):
        for rec in iter_records([path]):
            runs[rec.get("run_id") or path.stem].append(rec)
    if not runs:
        print(f"no run records under {args.runs}", file=sys.stderr)
        return 1

    problems = [_agreement_problem(run_id, benchmark_agreement(recs, bench))
                for run_id, recs in sorted(runs.items())
                if benchmark_agreement(recs, bench)["status"] == "mismatch"]
    if problems and not args.allow_benchmark_mismatch:
        print("refusing to score: the run records name other benchmark data than "
              f"{args.benchmark}.", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print("Score each arm against the directory it was run on, or pass "
              "--allow-benchmark-mismatch to record the override in the eval files.",
              file=sys.stderr)
        return 2
    for run_id, recs in sorted(runs.items()):
        if benchmark_agreement(recs, bench)["status"] == "not_recorded":
            print(f"warning: {run_id}: the records do not carry "
                  f"provenance.benchmark_sha256, so the benchmark they were run on cannot be "
                  f"verified", file=sys.stderr)

    summary = []
    for run_id, records in sorted(runs.items()):
        if bench.kind == "multiturn":
            results, info = score_multiturn_run(records, bench, ctx, setting=args.setting,
                                                score_missing=not args.skip_missing)
            agg = aggregate_multiturn(results)
            key = {"c": agg["c"], "h": agg["h"], "a": agg["a"], "context_accuracy": agg["context_accuracy"]}
        else:
            results, info = score_single_run(records, bench, ctx, score_missing=not args.skip_missing)
            agg = aggregate_single(results)
            key = {"h": agg["h"], "a": agg["a"], "f1_tools": agg["f1_tools"], "p_micro": agg["p_micro"]}
        meta = _meta(records, bench, ctx, run_id) | {"coverage": info}
        if args.allow_benchmark_mismatch:
            meta["scorer"]["benchmark_mismatch_override"] = {
                "flag": "--allow-benchmark-mismatch",
                "status": meta["scorer"]["benchmark_check"]["status"],
                "note": "scored against a benchmark directory the records do not name",
            }
        safe = "".join(c if c.isalnum() or c in "-._" else "_" for c in run_id)
        path = out_dir / f"eval_{safe}.json"
        path.write_text(json.dumps({"meta": meta, "aggregate": agg, "results": results},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
        summary.append({"run_id": run_id, "file": path.name, "setting": meta["setting"],
                        "coverage": info, "metrics": key})
        print(f"{run_id}: {path} ({info['n_records']} records, {len(results)} scored)")

    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
