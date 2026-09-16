"""Pass 13 - what the linter found after every other pass had run.

`lint_benchmarks.py` is the gate, so anything it reports is fixed here rather than
by hand, and re-running the whole pipeline reproduces the fix.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both

EN_QUESTION = {
    "st_gta_017": ("Please analyze the trend of the monthly transaction status.",
                   "the EN question was word for word st_gta_013's, although the KR questions differ "
                   "('월별로 거래 추세' against '월간 거래 현황 추이'), so the EN arm held a duplicate "
                   "the KR arm did not (L1-025, duplicate_question)"),
}


def apply(kr: Bench, en: Bench, log: ChangeLog) -> None:
    en_by = en.by_id()
    for case_id, (text, why) in EN_QUESTION.items():
        log.set_field(en_by[case_id], "en", "question", text, "C1-011/L1-025", why)


def main() -> int:
    kr, en = both()
    log = ChangeLog("p13_lint_fixes", "Fix what the pre-flight linter reported (C1-011).")
    apply(kr, en, log)
    en.save()
    print(log.report())
    print(f"log: {log.write()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
