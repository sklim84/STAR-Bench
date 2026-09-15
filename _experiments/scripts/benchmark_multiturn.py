"""Multi-turn runner: one Contract 2 record per turn, oracle or end-to-end.

    python -m _experiments.scripts.benchmark_multiturn \
        --config qwen35-27b-t --tools-lang kr --setting oracle \
        --cases-dir benchmarks_multiturn \
        --out _experiments/results_2026rerun/mt_oracle/qwen35-27b-t

`--setting oracle` injects the gold call and the gold tool result after every
turn, so each turn starts from a correct context. `--setting e2e` executes the
model's own calls on HOFINET and feeds the real results forward, so errors
propagate.

This runner takes the same options as the single-turn one and goes through the
same request layer, so the reasoning mode, the token budget, the gateway guard,
the schema arm and the provider options apply here too. They did not before, and
the gpt-oss (T) and (NT) multi-turn rows were in fact the same configuration run
twice (C2-012). `--tools-lang` makes every main-table column runnable on the
Korean schema (D17, L6-032).
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

SCENARIO_FILE = "cases_str_workflow.json"


def load_scenarios(cases_dir: Path) -> list[dict]:
    path = cases_dir / SCENARIO_FILE
    if not path.exists():
        raise SystemExit(f"no {SCENARIO_FILE} under {cases_dir}")
    scenarios = json.loads(path.read_text(encoding="utf-8"))
    if not scenarios:
        raise SystemExit(f"{path} is empty")
    return scenarios


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases-dir", type=Path, default=_PROJECT_ROOT / "benchmarks_multiturn",
                    help="benchmarks_multiturn or benchmarks_multiturn_en")
    ap.add_argument("--setting", choices=("oracle", "e2e"), default="oracle")
    ap.add_argument("-v", "--verbose", action="store_true")
    cli.add_common_arguments(ap)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")

    scenarios = load_scenarios(args.cases_dir)
    query_lang = "en" if args.cases_dir.name.endswith("_en") else "kr"
    # A scenario's questions are what the model reads; the flat `question` field the
    # preflight uses is the longest turn of the scenario.
    flat = [{"id": s["id"], "question": max((t["content"] for t in s.get("turns", [])),
                                            key=len, default="")} for s in scenarios]
    setup = cli.resolve(args, cases=flat, setting=args.setting, query_lang_default=query_lang)

    keys = loop.expected_keys(scenarios, multiturn=True)
    todo = cli.select_cases(scenarios, args, keys=keys, out_dir=args.out)

    client = ModelClient(cli.open_client(args, setup.chat_options), setup.chat_options)
    executor = loop.platform_executor()

    setup.writer.manifest({
        "setting": args.setting, "tools_lang": setup.arm.lang, "query_lang": setup.query_lang,
        "cases_dir": str(args.cases_dir), "n_scenarios_selected": len(todo),
        "n_scenarios_benchmark": len(scenarios), "n_turns_expected": len(keys),
        "config": setup.config, "provenance": setup.provenance, "argv": sys.argv[1:],
    })
    print(f"run {setup.run_id}: {len(todo)} scenario(s), {args.setting} -> {setup.writer.path}")

    for i, scenario in enumerate(todo, 1):
        turn_records = loop.run_scenario(
            scenario, client=client, arm=setup.arm, executor=executor, run_id=setup.run_id,
            config=setup.config, provenance=setup.provenance, query_lang=setup.query_lang,
            setting=args.setting)
        for record in turn_records:
            setup.writer.write(record)
        if args.verbose or i % 10 == 0:
            errors = sum(1 for r in turn_records if r.error)
            print(f"  [{i}/{len(todo)}] {scenario['id']}: {len(turn_records)} turn(s), "
                  f"{errors} error(s)")

    if not args.partial:
        summary = records.verify_run_complete(setup.writer.path, keys)
        print(f"records: {summary['n_records']}/{summary['n_expected']} "
              f"({'complete' if summary['complete'] else 'INCOMPLETE'})")
        if summary["missing"]:
            print(f"  missing: {len(summary['missing'])} (first: {summary['missing'][:5]})")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
