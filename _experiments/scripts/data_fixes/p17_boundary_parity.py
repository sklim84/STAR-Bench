"""Pass 17 - one boundary, one meaning, in both languages (L1-025).

The v3 fix table's G7 group rewrote 27 English questions that turned Korean 이상 (>=)
into "over"/"more than" (>). The closeout found seven it missed, five of them on the
value the gold pins, so the English arm was told a different number from the one the
gold checks. A sweep over all 1,258 pairs (numbers, comparison words, negation and
units, `impl/WS-D2_report.md`) found two more of the same shape, and a second group
where both languages say "more than" although the pinned value is the tool's inclusive
threshold: `detect_dormant_reactivation` filters `>= dormant_days` and
`>= min_reactivation_amount`, `detect_smurfing_network` `>= min_counterparts`, and
`detect_ctr_candidates(structuring)` sums to the threshold "or above".

`ENGLISH_ONLY` is the first group, `BOTH` the second. Two further cases of the second
group, `st_dorm_046` and `st_smurf_049`, are 2026-09 expansion cases and were corrected
in `new_cases/g4_single_tool.py`, which authors them.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both

PARITY = ("the Korean says 이상 (>=) and the English said a strict '>', so the two arms were "
          "given different thresholds (L1-025).")
GOLD_BOUND = ("the tool filters on '>=' and the gold pins the boundary value, so a question that "
              "says 'more than' asks for something the gold does not check (L1-025, sweep).")
HOPS = "the Korean counts hops; 'level' is not the unit the tool takes (L1-025, sweep)."

# case id -> [(before, after), ...] for the English question only.
ENGLISH_ONLY: dict[str, list[tuple[str, str]]] = {
    "st_an_017": [("up to level 2", "up to 2 hops")],
    "st_ctr_008": [("with amounts exceeding the reporting threshold",
                    "with amounts at or above the reporting threshold")],
    "st_ctr_013": [("high-value transactions over 50 million won",
                    "high-value transactions of 50 million won or more")],
    "st_ctr_030": [("cash transactions that exceed the reporting threshold",
                    "cash transactions at or above the reporting threshold")],
    "st_dorm_022": [("started transactions exceeding 5,000,000 won",
                     "started transactions of 5,000,000 won or more")],
    "st_dorm_028": [("where the transaction amount is over 30 million won",
                     "where the transaction amount is 30 million won or more")],
    "st_dorm_035": [("a withdrawal of over 10,000,000 won",
                     "a withdrawal of 10,000,000 won or more")],
    "st_dorm_038": [("dormant for over a year", "dormant for a year or more"),
                    ("with a transaction amount of over 20 million won",
                     "with a transaction amount of 20 million won or more")],
    "st_dorm_041": [("have transactions exceeding 50 million won upon reactivation",
                     "have transactions of 50 million won or more upon reactivation")],
    "st_qt_004": [("with a transaction amount of over 10 million won",
                   "with a transaction amount of 10 million won or more")],
    "st_qt_045": [("between 10,000,000 and 50,000,000 won",
                   "between 10,000,000 and 50,000,000 won inclusive")],
    "st_qt_050": [("medium (1,000,000 to 10,000,000 KRW)",
                   "medium (1,000,000 KRW or more but less than 10,000,000 KRW)"),
                  ("large (over 10,000,000 KRW)", "large (10,000,000 KRW or more)")],
}

# case id -> ([(kr before, kr after), ...], [(en before, en after), ...])
BOTH: dict[str, tuple[list[tuple[str, str]], list[tuple[str, str]]]] = {
    "st_ctr_019": ([("합산하면 천만원이 넘는데", "합산하면 천만원 이상인데")],
                   [("that total over 10 million won", "that total 10 million won or more")]),
    "st_dorm_026": ([("휴면 기간이 1년(365일) 넘는", "휴면 기간이 1년(365일) 이상인")],
                    [("dormant for more than 1 year (365 days)",
                      "dormant for 1 year (365 days) or more")]),
    "st_dorm_032": ([("거래 금액이 5000만원을 넘는", "거래 금액이 5000만원 이상인")],
                    [("the transaction amount exceeds 50 million won",
                      "the transaction amount is 50 million won or more")]),
    "st_dorm_042": ([("6개월 넘게 거래가 없던", "6개월 이상 거래가 없던")],
                    [("no activity for over 6 months", "no activity for 6 months or more")]),
    "st_dorm_044": ([("재활성화 금액이 500만원을 넘는", "재활성화 금액이 500만원 이상인")],
                    [("a reactivation amount exceeding 5,000,000 won",
                      "a reactivation amount of 5,000,000 won or more")]),
}

KR_BAND = ("중액(100만원~1000만원)", "중액(100만원 이상 1000만원 미만)")


def rewrite(bench: Bench, lang: str, case_id: str, edits, issue: str, why: str,
            log: ChangeLog) -> None:
    case = bench.get(case_id)
    if case is None:
        raise SystemExit(f"{case_id}: absent from {bench.root.name}")
    question = case["question"]
    for before, after in edits:
        if after in question:
            continue              # already applied
        if before not in question:
            raise SystemExit(f"{case_id} ({lang}): {before!r} is no longer in the question")
        question = question.replace(before, after)
    log.set_field(case, lang, "question", question, issue, why)


def main() -> int:
    kr, en = both()
    log = ChangeLog("p17_boundary_parity",
                    "Comparison words that match the threshold the gold checks, in both "
                    "languages (L1-025).")
    for case_id, edits in ENGLISH_ONLY.items():
        why = HOPS if case_id == "st_an_017" else PARITY
        rewrite(en, "en", case_id, edits, "L1-025", why, log)
    # st_qt_050's Korean band boundary is open at 1000만원 in both directions; the
    # reference SQL puts that value in the large band.
    rewrite(kr, "kr", "st_qt_050", [KR_BAND], "L1-025",
            "the Korean bands overlapped at 1000만원; the reference SQL puts it in the large "
            "band (L1-025, sweep).", log)
    for case_id, (kr_edits, en_edits) in BOTH.items():
        rewrite(kr, "kr", case_id, kr_edits, "L1-025", GOLD_BOUND, log)
        rewrite(en, "en", case_id, en_edits, "L1-025", GOLD_BOUND, log)
    kr.save()
    en.save()
    log.note(f"{len(ENGLISH_ONLY)} English questions brought back to the Korean boundary; "
             f"{len(BOTH)} pairs moved onto the inclusive threshold the tool applies; "
             f"st_dorm_046 and st_smurf_049 are fixed in new_cases/g4_single_tool.py.")
    print(log.report())
    print(f"log: {log.write()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
