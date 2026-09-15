"""Pass 03 - the follow-ups the fix table v3 did not cover.

L1-012  `compare_periods` gold keys `period_a_*` / `period_b_*` are not schema
        properties, so the five multi-tool cases could never pass a period check.
L1-013  `rank_risky_transactions.sample_size` above the schema maximum of 5000
        penalised models that honoured the schema; the question numbers move
        under the cap and the gold follows.
L1-025  Eight EN questions changed the tool or a parameter, further ones lost a
        condition; `question_ko` was a stale copy of an older KR question in 175
        cases and is dropped (the KR source is the same id in `benchmarks/`).
L1-027  Requests that cannot hold in HOFINET (offline channels, an "other"
        fraud type, unused code 6, residual/inherent risk, a phishing victim on
        the receiving side, a mule account that goes dormant afterwards, the
        identity behind a bank number).
L1-028  Conditions the gold tool cannot apply (institution and channel filters
        on `detect_ctr_candidates`, an input set for `rank_risky_transactions`,
        an industry average, a multiplier on rule R005).
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both

PERIOD_KEYS = {"period_a_start": "period1_start", "period_a_end": "period1_end",
               "period_b_start": "period2_start", "period_b_end": "period2_end"}

# L1-013: question number -> value at or below the schema maximum of 5000.
SAMPLE_SIZE = {
    "st_rrt_022": (10000, 5000, ["10000", "10,000"]),
    "st_rrt_043": (12000, 5000, ["12000", "12,000"]),
    "st_rrt_025": (8000, 4000, ["8000", "8,000"]),
    "st_rrt_041": (7000, 3500, ["7000", "7,000"]),
    "st_rrt_035": (6000, 3000, ["6000", "6000"]),
}

# L1-025: EN questions that changed the tool, a parameter or a condition.
EN_RETRANSLATION = {
    "st_ap_013": "Please detect circular transaction rings between 5 and 10 accounts long that are suspected of money laundering.",
    "st_mon_007": "Please run all of the suspicious transaction monitoring rules.",
    "st_mon_039": "Please use the monitoring rules to find accounts whose transactions were concentrated on one institution in the first half of 2024.",
    "st_grap_002": "Please analyze the pattern of funds coming into account 9876543210.",
    "st_cp_020": "Please compare the suspicious transactions of the third quarter of 2022 with those of the third quarter of 2024 and analyze how they changed over the two years.",
    "st_cp_040": "2021 Q4 is the first quarter of the data, and the plan is to compare the same fourth quarter across years in sequence; please start by comparing the fourth quarter of 2022 with the fourth quarter of 2023.",
    "st_ctr_015": "Please check whether any account is splitting transactions to stay under the reporting threshold.",
    "st_mtool_080": "Please analyze the risk by channel, and also pull the institution report for financial institution 120.",
    "st_ap_010": "Please compute the AML risk score for account 9876543210 with graph analysis.",
    "st_ap_031": "Please compute the risk score for account 7788991122 with graph analysis.",
    "st_ap_015": "Please compute the graph-based risk score for account 3333333333.",
    "st_acif_024": "Please find the institution pairs whose transactions between them have a high suspicious transaction ratio.",
    "st_acif_041": "Please check whether any institution pair had funds flowing in one direction over the whole of 2024, and analyze only pairs with at least 50 transactions.",
    "st_dorm_033": "Please find cases where a large amount of money moved out of an account whose transaction history had stopped.",
    "st_sar_038": "Please judge whether account 1000000001 is a high-risk account with a multi-factor assessment.",
    "st_ctr_033": "Please find transactions where one payment is split into several deposits.",
    "st_mtool_025": "Please analyze the network of account 3333333333, and also have the model pick the top 20 riskiest transactions.",
    "st_mtool_053": "Please run all the monitoring rules, and also look up the profile of the alerted account 1234567890 and its receiving-account view.",
    "st_fiu_005": "Please find the FIU reference type for suspicious transactions that use an account in someone else's name.",
    "st_gir_015": "Please write a report on withdrawal-side financial institution 125.",
    "st_gir_019": "Please analyze the main counterpart institutions and the suspicious transaction types of financial institution 133.",
}

# L1-027: requests that cannot hold in HOFINET. (KR, EN) after.
OUT_OF_SCOPE = {
    "st_acr_017": (
        "PC뱅킹·인터넷뱅킹 대비 전화·휴대전화 채널의 이상거래 발생률을 비교해줘",
        "Please compare the suspicious transaction rate of the PC banking and internet banking channels with that of the phone and mobile phone channels.",
        "every HOFINET media type is an electronic channel, so an offline channel cannot be compared",
    ),
    "st_gs_041": (
        "이상거래 유형 코드별(1, 2, 3, 4, 5, 7)로 각각 몇 건씩 발생했어?",
        "How many suspicious transactions occurred under each fraud type code (1, 2, 3, 4, 5, 7)?",
        "code 6 is not used in HOFINET, so asking for codes 1 through 7 has no answer",
    ),
    "st_sar_023": (
        "계좌 5555555555의 위험도를 행위 지표별 점수로 평가해줘",
        "Please assess the risk of account 5555555555 as a score over its behavioural indicators.",
        "score_account_risk returns five behavioural indicator scores, not a residual risk",
    ),
    "st_sar_025": (
        "위험평가 프레임워크에 따라 계좌 4444444444의 위험 점수를 산정해줘",
        "Please compute the risk score of account 4444444444 under the risk assessment framework.",
        "score_account_risk returns five behavioural indicator scores, not an inherent risk",
    ),
    "st_grap_042": (
        "계좌 9876543210의 수취 거래 패턴을 분석해서 보이스피싱 자금이 모이는 계좌인지 평가해줘",
        "Please analyze the incoming transaction pattern of account 9876543210 and assess whether it is an account where voice phishing proceeds are collected.",
        "a phishing victim is on the sending side, so a receiving profile cannot identify one",
    ),
    "st_dorm_023": (
        "오랫동안 거래가 없다가 갑자기 대규모로 활성화된 계좌 패턴을 찾아줘",
        "Please find patterns of accounts that had no transactions for a long time and were suddenly reactivated with a large amount.",
        "the as-is order (used as a mule account, then reactivated) is the reverse of dormant reactivation",
    ),
    "st_gir_010": (
        "금융회사 103번의 거래 규모와 이상거래 패턴을 확인해줘",
        "Please check the transaction volume and the suspicious transaction patterns of financial institution 103.",
        "the bank number is de-identified, so no tool can say which institution it is",
    ),
}

# L1-028: conditions the gold tool cannot apply.
UNSUPPORTED_CONDITION = {
    "st_mtool_044": (
        "기관간 자금 흐름을 분석하고, 월별 이상거래 추세도 확인하고, 고액거래 CTR 대상도 탐지해줘",
        "Please analyze the inter-institution fund flows, check the monthly suspicious transaction trend, and also detect high-value CTR candidates.",
        "detect_ctr_candidates has no institution filter, so the institution pair in the question was unscorable",
    ),
    "st_mtool_042": (
        "채널별 위험도를 분석하고, 고액거래를 CTR 대상으로 탐지하고, 스머핑 네트워크도 탐지해줘",
        "Analyze the risk by channel, detect high-value transactions as CTR candidates, and detect smurfing networks as well.",
        "detect_ctr_candidates has no channel filter, so the internet banking condition was unscorable",
    ),
    "st_mtool_063": (
        "다중거래의 동시 요청(유형 4) 이상거래를 조회하고, 위험 거래 상위 10건도 모델로 랭킹해줘",
        "Please query the suspicious transactions of the concurrent multiple transactions type (type 4), and also have the model rank the top 10 riskiest transactions.",
        "rank_risky_transactions samples the table itself and cannot take the rows another call returned",
    ),
    "st_mon_019": (
        "거래량이 전 분기 대비 급증한 계좌를 모니터링 규칙으로 탐지해줘",
        "Please use the monitoring rules to detect accounts whose transaction volume rose sharply against the previous quarter.",
        "rule R005 has no multiplier argument, so 'three times or more' could not be honoured",
    ),
}


def fix_period_keys(kr: Bench, en: Bench, log: ChangeLog) -> None:
    for bench in (kr, en):
        for _, case in bench.cases():
            checks = (case["expected"].get("param_checks") or {}).get("compare_periods")
            if not checks or not any(k in checks for k in PERIOD_KEYS):
                continue
            renamed = {PERIOD_KEYS.get(k, k): v for k, v in checks.items()}
            before = copy.deepcopy(case["expected"])
            case["expected"]["param_checks"]["compare_periods"] = renamed
            log.record(case["id"], bench.lang, "expected", before, case["expected"], "L1-012",
                       "period_a_*/period_b_* are not compare_periods properties, so the check could never pass")


def fix_sample_size(kr: Bench, en: Bench, log: ChangeLog) -> None:
    kr_by, en_by = kr.by_id(), en.by_id()
    for case_id, (old, new, spellings) in SAMPLE_SIZE.items():
        why = (f"sample_size {old} exceeds the schema maximum of 5000, so a model that honoured the "
               f"schema was scored wrong; the question now asks for {new}")
        for bench_by, lang in ((kr_by, "kr"), (en_by, "en")):
            case = bench_by[case_id]
            text = case["question"]
            for spelling in spellings:
                text = text.replace(spelling, f"{new:,}" if "," in spelling else str(new))
            if text == case["question"] and str(new) not in text.replace(",", ""):
                raise SystemExit(f"{case_id}: no sample size {old} in the {lang} question")
            log.set_field(case, lang, "question", text, "L1-013", why)
            gold = case["expected"]
            if gold["param_checks"]["rank_risky_transactions"]["sample_size"] != new:
                before = copy.deepcopy(gold)
                gold["param_checks"]["rank_risky_transactions"]["sample_size"] = new
                log.record(case_id, lang, "expected", before, gold, "L1-013", why)


def fix_en_translations(en: Bench, log: ChangeLog) -> None:
    en_by = en.by_id()
    for case_id, text in EN_RETRANSLATION.items():
        log.set_field(en_by[case_id], "en", "question", text, "L1-025",
                      "the EN question changed the tool, a parameter or a condition of the KR question")


def drop_question_ko(en: Bench, log: ChangeLog) -> None:
    n = 0
    for _, case in en.cases():
        if "question_ko" in case:
            del case["question_ko"]
            n += 1
    log.note(f"question_ko dropped from {n} EN cases (it was a stale copy of an older KR question in 175 "
             f"of them); the KR source is the same case id under benchmarks/")


def rewrite(bench_kr: Bench, bench_en: Bench, log: ChangeLog, table: dict, issue: str) -> None:
    kr_by, en_by = bench_kr.by_id(), bench_en.by_id()
    for case_id, (kr_text, en_text, why) in table.items():
        log.set_field(kr_by[case_id], "kr", "question", kr_text, issue, why)
        log.set_field(en_by[case_id], "en", "question", en_text, issue, why)


def add_statistics_tool(kr: Bench, en: Bench, log: ChangeLog) -> None:
    why = ("the question compares one institution with the industry average, which only get_statistics "
           "provides, so the gold now expects both calls")
    for bench in (kr, en):
        case = bench.get("st_gir_038")
        gold = case["expected"]
        if "get_statistics" in gold["tools_must_include"]:
            continue
        before = copy.deepcopy(gold)
        gold["tools_must_include"] = ["get_institution_report", "get_statistics"]
        log.record(case["id"], bench.lang, "expected", before, gold, "L1-028", why)


CRIME_TERMS = {
    "voice phishing": "보이스피싱", "mule account": "대포통장", "money laundering": "자금세탁",
    "smurfing": "스머핑", "illegal gambling": "불법 도박", "structuring": "구조화",
}
FRAUD_LABEL = {1: "갑작스러운 거래패턴의 변화", 2: "신규 수신처 거래", 3: "분할 거래",
               4: "다중거래의 동시 요청", 5: "거액 입금 후 당일 인출", 7: "심야/새벽 대량 거래"}


def squash(text: str) -> str:
    return text.replace(" ", "")


def verify_crime_names(kr: Bench, en: Bench, log: ChangeLog) -> None:
    """L1-025: an EN crime name must mirror the KR one and must not name the wrong fraud type.

    v3 deliberately keeps the descriptive questions descriptive, so a question that names no
    official type label is fine; a question that names the label of a DIFFERENT code is not.
    """
    kr_by = kr.by_id()
    checked, bad = 0, []
    for _, case in en.cases():
        question = case["question"].lower()
        korean = squash(kr_by[case["id"]]["question"])
        for term, kr_term in CRIME_TERMS.items():
            if term not in question:
                continue
            checked += 1
            if squash(kr_term) not in korean and term not in korean.lower():
                bad.append(f"{case['id']}: EN says {term!r}, the KR question does not say {kr_term!r}")
        code = (case["expected"].get("param_checks") or {}).get("get_fraud_type_summary", {}).get("fraud_type")
        if code in FRAUD_LABEL:
            wrong = [c for c, label in FRAUD_LABEL.items() if c != code and squash(label) in korean]
            if wrong and squash(FRAUD_LABEL[code]) not in korean:
                bad.append(f"{case['id']}: gold fraud_type {code} but the question names type {wrong}")
    log.note(f"crime-name check (L1-025): {checked} EN questions carry a concept term, "
             f"{len(bad)} contradict the KR question or the gold fraud type")
    for row in bad:
        log.note("  " + row)


def main() -> int:
    kr, en = both()
    log = ChangeLog("p03_followups", "Fix table v3 follow-ups: L1-012, L1-013, L1-025, L1-027, L1-028.")
    fix_period_keys(kr, en, log)
    fix_sample_size(kr, en, log)
    rewrite(kr, en, log, OUT_OF_SCOPE, "L1-027")
    rewrite(kr, en, log, UNSUPPORTED_CONDITION, "L1-028")
    add_statistics_tool(kr, en, log)
    fix_en_translations(en, log)
    drop_question_ko(en, log)
    verify_crime_names(kr, en, log)
    kr.save()
    en.save()
    print(log.report())
    for n in log.notes:
        print("  " + n)
    print(f"log: {log.write()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
