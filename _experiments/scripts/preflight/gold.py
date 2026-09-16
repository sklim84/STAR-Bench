"""Gate 4: the gold answers score against themselves and execute on the platform.

Two independent readings of the same data:

* `scoring.gold_selftest` renders each gold annotation as a run record and scores
  it. A case whose gold is internally inconsistent cannot score 1 against itself,
  and whatever does not is a data defect, not a scoring defect.
* the platform's own gold-call harness (`scripts/gold_calls.py`) executes every
  gold call on HOFINET. The round-2 audit ran exactly this and found 42.8% of the
  well-formed gold calls returning nothing usable (L3-007).

An error fails the gate. An empty or unexecutable call fails it too unless
`allow_empty.json` names that case and says why, so the ring and layering scans
that HOFINET cannot answer stay visible instead of being rounded away (D06).
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from .gate import BENCHMARK_DIRS, Check, Context, GateResult, run_command

NUMBER = 4
KEY = "gold"
TITLE = "gold answers"

ALLOW_PATH = Path(__file__).resolve().parent / "allow_empty.json"


def run(ctx: Context, *, update_allow_list: bool = False) -> GateResult:
    started = time.time()
    checks = [_selftest(ctx, name) for name in BENCHMARK_DIRS]
    checks.extend(_gold_calls(ctx, update_allow_list=update_allow_list))
    return GateResult(KEY, NUMBER, TITLE, checks, time.time() - started)


def _selftest(ctx: Context, benchmark: str) -> Check:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
        out = Path(handle.name)
    try:
        done = run_command([ctx.python, "-m", "_experiments.scripts.scoring.gold_selftest",
                            "--benchmark", benchmark, "--out", str(out)],
                           cwd=ctx.root, env=ctx.env, timeout=ctx.timeout_s)
        report = {}
        if out.is_file() and out.stat().st_size:
            report = json.loads(out.read_text(encoding="utf-8"))
    finally:
        out.unlink(missing_ok=True)

    defects = _defects(report)
    spoken = [line for line in done.stdout.strip().splitlines()
              if line.strip() and not line.startswith("report:")]
    detail = done.tail(4) if not done.ok else "; ".join(spoken[:2])
    if defects:
        detail = f"{len(defects)} defect(s): " + "; ".join(_describe(d) for d in defects[:4])
    return Check(f"gold self-test on {benchmark}", done.ok and not defects, detail,
                 done.command, {"defects": defects[:20]})


def _describe(defect: dict) -> str:
    """One line a data owner can act on: which case, and what did not score."""
    case = defect.get("case_id", "?")
    if defect.get("bad_turns"):
        turns = ", ".join(f"turn {t['turn']} h={t['h']}" for t in defect["bad_turns"][:3])
        return f"{case}: {turns}"
    blocking = [p for p in defect.get("render_problems") or [] if p.get("blocking")]
    if blocking:
        return f"{case}: {str(blocking[0].get('reason') or blocking[0])[:90]}"
    failed = defect.get("failed_checks") or []
    if failed:
        return f"{case}: {str(failed[0])[:90]}"
    return f"{case}: {defect.get('error_type', 'not perfect')}"


def _defects(report) -> list[dict]:
    """The defect rows of a gold self-test report, whatever shape it uses."""
    if isinstance(report, list):
        return [row for row in report if isinstance(row, dict) and row.get("defects")]
    if not isinstance(report, dict):
        return []
    found: list[dict] = []
    for key, value in report.items():
        if key == "advisories":
            continue
        if key in ("defects", "problems") and isinstance(value, list):
            found.extend(v if isinstance(v, dict) else {"reason": v} for v in value)
        elif isinstance(value, dict):
            found.extend(_defects(value))
    return found


def _gold_calls(ctx: Context, *, update_allow_list: bool) -> list[Check]:
    env = dict(ctx.env)
    env["STAR_BENCH_GOLD_DIRS"] = os.pathsep.join(str(ctx.root / d) for d in BENCHMARK_DIRS)
    done = run_command([ctx.platform_python, "-m", "_experiments.scripts.preflight._gold_driver"],
                       cwd=ctx.root, env=env, timeout=ctx.timeout_s)
    command = (f"STAR_BENCH_GOLD_DIRS={env['STAR_BENCH_GOLD_DIRS']} " + done.command
               + "   # same functions as: python scripts/gold_calls.py "
                 "../STAR-Bench/benchmarks ...")
    try:
        report = json.loads(done.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return [Check("gold calls execute on the platform", False,
                      f"the harness produced no JSON: {done.tail(6)}", command)]

    if update_allow_list:
        _write_allow_list(report)

    allowed = _allow_index()
    checks: list[Check] = []
    unexpected_total: list[str] = []
    for name, summary in report["directories"].items():
        totals = summary["totals"]
        kind = "multiturn" if "multiturn" in name else "single"
        unexpected = []
        for row in summary["non_ok"]:
            if row["status"] == "error":
                unexpected.append(f"{row['case_id']}"
                                  + (f"#{row['turn']}" if row["turn"] else "")
                                  + f" {row['tool']}: {row['detail'][:80]}")
            elif (kind, row["case_id"], row["turn"], row["tool"]) not in allowed:
                unexpected.append(f"{row['case_id']}"
                                  + (f"#{row['turn']}" if row["turn"] else "")
                                  + f" {row['tool']} returned nothing and is not in "
                                    f"allow_empty.json: {row['detail'][:70]}")
        unexpected_total.extend(unexpected)
        checks.append(Check(
            f"gold calls execute on {name}", not unexpected,
            f"{summary['calls']} calls: ok {totals['ok']}, empty {totals['empty']} (allowed), "
            f"error {totals['error']}, skipped {totals['skipped']} (allowed)"
            if not unexpected else "; ".join(unexpected[:5]),
            command, {"totals": totals, "per_tool": summary["per_tool"]}))

    stale = _stale(report, allowed)
    checks.append(Check(
        "every expected empty is on the allow-list", not unexpected_total,
        f"{len(allowed)} allow-list entries, all still empty"
        if not stale else
        f"{len(allowed)} allow-list entries; {len(stale)} no longer empty and can be "
        f"removed: {', '.join(sorted(stale)[:6])}",
        f"cat {ALLOW_PATH.relative_to(ctx.root)}",
        {"stale": sorted(stale), "unexpected": unexpected_total}))
    return checks


def _allow_index() -> set[tuple]:
    doc = json.loads(ALLOW_PATH.read_text(encoding="utf-8"))
    return {(e["kind"], e["case_id"], e.get("turn"), e["tool"]) for e in doc["entries"]}


def _stale(report: dict, allowed: set[tuple]) -> set[str]:
    """Allow-list entries whose call now returns rows: the list should shrink."""
    seen = set()
    for name, summary in report["directories"].items():
        kind = "multiturn" if "multiturn" in name else "single"
        for row in summary["non_ok"]:
            seen.add((kind, row["case_id"], row["turn"], row["tool"]))
    return {f"{k}/{case}" for (k, case, _turn, _tool) in allowed - seen}


def _write_allow_list(report: dict) -> None:
    doc = json.loads(ALLOW_PATH.read_text(encoding="utf-8"))
    known = {(e["kind"], e["case_id"], e.get("turn"), e["tool"]): e for e in doc["entries"]}
    entries = []
    for name, summary in report["directories"].items():
        kind = "multiturn" if "multiturn" in name else "single"
        for row in summary["non_ok"]:
            key = (kind, row["case_id"], row["turn"], row["tool"])
            if key in known:
                entries.append(known[key])
                continue
            entries.append({"kind": kind, "case_id": row["case_id"], "turn": row["turn"],
                            "tool": row["tool"], "status": row["status"],
                            "pattern_type": (row["arguments"] or {}).get("pattern_type"),
                            "reason": "TO BE EXPLAINED: " + row["detail"][:140]})
    seen, unique = set(), []
    for entry in entries:
        key = (entry["kind"], entry["case_id"], entry.get("turn"), entry["tool"])
        if key not in seen:
            seen.add(key)
            unique.append(entry)
    unique.sort(key=lambda e: (e["kind"], e["case_id"], e.get("turn") or 0, e["tool"]))
    doc["entries"] = unique
    ALLOW_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
