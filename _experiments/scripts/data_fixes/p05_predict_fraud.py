"""Pass 05 - put the `predict_fraud` inputs back into the HOFINET distribution (D12, C1-003).

HOFINET carries 48 distinct amounts, and fund type 4 (inter-bank auto transfer)
never carries a fraud label, so a question that asks for the fraud risk of a
"4,300,000 won inter-bank auto transfer" describes a transaction the data cannot
hold. Commit 868fd28 fixed this in April (rounds R3 and R7) and the fix was lost;
this pass re-applies it to the question text and the gold in both languages.
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both

# The 48 amounts HOFINET actually holds (SELECT DISTINCT amount FROM hofinet).
AMOUNTS = [1, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 20000, 30000, 40000,
           50000, 60000, 90000, 100000, 200000, 300000, 400000, 500000, 600000, 700000, 900000,
           1000000, 2000000, 3000000, 4000000, 5000000, 6000000, 7000000, 8000000, 9000000,
           10000000, 20000000, 30000000, 40000000, 50000000, 60000000, 70000000, 80000000,
           90000000, 100000000, 200000000, 300000000, 400000000, 500000000]

# R7 of 868fd28: the fund type each case moved to. Fraud rows carry only 0, 1 and 3.
R7 = {
    "st_pf_001": 3, "st_pf_003": 0, "st_pf_006": 0, "st_pf_008": 0, "st_pf_009": 1,
    "st_pf_011": 1, "st_pf_012": 0, "st_pf_015": 0, "st_pf_016": 3, "st_pf_018": 0,
    "st_pf_020": 0, "st_pf_021": 3, "st_pf_022": 0, "st_pf_023": 0, "st_pf_024": 1,
    "st_pf_026": 1, "st_pf_027": 3, "st_pf_028": 1, "st_pf_031": 1, "st_pf_032": 1,
    "st_pf_033": 1, "st_pf_035": 0, "st_pf_037": 0, "st_pf_040": 1, "st_pf_041": 1,
    "st_pf_044": 0, "st_pf_045": 3, "st_pf_048": 0,
    # Cases 868fd28 did not carry a decision for; 0 is the fund type of 79% of the fraud rows.
    "st_mtool_004": 0, "st_mtool_006": 0, "st_mtool_018": 0, "st_mtool_026": 1,
    "st_mtool_072": 0, "st_mtool_086": 3,
}
# Gold calls that never pinned every required argument, so they could not be executed at all.
COMPLETE = {"st_mtool_004": {"fund_type": 0, "media_type": 2},
            "st_mtool_006": {"sender_bank": 134, "receiver_bank": 119}}
FUND_LABEL = {0: ("일반", "general"), 1: ("급여", "salary"), 3: ("기타", "other"),
              4: ("타행 자동이체", "inter-bank auto transfer")}
# Inside a sentence the English label needs a noun to attach to.
FUND_PHRASE = {0: "general transfer", 1: "salary transfer", 3: "other-purpose transfer"}
KR_FUND_WORDS = r"(?:타행\s*자동이체|이체|일반|급여|기타)"
EN_FUND_WORDS = r"(?:inter-bank auto transfer|transfer|general|salary|other)"

# Questions where the mechanical rewrite reads badly; the whole sentence is given instead.
SENTENCE = {
    "st_pf_039": {
        "kr": "이 계좌에서 발생한 거래가 위험한지 판단해줘 — 출금사 131, 입금사 120, 밤 11시(거래시간대 21), 휴대전화(매체구분 4), 기타(자금구분 3), 4천만원",
        "en": "Please assess whether this transaction is risky - withdrawal institution 131, deposit institution 120, 11 PM (time slot 21), mobile phone (media type 4), other (fund type 3), 40 million won.",
    },
    "st_pf_037": {
        "kr": "오전 3시 새벽에 전화뱅킹으로 출금사 130에서 입금사 113으로 5백만원이 일반 자금(자금구분 0)으로 이체됐어. 이상거래인지 확률로 알려줘",
        "en": "At 3 AM, 5 million won was transferred as general funds (fund type 0) via phone banking from withdrawal institution 130 to deposit institution 113. Can you tell me the probability that this is a suspicious transaction?",
    },
    "st_pf_040": {
        "kr": "밤 10시에 PC뱅킹에서 출금사 113, 입금사 154로 급여(자금구분 1) 1억원짜리 거래가 이상거래인지 AI가 판단해줘",
        "en": "Please have the AI determine whether a 100 million won salary transaction (fund type 1) from withdrawal institution 113 to deposit institution 154 via PC banking at 10 PM is a suspicious transaction.",
    },
    "st_pf_048": {
        "kr": "이 거래가 수상한지 판단해줘 — 새벽 4시에 대량이체 매체를 통해 출금사 129에서 입금사 151로 2억원이 일반 자금(자금구분 0)으로 이동했어",
        "en": "Please assess whether this transaction is suspicious — at 4 AM, 200 million won moved from withdrawal institution 129 to deposit institution 151 as general funds (fund type 0) via bulk transfer.",
    },
    "st_pf_009": {
        "kr": "대량이체(매체구분 7), 자정(거래시간대 0), 출금사 118, 입금사 119, 급여(자금구분 1), 5백만원인 거래가 이상거래일 가능성을 AI로 예측해줘",
        "en": "Please use AI to predict how likely a 5 million won salary transaction (fund type 1) from withdrawal institution 118 to deposit institution 119 at midnight (time slot 0) via bulk transfer (media type 7) is to be suspicious.",
    },
    "st_pf_006": {
        "kr": "다음 거래를 이상거래 모델로 분석해줘: 거래시간대=15, 출금사=118, 입금사=119, 자금구분=0(일반), 기타 매체(매체구분 6), 7백만원",
        "en": "Please analyze the following transaction with the fraud model: time slot=15, withdrawal institution=118, deposit institution=119, fund type=0 (general), other media (media type 6), 7 million won.",
    },
    "st_mtool_004": {
        "kr": "거래시간대 3, 출금사 134, 입금사 119, 일반(자금구분 0), 인터넷뱅킹(매체구분 2), 1000만원 거래의 이상거래 확률을 예측하고, 해당 출금계좌 __ACCOUNT__의 네트워크도 분석해줘",
        "en": "Please predict the fraud probability of a 10,000,000 won general transaction (fund type 0) via internet banking (media type 2) with time slot 3, withdrawal institution 134, and deposit institution 119, and also analyze the network of withdrawal account __ACCOUNT__.",
    },
    "st_mtool_006": {
        "kr": "출금금융회사 134의 이상거래 데이터를 조회하고 이상거래 확률도 하나 예측해줘. 거래시간대 9, 출금사 134, 입금사 119, 일반(자금구분 0), 인터넷뱅킹(매체구분 2), 500만원 조건으로.",
        "en": "Please query the suspicious transaction data of withdrawal financial institution 134 and also predict one fraud probability under these conditions: time slot 9, withdrawal institution 134, deposit institution 119, general (fund type 0), internet banking (media type 2), 5,000,000 won.",
    },
    "st_mtool_018": {
        "kr": "갑작스러운 거래패턴의 변화(유형1) 이상거래 요약을 확인하고, 거래시간대 3, 출금사 118, 입금사 119, 일반(자금구분 0), PC뱅킹(매체구분 1), 1000만원 거래의 이상거래 확률도 예측해줘",
        "en": "Please check the summary of sudden change in transaction pattern (type 1) suspicious transactions and also predict the fraud probability of a 10,000,000 won general transaction (fund type 0) with time slot 3, withdrawal institution 118, deposit institution 119, and PC banking (media type 1).",
    },
    "st_mtool_026": {
        "kr": "금융회사 158 리포트를 확인하고, 해당 기관 이상거래를 SQL로 조회하고, 거래시간대 0, 출금사 158, 입금사 134, 급여(자금구분 1), PC뱅킹(매체구분 1), 2000만원 거래의 사기 확률도 예측해줘",
        "en": "Please check the report for financial institution 158, query that institution's suspicious transactions with SQL, and also predict the fraud probability of a 20 million won salary transaction (fund type 1) with time slot 0, withdrawal institution 158, deposit institution 134, and PC banking (media type 1).",
    },
    "st_mtool_072": {
        "kr": "거래시간대 21, 출금사 134, 입금사 119, 일반(자금구분 0), 인터넷뱅킹(매체구분 2), 300만원 조건으로 이상거래 확률을 예측하고, 전체 통계도 보여줘",
        "en": "Please predict the fraud probability under these conditions: time slot 21, withdrawal institution 134, deposit institution 119, general (fund type 0), internet banking (media type 2), 3,000,000 won, and also show the overall statistics.",
    },
    "st_mtool_086": {
        "kr": "출금금융회사 107의 이상거래를 조회하고, 예측 확률도 구해줘. 거래시간대 12, 출금사 107, 입금사 122, 기타(자금구분 3), 휴대전화(매체구분 4), 200만원.",
        "en": "Please query the suspicious transactions of withdrawal financial institution 107 and also get the prediction probability: time slot 12, withdrawal institution 107, deposit institution 122, other (fund type 3), mobile phone (media type 4), 2,000,000 won.",
    },
}


def nearest_amount(value: int) -> int:
    """Closest of the 48 real amounts; a tie takes the smaller, as 868fd28 R3 did."""
    return min(AMOUNTS, key=lambda a: (abs(a - value), a))


def spellings(value: int, lang: str) -> dict[str, str]:
    """The ways one amount is written, keyed by form so old and new pair up."""
    out = {"plain": str(value), "comma": f"{value:,}"}
    if lang == "kr":
        if value % 10_000 == 0 and value < 100_000_000:
            out["man"] = f"{value // 10_000}만원"
        if value % 1_000_000 == 0 and value < 10_000_000:
            out["baekman"] = f"{value // 1_000_000}백만원"
        if value % 10_000_000 == 0 and value < 100_000_000:
            out["cheonman"] = f"{value // 10_000_000}천만원"
        if value >= 100_000_000:
            out["eok"] = f"{value / 100_000_000:g}억원"
    elif value >= 1_000_000:
        out["million"] = f"{value / 1_000_000:g} million"
    return out


FORM_ORDER = ["man", "baekman", "cheonman", "eok", "million", "comma", "plain"]


def replace_amount(text: str, old: int, new: int, lang: str) -> str | None:
    before, after = spellings(old, lang), spellings(new, lang)
    for form in FORM_ORDER:
        if form not in before:
            continue
        pattern = re.compile(r"(?<![\d,.])" + re.escape(before[form]) + r"(?![\d,])")
        if not pattern.search(text):
            continue
        replacement = after.get(form) or after.get("man") or after["comma"]
        return pattern.sub(replacement, text, count=1)
    return None


# Only the words this pass inserts: a number, or one of the fund-type phrases.
ARTICLE_TARGET = re.compile(r"^(?:[\d,.]+|general|salary|other-purpose)\b", re.I)
VOWEL_SOUND = re.compile(r"^(?:8|11|18|other)", re.I)


def fix_article(text: str) -> str:
    """`a 8 million` and `an 20,000,000` read wrong after a number or a label changes."""
    def repair(m: re.Match) -> str:
        word = m.group(2)
        if not ARTICLE_TARGET.match(word):
            return m.group(0)
        return ("an " if VOWEL_SOUND.match(word) else "a ") + word
    return re.sub(r"\b(an?) (\S+)", repair, text)


def replace_fund(text: str, new: int, lang: str) -> str:
    label = FUND_LABEL[new][0 if lang == "kr" else 1]
    if lang == "kr":
        rules = [
            (rf"{KR_FUND_WORDS}\s*\(자금구분\s*4\)", f"{label}(자금구분 {new})"),
            (r"자금구분\s*4\s*\(" + KR_FUND_WORDS + r"\)", f"자금구분 {new}({label})"),
            (r"자금구분\s*=\s*4", f"자금구분={new}"),
            (r"자금구분\s*4(?![\d(])", f"자금구분 {new}"),
            (r"타행\s*자동이체", f"{label}(자금구분 {new})"),
        ]
    else:
        phrase = FUND_PHRASE[new]
        rules = [
            (rf"{EN_FUND_WORDS}\s*\(fund type 4\)", f"{phrase} (fund type {new})"),
            (r"fund type 4\s*\(" + EN_FUND_WORDS + r"\)", f"fund type {new} ({label})"),
            (r"fund type\s*=\s*4", f"fund type={new}"),
            (r"fund type 4(?!\d)", f"fund type {new}"),
            (r"inter-bank auto transfer", f"{phrase} (fund type {new})"),
        ]
    for pattern, replacement in rules:
        if re.search(pattern, text):
            return re.sub(pattern, replacement, text, count=1)
    return text


def apply(kr: Bench, en: Bench, log: ChangeLog) -> None:
    kr_by, en_by = kr.by_id(), en.by_id()
    n_amount = n_fund = 0
    for case_id, case in sorted(kr_by.items()):
        checks = (case["expected"].get("param_checks") or {}).get("predict_fraud")
        if not isinstance(checks, dict):
            continue
        english = en_by[case_id]
        old_amount = checks.get("amount")
        new_amount = nearest_amount(old_amount) if isinstance(old_amount, int) else None
        new_fund = R7.get(case_id) if checks.get("fund_type") in (4, None) else None
        missing = COMPLETE.get(case_id, {})
        if new_amount == old_amount and new_fund is None and not missing:
            continue
        why = []
        if new_amount != old_amount:
            why.append(f"{old_amount} is not one of the 48 amounts HOFINET holds, so the described "
                       f"transaction cannot exist; 868fd28 R3 maps it to the nearest, {new_amount}")
            n_amount += 1
        if new_fund is not None:
            why.append(f"fund type 4 carries no fraud label anywhere in HOFINET, so a fraud question "
                       f"about it has no possible answer; 868fd28 R7 moves it to {new_fund} "
                       f"({FUND_LABEL[new_fund][0]})")
            n_fund += 1
        if missing:
            why.append(f"the gold omitted the required arguments {sorted(missing)}, so the gold call "
                       f"could not be executed; they are taken from the question (L1-016)")
        reason = "; ".join(why)

        for bench_case, lang in ((case, "kr"), (english, "en")):
            before = copy.deepcopy(bench_case["expected"])
            spec = bench_case["expected"]["param_checks"]["predict_fraud"]
            if new_amount is not None:
                spec["amount"] = new_amount
            if new_fund is not None:
                spec["fund_type"] = new_fund
            spec.update(missing)
            log.record(case_id, lang, "expected", before, bench_case["expected"], "C1-003/D12", reason)

            override = SENTENCE.get(case_id, {}).get(lang)
            if override is None and case_id in COMPLETE:
                raise SystemExit(f"{case_id}: completing the gold needs a rewritten question")
            if override:
                account = re.search(r"\d{16}", bench_case["question"])
                text = override.replace("__ACCOUNT__", account.group(0) if account else "")
            else:
                text = bench_case["question"]
                if new_amount is not None and new_amount != old_amount:
                    moved = replace_amount(text, old_amount, new_amount, lang)
                    if moved is None:
                        raise SystemExit(f"{case_id} ({lang}): cannot find {old_amount} in the question, "
                                         f"add the sentence to SENTENCE")
                    text = moved
                if new_fund is not None:
                    text = replace_fund(text, new_fund, lang)
                if lang == "en":
                    text = fix_article(text)
            log.set_field(bench_case, lang, "question", text, "C1-003/D12", reason)
    log.note(f"{n_amount} amounts mapped onto the 48-value set, {n_fund} fund types moved off 4")


def main() -> int:
    kr, en = both()
    log = ChangeLog("p05_predict_fraud", "Re-apply the 868fd28 R3/R7 mapping so every predict_fraud "
                                         "input is a value HOFINET holds (D12, C1-003).")
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
