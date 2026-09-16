"""The gate framework: one pass/fail line per check, one JSON report per run.

A gate is a function `run(ctx) -> GateResult`. It reports; it does not repair.
Every check that shells out records the exact command it ran, because the point
of the report is that a co-author can paste the failing command and see the same
thing (L5-003).
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["Check", "CommandRun", "Context", "GateResult", "run_command", "format_line"]

STAR_BENCH_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_DIR = Path(__file__).resolve().parent
IMPL_DIR = STAR_BENCH_ROOT / "_experiments" / "dataset_fix_20260915" / "impl"

SINGLE_TURN_DIRS = ("benchmarks", "benchmarks_en")
MULTI_TURN_DIRS = ("benchmarks_multiturn", "benchmarks_multiturn_en")
BENCHMARK_DIRS = SINGLE_TURN_DIRS + MULTI_TURN_DIRS


@dataclass
class CommandRun:
    command: str
    returncode: int
    stdout: str
    stderr: str
    elapsed_s: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def tail(self, lines: int = 3) -> str:
        text = (self.stdout.strip() + "\n" + self.stderr.strip()).strip()
        return "\n".join(text.splitlines()[-lines:]) if text else ""


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    command: str | None = None
    data: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        out = {"name": self.name, "ok": self.ok, "detail": self.detail}
        if self.command:
            out["command"] = self.command
        if self.data:
            out["data"] = self.data
        return out


@dataclass
class GateResult:
    key: str
    number: int
    title: str
    checks: list[Check] = field(default_factory=list)
    elapsed_s: float = 0.0
    skipped: bool = False
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.skipped or all(c.ok for c in self.checks)

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.ok]

    def line(self) -> str:
        return format_line(self)

    def as_dict(self) -> dict:
        return {"gate": self.key, "number": self.number, "title": self.title,
                "ok": self.ok, "skipped": self.skipped, "note": self.note,
                "elapsed_s": round(self.elapsed_s, 2),
                "checks": [c.as_dict() for c in self.checks]}


def format_line(result: GateResult) -> str:
    if result.skipped:
        status = "SKIP"
    else:
        status = "PASS" if result.ok else "FAIL"
    passed = sum(1 for c in result.checks if c.ok)
    return (f"[{status}] gate {result.number} {result.title:<22s} "
            f"{passed}/{len(result.checks)} checks  {result.elapsed_s:6.1f}s")


@dataclass
class Context:
    """What the gates are allowed to know about the machine they run on."""
    root: Path = STAR_BENCH_ROOT
    platform_root: Path | None = None
    python: str = sys.executable
    platform_python: str | None = None
    configs: tuple[str, ...] = ()
    check_serving_stack: bool = False
    timeout_s: int = 3600
    verbose: bool = False

    def __post_init__(self):
        self.root = Path(self.root)
        if self.platform_root is None:
            self.platform_root = _find_platform(self.root)
        if self.platform_python is None:
            self.platform_python = self.python

    @property
    def env(self) -> dict:
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            p for p in [str(self.root), str(self.platform_root or ""), env.get("PYTHONPATH", "")] if p)
        env.setdefault("PYTHONWARNINGS", "ignore")
        return env


def _find_platform(root: Path) -> Path | None:
    configured = os.environ.get("STAR_BENCH_WEB")
    if configured:
        candidate = Path(configured).expanduser().resolve()
        return candidate if (candidate / "src" / "features" / "agent.py").is_file() else None
    for name in ("STAR-Bench-Web", "star-bench-web"):
        candidate = root.parent / name
        if (candidate / "src" / "features" / "agent.py").is_file():
            return candidate
    return None


def run_command(argv: list[str], *, cwd: Path, env: dict | None = None,
                timeout: int = 3600) -> CommandRun:
    text = " ".join(shlex.quote(a) for a in argv)
    started = time.time()
    try:
        done = subprocess.run(argv, cwd=str(cwd), env=env, capture_output=True,
                              text=True, timeout=timeout)
        return CommandRun(text, done.returncode, done.stdout, done.stderr, time.time() - started)
    except subprocess.TimeoutExpired as exc:
        return CommandRun(text, 124, exc.stdout or "", f"timed out after {timeout}s",
                          time.time() - started)
    except OSError as exc:
        return CommandRun(text, 127, "", str(exc), time.time() - started)
