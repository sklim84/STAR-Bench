"""Single-turn runner: writes Contract 2 records, and nothing else.

    python -m _experiments.scripts.benchmark \
        --config qwen35-27b-t --tools-lang kr --cases-dir benchmarks \
        --out _experiments/results_2026rerun/single/qwen35-27b-t

The runner no longer scores. It records what the model did, and
`_experiments/scripts/scoring/score_runs.py` reads those records together with
the gold and writes the eval files, so a scoring rule can change without
re-running a model (L4-016). The comparison spreadsheet and the aggregate tables
that used to live here moved with it.

Old checkpoints are never read: a run writes into a fresh directory, and
`--resume` skips only the cases that same directory already holds a record for,
after checking that its contents belong to this benchmark (C2-014, C2-015,
L5-027).

`--limit N` is a smoke run: the first N cases of the benchmark are the run, and
the run is verified against those N. It used to be checked against the whole
benchmark, so every smoke run ended "INCOMPLETE" with exit 1.

`--concurrency N` runs N cases at once (default from the registry). Cases share
nothing: each worker thread builds its own client, and the records are written
and the file sorted from the calling thread, so the output file is the same one a
serial run produces. `--concurrency 1` runs inline.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from _experiments.scripts.runner import cli, loop, parallel, records  # noqa: E402
from _experiments.scripts.runner import provenance as runner_provenance  # noqa: E402

logger = logging.getLogger(__name__)

def load_cases(cases_dir: Path) -> list[dict]:
    """Every case of the benchmark directory, in file order then case order."""
    cases: list[dict] = []
    seen: set[str] = set()
    for path in sorted(cases_dir.glob("cases_*.json")):
        for case in json.loads(path.read_text(encoding="utf-8")):
            case_id = case.get("id")
            if case_id in seen:
                raise SystemExit(f"{path.name}: duplicate case id {case_id}")
            seen.add(case_id)
            case.setdefault("_source", path.name)
            cases.append(case)
    if not cases:
        raise SystemExit(f"no cases_*.json under {cases_dir}")
    return cases


def main(argv: list[str] | None = None, *, executor=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases-dir", type=Path, default=_PROJECT_ROOT / "benchmarks",
                    help="benchmark directory (benchmarks or benchmarks_en)")
    ap.add_argument("-v", "--verbose", action="store_true")
    cli.add_common_arguments(ap)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")

    benchmark = load_cases(args.cases_dir)
    cases = cli.apply_limit(benchmark, args)
    query_lang = "en" if args.cases_dir.name.endswith("_en") else "kr"
    setup = cli.resolve(args, cases=cases, setting="single", query_lang_default=query_lang,
                        cases_dir=args.cases_dir)

    keys = loop.expected_keys(cases, multiturn=False)
    todo = cli.select_cases(cases, args, keys=keys, out_dir=args.out)

    clients = cli.client_pool(args, setup.chat_options)
    executor = executor or loop.platform_executor()
    max_rounds = args.max_rounds or loop.MAX_ROUNDS
    concurrency = setup.concurrency

    setup.writer.manifest({
        "setting": "single", "tools_lang": setup.arm.lang, "query_lang": setup.query_lang,
        "cases_dir": str(args.cases_dir), "n_cases_selected": len(todo),
        "n_cases_benchmark": len(benchmark), "n_cases_run": len(cases),
        "limit": args.limit, "config": setup.config,
        "benchmark_file_hashes": runner_provenance.benchmark_file_hashes(args.cases_dir),
        "provenance": setup.provenance, "max_rounds": max_rounds,
        "concurrency": concurrency, "argv": sys.argv[1:],
    })
    print(f"run {setup.run_id}: {len(todo)} case(s), concurrency {concurrency} "
          f"-> {setup.writer.path}")

    def work(case: dict):
        return loop.run_case(
            case, client=clients.get(), arm=setup.arm, executor=executor, run_id=setup.run_id,
            config=setup.config, provenance=setup.provenance, query_lang=setup.query_lang,
            max_rounds=max_rounds)

    done = 0

    def collect(case: dict, record, error: BaseException | None) -> None:
        nonlocal done
        done += 1
        if error is not None:
            # A worker that raised is this case's failure and nobody else's: the
            # case still gets a record, with the reason (L5-019).
            record = loop.failed_record(
                case["id"], error, run_id=setup.run_id, setting="single",
                tools_lang=setup.arm.lang, query_lang=setup.query_lang,
                config=setup.config, provenance=setup.provenance)
            logger.error("case %s raised: %s", case.get("id"), error)
        setup.writer.write(record)
        if args.verbose or done % 50 == 0:
            calls = sum(len(r.tool_calls) for r in record.rounds)
            print(f"  [{done}/{len(todo)}] {case['id']}: {len(record.rounds)} round(s), "
                  f"{calls} call(s), stop={record.stop_reason}")

    parallel.run_jobs(todo, work, concurrency=concurrency, on_result=collect)
    setup.writer.sort_by(keys)

    # A resumed run's own file holds only the cases that were missing, so the
    # whole output directory is what covers the case list.
    verify_target = args.out if args.resume else setup.writer.path
    summary = records.verify_run_complete(verify_target, keys) if not args.partial else None
    if summary is not None:
        scope = f", limited to {args.limit} of {len(benchmark)}" if args.limit else ""
        print(f"records: {summary['n_records']}/{summary['n_expected']} "
              f"({'complete' if summary['complete'] else 'INCOMPLETE'}{scope})")
        if summary["missing"]:
            print(f"  missing: {len(summary['missing'])} (first: {summary['missing'][:5]})")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
