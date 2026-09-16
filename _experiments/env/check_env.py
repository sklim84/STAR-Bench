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


def read_pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    if not path.exists():
        return pins
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
    return path, read_pins(path)


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
    pins = read_pins(_HERE / f"requirements-{name}.txt")
    problems: list[str] = []

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
        print(f"{name} stack: {len(pins)} pinned package(s), "
              f"{len(pins) - len(missing) - len(wrong)} match")
    for line in problems + wrong:
        print(f"  conflict: {line}", file=sys.stderr)
    for package in missing:
        print(f"  missing: {package}", file=sys.stderr)
    return 1 if (problems or wrong or missing) else 0


if __name__ == "__main__":
    raise SystemExit(main())
