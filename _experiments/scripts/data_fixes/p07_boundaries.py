"""Pass 07 - one gold tool per question (D11; L1-002 ... L1-011).

Ten pairs of tools overlap so far that the same sentence had different gold tools
in different files, and models that picked the other tool were scored wrong. D11
adds a discriminating cue to the question instead of accepting both tools, so
exactly one gold remains. The cues follow the tool that can actually answer:

* graph risk score vs behavioural risk score: the question names the graph.
* funnel vs smurfing: funnel questions state the few outgoing counterparties,
  smurfing questions state the counterparty count in one direction.
* CTR structuring vs HOFINET fraud type 3: "structuring below the reporting
  threshold" for CTR, "split transaction (type 3)" for the fraud type.
* get_statistics vs get_fraud_type_summary: a share of the total or a comparison
  across types is the distribution (get_statistics); one type's amounts, banks
  and dates are get_fraud_type_summary.
* institution report vs fraud type summary: the report question asks for the
  institution's overall status, not for one type.
* monitoring rules: the question names the rule or its alert.
* receiving profile vs smurfing: the profile question asks for the senders and
  their institutions, the smurfing question for a counterparty threshold.
* query_transactions vs the dedicated tools: the SQL question says so.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both

# case_id -> (kr question | None, en question | None, gold | None, issue, why)
EDITS = {
    # L1-002 graph risk score vs score_account_risk
    "st_ap_005": ("계좌 9000000000017070의 위험도 점수를 그래프 DB 기반으로 산출해줘",
                  "Please compute the risk score for account 9000000000017070 from the transfer graph.",
                  None, "L1-002",
                  "the as-is sentence is the one score_account_risk answers, so 96% of the "
                  "configurations called that tool and h was .04; the graph cue leaves one gold"),
    "st_ap_035": ("계좌 9000000001372521의 AML 위험 점수를 그래프 분석으로 계산해줘",
                  "Please compute the AML risk score for account 9000000001372521 with graph analysis.",
                  None, "L1-002",
                  "same overlap as st_ap_005 (h .07, 93% chose score_account_risk)"),

    # L1-003 funnel vs smurfing
    "st_ap_003": ("입금 상대는 많고 출금 상대는 소수인 funnel(집금) 계좌 패턴을 탐지해줘",
                  "Please detect funnel (collection) account patterns: many incoming counterparties and "
                  "only a few outgoing ones.",
                  None, "L1-003",
                  "both tools described mule accounts, so the boundary was invisible; the funnel "
                  "questions now state the few outgoing counterparties that define the pattern"),
    "st_ap_008": ("다수의 계좌에서 돈을 받아 소수의 계좌로만 내보내는 funnel 계좌를 탐지해줘",
                  "Please detect funnel accounts that receive from many accounts and forward to only a "
                  "few accounts.",
                  None, "L1-003", "71% chose detect_smurfing_network because the sentence named no "
                  "outgoing side; the funnel condition is now explicit"),
    "st_ap_012": ("보이스피싱 자금이 모이는 계좌를 찾아줘. 입금 상대는 많고 출금은 소수 계좌로만 나가는 구조야",
                  "Please identify accounts where voice phishing proceeds are collected: many incoming "
                  "counterparties and outgoing transfers to only a few accounts.",
                  None, "L1-003", "54% chose detect_smurfing_network; the outgoing condition is now explicit"),
    "st_ap_017": ("자금세탁 형태 중 다수 입금·소수 출금 구조의 funnel 계좌 패턴을 탐지해줘",
                  "Among money laundering typologies, please detect funnel accounts with many incoming "
                  "and few outgoing counterparties.",
                  None, "L1-003", "79% chose detect_smurfing_network; naming funnel and the outgoing "
                  "condition leaves one gold"),
    "st_ap_023": ("금융사기에 쓰이는 funnel(다수 입금·소수 출금) 계좌 패턴 20건을 탐지해줘",
                  "Please detect 20 funnel account patterns (many incoming, few outgoing counterparties) "
                  "used in financial fraud.",
                  None, "L1-003", "same funnel/smurfing overlap"),
    "st_ap_028": ("자금세탁 의심 계좌 중 입금 상대는 분산되고 출금은 소수 계좌로만 나가는 funnel 계좌를 탐지해줘",
                  "Please identify funnel accounts with suspicious money laundering activity where the "
                  "incoming counterparties are dispersed and the outgoing ones are only a few.",
                  None, "L1-003", "same funnel/smurfing overlap"),
    "st_ap_036": ("입금 상대가 많고 출금 상대가 소수인 funnel 의심 계좌를 25건 탐지해줘",
                  "Please identify 25 suspected funnel accounts with many incoming and few outgoing "
                  "counterparties.",
                  None, "L1-003", "same funnel/smurfing overlap"),
    "st_ap_039": ("여러 출처에서 소규모로 입금받아 소수 계좌로만 내보내는 집금책 funnel 계좌를 탐지해줘",
                  "Please identify collection (funnel) accounts that receive small deposits from many "
                  "sources and forward them to only a few accounts.",
                  None, "L1-003", "75% chose detect_smurfing_network; the outgoing condition is now explicit"),
    "st_smurf_040": ("계좌 9000000004388166이 여러 계좌에서 자금을 수집하는지, 유입 거래 상대 수 기준으로 분석해줘",
                     "Please analyze whether account 9000000004388166 collects funds from many accounts, "
                     "by its number of incoming counterparties.",
                     None, "L1-003",
                     "the as-is sentence ('collects and then forwards in one go') describes funnel, not "
                     "the inbound counterparty count the gold tool measures"),
    "st_smurf_015": ("유입 거래 상대가 5곳 이상인 자금 집결 계좌를 찾아줘",
                     "Please identify accounts that collect funds from five or more distinct sending "
                     "accounts.",
                     None, "L1-003", "the counterparty threshold is what separates smurfing from funnel"),
    "st_smurf_037": ("보이스피싱 조직이 피해자 여러 명에게서 나눠 받는 구조를, 유입 거래 상대 수 기준으로 탐지해줘",
                     "Please detect the structure in which a voice phishing group receives split payments "
                     "from many victims, by the number of incoming counterparties.",
                     None, "L1-003", "'consolidating into a single account' read as funnel"),
    "st_smurf_041": ("불법 도박 사이트 정산 계좌처럼 유입 거래 상대가 수십 곳인 집결 계좌를 탐지해줘",
                     "Please detect collection accounts with dozens of incoming counterparties, like the "
                     "settlement accounts of illegal gambling sites.",
                     None, "L1-003", "the counterparty count makes the smurfing tool the only fit"),

    # L1-004 smurfing wording on a CTR case
    "st_ctr_031": ("같은 날 보고 기준 미만으로 쪼갠 구조화(structuring) 의심 거래를 탐지해줘",
                   "Please detect suspected structuring: transactions split below the reporting threshold "
                   "on the same day.",
                   None, "L1-004",
                   "the word smurfing pointed at detect_smurfing_network, whose name and description "
                   "carry it (h .04, 82% chose that tool)"),

    # L1-005 get_statistics: the distribution, not one type
    "st_gs_031": ("이상거래 유형별 건수 분포를 보여주고 가장 적게 발생한 유형이 무엇인지 알려줘",
                  "Please show the distribution of suspicious transactions by fraud type and say which "
                  "type occurs least often.",
                  None, "L1-005",
                  "a single type's count is what get_fraud_type_summary returns; the question now asks "
                  "for the distribution, which only get_statistics gives"),
    "st_gs_035": ("이상거래 유형별 분포에서 심야/새벽 대량 거래 유형(유형7)이 차지하는 비율을 알려줘",
                  "In the distribution of suspicious transactions by fraud type, what share does the "
                  "late-night/early-morning bulk transaction type (type 7) hold?",
                  None, "L1-005",
                  "HOFINET has no 'other' fraud type, and a share of the total needs the distribution "
                  "and the total that only get_statistics returns"),
    "st_gs_046": ("이상거래 유형별 분포에서 다중거래의 동시 요청과 갑작스러운 거래패턴의 변화 중 어느 쪽이 더 많은지 알려줘",
                  "In the distribution by fraud type, which occurs more often, concurrent multiple "
                  "transactions or a sudden change in transaction pattern?",
                  None, "L1-005", "comparing two types needs the distribution, not one type's summary"),
    "st_gs_049": ("이상거래 유형별 분포에서 분할 거래 유형(유형3)이 차지하는 비중을 알려줘",
                  "In the distribution by fraud type, what share does the split transaction type (type 3) "
                  "hold?",
                  None, "L1-005", "a share of the total needs the distribution and the total"),
    "st_gs_050": ("이상거래 유형별 분포에서 거액 입금 후 당일 인출 유형(유형5)이 차지하는 비중을 알려줘",
                  "In the distribution by fraud type, what share does the same-day withdrawal after a "
                  "large deposit type (type 5) hold?",
                  None, "L1-005", "a single type's count was answerable by either tool"),
    "st_gs_040": ("데이터에 포함된 분기별 거래 추이를 보여줘서 분기 수와 기간 범위를 확인해줘",
                  "Please show the quarterly transaction trend of the data so I can see how many quarters "
                  "it covers and over what period.",
                  {"primary_tool": "get_trend_analysis", "tools_must_include": ["get_trend_analysis"],
                   "param_checks": {"get_trend_analysis": {"unit": "quarterly"}}},
                  "L1-005", "get_statistics returns no dates at all, so it could not answer the question "
                  "it was gold for; the quarterly trend carries the period labels"),

    # L1-006 get_fraud_type_summary: what the tool returns
    "st_gfs_009": ("분할 거래(유형3) 이상거래가 최근 발생한 날짜를 알려줘",
                   "Please give the most recent dates on which split transactions (type 3) occurred.",
                   None, "L1-006",
                   "the tool returns five recent distinct dates, not a frequency by date, so 'mainly on "
                   "which dates' sent 43% to query_transactions"),
    "st_gfs_036": ("갑작스러운 거래패턴의 변화(유형1) 이상거래의 평균 거래금액과 상위 관련 금융회사를 알려줘",
                   "Please give the average transaction amount and the top associated institutions for "
                   "suspicious transactions of the sudden change in transaction pattern type (type 1).",
                   None, "L1-006",
                   "comparing one type's average against the other types needs a call per type; the "
                   "question now stays inside what one call returns"),
    "st_gfs_037": (None, None,
                   {"primary_tool": "get_statistics", "tools_must_include": ["get_statistics"],
                    "param_checks": {}},
                   "L1-006",
                   "get_fraud_type_summary returns one type's count but not the fraud total, so the share "
                   "of all suspicious transactions can only come from get_statistics; this also settles "
                   "the contradiction with st_gs_017"),
    "st_gfs_038": ("거액 입금 후 당일 인출(유형5) 이상거래가 집중된 상위 금융회사를 알려줘",
                   "Please give the top institutions where suspicious transactions of the same-day "
                   "withdrawal after a large deposit type (type 5) are concentrated.",
                   None, "L1-006",
                   "the tool returns no channel at all, so the as-is question about the medium could not "
                   "be answered by its own gold"),

    # L1-007 institution report vs fraud type summary
    "st_gir_007": ("bank_id 156 금융회사의 이상거래 종합 현황을 유형 분포까지 포함해 보고해줘",
                   "Please report the overall suspicious transaction status of the institution with "
                   "bank_id 156, including its distribution by fraud type.",
                   None, "L1-007",
                   "naming one fraud type made get_fraud_type_summary(fraud_type, bank_id) the exact "
                   "fit; the question now asks for the institution's overall report"),
    "st_gir_011": ("출금 금융회사 번호가 106인 기관의 이상거래 종합 현황을 기관 리포트로 분석해줘",
                   "Please analyze the overall suspicious transaction status of the institution whose "
                   "withdrawal institution number is 106 with the institution report.",
                   None, "L1-007", "same overlap (32% chose get_fraud_type_summary)"),
    "st_gir_020": ("금융기관 135번의 이상거래 종합 현황을 기관 리포트로 확인해줘",
                   "Please check the overall suspicious transaction status of financial institution 135 "
                   "with the institution report.",
                   None, "L1-007", "same overlap (50% chose get_fraud_type_summary)"),
    "st_gir_023": ("금융회사 145번의 이상거래 종합 현황과 상대 기관 분포를 분석해줘",
                   "Please analyze the overall suspicious transaction status of financial institution 145 "
                   "and its distribution of counterpart institutions.",
                   None, "L1-007", "same overlap (46% chose get_fraud_type_summary)"),
    "st_gir_037": ("bank_id 117번 기관의 이상거래 종합 현황을 출금·입금 양방향으로 확인해줘",
                   "Please check the overall suspicious transaction status of the institution with bank_id "
                   "117 on both the sending and the receiving side.",
                   None, "L1-007", "same overlap (43% chose get_fraud_type_summary)"),
    "st_gir_039": ("금융회사 124번의 이상거래가 어느 유형에 집중되는지 기관 종합 리포트로 확인해줘",
                   "Please check which fraud types the suspicious transactions of financial institution "
                   "124 concentrate in, using the overall institution report.",
                   None, "L1-007", "same overlap (50% chose get_fraud_type_summary)"),

    # L1-008 monitoring rules
    "st_mon_004": ("모니터링 규칙으로 같은 금액을 반복해서 송금한 계좌 알림을 확인해줘",
                   "Please check the monitoring alerts for accounts that sent the same amount repeatedly.",
                   None, "L1-008",
                   "R003 is the repeated-identical-amount rule (D18), and the as-is wording 'fixed "
                   "amount pattern' matched neither the rule nor any tool"),
    "st_mon_012": ("모니터링 규칙 R003으로 동일한 금액을 세 번 이상 반복 송금한 계좌를 찾아줘",
                   "Please use monitoring rule R003 to find accounts that sent the same amount three or "
                   "more times.",
                   None, "L1-008",
                   "'exact multiples of 1,000,000 won' is a SQL filter, not rule R003; h was 0 of 28 and "
                   "every configuration called query_transactions"),
    "st_mon_033": ("모니터링 알림 기준으로 동일한 금액을 반복 송금하는 계좌를 찾아줘",
                   "Please find accounts that repeatedly send an identical amount, by the monitoring "
                   "alert rule.",
                   None, "L1-008", "R003 counts repeated identical amounts (D18), not a regular schedule"),
    "st_mon_040": ("모니터링 규칙으로 같은 금액을 세 번 이상 반복 송금하는 의심 계좌를 탐지해줘",
                   "Please use the monitoring rules to detect suspicious accounts that send the same "
                   "amount three or more times.",
                   None, "L1-008", "R003 counts repeated identical amounts (D18), not a regular schedule"),
    "st_mon_006": ("모니터링 규칙으로 거래량이 급증한 계좌 알림을 탐지해줘",
                   "Please use the monitoring rules to detect alerts for accounts whose transaction volume "
                   "rose sharply.",
                   None, "L1-008",
                   "'a sudden change in transaction pattern' is also the name of fraud type 1, so 57% "
                   "chose a fraud-type tool; the rule cue separates them"),
    "st_mon_024": ("2023년 하반기에 거래량이 급증한 계좌를 모니터링 규칙 알림으로 찾아줘",
                   "Please find accounts whose transaction volume rose sharply in the second half of 2023 "
                   "through the monitoring rule alerts.",
                   None, "L1-008", "same overlap with fraud type 1 (71% chose another tool)"),
    "st_mon_036": ("단기간에 거래량이 급증한 계좌를 모니터링 규칙 알림으로 탐지해줘",
                   "Please detect accounts whose transaction volume rose sharply within a short period "
                   "through the monitoring rule alerts.",
                   None, "L1-008", "same overlap with fraud type 1 (43% chose another tool)"),
    "st_mon_013": ("심야 시간대에 500만원 이상 거래가 발생한 모니터링 규칙 알림을 찾아줘",
                   "Please find the monitoring rule alerts for transactions of 5,000,000 won or more in "
                   "the night time slots.",
                   None, "L1-008",
                   "'large amounts at night' is also the name of fraud type 7, so the rule's own "
                   "threshold and slots are now in the question"),
    "st_mon_017": ("심야·새벽 시간대 대량 거래 모니터링 규칙 알림을 확인해줘",
                   "Please check the monitoring rule alerts for bulk transactions in the late-night and "
                   "early-morning time slots.",
                   None, "L1-008", "same overlap with fraud type 7 (46% chose another tool)"),
    "st_mon_005": ("거래의 절반 이상이 한 입금 기관으로 몰린 계좌를 모니터링 규칙 알림으로 찾아줘",
                   "Please find accounts that send at least half of their transactions to one receiving "
                   "institution, through the monitoring rule alerts.",
                   None, "L1-008",
                   "the as-is sentence was a SQL aggregation (h .29); the rule's own condition is now "
                   "in the question"),
    "st_mon_010": ("하루에 10건 이상 거래한 계좌를 모니터링 규칙 알림으로 찾아줘",
                   "Please find accounts with 10 or more transactions on one day through the monitoring "
                   "rule alerts.",
                   None, "L1-008",
                   "'several transactions on the same day' was also the CTR structuring case st_ctr_012; "
                   "R002's own threshold separates them"),
    "st_ctr_012": ("동일 계좌가 같은 날 보고 기준 미만으로 나눠서 거래한 구조화 의심 건을 찾아줘",
                   "Please find suspected structuring where one account split its transactions below the "
                   "reporting threshold on the same day.",
                   None, "L1-008", "the counterpart of st_mon_010: this one is the CTR structuring case"),

    # L1-009 receiving profile vs smurfing
    "st_grap_028": ("계좌 9000000004260440의 수취 프로파일에서 주요 송금인과 출처 금융기관을 확인해줘",
                    "Please check the main senders and their sending institutions in the receiving profile "
                    "of account 9000000004260440.",
                    None, "L1-009",
                    "'receiving from multiple accounts' is what detect_smurfing_network counts; the "
                    "profile's own return values (top senders and sending banks) are now asked for"),
    "st_grap_037": ("입금계좌 9000000004410697의 수취 프로파일에서 소액 다건 입금의 주요 송금인을 확인해줘",
                    "Please check the main senders behind the repeated small deposits in the receiving "
                    "profile of account 9000000004410697.",
                    None, "L1-009", "same overlap with the smurfing counterparty count"),
    "st_grap_038b": ("계좌 9000000004260440의 수취 프로파일에서 최근 입금 상대와 출처 기관 분포를 확인해줘",
                     "Please check the recent senders and the distribution of their institutions in the "
                     "receiving profile of account 9000000004260440.",
                     None, "L1-009", "57% chose detect_smurfing_network for the as-is sentence"),
    "st_grap_040": ("계좌 9000000000029571의 수취 프로파일에서 송금인 수와 출처 기관 분포를 확인해 자금 유입 구조를 판단해줘",
                    "Please judge the inflow structure of account 9000000000029571 from the number of "
                    "senders and the distribution of their institutions in its receiving profile.",
                    None, "L1-009", "same overlap with the smurfing counterparty count"),
    "st_smurf_029": ("계좌 9000000000026712로 자금을 보낸 거래 상대가 5곳 이상인지 스머핑 네트워크로 확인해줘",
                     "Please check with the smurfing network whether five or more distinct counterparties "
                     "sent funds to account 9000000000026712.",
                     None, "L1-009",
                     "50% chose get_receiving_account_profile for the as-is sentence; the counterparty "
                     "threshold is the smurfing tool's own condition"),
    "st_gap_016": ("계좌 9000000004256150의 거래 통계 프로파일을 조회해줘",
                   "Please look up the transaction statistics profile of account 9000000004256150.",
                   None, "L1-009", "'analyze this account' carried no cue for any particular tool"),
    "st_an_027": ("계좌 9000000004256150의 거래 네트워크에서 연결된 상대 계좌를 분석해줘",
                  "Please analyze the connected counterpart accounts in the transaction network of account "
                  "9000000004256150.",
                  None, "L1-009",
                  "'counterparties of the account' is also the profile's top-counterparty list, so 68% "
                  "chose get_account_profile; the network cue leaves one gold"),

    # L1-010 CTR structuring vs fraud type 3
    "st_ctr_003": ("CTR 보고 대상인 1000만원 이상 고액거래를 탐지해줘",
                   "Please detect high-value transactions of 10,000,000 won or more that are subject to "
                   "CTR reporting.",
                   None, "L1-010", "'show transactions over 10 million won' was a plain SQL request (39% "
                   "chose query_transactions)"),
    "st_ctr_004": ("보고 기준 미만으로 쪼갠 구조화(structuring) 의심 건을 탐지해줘",
                   "Please detect suspected structuring: transactions split below the reporting threshold.",
                   None, "L1-010",
                   "'split transaction' is the official name of HOFINET fraud type 3, so 50% chose a "
                   "fraud-type tool; CTR cases now say structuring"),
    "st_ctr_009": ("2024년 상반기에 보고 기준 미만으로 쪼갠 구조화 의심 건을 탐지해줘",
                   "Please detect suspected structuring below the reporting threshold in the first half "
                   "of 2024.",
                   None, "L1-010", "same naming clash with fraud type 3 (46% chose another tool)"),
    "st_ctr_021": ("5000만원 보고 기준 아래로 쪼갠 구조화 의심 건을 탐지해줘",
                   "Please detect suspected structuring below a reporting threshold of 50 million won.",
                   None, "L1-010", "same naming clash with fraud type 3"),
    "st_ctr_036": ("3000만원 보고 기준 아래로 쪼갠 구조화 의심 건을 찾아줘",
                   "Please find suspected structuring below a reporting threshold of 30 million won.",
                   None, "L1-010", "same naming clash with fraud type 3"),
    "st_mtool_029": ("보고 기준 미만으로 쪼갠 구조화 의심 건을 탐지하고 심야 대량 거래 모니터링 알림도 확인해줘",
                     "Please detect suspected structuring below the reporting threshold and also check the "
                     "nighttime bulk transaction monitoring alerts.",
                     None, "L1-010", "same naming clash with fraud type 3"),
    "st_mtool_038": ("CTR 대상 구조화 의심 건을 탐지하고, 입금계좌 9000000000022515의 수취 프로파일을 조회해줘",
                     "Please detect suspected structuring subject to CTR and look up the receiving profile "
                     "of deposit account 9000000000022515.",
                     None, "L1-010", "same naming clash with fraud type 3"),
    "st_mtool_055": ("CTR 구조화 의심 건을 탐지하고, 2023년 4분기와 2024년 1분기 이상거래를 비교해줘",
                     "Please detect suspected CTR structuring and compare the suspicious transactions of "
                     "the fourth quarter of 2023 with those of the first quarter of 2024.",
                     None, "L1-010", "same naming clash with fraud type 3"),
    "st_mtool_065": ("고액거래 CTR 대상을 탐지하고, 보고 기준 미만 구조화 의심 건도 함께 확인해줘",
                     "Please detect high-value CTR candidates and also check for suspected structuring "
                     "below the reporting threshold.",
                     None, "L1-010", "same naming clash with fraud type 3"),
    "st_mtool_074": ("보고 기준 미만 구조화 의심 건을 탐지하고, 고액거래도 함께 조회해줘",
                     "Please detect suspected structuring below the reporting threshold and also query the "
                     "high-value transactions.",
                     None, "L1-010", "same naming clash with fraud type 3"),

    # L1-011 SQL vs the dedicated tools
    "st_qt_019": ("SQL로 매체구분별 이상거래 건수를 집계해줘",
                  "Please aggregate the suspicious transaction count by media type with SQL.",
                  None, "L1-011",
                  "the same aggregation is analyze_channel_risk's own output; the SQL cue separates the "
                  "two files' cases"),
    "st_qt_022": ("SQL로 2023년에 발생한 이상거래의 월별 건수를 조회해줘",
                  "Please query the monthly count of suspicious transactions that occurred in 2023 with SQL.",
                  None, "L1-011", "the same aggregation is get_trend_analysis's own output"),
    "st_qt_038": ("SQL로 이상거래 유형별 거래 건수와 총 금액을 조회하고 총 금액 기준 내림차순으로 정렬해줘",
                  "Please query the transaction count and total amount per fraud type with SQL and sort "
                  "them in descending order of total amount.",
                  None, "L1-011", "the counts alone are get_statistics's output; the SQL cue and the "
                  "sort keep one gold"),
    "st_qt_053": ("SQL로 이상거래 유형별 거래 건수 비율(전체 이상거래 대비 %)을 계산해줘",
                  "Please calculate the share of each fraud type in all suspicious transactions (in "
                  "percent) with SQL.",
                  None, "L1-011", "the same ratio is get_statistics's output"),
    "st_acr_007": ("채널별 위험도 분석으로 인터넷뱅킹 채널의 이상거래 건수와 비중을 알려줘",
                   "Please give the suspicious transaction count and share of the internet banking channel "
                   "from the channel risk analysis.",
                   None, "L1-011",
                   "the as-is sentence was a one-channel count that query_transactions answers (h .29, "
                   "19 of 28 called it)"),
    "st_acr_019": ("채널별 위험도를 비교해서 이상거래 비중이 가장 높은 매체를 알려줘",
                   "Please compare the risk by channel and say which medium has the highest share of "
                   "suspicious transactions.",
                   None, "L1-011", "the as-is sentence named no channel analysis (h .14)"),
}


def apply(kr: Bench, en: Bench, log: ChangeLog) -> None:
    kr_by, en_by = kr.by_id(), en.by_id()
    for case_id, (kr_text, en_text, gold, issue, why) in EDITS.items():
        for bench_by, lang, text in ((kr_by, "kr", kr_text), (en_by, "en", en_text)):
            case = bench_by[case_id]
            if text:
                log.set_field(case, lang, "question", text, issue, why)
            if gold:
                log.set_field(case, lang, "expected", copy.deepcopy(gold), issue, why)
    by_issue: dict[str, int] = {}
    for _, _, _, issue, _ in EDITS.values():
        by_issue[issue] = by_issue.get(issue, 0) + 1
    log.note("cases per issue: " + ", ".join(f"{k} {v}" for k, v in sorted(by_issue.items())))


def main() -> int:
    kr, en = both()
    log = ChangeLog("p07_boundaries", "D11: a discriminating cue in every question where two tools "
                                      "overlapped (L1-002 ... L1-011).")
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
