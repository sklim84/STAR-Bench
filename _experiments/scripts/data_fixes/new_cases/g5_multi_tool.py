"""Group 5 - multi-tool cases (87 -> 112).

The multi-tool file had no case at all that combines an analysis tool with one of
the three regulatory-reporting tools, so a model could score well on multi-tool
work without ever reaching the catalog or the STR form. Fourteen of these 25 cases
close that gap; the rest pair the tools whose per-tool counts were thinnest after
WS-D (compare_periods, get_fraud_type_summary, detect_monitoring_alerts,
rank_risky_transactions, get_institution_report, analyze_cross_institution_flow).

Every combination here is new: none of the 87 existing multi-tool cases uses the
same gold tool set. Each question names its own cue for each tool, the STR
drafts follow , and the two `query_transactions` cases carry `sql_conditions`
plus an executable reference SQL (Contract 1).
"""

from __future__ import annotations

import json

from .g1_validate_str import base_draft, drop, merge_optional


def draft_text(draft: dict) -> str:
    return json.dumps(draft, ensure_ascii=False)


def build(grounding: dict) -> list[dict]:
    rows = grounding["str_sources"]
    monitoring = grounding["monitoring_accounts"]
    smurf_in = [row["account_id"] for row in grounding["accounts"]["smurf_in"]]
    funnel = grounding["funnel"]["accounts"][0]["account_id"]

    # STR drafts for the five cases that start from a draft. Each uses a source row
    # and a defect that the single-tool group does not use on that row, so no two
    # questions in the benchmark carry the same draft.
    d_104 = merge_optional(base_draft(rows[13]),
                           {"VII_Narrative": {"OverallOpinion": "Recommended for reporting to the FIU."}})
    d_105 = drop(base_draft(rows[17]), "III_TransactionDetails.TransactionChannel")
    d_106 = base_draft(rows[14])
    d_120 = drop(base_draft(rows[15]), "Header.ReportingDate")
    d_125 = merge_optional(base_draft(rows[10]),
                           {"I_ReportingInstitution": {"MLROName": "Reporting Officer"}})
    acc_105 = rows[17]["sender_acc"]
    acc_120 = rows[15]["receiver_acc"]
    acc_125 = rows[10]["sender_acc"]
    if acc_125 not in (monitoring.get("R003") or []):
        raise ValueError("the STR draft account for st_mtool_125 has no R003 alert")

    spec = [
        ("st_mtool_101", ["lookup_fiu_reference_types", "detect_ctr_candidates"],
         {"lookup_fiu_reference_types": {"keyword": "structuring"},
          "detect_ctr_candidates": {"mode": "structuring"}},
         ["lookup_fiu_reference_types", "detect_ctr_candidates"],
         "구조화(structuring)에 해당하는 FIU 의심거래 참고유형을 확인하고, 같은 관점에서 보고 기준 "
         "미만으로 쪼갠 거래도 탐지해줘",
         "Please check the FIU suspicious-transaction reference types for structuring, and from "
         "the same angle detect transactions split below the reporting threshold.",
         "first case to pair the FIU catalog with a detection tool"),
        ("st_mtool_102", ["get_aml_glossary", "detect_ctr_candidates"],
         {"get_aml_glossary": {"term": "CTR"}, "detect_ctr_candidates": {"mode": "high_value"}},
         ["get_aml_glossary", "detect_ctr_candidates"],
         "AML 용어집에서 CTR 항목의 보고 기준 금액을 확인하고, 그 기준 이상인 고액거래도 조회해줘",
         "Please check the reporting threshold recorded in the CTR entry of the AML glossary, and "
         "retrieve the high-value transactions at or above it.",
         "the glossary supplies the threshold the detection tool then applies"),
        ("st_mtool_103", ["get_aml_glossary", "detect_smurfing_network"],
         {"get_aml_glossary": {"term": "Structuring"},
          "detect_smurfing_network": {"direction": "inbound"}},
         ["get_aml_glossary", "detect_smurfing_network"],
         "AML 용어집의 Structuring 항목 정의를 확인하고, 유입 거래 상대가 많은 자금 집결 계좌도 "
         "탐지해줘",
         "Please check the definition of the Structuring entry in the AML glossary, and detect the "
         "collection accounts with many incoming counterparties.",
         "the definition frames the inbound smurfing scan"),
        ("st_mtool_104", ["validate_str_fields", "get_fraud_type_summary"],
         {"validate_str_fields": {"str_draft": d_104}, "get_fraud_type_summary": {"fraud_type": 3}},
         ["validate_str_fields", "get_fraud_type_summary"],
         "다음 STR 초안의 필수 항목을 점검하고, 초안에 적힌 의심 유형인 분할 거래(유형3)의 전체 통계도 "
         f"알려줘: {draft_text(d_104)}",
         "Please check the required fields of the following STR draft, and also give the overall "
         "statistics of split transaction (type 3), the suspicion type the draft records: "
         f"{draft_text(d_104)}",
         "the draft's suspicion type drives the second call"),
        ("st_mtool_105", ["validate_str_fields", "get_account_profile"],
         {"validate_str_fields": {"str_draft": d_105}, "get_account_profile": {"account_id": acc_105}},
         ["validate_str_fields", "get_account_profile"],
         "아래 STR 초안에서 빠진 필수 항목을 확인하고, 초안의 출금계좌 프로파일도 조회해줘: "
         f"{draft_text(d_105)}",
         "Please check which required fields are missing from the STR draft below, and retrieve the "
         f"profile of the withdrawal account it names: {draft_text(d_105)}",
         "the account to profile is the withdrawal account of the draft"),
        ("st_mtool_106", ["validate_str_fields", "lookup_fiu_reference_types"],
         {"validate_str_fields": {"str_draft": d_106},
          "lookup_fiu_reference_types": {"keyword": "structuring"}},
         ["validate_str_fields", "lookup_fiu_reference_types"],
         "아래 STR 초안의 필수 항목을 검증하고, 초안의 의심 유형인 분할 거래에 대응하는 FIU 참고유형도 "
         f"찾아줘: {draft_text(d_106)}",
         "Please validate the required fields of the STR draft below, and find the FIU reference "
         "type that corresponds to split transactions, the suspicion type the draft records: "
         f"{draft_text(d_106)}",
         "first case to pair the STR form check with the FIU catalog"),
        ("st_mtool_107", ["compare_periods", "get_fraud_type_summary"],
         {"compare_periods": {"period1_start": 20231001, "period1_end": 20231231,
                              "period2_start": 20241001, "period2_end": 20241231},
          "get_fraud_type_summary": {"fraud_type": 2}},
         ["compare_periods", "get_fraud_type_summary"],
         "2023년 4분기와 2024년 4분기 거래 통계를 비교하고, 건수가 가장 많은 신규 수신처 거래 유형의 "
         "기관별 분포도 알려줘",
         "Please compare the transaction statistics of the fourth quarter of 2023 and the fourth "
         "quarter of 2024, and give the institution distribution of transaction with new "
         "counterparty, the most frequent type.",
         "period comparison followed by the summary of one fraud type"),
        ("st_mtool_108", ["compare_periods", "analyze_channel_risk"],
         {"compare_periods": {"period1_start": 20240101, "period1_end": 20240630,
                              "period2_start": 20240701, "period2_end": 20241231},
          "analyze_channel_risk": {"date_from": 20240701, "date_to": 20241231}},
         ["compare_periods", "analyze_channel_risk"],
         "2024년 상반기와 하반기 거래 통계를 비교하고, 하반기 구간의 채널별 이상거래 비율도 분석해줘",
         "Please compare the transaction statistics of the first and the second half of 2024, and "
         "analyze the suspicious transaction ratio by channel over the second half.",
         "the second call reuses the second period of the comparison"),
        ("st_mtool_109", ["compare_periods", "detect_ctr_candidates"],
         {"compare_periods": {"period1_start": 20220101, "period1_end": 20221231,
                              "period2_start": 20230101, "period2_end": 20231231},
          "detect_ctr_candidates": {"mode": "high_value", "date_from": 20230101, "date_to": 20231231}},
         ["compare_periods", "detect_ctr_candidates"],
         "2022년과 2023년 연간 거래 통계를 비교하고, 2023년 구간의 고액거래 CTR 보고 후보도 조회해줘",
         "Please compare the annual transaction statistics of 2022 and 2023, and retrieve the "
         "high-value CTR reporting candidates over 2023.",
         "the reporting scan is restricted to the later of the two periods"),
        ("st_mtool_110", ["detect_monitoring_alerts", "get_account_profile"],
         {"detect_monitoring_alerts": {"rule_id": "R003", "account_id": monitoring["R003"][2]},
          "get_account_profile": {"account_id": monitoring["R003"][2]}},
         ["detect_monitoring_alerts", "get_account_profile"],
         f"계좌 {monitoring['R003'][2]}의 R003 동일 금액 반복 송금 알림을 확인하고, 그 계좌의 거래 "
         f"프로파일도 보여줘",
         f"Please check the R003 repeated identical amount alerts of account "
         f"{monitoring['R003'][2]}, and show the transaction profile of that account.",
         "the account filter of the rule and the profile use the same account"),
        ("st_mtool_111", ["detect_monitoring_alerts", "score_account_risk"],
         {"detect_monitoring_alerts": {"rule_id": "R002", "account_id": monitoring["R002"][1]},
          "score_account_risk": {"account_id": monitoring["R002"][1]}},
         ["detect_monitoring_alerts", "score_account_risk"],
         f"계좌 {monitoring['R002'][1]}의 R002 동일일 다건거래 알림을 조회하고, 그 계좌의 행동 위험 "
         f"점수도 산출해줘",
         f"Please retrieve the R002 same-day rapid-fire alerts of account {monitoring['R002'][1]}, "
         f"and score that account's behavioural risk.",
         "rule alert and behavioural score for one account"),
        ("st_mtool_112", ["rank_risky_transactions", "predict_fraud"],
         {"rank_risky_transactions": {"sample_size": 1000, "top_k": 20},
          "predict_fraud": {"time_slot": 21, "sender_bank": 159, "receiver_bank": 133,
                            "fund_type": 0, "media_type": 2, "amount": 50000000}},
         ["rank_risky_transactions", "predict_fraud"],
         "1000건 샘플에서 위험도 상위 20건을 랭킹하고, 거래시간대 21, 출금사 159, 입금사 133, "
         "일반(자금구분 0), 인터넷뱅킹(매체구분 2), 5000만원인 개별 거래의 위험 점수도 예측해줘",
         "Please rank the top 20 by risk out of a sample of 1,000 transactions, and also score one "
         "transaction with time slot 21, sender bank 159, receiver bank 133, general funds "
         "(fund type 0), internet banking (media type 2) and 50,000,000 KRW.",
         "batch ranking beside a single scored transaction; the six features are all given"),
        ("st_mtool_113", ["rank_risky_transactions", "get_institution_report"],
         {"rank_risky_transactions": {"sample_size": 2000, "top_k": 30},
          "get_institution_report": {"bank_id": 151}},
         ["get_institution_report", "rank_risky_transactions"],
         "금융회사 151의 입출금 양방향 현황 리포트를 확인하고, 2000건 샘플에서 위험도 상위 30건도 뽑아줘",
         "Please check the outbound and inbound status report of institution 151, and pull the top "
         "30 by risk out of a sample of 2,000 transactions.",
         "institution report beside a model-scored batch"),
        ("st_mtool_114", ["get_fraud_type_summary", "get_institution_report"],
         {"get_fraud_type_summary": {"fraud_type": 4, "bank_id": 147},
          "get_institution_report": {"bank_id": 147}},
         ["get_fraud_type_summary", "get_institution_report"],
         "출금금융회사 147의 다중거래의 동시 요청 이상거래 통계를 확인하고, 그 기관의 입출금 현황 "
         "리포트도 만들어줘",
         "Please check the statistics of concurrent multiple transactions at withdrawal institution "
         "147, and build the status report of that institution.",
         "the same institution seen through the fraud type and through the institution report"),
        ("st_mtool_115", ["lookup_fiu_reference_types", "detect_dormant_reactivation"],
         {"lookup_fiu_reference_types": {"keyword": "dormancy"},
          "detect_dormant_reactivation": {"dormant_days": 180}},
         ["lookup_fiu_reference_types", "detect_dormant_reactivation"],
         "장기간 휴면이던 계좌가 큰 자금으로 다시 움직이는 경우에 해당하는 FIU 참고유형을 찾고, "
         "실제로 180일 이상 휴면 후 재활성화된 계좌도 탐지해줘",
         "Please find the FIU reference type for accounts reactivated with large funds after a long "
         "dormancy, and detect the accounts actually reactivated after 180 days or more of dormancy.",
         "catalog row beside the detection it describes"),
        ("st_mtool_116", ["lookup_fiu_reference_types", "analyze_cross_institution_flow"],
         {"lookup_fiu_reference_types": {"keyword": "wire transfer"},
          "analyze_cross_institution_flow": {"date_from": 20240101, "date_to": 20241231}},
         ["lookup_fiu_reference_types", "analyze_cross_institution_flow"],
         "송금(wire transfer)이 등장하는 FIU 의심거래 참고유형을 조회하고, 2024년 기관 간 자금 "
         "흐름이 집중된 기관쌍도 분석해줘",
         "Please look up the FIU suspicious-transaction reference types in which a wire transfer "
         "appears, and analyze the institution pairs where the cross-institution fund flow "
         "concentrated in 2024.",
         "catalog row beside the institution-pair flow it would show up in"),
        ("st_mtool_117", ["get_aml_glossary", "detect_monitoring_alerts"],
         {"get_aml_glossary": {"term": "STR"}, "detect_monitoring_alerts": {"rule_id": "all"}},
         ["get_aml_glossary", "detect_monitoring_alerts"],
         "AML 용어집에서 STR 항목의 정의와 출처를 확인하고, STR 후보를 찾기 위해 전체 모니터링 규칙도 "
         "실행해줘",
         "Please check the definition and the source of the STR entry in the AML glossary, and run "
         "every monitoring rule to find STR candidates.",
         "the definition frames the rule run that produces the candidates"),
        ("st_mtool_118", ["get_fraud_type_summary", "query_transactions"],
         {"get_fraud_type_summary": {"fraud_type": 3, "bank_id": 159},
          "query_transactions": {"sql_conditions": [{"column": "fraud_type", "op": "=", "value": 3},
                                                    {"column": "sender_bank", "op": "=", "value": 159}],
                                 "sql_valid": True}},
         ["get_fraud_type_summary", "query_transactions"],
         "출금금융회사 159의 분할 거래(유형3) 이상거래 통계를 확인하고, 해당 거래 원본도 SQL로 조회해줘",
         "Please check the statistics of split transaction (type 3) at withdrawal institution 159, "
         "and query the underlying transactions with SQL as well.",
         "summary and raw rows for the same fraud type and institution",
         "SELECT date, time_slot, sender_acc, receiver_acc, amount FROM hofinet "
         "WHERE fraud_type = 3 AND sender_bank = 159 ORDER BY date DESC LIMIT 100"),
        ("st_mtool_119", ["compare_periods", "query_transactions"],
         {"compare_periods": {"period1_start": 20240101, "period1_end": 20240331,
                              "period2_start": 20240401, "period2_end": 20240630},
          "query_transactions": {"sql_conditions": [
              {"column": "is_fraud", "op": "=", "value": 1},
              {"column": "time_slot", "op": "=", "value": 21},
              {"column": "date", "op": "BETWEEN", "value": [20240101, 20240630]}],
              "sql_valid": True}},
         ["compare_periods", "query_transactions"],
         "2024년 1분기와 2분기 거래 통계를 비교하고, 2024년 상반기 중 거래시간대 21에 발생한 이상거래를 "
         "SQL로 조회해줘",
         "Please compare the transaction statistics of the first and the second quarter of 2024, "
         "and query with SQL the suspicious transactions that occurred in time slot 21 during the "
         "first half of 2024.",
         "comparison beside a SQL read restricted to the same half year",
         "SELECT date, time_slot, sender_bank, receiver_bank, amount, fraud_type FROM hofinet "
         "WHERE is_fraud = 1 AND time_slot = 21 AND date BETWEEN 20240101 AND 20240630 "
         "ORDER BY date DESC LIMIT 100"),
        ("st_mtool_120", ["validate_str_fields", "get_receiving_account_profile"],
         {"validate_str_fields": {"str_draft": d_120},
          "get_receiving_account_profile": {"account_id": acc_120}},
         ["validate_str_fields", "get_receiving_account_profile"],
         "아래 STR 초안의 필수 항목을 검증하고, 초안의 입금계좌가 어디에서 자금을 받았는지 입금 "
         f"프로파일로도 확인해줘: {draft_text(d_120)}",
         "Please validate the required fields of the STR draft below, and use the inbound profile "
         "to check where the receiving account it names took its funds from: "
         f"{draft_text(d_120)}",
         "the account to profile is the receiving account of the draft"),
        ("st_mtool_121", ["detect_smurfing_network", "analyze_cross_institution_flow"],
         {"detect_smurfing_network": {"direction": "inbound", "min_counterparts": 30,
                                      "date_from": 20240101, "date_to": 20241231},
          "analyze_cross_institution_flow": {"date_from": 20240101, "date_to": 20241231}},
         ["detect_smurfing_network", "analyze_cross_institution_flow"],
         "2024년에 30곳 이상에서 자금을 받은 집결 계좌를 탐지하고, 같은 기간 기관 간 자금 흐름이 "
         "집중된 기관쌍도 분석해줘",
         "Please detect the collection accounts that received funds from 30 or more counterparties "
         "in 2024, and analyze the institution pairs where the cross-institution fund flow "
         "concentrated over the same period.",
         "account-level collection beside institution-level flow, same window"),
        ("st_mtool_122", ["detect_aml_patterns", "get_account_profile"],
         {"detect_aml_patterns": {"pattern_type": "funnel"},
          "get_account_profile": {"account_id": funnel}},
         ["detect_aml_patterns", "get_account_profile"],
         "여러 곳에서 자금을 받아 소수 계좌로만 내보내는 깔때기(funnel) 계좌를 탐지하고, "
         f"계좌 {funnel}의 거래 프로파일도 조회해줘",
         "Please detect the funnel accounts that take funds from many counterparties and forward "
         f"them to only a few, and retrieve the transaction profile of account {funnel}.",
         "the profiled account is one the funnel scan returns at the tool defaults"),
        ("st_mtool_123", ["get_trend_analysis", "detect_monitoring_alerts"],
         {"get_trend_analysis": {"unit": "quarterly", "date_from": 20230101, "date_to": 20231231},
          "detect_monitoring_alerts": {"rule_id": "R001", "date_from": 20230701, "date_to": 20231231}},
         ["get_trend_analysis", "detect_monitoring_alerts"],
         "2023년 분기별 이상거래 추이를 확인하고, 2023년 하반기 심야 대량 거래(R001) 알림도 조회해줘",
         "Please check the quarterly suspicious transaction trend for 2023, and retrieve the "
         "nighttime bulk transaction alerts for the second half of 2023.",
         "trend over a year beside the rule alerts of its second half"),
        ("st_mtool_124", ["get_aml_glossary", "lookup_fiu_reference_types", "detect_ctr_candidates"],
         {"get_aml_glossary": {"term": "Structuring"},
          "lookup_fiu_reference_types": {"keyword": "structuring"},
          "detect_ctr_candidates": {"mode": "structuring"}},
         ["get_aml_glossary", "lookup_fiu_reference_types", "detect_ctr_candidates"],
         "AML 용어집의 Structuring 정의와 그에 해당하는 FIU 참고유형을 각각 확인하고, 실제 데이터에서 "
         "보고 기준 미만으로 쪼갠 의심 거래도 탐지해줘",
         "Please check the Structuring definition in the AML glossary and the FIU reference type "
         "that corresponds to it, and detect in the data the suspicious transactions split below "
         "the reporting threshold.",
         "the two catalogs and the detection tool in one case; three gold tools"),
        ("st_mtool_125", ["validate_str_fields", "get_account_profile", "detect_monitoring_alerts"],
         {"validate_str_fields": {"str_draft": d_125},
          "get_account_profile": {"account_id": acc_125},
          "detect_monitoring_alerts": {"rule_id": "R003", "account_id": acc_125}},
         ["validate_str_fields", "get_account_profile", "detect_monitoring_alerts"],
         "아래 STR 초안의 필수 항목을 점검하고, 초안의 출금계좌 프로파일과 그 계좌의 R003 동일 금액 "
         f"반복 송금 알림도 함께 확인해줘: {draft_text(d_125)}",
         "Please check the required fields of the STR draft below, and also look at the profile of "
         "the withdrawal account it names and that account's R003 repeated identical amount alerts: "
         f"{draft_text(d_125)}",
         "the STR form check drives two follow-up calls on the account the draft names"),
    ]

    # The second call takes an input or a frame from the first in these cases, so the
    # order is part of the gold; elsewhere the two calls are independent and are not
    # ordered, the way the existing multi-tool cases treat it.
    ordered = {"st_mtool_101", "st_mtool_102", "st_mtool_104", "st_mtool_105", "st_mtool_106",
               "st_mtool_109", "st_mtool_115", "st_mtool_116", "st_mtool_124", "st_mtool_125"}

    cases = []
    for entry in spec:
        case_id, _tools, checks, order, question, question_en, rationale = entry[:7]
        # The gold calls are rendered in `tools_must_include` order, so an ordered case
        # lists its tools in the order the question implies.
        expected = {"primary_tool": order[0], "tools_must_include": list(order),
                    "param_checks": {tool: checks[tool] for tool in order}}
        if case_id in ordered:
            expected["tool_order"] = list(order)
        if len(entry) > 7:
            expected["reference_calls"] = {"query_transactions": {"sql": entry[7]}}
        cases.append({"id": case_id, "file": "cases_multi_tool.json", "question": question,
                      "question_en": question_en, "expected": expected, "rationale": rationale})
    return cases
