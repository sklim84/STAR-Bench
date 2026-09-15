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
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from _experiments.scripts.runner import cli, loop, records  # noqa: E402
from _experiments.scripts.runner.client import ModelClient  # noqa: E402

logger = logging.getLogger(__name__)

CASE_FILES = (
    "cases_query_transactions", "cases_get_statistics", "cases_get_account_profile",
    "cases_detect_aml_patterns", "cases_analyze_network", "cases_predict_fraud",
    "cases_score_account_risk", "cases_detect_smurfing_network",
    "cases_get_receiving_account_profile", "cases_multi_tool",
)


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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases-dir", type=Path, default=_PROJECT_ROOT / "benchmarks",
                    help="benchmark directory (benchmarks or benchmarks_en)")
    ap.add_argument("-v", "--verbose", action="store_true")
    cli.add_common_arguments(ap)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")

    cases = load_cases(args.cases_dir)
    query_lang = "en" if args.cases_dir.name.endswith("_en") else "kr"
    setup = cli.resolve(args, cases=cases, setting="single", query_lang_default=query_lang)

    keys = loop.expected_keys(cases, multiturn=False)
    todo = cli.select_cases(cases, args, keys=keys, out_dir=args.out)

    client = ModelClient(cli.open_client(args, setup.chat_options), setup.chat_options)
    executor = loop.platform_executor()
    max_rounds = args.max_rounds or loop.MAX_ROUNDS

    setup.writer.manifest({
        "setting": "single", "tools_lang": setup.arm.lang, "query_lang": setup.query_lang,
        "cases_dir": str(args.cases_dir), "n_cases_selected": len(todo),
        "n_cases_benchmark": len(cases), "config": setup.config,
        "provenance": setup.provenance, "max_rounds": max_rounds,
        "argv": sys.argv[1:],
    })
    print(f"run {setup.run_id}: {len(todo)} case(s) -> {setup.writer.path}")

    for i, case in enumerate(todo, 1):
        record = loop.run_case(
            case, client=client, arm=setup.arm, executor=executor, run_id=setup.run_id,
            config=setup.config, provenance=setup.provenance, query_lang=setup.query_lang,
            max_rounds=max_rounds)
        setup.writer.write(record)
        if args.verbose or i % 50 == 0:
            calls = sum(len(r.tool_calls) for r in record.rounds)
            print(f"  [{i}/{len(todo)}] {case['id']}: {len(record.rounds)} round(s), "
                  f"{calls} call(s), stop={record.stop_reason}")

    summary = records.verify_run_complete(setup.writer.path, keys) if not args.partial else None
    if summary is not None:
        print(f"records: {summary['n_records']}/{summary['n_expected']} "
              f"({'complete' if summary['complete'] else 'INCOMPLETE'})")
        if summary["missing"]:
            print(f"  missing: {len(summary['missing'])} (first: {summary['missing'][:5]})")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
