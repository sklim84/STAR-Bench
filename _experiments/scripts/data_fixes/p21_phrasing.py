"""Pass 21 - schema spellings out of the question, and the phrasings the review flagged.

**Ask D - a parameter never appears in the question in its schema spelling.** The
question states the condition an analyst would state and the model maps it to the
schema. That covers a value in brackets after a Korean phrase ("모이는(inbound)"), an
identifier with an underscore ("고액거래(high_value)"), a parameter name ("bank_id 156")
and a phrase that names the slot rather than the condition ("structuring 모드로",
"inbound 방향의"). Two things stay, because they are names and not hints: the pattern
terms `funnel` and `structuring`, which `p20_terminology` fixed as the one spelling of
those patterns, and an AML glossary term or FIU keyword, which the tool matches
literally against an English catalog. HOFINET code tables (자금구분 3, 매체구분 2,
거래시간대 9, 유형 7, institution numbers) are the values the data itself carries, not
schema enums, and stay as they are. An ordinary English word that happens to coincide
with an enum value ("inbound", "high-value") is normal English and stays in the English
arm.

**Ask C - phrasings that read like a translated column name.** "상위 관련 기관",
"입출금 양방향 현황" and "상위 행" become what an analyst says; the sweep behind them is
in `impl/WS-D2_report.md`.

`st_mtool_061` is rewritten rather than only de-bracketed: it asked for the collection
*and* the dispersion direction while its gold pins one `detect_smurfing_network` call,
and `param_checks` holds one entry per tool, so the second half could never be scored.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both

SCHEMA_SPELLING = ("a parameter value or name in its schema spelling is not something an "
                   "analyst writes; the question states the condition instead (review ask D).")
COLUMN_NAME = ("the phrase read like a translated column name rather than what an analyst "
               "asks for (review ask C).")
GOLD_MISMATCH = ("the question asked for both directions while the gold pins one "
                 "detect_smurfing_network call, and param_checks holds one entry per tool "
                 "(review ask D, same shape as st_acr_042).")

# case id -> (Korean as-is, Korean to-be, English as-is, English to-be, why)
EDITS: dict[str, tuple[str, str, str, str, str]] = {
    "st_ctr_045": (
        "보고 기준을 2000만원으로 잡았을 때 그 아래로 나눠 거래한 계좌를 structuring 모드로 탐지해줘",
        "보고 기준을 2000만원으로 잡았을 때 그 아래로 나눠 거래한 계좌를 탐지해줘",
        "With the reporting threshold set to 20,000,000 KRW, please detect in structuring mode "
        "the accounts that split their transactions below it.",
        "With the reporting threshold set to 20,000,000 KRW, please detect the accounts that "
        "split their transactions below it.",
        SCHEMA_SPELLING),
    "st_ctr_048": (
        "고액거래(high_value) 보고 후보를 상위 50건까지 뽑아줘",
        "고액거래 보고 후보를 상위 50건까지 뽑아줘",
        "Please pull up to the top 50 high_value reporting candidates.",
        "Please pull up to the top 50 high-value reporting candidates.",
        SCHEMA_SPELLING),
    "st_mtool_034": (
        "입금이 한 계좌로 모이는(inbound) 스머핑 네트워크를 탐지하고 전체 통계도 확인해줘",
        "입금이 한 계좌로 모이는 스머핑 네트워크를 탐지하고 전체 통계도 확인해줘",
        "", "", SCHEMA_SPELLING),
    "st_mtool_039": (
        "입금이 모이는(inbound) 스머핑 네트워크를 탐지하고, 입금 상대가 많고 출금이 소수인 "
        "funnel 패턴도 함께 탐지해줘",
        "입금이 모이는 스머핑 네트워크를 탐지하고, 입금 상대가 많고 출금이 소수인 "
        "funnel 패턴도 함께 탐지해줘",
        "", "", SCHEMA_SPELLING),
    "st_mtool_042": (
        "채널별 위험도를 분석하고, 고액거래를 CTR 대상으로 탐지하고, 입금이 모이는(inbound) "
        "스머핑 네트워크도 탐지해줘",
        "채널별 위험도를 분석하고, 고액거래를 CTR 대상으로 탐지하고, 입금이 모이는 "
        "스머핑 네트워크도 탐지해줘",
        "", "", SCHEMA_SPELLING),
    "st_mtool_045": (
        "휴면계좌 재활성화를 탐지하고, 입금이 모이는(inbound) 스머핑 네트워크도 함께 탐지해줘",
        "휴면계좌 재활성화를 탐지하고, 입금이 모이는 스머핑 네트워크도 함께 탐지해줘",
        "", "", SCHEMA_SPELLING),
    "st_mtool_052": (
        "입금이 모이는(inbound) 스머핑 네트워크를 탐지하고, 탐지 결과를 바탕으로 계좌 "
        "9000000004388203의 위험도도 평가해줘",
        "입금이 모이는 스머핑 네트워크를 탐지하고, 탐지 결과를 바탕으로 계좌 "
        "9000000004388203의 위험도도 평가해줘",
        "", "", SCHEMA_SPELLING),
    "st_mtool_061": (
        "자금 수집(inbound) 스머핑을 탐지하고, 분산(outbound) 패턴도 함께 분석해줘",
        "스머핑 네트워크에서 자금이 한 계좌로 모이는 방향만 탐지해줘. 분산 방향은 지금 볼 필요 없어",
        "Please detect inbound smurfing for fund collection and also analyze the outbound patterns.",
        "In the smurfing network, please detect only the direction where funds collect into one "
        "account; the dispersion direction is not needed now.",
        GOLD_MISMATCH),
    "st_mtool_071": (
        "휴면계좌 재활성화를 90일 기준으로 탐지하고, 탐지된 계좌로 입금이 모이는(inbound) "
        "스머핑 패턴도 확인해줘",
        "휴면계좌 재활성화를 90일 기준으로 탐지하고, 탐지된 계좌로 입금이 모이는 "
        "스머핑 패턴도 확인해줘",
        "", "", SCHEMA_SPELLING),
    "st_mtool_077": (
        "자금 분산(outbound) 스머핑을 탐지하고, 상위 5건 고위험 거래를 랭킹해줘",
        "자금 분산 스머핑을 탐지하고, 상위 5건 고위험 거래를 랭킹해줘",
        "", "", SCHEMA_SPELLING),
    "st_smurf_036": (
        "입금이 한 계좌로 모이는(inbound) 스머핑 네트워크를 탐지해서 자금세탁 의심 계좌를 찾아줘",
        "입금이 한 계좌로 모이는 스머핑 네트워크를 탐지해서 자금세탁 의심 계좌를 찾아줘",
        "", "", SCHEMA_SPELLING),
    "st_smurf_005": (
        "inbound 방향의 스머핑 패턴을 탐지해줘",
        "자금이 한 계좌로 모이는 방향의 스머핑 패턴을 탐지해줘",
        "Please detect smurfing patterns in the inbound direction.",
        "Please detect smurfing patterns in the direction where funds collect into one account.",
        SCHEMA_SPELLING),
    "st_smurf_006": (
        "outbound 방향의 자금 분산 네트워크를 탐지해줘",
        "자금이 여러 계좌로 흩어져 나가는 분산 네트워크를 탐지해줘",
        "Please detect the outbound money distribution network.",
        "Please detect the distribution network where funds go out to many accounts.",
        SCHEMA_SPELLING),
    "st_smurf_046": (
        "계좌 9000000004410299로 25곳 이상에서 자금이 유입되는지 inbound 방향으로 확인해줘",
        "계좌 9000000004410299로 25곳 이상에서 자금이 유입되는지 확인해줘",
        "Please check in the inbound direction whether funds reach account 9000000004410299 "
        "from 25 or more accounts.",
        "Please check whether funds reach account 9000000004410299 from 25 or more accounts.",
        SCHEMA_SPELLING),
    "st_gir_007": (
        "bank_id 156 금융회사의 이상거래 종합 현황을 유형 분포까지 포함해 보고해줘",
        "금융회사 156의 이상거래 종합 현황을 유형 분포까지 포함해 보고해줘",
        "Please report the overall suspicious transaction status of the institution with "
        "bank_id 156, including its distribution by fraud type.",
        "Please report the overall suspicious transaction status of financial institution 156, "
        "including its distribution by fraud type.",
        SCHEMA_SPELLING),
    "st_gir_037": (
        "bank_id 117번 기관의 이상거래 종합 현황을 출금·입금 양방향으로 확인해줘",
        "금융회사 117번의 이상거래 종합 현황을 출금·입금 양쪽에서 확인해줘",
        "Please check the overall suspicious transaction status of the institution with "
        "bank_id 117 on both the sending and the receiving side.",
        "Please check the overall suspicious transaction status of financial institution 117 "
        "on both the sending and the receiving side.",
        SCHEMA_SPELLING),
    "st_gfs_016": (
        "심야/새벽 대량 거래(유형 7) 이상거래 건수와 상위 관련 기관을 알려줘",
        "심야/새벽 대량 거래(유형 7) 이상거래 건수와 이 유형이 가장 많이 발생한 금융회사를 알려줘",
        "Please provide the number of suspicious transactions of late-night/early-morning bulk "
        "transactions (type 7) and the top associated financial institutions.",
        "Please provide the number of late-night/early-morning bulk transaction (type 7) "
        "suspicious transactions and the financial institutions where that type occurs most.",
        COLUMN_NAME),
    "st_gfs_036": (
        "갑작스러운 거래패턴의 변화(유형1) 이상거래의 평균 거래금액과 상위 관련 금융회사를 알려줘",
        "갑작스러운 거래패턴의 변화(유형1) 이상거래의 평균 거래금액과 이 유형에서 건수가 가장 "
        "많은 금융회사를 알려줘",
        "Please give the average transaction amount and the top associated institutions for "
        "suspicious transactions of the sudden change in transaction pattern type (type 1).",
        "Please give the average transaction amount for suspicious transactions of the sudden "
        "change in transaction pattern type (type 1) and the financial institutions with the "
        "most cases of it.",
        COLUMN_NAME),
    "st_mp_030": (
        "그 이상거래 유형의 금액 통계와 상위 관련 기관을 알려줘",
        "그 이상거래 유형의 금액 통계와 그 유형에서 건수가 가장 많은 금융회사를 알려줘",
        "Please give the amount statistics and the top related institutions for that suspicious "
        "transaction type.",
        "Please give the amount statistics for that suspicious transaction type and the "
        "financial institutions with the most cases of it.",
        COLUMN_NAME),
    "st_mp_032": (
        "그 출금 금융회사의 입출금 양방향 현황 리포트를 만들어줘",
        "그 출금 금융회사의 입출금 자금흐름 현황 리포트를 만들어줘",
        "Please build the outbound and inbound status report for that withdrawal institution.",
        "Please build the report on the outbound and inbound fund flows of that withdrawal "
        "institution.",
        COLUMN_NAME),
    "st_mtool_113": (
        "금융회사 151의 입출금 양방향 현황 리포트를 확인하고, 2000건 샘플에서 위험도 상위 30건도 뽑아줘",
        "금융회사 151의 입출금 자금흐름 현황 리포트를 확인하고, 2000건 샘플에서 위험도 상위 30건도 뽑아줘",
        "Please check the outbound and inbound status report of institution 151, and pull the "
        "top 30 by risk out of a sample of 2,000 transactions.",
        "Please check the report on the outbound and inbound fund flows of institution 151, and "
        "pull the top 30 by risk out of a sample of 2,000 transactions.",
        COLUMN_NAME),
    "st_mp_044": (
        "그 SQL 쿼리를 실행해서 결과 건수와 상위 행을 보여줘",
        "그 SQL 쿼리를 실행해서 결과 건수와 상위 거래 내역을 보여줘",
        "Please run that SQL query and show the row count and the top rows.",
        "Please run that SQL query and show the number of rows and the transactions at the top "
        "of the result.",
        COLUMN_NAME),
}

BANNED = [
    re.compile(r"\(\s*(?:inbound|outbound|high_value|shortest_path|risk_score)\s*\)", re.I),
    re.compile(r"[가-힣]\s*\((?:structuring|funnel|ring|layering)\)"),
    re.compile(r"(?<![A-Za-z_])(?:bank_id|account_id|fraud_type|time_slot|sample_size|top_k|"
               r"rule_id|pattern_type|dormant_days|min_counterparts|date_from|date_to)"
               r"(?![A-Za-z_])"),
    re.compile(r"(?:structuring|high_value|inbound|outbound)\s*(?:모드|방향의)"),
]


def apply_one(bench: Bench, lang: str, log: ChangeLog) -> None:
    by_id = bench.by_id()
    index = 0 if lang == "kr" else 2
    for case_id, edit in EDITS.items():
        before, after, why = edit[index], edit[index + 1], edit[4]
        if not before:
            continue              # this arm never carried the schema spelling
        case = by_id.get(case_id)
        if case is None:
            raise SystemExit(f"{case_id}: absent from {bench.root.name}")
        question = case["question"]
        if question == after:
            continue              # already applied
        if question != before:
            raise SystemExit(f"{case_id} ({lang}): the question is neither the as-is nor the to-be")
        log.set_field(case, lang, "question", after, "review-C/review-D", why)


def residue(bench: Bench, lang: str) -> list[str]:
    out = []
    for _, case in bench.cases():
        question = case["question"]
        if len(question) > 600:
            continue              # STR drafts carry the form's own field names
        hit = [p.pattern[:40] for p in BANNED if p.search(question)]
        if hit:
            out.append(f"{case['id']} ({lang}): {hit}")
    return out


def main() -> int:
    kr, en = both()
    log = ChangeLog("p21_phrasing",
                    "Schema spellings out of the questions, and the phrasings the domain "
                    "review flagged (asks C and D).")
    apply_one(kr, "kr", log)
    apply_one(en, "en", log)
    left = residue(kr, "kr") + residue(en, "en")
    if left:
        raise SystemExit("a schema spelling is still in a question:\n  " + "\n  ".join(left))
    kr.save()
    en.save()
    print(log.report())
    print(f"log: {log.write()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
