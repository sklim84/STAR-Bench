"""Pass 19 - the three questions the closeout case sweep found (L1-009, L1-013).

* `st_acr_042` asked to compare the 2023 and the 2024 channel ratios and name the
  channels whose risk rose, but its gold is one `analyze_channel_risk(20230101-20241231)`
  call, which returns a single aggregate over both years and cannot show a change.
  `param_checks` holds one entry per tool, so two calls of the same tool cannot both be
  pinned; the question therefore asks what the one aggregate answers.
* `st_cp_025` asserted that the fourth quarter of 2021 is when the data was first
  collected. HOFINET starts on 2021-09-01, so the first complete quarter is 2021 Q4 and
  the first collected quarter is 2021 Q3.
* `st_cp_040` made the same claim in English ("2021 Q4 is the first quarter of the data").

The gold blocks do not change; the questions now say what the data and the gold support.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both

SINGLE_AGGREGATE = ("analyze_channel_risk returns one aggregate over the range it is given, so a "
                    "question about the change between two years cannot be answered by the gold "
                    "call; the question asks for the aggregate the gold produces (L1-009).")
FIRST_QUARTER = ("HOFINET starts on 2021-09-01, so 2021 Q4 is the first complete quarter, not the "
                 "quarter the data was first collected in (L1-013).")

EDITS = {
    "st_acr_042": (
        "2023년과 2024년 채널별 이상거래 비율 변화를 비교하여 위험도가 증가한 채널을 식별해줘",
        "2023년 1월부터 2024년 12월까지 채널별 이상거래 비율을 분석해서 위험도가 가장 높은 채널을 식별해줘",
        "Please compare the changes in the ratio of suspicious transactions by channel for the "
        "years 2023 and 2024 to identify any channels with increased risk.",
        "Please analyze the ratio of suspicious transactions by channel from January 2023 to "
        "December 2024 and identify the channel that carries the highest risk.",
        SINGLE_AGGREGATE),
    "st_cp_025": (
        "2021년 4분기 데이터가 처음 수집된 시기야. 그 이후 3년 뒤인 2024년 4분기와 비교해서 "
        "이상거래 동향 변화를 분석해줘",
        "2021년 4분기는 데이터에서 온전한 첫 분기야. 3년 뒤인 2024년 4분기와 비교해서 "
        "이상거래 동향 변화를 분석해줘",
        "Please analyze the changes in suspicious transaction trends by comparing the data "
        "collected in the fourth quarter of 2021 with the fourth quarter of 2024, three years "
        "later.",
        "The fourth quarter of 2021 is the first complete quarter of the data. Please analyze "
        "the change in suspicious transaction trends by comparing it with the fourth quarter of "
        "2024, three years later.",
        FIRST_QUARTER),
    "st_cp_040": (
        "데이터 수집 첫 해인 2021년 4분기부터 시작해서",
        "데이터에서 온전한 첫 분기인 2021년 4분기부터 시작해서",
        "2021 Q4 is the first quarter of the data,",
        "2021 Q4 is the first complete quarter of the data,",
        FIRST_QUARTER),
}


def rewrite(bench: Bench, lang: str, case_id: str, before: str, after: str, why: str,
            log: ChangeLog) -> None:
    case = bench.get(case_id)
    if case is None:
        raise SystemExit(f"{case_id}: absent from {bench.root.name}")
    question = case["question"]
    if after in question:
        return                    # already applied
    if before not in question:
        raise SystemExit(f"{case_id} ({lang}): {before!r} is no longer in the question")
    log.set_field(case, lang, "question", question.replace(before, after), "L1-009/L1-013", why)


def main() -> int:
    kr, en = both()
    log = ChangeLog("p19_sweep_fixes",
                    "The three questions the closeout case sweep found, brought back to what "
                    "the gold and the data support (L1-009, L1-013).")
    for case_id, (kr_before, kr_after, en_before, en_after, why) in EDITS.items():
        rewrite(kr, "kr", case_id, kr_before, kr_after, why, log)
        rewrite(en, "en", case_id, en_before, en_after, why, log)
    kr.save()
    en.save()
    print(log.report())
    print(f"log: {log.write()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
