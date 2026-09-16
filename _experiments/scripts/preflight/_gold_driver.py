"""Runs the platform's gold-call harness and prints every call that is not ok.

`scripts/gold_calls.py` caps its per-tool examples at five, which is right for a
printed table and wrong for a gate: the allow-list has to name every expected
empty. This calls the same `collect_calls` / `execute` / `summarize` functions
and adds the full list of non-ok calls.

    STAR_BENCH_GOLD_DIRS=dir1:dir2 python -m _experiments.scripts.preflight._gold_driver
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.preflight"


def main() -> int:
    from _experiments.scripts._platform import ensure_platform_on_path

    platform_root = ensure_platform_on_path()
    if str(platform_root) not in sys.path:
        sys.path.insert(0, str(platform_root))
    from scripts.gold_calls import collect_calls, execute, summarize

    raw = os.environ.get("STAR_BENCH_GOLD_DIRS", "")
    directories = [Path(p) for p in raw.split(os.pathsep) if p]
    report: dict = {"directories": {}, "missing": []}
    for directory in directories:
        if not directory.is_dir():
            report["missing"].append(str(directory))
            continue
        results = execute(collect_calls(directory))
        summary = summarize(results)
        non_ok = [{"case_id": r.call.case_id, "turn": r.call.turn, "tool": r.call.tool,
                   "status": r.status, "detail": r.detail[:200],
                   "arguments": r.call.arguments}
                  for r in results if r.status != "ok"]
        report["directories"][directory.name] = {
            "path": str(directory), "calls": len(results),
            "totals": summary["totals"],
            "per_tool": {tool: {k: entry[k] for k in ("ok", "empty", "error", "skipped")}
                         for tool, entry in sorted(summary["per_tool"].items())},
            "non_ok": non_ok,
        }
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
