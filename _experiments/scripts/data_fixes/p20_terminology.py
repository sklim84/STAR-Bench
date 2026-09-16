"""Pass 20 - one spelling per pattern term (domain review 2026-09-16, ask A).

The reviewer found 구조화(structuring), 구조화 and structuring used for the same thing,
and 깔때기(funnel), funnel(집금), 집금책 funnel and funnel for another. The convention,
applied to every case in both arms:

| pattern | Korean question | English question |
|---|---|---|
| `ring` | 순환거래 | circular transaction |
| `layering` | 레이어링 | layering |
| `funnel` | funnel | funnel |
| `structuring` | structuring | structuring |
| smurfing | 스머핑 | smurfing |

The Korean term is used where Korean AML practice has a word that states the condition
itself (순환거래, 레이어링, 스머핑). The English token is used for the two patterns where
the Korean word would be a second name for something the data already names: 구조화 reads
as a synonym of 분할 거래, which is HOFINET fraud type 3 and a different gold tool
(L1-010), and every Korean word for funnel (깔때기, 집금, 집금책) collides with the
집금/집결 wording `detect_smurfing_network` uses. Neither arm ever writes one language's
term with the other in brackets.

One exception: a question that asks for an AML glossary entry or an FIU catalog row
names it by its key, which the catalog holds in English ("Structuring 항목"). That is the
entry's name, not the pattern term.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both

ISSUE = "review-A"
WHY = ("one spelling per pattern term, in both arms, with no cross-language gloss in "
       "brackets (domain review 2026-09-16, ask A).")

KR = {
    "st_ap_003":
        ("입금 상대는 많고 출금 상대는 소수인 funnel(집금) 계좌 패턴을 탐지해줘",
         "입금 상대는 많고 출금 상대는 소수인 funnel 계좌 패턴을 탐지해줘"),
    "st_ap_027":
        ("ring 패턴 탐지 결과를 10건만 보여줘",
         "순환거래 패턴 탐지 결과를 10건만 보여줘"),
    "st_ap_029":
        ("layering 패턴을 15건 탐지해줘",
         "레이어링 패턴을 15건 탐지해줘"),
    "st_ap_039":
        ("여러 출처에서 소규모로 입금받아 소수 계좌로만 내보내는 집금책 funnel 계좌를 탐지해줘",
         "여러 출처에서 소규모로 입금받아 소수 계좌로만 내보내는 funnel 계좌를 탐지해줘"),
    "st_ctr_004":
        ("보고 기준 미만으로 쪼갠 구조화(structuring) 의심 건을 탐지해줘",
         "보고 기준 미만으로 쪼갠 structuring 의심 건을 탐지해줘"),
    "st_ctr_009":
        ("2024년 상반기에 보고 기준 미만으로 쪼갠 구조화 의심 건을 탐지해줘",
         "2024년 상반기에 보고 기준 미만으로 나눠 거래한 structuring 의심 건을 찾아줘"),
    "st_ctr_012":
        ("동일 계좌가 같은 날 보고 기준 미만으로 나눠서 거래한 구조화 의심 건을 찾아줘",
         "동일 계좌가 같은 날 보고 기준 미만으로 나눠서 거래한 structuring 의심 건을 찾아줘"),
    "st_ctr_021":
        ("5000만원 보고 기준 아래로 쪼갠 구조화 의심 건을 탐지해줘",
         "5000만원 보고 기준 아래로 쪼갠 structuring 의심 건을 탐지해줘"),
    "st_ctr_025":
        ("보고 기준 미만으로 쪼개 CTR 보고를 피한 구조화 패턴을 찾아줘",
         "보고 기준 미만으로 쪼개 CTR 보고를 피한 structuring 패턴을 찾아줘"),
    "st_ctr_031":
        ("같은 날 보고 기준 미만으로 쪼갠 구조화(structuring) 의심 거래를 탐지해줘",
         "같은 날 보고 기준 미만으로 쪼갠 structuring 의심 거래를 탐지해줘"),
    "st_ctr_036":
        ("3000만원 보고 기준 아래로 쪼갠 구조화 의심 건을 찾아줘",
         "3000만원 보고 기준 아래로 나눠서 거래한 structuring 의심 건을 확인해줘"),
    "st_ctr_038":
        ("2024년 3분기에 구조화 거래 패턴이 있는지 확인해줘",
         "2024년 3분기에 structuring 패턴이 있는지 확인해줘"),
    "st_ctr_041":
        ("감독 기관에 미보고될 위험이 있는 거래를 사전에 걸러내야 해. 보고 기준 미만으로 쪼갠 구조화 의심 건을 확인해줘",
         "감독 기관에 미보고될 위험이 있는 거래를 사전에 걸러내야 해. 보고 기준 미만으로 쪼갠 structuring 의심 건을 확인해줘"),
    "st_ctr_047":
        ("2021년 4분기 구조화(structuring) 의심 거래를 탐지해줘",
         "2021년 4분기 structuring 의심 거래를 탐지해줘"),
    "st_ctr_049":
        ("2023년 2분기에 500만원 기준 아래로 나눠 거래한 구조화(structuring) 의심 건을 찾아줘",
         "2023년 2분기에 500만원 기준 아래로 나눠 거래한 structuring 의심 건을 찾아줘"),
    "st_gl_008":
        ("AML 용어집에서 구조화(Structuring) 항목의 정의와 출처를 확인해줘",
         "AML 용어집에서 Structuring 항목의 정의와 출처를 확인해줘"),
    "st_mtool_029":
        ("보고 기준 미만으로 쪼갠 구조화 의심 건을 탐지하고 심야 대량 거래 모니터링 알림도 확인해줘",
         "보고 기준 미만으로 쪼갠 structuring 의심 건을 탐지하고 심야 대량 거래 모니터링 알림도 확인해줘"),
    "st_mtool_038":
        ("CTR 대상 구조화 의심 건을 탐지하고, 입금계좌 9000000000022515의 수취 프로파일을 조회해줘",
         "CTR 대상 structuring 의심 건을 탐지하고, 입금계좌 9000000000022515의 수취 프로파일을 조회해줘"),
    "st_mtool_055":
        ("CTR 구조화 의심 건을 탐지하고, 2023년 4분기와 2024년 1분기 이상거래를 비교해줘",
         "CTR structuring 의심 건을 탐지하고, 2023년 4분기와 2024년 1분기 이상거래를 비교해줘"),
    "st_mtool_065":
        ("고액거래 CTR 대상을 탐지하고, 보고 기준 미만 구조화 의심 건도 함께 확인해줘",
         "고액거래 CTR 대상을 탐지하고, 보고 기준 미만 structuring 의심 건도 함께 확인해줘"),
    "st_mtool_074":
        ("보고 기준 미만 구조화 의심 건을 탐지하고, 고액거래도 함께 조회해줘",
         "보고 기준 미만 structuring 의심 건을 탐지하고, 고액거래도 함께 조회해줘"),
    "st_mtool_101":
        ("구조화(structuring)에 해당하는 FIU 의심거래 참고유형을 확인하고, 같은 관점에서 보고 기준 미만으로 쪼갠 거래도 탐지해줘",
         "structuring에 해당하는 FIU 의심거래 참고유형을 확인하고, 같은 관점에서 보고 기준 미만으로 쪼갠 거래도 탐지해줘"),
    "st_mtool_122":
        ("여러 곳에서 자금을 받아 소수 계좌로만 내보내는 깔때기(funnel) 계좌를 탐지하고, 계좌 9000000004374328의 거래 프로파일도 조회해줘",
         "여러 곳에서 자금을 받아 소수 계좌로만 내보내는 funnel 계좌를 탐지하고, 계좌 9000000004374328의 거래 프로파일도 조회해줘"),
    "st_smurf_irr_004":
        ("FATF에서 자금 분산(structuring) 규제를 어떻게 다루는지 설명해줘",
         "FATF에서 structuring 규제를 어떻게 다루는지 설명해줘"),
    "st_smurf_irr_006":
        ("자금세탁 3단계(placement, layering, integration) 중 스머핑이 해당되는 단계는?",
         "자금세탁 3단계(배치·레이어링·통합) 중 스머핑이 해당되는 단계는?"),
}
EN = {
    "st_ap_003":
        ("Please detect funnel (collection) account patterns: many incoming counterparties and only a few outgoing ones.",
         "Please detect funnel account patterns: many incoming counterparties and only a few outgoing ones."),
    "st_ap_013":
        ("Please detect circular transaction rings between 5 and 10 accounts long that are suspected of money laundering.",
         "Please detect circular transactions between 5 and 10 accounts long that are suspected of money laundering."),
    "st_ap_027":
        ("Show me only 10 results of the ring pattern detection.",
         "Show me only 10 results of the circular transaction pattern detection."),
    "st_ap_039":
        ("Please identify collection (funnel) accounts that receive small deposits from many sources and forward them to only a few accounts.",
         "Please identify funnel accounts that receive small deposits from many sources and forward them to only a few accounts."),
    "st_ctr_038":
        ("Please check if there are any structured transaction patterns in the third quarter of 2024.",
         "Please check if there are any structuring patterns in the third quarter of 2024."),
    "st_smurf_irr_004":
        ("Please explain how the FATF addresses the regulation of fund structuring.",
         "Please explain how the FATF addresses the regulation of structuring."),
}

# What must no longer appear once the convention is applied. The glossary and FIU keys
# are capitalised, so the Korean check looks for the lower-case pattern tokens only.
KR_BANNED = [re.compile(p) for p in (r"구조화", r"깔때기", r"집금", r"(?<![A-Za-z])ring(?![A-Za-z])",
                                     r"(?<![A-Za-z])layering(?![A-Za-z])")]
EN_BANNED = [re.compile(p, re.I) for p in (r"circular transaction rings", r"\(funnel\)",
                                           r"\(collection\)", r"structured transaction")]


def apply_one(bench: Bench, lang: str, table: dict[str, tuple[str, str]], log: ChangeLog) -> None:
    """The table holds whole questions, so `already applied` is an equality, not a search.

    Several of the replacements leave a fragment of themselves behind (funnel(집금) -> funnel),
    and a substring test would then skip or repeat the edit.
    """
    by_id = bench.by_id()
    for case_id, (before, after) in table.items():
        case = by_id.get(case_id)
        if case is None:
            raise SystemExit(f"{case_id}: absent from {bench.root.name}")
        question = case["question"]
        if question == after:
            continue              # already applied
        if question != before:
            raise SystemExit(f"{case_id} ({lang}): the question is neither the as-is nor the to-be")
        log.set_field(case, lang, "question", after, ISSUE, WHY)


def residue(bench: Bench, lang: str) -> list[str]:
    banned = KR_BANNED if lang == "kr" else EN_BANNED
    out = []
    for _, case in bench.cases():
        hit = [p.pattern for p in banned if p.search(case["question"])]
        if hit:
            out.append(f"{case['id']} ({lang}): {hit}")
    return out


def main() -> int:
    kr, en = both()
    log = ChangeLog("p20_terminology",
                    "One spelling per pattern term, in both arms (domain review, ask A).")
    apply_one(kr, "kr", KR, log)
    apply_one(en, "en", EN, log)
    left = residue(kr, "kr") + residue(en, "en")
    if left:
        raise SystemExit("a second spelling is still in the data:\n  " + "\n  ".join(left))
    kr.save()
    en.save()
    log.note("st_ctr_009 and st_ctr_036 also change verb: with one spelling for the term "
             "they would otherwise sit at 0.76 and 0.80 character-3-gram Jaccard from "
             "st_ctr_004 and st_ctr_021, and the benchmark carries no pair above 0.72.")
    log.note("convention: ring=순환거래/circular transaction, layering=레이어링/layering, "
             "funnel=funnel, structuring=structuring, smurfing=스머핑/smurfing; glossary and "
             "FIU entries keep their English key.")
    print(log.report())
    print(f"log: {log.write()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
