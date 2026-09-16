"""Group 4 - single-tool cases for the thinnest tools and the uncovered arguments.

Picked from the per-tool counts after WS-D: the analysis tools sit between 48 and 75
gold cases, and two schema arguments had no case at all -- `get_fraud_type_summary.bank_id`
and `detect_monitoring_alerts.account_id`. Six of these cases cover the first and five
the second; the rest widen the parameter ranges (CTR thresholds and windows, period pairs,
sample sizes, dormancy windows, counterparty thresholds) that the existing cases leave out.

Accounts come from `grounding.json`: the smurfing accounts have the counterparty count the
question asks for, and each monitoring account is one the rule still alerts on when the
account filter is applied.
"""

from __future__ import annotations


def build(grounding: dict) -> list[dict]:
    smurf_out = [row["account_id"] for row in grounding["accounts"]["smurf_out"]]
    smurf_in = [row["account_id"] for row in grounding["accounts"]["smurf_in"]]
    monitoring = grounding["monitoring_accounts"]
    pairs = {(row["fraud_type"], row["bank_id"]) for row in grounding["fraud_type_by_bank"]}

    def fraud_bank(fraud_type: int, bank_id: int) -> dict:
        if (fraud_type, bank_id) not in pairs:
            raise ValueError(f"no HOFINET rows for fraud type {fraud_type} at bank {bank_id}")
        return {"fraud_type": fraud_type, "bank_id": bank_id}

    def monitor(rule: str, index: int = 0) -> int:
        accounts = monitoring.get(rule) or []
        if len(accounts) <= index:
            raise ValueError(f"no account with a surviving {rule} alert")
        return accounts[index]

    spec = [
        # ---- detect_ctr_candidates: thresholds and windows the existing cases leave out ----
        ("st_ctr_044", "cases_detect_ctr_candidates.json", "detect_ctr_candidates",
         {"mode": "high_value", "threshold": 300000000, "limit": 50},
         "3억원 이상 고액거래를 상위 50건까지 조회해줘",
         "Please retrieve up to the top 50 high-value transactions of 300,000,000 KRW or more.",
         "high_value with a threshold in the top amount band HOFINET holds"),
        ("st_ctr_045", "cases_detect_ctr_candidates.json", "detect_ctr_candidates",
         {"mode": "structuring", "threshold": 20000000},
         "2000만원 보고 기준 미만으로 쪼갠 구조화(structuring) 의심 건을 탐지해줘",
         "Please detect suspected structuring: transactions split below a 20,000,000 KRW "
         "reporting threshold.",
         "structuring at a threshold no existing case uses"),
        ("st_ctr_046", "cases_detect_ctr_candidates.json", "detect_ctr_candidates",
         {"mode": "high_value", "date_from": 20220701, "date_to": 20221231},
         "2022년 하반기 고액현금거래보고 대상 거래를 조회해줘",
         "Please retrieve the transactions subject to currency transaction reporting in the "
         "second half of 2022.",
         "high_value over a window the existing cases leave out"),
        ("st_ctr_047", "cases_detect_ctr_candidates.json", "detect_ctr_candidates",
         {"mode": "structuring", "date_from": 20211001, "date_to": 20211231},
         "2021년 4분기 구조화(structuring) 의심 거래를 탐지해줘",
         "Please detect suspected structuring transactions in the fourth quarter of 2021.",
         "structuring in the first full quarter of the data"),
        ("st_ctr_048", "cases_detect_ctr_candidates.json", "detect_ctr_candidates",
         {"mode": "high_value", "limit": 50},
         "고액거래(high_value) 보고 후보를 상위 50건까지 뽑아줘",
         "Please pull up to the top 50 high_value reporting candidates.",
         "the mode is named, so only the limit has to be read off the question"),
        ("st_ctr_049", "cases_detect_ctr_candidates.json", "detect_ctr_candidates",
         {"mode": "structuring", "threshold": 5000000, "date_from": 20230401, "date_to": 20230630},
         "2023년 2분기에 500만원 기준 아래로 나눠 거래한 구조화(structuring) 의심 건을 찾아줘",
         "Please find suspected structuring in the second quarter of 2023: transactions split "
         "below a 5,000,000 KRW threshold.",
         "structuring with both a threshold and a window"),

        # ---- compare_periods: period pairs the existing cases leave out ----
        ("st_cp_044", "cases_compare_periods.json", "compare_periods",
         {"period1_start": 20220101, "period1_end": 20220131,
          "period2_start": 20220701, "period2_end": 20220731},
         "2022년 1월과 2022년 7월 거래 통계를 비교해줘",
         "Please compare the transaction statistics of January 2022 and July 2022.",
         "two single months a half year apart"),
        ("st_cp_045", "cases_compare_periods.json", "compare_periods",
         {"period1_start": 20210901, "period1_end": 20211231,
          "period2_start": 20240901, "period2_end": 20241231},
         "데이터가 시작되는 2021년 9~12월과 마지막 구간인 2024년 9~12월의 거래 규모를 비교해줘",
         "Please compare the transaction volume of September-December 2021, where the data "
         "starts, with September-December 2024, where it ends.",
         "the first and the last window of the data range"),
        ("st_cp_046", "cases_compare_periods.json", "compare_periods",
         {"period1_start": 20220401, "period1_end": 20220630,
          "period2_start": 20221001, "period2_end": 20221231},
         "20220401부터 20220630까지와 20221001부터 20221231까지 이상거래 비율을 비교해줘",
         "Please compare the suspicious transaction ratio between 20220401-20220630 and "
         "20221001-20221231.",
         "the dates are written out, so nothing has to be derived"),
        ("st_cp_047", "cases_compare_periods.json", "compare_periods",
         {"period1_start": 20230801, "period1_end": 20230831,
          "period2_start": 20230901, "period2_end": 20230930},
         "2023년 8월과 9월 이상거래 건수를 비교해줘",
         "Please compare the suspicious transaction counts of August and September 2023.",
         "two consecutive months no existing case pairs"),
        ("st_cp_048", "cases_compare_periods.json", "compare_periods",
         {"period1_start": 20230101, "period1_end": 20230430,
          "period2_start": 20240101, "period2_end": 20240430},
         "20230101부터 20230430까지와 20240101부터 20240430까지 거래 통계를 비교해줘",
         "Please compare the transaction statistics between 20230101-20230430 and "
         "20240101-20240430.",
         "a four-month window against the same window a year later, dates written out"),
        ("st_cp_049", "cases_compare_periods.json", "compare_periods",
         {"period1_start": 20221001, "period1_end": 20221231,
          "period2_start": 20230101, "period2_end": 20230331},
         "2022년 4분기와 2023년 1분기 이상거래 추이를 비교해줘",
         "Please compare the suspicious transaction trend of the fourth quarter of 2022 and "
         "the first quarter of 2023.",
         "a year boundary pair the existing cases leave out"),

        # ---- get_fraud_type_summary: the bank_id argument, which had no case ----
        ("st_gfs_044", "cases_get_fraud_type_summary.json", "get_fraud_type_summary",
         fraud_bank(1, 159),
         "출금금융회사 159의 갑작스러운 거래패턴의 변화(유형1) 이상거래 현황을 알려줘",
         "Please give the status of sudden change in transaction pattern (type 1) suspicious "
         "transactions at withdrawal institution 159.",
         "first case to filter the fraud type summary by institution"),
        ("st_gfs_045", "cases_get_fraud_type_summary.json", "get_fraud_type_summary",
         fraud_bank(2, 134),
         "출금금융회사 134에서 발생한 신규 수신처 거래 이상거래 통계를 요약해줘",
         "Please summarize the statistics of transaction with new counterparty suspicious "
         "transactions at withdrawal institution 134.",
         "the fraud type has to be resolved from its name, the institution is given"),
        ("st_gfs_046", "cases_get_fraud_type_summary.json", "get_fraud_type_summary",
         fraud_bank(3, 159),
         "출금금융회사 159의 분할 거래(유형3) 이상거래 건수와 금액을 알려줘",
         "Please give the count and the amount of split transaction (type 3) suspicious "
         "transactions at withdrawal institution 159.",
         "institution filter on the type that concentrates at one institution"),
        ("st_gfs_047", "cases_get_fraud_type_summary.json", "get_fraud_type_summary",
         fraud_bank(4, 147),
         "다중거래의 동시 요청 이상거래 현황을 출금금융회사 147로 좁혀서 조회해줘",
         "Please retrieve the status of concurrent multiple transactions suspicious "
         "transactions narrowed to withdrawal institution 147.",
         "institution filter on the type that is almost entirely one institution's"),
        ("st_gfs_048", "cases_get_fraud_type_summary.json", "get_fraud_type_summary",
         fraud_bank(5, 159),
         "거액 입금 후 당일 인출 이상거래를 출금금융회사 159 기준으로 요약해줘",
         "Please summarize same-day withdrawal after large deposit suspicious transactions "
         "for withdrawal institution 159.",
         "institution filter on one of the two smallest fraud types"),
        ("st_gfs_049", "cases_get_fraud_type_summary.json", "get_fraud_type_summary",
         fraud_bank(7, 159),
         "심야/새벽 대량 거래 이상거래를 출금금융회사 159로 좁혀서 통계를 보여줘",
         "Please show the statistics of late-night/early-morning bulk transaction suspicious "
         "transactions narrowed to withdrawal institution 159.",
         "all 35 rows of this type sit at one institution; the filter must not empty the result"),

        # ---- rank_risky_transactions: sample and top-k ranges the existing cases leave out ----
        ("st_rrt_044", "cases_rank_risky_transactions.json", "rank_risky_transactions",
         {"sample_size": 800, "top_k": 12},
         "800건 샘플에서 위험 점수 상위 12건을 추출해줘",
         "Please extract the top 12 by risk score from a sample of 800 transactions.",
         "a sample and top-k pair no existing case uses"),
        ("st_rrt_045", "cases_rank_risky_transactions.json", "rank_risky_transactions",
         {"sample_size": 1800, "top_k": 45},
         "1800건 표본을 모델로 채점해서 위험도 상위 45건을 뽑아줘",
         "Please score a sample of 1,800 transactions with the model and pull the top 45 by risk.",
         "a sample and top-k pair no existing case uses"),
        ("st_rrt_046", "cases_rank_risky_transactions.json", "rank_risky_transactions",
         {"top_k": 100},
         "이 도구가 한 번에 돌려줄 수 있는 최대 건수까지 위험 거래를 랭킹해줘",
         "Please rank the risky transactions up to the largest number this tool returns at once.",
         "top_k has to be read off the schema maximum rather than the question"),
        ("st_rrt_047", "cases_rank_risky_transactions.json", "rank_risky_transactions",
         {"sample_size": 4800, "top_k": 75},
         "4800건 배치 예측을 돌린 뒤 위험도 상위 75건을 우선조사 목록으로 만들어줘",
         "Please run a batch prediction over 4,800 transactions and build a priority "
         "investigation list of the top 75 by risk.",
         "a sample and top-k pair no existing case uses"),
        ("st_rrt_048", "cases_rank_risky_transactions.json", "rank_risky_transactions",
         {"sample_size": 2600, "top_k": 35},
         "2600건 샘플 중 위험 점수가 가장 높은 35건을 정렬해서 보여줘",
         "Please sort and show the 35 highest-risk-score transactions out of a sample of 2,600.",
         "a sample and top-k pair no existing case uses"),

        # ---- detect_monitoring_alerts: the account_id argument, which had no case ----
        ("st_mon_044", "cases_detect_monitoring_alerts.json", "detect_monitoring_alerts",
         {"rule_id": "R002", "account_id": monitor("R002", 0)},
         f"계좌 {monitor('R002', 0)}이 같은 날 10건 이상 거래한 적이 있는지 R002 규칙으로 확인해줘",
         f"Please check with rule R002 whether account {monitor('R002', 0)} ever made 10 or more "
         f"transactions on one day.",
         "first case to apply the account filter of the monitoring tool"),
        ("st_mon_045", "cases_detect_monitoring_alerts.json", "detect_monitoring_alerts",
         {"rule_id": "R003", "account_id": monitor("R003", 0)},
         f"계좌 {monitor('R003', 0)}이 동일 금액을 반복 송금했는지 모니터링 규칙 알림으로 확인해줘",
         f"Please check through the monitoring rule alerts whether account {monitor('R003', 0)} "
         f"sent the same amount repeatedly.",
         "the rule has to be resolved from its description, the account is given"),
        ("st_mon_046", "cases_detect_monitoring_alerts.json", "detect_monitoring_alerts",
         {"rule_id": "R001", "account_id": monitor("R001", 0)},
         f"계좌 {monitor('R001', 0)}의 심야 대량 거래 알림(R001)을 조회해줘",
         f"Please retrieve the nighttime bulk transaction alerts (R001) of account "
         f"{monitor('R001', 0)}.",
         "account filter on the night-time rule"),
        ("st_mon_047", "cases_detect_monitoring_alerts.json", "detect_monitoring_alerts",
         {"rule_id": "R004", "account_id": monitor("R004", 0)},
         f"계좌 {monitor('R004', 0)}의 거래가 한 입금 기관에 절반 이상 몰렸는지 모니터링 규칙으로 "
         f"확인해줘",
         f"Please check through the monitoring rules whether account {monitor('R004', 0)} sends at "
         f"least half of its transactions to one receiving institution.",
         "the rule has to be resolved from its description, the account is given"),
        ("st_mon_048", "cases_detect_monitoring_alerts.json", "detect_monitoring_alerts",
         {"rule_id": "R005", "account_id": monitor("R005", 0)},
         f"계좌 {monitor('R005', 0)}의 거래량이 직전 동일 기간 대비 급증했는지 R005 규칙 알림으로 "
         f"확인해줘",
         f"Please check with the rule R005 alerts whether the volume of account "
         f"{monitor('R005', 0)} jumped against the preceding period of equal length.",
         "account filter on the pattern-change rule"),

        # ---- analyze_channel_risk: windows the existing cases leave out ----
        ("st_acr_044", "cases_analyze_channel_risk.json", "analyze_channel_risk",
         {"date_from": 20210901, "date_to": 20211231},
         "데이터가 시작되는 2021년 9월부터 12월까지 채널별 이상거래 비율을 분석해줘",
         "Please analyze the suspicious transaction ratio by channel from September to "
         "December 2021, where the data starts.",
         "the opening window of the data range"),
        ("st_acr_045", "cases_analyze_channel_risk.json", "analyze_channel_risk",
         {"date_from": 20220101, "date_to": 20220331},
         "2022년 1분기 매체구분별 위험도를 분석해줘",
         "Please analyze the risk by media type for the first quarter of 2022.",
         "a quarter the existing cases leave out"),
        ("st_acr_046", "cases_analyze_channel_risk.json", "analyze_channel_risk",
         {"date_from": 20221001, "date_to": 20221231},
         "2022년 4분기 채널별 이상거래 현황을 확인해줘",
         "Please check the suspicious transaction status by channel for the fourth quarter of 2022.",
         "a quarter the existing cases leave out"),
        ("st_acr_047", "cases_analyze_channel_risk.json", "analyze_channel_risk",
         {"date_from": 20231001, "date_to": 20231231},
         "2023년 4분기 채널별 위험도를 분석해서 이상거래 비율이 가장 높은 매체를 알려줘",
         "Please analyze the risk by channel for the fourth quarter of 2023 and tell me which "
         "media type has the highest suspicious transaction ratio.",
         "a quarter the existing cases leave out"),
        ("st_acr_048", "cases_analyze_channel_risk.json", "analyze_channel_risk",
         {"date_from": 20240501, "date_to": 20240831},
         "20240501부터 20240831까지 매체구분별 이상거래 비율을 분석해줘",
         "Please analyze the suspicious transaction ratio by media type from 20240501 to 20240831.",
         "a window that crosses quarter boundaries, dates written out"),

        # ---- detect_dormant_reactivation: dormancy windows and amounts not covered ----
        ("st_dorm_045", "cases_detect_dormant_reactivation.json", "detect_dormant_reactivation",
         {"dormant_days": 120},
         "120일 이상 거래가 없다가 다시 사용된 계좌를 탐지해줘",
         "Please detect accounts used again after 120 days or more without a transaction.",
         "a shorter dormancy window than any existing case"),
        ("st_dorm_046", "cases_detect_dormant_reactivation.json", "detect_dormant_reactivation",
         {"dormant_days": 450},
         "450일 넘게 휴면이던 계좌의 재활성화 거래를 찾아줘",
         "Please find the reactivation transactions of accounts dormant for more than 450 days.",
         "a dormancy window between the 365-day and 730-day cases"),
        ("st_dorm_047", "cases_detect_dormant_reactivation.json", "detect_dormant_reactivation",
         {"dormant_days": 240, "min_reactivation_amount": 100000000},
         "240일 이상 미사용 계좌 중 재활성화 금액이 1억원 이상인 건을 조회해줘",
         "Please retrieve accounts unused for 240 days or more whose reactivation amount is "
         "100,000,000 KRW or more.",
         "the largest reactivation amount that still returns rows"),
        ("st_dorm_048", "cases_detect_dormant_reactivation.json", "detect_dormant_reactivation",
         {"dormant_days": 800},
         "800일 이상 잠자던 계좌가 다시 쓰인 사례를 보여줘",
         "Please show the cases where an account dormant for 800 days or more was used again.",
         "the longest dormancy window that still returns rows"),
        ("st_dorm_049", "cases_detect_dormant_reactivation.json", "detect_dormant_reactivation",
         {"dormant_days": 150, "min_reactivation_amount": 10000000, "limit": 25},
         "150일 이상 휴면 상태였다가 1000만원 이상 거래로 재활성화된 계좌를 상위 25건 조회해줘",
         "Please retrieve the top 25 accounts that were dormant for 150 days or more and were "
         "reactivated with a transaction of 10,000,000 KRW or more.",
         "all three arguments set at once"),

        # ---- detect_smurfing_network: counterparty thresholds and fresh accounts ----
        ("st_smurf_045", "cases_detect_smurfing_network.json", "detect_smurfing_network",
         {"account_id": smurf_out[1], "direction": "outbound", "min_counterparts": 30},
         f"계좌 {smurf_out[1]}이 30곳 이상 수취 계좌로 자금을 분산하는지 확인해줘",
         f"Please check whether account {smurf_out[1]} disperses funds to 30 or more receiving "
         f"accounts.",
         "the direction has to be read from 'disperses'; the account has 60 outgoing counterparties"),
        ("st_smurf_046", "cases_detect_smurfing_network.json", "detect_smurfing_network",
         {"account_id": smurf_in[0], "direction": "inbound", "min_counterparts": 25},
         f"계좌 {smurf_in[0]}로 25곳 이상에서 자금이 유입되는지 inbound 방향으로 확인해줘",
         f"Please check in the inbound direction whether funds reach account {smurf_in[0]} from "
         f"25 or more accounts.",
         "the direction is named; the account has 60 incoming counterparties"),
        ("st_smurf_047", "cases_detect_smurfing_network.json", "detect_smurfing_network",
         {"direction": "inbound", "min_counterparts": 30, "date_from": 20230101, "date_to": 20231231},
         "2023년 한 해 동안 30곳 이상 거래처로부터 자금을 받은 집결 계좌를 조회해줘",
         "Please retrieve the collection accounts that received funds from 30 or more "
         "counterparties during 2023.",
         "a counterparty threshold and a window, both above what the existing cases use"),
        ("st_smurf_048", "cases_detect_smurfing_network.json", "detect_smurfing_network",
         {"direction": "outbound", "min_counterparts": 40, "limit": 15},
         "40개 이상 계좌로 자금을 내보내는 분산 계좌를 상위 15건만 보여줘",
         "Please show only the top 15 dispersion accounts that send funds to 40 or more accounts.",
         "the highest outbound counterparty threshold in the benchmark"),
        ("st_smurf_049", "cases_detect_smurfing_network.json", "detect_smurfing_network",
         {"account_id": smurf_in[2], "direction": "inbound", "min_counterparts": 50},
         f"계좌 {smurf_in[2]}로 50곳이 넘는 상대방이 송금했는지 유입 방향으로 분석해줘",
         f"Please analyze in the inbound direction whether more than 50 counterparties sent "
         f"money to account {smurf_in[2]}.",
         "the direction has to be read from 'inbound side'; the account has 60 senders"),
    ]

    cases = []
    for case_id, file_name, tool, checks, question, question_en, rationale in spec:
        cases.append({"id": case_id, "file": file_name, "question": question,
                      "question_en": question_en,
                      "expected": {"primary_tool": tool, "tools_must_include": [tool],
                                   "param_checks": {tool: checks}},
                      "rationale": rationale})
    return cases
