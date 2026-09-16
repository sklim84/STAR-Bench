"""Scenarios 14 to 50 of the multi-turn rebuild. See `scenarios.py` for the conventions."""

from __future__ import annotations

from .scenarios import DRAFT_023, DRAFT_046, draft_text, predict_args, rows, str_args
from .spec import Ref as R
from .spec import Scenario as S
from .spec import Turn as T

SCENARIOS_B: list[S] = [

    # ---------------------------------------------------------------- 014
    S(id="mt_str_014", sub="missing_parameter", ft=1,
      kr="계좌번호 없이 분석 요청, 되묻기, 계좌 지정 후 조회·예측을 거쳐 STR 작성",
      en="Analysis requested with no account, clarification, then query, prediction and STR",
      vars={"acc": 9000000000019720, "bank": 134},
      why="9000000000019720 carries 20 type-1 rows at institution 134, enough for a listing and a "
          "prediction without being one of the very large accounts.",
      turns=[
        T(kr="갑작스러운 거래패턴의 변화가 의심되는 거래가 있는데 분석 좀 해줘.",
          en="I have transactions that look like a sudden change in pattern. Can you analyse them?",
          clarify=True,
          point_kr="계좌번호가 없어 어떤 조회도 특정할 수 없다",
          point_en="no account is given, so no query can be aimed at anything"),
        T(kr="출금계좌 {acc:copula}야. 이 계좌의 갑작스러운 거래패턴의 변화 유형 거래를 금액 순으로 조회해줘.",
          en="The account is {acc}. List its sudden-pattern-change transactions, largest amount first.",
          tool="query_transactions",
          sql=rows("sender_acc = {acc} AND fraud_type = 1"),
          conds=[("sender_acc", "=", 9000000000019720), ("fraud_type", "=", 1)],
          bind={"n": R(2, "returned_count"), "amt": R(2, "result[0].amount"),
                "date": R(2, "result[0].date"), "rcv": R(2, "result[0].receiver_acc")}),
        T(kr="첫 번째 거래의 위험 점수를 예측해봐.",
          en="Score the first transaction in that result.",
          tool="predict_fraud", args=predict_args(2), ctx=(2, "result[0].amount", "amount"),
          bind={"score": R(3, "fraud_risk_score")}),
        T(kr="갑작스러운 거래패턴의 변화로 STR 작성해줘.",
          en="Draft the STR for a sudden change in transaction pattern.",
          tool="generate_str",
          args=str_args(1,
            "출금계좌 {acc}(출금기관 {bank})의 갑작스러운 거래패턴의 변화 유형 이상거래 상위 "
            "{n}건을 확인했다. 최대 건은 {date:date}에 입금계좌 {rcv:으로로} 이체한 {amt:,}원이고 "
            "예측 모델 위험 점수는 {score:copula}다. 거래 규모가 평소와 달라 갑작스러운 거래패턴의 "
            "변화로 판단한다.",
            "The top {n} sudden-change-in-transaction-pattern rows of withdrawal account {acc} "
            "(institution {bank}) were reviewed. The largest is {amt:,} KRW sent to receiving "
            "account {rcv} on {date:date}, with a model risk score of {score}. The size of the "
            "transfer departs from the account's usual level, so this is judged a sudden change in "
            "transaction pattern.",
            ["query_transactions", "predict_fraud"])),
      ]),

    # ---------------------------------------------------------------- 015
    S(id="mt_str_015", sub="missing_parameter", ft=4,
      kr="지시 대상이 불명확한 조회 요청, 되묻기, 계좌 지정 후 예측과 FIU 참조를 거쳐 STR 작성",
      en="Query request with an unresolved referent, clarification, then prediction, FIU lookup and STR",
      vars={"acc": 9000000004242077, "bank": 157},
      why="9000000004242077 has 91 type-4 rows, 62 of them in 2024, so the 2024 listing is not empty.",
      turns=[
        T(kr="그 계좌 거래 내역 좀 뽑아줘. 다중거래의 동시 요청이 의심돼.",
          en="Pull that account's transactions. I suspect concurrent multiple transactions.",
          clarify=True,
          point_kr="'그 계좌'가 가리키는 대상이 대화에 없다",
          point_en="'that account' refers to nothing in the conversation so far"),
        T(kr="출금계좌 {acc:copula}야. 2024년 다중거래의 동시 요청 유형 거래를 금액 순으로 조회해줘.",
          en="The account is {acc}. List its 2024 concurrent-multiple-transaction rows, largest amount first.",
          tool="query_transactions",
          sql=rows("sender_acc = {acc} AND fraud_type = 4 AND date BETWEEN 20240101 AND 20241231"),
          conds=[("sender_acc", "=", 9000000004242077), ("fraud_type", "=", 4),
                 ("date", "BETWEEN", [20240101, 20241231])],
          bind={"n": R(2, "returned_count"), "amt": R(2, "result[0].amount"),
                "date": R(2, "result[0].date")}),
        T(kr="첫 번째 거래를 예측해봐.",
          en="Score the first transaction.",
          tool="predict_fraud", args=predict_args(2), ctx=(2, "result[0].amount", "amount"),
          bind={"score": R(3, "fraud_risk_score")}),
        T(kr="분할 이체와 관련된 FIU 참고유형도 영어 키워드로 확인해줘.",
          en="Also look up the FIU reference type for split transfers, searching the English catalog.",
          tool="lookup_fiu_reference_types", args={"keyword": "split"},
          bind={"fiu": R(4, "result[0].description")}),
        T(kr="다중거래의 동시 요청으로 STR 작성해줘.",
          en="Draft the STR for concurrent multiple transactions.",
          tool="generate_str",
          args=str_args(4,
            "출금계좌 {acc}(출금기관 {bank})의 2024년 다중거래의 동시 요청 유형 이상거래 상위 "
            "{n}건을 확인했다. 최대 건은 {date:date}의 {amt:,}원이고 예측 모델 위험 점수는 "
            "{score:copula}다. FIU 참고유형 가운데 {fiu:ko|과와} 형태가 겹친다. 같은 날 다수 이체가 "
            "동시에 요청되어 다중거래의 동시 요청으로 판단한다.",
            "The top {n} concurrent-multiple-transaction rows of 2024 for withdrawal account {acc} "
            "(institution {bank}) were reviewed. The largest is {amt:,} KRW on {date:date}, with a "
            "model risk score of {score}. It overlaps with the FIU reference type '{fiu}'. Several "
            "transfers were requested together on one day, so this is judged a concurrent multiple "
            "transaction request.",
            ["query_transactions", "predict_fraud", "lookup_fiu_reference_types"])),
      ]),

    # ---------------------------------------------------------------- 016
    S(id="mt_str_016", sub="missing_parameter", ft=2,
      kr="기관 보고서 후 기간 없는 비교 요청, 되묻기, 기간 지정 비교와 거래 조회를 거쳐 STR 작성",
      en="Institution report, comparison requested without dates, clarification, comparison, query, STR",
      vars={"bank": 151},
      why="Institution 151 sends the type-2 accounts 9000000000027664 and 9000000004239253, so its "
          "report and a 2024 second-half listing both carry new-counterparty fraud.",
      turns=[
        T(kr="출금기관 {bank}의 이상거래 현황 보고서를 만들어줘.",
          en="Build the fraud report for institution {bank}.",
          tool="get_institution_report", args={"bank_id": "{bank}"},
          bind={"otot": R(1, "outbound.total_count"), "ofr": R(1, "outbound.fraud_count"),
                "ofrr": R(1, "outbound.fraud_ratio_percent"),
                "ttype": R(1, "fraud_type_distribution[0].type_name")}),
        T(kr="이 기관 거래를 두 기간으로 나눠서 비교해줘.",
          en="Compare this institution's activity across two periods.",
          clarify=True,
          point_kr="compare_periods의 필수 인자인 두 기간의 시작일과 종료일이 없다",
          point_en="compare_periods needs the start and end of both periods and neither is given"),
        T(kr="2024년 상반기와 하반기로 비교해줘.",
          en="Compare the first half of 2024 with the second half.",
          tool="compare_periods",
          args={"period1_start": 20240101, "period1_end": 20240630,
                "period2_start": 20240701, "period2_end": 20241231},
          bind={"dfr": R(3, "delta.fraud_count_pct"), "dppt": R(3, "delta.fraud_ratio_ppt")}),
        T(kr="출금기관 {bank}의 2024년 하반기 신규 수신처 거래 유형 이상거래를 금액 순으로 조회해줘.",
          en="List institution {bank}'s new-counterparty fraud in the second half of 2024, "
             "largest amount first.",
          tool="query_transactions",
          sql=rows("sender_bank = {bank} AND fraud_type = 2 AND date BETWEEN 20240701 AND 20241231"),
          conds=[("sender_bank", "=", 151), ("fraud_type", "=", 2),
                 ("date", "BETWEEN", [20240701, 20241231])],
          bind={"n": R(4, "returned_count"), "acc": R(4, "result[0].sender_acc"),
                "amt": R(4, "result[0].amount"), "date": R(4, "result[0].date")}),
        T(kr="신규 수신처 거래 의심으로 STR 작성해줘.",
          en="Draft the STR for transactions with new counterparties.",
          tool="generate_str",
          args=str_args(2,
            "출금기관 {bank}의 출금 거래는 {otot}건이고 이상거래는 {ofr}건({ofrr}%)이며 가장 많은 "
            "유형은 {ttype:copula}다. 2024년 상반기 대비 하반기에 이상거래 건수는 {dfr}%, 이상거래 "
            "비율은 {dppt}%p 변화했다. 하반기 신규 수신처 거래 유형 상위 {n}건 가운데 최대 건은 "
            "{date:date}에 출금계좌 {acc:이가} 이체한 {amt:,}원이다. 거래 이력이 없던 상대로 자금이 "
            "이동해 신규 수신처 거래로 판단한다.",
            "Institution {bank} sends {otot} transactions, {ofr} of them flagged ({ofrr}%), and its "
            "most common type is {ttype}. Between the first and the second half of 2024 the flagged "
            "count moved by {dfr}% and the flagged ratio by {dppt} percentage points. Among the top "
            "{n} new-counterparty rows of the second half the largest is {amt:,} KRW sent by "
            "withdrawal account {acc} on {date:date}. Funds moved to a counterparty with no earlier "
            "history, so this is judged a transaction with a new counterparty.",
            ["get_institution_report", "compare_periods", "query_transactions"])),
      ]),

    # ---------------------------------------------------------------- 017
    S(id="mt_str_017", sub="missing_parameter", ft=3,
      kr="방향 없는 스머핑 요청, 되묻기, 유입 방향 분석과 funnel 점검을 거쳐 STR 작성",
      en="Smurfing requested without a direction, clarification, inbound analysis, funnel check, STR",
      vars={"racc": 9000000004424162},
      why="9000000004424162 receives 361 transfers from six senders, 44 of them labelled type 3, "
          "which is the split-transaction collection pattern the scenario describes.",
      turns=[
        T(kr="계좌 {racc}의 스머핑 패턴을 분석해줘.",
          en="Analyse the smurfing pattern of account {racc}.",
          clarify=True,
          point_kr="detect_smurfing_network의 필수 인자 direction(inbound/outbound)이 없다",
          point_en="detect_smurfing_network needs its required direction argument"),
        T(kr="이 계좌로 들어오는 방향, 즉 inbound를 상대 5곳 이상 기준으로 분석해줘.",
          en="Analyse the inbound direction, with a threshold of five or more counterparties.",
          tool="detect_smurfing_network",
          args={"account_id": "{racc}", "direction": "inbound", "min_counterparts": 5},
          bind={"cp": R(2, "result[0].counterparty_count"), "stx": R(2, "result[0].total_tx_count"),
                "sfr": R(2, "result[0].fraud_count"), "savg": R(2, "result[0].avg_amount")}),
        T(kr="입금 상대 3곳 이상, 출금 상대 5곳 이하 기준으로 funnel 패턴 계좌도 찾아줘.",
          en="Also scan for funnel accounts with at least three inflow counterparties and at most "
             "five outflow counterparties.",
          tool="detect_aml_patterns",
          args={"pattern_type": "funnel", "min_inflow": 3, "max_outflow": 5},
          bind={"fn": R(3, "count")}),
        T(kr="분할 거래로 STR 작성해줘.",
          en="Draft the STR for split transactions.",
          tool="generate_str",
          args=str_args(3,
            "입금계좌 {racc:은는} 송금 계좌 {cp}곳에서 {stx}건을 받았고 그중 {sfr}건이 이상거래로 "
            "분류됐다. 건당 평균 금액은 {savg:,.0f}원이다. 같은 기준의 funnel 스캔에서는 {fn}개 "
            "계좌가 나왔고 이 계좌는 포함되지 않아 수집 후 재이체 형태는 확인되지 않는다. 소수 "
            "송금인이 소액을 반복 이체해 모아 주는 형태여서 분할 거래로 판단한다.",
            "Receiving account {racc} took {stx} transfers from {cp} sending accounts, {sfr} of "
            "them flagged, at {savg:,.0f} KRW per transfer on average. A funnel scan on the same "
            "threshold returned {fn} accounts and this one is not among them, so no "
            "collect-and-forward shape is present. A few senders transfer small amounts repeatedly "
            "into one account, so this is judged a split transaction.",
            ["detect_smurfing_network", "detect_aml_patterns"])),
      ]),

    # ---------------------------------------------------------------- 018
    S(id="mt_str_018", sub="missing_parameter", ft=1,
      kr="기관번호 없는 보고서 요청, 되묻기, 기관 보고서와 거래 조회를 거쳐 STR 작성",
      en="Institution report requested without an id, clarification, report, query, STR",
      vars={"bank": 134},
      why="Institution 134 has 86 type-1 rows in 2024, so its report and the 2024 listing both "
          "support the sudden-pattern-change reading.",
      turns=[
        T(kr="금융회사 하나 이상거래 보고서를 만들어줘.",
          en="Build me the fraud report for a financial institution.",
          clarify=True,
          point_kr="get_institution_report의 필수 인자 bank_id가 없다",
          point_en="get_institution_report needs its required bank_id"),
        T(kr="출금기관 {bank:으로로} 해줘.",
          en="Use institution {bank}.",
          tool="get_institution_report", args={"bank_id": "{bank}"},
          bind={"otot": R(2, "outbound.total_count"), "ofr": R(2, "outbound.fraud_count"),
                "ofrr": R(2, "outbound.fraud_ratio_percent")}),
        T(kr="이 기관의 2024년 갑작스러운 거래패턴의 변화 유형 이상거래를 금액 순으로 조회해줘.",
          en="List this institution's 2024 sudden-pattern-change fraud, largest amount first.",
          tool="query_transactions",
          sql=rows("sender_bank = {bank} AND fraud_type = 1 AND date BETWEEN 20240101 AND 20241231"),
          conds=[("sender_bank", "=", 134), ("fraud_type", "=", 1),
                 ("date", "BETWEEN", [20240101, 20241231])],
          bind={"n": R(3, "returned_count"), "acc": R(3, "result[0].sender_acc"),
                "amt": R(3, "result[0].amount"), "date": R(3, "result[0].date"),
                "slot": R(3, "result[0].time_slot")}),
        T(kr="갑작스러운 거래패턴의 변화로 STR 작성해줘.",
          en="Draft the STR for a sudden change in transaction pattern.",
          tool="generate_str",
          args=str_args(1,
            "출금기관 {bank}의 출금 거래 {otot}건 가운데 이상거래는 {ofr}건({ofrr}%)이다. 2024년 "
            "갑작스러운 거래패턴의 변화 유형 상위 {n}건 중 최대 건은 {date:date} 거래시간대 {slot} "
            "구간에 출금계좌 {acc:이가} 이체한 {amt:,}원이다. 기관 평균을 크게 벗어난 금액이 한 "
            "계좌에서 나가 갑작스러운 거래패턴의 변화로 판단한다.",
            "Of the {otot} transactions institution {bank} sends, {ofr} are flagged ({ofrr}%). "
            "Among the top {n} sudden-change rows of 2024 the largest is {amt:,} KRW sent by "
            "withdrawal account {acc} on {date:date} in time slot {slot}. An amount far above the "
            "institution's average left a single account, so this is judged a sudden change in "
            "transaction pattern.",
            ["get_institution_report", "query_transactions"])),
      ]),

    # ---------------------------------------------------------------- 019
    S(id="mt_str_019", sub="missing_parameter", ft=4,
      kr="유형을 지정하지 않은 상세 요청, 되묻기, 유형 현황과 거래 조회를 거쳐 STR 작성",
      en="Detail requested without naming a type, clarification, type summary, query, STR",
      vars={"bank": 147},
      why="Institution 147 holds 812 of the 929 type-4 rows, so the type summary really points at it.",
      turns=[
        T(kr="전체 거래 통계를 보여줘.",
          en="Show me the overall transaction statistics.",
          tool="get_statistics",
          bind={"tot": R(1, "summary_statistics.total_tx_count"),
                "frn": R(1, "summary_statistics.fraud_tx_count")}),
        T(kr="이 중 한 유형의 상세 현황을 자세히 봐줘.",
          en="Take a closer look at one of these types.",
          clarify=True,
          point_kr="get_fraud_type_summary의 필수 인자 fraud_type을 어느 유형으로 할지 정해지지 않았다",
          point_en="get_fraud_type_summary needs a fraud_type and none of the six has been picked"),
        T(kr="다중거래의 동시 요청 유형으로 해줘.",
          en="Use the concurrent multiple transactions type.",
          tool="get_fraud_type_summary", args={"fraud_type": 4},
          bind={"t4n": R(3, "total_count"), "t4amt": R(3, "total_amount"),
                "t4bank": R(3, "top_banks[0].bank_id"), "t4bn": R(3, "top_banks[0].count")}),
        T(kr="출금기관 {bank}의 2024년 해당 유형 거래를 금액 순으로 조회해줘.",
          en="List institution {bank}'s transactions of that type in 2024, largest amount first.",
          tool="query_transactions",
          sql=rows("sender_bank = {bank} AND fraud_type = 4 AND date BETWEEN 20240101 AND 20241231"),
          conds=[("sender_bank", "=", 147), ("fraud_type", "=", 4),
                 ("date", "BETWEEN", [20240101, 20241231])],
          bind={"n": R(4, "returned_count"), "acc": R(4, "result[0].sender_acc"),
                "amt": R(4, "result[0].amount"), "date": R(4, "result[0].date")}),
        T(kr="다중거래의 동시 요청으로 STR 작성해줘.",
          en="Draft the STR for concurrent multiple transactions.",
          tool="generate_str",
          args=str_args(4,
            "HOFINET 전체 거래 {tot}건 가운데 이상거래는 {frn}건이다. 다중거래의 동시 요청 유형은 "
            "{t4n}건, {t4amt:,}원이고 출금기관 {t4bank:이가} {t4bn}건으로 가장 많다. 출금기관 "
            "{bank}의 2024년 해당 유형 상위 {n}건 중 최대 건은 {date:date}에 출금계좌 {acc:이가} "
            "이체한 {amt:,}원이다. 같은 날 같은 계좌에서 다수 이체가 동시에 요청되어 다중거래의 "
            "동시 요청으로 판단한다.",
            "Of the {tot} transactions in HOFINET, {frn} are flagged. The "
            "concurrent-multiple-transaction type covers {t4n} rows worth {t4amt:,} KRW, and "
            "withdrawal institution {t4bank} leads it with {t4bn}. Among the top {n} rows of that "
            "type at institution {bank} in 2024 the largest is {amt:,} KRW sent by withdrawal "
            "account {acc} on {date:date}. Several transfers were requested together from one "
            "account on one day, so this is judged a concurrent multiple transaction request.",
            ["get_statistics", "get_fraud_type_summary", "query_transactions"])),
      ]),

    # ---------------------------------------------------------------- 020
    S(id="mt_str_020", sub="missing_parameter", ft=1,
      kr="용어 확인 후 패턴 유형 없는 탐지 요청, 되묻기, 레이어링 점검과 계좌 조회를 거쳐 STR 작성",
      en="Glossary, detection requested without a pattern type, clarification, layering check, query, STR",
      vars={"acc": 9000000004235447, "bank": 134},
      why="9000000004235447 has 19 type-1 rows at institution 134. The layering scan is kept "
          "because its documented empty answer is the point of the turn: HOFINET's transfer graph "
          "is acyclic and its longest fraud chain is two transfers.",
      turns=[
        T(kr="AML 용어집의 Layering 항목이 무슨 뜻인지 설명해줘.",
          en="Explain what layering means.",
          tool="get_aml_glossary", args={"term": "Layering"},
          bind={"gdef": R(1, "definition")}),
        T(kr="그러면 AML 패턴 탐지를 해줘.",
          en="Then run AML pattern detection.",
          clarify=True,
          point_kr="detect_aml_patterns의 필수 인자 pattern_type이 없다",
          point_en="detect_aml_patterns needs its required pattern_type"),
        T(kr="3단계 이상 레이어링 패턴을 탐지해줘.",
          en="Detect layering chains of three steps or more.",
          tool="detect_aml_patterns", args={"pattern_type": "layering", "min_layers": 3},
          bind={"ln": R(3, "count"), "lnotice": R(3, "notice")},
          point_kr="HOFINET에서 3단계 레이어링은 구조적으로 발생하지 않으며 도구가 그 사실을 답한다",
          point_en="three-step layering cannot occur in HOFINET and the tool says so"),
        T(kr="출금계좌 {acc}의 갑작스러운 거래패턴의 변화 유형 거래를 금액 순으로 조회해줘.",
          en="List the sudden-pattern-change transactions of account {acc}, largest amount first.",
          tool="query_transactions",
          sql=rows("sender_acc = {acc} AND fraud_type = 1"),
          conds=[("sender_acc", "=", 9000000004235447), ("fraud_type", "=", 1)],
          bind={"n": R(4, "returned_count"), "amt": R(4, "result[0].amount"),
                "date": R(4, "result[0].date"), "media": R(4, "result[0].media_type")}),
        T(kr="갑작스러운 거래패턴의 변화로 STR 작성해줘.",
          en="Draft the STR for a sudden change in transaction pattern.",
          tool="generate_str",
          args=str_args(1,
            "레이어링은 {gdef:ko}. 3단계 이상 레이어링 탐지 결과는 {ln}건으로, {lnotice:ko}. "
            "출금계좌 {acc}(출금기관 {bank})의 갑작스러운 거래패턴의 변화 유형 이상거래 상위 {n}건 "
            "중 최대 건은 {date:date}에 매체구분 {media} 채널로 이체한 {amt:,}원이다. 다단계 분산은 "
            "확인되지 않지만 단일 계좌의 거래 규모 변화가 커 갑작스러운 거래패턴의 변화로 판단한다.",
            "Layering is defined as follows. {gdef} The scan for layering of three or more steps "
            "returned {ln} matches. {lnotice} Among the top {n} sudden-change rows of withdrawal "
            "account {acc} (institution {bank}) the largest is {amt:,} KRW sent over media type "
            "{media} on {date:date}. No multi-step dispersion is present, but the single account's "
            "transaction size changed sharply, so this is judged a sudden change in transaction "
            "pattern.",
            ["get_aml_glossary", "detect_aml_patterns", "query_transactions"])),
      ]),

    # ---------------------------------------------------------------- 021
    S(id="mt_str_021", sub="missing_parameter", ft=3,
      kr="모드 없는 CTR 요청, 되묻기, 분할거래 탐지와 위험도 평가를 거쳐 STR 작성",
      en="CTR requested without a mode, clarification, structuring detection, risk score, STR",
      vars={},
      why="The 2023 structuring scan really returns 9000000004243626 first: 93 same-day transfers "
          "totalling 103,870,000 KRW with a 5,000,000 KRW maximum, which is the structuring shape.",
      turns=[
        T(kr="CTR 관련해서 2023년 거래를 확인해줘.",
          en="Check the 2023 transactions against the CTR rules.",
          clarify=True,
          point_kr="detect_ctr_candidates의 필수 인자 mode(high_value/structuring)가 없다",
          point_en="detect_ctr_candidates needs its required mode"),
        T(kr="structuring 의심 건으로 탐지해줘.",
          en="Detect the structuring candidates.",
          tool="detect_ctr_candidates",
          args={"mode": "structuring", "date_from": 20230101, "date_to": 20231231},
          bind={"cacc": R(2, "result[0].sender_acc"), "cdate": R(2, "result[0].date"),
                "ctx_n": R(2, "result[0].tx_count"), "camt": R(2, "result[0].total_amount"),
                "cmax": R(2, "result[0].max_single_amount"), "cthr": R(2, "threshold")}),
        T(kr="1순위로 나온 계좌의 위험도를 평가해줘.",
          en="Score the risk of the account that came out first.",
          tool="score_account_risk", args={"account_id": R(2, "result[0].sender_acc")},
          ctx=(2, "result[0].sender_acc", "account_id"),
          bind={"risk": R(3, "total_score"), "level": R(3, "risk_level"),
                "cnt": R(3, "total_count")}),
        T(kr="분할 거래로 STR 작성해줘.",
          en="Draft the STR for split transactions.",
          tool="generate_str",
          args=str_args(3,
            "CTR 구조화 기준({cthr:,}원)으로 2023년을 보면 출금계좌 {cacc:이가} {cdate:date} "
            "하루에 {ctx_n}건, 합계 {camt:,}원을 이체했고 단건 최대는 {cmax:,}원이다. 이 계좌의 "
            "전체 거래는 {cnt}건이고 위험도 평가는 {risk}점({level})이다. 보고 기준 미만으로 금액을 "
            "쪼개 같은 날 반복 이체한 형태여서 분할 거래로 판단한다.",
            "Under the CTR structuring threshold of {cthr:,} KRW, in 2023 withdrawal account {cacc} "
            "made {ctx_n} transfers on {cdate:date} totalling {camt:,} KRW, the largest single one "
            "{cmax:,} KRW. The account has {cnt} transactions in all and a behavioural risk score "
            "of {risk} ({level}). Amounts were split below the reporting threshold and repeated on "
            "one day, so this is judged a split transaction.",
            ["detect_ctr_candidates", "score_account_risk"])),
      ]),

    # ---------------------------------------------------------------- 022
    S(id="mt_str_022", sub="missing_parameter", ft=2,
      kr="기간 없는 비교 요청, 되묻기, 연도 비교와 거래 조회를 거쳐 STR 작성",
      en="Comparison requested without periods, clarification, year comparison, query, STR",
      vars={},
      why="2024 has 1,424 type-2 rows in the second half alone, so the year comparison and the "
          "listing are both grounded.",
      turns=[
        T(kr="이상거래가 급증한 것 같아. 기간을 나눠서 비교해줘.",
          en="Fraud looks like it jumped. Compare two periods for me.",
          clarify=True,
          point_kr="compare_periods의 필수 인자인 두 기간의 시작일과 종료일이 없다",
          point_en="compare_periods needs the start and end of both periods"),
        T(kr="2023년 전체와 2024년 전체를 비교해줘.",
          en="Compare the whole of 2023 with the whole of 2024.",
          tool="compare_periods",
          args={"period1_start": 20230101, "period1_end": 20231231,
                "period2_start": 20240101, "period2_end": 20241231},
          bind={"f1": R(2, "period1.fraud_count"), "f2": R(2, "period2.fraud_count"),
                "dfr": R(2, "delta.fraud_count_pct")}),
        T(kr="2024년 하반기 신규 수신처 거래 유형 이상거래를 금액 순으로 조회해줘.",
          en="List the new-counterparty fraud in the second half of 2024, largest amount first.",
          tool="query_transactions",
          sql=rows("fraud_type = 2 AND date BETWEEN 20240701 AND 20241231"),
          conds=[("fraud_type", "=", 2), ("date", "BETWEEN", [20240701, 20241231])],
          bind={"n": R(3, "returned_count"), "acc": R(3, "result[0].sender_acc"),
                "amt": R(3, "result[0].amount"), "date": R(3, "result[0].date"),
                "rcv": R(3, "result[0].receiver_acc"), "bank": R(3, "result[0].sender_bank")}),
        T(kr="신규 수신처 거래로 STR 작성해줘.",
          en="Draft the STR for transactions with new counterparties.",
          tool="generate_str",
          args=str_args(2,
            "2023년 이상거래는 {f1}건, 2024년은 {f2}건으로 {dfr}% 변화했다. 2024년 하반기 신규 "
            "수신처 거래 유형 상위 {n}건 중 최대 건은 {date:date}에 출금기관 {bank} 소속 출금계좌 "
            "{acc:이가} 입금계좌 {rcv:으로로} 이체한 {amt:,}원이다. 거래 이력이 없던 상대로 거액이 "
            "이동해 신규 수신처 거래로 판단한다.",
            "Flagged transactions numbered {f1} in 2023 and {f2} in 2024, a change of {dfr}%. Among "
            "the top {n} new-counterparty rows of the second half of 2024 the largest is {amt:,} "
            "KRW sent on {date:date} by withdrawal account {acc} at institution {bank} to receiving "
            "account {rcv}. A large amount moved to a counterparty with no earlier history, so this "
            "is judged a transaction with a new counterparty.",
            ["compare_periods", "query_transactions"])),
      ]),

    # ---------------------------------------------------------------- 023
    S(id="mt_str_023", sub="missing_parameter", ft=5,
      kr="검색어 없는 FIU 조회 요청, 되묻기, 참고유형과 거래 조회, 초안 검증을 거쳐 STR 작성",
      en="FIU lookup without a keyword, clarification, reference type, query, draft validation, STR",
      vars={"acc": 9000000004387158, "bank": 159, "draft": draft_text(DRAFT_023)},
      why="9000000004387158 holds 66 of the 243 type-5 rows, and the balance-certificate entry is "
          "the FIU reference type for the same-day withdrawal pattern.",
      turns=[
        T(kr="FIU 참고유형을 확인하고 싶어.",
          en="I want to look up an FIU reference type.",
          clarify=True,
          point_kr="lookup_fiu_reference_types의 필수 인자 keyword가 없다",
          point_en="lookup_fiu_reference_types needs its required keyword"),
        T(kr="거액을 입금했다가 잔액증명서를 받고 다음 날 전액 인출하는 형태로 찾아줘. 목록이 영어니까 영어 키워드로 해줘.",
          en="Search for the pattern where large funds are deposited, a balance certificate is "
             "issued and the whole amount is withdrawn the next day. The catalog is in English.",
          tool="lookup_fiu_reference_types", args={"keyword": "balance certificate"},
          bind={"fiu": R(2, "result[0].description"), "fiu_n": R(2, "count")}),
        T(kr="출금계좌 {acc}의 거액 입금 후 당일 인출 유형 거래를 금액 순으로 조회해줘.",
          en="List the same-day-withdrawal transactions of account {acc}, largest amount first.",
          tool="query_transactions",
          sql=rows("sender_acc = {acc} AND fraud_type = 5"),
          conds=[("sender_acc", "=", 9000000004387158), ("fraud_type", "=", 5)],
          bind={"n": R(3, "returned_count"), "amt": R(3, "result[0].amount"),
                "date": R(3, "result[0].date"), "media": R(3, "result[0].media_type")}),
        T(kr="작성 중인 STR 초안이 이거야. 필수 항목이 빠졌는지 검증해줘. {draft}",
          en="Here is the STR draft I am working on. Check it for missing required fields. {draft}",
          tool="validate_str_fields", args={"str_draft": DRAFT_023},
          bind={"valid": R(4, "valid"), "missing": R(4, "missing_required")}),
        T(kr="거액 입금 후 당일 인출로 STR 작성해줘.",
          en="Draft the STR for same-day withdrawal after a large deposit.",
          tool="generate_str",
          args=str_args(5,
            "FIU 참고유형 검색에서 {fiu_n}건이 나왔고 그중 {fiu:ko|이가} 이 사안과 같은 형태다. "
            "출금계좌 {acc}(출금기관 {bank})의 거액 입금 후 당일 인출 유형 이상거래 상위 {n}건 중 "
            "최대 건은 {date:date}에 매체구분 {media} 채널로 이체한 {amt:,}원이다. 초안 검증 결과 "
            "필수 항목 충족 여부는 {valid:copula}고 미기재 항목은 {missing:copula}다. 거액이 들어온 "
            "직후 같은 규모가 빠져나가 거액 입금 후 당일 인출로 판단한다.",
            "The FIU reference lookup returned {fiu_n} rows, of which '{fiu}' matches this case. "
            "Among the top {n} same-day-withdrawal rows of withdrawal account {acc} (institution "
            "{bank}) the largest is {amt:,} KRW sent over media type {media} on {date:date}. The "
            "draft validation reports the required fields as {valid} and the missing items as "
            "{missing}. A large deposit left again at the same size straight away, so this is "
            "judged a same-day withdrawal after a large deposit.",
            ["lookup_fiu_reference_types", "query_transactions", "validate_str_fields"])),
      ]),

    # ---------------------------------------------------------------- 024
    S(id="mt_str_024", sub="missing_parameter", ft=3,
      kr="계좌 없는 분석 요청, 되묻기, 프로필과 최다 상대 계좌 수취 분석을 거쳐 STR 작성",
      en="Analysis without an account, clarification, profile, top-counterparty inflow analysis, STR",
      vars={"acc": 9000000000042369, "bank": 159},
      why="9000000000042369 has 40 type-3 rows and 806 distinct receivers, so its profile really "
          "names a top counterparty to follow.",
      turns=[
        T(kr="계좌 하나 분석해줘.",
          en="Analyse an account for me.",
          clarify=True,
          point_kr="get_account_profile의 필수 인자 account_id가 없다",
          point_en="get_account_profile needs its required account_id"),
        T(kr="출금계좌 {acc:copula}야. 프로필을 확인해줘.",
          en="The account is {acc}. Show me its profile.",
          tool="get_account_profile", args={"account_id": "{acc}"},
          bind={"tot": R(2, "total_count"), "fr": R(2, "fraud_ratio_percent"),
                "tamt": R(2, "total_amount"), "cp": R(2, "top_counterparts[0].account_id"),
                "cpn": R(2, "top_counterparts[0].count"), "media": R(2, "top_media[0]")}),
        T(kr="가장 많이 거래한 상대 계좌의 입금 패턴도 봐줘.",
          en="Look at the inflow pattern of the counterparty it deals with most.",
          tool="get_receiving_account_profile",
          args={"account_id": R(2, "top_counterparts[0].account_id")},
          ctx=(2, "top_counterparts[0].account_id", "account_id"),
          bind={"snd": R(3, "unique_senders"), "rtx": R(3, "total_txns"),
                "rfr": R(3, "fraud_ratio_percent")}),
        T(kr="출금계좌의 거래 네트워크도 분석해줘.",
          en="Analyse the withdrawal account's transaction network too.",
          tool="analyze_network", args={"account_id": "{acc}"},
          bind={"neigh": R(4, "connected_account_count"), "nfrn": R(4, "fraud_tx_count")}),
        T(kr="분할 거래로 STR 작성해줘.",
          en="Draft the STR for split transactions.",
          tool="generate_str",
          args=str_args(3,
            "출금계좌 {acc}(출금기관 {bank})의 전체 거래는 {tot}건, {tamt:,}원이고 이상거래 비율은 "
            "{fr}%이며 주 이체 채널은 {media:copula}다. 최다 상대 계좌 {cp:으로로} {cpn}건이 "
            "나갔고, 이 입금계좌는 송금 계좌 {snd}곳에서 {rtx}건을 받으며 이상거래 비율은 {rfr}%다. "
            "출금계좌의 1단계 네트워크는 연결 계좌 {neigh}개, 이상거래 {nfrn}건이다. 소액을 여러 "
            "상대에게 나눠 보내고 특정 계좌로 모이는 형태여서 분할 거래로 판단한다.",
            "Withdrawal account {acc} (institution {bank}) has {tot} transactions worth {tamt:,} "
            "KRW in all, a suspicious-transaction ratio of {fr}% and {media} as its main channel. "
            "{cpn} transfers went to its busiest counterparty {cp}, and that receiving account "
            "takes {rtx} transfers from {snd} sending accounts with a suspicious-transaction ratio "
            "of {rfr}%. The one-hop network of the withdrawal account holds {neigh} connected "
            "accounts and {nfrn} flagged transactions. Small amounts are split across "
            "counterparties and collected into one account, so this is judged a split transaction.",
            ["get_account_profile", "get_receiving_account_profile", "analyze_network"])),
      ]),

    # ---------------------------------------------------------------- 025
    S(id="mt_str_025", sub="missing_parameter", ft=2,
      kr="계좌 없는 분석 요청, 되묻기, 조회·예측·위험도 확인 결과 보고 불요 판단",
      en="Analysis without an account, clarification, query, prediction, risk score, no report needed",
      vars={"acc": 9000000000019227, "bank": 134},
      why="9000000000019227 has 40 transactions, none labelled, a maximum of 300,000 KRW and a "
          "model score of 0.0, so the correct conclusion is that no STR is warranted.",
      turns=[
        T(kr="어떤 계좌가 좀 의심스러운데 분석해줘.",
          en="An account looks suspicious to me. Can you analyse it?",
          clarify=True,
          point_kr="계좌번호가 없어 조회 대상을 특정할 수 없다",
          point_en="no account number, so there is nothing to query"),
        T(kr="출금계좌 {acc:copula}야. 이 계좌 거래를 금액 순으로 조회해줘.",
          en="The account is {acc}. List its transactions, largest amount first.",
          tool="query_transactions",
          sql=rows("sender_acc = {acc}"),
          conds=[("sender_acc", "=", 9000000000019227)],
          bind={"n": R(2, "returned_count"), "amt": R(2, "result[0].amount")}),
        T(kr="첫 번째 거래의 위험 점수를 예측해봐.",
          en="Score the first transaction.",
          tool="predict_fraud", args=predict_args(2), ctx=(2, "result[0].amount", "amount"),
          bind={"score": R(3, "fraud_risk_score"), "lvl": R(3, "risk_level")}),
        T(kr="이 계좌의 위험도도 평가해줘.",
          en="Score the account's risk as well.",
          tool="score_account_risk", args={"account_id": "{acc}"},
          bind={"risk": R(4, "total_score"), "level": R(4, "risk_level"),
                "fh": R(4, "components.fraud_history")}),
        T(kr="STR 작성이 필요할까?",
          en="Does this need an STR?", abstain=True,
          point_kr="예측 점수와 위험도가 모두 낮아 보고 불요를 근거와 함께 답하는 것이 정답",
          point_en="the model score and the risk score are both low, so the correct answer is that "
                   "no report is needed, with the reasons"),
      ]),

    # ---------------------------------------------------------------- 026
    S(id="mt_str_026", sub="missing_parameter", ft=4,
      kr="거래시간대가 빠진 예측 요청, 되묻기, 예측과 해당 거래 조회·프로필을 거쳐 STR 작성",
      en="Prediction missing the time slot, clarification, prediction, query, profile, STR",
      vars={"amt": 90000000},
      why="The six features are those of a real transaction: 9000000004390593's 90,000,000 KRW "
          "type-4 transfer on 2022-07-22 from institution 159 to 155 over internet banking.",
      turns=[
        T(kr="거래금액 {amt:,}원, 출금기관 159, 입금기관 155, 자금구분 0, 매체구분 2인 거래의 위험 점수를 예측해줘.",
          en="Score a transaction of {amt:,} KRW, sender institution 159, receiver institution 155, "
             "fund type 0, media type 2.",
          clarify=True,
          point_kr="predict_fraud의 필수 인자 6개 중 time_slot이 빠졌다",
          point_en="predict_fraud needs six features and time_slot is missing"),
        T(kr="거래시간대는 9야.",
          en="The time slot is 9.",
          tool="predict_fraud",
          args={"time_slot": 9, "sender_bank": 159, "receiver_bank": 155,
                "fund_type": 0, "media_type": 2, "amount": 90000000},
          bind={"score": R(2, "fraud_risk_score"), "lvl": R(2, "risk_level")}),
        T(kr="이 조건에 맞는 실제 거래를 찾아줘. 2022년 7월 22일 다중거래의 동시 요청 유형 중 {amt:,}원 건이야.",
          en="Find the real transaction behind it: the {amt:,} KRW concurrent-multiple-transaction "
             "row of 22 July 2022.",
          tool="query_transactions",
          sql=rows("fraud_type = 4 AND date = 20220722 AND amount = {amt}", limit=5),
          conds=[("fraud_type", "=", 4), ("date", "=", 20220722), ("amount", "=", 90000000)],
          bind={"acc": R(3, "result[0].sender_acc"), "n": R(3, "returned_count")}),
        T(kr="그 출금계좌의 프로필을 봐줘.",
          en="Profile that withdrawal account.",
          tool="get_account_profile", args={"account_id": R(3, "result[0].sender_acc")},
          ctx=(3, "result[0].sender_acc", "account_id"),
          bind={"tot": R(4, "total_count"), "fr": R(4, "fraud_ratio_percent"),
                "frn": R(4, "fraud_count")}),
        T(kr="다중거래의 동시 요청으로 STR 작성해줘.",
          en="Draft the STR for concurrent multiple transactions.",
          tool="generate_str",
          args=str_args(4,
            "거래시간대 9, 출금기관 159, 입금기관 155, 자금구분 0, 매체구분 2, {amt:,}원 조건의 "
            "위험 점수는 {score}, 위험 수준은 {lvl}이다. 같은 조건의 실제 거래는 2022년 7월 22일 "
            "{n}건이고 출금계좌는 {acc:copula}다. 이 계좌의 전체 거래는 {tot}건, 이상거래는 "
            "{frn}건({fr}%)이다. 하루에 동일 규모 이체가 몰려 다중거래의 동시 요청으로 판단한다.",
            "For time slot 9, withdrawal institution 159, deposit institution 155, fund type 0, "
            "media type 2 and {amt:,} KRW the risk score is {score} at risk level {lvl}. The data "
            "holds {n} real transactions on those terms on 22 July 2022, from withdrawal account "
            "{acc}. That account has {tot} transactions in all and {frn} flagged ones ({fr}%). "
            "Transfers of the same size concentrate on one day, so this is judged a concurrent "
            "multiple transaction request.",
            ["predict_fraud", "query_transactions", "get_account_profile"])),
      ]),

    # ---------------------------------------------------------------- 027
    S(id="mt_str_027", sub="long_context", ft=1,
      kr="기관 보고서에서 유형별 집계를 거쳐 최다 계좌 프로필을 확인하고 STR 작성",
      en="Institution report, per-account aggregation, profile the top account, draft the STR",
      vars={"bank": 157},
      why="Institution 157's 2024 type-1 rows really group to 9000000004242077 first (53 rows).",
      turns=[
        T(kr="출금기관 {bank}의 이상거래 현황을 보고해줘.",
          en="Report the fraud picture for institution {bank}.",
          tool="get_institution_report", args={"bank_id": "{bank}"},
          bind={"otot": R(1, "outbound.total_count"), "ofr": R(1, "outbound.fraud_count"),
                "ofrr": R(1, "outbound.fraud_ratio_percent")}),
        T(kr="이 기관의 2024년 갑작스러운 거래패턴의 변화 유형을 출금계좌별 건수 상위 5개로 집계해줘.",
          en="Aggregate this institution's 2024 sudden-pattern-change rows into the top five "
             "withdrawal accounts by count.",
          tool="query_transactions",
          sql="SELECT sender_acc, count(*) AS tx_count, sum(amount) AS total_amount, "
              "max(amount) AS max_amount FROM hofinet WHERE sender_bank = {bank} AND fraud_type = 1 "
              "AND date BETWEEN 20240101 AND 20241231 GROUP BY sender_acc "
              "ORDER BY tx_count DESC, sender_acc LIMIT 5",
          conds=[("sender_bank", "=", 157), ("fraud_type", "=", 1),
                 ("date", "BETWEEN", [20240101, 20241231])],
          bind={"acc": R(2, "result[0].sender_acc"), "acc_n": R(2, "result[0].tx_count"),
                "acc_max": R(2, "result[0].max_amount")}),
        T(kr="가장 건수가 많은 계좌의 프로필을 조회해줘.",
          en="Profile the account with the highest count.",
          tool="get_account_profile", args={"account_id": R(2, "result[0].sender_acc")},
          ctx=(2, "result[0].sender_acc", "account_id"),
          bind={"tot": R(3, "total_count"), "frn": R(3, "fraud_count"),
                "fr": R(3, "fraud_ratio_percent"), "hours": R(3, "top_hours[0]"),
                "media": R(3, "top_media[0]")}),
        T(kr="갑작스러운 거래패턴의 변화로 STR 작성해줘.",
          en="Draft the STR for a sudden change in transaction pattern.",
          tool="generate_str",
          args=str_args(1,
            "출금기관 {bank}의 출금 거래 {otot}건 가운데 이상거래는 {ofr}건({ofrr}%)이다. 2024년 "
            "갑작스러운 거래패턴의 변화 유형은 출금계좌 {acc}에 {acc_n}건으로 집중되며 단건 최대는 "
            "{acc_max:,}원이다. 이 계좌의 전체 거래는 {tot}건, 이상거래는 {frn}건({fr}%)이고 주 "
            "거래시간대는 {hours} 구간, 주 이체 채널은 {media:copula}다. 한 계좌에 이상거래가 "
            "몰리고 금액대가 평소와 달라 갑작스러운 거래패턴의 변화로 판단한다.",
            "Of the {otot} transactions institution {bank} sends, {ofr} are flagged ({ofrr}%). In "
            "2024 the sudden-change type concentrates on withdrawal account {acc} with {acc_n} "
            "rows, the largest single one {acc_max:,} KRW. That account has {tot} transactions in "
            "all and {frn} flagged ones ({fr}%), with {hours} as its main time slots and {media} as "
            "its main channel. Flagged rows concentrate on one account and the amounts depart from "
            "its usual level, so this is judged a sudden change in transaction pattern.",
            ["get_institution_report", "query_transactions", "get_account_profile"])),
      ]),

    # ---------------------------------------------------------------- 028
    S(id="mt_str_028", sub="long_context", ft=3,
      kr="거래 조회에서 최다 입금계좌를 특정해 수취 프로필과 수집 패턴을 분석하고 STR 작성",
      en="Query, take the busiest receiving account, profile it, analyse the collection, draft the STR",
      vars={"acc": 9000000004234041, "bank": 134},
      why="9000000004234041 has 47 type-3 rows and its busiest receiver is 9000000004289938 with "
          "91 transfers, so the reference resolves inside the real result.",
      turns=[
        T(kr="출금계좌 {acc}의 분할 거래 유형 내역을 입금계좌별 건수 상위 5개로 집계해줘.",
          en="Aggregate the split transactions of account {acc} into the top five receiving accounts "
             "by count.",
          tool="query_transactions",
          sql="SELECT receiver_acc, count(*) AS tx_count, sum(amount) AS total_amount "
              "FROM hofinet WHERE sender_acc = {acc} AND fraud_type = 3 "
              "GROUP BY receiver_acc ORDER BY tx_count DESC, receiver_acc LIMIT 5",
          conds=[("sender_acc", "=", 9000000004234041), ("fraud_type", "=", 3)],
          bind={"rcv": R(1, "result[0].receiver_acc"), "rn": R(1, "result[0].tx_count"),
                "ramt": R(1, "result[0].total_amount")}),
        T(kr="가장 많이 받은 입금계좌의 프로필을 봐줘.",
          en="Profile the receiving account that took the most.",
          tool="get_receiving_account_profile", args={"account_id": R(1, "result[0].receiver_acc")},
          ctx=(1, "result[0].receiver_acc", "account_id"),
          bind={"snd": R(2, "unique_senders"), "sbank": R(2, "unique_sender_banks"),
                "rtx": R(2, "total_txns"), "rfr": R(2, "fraud_ratio_percent")}),
        T(kr="이 입금계좌의 자금 수집 패턴을 상대 5곳 이상 기준으로 분석해줘.",
          en="Analyse this receiving account's collection pattern, five or more counterparties.",
          tool="detect_smurfing_network",
          args={"account_id": R(1, "result[0].receiver_acc"), "direction": "inbound",
                "min_counterparts": 5},
          ctx=(1, "result[0].receiver_acc", "account_id"),
          bind={"cp": R(3, "result[0].counterparty_count"), "cavg": R(3, "result[0].avg_amount")}),
        T(kr="분할 거래로 STR 작성해줘.",
          en="Draft the STR for split transactions.",
          tool="generate_str",
          args=str_args(3,
            "출금계좌 {acc}(출금기관 {bank})의 분할 거래 유형은 입금계좌 {rcv:으로로} 이체 {rn}건, "
            "{ramt:,}원이 몰려 있다. 이 입금계좌는 송금 계좌 {snd}곳, 송금 기관 {sbank}곳에서 "
            "{rtx}건을 받았고 이상거래 비율은 {rfr}%다. 수집 패턴 분석에서 상대 {cp}곳, 건당 평균 "
            "{cavg:,.0f}원이 확인된다. 금액을 쪼개 한 계좌로 모으는 형태여서 분할 거래로 판단한다.",
            "The split-transaction rows of withdrawal account {acc} (institution {bank}) "
            "concentrate on receiving account {rcv}: {rn} transfers worth {ramt:,} KRW. That "
            "receiving account takes {rtx} transfers from {snd} sending accounts at {sbank} "
            "institutions, with a suspicious-transaction ratio of {rfr}%. The collection analysis "
            "finds {cp} counterparties at {cavg:,.0f} KRW per transfer on average. Amounts are "
            "split and gathered into one account, so this is judged a split transaction.",
            ["query_transactions", "get_receiving_account_profile", "detect_smurfing_network"])),
      ]),

    # ---------------------------------------------------------------- 029
    S(id="mt_str_029", sub="long_context", ft=2,
      kr="R005 패턴 급변 알림에서 계좌를 특정해 거래 조회와 기간 비교를 거쳐 STR 작성",
      en="R005 pattern-change alert, query the account, compare the periods, draft the STR",
      vars={},
      why="R005 really flags 9000000004236923 first (12 to 264 transactions between quarters); its "
          "labelled fraud is dominated by type 2.",
      turns=[
        T(kr="거래패턴 급변(R005) 모니터링 알림을 확인해줘.",
          en="Check the R005 transaction-pattern-change alerts.",
          tool="detect_monitoring_alerts", args={"rule_id": "R005"},
          bind={"racc": R(1, "result[0].sender_acc"), "base_n": R(1, "result[0].base_period_count"),
                "comp_n": R(1, "result[0].comp_period_count"),
                "mult": R(1, "result[0].count_change_multiple"),
                "comp_amt": R(1, "result[0].comp_period_amount")}),
        T(kr="가장 급변한 계좌의 2024년 4분기 거래를 금액 순으로 조회해줘.",
          en="List the 2024Q4 transactions of the account that changed the most, largest amount first.",
          tool="query_transactions",
          sql=rows("sender_acc = {racc} AND date BETWEEN 20241001 AND 20241231"),
          conds=[("sender_acc", "=", R(1, "result[0].sender_acc")),
                 ("date", "BETWEEN", [20241001, 20241231])],
          ctx=(1, "result[0].sender_acc", "sql"),
          bind={"n": R(2, "returned_count"), "amt": R(2, "result[0].amount"),
                "bank": R(2, "result[0].sender_bank"), "media": R(2, "result[0].media_type")}),
        T(kr="이 계좌가 속한 기간을 3분기와 4분기로 나눠 비교해줘.",
          en="Compare the third and fourth quarters of 2024.",
          tool="compare_periods",
          args={"period1_start": 20240701, "period1_end": 20240930,
                "period2_start": 20241001, "period2_end": 20241231},
          bind={"dfr": R(3, "delta.fraud_count_pct")}),
        T(kr="신규 수신처 거래로 STR 작성해줘.",
          en="Draft the STR for transactions with new counterparties.",
          tool="generate_str",
          args=str_args(2,
            "모니터링 R005에서 출금계좌 {racc}(출금기관 {bank})의 거래 건수가 기준 기간 "
            "{base_n}건에서 비교 기간 {comp_n}건으로 {mult}배 늘었고 금액은 {comp_amt:,}원이다. "
            "2024년 4분기 거래 상위 {n}건의 최대 금액은 매체구분 {media} 채널 이체 {amt:,}원이다. "
            "같은 기간 전체 이상거래 건수는 직전 분기 대비 {dfr}% 변화했다. 거래 상대가 급격히 "
            "늘어난 형태여서 신규 수신처 거래로 판단한다.",
            "The R005 monitoring rule shows withdrawal account {racc} (institution {bank}) rising "
            "from {base_n} transactions in the baseline period to {comp_n} in the comparison "
            "period, a factor of {mult}, worth {comp_amt:,} KRW. Among its top {n} fourth-quarter "
            "2024 transactions the largest is {amt:,} KRW over media type {media}. Over the same "
            "period the overall flagged count moved by {dfr}% against the previous quarter. The "
            "number of counterparties rose sharply, so this is judged a transaction with a new "
            "counterparty.",
            ["detect_monitoring_alerts", "query_transactions", "compare_periods"])),
      ]),

    # ---------------------------------------------------------------- 030
    S(id="mt_str_030", sub="long_context", ft=1,
      kr="CTR 고액거래 탐지에서 계좌를 특정해 네트워크와 그래프 위험 점수를 확인하고 STR 작성",
      en="CTR high-value detection, take the account, network and graph risk score, draft the STR",
      vars={},
      why="The 2024 high-value CTR scan really returns 9000000004242077's 500,000,000 KRW transfer "
          "first; that account carries 151 type-1 rows.",
      turns=[
        T(kr="2024년 CTR 고액거래 대상을 탐지해줘.",
          en="Detect the 2024 high-value CTR candidates.",
          tool="detect_ctr_candidates",
          args={"mode": "high_value", "date_from": 20240101, "date_to": 20241231},
          bind={"cacc": R(1, "result[0].sender_acc"), "camt": R(1, "result[0].amount"),
                "cdate": R(1, "result[0].date"), "cthr": R(1, "threshold"),
                "cbank": R(1, "result[0].sender_bank")}),
        T(kr="1순위 거래의 출금계좌 네트워크를 분석해줘.",
          en="Analyse the withdrawal account of the top transaction.",
          tool="analyze_network", args={"account_id": R(1, "result[0].sender_acc")},
          ctx=(1, "result[0].sender_acc", "account_id"),
          bind={"neigh": R(2, "connected_account_count"), "nfrn": R(2, "fraud_tx_count"),
                "nfr": R(2, "fraud_ratio_percent")}),
        T(kr="이 계좌의 그래프 기반 위험 점수도 계산해봐.",
          en="Compute this account's graph-based risk score as well.",
          tool="detect_aml_patterns",
          args={"pattern_type": "risk_score", "account_id": R(1, "result[0].sender_acc")},
          ctx=(1, "result[0].sender_acc", "account_id"),
          bind={"grisk": R(3, "risk_score"), "gimb": R(3, "components.in_out_imbalance_percent")}),
        T(kr="갑작스러운 거래패턴의 변화로 STR 작성해줘.",
          en="Draft the STR for a sudden change in transaction pattern.",
          tool="generate_str",
          args=str_args(1,
            "CTR 고액거래 기준({cthr:,}원)으로 2024년 1순위는 {cdate:date}에 출금기관 {cbank} 소속 "
            "출금계좌 {cacc:이가} 이체한 {camt:,}원이다. 이 계좌의 1단계 네트워크는 연결 계좌 "
            "{neigh}개, 이상거래 {nfrn}건({nfr}%)이다. 그래프 위험 점수는 {grisk:copula}고 입출금 "
            "불균형 지표는 {gimb}%다. 거래 규모가 종전 수준을 벗어나 갑작스러운 거래패턴의 변화로 "
            "판단한다.",
            "Under the CTR high-value threshold of {cthr:,} KRW the top row of 2024 is {camt:,} KRW "
            "sent on {cdate:date} by withdrawal account {cacc} at institution {cbank}. The one-hop "
            "network of that account holds {neigh} connected accounts and {nfrn} flagged "
            "transactions ({nfr}%). Its graph risk score is {grisk} and its inflow/outflow "
            "imbalance indicator is {gimb}%. The size of the transfer leaves the account's earlier "
            "level behind, so this is judged a sudden change in transaction pattern.",
            ["detect_ctr_candidates", "analyze_network", "detect_aml_patterns"])),
      ]),
]
