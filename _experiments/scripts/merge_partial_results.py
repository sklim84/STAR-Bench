"""Merges partial Contract 2 runs into one record set, and says where each line came from.

    python -m _experiments.scripts.merge_partial_results \
        --runs _experiments/runs/single/qwen35-27b-t \
        --expect benchmarks --out merged.jsonl

The old merger read checkpoints line by line into `records[key] = rec` and kept
whichever line came last, with no run identifier anywhere. A forced rerun that
failed therefore left the older record in place and looked like a success. This
one:

  * keeps the newest record per key by the run's own `started_at`, and prints the
    run each key was taken from;
  * refuses when a key appears in more than one run and `--prefer` does not say
    which run wins;
  * refuses when a key the caller said would be rerun (`--rerun-key`, or every
    key of a `.partial` file) is missing from the newer run, instead of silently
    falling back to the old record;
  * checks the merged set against the case list and exits non-zero when it is
    incomplete.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from _experiments.scripts.runner import records as R


def _key(rec: dict) -> str:
    case_id = rec.get("case_id")
    return case_id if rec.get("turn") is None else f"{case_id}#{rec['turn']}"


def _started(rec: dict) -> str:
    return (rec.get("provenance") or {}).get("started_at") or ""


def _expected_keys(path: Path) -> list[str]:
    from _experiments.scripts.runner.loop import expected_keys

    multiturn = (path / "cases_str_workflow.json").exists()
    if multiturn:
        cases = json.loads((path / "cases_str_workflow.json").read_text(encoding="utf-8"))
    else:
        cases = []
        for case_file in sorted(path.glob("cases_*.json")):
            cases.extend(json.loads(case_file.read_text(encoding="utf-8")))
    return expected_keys(cases, multiturn=multiturn)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", required=True, type=Path, help="directory of *.jsonl run records")
    ap.add_argument("--out", required=True, type=Path, help="merged JSONL file")
    ap.add_argument("--expect", type=Path,
                    help="benchmark directory the merged set must cover completely")
    ap.add_argument("--prefer", help="run id that wins where two runs hold the same key")
    ap.add_argument("--rerun-key", action="append", default=[],
                    help="key that must come from a newer run; repeatable")
    args = ap.parse_args(argv)

    files = sorted(p for p in args.runs.glob("*.jsonl"))
    if not files:
        print(f"no *.jsonl under {args.runs}", file=sys.stderr)
        return 1

    by_key: dict[str, list[dict]] = defaultdict(list)
    partial_keys: set[str] = set()
    for path in files:
        for rec in R.read_records(path):
            by_key[_key(rec)].append(rec)
            if path.name.endswith(".partial.jsonl"):
                partial_keys.add(_key(rec))

    chosen: dict[str, dict] = {}
    conflicts: list[str] = []
    for key, recs in by_key.items():
        if len(recs) == 1:
            chosen[key] = recs[0]
            continue
        runs = {r.get("run_id") for r in recs}
        if args.prefer and args.prefer in runs:
            chosen[key] = next(r for r in recs if r.get("run_id") == args.prefer)
            continue
        ordered = sorted(recs, key=_started)
        if _started(ordered[-1]) == _started(ordered[0]):
            conflicts.append(f"{key}: {len(recs)} records from {sorted(runs)} with no "
                             f"distinguishing start time; pass --prefer <run id>")
            continue
        chosen[key] = ordered[-1]

    missing_rerun = sorted(k for k in set(args.rerun_key) | partial_keys
                           if k in chosen and chosen[k].get("run_id") is None)
    unseen_rerun = sorted(k for k in args.rerun_key if k not in chosen)
    if unseen_rerun:
        conflicts.append(f"{len(unseen_rerun)} key(s) marked for rerun have no record at all: "
                         f"{unseen_rerun[:5]}")
    if missing_rerun:
        conflicts.append(f"{len(missing_rerun)} key(s) marked for rerun carry no run id")
    if conflicts:
        for c in conflicts:
            print(f"refusing to merge: {c}", file=sys.stderr)
        return 2

    sources: dict[str, int] = defaultdict(int)
    for rec in chosen.values():
        sources[rec.get("run_id") or "?"] += 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        for key in sorted(chosen):
            fh.write(json.dumps(chosen[key], ensure_ascii=False, default=str) + "\n")
    print(f"merged {len(chosen)} record(s) into {args.out}")
    for run_id, n in sorted(sources.items(), key=lambda kv: -kv[1]):
        print(f"  {n:6d} from {run_id}")

    if args.expect:
        summary = R.verify_run_complete(args.out, _expected_keys(args.expect))
        print(f"coverage: {summary['n_records']}/{summary['n_expected']} "
              f"({'complete' if summary['complete'] else 'INCOMPLETE'})")
        if not summary["complete"]:
            print(f"  missing {len(summary['missing'])}, unknown {len(summary['unknown'])}",
                  file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
