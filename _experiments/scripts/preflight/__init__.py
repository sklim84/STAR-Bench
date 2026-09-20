"""Pre-flight gate suite: everything that has to be true before a benchmark run.

One command runs every gate, in dependency order, and exits non-zero when any of
them fails:

    python -m _experiments.scripts.preflight.run --all

The suite never repairs anything. A gate that fails names the file, the id and
what is wrong, so the defect can be fixed where it lives.
"""

from .gate import Check, CommandRun, Context, GateResult, run_command

__all__ = ["Check", "CommandRun", "Context", "GateResult", "run_command"]
