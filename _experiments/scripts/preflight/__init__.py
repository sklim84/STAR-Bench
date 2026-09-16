"""Pre-flight gate suite: everything that has to be true before the rerun starts.

Register step 10, issue L5-003. One command runs every gate the other work
streams left callable, in dependency order, and exits non-zero when any of them
fails:

    python -m _experiments.scripts.preflight.run --all

The suite never repairs anything. A gate that fails names the file, the id and
what is wrong, so the defect goes back to the stream that owns it.
"""

from .gate import Check, CommandRun, Context, GateResult, run_command

__all__ = ["Check", "CommandRun", "Context", "GateResult", "run_command"]
