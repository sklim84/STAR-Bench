"""Locate the companion AML agent platform repository (STAR-Bench-Web).

This repository holds the benchmark cases, the evaluator, and the runner
scripts.  The *executable* AML tools -- the 23 functions the agent calls, the
DuckDB query layer, and the HOFINET transaction environment -- live in the
companion platform repository, which the paper releases alongside this one.

The tool layer is deliberately **not** copied here.  Both repositories are
public, so a second copy would only invite the two from drifting apart; keeping
one copy means the benchmark always executes exactly the code the platform
ships.

Expected layout (either name is recognised)::

    <workspace>/
      STAR-Bench/          <- this repository
      STAR-Bench-Web/      <- companion platform

Resolution order:

1. ``$STAR_BENCH_WEB``, if set -- use this when the two repositories are not
   siblings.
2. A sibling directory of this repository that contains
   ``src/features/agent.py``.  The scan is case-insensitive, so checkouts
   named ``STAR-Bench-Web``, ``star-bench-web`` or anything in between all
   resolve on case-sensitive filesystems.

If neither succeeds, :func:`ensure_platform_on_path` raises with instructions
rather than letting the caller die on an opaque ``ModuleNotFoundError``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

__all__ = [
    "STARBENCH_ROOT",
    "find_platform_root",
    "ensure_platform_on_path",
]

STARBENCH_ROOT = Path(__file__).resolve().parent.parent.parent

# Marker that identifies a platform checkout rather than any sibling directory.
_MARKER = Path("src") / "features" / "agent.py"

_ENV_VAR = "STAR_BENCH_WEB"
_PREFERRED_NAMES = ("STAR-Bench-Web", "star-bench-web")


def _is_platform(path: Path) -> bool:
    return (path / _MARKER).is_file()


def find_platform_root() -> Path | None:
    """Return the platform repository root, or ``None`` if it cannot be found."""
    env_value = os.environ.get(_ENV_VAR)
    if env_value:
        candidate = Path(env_value).expanduser().resolve()
        if _is_platform(candidate):
            return candidate
        # An explicitly configured path that is wrong is a mistake worth
        # surfacing, not something to silently fall back from.
        raise RuntimeError(
            f"${_ENV_VAR} is set to {candidate}, but {candidate / _MARKER} does not "
            f"exist. Point it at the STAR-Bench-Web checkout, or unset it to fall "
            f"back to sibling-directory discovery."
        )

    workspace = STARBENCH_ROOT.parent

    for name in _PREFERRED_NAMES:
        candidate = workspace / name
        if _is_platform(candidate):
            return candidate

    # Case-insensitive sweep, so the directory name does not have to match.
    wanted = {name.lower() for name in _PREFERRED_NAMES}
    try:
        siblings = sorted(workspace.iterdir())
    except OSError:
        return None
    for candidate in siblings:
        if candidate.is_dir() and candidate.name.lower() in wanted and _is_platform(candidate):
            return candidate

    return None


def ensure_platform_on_path() -> Path:
    """Put this repository and the platform on ``sys.path``; return the platform root.

    Raises:
        RuntimeError: if the platform repository cannot be located, with the
            two ways to fix it.
    """
    if str(STARBENCH_ROOT) not in sys.path:
        sys.path.insert(0, str(STARBENCH_ROOT))

    platform_root = find_platform_root()
    if platform_root is None:
        raise RuntimeError(
            "Could not find the STAR-Bench-Web platform repository, which provides "
            "the executable AML tools (src.features.agent).\n"
            "\n"
            "Fix it in one of two ways:\n"
            f"  1. Clone it next to this repository:\n"
            f"       cd {STARBENCH_ROOT.parent}\n"
            f"       git clone <STAR-Bench-Web URL> STAR-Bench-Web\n"
            f"  2. Or point at an existing checkout:\n"
            f"       export {_ENV_VAR}=/path/to/STAR-Bench-Web\n"
            "\n"
            "The platform also needs the HOFINET transaction environment and the "
            "trained detector; see its README for the one-time setup."
        )

    if str(platform_root) not in sys.path:
        sys.path.insert(0, str(platform_root))
    return platform_root


if __name__ == "__main__":
    # Used by the shell runners: prints the platform root, or exits non-zero
    # with the instructions on stderr.
    try:
        print(ensure_platform_on_path())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
