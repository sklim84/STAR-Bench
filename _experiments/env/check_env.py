"""Checks an installed environment against the pins, and names every conflict.

    python -m _experiments.env.check_env                 # evaluation stack
    python -m _experiments.env.check_env --serving       # serving stack

The evaluation stack shares three packages with the platform tool layer. They are
pinned in two files, and a mismatch between them is what made the numpy version
unresolvable (R1-R4), so this compares the two files with each other and both
with what is installed.
"""

from __future__ import annotations

import argparse
import re
import sys
from importlib import metadata
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]

_PIN = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*==\s*([^\s#]+)")

# The stack name on the command line is not the file name. It used to be spelled
# into `requirements-{name}.txt`, which read `requirements-evaluation.txt`: a file
# that does not exist, so every evaluation pin went unchecked and the run still
# said "12 of 12 match".
PIN_FILES = {"evaluation": "requirements-eval.txt",
             "serving": "requirements-serving.txt"}


class MissingPinFile(FileNotFoundError):
    """A stack was asked for and its pin file is not in the repository."""


def pin_path(name: str) -> Path:
    return _HERE / PIN_FILES[name]


def read_pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    if not path.exists():
        raise MissingPinFile(f"{path} does not exist, so nothing would be checked")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _PIN.match(line)
        if match:
            pins[match.group(1).lower().replace("_", "-")] = match.group(2)
    return pins


def platform_tools_pins() -> tuple[Path | None, dict[str, str]]:
    sys.path.insert(0, str(_ROOT))
    try:
        from _experiments.scripts._platform import find_platform_root
        root = find_platform_root()
    except Exception:
        root = None
    if root is None:
        return None, {}
    path = Path(root) / "requirements-tools.txt"
    try:
        return path, read_pins(path)
    except MissingPinFile:
        return path, {}


def installed(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serving", action="store_true", help="check the serving stack instead")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    name = "serving" if args.serving else "evaluation"
    path = pin_path(name)
    try:
        pins = read_pins(path)
    except MissingPinFile as exc:
        print(f"  missing pin file: {exc}", file=sys.stderr)
        return 2
    problems: list[str] = []
    if not pins:
        print(f"  {path} pins nothing, so this check would pass on any environment",
              file=sys.stderr)
        return 2

    if not args.serving:
        tools_path, tools_pins = platform_tools_pins()
        if not tools_pins:
            problems.append("the platform requirements-tools.txt could not be read; "
                            "point $STAR_BENCH_WEB at the checkout")
        for package, version in sorted(tools_pins.items()):
            if package in pins and pins[package] != version:
                problems.append(f"{package}: this repository pins {pins[package]}, "
                                f"{tools_path} pins {version}")
        pins = {**tools_pins, **pins}

    missing, wrong = [], []
    for package, version in sorted(pins.items()):
        have = installed(package)
        if have is None:
            missing.append(package)
        elif have != version:
            wrong.append(f"{package}: installed {have}, pinned {version}")

    if not args.quiet:
        print(f"{name} stack ({path.name}): {len(pins)} pinned package(s), "
              f"{len(pins) - len(missing) - len(wrong)} match")
    for line in problems + wrong:
        print(f"  conflict: {line}", file=sys.stderr)
    for package in missing:
        print(f"  missing: {package}", file=sys.stderr)
    return 1 if (problems or wrong or missing) else 0


if __name__ == "__main__":
    raise SystemExit(main())
