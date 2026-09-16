"""Pass 09 - Contract 1 for the SQL cases: sql_conditions and an executable reference SQL.

`sql_contains` was a substring test, so `["4"]` was satisfied by the year 2024 or
by `LIMIT 10`, and a keyword inside a comment counted as a condition (L4-015).
Contract 1 replaces it with `sql_conditions`, a list of restricting predicates the
scorer reads out of the statement, and requires every case that expects
`query_transactions` to carry `expected.reference_calls.query_transactions.sql`:
the statement the gold answer runs, so the gold call is executable and the oracle
history has a real result.

Three questions also asked for fraud with fund type 4, which carries no fraud
label anywhere in HOFINET, so their reference SQL would return nothing (C1-003).
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both

FRAUD = {"column": "is_fraud", "op": "=", "value": 1}


def C(column, op, value):
    return {"column": column, "op": op, "value": value}


# case_id -> (conditions, reference sql)
SQL = {
    "st_ap_irr_007": ([C("sender_acc", "=", 9000000000017070)],
        "SELECT date, time_slot, receiver_bank, receiver_acc, amount, is_fraud FROM hofinet "
        "WHERE sender_acc = 9000000000017070 ORDER BY date DESC LIMIT 100"),
    "st_gir_irr_006": ([FRAUD],
        "SELECT sender_bank, COUNT(*) AS fraud_count FROM hofinet WHERE is_fraud = 1 "
        "GROUP BY sender_bank ORDER BY fraud_count DESC LIMIT 10"),
    "st_mtool_001": ([C("sender_bank", "=", 134), FRAUD],
        "SELECT sender_acc, COUNT(*) AS fraud_count FROM hofinet WHERE sender_bank = 134 "
        "AND is_fraud = 1 GROUP BY sender_acc ORDER BY fraud_count DESC LIMIT 10"),
    "st_mtool_002": ([FRAUD],
        "SELECT sender_bank, COUNT(*) AS fraud_count FROM hofinet WHERE is_fraud = 1 "
        "GROUP BY sender_bank ORDER BY fraud_count DESC LIMIT 10"),
    "st_mtool_006": ([C("sender_bank", "=", 134), FRAUD],
        "SELECT date, time_slot, receiver_bank, amount, fraud_type FROM hofinet "
        "WHERE sender_bank = 134 AND is_fraud = 1 ORDER BY date DESC LIMIT 100"),
    "st_mtool_007": ([C("sender_acc", "=", 9000000000036484)],
        "SELECT date, time_slot, receiver_bank, amount, is_fraud FROM hofinet "
        "WHERE sender_acc = 9000000000036484 ORDER BY date DESC LIMIT 100"),
    "st_mtool_008": ([C("sender_bank", "=", 123), FRAUD],
        "SELECT date, time_slot, sender_acc, receiver_acc, amount FROM hofinet "
        "WHERE sender_bank = 123 AND is_fraud = 1 ORDER BY amount DESC LIMIT 100"),
    "st_mtool_010": ([C("sender_bank", "=", 134), FRAUD],
        "SELECT date, sender_acc, receiver_acc, amount FROM hofinet WHERE sender_bank = 134 "
        "AND is_fraud = 1 ORDER BY date DESC LIMIT 100"),
    "st_mtool_011": ([C("fraud_type", "=", 4)],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE fraud_type = 4 "
        "ORDER BY date DESC LIMIT 100"),
    "st_mtool_015": ([C("fraud_type", "=", 4)],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE fraud_type = 4 "
        "ORDER BY date DESC LIMIT 100"),
    "st_mtool_017": ([C("sender_bank", "=", 147), FRAUD],
        "SELECT date, receiver_bank, amount, fraud_type FROM hofinet WHERE sender_bank = 147 "
        "AND is_fraud = 1 ORDER BY date DESC LIMIT 100"),
    "st_mtool_026": ([C("sender_bank", "=", 158), FRAUD],
        "SELECT date, receiver_bank, amount, fraud_type FROM hofinet WHERE sender_bank = 158 "
        "AND is_fraud = 1 ORDER BY date DESC LIMIT 100"),
    "st_mtool_041": ([C("sender_acc", "=", 9000000004388166)],
        "SELECT date, receiver_acc, amount, is_fraud FROM hofinet "
        "WHERE sender_acc = 9000000004388166 ORDER BY date DESC LIMIT 100"),
    "st_mtool_056": ([C("receiver_acc", "=", 9000000000034017)],
        "SELECT date, sender_bank, sender_acc, amount, is_fraud FROM hofinet "
        "WHERE receiver_acc = 9000000000034017 ORDER BY date DESC LIMIT 100"),
    "st_mtool_062": ([C("sender_bank", "=", 150), FRAUD],
        "SELECT date, receiver_bank, amount, fraud_type FROM hofinet WHERE sender_bank = 150 "
        "AND is_fraud = 1 ORDER BY date DESC LIMIT 100"),
    "st_mtool_063": ([C("fraud_type", "=", 4)],
        "SELECT date, sender_acc, receiver_acc, amount FROM hofinet WHERE fraud_type = 4 "
        "ORDER BY amount DESC LIMIT 100"),
    "st_mtool_069": ([C("fraud_type", "=", 3)],
        "SELECT date, sender_acc, receiver_acc, amount FROM hofinet WHERE fraud_type = 3 "
        "ORDER BY date DESC LIMIT 100"),
    "st_mtool_070": ([C("sender_bank", "=", 102), FRAUD],
        "SELECT date, receiver_bank, amount, fraud_type FROM hofinet WHERE sender_bank = 102 "
        "AND is_fraud = 1 ORDER BY date DESC LIMIT 100"),
    "st_mtool_081": ([C("sender_bank", "=", 134), FRAUD],
        "SELECT date, receiver_bank, amount, fraud_type FROM hofinet WHERE sender_bank = 134 "
        "AND is_fraud = 1 ORDER BY date DESC LIMIT 100"),
    "st_mtool_082": ([C("fraud_type", "=", 5)],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE fraud_type = 5 "
        "ORDER BY date DESC LIMIT 20"),
    "st_mtool_086": ([C("sender_bank", "=", 107), FRAUD],
        "SELECT date, receiver_bank, amount, fraud_type FROM hofinet WHERE sender_bank = 107 "
        "AND is_fraud = 1 ORDER BY date DESC LIMIT 100"),
    "st_mtool_088": ([C("fraud_type", "=", 7)],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE fraud_type = 7 "
        "ORDER BY date DESC LIMIT 100"),
    "st_qt_001": ([C("sender_bank", "=", 134), FRAUD],
        "SELECT COUNT(*) AS fraud_count FROM hofinet WHERE sender_bank = 134 AND is_fraud = 1"),
    "st_qt_002": ([C("fraud_type", "=", 4)],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE fraud_type = 4 LIMIT 10"),
    "st_qt_003": ([C("media_type", "=", 2), FRAUD],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE media_type = 2 "
        "AND is_fraud = 1 ORDER BY date DESC LIMIT 100"),
    "st_qt_004": ([C("amount", ">=", 10000000), FRAUD],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE amount >= 10000000 "
        "AND is_fraud = 1 ORDER BY amount DESC LIMIT 100"),
    "st_qt_005": ([C("time_slot", "=", 3), FRAUD],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE time_slot = 3 "
        "AND is_fraud = 1 ORDER BY date DESC LIMIT 100"),
    "st_qt_006": ([C("fund_type", "=", 3), FRAUD],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE fund_type = 3 "
        "AND is_fraud = 1 ORDER BY date DESC LIMIT 100"),
    "st_qt_007": ([C("sender_acc", "=", 9000000000024638)],
        "SELECT date, time_slot, receiver_bank, amount, is_fraud FROM hofinet "
        "WHERE sender_acc = 9000000000024638 ORDER BY date DESC LIMIT 100"),
    "st_qt_008": ([FRAUD],
        "SELECT sender_bank, COUNT(*) AS fraud_count FROM hofinet WHERE is_fraud = 1 "
        "GROUP BY sender_bank ORDER BY fraud_count DESC"),
    "st_qt_009": ([FRAUD],
        "SELECT fraud_type, AVG(amount) AS avg_amount FROM hofinet WHERE is_fraud = 1 "
        "GROUP BY fraud_type ORDER BY fraud_type"),
    "st_qt_010": ([C("fraud_type", "=", 3)],
        "SELECT date, sender_acc, receiver_acc, amount FROM hofinet WHERE fraud_type = 3 "
        "ORDER BY amount DESC LIMIT 100"),
    "st_qt_011": ([C("media_type", "=", 4), FRAUD],
        "SELECT sender_acc, SUM(amount) AS total_amount FROM hofinet WHERE media_type = 4 "
        "AND is_fraud = 1 GROUP BY sender_acc ORDER BY total_amount DESC LIMIT 5"),
    "st_qt_012": ([C("date", ">=", 20240101), C("date", "<=", 20240331), FRAUD],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet "
        "WHERE date BETWEEN 20240101 AND 20240331 AND is_fraud = 1 ORDER BY date LIMIT 100"),
    "st_qt_013": ([C("fraud_type", "IN", [1, 4])],
        "SELECT fraud_type, date, sender_bank, receiver_bank, amount FROM hofinet "
        "WHERE fraud_type IN (1, 4) ORDER BY date DESC LIMIT 100"),
    "st_qt_014": ([C("receiver_bank", "=", 119), FRAUD],
        "SELECT date, sender_bank, sender_acc, amount FROM hofinet WHERE receiver_bank = 119 "
        "AND is_fraud = 1 ORDER BY date DESC LIMIT 20"),
    "st_qt_015": ([FRAUD],
        "SELECT time_slot, COUNT(*) AS fraud_count FROM hofinet WHERE is_fraud = 1 "
        "GROUP BY time_slot ORDER BY fraud_count DESC"),
    "st_qt_016": ([C("fraud_type", "=", 1)],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE fraud_type = 1 "
        "ORDER BY date DESC LIMIT 30"),
    "st_qt_017": ([C("receiver_acc", "=", 9000000000036484), FRAUD],
        "SELECT date, sender_bank, sender_acc, amount FROM hofinet "
        "WHERE receiver_acc = 9000000000036484 AND is_fraud = 1 ORDER BY date DESC LIMIT 100"),
    "st_qt_018": ([C("amount", ">=", 50000000), FRAUD],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE amount >= 50000000 "
        "AND is_fraud = 1 ORDER BY amount DESC LIMIT 100"),
    "st_qt_019": ([FRAUD],
        "SELECT media_type, COUNT(*) AS fraud_count FROM hofinet WHERE is_fraud = 1 "
        "GROUP BY media_type ORDER BY fraud_count DESC"),
    "st_qt_020": ([C("sender_bank", "=", 118), C("fraud_type", "=", 3)],
        "SELECT sender_acc, SUM(amount) AS total_amount FROM hofinet WHERE sender_bank = 118 "
        "AND fraud_type = 3 GROUP BY sender_acc ORDER BY total_amount DESC LIMIT 5"),
    "st_qt_021": ([C("media_type", "=", 4), C("fund_type", "=", 3), FRAUD],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE media_type = 4 "
        "AND fund_type = 3 AND is_fraud = 1 ORDER BY date DESC LIMIT 100"),
    "st_qt_022": ([C("date", ">=", 20230101), C("date", "<=", 20231231), FRAUD],
        "SELECT date / 100 AS month, COUNT(*) AS fraud_count FROM hofinet "
        "WHERE date BETWEEN 20230101 AND 20231231 AND is_fraud = 1 GROUP BY month ORDER BY month"),
    "st_qt_023": ([FRAUD],
        "SELECT sender_bank, SUM(amount) AS total_amount FROM hofinet WHERE is_fraud = 1 "
        "GROUP BY sender_bank ORDER BY total_amount DESC LIMIT 10"),
    "st_qt_024": ([C("time_slot", "=", 21), FRAUD],
        "SELECT COUNT(*) AS fraud_count FROM hofinet WHERE time_slot = 21 AND is_fraud = 1"),
    "st_qt_025": ([C("fraud_type", "=", 5)],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE fraud_type = 5 "
        "AND amount >= (SELECT AVG(amount) FROM hofinet WHERE fraud_type = 5) "
        "ORDER BY amount DESC LIMIT 100"),
    "st_qt_026": ([C("receiver_bank", "=", 122), FRAUD],
        "SELECT date, sender_bank, sender_acc, amount FROM hofinet WHERE receiver_bank = 122 "
        "AND is_fraud = 1 ORDER BY amount DESC LIMIT 100"),
    "st_qt_027": ([C("fraud_type", "=", 3)],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE fraud_type = 3 LIMIT 20"),
    "st_qt_028": ([C("sender_bank", "=", 128)],
        "SELECT date, time_slot, receiver_bank, amount, is_fraud FROM hofinet "
        "WHERE sender_bank = 128 ORDER BY date DESC LIMIT 100"),
    "st_qt_029": ([C("receiver_acc", "=", 9000000000024638)],
        "SELECT date, sender_bank, sender_acc, amount, is_fraud FROM hofinet "
        "WHERE receiver_acc = 9000000000024638 ORDER BY date DESC LIMIT 100"),
    "st_qt_030": ([C("amount", "<=", 1000000), FRAUD],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE amount <= 1000000 "
        "AND is_fraud = 1 ORDER BY amount DESC LIMIT 100"),
    "st_qt_031": ([C("fraud_type", "=", 2)],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE fraud_type = 2 "
        "ORDER BY date DESC LIMIT 50"),
    "st_qt_032": ([C("fund_type", "=", 1), FRAUD],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE fund_type = 1 "
        "AND is_fraud = 1 ORDER BY date DESC LIMIT 100"),
    "st_qt_033": ([C("date", ">=", 20221001), C("date", "<=", 20221231), FRAUD],
        "SELECT COUNT(*) AS fraud_count FROM hofinet WHERE date BETWEEN 20221001 AND 20221231 "
        "AND is_fraud = 1"),
    "st_qt_034": ([FRAUD],
        "SELECT receiver_bank, SUM(amount) AS total_amount FROM hofinet WHERE is_fraud = 1 "
        "GROUP BY receiver_bank ORDER BY total_amount DESC"),
    "st_qt_035": ([FRAUD],
        "SELECT sender_acc, COUNT(*) AS fraud_count FROM hofinet WHERE is_fraud = 1 "
        "GROUP BY sender_acc ORDER BY fraud_count DESC LIMIT 10"),
    "st_qt_036": ([C("fraud_type", "=", 1)],
        "SELECT MAX(amount) AS max_amount, MIN(amount) AS min_amount FROM hofinet WHERE fraud_type = 1"),
    "st_qt_037": ([C("media_type", "IN", [3, 4]), FRAUD],
        "SELECT media_type, date, sender_bank, receiver_bank, amount FROM hofinet "
        "WHERE media_type IN (3, 4) AND is_fraud = 1 ORDER BY date DESC LIMIT 100"),
    "st_qt_038": ([FRAUD],
        "SELECT fraud_type, COUNT(*) AS fraud_count, SUM(amount) AS total_amount FROM hofinet "
        "WHERE is_fraud = 1 GROUP BY fraud_type ORDER BY total_amount DESC"),
    "st_qt_039": ([C("sender_bank", "=", 134), C("date", ">=", 20230101), C("date", "<=", 20230630), FRAUD],
        "SELECT COUNT(*) AS fraud_count FROM hofinet WHERE sender_bank = 134 "
        "AND date BETWEEN 20230101 AND 20230630 AND is_fraud = 1 "
        "AND amount >= (SELECT AVG(amount) FROM hofinet WHERE sender_bank = 134 "
        "AND date BETWEEN 20230101 AND 20230630 AND is_fraud = 1)"),
    "st_qt_040": ([FRAUD],
        "SELECT sender_acc, date, COUNT(*) AS fraud_count FROM hofinet WHERE is_fraud = 1 "
        "GROUP BY sender_acc, date HAVING COUNT(*) >= 3 ORDER BY fraud_count DESC LIMIT 100"),
    "st_qt_041": ([FRAUD],
        "SELECT date, COUNT(*) AS fraud_count FROM hofinet WHERE is_fraud = 1 GROUP BY date "
        "ORDER BY date LIMIT 100"),
    "st_qt_042": ([FRAUD],
        "SELECT date, sender_bank, receiver_bank, amount, fraud_type FROM hofinet "
        "WHERE is_fraud = 1 LIMIT 5"),
    "st_qt_043": ([C("amount", "<=", 50000), FRAUD],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE amount <= 50000 "
        "AND is_fraud = 1 ORDER BY amount LIMIT 100"),
    "st_qt_044": ([C("sender_bank", "=", 123)],
        "SELECT date, time_slot, receiver_bank, amount, is_fraud FROM hofinet WHERE sender_bank = 123 "
        "ORDER BY date DESC LIMIT 15"),
    "st_qt_045": ([C("amount", "BETWEEN", [10000000, 50000000]), FRAUD],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet "
        "WHERE amount BETWEEN 10000000 AND 50000000 AND is_fraud = 1 ORDER BY amount DESC LIMIT 100"),
    "st_qt_046": ([C("fraud_type", "=", 7)],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet WHERE fraud_type = 7 LIMIT 10"),
    "st_qt_047": ([FRAUD],
        "SELECT fraud_type, AVG(amount) AS avg_amount, MAX(amount) AS max_amount FROM hofinet "
        "WHERE is_fraud = 1 GROUP BY fraud_type ORDER BY fraud_type"),
    "st_qt_048": ([C("date", ">=", 20230401), C("date", "<=", 20230630), C("fraud_type", "=", 1)],
        "SELECT date, sender_bank, receiver_bank, amount FROM hofinet "
        "WHERE date BETWEEN 20230401 AND 20230630 AND fraud_type = 1 ORDER BY date LIMIT 100"),
    "st_qt_049": ([C("fraud_type", "=", 4)],
        "SELECT receiver_acc, COUNT(*) AS fraud_count FROM hofinet WHERE fraud_type = 4 "
        "GROUP BY receiver_acc HAVING COUNT(*) >= 2 ORDER BY fraud_count DESC LIMIT 100"),
    "st_qt_050": ([FRAUD],
        "SELECT CASE WHEN amount < 1000000 THEN 'small' WHEN amount < 10000000 THEN 'medium' "
        "ELSE 'large' END AS band, COUNT(*) AS fraud_count FROM hofinet WHERE is_fraud = 1 "
        "GROUP BY band ORDER BY fraud_count DESC"),
    "st_qt_051": ([FRAUD],
        "WITH per_bank AS (SELECT sender_bank, COUNT(*) AS fraud_count FROM hofinet "
        "WHERE is_fraud = 1 GROUP BY sender_bank) SELECT sender_bank, fraud_count FROM per_bank "
        "WHERE fraud_count > (SELECT AVG(fraud_count) FROM per_bank) ORDER BY fraud_count DESC"),
    "st_qt_052": ([C("fund_type", "=", 1), FRAUD],
        "SELECT sender_acc, date, COUNT(DISTINCT receiver_acc) AS receivers FROM hofinet "
        "WHERE fund_type = 1 AND is_fraud = 1 GROUP BY sender_acc, date "
        "HAVING COUNT(DISTINCT receiver_acc) >= 5 ORDER BY receivers DESC LIMIT 100"),
    "st_qt_053": ([FRAUD],
        "SELECT fraud_type, COUNT(*) AS fraud_count, "
        "ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS percent FROM hofinet "
        "WHERE is_fraud = 1 GROUP BY fraud_type ORDER BY fraud_count DESC"),
}

# C1-003: fund type 4 never carries a fraud label, so these questions had no answer.
FUND_TYPE_FOUR = {
    "st_qt_006": ("기타(자금구분 3) 유형의 이상거래를 조회해줘",
                  "Please query the suspicious transactions with fund type 3 (other)."),
    "st_qt_021": ("휴대전화(매체구분 4)를 통한 기타(자금구분 3) 이상거래를 조회해줘",
                  "Please query the suspicious transactions with fund type 3 (other) made via mobile "
                  "phone (media type 4)."),
    "st_qt_052": ("같은 날 동일한 출금계좌에서 서로 다른 입금계좌로 5건 이상 급여(자금구분 1) 이상거래를 보낸 계좌를 조회해줘",
                  "Please query the accounts that sent five or more salary (fund type 1) suspicious "
                  "transactions to different receiving accounts from the same sending account on one day."),
}

CONTRACT_WHY = ("Contract 1: sql_contains was a substring test, so a keyword matched a year, a LIMIT or "
                "a comment; the conditions are read out of the statement as restricting predicates, and "
                "the reference SQL makes the gold call executable (L4-015)")
FUND_WHY = ("fund type 4 carries no fraud label anywhere in HOFINET, so the question asked for a result "
            "set that is empty by construction (C1-003)")


def apply(kr: Bench, en: Bench, log: ChangeLog) -> None:
    kr_by, en_by = kr.by_id(), en.by_id()
    for case_id, (kr_text, en_text) in FUND_TYPE_FOUR.items():
        log.set_field(kr_by[case_id], "kr", "question", kr_text, "C1-003/D12", FUND_WHY)
        log.set_field(en_by[case_id], "en", "question", en_text, "C1-003/D12", FUND_WHY)

    missing = [cid for cid, case in kr_by.items()
               if "sql_contains" in ((case["expected"].get("param_checks") or {})
                                     .get("query_transactions") or {}) and cid not in SQL]
    if missing:
        raise SystemExit(f"no Contract 1 conversion for {missing}")

    for case_id, (conditions, sql) in SQL.items():
        for bench_by, lang in ((kr_by, "kr"), (en_by, "en")):
            case = bench_by[case_id]
            gold = copy.deepcopy(case["expected"])
            checks = gold["param_checks"]["query_transactions"]
            checks.pop("sql_contains", None)
            gold["param_checks"]["query_transactions"] = {
                "sql_conditions": copy.deepcopy(conditions), "sql_valid": True,
                **{k: v for k, v in checks.items() if k != "sql_valid"},
            }
            gold.setdefault("reference_calls", {})["query_transactions"] = {"sql": sql}
            log.set_field(case, lang, "expected", gold, "C1-011/Contract1", CONTRACT_WHY)
    log.note(f"{len(SQL)} query_transactions cases converted to sql_conditions with a reference SQL")
    log.note(f"{len(FUND_TYPE_FOUR)} questions moved off fund type 4, whose fraud result set is empty")


def main() -> int:
    kr, en = both()
    log = ChangeLog("p09_contract1", "Contract 1 for the SQL cases: sql_conditions plus an executable "
                                     "reference SQL under expected.reference_calls.")
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
