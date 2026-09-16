"""The 50 multi-turn STR scenarios, on real HOFINET entities (D03, L3-018).

Every account, institution, date, amount and channel below exists in HOFINET and
was chosen because it carries the story the scenario tells: a night-bulk alert
scenario uses an account the redefined R001 really flags, a smurfing scenario
uses an account with hundreds of real counterparties, and a `predict_fraud` turn
uses the feature combination of a transaction that is really in the data.

`Ref` values are read out of the executed result of an earlier turn while the
file is being built, so a scenario's gold arguments, its `context_ref`s and the
figures in its STR summary all come from the tool output the model sees.

The one-line reason for each entity choice is in `Scenario.why` and lands in
`rebuild_log.json`.
"""

from __future__ import annotations

import json

from .spec import Ref as R
from .spec import STR_SECTION_VI, Scenario as S, Turn as T

COLS = ("date, time_slot, sender_bank, sender_acc, receiver_bank, receiver_acc, "
        "fund_type, media_type, amount, fraud_type")


# A listing query has to be a total order, or two rows that tie on the ordering
# columns come back in either order and the injected result is not reproducible.
TIEBREAK = "sender_acc, receiver_acc, date, amount, time_slot, media_type, fund_type"


def rows(where: str, order: str = "amount DESC, date, receiver_acc", limit: int = 20) -> str:
    return (f"SELECT {COLS} FROM hofinet WHERE {where} "
            f"ORDER BY {order}, {TIEBREAK} LIMIT {limit}")


def predict_args(turn: int) -> dict:
    """The six model features of row 0 of a query result."""
    return {"time_slot": R(turn, "result[0].time_slot"),
            "sender_bank": R(turn, "result[0].sender_bank"),
            "receiver_bank": R(turn, "result[0].receiver_bank"),
            "fund_type": R(turn, "result[0].fund_type"),
            "media_type": R(turn, "result[0].media_type"),
            "amount": R(turn, "result[0].amount")}


def str_args(ft: int, summary: str, tools: list[str]) -> dict:
    return {"summary": summary, "fraud_type": STR_SECTION_VI[ft], "tools_used": tools}


# A deliberately incomplete STR draft: it fills the first four sections and
# leaves §VI and §VII empty, so `validate_str_fields` has something to report.
DRAFT_046 = {
    "Header": {"ReportingDate": "2024-12-31"},
    "I_ReportingInstitution": {"WithdrawalInstitutionCode": "159"},
    "II_Transactor": {"WithdrawalAccountNumber": "9000000004242511",
                      "ReceivingAccountNumber": "9000000004421535"},
    "III_TransactionDetails": {"TransactionPeriod": "20241001-20241231",
                               "TransactionCount": 43,
                               "TransactionChannel": "Internet Banking",
                               "TotalAmount_KRW": 172000000},
}
DRAFT_023 = {
    "Header": {"ReportingDate": "2024-12-31"},
    "I_ReportingInstitution": {"WithdrawalInstitutionCode": "159"},
    "II_Transactor": {"WithdrawalAccountNumber": "9000000000041932",
                      "ReceivingAccountNumber": "9000000002364786"},
    "III_TransactionDetails": {"TransactionPeriod": "20240101-20241231",
                               "TransactionCount": 6,
                               "TransactionChannel": "Internet Banking",
                               "TotalAmount_KRW": 320000000},
}


def draft_text(draft: dict) -> str:
    return json.dumps(draft, ensure_ascii=False)


SCENARIOS: list[S] = [

    # ---------------------------------------------------------------- 001
    S(id="mt_str_001", sub="base", ft=1,
      kr="계좌 지정 이상거래 조회에서 예측·네트워크 분석을 거쳐 STR 작성",
      en="Named account: query the transactions, predict, analyse the network, draft the STR",
      vars={"acc": 9000000000037352, "bank": 157},
      why="9000000000037352 carries 161 type-1 (sudden pattern change) transactions, the most of "
          "any account in HOFINET, and is a sender at institution 157.",
      turns=[
        T(kr="출금계좌 {acc}에서 갑작스러운 거래패턴의 변화가 의심돼. 이 계좌의 2024년 해당 유형 거래를 "
             "금액이 큰 순서로 조회해줘.",
          en="Withdrawal account {acc} looks like a sudden change in transaction pattern. List its "
             "2024 rows of that type, largest amount first.",
          tool="query_transactions",
          sql=rows("sender_acc = {acc} AND fraud_type = 1 AND date BETWEEN 20240101 AND 20241231"),
          conds=[("sender_acc", "=", 9000000000037352), ("fraud_type", "=", 1),
                 ("date", "BETWEEN", [20240101, 20241231])],
          bind={"n": R(1, "returned_count"), "top_amt": R(1, "result[0].amount"),
                "top_date": R(1, "result[0].date"), "top_rcv": R(1, "result[0].receiver_acc")}),
        T(kr="조회 결과 첫 번째 거래의 이상거래 위험 점수를 예측해줘.",
          en="Score the first transaction in that result with the risk model.",
          tool="predict_fraud", args=predict_args(1), ctx=(1, "result[0].amount", "amount"),
          bind={"score": R(2, "fraud_risk_score")}),
        T(kr="이 계좌의 1단계 거래 네트워크도 분석해줘.",
          en="Analyse this account's one-hop transaction network as well.",
          tool="analyze_network", args={"account_id": "{acc}"},
          bind={"neigh": R(3, "connected_account_count"), "nfr": R(3, "fraud_ratio_percent"),
                "ntot": R(3, "total_tx_count"), "nfrn": R(3, "fraud_tx_count")}),
        T(kr="분석 결과를 종합해서 갑작스러운 거래패턴의 변화 혐의로 STR을 작성해줘.",
          en="Put the analysis together and draft an STR for a sudden change in transaction pattern.",
          tool="generate_str",
          args=str_args(1,
            "출금계좌 {acc}(출금기관 {bank})의 전체 거래는 {ntot}건이고 이상거래는 {nfrn}건({nfr}%)이다. "
            "2024년 갑작스러운 거래패턴의 변화 유형 상위 {n}건 가운데 가장 큰 건은 {top_date:date}에 "
            "입금계좌 {top_rcv:으로로} 이체한 {top_amt:,}원이며 예측 모델 위험 점수는 {score:copula}다. "
            "1단계 네트워크에는 연결 계좌 {neigh}개가 있다. "
            "거래 규모와 상대 계좌 수가 종전 패턴과 달라 갑작스러운 거래패턴의 변화로 판단한다.",
            ["query_transactions", "predict_fraud", "analyze_network"])),
      ]),

    # ---------------------------------------------------------------- 002
    S(id="mt_str_002", sub="missing_parameter", ft=4,
      kr="정보 없이 STR 요청 후 되묻기, 계좌 지정, 조회·예측·CTR 확인을 거쳐 STR 작성",
      en="STR requested with nothing to report on, clarification, then query, prediction, CTR check, STR",
      vars={"acc": 9000000004236284, "bank": 147},
      why="9000000004236284 has 431 type-4 (concurrent multiple transactions) rows, the most in "
          "HOFINET, and its 2024 activity is large enough for a CTR high-value check.",
      turns=[
        T(kr="STR 하나 작성해야 하는데 도와줄 수 있어?",
          en="I need to file an STR. Can you help?", clarify=True,
          point_kr="분석 대상과 근거가 없어 generate_str의 필수 인자 summary를 만들 수 없다",
          point_en="no subject and no findings yet, so generate_str has nothing for its required summary"),
        T(kr="출금계좌 {acc:copula}고 다중거래의 동시 요청이 의심돼. 2024년 이상거래 내역을 금액 순으로 20건 조회해줘.",
          en="The account is {acc} and I suspect concurrent multiple transactions. List its 2024 "
             "flagged transactions, the 20 largest by amount.",
          tool="query_transactions",
          sql=rows("sender_acc = {acc} AND is_fraud = 1 AND date BETWEEN 20240101 AND 20241231"),
          conds=[("sender_acc", "=", 9000000004236284), ("is_fraud", "=", 1),
                 ("date", "BETWEEN", [20240101, 20241231])],
          bind={"n": R(2, "returned_count"), "top_amt": R(2, "result[0].amount"),
                "top_date": R(2, "result[0].date"), "media": R(2, "result[0].media_type")}),
        T(kr="첫 번째 거래의 위험 점수를 예측해봐.",
          en="Score the first transaction in that result.",
          tool="predict_fraud", args=predict_args(2), ctx=(2, "result[0].amount", "amount"),
          bind={"score": R(3, "fraud_risk_score")}),
        T(kr="2024년 거래 중 1천만원 이상 고액 건이 CTR 대상인지도 확인해줘.",
          en="Also check which 2024 transactions of 10 million KRW or more are CTR candidates.",
          tool="detect_ctr_candidates",
          args={"mode": "high_value", "date_from": 20240101, "date_to": 20241231},
          bind={"ctr_n": R(4, "count")}),
        T(kr="다중거래의 동시 요청으로 STR 작성해줘.",
          en="Draft the STR for concurrent multiple transactions.",
          tool="generate_str",
          args=str_args(4,
            "출금계좌 {acc}(출금기관 {bank})의 2024년 다중거래의 동시 요청 유형 상위 {n}건을 확인했고 "
            "최대 건은 {top_date:date}에 매체구분 {media} 채널로 이체한 {top_amt:,}원이다. "
            "해당 건의 예측 모델 위험 점수는 {score:copula}다. "
            "같은 기간 CTR 고액거래 조회에서 상위 {ctr_n}건이 나왔다. "
            "동일 시점에 다수 거래가 몰리는 형태여서 다중거래의 동시 요청으로 판단한다.",
            ["query_transactions", "predict_fraud", "detect_ctr_candidates"])),
      ]),

    # ---------------------------------------------------------------- 003
    S(id="mt_str_003", sub="long_context", ft=3,
      kr="금융회사 단위 분할 거래 집계에서 최다 계좌를 특정해 프로필·위험도 평가 후 STR 작성",
      en="Aggregate split transactions per institution, take the top account, profile and score it, draft the STR",
      vars={"bank": 159},
      why="Institution 159 is the top sender bank for type-3 (split) transactions (1,464 of 2,073); "
          "the grouped query really returns 9000000004390593 first.",
      turns=[
        T(kr="출금기관 {bank}에서 분할 거래 유형 이상거래가 많다고 들었어. 2024년 기준으로 출금계좌별 건수 상위 5개를 뽑아줘.",
          en="I hear institution {bank} has a lot of split-transaction fraud. Give me the top five "
             "withdrawal accounts by count for 2024.",
          tool="query_transactions",
          sql="SELECT sender_acc, count(*) AS tx_count, sum(amount) AS total_amount, "
              "min(date) AS first_date, max(date) AS last_date FROM hofinet "
              "WHERE sender_bank = {bank} AND fraud_type = 3 AND date BETWEEN 20240101 AND 20241231 "
              "GROUP BY sender_acc ORDER BY tx_count DESC, sender_acc LIMIT 5",
          conds=[("sender_bank", "=", 159), ("fraud_type", "=", 3),
                 ("date", "BETWEEN", [20240101, 20241231])],
          bind={"acc": R(1, "result[0].sender_acc"), "acc_n": R(1, "result[0].tx_count"),
                "acc_amt": R(1, "result[0].total_amount")}),
        T(kr="가장 건수가 많은 그 계좌의 프로필을 확인해줘.",
          en="Profile the account with the highest count.",
          tool="get_account_profile", args={"account_id": R(1, "result[0].sender_acc")},
          ctx=(1, "result[0].sender_acc", "account_id"),
          bind={"tot": R(2, "total_count"), "fr": R(2, "fraud_ratio_percent"),
                "cp": R(2, "top_counterparts[0].account_id")}),
        T(kr="이 계좌의 위험도도 평가해줘.",
          en="Score this account's risk as well.",
          tool="score_account_risk", args={"account_id": R(1, "result[0].sender_acc")},
          ctx=(1, "result[0].sender_acc", "account_id"),
          bind={"risk": R(3, "total_score"), "level": R(3, "risk_level")}),
        T(kr="지금까지 분석한 내용을 종합해서 분할 거래 혐의로 STR을 작성해줘.",
          en="Pull the analysis together and draft an STR for split transactions.",
          tool="generate_str",
          args=str_args(3,
            "출금기관 {bank} 소속 출금계좌 {acc:은는} 2024년에 분할 거래 유형 이상거래 {acc_n}건, {acc_amt:,}원을 "
            "실행해 해당 기관에서 건수가 가장 많다. 계좌 전체 거래는 {tot}건이고 이상거래 비율은 {fr}%다. "
            "최다 상대 계좌는 {cp:copula}며 위험도 평가는 {risk}점({level})이다. "
            "같은 상대에게 소액을 반복 이체하는 형태여서 분할 거래로 판단한다.",
            ["query_transactions", "get_account_profile", "score_account_risk"])),
      ]),

    # ---------------------------------------------------------------- 004
    S(id="mt_str_004", sub="base", ft=3,
      kr="분할 거래 의심 계좌의 거래 조회, 자금 분산 분석, 네트워크 분석 후 STR 작성",
      en="Query a split-transaction account, analyse its dispersion and network, draft the STR",
      vars={"acc": 9000000000039222, "bank": 159},
      why="9000000000039222 sends to 856 distinct accounts with 83 type-3 rows, so the outbound "
          "smurfing scan really returns it.",
      turns=[
        T(kr="계좌 {acc}의 2024년 분할 거래 유형 내역을 금액 순으로 조회해줘.",
          en="List the 2024 split-transaction rows of account {acc}, largest amount first.",
          tool="query_transactions",
          sql=rows("sender_acc = {acc} AND fraud_type = 3 AND date BETWEEN 20240101 AND 20241231"),
          conds=[("sender_acc", "=", 9000000000039222), ("fraud_type", "=", 3),
                 ("date", "BETWEEN", [20240101, 20241231])],
          bind={"n": R(1, "returned_count"), "top_amt": R(1, "result[0].amount")}),
        T(kr="이 계좌의 자금 분산 패턴을 상대 5곳 이상 기준으로 분석해봐.",
          en="Analyse how this account disperses funds, using a threshold of five or more counterparties.",
          tool="detect_smurfing_network",
          args={"account_id": "{acc}", "direction": "outbound", "min_counterparts": 5},
          bind={"cp": R(2, "result[0].counterparty_count"), "stx": R(2, "result[0].total_tx_count"),
                "savg": R(2, "result[0].avg_amount"), "sfrn": R(2, "result[0].fraud_count")}),
        T(kr="거래 네트워크도 분석해줘.",
          en="Analyse the transaction network too.",
          tool="analyze_network", args={"account_id": "{acc}"},
          bind={"nfr": R(3, "fraud_ratio_percent")}),
        T(kr="분할 거래로 STR 작성해줘.",
          en="Draft the STR for split transactions.",
          tool="generate_str",
          args=str_args(3,
            "출금계좌 {acc}(출금기관 {bank})의 2024년 분할 거래 유형 상위 {n}건 중 최대 금액은 {top_amt:,}원이다. "
            "자금 분산 분석 결과 상대 계좌 {cp}곳에 총 {stx}건, 건당 평균 {savg:,.0f}원을 이체했고 "
            "그중 {sfrn}건이 이상거래로 분류됐다. "
            "1단계 네트워크의 이상거래 비율은 {nfr}%다. "
            "소액을 다수 상대에게 쪼개 보내는 형태여서 분할 거래로 판단한다.",
            ["query_transactions", "detect_smurfing_network", "analyze_network"])),
      ]),

    # ---------------------------------------------------------------- 005
    S(id="mt_str_005", sub="base", ft=5,
      kr="거액 입금 후 당일 인출 유형 현황을 본 뒤 계좌 거래 조회와 예측을 거쳐 STR 작성",
      en="Review the same-day-withdrawal type, query the account, predict, draft the STR",
      vars={"acc": 9000000000041932, "bank": 159},
      why="Type 5 has only 243 rows in HOFINET; 9000000000041932 holds 75 of them, the most of any "
          "account.",
      turns=[
        T(kr="거액 입금 후 당일 인출 유형의 전체 현황을 알려줘.",
          en="Show me the overall picture for the same-day-withdrawal-after-large-deposit type.",
          tool="get_fraud_type_summary", args={"fraud_type": 5},
          bind={"t5n": R(1, "total_count"), "t5amt": R(1, "total_amount"),
                "t5bank": R(1, "top_banks[0].bank_id")}),
        T(kr="출금계좌 {acc}의 해당 유형 거래를 금액 순으로 20건 조회해줘.",
          en="List that type's transactions for withdrawal account {acc}, the 20 largest by amount.",
          tool="query_transactions",
          sql=rows("sender_acc = {acc} AND fraud_type = 5"),
          conds=[("sender_acc", "=", 9000000000041932), ("fraud_type", "=", 5)],
          bind={"n": R(2, "returned_count"), "top_amt": R(2, "result[0].amount"),
                "top_date": R(2, "result[0].date"), "media": R(2, "result[0].media_type")}),
        T(kr="첫 번째 거래의 위험 점수를 예측해봐.",
          en="Score the first transaction in that result.",
          tool="predict_fraud", args=predict_args(2), ctx=(2, "result[0].amount", "amount"),
          bind={"score": R(3, "fraud_risk_score")}),
        T(kr="거액 입금 후 당일 인출로 STR을 작성해줘.",
          en="Draft the STR for same-day withdrawal after a large deposit.",
          tool="generate_str",
          args=str_args(5,
            "거액 입금 후 당일 인출 유형은 HOFINET 전체에서 {t5n}건, {t5amt:,}원이고 상위 출금기관은 {t5bank:copula}다. "
            "출금계좌 {acc}(출금기관 {bank})의 해당 유형 상위 {n}건 중 최대 건은 {top_date:date}에 "
            "매체구분 {media} 채널로 이체한 {top_amt:,}원이다. "
            "해당 건의 예측 모델 위험 점수는 {score:copula}다. "
            "거액이 들어온 당일에 같은 규모가 빠져나가는 형태여서 거액 입금 후 당일 인출로 판단한다.",
            ["get_fraud_type_summary", "query_transactions", "predict_fraud"])),
      ]),

    # ---------------------------------------------------------------- 006
    S(id="mt_str_006", sub="base", ft=7,
      kr="심야 대량거래 관련 FIU 참고유형을 확인하고 계좌 거래 조회와 위험도 평가 후 STR 작성",
      en="Look up the FIU reference type for night-time bulk activity, query the account, score it, draft the STR",
      vars={"acc": 9000000000038845, "bank": 159},
      why="9000000000038845 holds 23 of the 35 type-7 rows in HOFINET; every one of them is in "
          "time slot 21.",
      turns=[
        T(kr="심야 시간대 대량 이체와 관련된 FIU 참고유형을 영어 키워드로 찾아줘.",
          en="Find the FIU reference type for bulk transfers at night, searching the English catalog.",
          tool="lookup_fiu_reference_types", args={"keyword": "night"},
          bind={"fiu": R(1, "result[0].description"), "fiu_cat": R(1, "result[0].category")}),
        T(kr="출금계좌 {acc}의 심야/새벽 대량 거래 유형 내역을 날짜 순으로 조회해줘.",
          en="List the late-night bulk transactions of withdrawal account {acc} by date.",
          tool="query_transactions",
          sql=rows("sender_acc = {acc} AND fraud_type = 7", order="date, receiver_acc", limit=25),
          conds=[("sender_acc", "=", 9000000000038845), ("fraud_type", "=", 7)],
          bind={"n": R(2, "total_count"), "slot": R(2, "result[0].time_slot"),
                "amt0": R(2, "result[0].amount"), "d0": R(2, "result[0].date")}),
        T(kr="이 계좌의 위험도를 평가해줘.",
          en="Score this account's risk.",
          tool="score_account_risk", args={"account_id": "{acc}"},
          bind={"risk": R(3, "total_score"), "level": R(3, "risk_level"),
                "night": R(3, "components.nighttime_ratio")}),
        T(kr="심야/새벽 대량 거래로 STR 작성해줘.",
          en="Draft the STR for late-night bulk transactions.",
          tool="generate_str",
          args=str_args(7,
            "출금기관 {bank} 소속 출금계좌 {acc:은는} {d0:date|을를} 시작으로 거래시간대 {slot} 구간에서 "
            "건당 {amt0:,}원 규모의 이체 {n}건을 실행했다. 위험도 평가는 {risk}점({level})이고 "
            "심야 거래 비중 지표는 {night:copula}다. FIU 참고유형 {fiu_cat} 항목 '{fiu}'에 해당한다. "
            "영업시간 외 시간대에 같은 금액이 반복되어 심야/새벽 대량 거래로 판단한다.",
            ["lookup_fiu_reference_types", "query_transactions", "score_account_risk"])),
      ]),

    # ---------------------------------------------------------------- 007
    S(id="mt_str_007", sub="base", ft=1,
      kr="채널별 위험도 분석에서 PC뱅킹 이상거래를 찾아 예측한 뒤 STR 작성",
      en="Channel risk analysis, find the PC-banking fraud, predict, draft the STR",
      vars={},
      why="PC Banking (media_type 1) is the highest-fraud-ratio channel in 2024; the largest "
          "type-1 PC-banking transaction is account 9000000000020857's 300,000,000 KRW transfer.",
      turns=[
        T(kr="2024년 채널별 위험도를 분석해줘.",
          en="Analyse channel risk for 2024.",
          tool="analyze_channel_risk", args={"date_from": 20240101, "date_to": 20241231},
          bind={"ch": R(1, "channel_stats[0].channel_name"),
                "chm": R(1, "channel_stats[0].media_type"),
                "chr": R(1, "channel_stats[0].fraud_ratio_percent")}),
        T(kr="PC뱅킹 채널에서 갑작스러운 거래패턴의 변화 유형 이상거래를 금액 순으로 조회해줘. 2024년 기준이야.",
          en="List the sudden-pattern-change fraud on the PC banking channel in 2024, largest amount first.",
          tool="query_transactions",
          sql=rows("media_type = 1 AND fraud_type = 1 AND date BETWEEN 20240101 AND 20241231",
                   limit=10),
          conds=[("media_type", "=", 1), ("fraud_type", "=", 1),
                 ("date", "BETWEEN", [20240101, 20241231])],
          bind={"n": R(2, "returned_count"), "acc": R(2, "result[0].sender_acc"),
                "bank": R(2, "result[0].sender_bank"), "amt": R(2, "result[0].amount"),
                "date": R(2, "result[0].date")}),
        T(kr="첫 번째 거래의 위험 점수를 예측해줘.",
          en="Score the first transaction in that result.",
          tool="predict_fraud", args=predict_args(2), ctx=(2, "result[0].amount", "amount"),
          bind={"score": R(3, "fraud_risk_score")}),
        T(kr="갑작스러운 거래패턴의 변화로 STR 작성해줘.",
          en="Draft the STR for a sudden change in transaction pattern.",
          tool="generate_str",
          args=str_args(1,
            "2024년 채널 분석에서 이상거래 비율이 가장 높은 채널은 {ch}(매체구분 {chm}, {chr}%)이다. "
            "이 채널의 갑작스러운 거래패턴의 변화 유형 상위 {n}건 중 최대 건은 {date:date}에 "
            "출금기관 {bank} 소속 출금계좌 {acc:이가} 이체한 {amt:,}원이다. 해당 건의 예측 모델 위험 점수는 {score:copula}다. "
            "평소 사용하지 않던 채널에서 거액이 나간 형태여서 갑작스러운 거래패턴의 변화로 판단한다.",
            ["analyze_channel_risk", "query_transactions", "predict_fraud"])),
      ]),

    # ---------------------------------------------------------------- 008
    S(id="mt_str_008", sub="base", ft=2,
      kr="전체 통계와 위험 거래 랭킹을 본 뒤 1순위 거래를 예측해 STR 작성",
      en="Overall statistics, risk ranking, predict the top transaction, draft the STR",
      vars={},
      why="The deterministic ranking puts account 9000000004241908's 6,000,000 KRW transfer first; "
          "that account's labelled fraud is dominated by type 2 (21 of 41 rows).",
      turns=[
        T(kr="전체 거래 통계를 조회해줘.",
          en="Show me the overall transaction statistics.",
          tool="get_statistics",
          bind={"tot": R(1, "summary_statistics.total_tx_count"),
                "frn": R(1, "summary_statistics.fraud_tx_count"),
                "frr": R(1, "summary_statistics.fraud_ratio_percent")}),
        T(kr="표본 1,000건에서 위험도 상위 10건을 랭킹해줘.",
          en="Rank the ten riskiest transactions out of a 1,000-transaction sample.",
          tool="rank_risky_transactions", args={"sample_size": 1000, "top_k": 10},
          bind={"racc": R(2, "results[0].sender_acc"), "ramt": R(2, "results[0].amount"),
                "rscore": R(2, "results[0].fraud_risk_score"), "rdate": R(2, "results[0].date"),
                "rrcv": R(2, "results[0].receiver_acc")}),
        T(kr="1순위 거래를 모델로 다시 예측해봐.",
          en="Re-score the top-ranked transaction with the model.",
          tool="predict_fraud",
          args={"time_slot": R(2, "results[0].time_slot"),
                "sender_bank": R(2, "results[0].sender_bank"),
                "receiver_bank": R(2, "results[0].receiver_bank"),
                "fund_type": R(2, "results[0].fund_type"),
                "media_type": R(2, "results[0].media_type"),
                "amount": R(2, "results[0].amount")},
          ctx=(2, "results[0].amount", "amount"),
          bind={"score": R(3, "fraud_risk_score")}),
        T(kr="신규 수신처 거래 의심으로 STR 작성해줘.",
          en="Draft the STR for a transaction with a new counterparty.",
          tool="generate_str",
          args=str_args(2,
            "HOFINET 전체 거래는 {tot}건이고 이상거래는 {frn}건({frr}%)이다. "
            "위험도 랭킹 1순위는 {rdate:date}에 출금계좌 {racc:이가} 입금계좌 {rrcv:으로로} 이체한 {ramt:,}원이며 "
            "랭킹 점수는 {rscore}, 재예측 점수는 {score:copula}다. "
            "거래 상대가 종전 거래 이력에 없던 계좌여서 신규 수신처 거래로 판단한다.",
            ["get_statistics", "rank_risky_transactions", "predict_fraud"])),
      ]),

    # ---------------------------------------------------------------- 009
    S(id="mt_str_009", sub="base", ft=2,
      kr="기관간 자금 흐름에서 이상거래 비율이 가장 높은 구간을 조회하고 예측해 STR 작성",
      en="Cross-institution flow, query the worst pair, predict, draft the STR",
      vars={},
      why="In 2024Q4 the 151 to 149 leg has the highest fraud ratio (14.29%) among legs with at "
          "least ten transactions; its 2024 fraud rows are all type 2.",
      turns=[
        T(kr="2024년 4분기 기관간 자금 흐름을 거래 10건 이상 기준으로 분석해줘.",
          en="Analyse the 2024Q4 flows between institutions, counting legs with at least ten transactions.",
          tool="analyze_cross_institution_flow",
          args={"date_from": 20241001, "date_to": 20241231, "min_transactions": 10, "limit": 10},
          bind={"sb": R(1, "result[0].sender_institution"), "rb": R(1, "result[0].receiver_institution"),
                "fratio": R(1, "result[0].fraud_ratio_percent"), "ftx": R(1, "result[0].tx_count")}),
        T(kr="출금기관 {sb}에서 입금기관 {rb:으로로} 간 2024년 이상거래를 금액 순으로 조회해줘.",
          en="List the 2024 flagged transactions from institution {sb} to institution {rb}, "
             "largest amount first.",
          tool="query_transactions",
          sql=rows("sender_bank = {sb} AND receiver_bank = {rb} AND is_fraud = 1 "
                   "AND date BETWEEN 20240101 AND 20241231"),
          conds=[("sender_bank", "=", R(1, "result[0].sender_institution")),
                 ("receiver_bank", "=", R(1, "result[0].receiver_institution")),
                 ("is_fraud", "=", 1), ("date", "BETWEEN", [20240101, 20241231])],
          bind={"n": R(2, "returned_count"), "acc": R(2, "result[0].sender_acc"),
                "amt": R(2, "result[0].amount"), "date": R(2, "result[0].date")}),
        T(kr="첫 번째 거래의 위험 점수를 예측해줘.",
          en="Score the first transaction in that result.",
          tool="predict_fraud", args=predict_args(2), ctx=(2, "result[0].amount", "amount"),
          bind={"score": R(3, "fraud_risk_score")}),
        T(kr="신규 수신처 거래로 STR 작성해줘.",
          en="Draft the STR for a transaction with a new counterparty.",
          tool="generate_str",
          args=str_args(2,
            "2024년 4분기 기관간 흐름에서 출금기관 {sb}에서 입금기관 {rb:으로로} 가는 구간의 이상거래 비율이 "
            "{fratio}%로 가장 높고 거래는 {ftx}건이다. 2024년 전체로 보면 이 구간의 이상거래는 {n}건이며 "
            "최대 건은 {date:date}에 출금계좌 {acc:이가} 이체한 {amt:,}원이다. 해당 건의 예측 모델 위험 점수는 {score:copula}다. "
            "이전 거래 이력이 없는 상대 기관으로 자금이 몰려 신규 수신처 거래로 판단한다.",
            ["analyze_cross_institution_flow", "query_transactions", "predict_fraud"])),
      ]),

    # ---------------------------------------------------------------- 010
    S(id="mt_str_010", sub="base", ft=2,
      kr="휴면계좌 재활성화 탐지 후 계좌 프로필과 CTR 분할거래 확인을 거쳐 STR 작성",
      en="Dormant-account reactivation, account profile, CTR structuring check, STR",
      vars={},
      why="With the default thresholds the reactivation scan really returns 9000000000023022 first "
          "(978 dormant days, a 5,000,000 KRW reactivation); its one labelled transaction is type 2.",
      turns=[
        T(kr="180일 이상 휴면 후 500만원 이상으로 재활성화된 계좌를 찾아줘.",
          en="Find accounts dormant for 180 days or more that were reactivated with 5,000,000 KRW or more.",
          tool="detect_dormant_reactivation",
          args={"dormant_days": 180, "min_reactivation_amount": 5000000},
          bind={"dacc": R(1, "result[0].sender_acc"), "ddays": R(1, "result[0].dormant_days"),
                "dlast": R(1, "result[0].last_activity_date"),
                "dre": R(1, "result[0].reactivation_date"),
                "damt": R(1, "result[0].reactivation_amount")}),
        T(kr="가장 오래 휴면했던 계좌 {dacc}의 프로필을 확인해줘.",
          en="Profile account {dacc}, the one dormant the longest.",
          tool="get_account_profile", args={"account_id": "{dacc}"},
          bind={"tot": R(2, "total_count"), "fr": R(2, "fraud_ratio_percent"),
                "tamt": R(2, "total_amount"), "media": R(2, "top_media[0]")}),
        T(kr="재활성화된 2024년 12월에 분할거래 의심 건이 있었는지 CTR 기준으로 확인해줘.",
          en="Check with the CTR structuring rule whether December 2024 shows structuring candidates.",
          tool="detect_ctr_candidates",
          args={"mode": "structuring", "date_from": 20241201, "date_to": 20241231},
          bind={"ctr_n": R(3, "count"), "ctr_acc": R(3, "result[0].sender_acc"),
                "ctr_tx": R(3, "result[0].tx_count")}),
        T(kr="신규 수신처 거래로 STR 작성해줘.",
          en="Draft the STR for a transaction with a new counterparty.",
          tool="generate_str",
          args=str_args(2,
            "출금계좌 {dacc:은는} {dlast:date|을를} 마지막으로 {ddays}일 동안 거래가 없다가 {dre:date}에 {damt:,}원으로 "
            "재활성화됐다. 계좌 전체 거래는 {tot}건, {tamt:,}원이고 이상거래 비율은 {fr}%이며 "
            "주 이체 채널은 {media:copula}다. "
            "같은 달 CTR 분할거래 조회 상위 {ctr_n}건 가운데 최다 건수는 {ctr_acc}의 {ctr_tx}건이다. "
            "장기 휴면 계좌가 종전에 없던 상대와 거래를 재개해 신규 수신처 거래로 판단한다.",
            ["detect_dormant_reactivation", "get_account_profile", "detect_ctr_candidates"])),
      ]),

    # ---------------------------------------------------------------- 011
    S(id="mt_str_011", sub="base", ft=3,
      kr="모니터링 알림 전체 실행 후 동일 금액 반복 계좌를 조회하고 위험도를 평가해 STR 작성",
      en="Run every monitoring rule, query the repeated-amount account, score it, draft the STR",
      vars={},
      why="R003 (repeated identical amounts) really flags 9000000000041188 first in 2024Q4: 202 "
          "transfers of exactly 4,000,000 KRW; the account's labelled fraud is type 3.",
      turns=[
        T(kr="2024년 4분기 거래 모니터링 알림을 전체 규칙으로 실행해줘. 규칙별 3건씩만 보여줘.",
          en="Run every monitoring rule over 2024Q4 and show three hits per rule.",
          tool="detect_monitoring_alerts",
          args={"rule_id": "all", "date_from": 20241001, "date_to": 20241231, "limit": 3},
          bind={"r3acc": R(1, "result.R003.result[0].sender_acc"),
                "r3amt": R(1, "result.R003.result[0].amount"),
                "r3n": R(1, "result.R003.result[0].repeat_count"),
                "r3rcv": R(1, "result.R003.result[0].receiver_count")}),
        T(kr="R003 동일 금액 반복 알림에 걸린 계좌 {r3acc}의 2024년 4분기 거래를 금액 순으로 조회해줘.",
          en="List the 2024Q4 transactions of account {r3acc}, the one R003 flagged, largest amount first.",
          tool="query_transactions",
          sql=rows("sender_acc = {r3acc} AND date BETWEEN 20241001 AND 20241231"),
          conds=[("sender_acc", "=", R(1, "result.R003.result[0].sender_acc")),
                 ("date", "BETWEEN", [20241001, 20241231])],
          bind={"n": R(2, "returned_count"), "bank": R(2, "result[0].sender_bank")}),
        T(kr="이 계좌의 위험도를 평가해줘.",
          en="Score this account's risk.",
          tool="score_account_risk", args={"account_id": R(1, "result.R003.result[0].sender_acc")},
          bind={"risk": R(3, "total_score"), "level": R(3, "risk_level")}),
        T(kr="분할 거래로 STR 작성해줘.",
          en="Draft the STR for split transactions.",
          tool="generate_str",
          args=str_args(3,
            "모니터링 R003(동일 금액 반복) 알림에서 출금계좌 {r3acc:이가} {r3amt:,}원을 {r3n}회, "
            "상대 계좌 {r3rcv}곳에 반복 이체한 것으로 나타났다. "
            "이 계좌(출금기관 {bank})의 2024년 4분기 거래 상위 {n}건을 확인했고 위험도 평가는 {risk}점({level})이다. "
            "같은 금액을 다수 상대에게 반복해 보내는 형태여서 분할 거래로 판단한다.",
            ["detect_monitoring_alerts", "query_transactions", "score_account_risk"])),
      ]),

    # ---------------------------------------------------------------- 012
    S(id="mt_str_012", sub="base", ft=7,
      kr="분기 트렌드와 기간 비교로 급증 구간을 찾은 뒤 심야 대량거래를 조회해 STR 작성",
      en="Quarterly trend, period comparison, query the night-time bulk transactions, draft the STR",
      vars={"acc": 9000000004242392, "bank": 159},
      why="9000000004242392 holds 7 type-7 rows and 2,626 of its transactions are in the 21 slot, "
          "so a night-time reading of this account is grounded.",
      turns=[
        T(kr="분기별 이상거래 트렌드를 분석해줘.",
          en="Analyse the quarterly fraud trend.",
          tool="get_trend_analysis", args={"unit": "quarterly"},
          bind={"pn": R(1, "period_count"), "lastq": R(1, "result[13].period"),
                "lastr": R(1, "result[13].fraud_ratio_percent")}),
        T(kr="2024년 3분기와 4분기를 비교해줘.",
          en="Compare 2024Q3 with 2024Q4.",
          tool="compare_periods",
          args={"period1_start": 20240701, "period1_end": 20240930,
                "period2_start": 20241001, "period2_end": 20241231},
          bind={"dfr": R(2, "delta.fraud_count_pct"), "dcnt": R(2, "delta.total_count_pct")}),
        T(kr="출금계좌 {acc}의 심야/새벽 대량 거래 유형 내역을 날짜 순으로 조회해줘.",
          en="List the late-night bulk transactions of withdrawal account {acc} by date.",
          tool="query_transactions",
          sql=rows("sender_acc = {acc} AND fraud_type = 7", order="date, amount DESC", limit=10),
          conds=[("sender_acc", "=", 9000000004242392), ("fraud_type", "=", 7)],
          bind={"n": R(3, "total_count"), "slot": R(3, "result[0].time_slot"),
                "d0": R(3, "result[0].date"), "amt": R(3, "result[0].amount")}),
        T(kr="심야/새벽 대량 거래로 STR 작성해줘.",
          en="Draft the STR for late-night bulk transactions.",
          tool="generate_str",
          args=str_args(7,
            "분기 트렌드 {pn}개 구간에서 마지막 분기 {lastq}의 이상거래 비율은 {lastr}%다. "
            "2024년 3분기 대비 4분기는 거래 건수가 {dcnt}%, 이상거래 건수가 {dfr}% 변화했다. "
            "출금기관 {bank} 소속 출금계좌 {acc:은는} 거래시간대 {slot} 구간에서 심야/새벽 대량 거래 유형 {n}건을 "
            "실행했고 {d0:date}의 {amt:,}원이 가장 크다. "
            "영업시간 외 시간대에 대량 이체가 몰려 심야/새벽 대량 거래로 판단한다.",
            ["get_trend_analysis", "compare_periods", "query_transactions"])),
      ]),

    # ---------------------------------------------------------------- 013
    S(id="mt_str_013", sub="base", ft=1,
      kr="입금계좌 자금 유입 분석과 수집 패턴, 계좌 위험 패턴 점수를 거쳐 STR 작성",
      en="Receiving-account inflow, collection pattern, graph risk score, STR",
      vars={"racc": 9000000004371903},
      why="9000000004371903 receives from 123 distinct senders with 103 flagged inbound "
          "transactions, the highest fraud count among receiving accounts.",
      turns=[
        T(kr="입금계좌 {racc}의 자금 유입 패턴을 분석해줘.",
          en="Analyse the inflow pattern of receiving account {racc}.",
          tool="get_receiving_account_profile", args={"account_id": "{racc}"},
          bind={"snd": R(1, "unique_senders"), "sbank": R(1, "unique_sender_banks"),
                "rtx": R(1, "total_txns"), "rfr": R(1, "fraud_ratio_percent"),
                "ramt": R(1, "total_amount"), "top_s": R(1, "top_senders[0].sender_id")}),
        T(kr="이 계좌로 들어오는 자금 수집 패턴을 상대 20곳 이상 기준으로 분석해봐.",
          en="Analyse the collection pattern into this account, with a threshold of twenty or more counterparties.",
          tool="detect_smurfing_network",
          args={"account_id": "{racc}", "direction": "inbound", "min_counterparts": 20},
          bind={"cp": R(2, "result[0].counterparty_count"),
                "cavg": R(2, "result[0].avg_amount")}),
        T(kr="이 계좌의 그래프 기반 위험 점수도 계산해줘.",
          en="Compute this account's graph-based risk score as well.",
          tool="detect_aml_patterns", args={"pattern_type": "risk_score", "account_id": "{racc}"},
          bind={"grisk": R(3, "risk_score"),
                "gnb": R(3, "components.neighbor_fraud_ratio_percent")}),
        T(kr="갑작스러운 거래패턴의 변화로 STR 작성해줘.",
          en="Draft the STR for a sudden change in transaction pattern.",
          tool="generate_str",
          args=str_args(1,
            "입금계좌 {racc:은는} 송금 계좌 {snd}곳, 송금 기관 {sbank}곳에서 이체 {rtx}건, {ramt:,}원을 받았고 "
            "이상거래 비율은 {rfr}%다. 최다 송금 계좌는 {top_s:copula}다. "
            "자금 수집 분석에서 상대 {cp}곳, 건당 평균 {cavg:,.0f}원이 확인된다. "
            "그래프 위험 점수는 {grisk:copula}고 이웃 계좌 이상거래 비율은 {gnb}%다. "
            "유입 상대와 규모가 종전과 달라져 갑작스러운 거래패턴의 변화로 판단한다.",
            ["get_receiving_account_profile", "detect_smurfing_network", "detect_aml_patterns"])),
      ]),
]
