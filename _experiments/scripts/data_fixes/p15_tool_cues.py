"""Pass 15 - the last questions whose wording fits two gold tools (L1-003, L1-010, D11).

`p07_boundaries` added a discriminating cue to 66 questions. The closeout found five
questions that still say 대포통장 / "mule account", a word the data used for a
`detect_aml_patterns(funnel)` gold, for a `get_receiving_account_profile` gold and for
an abstention, and three that used bare splitting language across a
`detect_ctr_candidates(structuring)` gold and a `get_fraud_type_summary(fraud_type=3)`
gold. Each question now carries the one cue its own gold answers, and no alternatives
are added (D11).
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both

FUNNEL = ("detect_aml_patterns(funnel) is the only tool that returns accounts with many "
          "incoming and few outgoing counterparties; 대포통장 / 'mule account' named that tool, "
          "the receiving-account profile and an abstention at the same time (L1-003, D11).")
INBOUND = ("get_receiving_account_profile is the only tool that returns the inbound count, the "
           "number of distinct senders and sending banks and the inbound fraud ratio of one "
           "account (L1-003, D11).")
NO_TOOL = ("the question asks for investigative criteria rather than for data, so no tool "
           "answers it; the crime name that pointed at two tools is gone (L1-003, D10).")
CTR = ("detect_ctr_candidates(mode=structuring) is defined by the reporting threshold: single "
       "transactions below it that sum to it or above on one day. The question now names the "
       "threshold, so it no longer reads as a fraud-type filter (L1-010, D11).")
TYPE3 = ("get_fraud_type_summary(fraud_type=3) summarises a HOFINET label, so the question names "
         "the label rather than describing CTR structuring (L1-010, D11).")

# case id -> (Korean before, Korean after, English before, English after, why)
EDITS: dict[str, tuple[str, str, str, str, str]] = {
    "st_mtool_013": (
        "대포통장 패턴도 탐지해줘",
        "입금 상대는 많고 출금 상대는 소수인 funnel 계좌 패턴도 탐지해줘",
        "also detect any mule account patterns",
        "also detect funnel account patterns: many incoming counterparties and only a few "
        "outgoing ones",
        FUNNEL),
    "st_mtool_019": (
        "대포통장 패턴을 탐지하고",
        "입금 상대는 많고 출금 상대는 소수인 funnel 계좌 패턴을 탐지하고",
        "Detect mule account patterns,",
        "Detect funnel account patterns with many incoming and few outgoing counterparties,",
        FUNNEL),
    "st_mtool_059": (
        "대포통장 패턴도 탐지해줘",
        "입금 상대는 많고 출금 상대는 소수인 funnel 계좌 패턴도 탐지해줘",
        "detect any mule account patterns",
        "detect funnel account patterns with many incoming and few outgoing counterparties",
        FUNNEL),
    "st_grap_039": (
        "입금계좌 9000000000017070의 수취 패턴을 종합 분석하여 대포통장 여부를 판단해줘",
        "입금계좌 9000000000017070로 들어온 거래 건수와 송금 계좌·송금 기관 수, "
        "이상거래 비율을 수취 프로파일로 조회해줘",
        "Please conduct a comprehensive analysis of the deposit account 9000000000017070's "
        "receipt patterns to determine if it is a mule account.",
        "Please retrieve the receiving profile of deposit account 9000000000017070: its inbound "
        "transaction count, the number of distinct sending accounts and sending banks, and the "
        "inbound suspicious-transaction ratio.",
        INBOUND),
    "st_grap_irr_002": (
        "입금계좌번호 없이 대포통장을 탐지하는 방법을 알려줘",
        "입금계좌 정보를 확보하기 전에 수취 계좌가 자금세탁에 이용됐는지 판단하는 "
        "일반적인 기준을 설명해줘",
        "Please provide a method for detecting mule accounts without the deposit account number.",
        "Please explain the general criteria for judging whether a receiving account has been "
        "used for money laundering, before the deposit account information is obtained.",
        NO_TOOL),
    "st_ctr_029": (
        "거래 분할 패턴을 탐지해줘",
        "CTR 보고 기준 미만으로 나눈 거래 분할 패턴을 탐지해줘",
        "Please detect transaction splitting patterns.",
        "Please detect transaction splitting patterns that stay below the CTR reporting threshold.",
        CTR),
    "st_ctr_033": (
        "대금을 여러 번에 나눠서 입금하는 거래를 찾아줘",
        "대금을 CTR 보고 기준 미만으로 여러 번에 나눠서 입금하는 거래를 찾아줘",
        "Please find transactions where one payment is split into several deposits.",
        "Please find transactions where one payment is split into several deposits, each of them "
        "below the CTR reporting threshold.",
        CTR),
    "st_gfs_041": (
        "금액을 여러 번으로 쪼개 보낸 것으로 의심되는 이상거래 현황을 요약해줘",
        "이상거래 유형 가운데 분할 거래(유형3)로 분류된 건의 건수와 금액 요약을 보여줘",
        "Please summarize the status of suspicious transactions in which an amount appears to "
        "have been split into several transfers.",
        "Among the suspicious transaction types, please show the count and the amount summary of "
        "the ones labelled split transaction (type 3).",
        TYPE3),
}

BANNED = (("대포통장", "kr"), ("mule account", "en"))


def apply_one(bench: Bench, lang: str, log: ChangeLog) -> None:
    by_id = bench.by_id()
    index = 0 if lang == "kr" else 2
    for case_id, edit in EDITS.items():
        before, after, why = edit[index], edit[index + 1], edit[4]
        case = by_id.get(case_id)
        if case is None:
            raise SystemExit(f"{case_id}: absent from {bench.root.name}")
        question = case["question"]
        if after in question:
            continue              # already applied
        if before not in question:
            raise SystemExit(f"{case_id} ({lang}): {before!r} is no longer in the question")
        log.set_field(case, lang, "question", question.replace(before, after), "L1-003/L1-010/D11", why)


def residue(bench: Bench, lang: str) -> list[str]:
    word = "대포통장" if lang == "kr" else "mule account"
    return [f"{case['id']} ({lang})" for _, case in bench.cases()
            if word in case["question"].lower() or word in case["question"]]


def main() -> int:
    kr, en = both()
    log = ChangeLog("p15_tool_cues",
                    "One discriminating cue per question, so exactly one gold tool fits "
                    "(L1-003, L1-010, D11).")
    apply_one(kr, "kr", log)
    apply_one(en, "en", log)
    left = residue(kr, "kr") + residue(en, "en")
    if left:
        raise SystemExit("the ambiguous crime name is still in:\n  " + "\n  ".join(left))
    kr.save()
    en.save()
    log.note("5 cases lose 대포통장 / 'mule account'; 3 cases separate CTR structuring from "
             "the HOFINET split-transaction label.")
    print(log.report())
    print(f"log: {log.write()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
