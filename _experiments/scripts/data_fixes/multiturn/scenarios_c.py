"""Scenarios 31 to 50 of the multi-turn rebuild. See `scenarios.py` for the conventions."""

from __future__ import annotations

from .scenarios import DRAFT_046, draft_text, predict_args, rows, str_args
from .spec import Ref as R
from .spec import Scenario as S
from .spec import Turn as T

SCENARIOS_C: list[S] = [

    # ---------------------------------------------------------------- 031
    S(id="mt_str_031", sub="long_context", ft=4,
      kr="유형 현황에서 상위 기관을 특정해 계좌별 집계와 위험도 평가를 거쳐 STR 작성",
      en="Type summary, take the top institution, aggregate per account, score it, draft the STR",
      vars={},
      why="The type-4 summary really names institution 147 first (812 of 929 rows), and that "
          "institution's 2024 rows group to 9000000004236284 first.",
      turns=[
        T(kr="다중거래의 동시 요청 유형 현황을 알려줘.",
          en="Show me the picture for the concurrent multiple transactions type.",
          tool="get_fraud_type_summary", args={"fraud_type": 4},
          bind={"t4n": R(1, "total_count"), "t4bank": R(1, "top_banks[0].bank_id"),
                "t4bn": R(1, "top_banks[0].count"), "t4avg": R(1, "avg_amount")}),
        T(kr="가장 많은 출금기관의 2024년 해당 유형 거래를 출금계좌별 건수 상위 5개로 집계해줘.",
          en="Aggregate that institution's 2024 rows of this type into the top five withdrawal "
             "accounts by count.",
          tool="query_transactions",
          sql="SELECT sender_acc, count(*) AS tx_count, sum(amount) AS total_amount "
              "FROM hofinet WHERE sender_bank = {t4bank} AND fraud_type = 4 "
              "AND date BETWEEN 20240101 AND 20241231 GROUP BY sender_acc "
              "ORDER BY tx_count DESC, sender_acc LIMIT 5",
          conds=[("sender_bank", "=", R(1, "top_banks[0].bank_id")), ("fraud_type", "=", 4),
                 ("date", "BETWEEN", [20240101, 20241231])],
          ctx=(1, "top_banks[0].bank_id", "sql"),
          bind={"acc": R(2, "result[0].sender_acc"), "acc_n": R(2, "result[0].tx_count"),
                "acc_amt": R(2, "result[0].total_amount")}),
        T(kr="가장 건수가 많은 계좌의 위험도를 평가해줘.",
          en="Score the risk of the account with the highest count.",
          tool="score_account_risk", args={"account_id": R(2, "result[0].sender_acc")},
          ctx=(2, "result[0].sender_acc", "account_id"),
          bind={"risk": R(3, "total_score"), "level": R(3, "risk_level"),
                "vel": R(3, "components.velocity_change")}),
        T(kr="다중거래의 동시 요청으로 STR 작성해줘.",
          en="Draft the STR for concurrent multiple transactions.",
          tool="generate_str",
          args=str_args(4,
            "다중거래의 동시 요청 유형은 전체 {t4n}건이고 출금기관 {t4bank:이가} {t4bn}건으로 가장 "
            "많다. 유형 평균 금액은 {t4avg:,.0f}원이다. 이 기관의 2024년 해당 유형은 출금계좌 "
            "{acc}에 {acc_n}건, {acc_amt:,}원으로 집중된다. 위험도 평가는 {risk}점({level})이고 "
            "거래 속도 변화 지표는 {vel:copula}다. 동일 계좌에서 같은 날 다수 이체가 몰려 "
            "다중거래의 동시 요청으로 판단한다.",
            "The concurrent-multiple-transaction type covers {t4n} rows in all, and withdrawal "
            "institution {t4bank} leads it with {t4bn}. The type averages {t4avg:,.0f} KRW per "
            "transaction. At that institution the 2024 rows of the type concentrate on withdrawal "
            "account {acc}: {acc_n} rows worth {acc_amt:,} KRW. Its behavioural risk score is "
            "{risk} ({level}) and its transaction-velocity indicator is {vel}. Several transfers "
            "concentrate on one day from one account, so this is judged a concurrent multiple "
            "transaction request.",
            ["get_fraud_type_summary", "query_transactions", "score_account_risk"])),
      ]),

    # ---------------------------------------------------------------- 032
    S(id="mt_str_032", sub="long_context", ft=1,
      kr="월별 트렌드와 12월 채널 위험도에서 최고 위험 채널을 특정해 거래 조회와 예측 후 STR 작성",
      en="Monthly trend, December channel risk, query the riskiest channel, predict, draft the STR",
      vars={},
      why="In December 2024 the riskiest channel is media type 6 (Other) and that month really has "
          "17 type-1 rows on that channel.",
      turns=[
        T(kr="2024년 월별 이상거래 트렌드를 분석해줘.",
          en="Analyse the monthly fraud trend for 2024.",
          tool="get_trend_analysis",
          args={"unit": "monthly", "date_from": 20240101, "date_to": 20241231},
          bind={"pn": R(1, "period_count"), "p0": R(1, "result[11].period"),
                "p0r": R(1, "result[11].fraud_ratio_percent")}),
        T(kr="12월의 채널별 위험도를 분석해줘.",
          en="Analyse channel risk for December.",
          tool="analyze_channel_risk", args={"date_from": 20241201, "date_to": 20241231},
          bind={"chm": R(2, "channel_stats[0].media_type"),
                "chn": R(2, "channel_stats[0].channel_name"),
                "chr": R(2, "channel_stats[0].fraud_ratio_percent")}),
        T(kr="이상거래 비율이 가장 높은 채널의 12월 갑작스러운 거래패턴의 변화 유형 거래를 금액 순으로 조회해줘.",
          en="List the December sudden-pattern-change transactions on the riskiest channel, "
             "largest amount first.",
          tool="query_transactions",
          sql=rows("media_type = {chm} AND fraud_type = 1 AND date BETWEEN 20241201 AND 20241231",
                   limit=10),
          conds=[("media_type", "=", R(2, "channel_stats[0].media_type")), ("fraud_type", "=", 1),
                 ("date", "BETWEEN", [20241201, 20241231])],
          ctx=(2, "channel_stats[0].media_type", "sql"),
          bind={"n": R(3, "returned_count"), "acc": R(3, "result[0].sender_acc"),
                "amt": R(3, "result[0].amount"), "date": R(3, "result[0].date"),
                "bank": R(3, "result[0].sender_bank")}),
        T(kr="첫 번째 거래의 위험 점수를 예측해줘.",
          en="Score the first transaction in that result.",
          tool="predict_fraud", args=predict_args(3), ctx=(3, "result[0].amount", "amount"),
          bind={"score": R(4, "fraud_risk_score")}),
        T(kr="갑작스러운 거래패턴의 변화로 STR 작성해줘.",
          en="Draft the STR for a sudden change in transaction pattern.",
          tool="generate_str",
          args=str_args(1,
            "2024년 월별 트렌드 {pn}개 구간에서 {p0}의 이상거래 비율은 {p0r}%다. 12월 채널 분석에서 "
            "이상거래 비율이 가장 높은 채널은 {chn}(매체구분 {chm}, {chr}%)이다. 이 채널의 12월 "
            "갑작스러운 거래패턴의 변화 유형 상위 {n}건 중 최대 건은 {date:date}에 출금기관 {bank} "
            "소속 출금계좌 {acc:이가} 이체한 {amt:,}원이고 예측 모델 위험 점수는 {score:copula}다. "
            "평소 쓰지 않던 채널로 거액이 이동해 갑작스러운 거래패턴의 변화로 판단한다.",
            "Across the {pn} monthly periods of 2024 the suspicious-transaction ratio of {p0} is "
            "{p0r}%. In the December channel analysis the highest ratio belongs to {chn} (media "
            "type {chm}, {chr}%). Among the top {n} December sudden-change rows on that channel the "
            "largest is {amt:,} KRW sent on {date:date} by withdrawal account {acc} at institution "
            "{bank}, with a model risk score of {score}. A large amount moved over a channel the "
            "account does not normally use, so this is judged a sudden change in transaction "
            "pattern.",
            ["get_trend_analysis", "analyze_channel_risk", "query_transactions", "predict_fraud"])),
      ]),

    # ---------------------------------------------------------------- 033
    S(id="mt_str_033", sub="long_context", ft=3,
      kr="전체 통계와 분할 거래 유형 현황에서 상위 기관을 특정해 기관 보고서를 확인하고 STR 작성",
      en="Statistics, split-transaction summary, report on the top institution, draft the STR",
      vars={},
      why="Institution 159 sends 1,464 of the 2,073 type-3 rows, so the summary's top institution "
          "is the one whose report matters.",
      turns=[
        T(kr="전체 통계를 먼저 보여줘.",
          en="Show me the overall statistics first.",
          tool="get_statistics",
          bind={"tot": R(1, "summary_statistics.total_tx_count"),
                "frr": R(1, "summary_statistics.fraud_ratio_percent")}),
        T(kr="분할 거래 유형을 자세히 봐줘.",
          en="Take a closer look at the split transaction type.",
          tool="get_fraud_type_summary", args={"fraud_type": 3},
          bind={"t3n": R(2, "total_count"), "t3amt": R(2, "total_amount"),
                "t3bank": R(2, "top_banks[0].bank_id"), "t3bn": R(2, "top_banks[0].count")}),
        T(kr="이 유형이 가장 많은 출금기관의 보고서를 조회해줘.",
          en="Pull the report for the institution with the most of this type.",
          tool="get_institution_report", args={"bank_id": R(2, "top_banks[0].bank_id")},
          ctx=(2, "top_banks[0].bank_id", "bank_id"),
          bind={"otot": R(3, "outbound.total_count"), "ofr": R(3, "outbound.fraud_count"),
                "ofrr": R(3, "outbound.fraud_ratio_percent"),
                "tb": R(3, "top_counterpart_banks[0].bank_id")}),
        T(kr="분할 거래로 STR 작성해줘.",
          en="Draft the STR for split transactions.",
          tool="generate_str",
          args=str_args(3,
            "HOFINET 전체 거래는 {tot}건이고 이상거래 비율은 {frr}%다. 분할 거래 유형은 {t3n}건, "
            "{t3amt:,}원이며 출금기관 {t3bank:이가} {t3bn}건으로 가장 많다. 이 기관의 출금 거래는 "
            "{otot}건, 이상거래는 {ofr}건({ofrr}%)이고 최다 상대 기관은 {tb:copula}다. 한 기관에 "
            "분할 이체가 집중되어 분할 거래로 판단한다.",
            "HOFINET holds {tot} transactions in all, with a suspicious-transaction ratio of "
            "{frr}%. The split-transaction type covers {t3n} rows worth {t3amt:,} KRW, and "
            "withdrawal institution {t3bank} leads it with {t3bn}. That institution sends {otot} "
            "transactions, {ofr} of them flagged ({ofrr}%), and its busiest counterpart institution "
            "is {tb}. Split transfers concentrate on one institution, so this is judged a split "
            "transaction.",
            ["get_statistics", "get_fraud_type_summary", "get_institution_report"])),
      ]),

    # ---------------------------------------------------------------- 034
    S(id="mt_str_034", sub="long_context", ft=1,
      kr="장기 휴면 후 거액 재활성화 계좌를 특정해 프로필과 CTR 고액거래를 확인하고 STR 작성",
      en="Long-dormant account reactivated with a large amount, profile, high-value CTR check, STR",
      vars={},
      why="With a 100,000,000 KRW reactivation threshold the scan returns 9000000000028288 first "
          "(648 dormant days); the account carries a type-1 row.",
      turns=[
        T(kr="180일 이상 휴면했다가 1억원 이상으로 재활성화된 계좌를 찾아줘.",
          en="Find accounts dormant for 180 days or more that were reactivated with 100 million KRW or more.",
          tool="detect_dormant_reactivation",
          args={"dormant_days": 180, "min_reactivation_amount": 100000000},
          bind={"dacc": R(1, "result[0].sender_acc"), "ddays": R(1, "result[0].dormant_days"),
                "dlast": R(1, "result[0].last_activity_date"),
                "dre": R(1, "result[0].reactivation_date"),
                "damt": R(1, "result[0].reactivation_amount")}),
        T(kr="가장 오래 휴면했던 계좌의 프로필을 봐줘.",
          en="Profile the account that was dormant the longest.",
          tool="get_account_profile", args={"account_id": R(1, "result[0].sender_acc")},
          ctx=(1, "result[0].sender_acc", "account_id"),
          bind={"tot": R(2, "total_count"), "frn": R(2, "fraud_count"),
                "fr": R(2, "fraud_ratio_percent"), "tamt": R(2, "total_amount"),
                "media": R(2, "top_media[0]")}),
        T(kr="재활성화가 있었던 2023년에 CTR 고액거래 대상이 있었는지 확인해줘.",
          en="Check the high-value CTR candidates for 2023, the year of the reactivation.",
          tool="detect_ctr_candidates",
          args={"mode": "high_value", "date_from": 20230101, "date_to": 20231231},
          bind={"cn": R(3, "count"), "cthr": R(3, "threshold")}),
        T(kr="갑작스러운 거래패턴의 변화로 STR 작성해줘.",
          en="Draft the STR for a sudden change in transaction pattern.",
          tool="generate_str",
          args=str_args(1,
            "출금계좌 {dacc:은는} {dlast:date|을를} 마지막으로 {ddays}일 동안 거래가 없다가 "
            "{dre:date}에 {damt:,}원으로 재활성화됐다. 계좌 전체 거래는 {tot}건, {tamt:,}원이고 "
            "이상거래는 {frn}건({fr}%)이며 주 이체 채널은 {media:copula}다. 재활성화 연도의 CTR "
            "고액거래 조회({cthr:,}원 기준)에서 상위 {cn}건이 나왔다. 장기 휴면 계좌에서 거액이 한 "
            "번에 나가 갑작스러운 거래패턴의 변화로 판단한다.",
            "Withdrawal account {dacc} was last active on {dlast:date}, stayed silent for {ddays} "
            "days and was reactivated on {dre:date} with {damt:,} KRW. The account has {tot} "
            "transactions worth {tamt:,} KRW in all, {frn} of them flagged ({fr}%), and {media} as "
            "its main channel. A CTR high-value query for the year of the reactivation, at a "
            "threshold of {cthr:,} KRW, returned {cn} rows. A large amount left a long-dormant "
            "account in one go, so this is judged a sudden change in transaction pattern.",
            ["detect_dormant_reactivation", "get_account_profile", "detect_ctr_candidates"])),
      ]),

    # ---------------------------------------------------------------- 035
    S(id="mt_str_035", sub="base", ft=7,
      kr="심야 대량거래 의심 계좌를 조회·예측·위험도 평가한 결과 보고 불요 판단",
      en="Account suspected of night-time bulk activity: query, predict, score, no report needed",
      vars={"acc": 9000000000007575, "bank": 133},
      why="9000000000007575 has 40 transactions, none labelled, a maximum of 300,000 KRW and no "
          "night-slot activity, so the night-time bulk suspicion does not hold.",
      turns=[
        T(kr="계좌 {acc:이가} 심야/새벽 대량 거래로 의심된다는 제보가 있어. 이 계좌 거래를 금액 순으로 조회해줘.",
          en="Account {acc} was reported for late-night bulk activity. List its transactions, "
             "largest amount first.",
          tool="query_transactions",
          sql=rows("sender_acc = {acc}"),
          conds=[("sender_acc", "=", 9000000000007575)],
          bind={"n": R(1, "returned_count"), "amt": R(1, "result[0].amount"),
                "slot": R(1, "result[0].time_slot")}),
        T(kr="첫 번째 거래의 위험 점수를 예측해봐.",
          en="Score the first transaction.",
          tool="predict_fraud", args=predict_args(1), ctx=(1, "result[0].amount", "amount"),
          bind={"score": R(2, "fraud_risk_score"), "lvl": R(2, "risk_level")}),
        T(kr="이 계좌의 위험도도 확인해줘.",
          en="Check the account's risk score too.",
          tool="score_account_risk", args={"account_id": "{acc}"},
          bind={"risk": R(3, "total_score"), "level": R(3, "risk_level"),
                "night": R(3, "components.nighttime_ratio")}),
        T(kr="STR 작성이 필요할까?",
          en="Does this need an STR?", abstain=True,
          point_kr="심야 거래 비중과 위험 점수가 낮아 보고 불요를 근거와 함께 답하는 것이 정답",
          point_en="the night-time share and the risk score are low, so the correct answer is that "
                   "no report is needed, with the reasons"),
      ]),

    # ---------------------------------------------------------------- 036
    S(id="mt_str_036", sub="long_context", ft=4,
      kr="기관간 흐름에서 최고 위험 구간의 송금 기관 보고서를 확인하고 구간 거래를 조회해 STR 작성",
      en="Cross-institution flow, report on the sending institution of the worst leg, query the leg, STR",
      vars={},
      why="Over 2024 the 147 to 154 leg has the highest fraud ratio (30.57% of 157 transactions) "
          "among legs with 50 or more transactions, and its fraud is dominated by type 4.",
      turns=[
        T(kr="2024년 기관간 자금 흐름을 거래 50건 이상 기준으로 분석해줘.",
          en="Analyse the 2024 flows between institutions, counting legs with at least 50 transactions.",
          tool="analyze_cross_institution_flow",
          args={"date_from": 20240101, "date_to": 20241231, "min_transactions": 50, "limit": 10},
          bind={"sb": R(1, "result[0].sender_institution"),
                "rb": R(1, "result[0].receiver_institution"),
                "ftx": R(1, "result[0].tx_count"), "ffr": R(1, "result[0].fraud_count"),
                "fratio": R(1, "result[0].fraud_ratio_percent")}),
        T(kr="이상거래 비율이 가장 높은 구간의 송금 기관 보고서를 조회해줘.",
          en="Pull the report for the sending institution of the riskiest leg.",
          tool="get_institution_report", args={"bank_id": R(1, "result[0].sender_institution")},
          ctx=(1, "result[0].sender_institution", "bank_id"),
          bind={"otot": R(2, "outbound.total_count"), "ofr": R(2, "outbound.fraud_count"),
                "ofrr": R(2, "outbound.fraud_ratio_percent"),
                "ttype": R(2, "fraud_type_distribution[0].type_name")}),
        T(kr="출금기관 {sb}에서 입금기관 {rb:으로로} 간 2024년 이상거래를 금액 순으로 조회해줘.",
          en="List the 2024 flagged transactions from institution {sb} to institution {rb}, "
             "largest amount first.",
          tool="query_transactions",
          sql=rows("sender_bank = {sb} AND receiver_bank = {rb} AND is_fraud = 1 "
                   "AND date BETWEEN 20240101 AND 20241231"),
          conds=[("sender_bank", "=", R(1, "result[0].sender_institution")),
                 ("receiver_bank", "=", R(1, "result[0].receiver_institution")),
                 ("is_fraud", "=", 1), ("date", "BETWEEN", [20240101, 20241231])],
          bind={"n": R(3, "returned_count"), "acc": R(3, "result[0].sender_acc"),
                "amt": R(3, "result[0].amount"), "date": R(3, "result[0].date")}),
        T(kr="다중거래의 동시 요청으로 STR 작성해줘.",
          en="Draft the STR for concurrent multiple transactions.",
          tool="generate_str",
          args=str_args(4,
            "2024년 기관간 흐름에서 출금기관 {sb}에서 입금기관 {rb:으로로} 가는 구간은 거래 {ftx}건 "
            "중 이상거래가 {ffr}건({fratio}%)으로 가장 높다. 출금기관 {sb}의 출금 거래는 {otot}건, "
            "이상거래는 {ofr}건({ofrr}%)이며 가장 많은 유형은 {ttype:copula}다. 이 구간의 2024년 "
            "이상거래 상위 {n}건 중 최대 건은 {date:date}에 출금계좌 {acc:이가} 이체한 "
            "{amt:,}원이다. 같은 구간으로 다수 이체가 동시에 몰려 다중거래의 동시 요청으로 "
            "판단한다.",
            "In the 2024 cross-institution flow the leg from withdrawal institution {sb} to deposit "
            "institution {rb} carries {ffr} flagged rows out of {ftx} transactions ({fratio}%), the "
            "highest of all. Institution {sb} sends {otot} transactions, {ofr} of them flagged "
            "({ofrr}%), and its most common type is {ttype}. Among the top {n} flagged rows of that "
            "leg in 2024 the largest is {amt:,} KRW sent by withdrawal account {acc} on "
            "{date:date}. Several transfers concentrate on the same leg at once, so this is judged "
            "a concurrent multiple transaction request.",
            ["analyze_cross_institution_flow", "get_institution_report", "query_transactions"])),
      ]),

    # ---------------------------------------------------------------- 037
    S(id="mt_str_037", sub="long_context", ft=2,
      kr="4분기 채널 위험도에서 최고 위험 채널의 거래를 조회하고 계좌 프로필·네트워크를 확인해 STR 작성",
      en="Q4 channel risk, query the riskiest channel, profile the account and its network, STR",
      vars={},
      why="PC Banking is the riskiest channel in 2024Q4 (1.495%) and its Q4 fraud is eight type-2 "
          "rows, so the chain resolves on real data.",
      turns=[
        T(kr="2024년 4분기 채널별 위험도를 분석해줘.",
          en="Analyse channel risk for 2024Q4.",
          tool="analyze_channel_risk", args={"date_from": 20241001, "date_to": 20241231},
          bind={"chm": R(1, "channel_stats[0].media_type"),
                "chn": R(1, "channel_stats[0].channel_name"),
                "chr": R(1, "channel_stats[0].fraud_ratio_percent"),
                "chtx": R(1, "channel_stats[0].total_txns")}),
        T(kr="이상거래 비율이 가장 높은 채널의 4분기 신규 수신처 거래 유형 거래를 금액 순으로 조회해줘.",
          en="List that channel's Q4 new-counterparty fraud, largest amount first.",
          tool="query_transactions",
          sql=rows("media_type = {chm} AND fraud_type = 2 AND date BETWEEN 20241001 AND 20241231",
                   limit=10),
          conds=[("media_type", "=", R(1, "channel_stats[0].media_type")), ("fraud_type", "=", 2),
                 ("date", "BETWEEN", [20241001, 20241231])],
          ctx=(1, "channel_stats[0].media_type", "sql"),
          bind={"n": R(2, "returned_count"), "acc": R(2, "result[0].sender_acc"),
                "amt": R(2, "result[0].amount"), "date": R(2, "result[0].date"),
                "bank": R(2, "result[0].sender_bank")}),
        T(kr="가장 큰 건의 출금계좌 프로필을 확인해줘.",
          en="Profile the withdrawal account of the largest transaction.",
          tool="get_account_profile", args={"account_id": R(2, "result[0].sender_acc")},
          ctx=(2, "result[0].sender_acc", "account_id"),
          bind={"tot": R(3, "total_count"), "frn": R(3, "fraud_count"),
                "fr": R(3, "fraud_ratio_percent")}),
        T(kr="이 계좌의 거래 네트워크도 분석해줘.",
          en="Analyse this account's transaction network as well.",
          tool="analyze_network", args={"account_id": R(2, "result[0].sender_acc")},
          ctx=(2, "result[0].sender_acc", "account_id"),
          bind={"neigh": R(4, "connected_account_count"), "nfr": R(4, "fraud_ratio_percent")}),
        T(kr="신규 수신처 거래로 STR 작성해줘.",
          en="Draft the STR for transactions with new counterparties.",
          tool="generate_str",
          args=str_args(2,
            "2024년 4분기 채널 분석에서 {chn}(매체구분 {chm})의 이상거래 비율이 {chr}%로 가장 높고 "
            "거래는 {chtx}건이다. 이 채널의 4분기 신규 수신처 거래 유형 상위 {n}건 중 최대 건은 "
            "{date:date}에 출금기관 {bank} 소속 출금계좌 {acc:이가} 이체한 {amt:,}원이다. 이 계좌의 "
            "전체 거래는 {tot}건, 이상거래는 {frn}건({fr}%)이고 1단계 네트워크는 연결 계좌 "
            "{neigh}개, 이상거래 비율 {nfr}%다. 거래 이력이 없던 상대로 자금이 나가 신규 수신처 "
            "거래로 판단한다.",
            "In the fourth-quarter 2024 channel analysis {chn} (media type {chm}) carries the "
            "highest suspicious-transaction ratio at {chr}% over {chtx} transactions. Among the top "
            "{n} new-counterparty rows on that channel in the quarter the largest is {amt:,} KRW "
            "sent on {date:date} by withdrawal account {acc} at institution {bank}. That account "
            "has {tot} transactions in all and {frn} flagged ones ({fr}%), and its one-hop network "
            "holds {neigh} connected accounts at a suspicious-transaction ratio of {nfr}%. Funds "
            "left for a counterparty with no earlier history, so this is judged a transaction with "
            "a new counterparty.",
            ["analyze_channel_risk", "query_transactions", "get_account_profile",
            "analyze_network"])),
      ]),

    # ---------------------------------------------------------------- 038
    S(id="mt_str_038", sub="long_context", ft=2,
      kr="기관 보고서와 최다 거래 계좌 위험도 평가 결과 보고 불요 판단",
      en="Institution report, score the busiest account, conclude that no report is needed",
      vars={"bank": 145},
      why="Institution 145's busiest 2024Q4 sender, 9000000000020983, has 69 transactions and no "
          "labelled fraud, so the correct conclusion is that no STR is warranted.",
      turns=[
        T(kr="출금기관 {bank}의 현황을 봐줘.",
          en="Show me the picture for institution {bank}.",
          tool="get_institution_report", args={"bank_id": "{bank}"},
          bind={"otot": R(1, "outbound.total_count"), "ofr": R(1, "outbound.fraud_count"),
                "ofrr": R(1, "outbound.fraud_ratio_percent")}),
        T(kr="이 기관의 2024년 4분기 거래를 출금계좌별 건수 상위 5개로 집계해줘.",
          en="Aggregate this institution's 2024Q4 activity into the top five withdrawal accounts by count.",
          tool="query_transactions",
          sql="SELECT sender_acc, count(*) AS tx_count, sum(is_fraud) AS fraud_count, "
              "sum(amount) AS total_amount FROM hofinet WHERE sender_bank = {bank} "
              "AND date BETWEEN 20241001 AND 20241231 GROUP BY sender_acc "
              "ORDER BY tx_count DESC, sender_acc LIMIT 5",
          conds=[("sender_bank", "=", 145), ("date", "BETWEEN", [20241001, 20241231])],
          bind={"acc": R(2, "result[0].sender_acc"), "acc_n": R(2, "result[0].tx_count"),
                "acc_fr": R(2, "result[0].fraud_count"), "acc_amt": R(2, "result[0].total_amount")}),
        T(kr="가장 건수가 많은 계좌의 위험도를 평가해줘.",
          en="Score the risk of the account with the highest count.",
          tool="score_account_risk", args={"account_id": R(2, "result[0].sender_acc")},
          ctx=(2, "result[0].sender_acc", "account_id"),
          bind={"risk": R(3, "total_score"), "level": R(3, "risk_level")}),
        T(kr="STR을 작성할 필요가 있을까?",
          en="Is an STR called for here?", abstain=True,
          point_kr="최다 거래 계좌에 이상거래 라벨이 없고 위험도가 낮아 보고 불요가 정답",
          point_en="the busiest account carries no labelled fraud and a low risk score, so no report "
                   "is the correct answer"),
      ]),

    # ---------------------------------------------------------------- 039
    S(id="mt_str_039", sub="long_context", ft=1,
      kr="R002 동일일 다건 알림에서 계좌를 특정해 거래 조회와 CTR 분할거래 확인 후 STR 작성",
      en="R002 same-day burst alert, query the account, CTR structuring check, draft the STR",
      vars={},
      why="R002 really flags 9000000000044046 first in 2024Q4 (164 transfers on 31 December); the "
          "account's labelled fraud is type 1.",
      turns=[
        T(kr="2024년 4분기 R002 동일일 다건거래 알림을 확인해줘.",
          en="Check the R002 same-day burst alerts for 2024Q4.",
          tool="detect_monitoring_alerts",
          args={"rule_id": "R002", "date_from": 20241001, "date_to": 20241231},
          bind={"racc": R(1, "result[0].sender_acc"), "rdate": R(1, "result[0].date"),
                "rn": R(1, "result[0].tx_count"), "ramt": R(1, "result[0].total_amount"),
                "rfr": R(1, "result[0].fraud_count")}),
        T(kr="가장 건수가 많은 계좌의 그날 거래를 금액 순으로 조회해줘.",
          en="List that day's transactions of the account with the highest count, largest amount first.",
          tool="query_transactions",
          sql=rows("sender_acc = {racc} AND date = {rdate}"),
          conds=[("sender_acc", "=", R(1, "result[0].sender_acc")),
                 ("date", "=", R(1, "result[0].date"))],
          ctx=(1, "result[0].sender_acc", "sql"),
          bind={"n": R(2, "returned_count"), "amt": R(2, "result[0].amount"),
                "bank": R(2, "result[0].sender_bank")}),
        T(kr="4분기에 분할거래 의심 건이 있는지 CTR 기준으로 확인해줘.",
          en="Check the Q4 structuring candidates with the CTR rule.",
          tool="detect_ctr_candidates",
          args={"mode": "structuring", "date_from": 20241001, "date_to": 20241231},
          bind={"cn": R(3, "count"), "cacc": R(3, "result[0].sender_acc"),
                "ctx_n": R(3, "result[0].tx_count")}),
        T(kr="갑작스러운 거래패턴의 변화로 STR 작성해줘.",
          en="Draft the STR for a sudden change in transaction pattern.",
          tool="generate_str",
          args=str_args(1,
            "모니터링 R002에서 출금기관 {bank} 소속 출금계좌 {racc:이가} {rdate:date} 하루에 "
            "{rn}건, {ramt:,}원을 이체한 것으로 나타났다. 그날 거래 상위 {n}건의 최대 금액은 "
            "{amt:,}원이고 그중 이상거래로 분류된 건은 {rfr}건이다. 같은 분기 CTR 분할거래 조회 "
            "상위 {cn}건 가운데 최다는 {cacc}의 {ctx_n}건이다. 하루 거래 건수가 평소 수준을 크게 "
            "벗어나 갑작스러운 거래패턴의 변화로 판단한다.",
            "The R002 monitoring rule shows withdrawal account {racc}, at institution {bank}, "
            "making {rn} transfers worth {ramt:,} KRW on {rdate:date}. Among the top {n} "
            "transactions of that day the largest is {amt:,} KRW and {rfr} of them are flagged. A "
            "CTR structuring query over the same quarter returned {cn} rows, the busiest being "
            "{ctx_n} transfers by account {cacc}. The number of transactions in one day is far "
            "above the account's usual level, so this is judged a sudden change in transaction "
            "pattern.",
            ["detect_monitoring_alerts", "query_transactions", "detect_ctr_candidates"])),
      ]),

    # ---------------------------------------------------------------- 040
    S(id="mt_str_040", sub="long_context", ft=5,
      kr="전체 통계와 거액 입금 후 당일 인출 현황에서 상위 기관 거래를 조회하고 FIU 참조 후 STR 작성",
      en="Statistics, same-day-withdrawal summary, query the top institution, FIU lookup, STR",
      vars={},
      why="Institution 159 sends 148 of the 243 type-5 rows and 59 of them fall in 2024, so the "
          "reference from the summary to the query lands on real rows.",
      turns=[
        T(kr="이상거래 유형별 현황을 보여줘.",
          en="Show me the fraud picture by type.",
          tool="get_statistics",
          bind={"frn": R(1, "summary_statistics.fraud_tx_count"),
                "t5": R(1, "fraud_type_distribution[4].count")}),
        T(kr="거액 입금 후 당일 인출 유형의 상세 현황을 봐줘.",
          en="Show me the detail for the same-day-withdrawal-after-large-deposit type.",
          tool="get_fraud_type_summary", args={"fraud_type": 5},
          bind={"t5n": R(2, "total_count"), "t5amt": R(2, "total_amount"),
                "t5bank": R(2, "top_banks[0].bank_id"), "t5bn": R(2, "top_banks[0].count")}),
        T(kr="이 유형이 가장 많은 출금기관의 2024년 해당 유형 거래를 금액 순으로 조회해줘.",
          en="List that institution's 2024 transactions of this type, largest amount first.",
          tool="query_transactions",
          sql=rows("sender_bank = {t5bank} AND fraud_type = 5 AND date BETWEEN 20240101 AND 20241231"),
          conds=[("sender_bank", "=", R(2, "top_banks[0].bank_id")), ("fraud_type", "=", 5),
                 ("date", "BETWEEN", [20240101, 20241231])],
          ctx=(2, "top_banks[0].bank_id", "sql"),
          bind={"n": R(3, "returned_count"), "acc": R(3, "result[0].sender_acc"),
                "amt": R(3, "result[0].amount"), "date": R(3, "result[0].date")}),
        T(kr="거액 입금 후 당일 인출과 관련된 FIU 참고유형도 영어 키워드로 확인해줘.",
          en="Also look up the FIU reference type for this pattern, searching the English catalog.",
          tool="lookup_fiu_reference_types", args={"keyword": "balance certificate"},
          bind={"fiu": R(4, "result[0].description")}),
        T(kr="거액 입금 후 당일 인출로 STR 작성해줘.",
          en="Draft the STR for same-day withdrawal after a large deposit.",
          tool="generate_str",
          args=str_args(5,
            "HOFINET 이상거래 {frn}건 가운데 거액 입금 후 당일 인출 유형은 {t5}건이다. 유형 합계는 "
            "{t5n}건, {t5amt:,}원이고 출금기관 {t5bank:이가} {t5bn}건으로 가장 많다. 이 기관의 "
            "2024년 해당 유형 상위 {n}건 중 최대 건은 {date:date}에 출금계좌 {acc:이가} 이체한 "
            "{amt:,}원이다. FIU 참고유형 가운데 {fiu:ko|과와} 형태가 일치한다. 거액 입금 직후 같은 "
            "규모가 인출되어 거액 입금 후 당일 인출로 판단한다.",
            "Of the {frn} flagged transactions in HOFINET, {t5} are of the "
            "same-day-withdrawal-after-large-deposit type. The type covers {t5n} rows worth "
            "{t5amt:,} KRW, and withdrawal institution {t5bank} leads it with {t5bn}. Among the top "
            "{n} rows of that type at the institution in 2024 the largest is {amt:,} KRW sent by "
            "withdrawal account {acc} on {date:date}. It matches the FIU reference type '{fiu}'. A "
            "large deposit is withdrawn again at the same size, so this is judged a same-day "
            "withdrawal after a large deposit.",
            ["get_statistics", "get_fraud_type_summary", "query_transactions",
            "lookup_fiu_reference_types"])),
      ]),

    # ---------------------------------------------------------------- 041
    S(id="mt_str_041", sub="long_context", ft=4,
      kr="계좌 거래 조회와 예측 후 최다 입금계좌의 수취 프로필과 수집 패턴을 분석해 STR 작성",
      en="Query and predict, then profile the busiest receiving account and its collection pattern, STR",
      vars={"acc": 9000000004236284, "bank": 147},
      why="9000000004236284 has 244 type-4 rows in 2024 and its busiest receiver is "
          "9000000004376103 with 952 transfers.",
      turns=[
        T(kr="출금계좌 {acc}의 2024년 다중거래의 동시 요청 유형 거래를 금액 순으로 조회해줘.",
          en="List the 2024 concurrent-multiple-transaction rows of account {acc}, largest amount first.",
          tool="query_transactions",
          sql=rows("sender_acc = {acc} AND fraud_type = 4 AND date BETWEEN 20240101 AND 20241231"),
          conds=[("sender_acc", "=", 9000000004236284), ("fraud_type", "=", 4),
                 ("date", "BETWEEN", [20240101, 20241231])],
          bind={"n": R(1, "returned_count"), "amt": R(1, "result[0].amount"),
                "date": R(1, "result[0].date"), "rcv": R(1, "result[0].receiver_acc")}),
        T(kr="첫 번째 거래를 예측해봐.",
          en="Score the first transaction.",
          tool="predict_fraud", args=predict_args(1), ctx=(1, "result[0].amount", "amount"),
          bind={"score": R(2, "fraud_risk_score")}),
        T(kr="그 거래의 입금계좌 프로필을 봐줘.",
          en="Profile the receiving account of that transaction.",
          tool="get_receiving_account_profile", args={"account_id": R(1, "result[0].receiver_acc")},
          ctx=(1, "result[0].receiver_acc", "account_id"),
          bind={"snd": R(3, "unique_senders"), "rtx": R(3, "total_txns"),
                "rfr": R(3, "fraud_ratio_percent")}),
        T(kr="이 입금계좌의 자금 수집 패턴도 상대 5곳 이상 기준으로 분석해줘.",
          en="Analyse this receiving account's collection pattern, five or more counterparties.",
          tool="detect_smurfing_network",
          args={"account_id": R(1, "result[0].receiver_acc"), "direction": "inbound",
                "min_counterparts": 5},
          ctx=(1, "result[0].receiver_acc", "account_id"),
          bind={"cp": R(4, "result[0].counterparty_count"), "cavg": R(4, "result[0].avg_amount")}),
        T(kr="다중거래의 동시 요청으로 STR 작성해줘.",
          en="Draft the STR for concurrent multiple transactions.",
          tool="generate_str",
          args=str_args(4,
            "출금계좌 {acc}(출금기관 {bank})의 2024년 다중거래의 동시 요청 유형 상위 {n}건 중 최대 "
            "건은 {date:date}에 입금계좌 {rcv:으로로} 이체한 {amt:,}원이고 예측 모델 위험 점수는 "
            "{score:copula}다. 이 입금계좌는 송금 계좌 {snd}곳에서 {rtx}건을 받았고 이상거래 비율은 "
            "{rfr}%다. 수집 패턴 분석에서 상대 {cp}곳, 건당 평균 {cavg:,.0f}원이 확인된다. 같은 "
            "상대에게 동시에 여러 건이 요청되어 다중거래의 동시 요청으로 판단한다.",
            "Among the top {n} concurrent-multiple-transaction rows of 2024 for withdrawal account "
            "{acc} (institution {bank}) the largest is {amt:,} KRW sent to receiving account {rcv} "
            "on {date:date}, with a model risk score of {score}. That receiving account takes {rtx} "
            "transfers from {snd} sending accounts, with a suspicious-transaction ratio of {rfr}%. "
            "The collection analysis finds {cp} counterparties at {cavg:,.0f} KRW per transfer on "
            "average. Several transfers were requested at once to the same counterparty, so this is "
            "judged a concurrent multiple transaction request.",
            ["query_transactions", "predict_fraud", "get_receiving_account_profile",
            "detect_smurfing_network"])),
      ]),

    # ---------------------------------------------------------------- 042
    S(id="mt_str_042", sub="long_context", ft=2,
      kr="R004 기관집중 알림에서 집중 기관을 특정해 기관 보고서와 유입 이상거래를 조회하고 STR 작성",
      en="R004 concentration alert, report on the concentrated institution, query its inbound fraud, STR",
      vars={},
      why="R004 flags 9000000004237509 first in 2024 with 84.62% of its transfers going to "
          "institution 156, and institution 156 receives 354 type-2 rows in 2024.",
      turns=[
        T(kr="2024년 R004 기관집중거래 알림을 확인해줘.",
          en="Check the R004 institution-concentration alerts for 2024.",
          tool="detect_monitoring_alerts",
          args={"rule_id": "R004", "date_from": 20240101, "date_to": 20241231},
          bind={"racc": R(1, "result[0].sender_acc"), "rtot": R(1, "result[0].total_tx_count"),
                "rmax": R(1, "result[0].max_bank_tx_count"),
                "rpct": R(1, "result[0].concentration_percent"),
                "rbank": R(1, "result[0].concentration_bank")}),
        T(kr="자금이 집중된 그 입금기관의 보고서를 조회해줘.",
          en="Pull the report for the institution the funds concentrate into.",
          tool="get_institution_report", args={"bank_id": R(1, "result[0].concentration_bank")},
          ctx=(1, "result[0].concentration_bank", "bank_id"),
          bind={"itot": R(2, "inbound.total_count"), "ifr": R(2, "inbound.fraud_count"),
                "ifrr": R(2, "inbound.fraud_ratio_percent")}),
        T(kr="이 기관으로 들어온 2024년 신규 수신처 거래 유형 이상거래를 금액 순으로 조회해줘.",
          en="List the 2024 new-counterparty fraud received by this institution, largest amount first.",
          tool="query_transactions",
          sql=rows("receiver_bank = {rbank} AND fraud_type = 2 AND date BETWEEN 20240101 AND 20241231"),
          conds=[("receiver_bank", "=", R(1, "result[0].concentration_bank")),
                 ("fraud_type", "=", 2), ("date", "BETWEEN", [20240101, 20241231])],
          bind={"n": R(3, "returned_count"), "acc": R(3, "result[0].sender_acc"),
                "amt": R(3, "result[0].amount"), "date": R(3, "result[0].date")}),
        T(kr="신규 수신처 거래로 STR 작성해줘.",
          en="Draft the STR for transactions with new counterparties.",
          tool="generate_str",
          args=str_args(2,
            "모니터링 R004에서 출금계좌 {racc}의 거래 {rtot}건 중 {rmax}건({rpct}%)이 입금기관 "
            "{rbank} 한 곳으로 집중됐다. 이 기관의 입금 거래는 {itot}건이고 이상거래는 "
            "{ifr}건({ifrr}%)이다. 2024년 이 기관으로 들어온 신규 수신처 거래 유형 상위 {n}건 중 "
            "최대 건은 {date:date}에 출금계좌 {acc:이가} 이체한 {amt:,}원이다. 거래 이력이 없던 "
            "상대 기관으로 자금이 쏠려 신규 수신처 거래로 판단한다.",
            "The R004 monitoring rule shows {rmax} of the {rtot} transactions of withdrawal account "
            "{racc} ({rpct}%) concentrating on deposit institution {rbank} alone. That institution "
            "receives {itot} transactions, {ifr} of them flagged ({ifrr}%). Among the top {n} "
            "new-counterparty rows that reached it in 2024 the largest is {amt:,} KRW sent by "
            "withdrawal account {acc} on {date:date}. Funds concentrate on a counterpart "
            "institution with no earlier history, so this is judged a transaction with a new "
            "counterparty.",
            ["detect_monitoring_alerts", "get_institution_report", "query_transactions"])),
      ]),

    # ---------------------------------------------------------------- 043
    S(id="mt_str_043", sub="long_context", ft=1,
      kr="계좌 조회와 예측, 네트워크 분석 후 제보 계좌까지의 최단 경로를 확인해 STR 작성",
      en="Query and predict, analyse the network, trace the shortest path to the reported account, STR",
      vars={"acc": 9000000000038694, "bank": 159, "target": 9000000001279469},
      why="9000000000038694 has 18 type-1 rows in 2024 and a real two-hop path to "
          "9000000001279469 through 9000000000036484.",
      turns=[
        T(kr="출금계좌 {acc}의 2024년 갑작스러운 거래패턴의 변화 유형 거래를 금액 순으로 조회해줘.",
          en="List the 2024 sudden-pattern-change rows of account {acc}, largest amount first.",
          tool="query_transactions",
          sql=rows("sender_acc = {acc} AND fraud_type = 1 AND date BETWEEN 20240101 AND 20241231"),
          conds=[("sender_acc", "=", 9000000000038694), ("fraud_type", "=", 1),
                 ("date", "BETWEEN", [20240101, 20241231])],
          bind={"n": R(1, "returned_count"), "amt": R(1, "result[0].amount"),
                "date": R(1, "result[0].date"), "media": R(1, "result[0].media_type")}),
        T(kr="첫 번째 거래를 예측해봐.",
          en="Score the first transaction.",
          tool="predict_fraud", args=predict_args(1), ctx=(1, "result[0].amount", "amount"),
          bind={"score": R(2, "fraud_risk_score")}),
        T(kr="이 계좌의 거래 네트워크를 분석해줘.",
          en="Analyse this account's transaction network.",
          tool="analyze_network", args={"account_id": "{acc}"},
          bind={"neigh": R(3, "connected_account_count"), "nfr": R(3, "fraud_ratio_percent")}),
        T(kr="제보된 계좌 {target}까지 자금이 어떤 경로로 가는지 최단 경로를 찾아줘.",
          en="Trace the shortest path from this account to the reported account {target}.",
          tool="detect_aml_patterns",
          args={"pattern_type": "shortest_path", "account_a": "{acc}", "account_b": "{target}"},
          bind={"hops": R(4, "hops"), "mid": R(4, "path[1]"),
                "e0": R(4, "edges[0].tx_count"), "e1": R(4, "edges[1].tx_count")}),
        T(kr="갑작스러운 거래패턴의 변화로 STR 작성해줘.",
          en="Draft the STR for a sudden change in transaction pattern.",
          tool="generate_str",
          args=str_args(1,
            "출금계좌 {acc}(출금기관 {bank})의 2024년 갑작스러운 거래패턴의 변화 유형 상위 {n}건 중 "
            "최대 건은 {date:date}에 매체구분 {media} 채널로 이체한 {amt:,}원이고 예측 모델 위험 "
            "점수는 {score:copula}다. 1단계 네트워크는 연결 계좌 {neigh}개, 이상거래 비율 {nfr}%다. "
            "제보 계좌 {target}까지는 {hops}단계이며 중간 계좌 {mid:을를} 거친다. 구간 거래는 각각 "
            "{e0}건과 {e1}건이다. 거래 규모와 경로가 종전과 달라 갑작스러운 거래패턴의 변화로 "
            "판단한다.",
            "Among the top {n} sudden-change rows of 2024 for withdrawal account {acc} (institution "
            "{bank}) the largest is {amt:,} KRW sent over media type {media} on {date:date}, with a "
            "model risk score of {score}. Its one-hop network holds {neigh} connected accounts at a "
            "suspicious-transaction ratio of {nfr}%. The reported account {target} is {hops} steps "
            "away, through intermediate account {mid}. The two legs carry {e0} and {e1} "
            "transactions. The size of the transfers and the path they take depart from the earlier "
            "pattern, so this is judged a sudden change in transaction pattern.",
            ["query_transactions", "predict_fraud", "analyze_network", "detect_aml_patterns"])),
      ]),

    # ---------------------------------------------------------------- 044
    S(id="mt_str_044", sub="base", ft=7,
      kr="심야 대량거래 의심 계좌의 프로필·예측·자금 분산 확인 결과 보고 불요 판단",
      en="Profile, predict and check dispersion for a night-time suspicion: no report needed",
      vars={"acc": 9000000004232727, "bank": 134},
      why="9000000004232727 has 40 transactions of at most 100,000 KRW, no labelled fraud and a "
          "model score of 0.0, so the suspicion does not hold.",
      turns=[
        T(kr="계좌 {acc:이가} 심야/새벽 대량 거래로 의심된다는 제보가 들어왔어. 프로필을 봐줘.",
          en="Account {acc} was reported for late-night bulk activity. Show me its profile.",
          tool="get_account_profile", args={"account_id": "{acc}"},
          bind={"tot": R(1, "total_count"), "frn": R(1, "fraud_count"),
                "fr": R(1, "fraud_ratio_percent"), "tamt": R(1, "total_amount"),
                "hours": R(1, "top_hours[0]")}),
        T(kr="이 계좌의 최대 거래는 거래시간대 15, 출금기관 134, 입금기관 155, 자금구분 0, 매체구분 4, 10만원이야. 예측해봐.",
          en="Its largest transaction is time slot 15, sender institution 134, receiver institution "
             "155, fund type 0, media type 4, 100,000 KRW. Score it.",
          tool="predict_fraud",
          args={"time_slot": 15, "sender_bank": 134, "receiver_bank": 155,
                "fund_type": 0, "media_type": 4, "amount": 100000},
          bind={"score": R(2, "fraud_risk_score"), "lvl": R(2, "risk_level")}),
        T(kr="자금 분산 패턴이 있는지 상대 5곳 이상 기준으로 확인해봐.",
          en="Check for a dispersion pattern with a threshold of five or more counterparties.",
          tool="detect_smurfing_network",
          args={"account_id": "{acc}", "direction": "outbound", "min_counterparts": 5},
          bind={"cp": R(3, "result[0].counterparty_count"), "sfr": R(3, "result[0].fraud_count"),
                "savg": R(3, "result[0].avg_amount")}),
        T(kr="STR 작성이 필요한 수준인가?",
          en="Is this at the level where an STR is needed?", abstain=True,
          point_kr="이상거래 라벨이 없고 예측 점수와 금액대가 모두 낮아 보고 불요가 정답",
          point_en="no labelled fraud, a low model score and small amounts, so no report is correct"),
      ]),

    # ---------------------------------------------------------------- 045
    S(id="mt_str_045", sub="long_context", ft=1,
      kr="R001 심야 대량 알림에서 계좌를 특정해 프로필·위험도·기관 보고서를 확인하고 STR 작성",
      en="R001 night-time bulk alert, profile and score the account, institution report, STR",
      vars={},
      why="R001 as redefined (slots 21/0/3, 5,000,000 KRW and above) really flags "
          "9000000004234408's 200,000,000 KRW transfer at slot 21 on 2024-12-10 first; the account "
          "carries 21 type-1 rows.",
      turns=[
        T(kr="2024년 4분기 R001 심야 대량거래 알림을 확인해줘.",
          en="Check the R001 night-time bulk alerts for 2024Q4.",
          tool="detect_monitoring_alerts",
          args={"rule_id": "R001", "date_from": 20241001, "date_to": 20241231},
          bind={"racc": R(1, "result[0].sender_acc"), "rdate": R(1, "result[0].date"),
                "rslot": R(1, "result[0].time_slot"), "ramt": R(1, "result[0].amount"),
                "rbank": R(1, "result[0].sender_bank"), "rn": R(1, "count")}),
        T(kr="가장 금액이 큰 건의 출금계좌 프로필을 봐줘.",
          en="Profile the withdrawal account of the largest hit.",
          tool="get_account_profile", args={"account_id": R(1, "result[0].sender_acc")},
          ctx=(1, "result[0].sender_acc", "account_id"),
          bind={"tot": R(2, "total_count"), "frn": R(2, "fraud_count"),
                "fr": R(2, "fraud_ratio_percent")}),
        T(kr="이 계좌의 위험도 평가도 해줘.",
          en="Score this account's risk as well.",
          tool="score_account_risk", args={"account_id": R(1, "result[0].sender_acc")},
          ctx=(1, "result[0].sender_acc", "account_id"),
          bind={"risk": R(3, "total_score"), "level": R(3, "risk_level"),
                "night": R(3, "components.nighttime_ratio")}),
        T(kr="이 계좌가 속한 출금기관의 보고서도 봐줘.",
          en="Pull the report for the institution this account belongs to.",
          tool="get_institution_report", args={"bank_id": R(1, "result[0].sender_bank")},
          ctx=(1, "result[0].sender_bank", "bank_id"),
          bind={"otot": R(4, "outbound.total_count"), "ofrr": R(4, "outbound.fraud_ratio_percent")}),
        T(kr="갑작스러운 거래패턴의 변화로 STR 작성해줘.",
          en="Draft the STR for a sudden change in transaction pattern.",
          tool="generate_str",
          args=str_args(1,
            "모니터링 R001에서 2024년 4분기 심야 대량거래 알림 상위 {rn}건이 나왔고 최대 건은 "
            "{rdate:date} 거래시간대 {rslot} 구간에 출금기관 {rbank} 소속 출금계좌 {racc:이가} "
            "이체한 {ramt:,}원이다. 이 계좌의 전체 거래는 {tot}건, 이상거래는 {frn}건({fr}%)이고 "
            "위험도 평가는 {risk}점({level}), 심야 거래 비중 지표는 {night:copula}다. 출금기관의 "
            "출금 거래는 {otot}건이고 이상거래 비율은 {ofrr}%다. 영업시간 외 시간대에 거액이 나가 "
            "갑작스러운 거래패턴의 변화로 판단한다.",
            "The R001 monitoring rule returned the top {rn} late-night bulk alerts of the fourth "
            "quarter of 2024; the largest is {ramt:,} KRW sent on {rdate:date} in time slot {rslot} "
            "by withdrawal account {racc} at institution {rbank}. That account has {tot} "
            "transactions in all and {frn} flagged ones ({fr}%), a behavioural risk score of {risk} "
            "({level}) and a night-transaction share indicator of {night}. The institution sends "
            "{otot} transactions at a suspicious-transaction ratio of {ofrr}%. A large amount left "
            "outside business hours, so this is judged a sudden change in transaction pattern.",
            ["detect_monitoring_alerts", "get_account_profile", "score_account_risk",
            "get_institution_report"])),
      ]),

    # ---------------------------------------------------------------- 046
    S(id="mt_str_046", sub="long_context", ft=3,
      kr="계좌 조회와 예측 후 STR 초안을 검증하고 STR 작성",
      en="Query and predict, validate the STR draft, draft the STR",
      vars={"acc": 9000000004242511, "bank": 159, "draft": draft_text(DRAFT_046)},
      why="9000000004242511 has 43 type-3 rows in 2024, which is what the draft in the turn text "
          "reports.",
      turns=[
        T(kr="출금계좌 {acc}의 2024년 분할 거래 유형 내역을 금액 순으로 조회해줘.",
          en="List the 2024 split transactions of account {acc}, largest amount first.",
          tool="query_transactions",
          sql=rows("sender_acc = {acc} AND fraud_type = 3 AND date BETWEEN 20240101 AND 20241231"),
          conds=[("sender_acc", "=", 9000000004242511), ("fraud_type", "=", 3),
                 ("date", "BETWEEN", [20240101, 20241231])],
          bind={"n": R(1, "returned_count"), "tot": R(1, "total_count"),
                "amt": R(1, "result[0].amount"), "date": R(1, "result[0].date"),
                "media": R(1, "result[0].media_type")}),
        T(kr="첫 번째 거래를 예측해봐.",
          en="Score the first transaction.",
          tool="predict_fraud", args=predict_args(1), ctx=(1, "result[0].amount", "amount"),
          bind={"score": R(2, "fraud_risk_score")}),
        T(kr="작성 중인 STR 초안이야. 필수 항목이 빠졌는지 검증해줘. {draft}",
          en="Here is the STR draft I am working on. Check it for missing required fields. {draft}",
          tool="validate_str_fields", args={"str_draft": DRAFT_046},
          bind={"valid": R(3, "valid"), "missing": R(3, "missing_required"),
                "opt": R(3, "missing_optional")}),
        T(kr="분할 거래로 STR 작성해줘.",
          en="Draft the STR for split transactions.",
          tool="generate_str",
          args=str_args(3,
            "출금계좌 {acc}(출금기관 {bank})의 2024년 분할 거래 유형 상위 {n}건 중 최대 건은 "
            "{date:date}에 매체구분 {media} 채널로 이체한 {amt:,}원이고 예측 모델 위험 점수는 "
            "{score:copula}다. 초안 검증 결과 필수 항목 충족 여부는 {valid:copula}고 미기재 필수 "
            "항목은 {missing}, 미기재 선택 항목은 {opt:copula}다. 같은 금액을 여러 상대에게 나눠 "
            "보내는 형태여서 분할 거래로 판단한다.",
            "Among the top {n} split-transaction rows of 2024 for withdrawal account {acc} "
            "(institution {bank}) the largest is {amt:,} KRW sent over media type {media} on "
            "{date:date}, with a model risk score of {score}. The draft validation reports the "
            "required fields as {valid}, the missing required items as {missing} and the missing "
            "optional items as {opt}. The same amount is split across several counterparties, so "
            "this is judged a split transaction.",
            ["query_transactions", "predict_fraud", "validate_str_fields"])),
      ]),

    # ---------------------------------------------------------------- 047
    S(id="mt_str_047", sub="base", ft=4,
      kr="다중거래 동시 요청 의심 계좌의 조회·위험도·네트워크 확인 결과 보고 불요 판단",
      en="Query, score and map a network for a concurrent-transaction suspicion: no report needed",
      vars={"acc": 9000000000027378, "bank": 151},
      why="9000000000027378 has 40 transactions of at most 100,000 KRW spread over 24 counterparties "
          "with no labelled fraud, so the suspicion does not hold.",
      turns=[
        T(kr="계좌 {acc:이가} 다중거래의 동시 요청인지 확인해줘. 거래를 금액 순으로 조회해봐.",
          en="Check whether account {acc} shows concurrent multiple transactions. List its "
             "transactions, largest amount first.",
          tool="query_transactions",
          sql=rows("sender_acc = {acc}"),
          conds=[("sender_acc", "=", 9000000000027378)],
          bind={"n": R(1, "returned_count"), "amt": R(1, "result[0].amount")}),
        T(kr="위험도를 평가해줘.",
          en="Score its risk.",
          tool="score_account_risk", args={"account_id": "{acc}"},
          bind={"risk": R(2, "total_score"), "level": R(2, "risk_level")}),
        T(kr="네트워크도 분석해봐.",
          en="Analyse the network too.",
          tool="analyze_network", args={"account_id": "{acc}"},
          bind={"neigh": R(3, "connected_account_count"), "nfrn": R(3, "fraud_tx_count"),
                "namt": R(3, "total_amount")}),
        T(kr="다중거래의 동시 요청으로 STR을 작성해야 할까?",
          en="Should this be reported as concurrent multiple transactions?", abstain=True,
          point_kr="네트워크 이상거래가 0건이고 금액대가 낮아 보고 불요가 정답",
          point_en="no fraud in the network and small amounts, so no report is correct"),
      ]),

    # ---------------------------------------------------------------- 048
    S(id="mt_str_048", sub="long_context", ft=7,
      kr="FIU 참고유형 확인 후 심야 대량 거래 계좌와 최다 입금계좌를 분석해 STR 작성",
      en="FIU reference type, night-time bulk account, its busiest receiver, risk score, STR",
      vars={"acc": 9000000004242392, "bank": 159},
      why="9000000004242392 holds 7 type-7 rows and 2,626 transactions in the 21 slot, and its "
          "type-7 rows all go to 9000000004421588.",
      turns=[
        T(kr="심야 시간을 포함한 대량 이체와 관련된 FIU 참고유형을 영어 키워드로 확인해줘.",
          en="Look up the FIU reference type for bulk transfers including night hours, searching "
             "the English catalog.",
          tool="lookup_fiu_reference_types", args={"keyword": "bulk"},
          bind={"fiu": R(1, "result[0].description"), "fiu_n": R(1, "count")}),
        T(kr="출금계좌 {acc}의 심야/새벽 대량 거래 유형 내역을 금액 순으로 조회해줘.",
          en="List the late-night bulk transactions of account {acc}, largest amount first.",
          tool="query_transactions",
          sql=rows("sender_acc = {acc} AND fraud_type = 7", limit=10),
          conds=[("sender_acc", "=", 9000000004242392), ("fraud_type", "=", 7)],
          bind={"n": R(2, "returned_count"), "amt": R(2, "result[0].amount"),
                "date": R(2, "result[0].date"), "slot": R(2, "result[0].time_slot"),
                "rcv": R(2, "result[0].receiver_acc")}),
        T(kr="가장 큰 건의 입금계좌 프로필을 봐줘.",
          en="Profile the receiving account of the largest one.",
          tool="get_receiving_account_profile", args={"account_id": R(2, "result[0].receiver_acc")},
          ctx=(2, "result[0].receiver_acc", "account_id"),
          bind={"snd": R(3, "unique_senders"), "rtx": R(3, "total_txns"),
                "rfr": R(3, "fraud_ratio_percent")}),
        T(kr="출금계좌의 위험도를 평가해줘.",
          en="Score the withdrawal account's risk.",
          tool="score_account_risk", args={"account_id": "{acc}"},
          bind={"risk": R(4, "total_score"), "level": R(4, "risk_level"),
                "night": R(4, "components.nighttime_ratio")}),
        T(kr="심야/새벽 대량 거래로 STR 작성해줘.",
          en="Draft the STR for late-night bulk transactions.",
          tool="generate_str",
          args=str_args(7,
            "FIU 참고유형 검색에서 {fiu_n}건이 나왔고 {fiu:ko|이가} 이 사안과 같은 형태다. 출금계좌 "
            "{acc}(출금기관 {bank})의 심야/새벽 대량 거래 유형은 상위 {n}건이고 최대 건은 "
            "{date:date} 거래시간대 {slot} 구간에 입금계좌 {rcv:으로로} 이체한 {amt:,}원이다. 이 "
            "입금계좌는 송금 계좌 {snd}곳에서 {rtx}건을 받았고 이상거래 비율은 {rfr}%다. 출금계좌 "
            "위험도는 {risk}점({level}), 심야 거래 비중 지표는 {night:copula}다. 영업시간 외 "
            "시간대에 거액이 한 상대로 반복되어 심야/새벽 대량 거래로 판단한다.",
            "The FIU reference lookup returned {fiu_n} rows, and '{fiu}' matches this case. "
            "Withdrawal account {acc} (institution {bank}) carries {n} late-night/early-morning "
            "bulk rows; the largest is {amt:,} KRW sent to receiving account {rcv} on {date:date} "
            "in time slot {slot}. That receiving account takes {rtx} transfers from {snd} sending "
            "accounts, with a suspicious-transaction ratio of {rfr}%. The withdrawal account's "
            "behavioural risk score is {risk} ({level}) and its night-transaction share indicator "
            "is {night}. Large amounts repeat to one counterparty outside business hours, so this "
            "is judged a late-night/early-morning bulk transaction.",
            ["lookup_fiu_reference_types", "query_transactions", "get_receiving_account_profile",
            "score_account_risk"])),
      ]),

    # ---------------------------------------------------------------- 049
    S(id="mt_str_049", sub="long_context", ft=3,
      kr="R003 동일 금액 반복 알림에서 계좌를 특정해 프로필·CTR·용어 확인을 거쳐 STR 작성",
      en="R003 repeated-amount alert, profile the account, CTR check, glossary, STR",
      vars={},
      why="R003 as redefined (the same amount of 2,000,000 KRW or more, three times or more) flags "
          "9000000004390593 first: 2,126 transfers of exactly 4,000,000 KRW; the account carries "
          "616 type-3 rows.",
      turns=[
        T(kr="R003 동일 금액 반복 알림을 확인해줘.",
          en="Check the R003 repeated-identical-amount alerts.",
          tool="detect_monitoring_alerts", args={"rule_id": "R003"},
          bind={"racc": R(1, "result[0].sender_acc"), "ramt": R(1, "result[0].amount"),
                "rrep": R(1, "result[0].repeat_count"), "rtot": R(1, "result[0].total_amount"),
                "rrcv": R(1, "result[0].receiver_count")}),
        T(kr="가장 반복이 많은 계좌의 프로필을 봐줘.",
          en="Profile the account with the most repeats.",
          tool="get_account_profile", args={"account_id": R(1, "result[0].sender_acc")},
          ctx=(1, "result[0].sender_acc", "account_id"),
          bind={"tot": R(2, "total_count"), "frn": R(2, "fraud_count"),
                "fr": R(2, "fraud_ratio_percent")}),
        T(kr="2024년에 분할거래 의심 건이 있는지 CTR 기준으로 확인해줘.",
          en="Check the 2024 structuring candidates with the CTR rule.",
          tool="detect_ctr_candidates",
          args={"mode": "structuring", "date_from": 20240101, "date_to": 20241231},
          bind={"cn": R(3, "count"), "cacc": R(3, "result[0].sender_acc"),
                "ctx_n": R(3, "result[0].tx_count"), "camt": R(3, "result[0].total_amount")}),
        T(kr="AML 용어집의 Structuring 항목도 무슨 뜻인지 설명해줘.",
          en="Explain what structuring means as well.",
          tool="get_aml_glossary", args={"term": "Structuring"},
          bind={"gdef": R(4, "definition")}),
        T(kr="분할 거래로 STR 작성해줘.",
          en="Draft the STR for split transactions.",
          tool="generate_str",
          args=str_args(3,
            "모니터링 R003에서 출금계좌 {racc:이가} {ramt:,}원을 {rrep}회, 상대 계좌 {rrcv}곳에 "
            "반복 이체해 합계 {rtot:,}원이 확인된다. 이 계좌의 전체 거래는 {tot}건이고 이상거래는 "
            "{frn}건({fr}%)이다. 2024년 CTR 분할거래 조회 상위 {cn}건 가운데 최다는 {cacc:이가} "
            "하루 {ctx_n}건, {camt:,}원이다. structuring은 {gdef:ko}. 동일 금액을 반복해 다수 상대에게 "
            "보내는 형태여서 분할 거래로 판단한다.",
            "The R003 monitoring rule shows withdrawal account {racc} sending {ramt:,} KRW {rrep} "
            "times to {rrcv} counterparty accounts, {rtot:,} KRW in all. The account has {tot} "
            "transactions in all and {frn} flagged ones ({fr}%). A 2024 CTR structuring query "
            "returned {cn} rows, the busiest being {ctx_n} transfers worth {camt:,} KRW in one day "
            "by account {cacc}. Structuring is defined as follows. {gdef} The same amount goes "
            "repeatedly to many counterparties, so this is judged a split transaction.",
            ["detect_monitoring_alerts", "get_account_profile", "detect_ctr_candidates",
            "get_aml_glossary"])),
      ]),

    # ---------------------------------------------------------------- 050
    S(id="mt_str_050", sub="long_context", ft=1,
      kr="계좌 조회와 예측, 네트워크·위험도 평가, FIU 참조를 모두 거친 6턴 STR 작성",
      en="Query, predict, network, risk score and FIU lookup across six turns, then the STR",
      vars={"acc": 9000000000017766, "bank": 134},
      why="9000000000017766 has 24 type-1 rows at institution 134 and 288 counterparties, so every "
          "one of the five analysis turns returns data.",
      turns=[
        T(kr="출금계좌 {acc:이가} 갑작스러운 거래패턴의 변화로 의심돼. 해당 유형 거래를 금액 순으로 조회해줘.",
          en="Account {acc} is suspected of a sudden change in transaction pattern. List its rows "
             "of that type, largest amount first.",
          tool="query_transactions",
          sql=rows("sender_acc = {acc} AND fraud_type = 1"),
          conds=[("sender_acc", "=", 9000000000017766), ("fraud_type", "=", 1)],
          bind={"n": R(1, "returned_count"), "amt": R(1, "result[0].amount"),
                "date": R(1, "result[0].date"), "rcv": R(1, "result[0].receiver_acc")}),
        T(kr="첫 번째 거래를 예측해봐.",
          en="Score the first transaction.",
          tool="predict_fraud", args=predict_args(1), ctx=(1, "result[0].amount", "amount"),
          bind={"score": R(2, "fraud_risk_score"), "lvl": R(2, "risk_level")}),
        T(kr="이 계좌의 네트워크를 분석해줘.",
          en="Analyse this account's network.",
          tool="analyze_network", args={"account_id": "{acc}"},
          bind={"neigh": R(3, "connected_account_count"), "nfrn": R(3, "fraud_tx_count"),
                "nfr": R(3, "fraud_ratio_percent")}),
        T(kr="위험도도 평가해줘.",
          en="Score its risk too.",
          tool="score_account_risk", args={"account_id": "{acc}"},
          bind={"risk": R(4, "total_score"), "level": R(4, "risk_level"),
                "amta": R(4, "components.amount_anomaly")}),
        T(kr="받은 자금을 제3자에게 다시 보내는 형태의 FIU 참고유형도 영어 키워드로 확인해줘.",
          en="Also look up the FIU reference type for passing received funds on to a third "
             "party, searching the English catalog.",
          tool="lookup_fiu_reference_types", args={"keyword": "third party"},
          bind={"fiu": R(5, "result[0].description"), "fiu_n": R(5, "count")}),
        T(kr="갑작스러운 거래패턴의 변화로 STR 작성해줘.",
          en="Draft the STR for a sudden change in transaction pattern.",
          tool="generate_str",
          args=str_args(1,
            "출금계좌 {acc}(출금기관 {bank})의 갑작스러운 거래패턴의 변화 유형 이상거래 상위 {n}건 "
            "중 최대 건은 {date:date}에 입금계좌 {rcv:으로로} 이체한 {amt:,}원이고 예측 모델 위험 "
            "점수는 {score}, 위험 수준은 {lvl}이다. 1단계 네트워크는 연결 계좌 {neigh}개, 이상거래 "
            "{nfrn}건({nfr}%)이다. 위험도 평가는 {risk}점({level})이고 금액 이상치 지표는 "
            "{amta:copula}다. FIU 참고유형 검색 {fiu_n}건 중 {fiu:ko|과와} 형태가 겹친다. 거래 "
            "규모와 상대 구성이 종전과 달라 갑작스러운 거래패턴의 변화로 판단한다.",
            "Among the top {n} sudden-change rows of withdrawal account {acc} (institution {bank}) "
            "the largest is {amt:,} KRW sent to receiving account {rcv} on {date:date}, with a "
            "model risk score of {score} at risk level {lvl}. Its one-hop network holds {neigh} "
            "connected accounts and {nfrn} flagged transactions ({nfr}%). Its behavioural risk "
            "score is {risk} ({level}) and its amount-anomaly indicator is {amta}. Of the {fiu_n} "
            "FIU reference rows found, '{fiu}' overlaps with this case. The size of the transfers "
            "and the mix of counterparties departed from the earlier pattern, so this is judged a "
            "sudden change in transaction pattern.",
            ["query_transactions", "predict_fraud", "analyze_network", "score_account_risk",
            "lookup_fiu_reference_types"])),
      ]),
]
