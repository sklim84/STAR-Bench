"""One command that runs every pre-flight gate before the rerun (L5-003).

    python -m _experiments.scripts.preflight.run --all
    python -m _experiments.scripts.preflight.run --all --report
    python -m _experiments.scripts.preflight.run --only data,gold
    python -m _experiments.scripts.preflight.run canary --config qwen35-4b-nt \
        --base-url http://127.0.0.1:11434/v1

Gates run in dependency order and all of them run even when an early one fails,
because the point is one report rather than one error at a time. The exit status
is non-zero if any gate failed. Nothing here repairs anything: a gate that fails
names the file and the id, and the stream that owns it fixes it.

Gate 6 (the canary) needs a served model, so it is a subcommand and not part of
`--all`; `--mock` runs it against the mock OpenAI server for testing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.preflight"

from . import canary as canary_module
from . import code_tests, data, environment, gold, report, serving
from .gate import Context, GateResult, STAR_BENCH_ROOT

GATES = {
    environment.KEY: environment,
    code_tests.KEY: code_tests,
    data.KEY: data,
    gold.KEY: gold,
    serving.KEY: serving,
}
ORDER = (environment.KEY, code_tests.KEY, data.KEY, gold.KEY, serving.KEY)


def _context(args) -> Context:
    return Context(root=Path(args.root), python=args.python or sys.executable,
                   platform_python=args.platform_python,
                   platform_root=Path(args.platform_root) if args.platform_root else None,
                   configs=tuple(c.strip() for c in (args.configs or "").split(",") if c.strip()),
                   check_serving_stack=args.serving_stack, timeout_s=args.timeout,
                   verbose=args.verbose)


def _add_shared(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=str(STAR_BENCH_ROOT), help="STAR-Bench checkout")
    parser.add_argument("--platform-root", help="STAR-Bench-Web checkout")
    parser.add_argument("--python", help="interpreter for this repository's commands")
    parser.add_argument("--platform-python",
                        help="interpreter for the platform suite, when it has its own environment")
    parser.add_argument("--configs", help="comma-separated configuration ids to check; "
                                          "default is every configuration in the run plan")
    parser.add_argument("--serving-stack", action="store_true",
                        help="also check the serving dependency pins (run this on the serving host)")
    parser.add_argument("--timeout", type=int, default=3600, help="seconds per command")
    parser.add_argument("-v", "--verbose", action="store_true")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-"):
        argv = ["gates", *argv]

    ap = argparse.ArgumentParser(prog="preflight", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = ap.add_subparsers(dest="command", required=True)

    gates = subparsers.add_parser("gates", help="run the gates that need no GPU (default)")
    gates.add_argument("--all", action="store_true", help="run every gate")
    gates.add_argument("--only", help="comma-separated gate keys: " + ", ".join(ORDER))
    gates.add_argument("--report", action="store_true",
                       help=f"write {report.REPORT_PATH.name} next to the other stream reports")
    gates.add_argument("--json", help="write the JSON report here "
                                      f"(default {report.JSON_PATH.name} with --report)")
    gates.add_argument("--update-allow-list", action="store_true",
                       help="rewrite allow_empty.json from this run, for review")
    _add_shared(gates)

    can = subparsers.add_parser("canary", help="gate 6: a fixed sample against a served model")
    can.add_argument("--config", help="serving configuration id")
    can.add_argument("--model", help="model id, when the run is not a registry entry")
    can.add_argument("--base-url", help="OpenAI-compatible endpoint")
    can.add_argument("--mock", action="store_true",
                     help="run against the mock server instead of a real one")
    can.add_argument("--setting", choices=("oracle", "e2e"), default="oracle")
    can.add_argument("--out", help="output directory (default: a fresh one under _experiments/logs)")
    can.add_argument("--thresholds", help="threshold file (default thresholds.json)")
    can.add_argument("--allow-unpinned-revision", action="store_true")
    can.add_argument("--no-env-check", action="store_true")
    can.add_argument("--rebuild-sample", action="store_true",
                     help="rewrite canary_sample.json from the benchmark and stop")
    can.add_argument("--json", help="write the JSON report here")
    _add_shared(can)

    args = ap.parse_args(argv)
    return _canary(args) if args.command == "canary" else _gates(args)


def _gates(args) -> int:
    ctx = _context(args)
    keys = [k.strip() for k in args.only.split(",")] if args.only else list(ORDER)
    unknown = [k for k in keys if k not in GATES]
    if unknown:
        print(f"unknown gate(s): {', '.join(unknown)}; known: {', '.join(ORDER)}", file=sys.stderr)
        return 2

    results: list[GateResult] = []
    for key in ORDER:
        module = GATES[key]
        if key not in keys:
            results.append(GateResult(key, module.NUMBER, module.TITLE, [], 0.0, skipped=True))
            continue
        if key == gold.KEY:
            result = module.run(ctx, update_allow_list=args.update_allow_list)
        else:
            result = module.run(ctx)
        results.append(result)
        print(result.line(), flush=True)
        for check in result.checks:
            if not check.ok:
                print(f"       {check.name}: {check.detail}", flush=True)
            elif args.verbose:
                print(f"       {check.name}: {check.detail}", flush=True)

    results.append(GateResult(canary_module.KEY, canary_module.NUMBER, canary_module.TITLE,
                              [], 0.0, skipped=True,
                              note="needs a served model; run the `canary` subcommand"))
    print(results[-1].line(), flush=True)

    ok = all(r.ok for r in results)
    command = "python -m _experiments.scripts.preflight.run " + " ".join(sys.argv[1:])
    versions = report.collect_versions(ctx)
    payload = report.as_json(results, command=command, versions=versions)

    json_path = Path(args.json) if args.json else (report.JSON_PATH if args.report else None)
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"json report: {json_path}")
    if args.report:
        path = report.write_markdown(results, command=command, versions=versions)
        print(f"report: {path}")

    print("\n" + ("all gates pass" if ok else "FAILED: "
                  + ", ".join(f"gate {r.number} {r.title}" for r in results if not r.ok)))
    return 0 if ok else 1


def _canary(args) -> int:
    ctx = _context(args)
    if args.rebuild_sample:
        sample = canary_module.build_sample(ctx.root)
        canary_module.SAMPLE_PATH.write_text(
            json.dumps(sample, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{canary_module.SAMPLE_PATH}: {len(sample['cases'])} cases covering "
              f"{len(sample['tools_covered'])} tools, {len(sample['scenarios'])} scenarios")
        return 0

    if not args.mock and not args.base_url:
        print("pass --base-url <endpoint>, or --mock to run against the mock server",
              file=sys.stderr)
        return 2
    if not args.config and not args.model and not args.mock:
        print("pass --config <registry id> or --model <model id>", file=sys.stderr)
        return 2

    out_dir = Path(args.out) if args.out else (
        ctx.root / "_experiments" / "logs" / f"canary_{_stamp()}")
    thresholds = Path(args.thresholds) if args.thresholds else None

    if args.mock:
        from _experiments.scripts.tests_runner.mock_server import MockOpenAIServer, text, tool_call

        def respond(request: dict):
            # One call, then an answer: the shape a healthy configuration produces.
            messages = request.get("messages") or []
            if messages and messages[-1].get("role") == "tool":
                return text("Here is the answer, based on the tool result.")
            return tool_call("get_statistics", {})

        with MockOpenAIServer() as server:
            server.respond_with(respond)
            result = canary_module.run(
                ctx, base_url=server.url, out_dir=out_dir,
                config_id=args.config, model=args.model or "mock",
                allow_unpinned=True, no_env_check=True, thresholds_path=thresholds,
                setting=args.setting)
    else:
        result = canary_module.run(
            ctx, base_url=args.base_url, out_dir=out_dir, config_id=args.config,
            model=args.model, allow_unpinned=args.allow_unpinned_revision,
            no_env_check=args.no_env_check, thresholds_path=thresholds, setting=args.setting)

    print(result.line())
    for check in result.checks:
        print(f"  {'pass' if check.ok else 'TRIPPED'}  {check.name}: {check.detail}")
    if args.json:
        Path(args.json).write_text(json.dumps(result.as_dict(), ensure_ascii=False, indent=1),
                                   encoding="utf-8")
        print(f"json report: {args.json}")
    print("\n" + ("canary clean" if result.ok else "FAILED: "
                  + ", ".join(c.name for c in result.failures)))
    return 0 if result.ok else 1


def _stamp() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
