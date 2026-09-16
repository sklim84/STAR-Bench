"""Run every single-turn data-fix pass in order, then the linter and the gold self-test.

    python -m _experiments.scripts.data_fixes.run_all                 # re-check a finished tree
    python -m _experiments.scripts.data_fixes.run_all --from 574c077  # reproduce from the snapshot

`--from <commit>` restores `benchmarks/` and `benchmarks_en/` from that commit first,
so the whole sequence replays from the pre-audit data and the result can be diffed
against the committed one. Without it the passes run over the current tree: those
that are already applied report zero changes, so this doubles as a consistency check.
"""

from __future__ import annotations

import argparse
import importlib
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import EN, KR, REPO

PASSES = [
    "p01_apply_v3", "p02_dedupe", "p03_followups", "p04_accounts", "p05_predict_fraud",
    "p06_relevance", "p07_boundaries", "p08_clarification", "p09_contract1",
    "p10_executable_gold", "p11_difficulty", "p12_notes", "p13_lint_fixes",
]


def restore(commit: str) -> None:
    for path in (KR, EN):
        subprocess.run(["git", "checkout", commit, "--", str(path.relative_to(REPO))],
                       cwd=REPO, check=True)
    print(f"benchmarks restored from {commit}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="commit", help="restore the benchmark directories from this commit first")
    ap.add_argument("--skip-checks", action="store_true", help="passes only, no linter and no self-test")
    args = ap.parse_args(argv)

    if args.commit:
        restore(args.commit)
    for name in PASSES:
        print(f"\n=== {name} ===")
        module = importlib.import_module(f".{name}", __package__)
        rc = module.main()
        if rc:
            return rc
    if args.skip_checks:
        return 0
    print("\n=== linter ===")
    from .lint_benchmarks import main as lint  # noqa: PLC0415

    rc = lint([])
    if rc:
        return rc
    print("\n=== gold self-test ===")
    from _experiments.scripts.scoring.gold_selftest import main as selftest  # noqa: PLC0415

    for path in (KR, EN):
        rc = selftest(["--benchmark", str(path)])
        if rc:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
