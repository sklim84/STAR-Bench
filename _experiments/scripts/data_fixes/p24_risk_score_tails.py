"""Pass 24 - the five English questions `p14` left ungrammatical (C1-003, D12).

`p14_risk_score` rewrote 49 questions that asked for a fraud *probability* so that they
ask for the risk score the tools return. In the English arm it replaced the head of the
sentence by a table of prefixes, and for five questions the sentence it replaced ended in
a clause the new head does not govern:

    What is the probability that a 9,000,000 won transaction ... is suspicious?
    What is the fraud risk score of a 9,000,000 won transaction ... is suspicious?

The trailing "is suspicious" is the tail of the old question. The five questions are
rewritten whole here rather than patched at the seam.

Nothing else changes: the same six `predict_fraud` features are named, in the same
order, with the same values, so the gold is untouched. The Korean arm reads correctly
already ("... 900만원 거래의 이상거래 위험 점수는?") and is not changed.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both

ISSUE = "C1-003"
WHY = ("p14 replaced the head of the sentence and left the trailing clause of the old "
       "one, so the English question did not parse (closeout verification F2).")

EN = {
    "st_pf_012": (
        "What is the fraud risk score of a 9,000,000 won transaction via internet banking "
        "(media type 2) at 6 PM (time slot 18) from withdrawal institution 130 to deposit "
        "institution 157 as a general transfer (fund type 0) is suspicious?",
        "What is the fraud risk score of a 9,000,000 won transaction via internet banking "
        "(media type 2) at 6 PM (time slot 18) from withdrawal institution 130 to deposit "
        "institution 157 as a general transfer (fund type 0)?"),
    "st_pf_015": (
        "What is the fraud risk score of a 4,000,000 won general transfer (fund type 0) "
        "from withdrawal institution 118 to deposit institution 156 at 12 PM (time slot 12) "
        "via other media (media type 6) is suspicious?",
        "What is the fraud risk score of a 4,000,000 won general transfer (fund type 0) "
        "from withdrawal institution 118 to deposit institution 156 at 12 PM (time slot 12) "
        "via other media (media type 6)?"),
    "st_pf_022": (
        "What is the fraud risk score of a transaction with time slot 9, withdrawal "
        "institution 108, deposit institution 134, fund type 0 (general), media type 2 "
        "(internet banking), and an amount of 4,000,000 won is suspicious?",
        "What is the fraud risk score of a transaction with time slot 9, withdrawal "
        "institution 108, deposit institution 134, fund type 0 (general), media type 2 "
        "(internet banking) and an amount of 4,000,000 won?"),
    "st_pf_028": (
        "What is the fraud risk score of a 20,000,000 won transaction at 9 AM (time slot 9) "
        "via PC banking (media type 1) from withdrawal institution 118 to deposit "
        "institution 114 as a salary transfer (fund type 1) is suspicious?",
        "What is the fraud risk score of a 20,000,000 won transaction at 9 AM (time slot 9) "
        "via PC banking (media type 1) from withdrawal institution 118 to deposit "
        "institution 114 as a salary transfer (fund type 1)?"),
    "st_pf_042": (
        "What is the fraud risk score of a 40 million won transaction at 6 PM (time slot 18) "
        "via bulk transfer (media type 7) from withdrawal institution 134 to deposit "
        "institution 112 with salary (fund type 1) is suspicious?",
        "What is the fraud risk score of a 40 million won transaction at 6 PM (time slot 18) "
        "via bulk transfer (media type 7) from withdrawal institution 134 to deposit "
        "institution 112 as a salary transfer (fund type 1)?"),
}

# Whole questions, so the residue check is an equality: no rewritten question may end in
# a clause the "What is the fraud risk score of" head does not govern.
BANNED_TAIL = " is suspicious?"


def apply_one(bench: Bench, lang: str, table: dict[str, tuple[str, str]], log: ChangeLog) -> None:
    by_id = bench.by_id()
    for case_id, (before, after) in table.items():
        case = by_id.get(case_id)
        if case is None:
            raise SystemExit(f"{case_id}: absent from {bench.root.name}")
        if case["question"] == after:
            continue
        if case["question"] != before:
            raise SystemExit(f"{case_id} ({lang}): the question is neither the as-is nor the to-be")
        log.set_field(case, lang, "question", after, ISSUE, WHY)


def residue(bench: Bench) -> list[str]:
    return [f"{case['id']}: ends in {BANNED_TAIL!r} after a risk-score head"
            for _, case in bench.cases()
            if case["question"].startswith("What is the fraud risk score")
            and case["question"].endswith(BANNED_TAIL)]


def main() -> int:
    _, en = both()
    log = ChangeLog("p24_risk_score_tails",
                    "The five English questions p14 left ungrammatical, rewritten whole.")
    apply_one(en, "en", EN, log)
    left = residue(en)
    if left:
        raise SystemExit("a risk-score question still carries the old tail:\n  " + "\n  ".join(left))
    en.save()
    log.note("The Korean arm of these five cases already read correctly and is unchanged; "
             "the gold is unchanged in both arms.")
    print(log.report())
    print(f"log: {log.write()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
