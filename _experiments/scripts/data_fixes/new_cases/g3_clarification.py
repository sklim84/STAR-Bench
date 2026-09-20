"""Group 3 - clarification cases (21 -> 40).

a case expects a clarification only when a *schema-required* argument of the
tool the question asks for is missing or is left as an unresolved reference. Each
entry below names that tool and that argument, and the question names everything
else, so a default call cannot answer it and asking back is the only correct move.
Tools whose arguments are all optional are deliberately absent: for those a default
call is correct, which is what settled for `st_mp_012/013/019/021/023`.
"""

from __future__ import annotations

# tool whose required argument is missing, the argument, Korean question, English question
MISSING = [
    ("detect_ctr_candidates", "mode",
     "앞에서 말한 조회 모드로 CTR 대상 거래를 뽑아줘",
     "Please pull the CTR candidate transactions in the query mode we talked about."),
    ("score_account_risk", "account_id",
     "그 계좌의 행동 위험 점수를 5개 지표로 산출해줘",
     "Please score that account's behavioural risk over the five indicators."),
    ("predict_fraud", "time_slot, sender_bank, receiver_bank, fund_type, media_type, amount",
     "그 거래 건의 이상거래 위험 점수를 모델로 예측해줘",
     "Please score that transaction for fraud risk with the model."),
    ("query_transactions", "sql",
     "앞에서 얘기한 조건으로 거래 테이블을 SQL로 조회해줘",
     "Please query the transaction table with SQL on the conditions we discussed."),
    ("get_fraud_type_summary", "fraud_type",
     "그 이상거래 유형의 금액 통계와 상위 관련 기관을 알려줘",
     "Please give the amount statistics and the top related institutions for that suspicious "
     "transaction type."),
    ("compare_periods", "period1_start, period1_end, period2_start, period2_end",
     "그 두 분기 거래 통계를 비교해서 증감률을 계산해줘",
     "Please compare the transaction statistics of those two quarters and work out the rate "
     "of change."),
    ("get_institution_report", "bank_id",
     "그 출금 금융회사의 입출금 양방향 현황 리포트를 만들어줘",
     "Please build the outbound and inbound status report for that withdrawal institution."),
    ("detect_aml_patterns", "account_b",
     "계좌 9000000000024638에서 그 계좌까지 이어지는 최단 이체 경로를 찾아줘",
     "Please find the shortest chain of transfers from account 9000000000024638 to that account."),
    ("get_aml_glossary", "term",
     "AML 용어집에서 아까 언급한 약어 항목의 정의와 출처를 확인해줘",
     "Please check the definition and the source of the abbreviation we mentioned earlier in "
     "the AML glossary."),
    ("lookup_fiu_reference_types", "keyword",
     "그 유형에 해당하는 FIU 의심거래 참고유형을 은행업 기준으로 조회해줘",
     "Please look up the FIU suspicious-transaction reference types for that type, restricted "
     "to the banking industry."),
    ("validate_str_fields", "str_draft",
     "방금 작성한 STR 초안의 필수 항목 누락 여부를 점검해줘",
     "Please check the STR draft we just wrote for missing required fields."),
    ("analyze_network", "account_id",
     "그 계좌 주변 거래 네트워크를 2홉까지 분석해줘",
     "Please analyze the transaction network around that account out to two hops."),
    ("get_account_profile", "account_id",
     "그 출금계좌의 거래 프로파일과 주요 거래상대 5곳을 보여줘",
     "Please show that withdrawal account's transaction profile and its top five counterparties."),
    ("get_receiving_account_profile", "account_id",
     "그 수취계좌로 자금을 보낸 기관 분포를 입금 프로파일로 조회해줘",
     "Please look up, in the inbound profile, the distribution of institutions that sent funds "
     "to that receiving account."),
    ("detect_smurfing_network", "direction",
     "계좌 9000000000024638의 스머핑 네트워크를 앞에서 정한 방향 기준으로 분석해줘",
     "Please analyze the smurfing network of account 9000000000024638 in the direction we "
     "settled on earlier."),
    ("detect_monitoring_alerts", "rule_id",
     "2024년 3분기 기간으로 그 모니터링 규칙의 알림을 조회해줘",
     "Please look up the alerts of that monitoring rule over the third quarter of 2024."),
    ("detect_aml_patterns", "pattern_type",
     "그 자금세탁 패턴 유형을 상위 20건까지 탐지해줘",
     "Please detect up to the top 20 of that money laundering pattern type."),
    ("predict_fraud", "sender_bank, receiver_bank, fund_type",
     "거래시간대 9, 인터넷뱅킹(매체구분 2), 500만원까지는 정해졌어. 이 거래의 이상거래 위험 "
     "점수를 예측해줘",
     "Time slot 9, internet banking (media type 2) and 5,000,000 KRW are settled. Please score "
     "this transaction for fraud risk."),
    ("query_transactions", "sql",
     "그 SQL 쿼리를 실행해서 결과 건수와 상위 행을 보여줘",
     "Please run that SQL query and show the row count and the top rows."),
]


def build(grounding: dict) -> list[dict]:
    cases = []
    for index, (tool, argument, question, question_en) in enumerate(MISSING, start=26):
        cases.append({
            "id": f"st_mp_{index:03d}",
            "file": "cases_missing_parameters.json",
            "question": question,
            "question_en": question_en,
            "expected": {"primary_tool": "", "tools_must_include": [], "expect_clarification": True},
            "rationale": f"{tool} cannot run: its required argument {argument} is unresolved",
        })
    return cases
