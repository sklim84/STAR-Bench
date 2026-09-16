"""Gate 2: the code that produces and reads the run records still passes its tests.

Four suites and one generator check, because the rerun depends on all of them:
the platform tool layer (WS-A), the scoring module (WS-B), the runners (WS-C)
and this suite; plus `gen_tools_kr --check`, which fails while the generated
Korean arm is stale, so a description added on the platform side cannot reach
the English arm alone (D16, C2-005).

The platform suite may need its own interpreter (`--platform-python`): it pins
numpy 2 through the tool layer while the serving stack follows vLLM (R1-R4).
"""

from __future__ import annotations

import re
import time

from .gate import Check, Context, GateResult, run_command

NUMBER = 2
KEY = "tests"
TITLE = "code tests"

_SUMMARY = re.compile(r"^(?:=+\s*)?(\d+ (?:passed|failed).*?)(?:\s*=+)?$", re.MULTILINE)


def run(ctx: Context) -> GateResult:
    started = time.time()
    checks = []

    if ctx.platform_root is None:
        checks.append(Check("platform test suite", False,
                            "no STAR-Bench-Web checkout found; set $STAR_BENCH_WEB"))
    else:
        checks.append(_pytest(ctx, "platform test suite", ["-q"],
                              python=ctx.platform_python, cwd=ctx.platform_root))

    checks.append(_pytest(ctx, "scoring test suite", ["-q", "_experiments/scripts/tests"]))
    checks.append(_pytest(ctx, "runner test suite", ["-q", "_experiments/scripts/tests_runner"]))
    checks.append(_pytest(ctx, "pre-flight test suite",
                          ["-q", "_experiments/scripts/tests_preflight"]))
    checks.append(_schema_arm_parity(ctx))

    return GateResult(KEY, NUMBER, TITLE, checks, time.time() - started)


def _pytest(ctx: Context, name: str, args: list[str], *, python: str | None = None,
            cwd=None) -> Check:
    done = run_command([python or ctx.python, "-m", "pytest", *args],
                       cwd=cwd or ctx.root, env=ctx.env, timeout=ctx.timeout_s)
    summary = _SUMMARY.findall(done.stdout) or _SUMMARY.findall(done.stderr)
    detail = summary[-1].strip() if summary else done.tail(4)
    return Check(name, done.ok, detail, done.command)


def _schema_arm_parity(ctx: Context) -> Check:
    """The Korean arm is generated from `agent.TOOLS`, so it cannot drift (D16)."""
    done = run_command([ctx.python, "-m", "_experiments.scripts.gen_tools_kr", "--check"],
                       cwd=ctx.root, env=ctx.env, timeout=600)
    return Check("Korean arm is generated from the platform schema", done.ok,
                 done.tail(4) or "tools_kr.py is up to date", done.command)
