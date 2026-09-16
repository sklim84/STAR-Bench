"""Run every single-turn data-fix pass in order, then the linter and the gold self-test.

    python -m _experiments.scripts.data_fixes.run_all --from 574c077  # reproduce from the snapshot

`--from <commit>` restores `benchmarks/` and `benchmarks_en/` from that commit first,
so the whole sequence replays from the pre-audit data and the result can be diffed
against the committed one, which is what "no hand edits" means. It is the only
supported way to run the sequence: without it `p01_apply_v3` stops on the first case
whose question is no longer the fix table's as-is value, which is the guard that keeps
an old fix table from overwriting a later pass. To re-check a finished tree, run the
verifiers instead (`lint_benchmarks`, `verify_gold_calls`, `scoring.gold_selftest`,
`new_cases.verify --gate`).

Every input the sequence reads lives in `inputs/` and is tracked, so a clean clone can
replay it.

`new_cases.author` (WS-G) is one of the steps: the 143 expansion cases have to exist
before the domain-review passes that were written on them, and before `p11_difficulty`
and `p12_notes` derive their values from the final question and gold.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import EN, KR, REPO

# `p11_difficulty` and `p12_notes` derive their values from the question and the gold,
# so they run last, after every pass that changes either. In the first round they ran
# before `p13_lint_fixes`, which left eight notes naming a value their gold no longer
# carried; the order below is what fixes that. `p13_lint_fixes` writes whole questions
# from its own table, so it runs before the passes that reword them.
PASSES = [
    "p01_apply_v3", "p02_dedupe", "p03_followups", "p04_accounts", "p05_predict_fraud",
    "p06_relevance", "p07_boundaries", "p08_clarification", "p09_contract1",
    "p10_executable_gold", "p13_lint_fixes",
    # closeout round (2026-09-16)
    "p14_risk_score", "p15_tool_cues", "p16_executable_gold2", "p17_boundary_parity",
    "p18_str_drafts", "p19_sweep_fixes",
    # The 143 expansion cases (WS-G) are authored here, because the domain review that
    # follows was written on them and the two difficulty and note passes have to see them.
    "new_cases.author",
    # domain review (2026-09-16)
    "p20_terminology", "p21_phrasing", "p22_clarification_audit",
    # closeout verification (2026-09-16): what the independent read found afterwards
    "p23_terminology_residue", "p24_risk_score_tails", "p25_catalog_gold",
    "p26_closeout_nits",
    "p11_difficulty", "p12_notes",
]


def restore(commit: str) -> None:
    """Put the snapshot in the working tree only.

    `git checkout <commit> -- <path>` also writes the index, and on a shared branch the next
    `git commit -a` from another work stream would then commit the snapshot over the fixed
    data. The index is reset straight back to HEAD, so only the working tree carries it.
    """
    for path in (KR, EN):
        relative = str(path.relative_to(REPO))
        subprocess.run(["git", "checkout", commit, "--", relative], cwd=REPO, check=True)
        subprocess.run(["git", "reset", "-q", "HEAD", "--", relative], cwd=REPO, check=True)
    print(f"benchmarks restored from {commit} (working tree only)")


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
        # Most passes take no arguments; the ones that parse a command line get an
        # empty one, or they would read this script's own arguments.
        takes_argv = bool(inspect.signature(module.main).parameters)
        rc = module.main([]) if takes_argv else module.main()
        if rc:
            return rc
    if args.skip_checks:
        return 0
    print("\n=== linter ===")
    from .lint_benchmarks import main as lint  # noqa: PLC0415

    rc = lint([])
    if rc:
        return rc
    print("\n=== gold call execution ===")
    from .verify_gold_calls import main as verify  # noqa: PLC0415

    for path in (KR, EN):
        rc = verify(["--benchmark", str(path), "--gate"])
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
