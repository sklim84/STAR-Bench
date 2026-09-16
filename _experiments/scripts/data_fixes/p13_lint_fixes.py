"""Pass 13 - what the pre-flight checks found after every other pass had run.

`lint_benchmarks.py` and `verify_gold_calls.py` are the gates, so anything they
report is fixed here rather than by hand, and re-running the whole pipeline
reproduces the fix.

Eight reference queries returned no rows, which means the question asked for
something HOFINET does not hold: the smallest flagged amount is 2,000,000 won, the
03:00 slot carries no flagged transaction at all, twelve sending and seven
receiving institutions have none either, and fund type 3 never occurs with mobile
phone on a flagged transaction. Each question moves to a value the data holds.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both

# case_id -> (kr question, en question, gold patch as {tool: {key: value}}, reference sql, why)
EMPTY_RESULT = {
    "st_qt_005": ("오전 6시대(거래시간대 6)에 발생한 이상거래를 조회해줘",
                  "Please query the suspicious transactions that occurred in the 6 AM time slot "
                  "(time slot 6).",
                  {"time_slot": 6},
                  "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE time_slot = 6 "
                  "AND is_fraud = 1 ORDER BY date DESC LIMIT 100",
                  "time slot 3 carries 116 transactions in total and none of them is flagged, so the "
                  "question had no answer; slot 6 carries 495 flagged transactions"),
    "st_qt_014": ("입금금융회사 133으로 들어온 이상거래 중 최근 20건을 보여줘",
                  "Show me the 20 most recent suspicious transactions that came into deposit "
                  "institution 133.",
                  {"receiver_bank": 133},
                  "SELECT date, sender_bank, sender_acc, amount FROM hofinet WHERE receiver_bank = 133 "
                  "AND is_fraud = 1 ORDER BY date DESC LIMIT 20",
                  "institution 119 receives no flagged transaction at all (seven receiving institutions "
                  "do not); 133 receives 1,831"),
    "st_qt_020": ("출금사 159에서 분할 거래(이상거래유형 3) 거래 중 거래금액 합계가 가장 큰 계좌를 찾아줘",
                  "At withdrawal institution 159, please find the account with the largest total amount "
                  "among the split transaction (type 3) transactions.",
                  {"sender_bank": 159},
                  "SELECT sender_acc, SUM(amount) AS total_amount FROM hofinet WHERE sender_bank = 159 "
                  "AND fraud_type = 3 GROUP BY sender_acc ORDER BY total_amount DESC LIMIT 5",
                  "institution 118 has no type 3 transaction; 159 has 1,464"),
    "st_qt_021": ("기타 매체(매체구분 6)를 통한 기타(자금구분 3) 이상거래를 조회해줘",
                  "Please query the suspicious transactions with fund type 3 (other) made via other "
                  "media (media type 6).",
                  {"media_type": 6},
                  "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE media_type = 6 "
                  "AND fund_type = 3 AND is_fraud = 1 ORDER BY date DESC LIMIT 100",
                  "fund type 3 never occurs with mobile phone on a flagged transaction; with other "
                  "media it occurs 162 times"),
    "st_qt_030": ("거래금액이 300만원 이하인 이상거래를 조회해줘",
                  "Please query the suspicious transactions with an amount of 3,000,000 won or less.",
                  {"amount": 3000000},
                  "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE amount <= 3000000 "
                  "AND is_fraud = 1 ORDER BY amount DESC LIMIT 100",
                  "the smallest flagged amount in HOFINET is 2,000,000 won, so 'at most 1,000,000' "
                  "selects nothing; at most 3,000,000 selects 142"),
    "st_qt_043": ("이상거래 중 거래금액이 200만원 이하인 최소 구간 거래를 조회해줘",
                  "Please query the suspicious transactions in the lowest amount band, 2,000,000 won or "
                  "less.",
                  {"amount": 2000000},
                  "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE amount <= 2000000 "
                  "AND is_fraud = 1 ORDER BY amount LIMIT 100",
                  "the smallest flagged amount is 2,000,000 won, so 'at most 50,000' selects nothing"),
    "st_mtool_070": ("금융회사 151의 기관 리포트를 확인하고, 해당 기관 이상거래를 SQL로 조회해줘",
                     "Please check the institution report for financial institution 151 and query that "
                     "institution's suspicious transactions with SQL.",
                     {"sender_bank": 151, "bank_id": 151},
                     "SELECT date, receiver_bank, amount, fraud_type FROM hofinet WHERE sender_bank = 151 "
                     "AND is_fraud = 1 ORDER BY date DESC LIMIT 100",
                     "institution 102 sends no flagged transaction (twelve sending institutions do not); "
                     "151 sends 1,699"),
    "st_mtool_086": ("출금금융회사 133의 이상거래를 조회하고, 예측 확률도 구해줘. 거래시간대 12, 출금사 133, 입금사 122, 기타(자금구분 3), 휴대전화(매체구분 4), 200만원.",
                     "Please query the suspicious transactions of withdrawal financial institution 133 "
                     "and also get the prediction probability: time slot 12, withdrawal institution 133, "
                     "deposit institution 122, other (fund type 3), mobile phone (media type 4), "
                     "2,000,000 won.",
                     {"sender_bank": 133},
                     "SELECT date, receiver_bank, amount, fraud_type FROM hofinet WHERE sender_bank = 133 "
                     "AND is_fraud = 1 ORDER BY date DESC LIMIT 100",
                     "institution 107 sends no flagged transaction; 133 sends 1,239"),
}

EN_QUESTION = {
    "st_gta_017": ("Please analyze the trend of the monthly transaction status.",
                   "the EN question was word for word st_gta_013's, although the KR questions differ "
                   "('월별로 거래 추세' against '월간 거래 현황 추이'), so the EN arm held a duplicate "
                   "the KR arm did not (L1-025, duplicate_question)"),
}


def apply(kr: Bench, en: Bench, log: ChangeLog) -> None:
    kr_by, en_by = kr.by_id(), en.by_id()
    for case_id, (text, why) in EN_QUESTION.items():
        log.set_field(en_by[case_id], "en", "question", text, "C1-011/L1-025", why)

    for case_id, (kr_text, en_text, patch, sql, why) in EMPTY_RESULT.items():
        for bench_by, lang, text in ((kr_by, "kr", kr_text), (en_by, "en", en_text)):
            case = bench_by[case_id]
            log.set_field(case, lang, "question", text, "C1-003", why)
            gold = copy.deepcopy(case["expected"])
            for tool, checks in gold["param_checks"].items():
                for key, value in patch.items():
                    if key in checks:
                        checks[key] = value
                for cond in checks.get("sql_conditions") or []:
                    if cond["column"] in patch:
                        cond["value"] = patch[cond["column"]]
            gold["reference_calls"]["query_transactions"]["sql"] = sql
            log.set_field(case, lang, "expected", gold, "C1-003", why)


def main() -> int:
    kr, en = both()
    log = ChangeLog("p13_lint_fixes", "Fix what the pre-flight linter reported (C1-011).")
    apply(kr, en, log)
    kr.save()
    en.save()
    print(log.report())
    print(f"log: {log.write()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
