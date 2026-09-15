"""Pass 08 - when a question is a clarification case (D19; L1-014, L1-015, L1-016, L1-018).

D19: a case expects a clarification only when a SCHEMA-REQUIRED argument, or an
unresolved reference to one, is missing. Ten of the 25 missing-parameter cases
failed that rule: their tool has no required argument at all, so a default call
was correct and a model that asked back was scored wrong. Five of them become
tool cases with the default call, five ask for a tool whose required argument the
question genuinely does not give. Every clarification case now carries
`expected.expect_clarification`, which Contract 1 requires.

The same rule cuts the other way for tool cases: a required enum value has to be
in the question (L1-016), and `validate_str_fields` cannot be a tool case without
a draft to validate (L1-014). L1-018 fixes the parameters a question did not pin
down or contradicted.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both

# L1-014: an STR draft the question hands over, each missing one required field.
DRAFTS = {
    "st_strv_001": {
        "Header": {"ReportingDate": "20241231"},
        "I_ReportingInstitution": {"WithdrawalInstitutionCode": 134},
        "II_Transactor": {"WithdrawalAccountNumber": "9000000000024638",
                          "ReceivingAccountNumber": "9000000004383302"},
        "III_TransactionDetails": {"TransactionPeriod": "20241201-20241231", "TransactionCount": 14,
                                   "TransactionChannel": "Internet Banking", "TotalAmount_KRW": 48000000},
        "VI_TransactionType": {"PrimarySuspicionType": "Split Transaction"},
        "VII_Narrative": {},
    },
    "st_strv_002": {
        "Header": {"ReportingDate": "20241115"},
        "I_ReportingInstitution": {"WithdrawalInstitutionCode": 118},
        "II_Transactor": {"WithdrawalAccountNumber": "9000000000021321",
                          "ReceivingAccountNumber": "9000000000017070"},
        "III_TransactionDetails": {"TransactionPeriod": "20241101-20241115", "TransactionCount": 9,
                                   "TotalAmount_KRW": 27000000},
        "VI_TransactionType": {"PrimarySuspicionType": "Concurrent Multiple Transactions"},
        "VII_Narrative": {"SuspicionJudgmentReason": "Nine transfers of the same amount within two weeks."},
    },
    "st_strv_003": {
        "Header": {"ReportingDate": "20240930"},
        "I_ReportingInstitution": {"WithdrawalInstitutionCode": 123},
        "II_Transactor": {"WithdrawalAccountNumber": "9000000000019300",
                          "ReceivingAccountNumber": "9000000000022564"},
        "III_TransactionDetails": {"TransactionPeriod": "20240901-20240930", "TransactionCount": 21,
                                   "TransactionChannel": "Mobile Phone", "TotalAmount_KRW": 63000000},
        "VI_TransactionType": {},
        "VII_Narrative": {"SuspicionJudgmentReason": "Funds received from 21 accounts were withdrawn the same day."},
    },
}
STR_QUESTION_KR = {
    "st_strv_001": "다음 STR 초안의 필수 필드가 모두 채워졌는지 점검해줘: ",
    "st_strv_002": "다음 STR 보고서 초안에 필수 항목이 누락되었는지 검증해줘: ",
    "st_strv_003": "다음 초안이 의심거래보고서 양식의 필수 필드를 갖췄는지 확인해줘: ",
}
STR_QUESTION_EN = {
    "st_strv_001": "Please check whether every required field of this STR draft is filled in: ",
    "st_strv_002": "Please verify whether any required item is missing from this draft STR report: ",
    "st_strv_003": "Please check whether this draft carries the required fields of the suspicious "
                   "transaction report form: ",
}

# L1-015: missing-parameter cases whose tool has no required argument at all.
TO_TOOL_CASE = {
    "st_mp_012": ("고위험 거래를 위험도 순으로 랭킹해줘",
                  "Please rank the high-risk transactions by risk.",
                  {"primary_tool": "rank_risky_transactions",
                   "tools_must_include": ["rank_risky_transactions"], "param_checks": {}},
                  "rank_risky_transactions has no required argument and top_k defaults to 20, so a "
                  "default call answers; 26 of 28 configurations called it and were scored wrong"),
    "st_mp_013": ("재활성화된 휴면계좌 알림을 보여줘",
                  "Please show the alerts for reactivated dormant accounts.",
                  {"primary_tool": "detect_dormant_reactivation",
                   "tools_must_include": ["detect_dormant_reactivation"], "param_checks": {}},
                  "detect_dormant_reactivation takes no period argument, so 'at that time' could not be "
                  "carried into the call and 27 of 28 called the tool"),
    "st_mp_019": ("전체 채널의 위험도를 분석해서 비교해줘",
                  "Please analyze and compare the risk of every channel.",
                  {"primary_tool": "analyze_channel_risk", "tools_must_include": ["analyze_channel_risk"],
                   "param_checks": {}},
                  "analyze_channel_risk has no channel argument and returns every channel, so "
                  "'that channel' could not be a missing parameter"),
    "st_mp_021": (None, None,
                  {"primary_tool": "detect_dormant_reactivation",
                   "tools_must_include": ["detect_dormant_reactivation"], "param_checks": {}},
                  "detect_dormant_reactivation has no required argument, so 'recently' asks for the "
                  "default call; 26 of 28 made it"),
    "st_mp_023": ("기관 간 자금 흐름이 집중된 기관쌍을 분석해줘",
                  "Please analyze the institution pairs where the fund flow between institutions is "
                  "concentrated.",
                  {"primary_tool": "analyze_cross_institution_flow",
                   "tools_must_include": ["analyze_cross_institution_flow"], "param_checks": {}},
                  "analyze_cross_institution_flow has no institution filter, so 'that pair' could not be "
                  "a missing parameter"),
}

# L1-015: the rest keep the clarification gold but ask for a tool with a real required argument.
TO_REQUIRED_GAP = {
    "st_mp_001": ("그 용어의 정의를 AML 용어집에서 찾아줘",
                  "Please look up the definition of that term in the AML glossary.",
                  "query_transactions only requires `sql`, which a model can always write, so 'the most "
                  "recent quarter' was derivable; get_aml_glossary requires `term` and the question "
                  "leaves it unresolved"),
    "st_mp_004": ("그 키워드에 해당하는 FIU 의심거래 참고유형을 찾아줘",
                  "Please find the FIU suspicious-transaction reference types for that keyword.",
                  "get_statistics has no argument at all, so 'last week' could not be a missing "
                  "parameter; lookup_fiu_reference_types requires `keyword`"),
    "st_mp_015": ("그 초안이 STR 필수 항목을 갖췄는지 점검해줘",
                  "Please check whether that draft carries the required STR items.",
                  "`threshold` has a default and the mode was derivable, so nothing required was "
                  "missing; validate_str_fields requires `str_draft`, which the question does not give"),
    "st_mp_016": ("그 기간과 직전 동일 기간의 이상거래 증감을 비교해줘",
                  "Please compare the change in suspicious transactions between that period and the "
                  "preceding period of equal length.",
                  "get_trend_analysis has no required argument, so 'that period' was optional; "
                  "compare_periods requires all four period bounds"),
    "st_mp_025": ("그 시점 이후 그 기관의 이상거래 리포트를 확인해줘",
                  "Please check the suspicious transaction report of that institution from that point on.",
                  "analyze_cross_institution_flow has no required argument; get_institution_report "
                  "requires `bank_id`, which the question leaves unresolved"),
}

# D10's defensible-either-way missing-parameter cases that keep their clarification gold.
CLARIFICATION_ALTERNATIVES = {
    "st_mp_005": ({"tools_must_include": ["rank_risky_transactions"]},
                  "score_account_risk requires account_id and the question names no account, so asking "
                  "back is right; ranking the risky accounts without an argument is defensible too"),
}

# L1-016: a required enum value has to be in the question.
ENUM_IN_QUESTION = {
    "st_smurf_036": ("입금이 한 계좌로 모이는(inbound) 스머핑 네트워크를 탐지해서 자금세탁 의심 계좌를 찾아줘",
                     "Please detect the inbound smurfing network, where funds collect into one account, "
                     "and identify the accounts suspected of money laundering.",
                     None,
                     "direction is a required enum and the question named no direction, while the "
                     "near-identical st_mp_009 is a clarification case for exactly that gap"),
    "st_mtool_071": ("휴면계좌 재활성화를 90일 기준으로 탐지하고, 탐지된 계좌로 입금이 모이는(inbound) 스머핑 패턴도 확인해줘",
                     "Please detect dormant account reactivations on a 90-day basis and also check the "
                     "inbound smurfing pattern, where funds collect into the detected accounts.",
                     None, "direction is required and was not in the question (21 of 28 failed the check)"),
    "st_ctr_025": ("보고 기준 미만으로 쪼개 CTR 보고를 피한 구조화 패턴을 찾아줘",
                   "Please find structuring patterns that avoided CTR reporting by splitting below the "
                   "reporting threshold.",
                   None, "mode is a required enum and 'a risk of missing CTR reporting' fits both values"),
    "st_ctr_042": ("CTR 보고 누락 리스크를 줄이기 위해 2024년 전체 기간의 고액거래 CTR 대상을 탐지해서 리스트로 만들어줘",
                   "Please detect and list the high-value CTR candidates over the whole of 2024 to reduce "
                   "the risk of missing a CTR report.",
                   {"primary_tool": "detect_ctr_candidates", "tools_must_include": ["detect_ctr_candidates"],
                    "param_checks": {"detect_ctr_candidates": {"mode": "high_value", "date_from": 20240101,
                                                               "date_to": 20241231}}},
                   "the gold omitted the required `mode` entirely, so the gold call itself failed with "
                   "\"mode must be 'high_value' or 'structuring'\"; the question asked for two modes, "
                   "which one call cannot deliver"),
    "st_mtool_058": (None, None,
                     {"primary_tool": "get_trend_analysis",
                      "tools_must_include": ["get_trend_analysis", "get_statistics"],
                      "tool_order": ["get_trend_analysis", "get_statistics"],
                      "param_checks": {"get_trend_analysis": {"unit": "quarterly"}}},
                     "'a summary by fraud type' has no type in the question, so get_fraud_type_summary "
                     "could not be called at all; get_statistics returns the distribution over all types"),
    "st_mtool_085": (None, None,
                     {"primary_tool": "detect_monitoring_alerts",
                      "tools_must_include": ["detect_monitoring_alerts", "get_statistics"],
                      "param_checks": {"detect_monitoring_alerts": {"rule_id": "all"}}},
                     "same required-argument gap on get_fraud_type_summary; get_statistics already "
                     "carries the distribution the question asks for"),
    "st_mtool_092": (None, None,
                     {"primary_tool": "get_statistics",
                      "tools_must_include": ["get_statistics", "get_trend_analysis"],
                      "tool_order": ["get_statistics", "get_trend_analysis"],
                      "param_checks": {"get_trend_analysis": {"unit": "monthly"}}},
                     "same required-argument gap on get_fraud_type_summary"),
    "st_mon_025": (None, None,
                   {"primary_tool": "detect_monitoring_alerts",
                    "tools_must_include": ["detect_monitoring_alerts"],
                    "param_checks": {"detect_monitoring_alerts": {"rule_id": "all"}},
                    "alternatives": [
                        {"tools_must_include": ["detect_monitoring_alerts"],
                         "param_checks": {"detect_monitoring_alerts": {"rule_id": "R001"}}},
                        {"tools_must_include": ["detect_monitoring_alerts"],
                         "param_checks": {"detect_monitoring_alerts": {"rule_id": "R005"}}}]},
                   "the question names the night slots and the volume change, so running R001 and R005 "
                   "is as correct as running all five rules"),
}

# L1-018: parameters the question did not pin down, or pinned the other way round.
PARAMETERS = {
    "st_cp_019": ("작년 같은 달(2023년 6월)과 올해 같은 달(2024년 6월)을 비교해줘",
                  "Please compare the same month last year (June 2023) with the same month this year "
                  "(June 2024).",
                  None,
                  "the gold puts 2023 in period1 but the question named 2024 first, so a = .46; the "
                  "question is now in chronological order"),
    "st_cp_022": ("2023년 상반기와 2024년 상반기 거래 규모를 비교해줘",
                  "Please compare the transaction volume of the first half of 2023 with that of the "
                  "first half of 2024.",
                  None, "same reversed order as st_cp_019 (a = .48)"),
    "st_gta_037": ("2024년 상반기 분기별 이상거래 비율 추이를 분석해줘",
                   "Please analyze the quarterly trend of the suspicious transaction ratio in the first "
                   "half of 2024.",
                   None,
                   "the gold starts at 20240101 but the question asked for a year-on-year comparison, so "
                   "24 of 28 configurations started at 2023 and failed the check"),
    "st_acr_031": ("2023년 상반기 채널별 위험도를 분석해서 어떤 채널이 고위험인지 알려줘",
                   "Please analyze the risk by channel in the first half of 2023 and say which channel is "
                   "high risk.",
                   None, "the gold holds one period, but 'compared with the first half of 2023' implied a "
                         "second period the question never named"),
    "st_smurf_032": ("12개 이상 출처에서 자금을 받은 계좌를 찾아줘",
                     "Please find accounts that received funds from 12 or more sources.",
                     None,
                     "'during a specific period' named no period and the gold checks none, while the "
                     "same phrase is a clarification case elsewhere"),
    "st_acif_043": ("AML 위험도가 높은 기관 쌍을 선별하기 위해 거래 건수 100건 이상 조건을 적용하고 2023년 하반기 데이터만 대상으로 상위 15개 기관 쌍의 교차 흐름을 분석해줘",
                    "Please apply a threshold of at least 100 transactions to select the institution pairs "
                    "with high AML risk, and analyze the cross-flow of the top 15 pairs using only data "
                    "from the second half of 2023.",
                    {"primary_tool": "analyze_cross_institution_flow",
                     "tools_must_include": ["analyze_cross_institution_flow"],
                     "param_checks": {"analyze_cross_institution_flow": {
                         "date_from": 20230701, "date_to": 20231231, "min_transactions": 100, "limit": 15}}},
                    "'apply a strict transaction count' named no value and nothing checked it"),
    "st_ctr_013": (None, None,
                   {"primary_tool": "detect_ctr_candidates", "tools_must_include": ["detect_ctr_candidates"],
                    "param_checks": {"detect_ctr_candidates": {"mode": "high_value", "threshold": 50000000}}},
                   "the question names 50 million won but the gold checked no threshold, while the "
                   "parallel st_ctr_035 checks 20 million"),
}

CLARIFICATION_WHY = ("D19: a clarification case is one where a schema-required argument, or an "
                     "unresolved reference to one, is missing; the flag makes that explicit for the "
                     "scorer (Contract 1)")


def apply(kr: Bench, en: Bench, log: ChangeLog) -> None:
    kr_by, en_by = kr.by_id(), en.by_id()

    def edit(case_id, table, issue):
        for bench_by, lang, index in ((kr_by, "kr", 0), (en_by, "en", 1)):
            entry = table[case_id]
            case = bench_by[case_id]
            if entry[index]:
                log.set_field(case, lang, "question", entry[index], issue, entry[-1])
            if len(entry) == 4 and entry[2]:
                log.set_field(case, lang, "expected", copy.deepcopy(entry[2]), issue, entry[-1])

    # L1-014: hand the draft over and check that it was passed on.
    for case_id, draft in DRAFTS.items():
        text = json.dumps(draft, ensure_ascii=False)
        why = ("validate_str_fields requires str_draft and no question carried one, so a model that "
               "asked for the draft was scored wrong (20 of 28 made no call); the draft is now in the "
               "question and the gold checks that it reaches the tool")
        gold = {"primary_tool": "validate_str_fields", "tools_must_include": ["validate_str_fields"],
                "param_checks": {"validate_str_fields": {"str_draft": draft}}}
        log.set_field(kr_by[case_id], "kr", "question", STR_QUESTION_KR[case_id] + text, "L1-014/D19", why)
        log.set_field(en_by[case_id], "en", "question", STR_QUESTION_EN[case_id] + text, "L1-014/D19", why)
        for bench_by, lang in ((kr_by, "kr"), (en_by, "en")):
            log.set_field(bench_by[case_id], lang, "expected", copy.deepcopy(gold), "L1-014/D19", why)

    for case_id in TO_TOOL_CASE:
        edit(case_id, TO_TOOL_CASE, "L1-015/D19")
    for case_id, (kr_text, en_text, why) in TO_REQUIRED_GAP.items():
        log.set_field(kr_by[case_id], "kr", "question", kr_text, "L1-015/D19", why)
        log.set_field(en_by[case_id], "en", "question", en_text, "L1-015/D19", why)
    for case_id in ENUM_IN_QUESTION:
        edit(case_id, ENUM_IN_QUESTION, "L1-016/D19")
    for case_id in PARAMETERS:
        edit(case_id, PARAMETERS, "L1-018")

    # st_gir_irr_002 is a missing-parameter case, not an irrelevant one.
    for bench_by, lang in ((kr_by, "kr"), (en_by, "en")):
        case = bench_by["st_gir_irr_002"]
        gold = copy.deepcopy(case["expected"])
        gold["expect_clarification"] = True
        log.set_field(case, lang, "expected", gold, "L1-015/D19",
                      "get_institution_report requires bank_id and the question names no institution, so "
                      "this is a clarification case and not an irrelevant request")

    # Contract 1: every clarification case carries the flag.
    n_flag = 0
    for bench_by, lang in ((kr_by, "kr"), (en_by, "en")):
        for case_id, case in bench_by.items():
            if not case_id.startswith("st_mp_"):
                continue
            gold = case["expected"]
            if gold.get("tools_must_include") or gold.get("primary_tool"):
                continue
            if gold.get("expect_clarification"):
                continue
            new = copy.deepcopy(gold)
            new["expect_clarification"] = True
            log.set_field(case, lang, "expected", new, "L1-015/D19", CLARIFICATION_WHY)
            n_flag += 1

    for case_id, (alternative, why) in CLARIFICATION_ALTERNATIVES.items():
        for bench_by, lang in ((kr_by, "kr"), (en_by, "en")):
            case = bench_by[case_id]
            gold = copy.deepcopy(case["expected"])
            gold["alternatives"] = [copy.deepcopy(alternative)]
            log.set_field(case, lang, "expected", gold, "L1-015/D19", why)

    log.note(f"{len(DRAFTS)} validate_str_fields cases carry an STR draft and check that it reaches the tool")
    log.note(f"{len(TO_TOOL_CASE)} missing-parameter cases became tool cases (their tool has no required "
             f"argument), {len(TO_REQUIRED_GAP)} were rewritten around a tool whose required argument the "
             f"question leaves unresolved")
    log.note(f"{n_flag // 2} clarification cases carry expect_clarification, plus st_gir_irr_002")
    log.note(f"{len(ENUM_IN_QUESTION)} cases state the required enum value or drop a gold call that could "
             f"not be made, {len(PARAMETERS)} pin down a parameter the question left open")


def main() -> int:
    kr, en = both()
    log = ChangeLog("p08_clarification", "D19: what makes a clarification case, STR drafts, required "
                                         "enum values and under-specified parameters.")
    apply(kr, en, log)
    kr.save()
    en.save()
    print(log.report())
    for n in log.notes:
        print("  " + n)
    print(f"log: {log.write()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
