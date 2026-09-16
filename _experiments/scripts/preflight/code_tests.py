"""Gate 2: the code that produces and reads the run records still passes its tests.

Four suites and one generator check, because the rerun depends on all of them:
the platform tool layer (WS-A), the scoring module (WS-B), the runners (WS-C)
and this suite; plus `gen_tools_kr --check`, which fails while the generated
Korean arm is stale, so a description added on the platform side cannot reach
the English arm alone (D16, C2-005).

A skipped test is a test that did not run. The gate used to read the exit status
alone, so `test_templates.py` could skip itself for want of jinja2 and the
report still said the D21/C2-007/C2-018 template repairs had been exercised.
Every suite now runs with `-rs` and a skip fails the gate unless its reason is
in `skips_allowed.json`, which lists only reasons that are properties of the
release (optional drivers, app-only packages, unreleased source data).

The platform suite may need its own interpreter (`--platform-python`): it pins
numpy 2 through the tool layer while the serving stack follows vLLM (R1-R4).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from .gate import Check, Context, GateResult, run_command

NUMBER = 2
KEY = "tests"
TITLE = "code tests"

SKIPS_PATH = Path(__file__).resolve().parent / "skips_allowed.json"

_SUMMARY = re.compile(r"^(?:=+\s*)?(\d+ (?:passed|failed).*?)(?:\s*=+)?$", re.MULTILINE)
_SKIPPED = re.compile(r"^SKIPPED \[(\d+)\] (\S+?): (.*)$", re.MULTILINE)


def allowed_reasons() -> list[dict]:
    return json.loads(SKIPS_PATH.read_text(encoding="utf-8"))["allowed"]


def unexplained_skips(output: str, allowed: list[dict] | None = None) -> list[tuple[int, str, str]]:
    """(count, where, reason) for every skip whose reason is not on the allow-list."""
    allowed = allowed_reasons() if allowed is None else allowed
    patterns = [entry["reason_contains"] for entry in allowed]
    out = []
    for count, where, reason in _SKIPPED.findall(output):
        if not any(pattern in reason for pattern in patterns):
            out.append((int(count), where, reason.strip()))
    return out


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
    done = run_command([python or ctx.python, "-m", "pytest", "-rs", *args],
                       cwd=cwd or ctx.root, env=ctx.env, timeout=ctx.timeout_s)
    output = done.stdout + "\n" + done.stderr
    summary = _SUMMARY.findall(done.stdout) or _SUMMARY.findall(done.stderr)
    detail = summary[-1].strip() if summary else done.tail(4)
    skips = unexplained_skips(output)
    if skips:
        n = sum(count for count, _w, _r in skips)
        detail = (f"{detail}; {n} test(s) skipped for a reason "
                  f"{SKIPS_PATH.name} does not allow: "
                  + "; ".join(f"{where} ({reason})" for _c, where, reason in skips[:3]))
    return Check(name, done.ok and not skips, detail, done.command,
                 {"unexplained_skips": [{"count": c, "where": w, "reason": r}
                                        for c, w, r in skips]} if skips else {})


def _schema_arm_parity(ctx: Context) -> Check:
    """The Korean arm is generated from `agent.TOOLS`, so it cannot drift (D16)."""
    done = run_command([ctx.python, "-m", "_experiments.scripts.gen_tools_kr", "--check"],
                       cwd=ctx.root, env=ctx.env, timeout=600)
    return Check("Korean arm is generated from the platform schema", done.ok,
                 done.tail(4) or "tools_kr.py is up to date", done.command)
