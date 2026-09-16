"""Pass 14 - ask for the risk score, not a probability (register C1-003, D12).

`predict_fraud` and `rank_risky_transactions` return `fraud_risk_score`, described
as an "uncalibrated XGBoost score in [0, 1]; not a probability of fraud", and
`score_account_risk` returns a behavioural risk score between 0 and 100. 49
questions still asked for a 확률 / probability / likelihood, so the question named
something the tool does not produce. The multi-turn data already says 위험 점수
(L2-012); this pass makes the single-turn wording say the same thing.

The gold blocks are untouched: only the wording changes, the arguments do not.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both

ISSUE = "C1-003/D12"
WHY = ("predict_fraud and rank_risky_transactions return fraud_risk_score, an uncalibrated "
       "score that is not a probability of fraud, and score_account_risk returns a 0-100 "
       "behavioural risk score; the question now asks for the score.")

# case id -> (Korean fragment, its replacement), or None when that language is unchanged.
KR: dict[str, tuple[str, str]] = {
    "st_mp_017": ("이상거래 확률을 예측해줘", "이상거래 위험 점수를 예측해줘"),
    "st_mtool_004": ("이상거래 확률을 예측하고", "이상거래 위험 점수를 예측하고"),
    "st_mtool_006": ("이상거래 확률도 하나 예측해줘", "이상거래 위험 점수도 하나 예측해줘"),
    "st_mtool_018": ("이상거래 확률도 예측해줘", "이상거래 위험 점수도 예측해줘"),
    "st_mtool_026": ("사기 확률도 예측해줘", "이상거래 위험 점수도 예측해줘"),
    "st_mtool_072": ("이상거래 확률을 예측하고", "이상거래 위험 점수를 예측하고"),
    "st_mtool_086": ("예측 확률도 구해줘", "예측 모델 위험 점수도 구해줘"),
    "st_pf_001": ("이상거래 확률을 예측해줘", "이상거래 위험 점수를 예측해줘"),
    "st_pf_002": ("이 거래가 이상거래일 확률은?", "이 거래의 이상거래 위험 점수는?"),
    "st_pf_004": ("사기 확률을 예측해줘", "이상거래 위험 점수를 예측해줘"),
    "st_pf_007": ("이 거래의 이상거래 가능성을 수치로 보여줘", "이 거래의 이상거래 위험 점수를 보여줘"),
    "st_pf_008": ("사기 확률을 예측해줘", "이상거래 위험 점수를 예측해줘"),
    "st_pf_009": ("거래가 이상거래일 가능성을 AI로 예측해줘", "거래의 이상거래 위험 점수를 AI로 예측해줘"),
    "st_pf_010": ("이상거래 확률을 계산해줘", "이상거래 위험 점수를 계산해줘"),
    "st_pf_011": ("이상거래 확률을 예측해줘", "이상거래 위험 점수를 예측해줘"),
    "st_pf_012": ("이상거래 확률은?", "이상거래 위험 점수는?"),
    "st_pf_015": ("400만원 거래가 이상거래일 확률은?", "400만원 거래의 이상거래 위험 점수는?"),
    "st_pf_017": ("이상거래 확률을 계산해줘", "이상거래 위험 점수를 계산해줘"),
    "st_pf_019": ("이상거래 가능성을 예측해줘", "이상거래 위험 점수를 예측해줘"),
    "st_pf_020": ("이상거래 확률을 구해줘", "이상거래 위험 점수를 구해줘"),
    "st_pf_022": ("이상거래 확률은?", "이상거래 위험 점수는?"),
    "st_pf_023": ("사기 가능성을 예측해줘", "이상거래 위험 점수를 예측해줘"),
    "st_pf_025": ("이상거래 확률을 모델로 구해줘", "이상거래 위험 점수를 모델로 구해줘"),
    "st_pf_027": ("이상거래 확률을 예측해줘", "이상거래 위험 점수를 예측해줘"),
    "st_pf_028": ("2000만원 거래가 이상거래일 확률은?", "2000만원 거래의 이상거래 위험 점수는?"),
    "st_pf_029": ("사기 확률을 AI로 구해줘", "이상거래 위험 점수를 AI로 구해줘"),
    "st_pf_031": ("이상거래 가능성을 예측해줘", "이상거래 위험 점수를 예측해줘"),
    "st_pf_033": ("사기 확률을 모델로 예측해줘", "이상거래 위험 점수를 모델로 예측해줘"),
    "st_pf_034": ("이상거래 확률을 XGBoost 모델로 예측해줘", "이상거래 위험 점수를 XGBoost 모델로 예측해줘"),
    "st_pf_035": ("이 거래가 이상거래일 가능성을 수치로 알려줘", "이 거래의 이상거래 위험 점수를 알려줘"),
    "st_pf_037": ("이상거래인지 확률로 알려줘", "이 거래의 이상거래 위험 점수를 알려줘"),
    "st_pf_041": ("이상거래 확률을 예측해줘", "이상거래 위험 점수를 예측해줘"),
    "st_pf_042": ("4000만원인 거래가 이상거래일 확률은?", "4000만원인 거래의 이상거래 위험 점수는?"),
    "st_pf_044": ("이상거래 확률을 예측해줘", "이상거래 위험 점수를 예측해줘"),
    "st_pf_045": ("이상거래 가능성을 AI로 평가해줘", "이상거래 위험 점수를 AI로 평가해줘"),
    "st_pf_046": ("이상거래인지 확률로 알려줘", "이 거래의 이상거래 위험 점수를 알려줘"),
    "st_pf_047": ("사기 확률을 XGBoost로 예측해줘", "이상거래 위험 점수를 XGBoost로 예측해줘"),
    "st_rrt_002": ("이상거래 확률이 높은", "이상거래 위험 점수가 높은"),
    "st_rrt_006": ("이상거래 확률 TOP 50건", "이상거래 위험 점수 TOP 50건"),
    "st_rrt_010": ("가장 이상거래 확률이 높은 거래들", "이상거래 위험 점수가 가장 높은 거래들"),
    "st_rrt_011": ("이상거래 확률을 예측하고, 확률이 가장 높은 50건",
                   "이상거래 위험 점수를 예측하고, 점수가 가장 높은 50건"),
    "st_rrt_016": ("이상거래 확률이 가장 높은 10건", "이상거래 위험 점수가 가장 높은 10건"),
    "st_rrt_019": ("이상거래 확률 Top 30", "이상거래 위험 점수 Top 30"),
    "st_rrt_023": ("이상거래 확률 상위 50건", "이상거래 위험 점수 상위 50건"),
    "st_rrt_031": ("이상거래 예측 확률이 높은", "예측 모델 위험 점수가 높은"),
    "st_rrt_035": ("이상거래 확률 TOP 20건", "이상거래 위험 점수 TOP 20건"),
    "st_rrt_037": ("이상거래 확률이 가장 높은 35건", "이상거래 위험 점수가 가장 높은 35건"),
    "st_rrt_040": ("이상거래 확률 기준 TOP 8건", "이상거래 위험 점수 기준 TOP 8건"),
    "st_sar_015": ("9000000000034017가 자금세탁에 사용될 가능성을 수치로 알려줘",
                   "9000000000034017의 자금세탁 위험도를 점수로 알려줘"),
}

EN: dict[str, tuple[str, str]] = {
    "st_mp_017": ("predict the likelihood of that type of suspicious transaction",
                  "predict the suspicious-transaction risk score of that type"),
    "st_mtool_004": ("predict the fraud probability of", "predict the fraud risk score of"),
    "st_mtool_006": ("predict one fraud probability under these conditions",
                     "predict one fraud risk score under these conditions"),
    "st_mtool_018": ("predict the fraud probability of", "predict the fraud risk score of"),
    "st_mtool_026": ("predict the fraud probability of", "predict the fraud risk score of"),
    "st_mtool_072": ("Please predict the fraud probability under these conditions",
                     "Please predict the fraud risk score under these conditions"),
    "st_mtool_086": ("get the prediction probability", "get the predicted risk score"),
    "st_pf_001": ("predict the fraud probability of", "predict the fraud risk score of"),
    "st_pf_002": ("What is the probability that this transaction is suspicious?",
                  "What is the fraud risk score of this transaction?"),
    "st_pf_004": ("predict the fraud probability of", "predict the fraud risk score of"),
    "st_pf_007": ("Please show numerically how likely the following transaction is to be suspicious",
                  "Please show the fraud risk score of the following transaction"),
    "st_pf_008": ("predict the fraud probability when", "predict the fraud risk score for the transaction where"),
    "st_pf_009": ("Please use AI to predict how likely a 5 million won salary transaction "
                  "(fund type 1) from withdrawal institution 118 to deposit institution 119 at "
                  "midnight (time slot 0) via bulk transfer (media type 7) is to be suspicious.",
                  "Please use AI to predict the fraud risk score of a 5 million won salary "
                  "transaction (fund type 1) from withdrawal institution 118 to deposit "
                  "institution 119 at midnight (time slot 0) via bulk transfer (media type 7)."),
    "st_pf_010": ("calculate the fraud probability under these conditions",
                  "calculate the fraud risk score under these conditions"),
    "st_pf_011": ("predict the fraud probability of", "predict the fraud risk score of"),
    "st_pf_012": ("What is the probability that a 9,000,000 won transaction",
                  "What is the fraud risk score of a 9,000,000 won transaction"),
    "st_pf_015": ("What is the probability that a 4,000,000 won general transfer",
                  "What is the fraud risk score of a 4,000,000 won general transfer"),
    "st_pf_017": ("calculate the fraud probability of", "calculate the fraud risk score of"),
    "st_pf_019": ("Please predict how likely an 8 million won transaction via phone banking "
                  "(media type 3) at 4 PM (time slot 15) from withdrawal institution 147 to "
                  "deposit institution 127 with fund type 1 (salary) is to be suspicious.",
                  "Please predict the fraud risk score of an 8 million won transaction via phone "
                  "banking (media type 3) at 4 PM (time slot 15) from withdrawal institution 147 "
                  "to deposit institution 127 with fund type 1 (salary)."),
    "st_pf_020": ("calculate the fraud probability of", "calculate the fraud risk score of"),
    "st_pf_022": ("What is the probability that a transaction with time slot 9",
                  "What is the fraud risk score of a transaction with time slot 9"),
    "st_pf_023": ("predict the fraud likelihood of", "predict the fraud risk score of"),
    "st_pf_025": ("use the model to calculate the fraud probability of",
                  "use the model to calculate the fraud risk score of"),
    "st_pf_027": ("predict the fraud probability of", "predict the fraud risk score of"),
    "st_pf_028": ("What is the probability that a 20,000,000 won transaction",
                  "What is the fraud risk score of a 20,000,000 won transaction"),
    "st_pf_029": ("use AI to calculate the fraud probability of",
                  "use AI to calculate the fraud risk score of"),
    "st_pf_031": ("Please predict how likely it is to be suspicious.",
                  "Please predict its fraud risk score."),
    "st_pf_033": ("use the model to predict the fraud probability of",
                  "use the model to predict the fraud risk score of"),
    "st_pf_034": ("predict the probability that the following transaction is suspicious",
                  "predict the fraud risk score of the following transaction"),
    "st_pf_035": ("please tell me numerically how likely this transaction is to be suspicious",
                  "please tell me the fraud risk score of this transaction"),
    "st_pf_037": ("Can you tell me the probability that this is a suspicious transaction?",
                  "Can you tell me the fraud risk score of this transaction?"),
    "st_pf_041": ("predict the fraud probability of", "predict the fraud risk score of"),
    "st_pf_042": ("What is the probability that a 40 million won transaction",
                  "What is the fraud risk score of a 40 million won transaction"),
    "st_pf_044": ("predict the fraud probability of", "predict the fraud risk score of"),
    "st_pf_045": ("Please use AI to assess how likely a 20 million won transaction at 9 AM "
                  "(time slot 9) via internet banking (media type 2) from withdrawal institution "
                  "107 to deposit institution 112 as an other-purpose transfer (fund type 3) is "
                  "to be suspicious.",
                  "Please use AI to assess the fraud risk score of a 20 million won transaction "
                  "at 9 AM (time slot 9) via internet banking (media type 2) from withdrawal "
                  "institution 107 to deposit institution 112 as an other-purpose transfer "
                  "(fund type 3)."),
    "st_pf_046": ("Can you tell me the probability that this is a suspicious transaction?",
                  "Can you tell me the fraud risk score of this transaction?"),
    "st_pf_047": ("use XGBoost to predict the fraud probability of",
                  "use XGBoost to predict the fraud risk score of"),
    "st_rrt_002": ("with the highest likelihood of being suspicious",
                   "with the highest suspicious-transaction risk score"),
    "st_rrt_006": ("rank the top 50 suspicious transactions by probability",
                   "rank the top 50 suspicious transactions by risk score"),
    "st_rrt_010": ("with the highest likelihood of being suspicious",
                   "with the highest suspicious-transaction risk score"),
    "st_rrt_011": ("use the AI model to predict the likelihood of suspicious transactions, and "
                   "display the 50 records with the highest probabilities",
                   "use the AI model to score them for suspicious-transaction risk, and display "
                   "the 50 records with the highest scores"),
    "st_rrt_016": ("the top 10 transactions with the highest probability of being suspicious",
                   "the top 10 transactions with the highest suspicious-transaction risk score"),
    "st_rrt_019": ("the top 30 suspicious transaction probabilities",
                   "the top 30 suspicious transactions by risk score"),
    "st_rrt_023": ("the top 50 suspicious transactions with the highest probability",
                   "the top 50 suspicious transactions with the highest risk score"),
    "st_rrt_031": ("a list of transactions with a high probability of being suspicious",
                   "a list of transactions with a high suspicious-transaction risk score"),
    "st_rrt_035": ("the top 20 suspicious transactions based on their probability",
                   "the top 20 suspicious transactions based on their risk score"),
    "st_rrt_037": ("the 35 transactions with the highest likelihood of being suspicious",
                   "the 35 transactions with the highest suspicious-transaction risk score"),
    "st_rrt_040": ("the top 8 suspicious transactions based on the probability criteria",
                   "the top 8 suspicious transactions based on their risk score"),
    "st_sar_015": ("Please provide a numerical assessment of the likelihood that account "
                   "9000000000034017 is being used for money laundering.",
                   "Please give the money-laundering risk score of account 9000000000034017."),
}

BANNED_KR = ("확률", "가능성")
BANNED_EN = ("probabilit", "likelihood", "how likely", "likely")


def apply_one(bench: Bench, lang: str, table: dict[str, tuple[str, str]], log: ChangeLog) -> None:
    by_id = bench.by_id()
    for case_id, (before, after) in table.items():
        case = by_id.get(case_id)
        if case is None:
            raise SystemExit(f"{case_id}: absent from {bench.root.name}")
        question = case["question"]
        if after in question:
            continue              # already applied
        if before not in question:
            raise SystemExit(f"{case_id} ({lang}): {before!r} is no longer in the question")
        log.set_field(case, lang, "question", question.replace(before, after), ISSUE, WHY)


def residue(bench: Bench, lang: str) -> list[str]:
    """Any question of the three scoring tools that still names a probability."""
    tools = {"predict_fraud", "rank_risky_transactions", "score_account_risk"}
    banned = BANNED_KR if lang == "kr" else BANNED_EN
    out = []
    for _, case in bench.cases():
        expected = case["expected"]
        named = set(expected.get("tools_must_include") or [])
        if expected.get("primary_tool"):
            named.add(expected["primary_tool"])
        if not (named & tools) and case["id"] not in KR:
            continue
        text = case["question"].lower()
        hit = [w for w in banned if w in text]
        if hit:
            out.append(f"{case['id']} ({lang}): {hit}")
    return out


def main() -> int:
    kr, en = both()
    log = ChangeLog("p14_risk_score",
                    "The scoring tools answer with a risk score, so the questions ask for one "
                    "(C1-003, D12).")
    apply_one(kr, "kr", KR, log)
    apply_one(en, "en", EN, log)
    left = residue(kr, "kr") + residue(en, "en")
    if left:
        raise SystemExit("probability wording left behind:\n  " + "\n  ".join(left))
    kr.save()
    en.save()
    log.note(f"{len(KR)} Korean and {len(EN)} English questions reworded; no gold changed.")
    print(log.report())
    print(f"log: {log.write()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
