"""Pass 26 - the low-severity findings of the closeout verification (F9, F10, F11).

**F9 - five English near-duplicate pairs the round created.** `p14_risk_score` rewrote
the `rank_risky_transactions` questions onto one phrase ("... suspicious transactions by
risk score from a sample of N cases"), which pushed four `st_rrt_*` pairs and
`st_mtool_020`/`st_mtool_084` to 0.72-0.75 character-3-gram Jaccard. Their golds differ
exactly as their numbers differ, so no case conflicts with another; the wording is
simply too close to tell them apart at a glance. Four English questions are reworded and
the five pairs drop to 0.44-0.62. The English arm returns to 78 pairs at or above 0.72,
the count it carried before the round, and no new pair is created.

**F10 - `st_acif_034` pins `min_transactions=1`.** The question asks for the pairs "중점
거래 건수 조건 없이 전수" / "without any conditions on the number of key transactions",
and `min_transactions` defaults to 10, so the value has to be stated. Both 1 and 0 say
"no condition" and the tool returns a byte-identical answer for them, because every
group it aggregates has at least one transaction. The gold keeps 1 as its primary value
and accepts 0 as an alternative, which is what the alternatives block is for (Contract
1); the note `p12_notes` regenerates says so.

**F11 - two English fluency nits, both older than this round.** `st_an_irr_002` had a
singular verb on a plural subject. `st_strv_005` said the draft "fills in" the details,
where the Korean says the draft *has* them filled in.

None of this touches the Korean arm or any gold value except the added alternative.
"""

from __future__ import annotations

import copy
import itertools
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both

SIMILARITY_LIMIT = 0.72

# --------------------------------------------------------------------------- F9
NEAR_DUPLICATE_EN = {
    "st_rrt_006": (
        "Please rank the top 50 suspicious transactions by risk score from a sample of "
        "1000 cases.",
        "Please rank the 50 riskiest of a 1000-case sample by suspicious-transaction "
        "risk score."),
    "st_rrt_016": (
        "Please extract the top 10 transactions with the highest suspicious-transaction "
        "risk score from a sample of 500 cases.",
        "Out of a 500-record sample, please extract the 10 transactions whose "
        "suspicious-transaction risk score is highest."),
    "st_rrt_019": (
        "Please extract the top 30 suspicious transactions by risk score from a sample "
        "of 1500 cases.",
        "From a sample of 1500 transactions, please pull out the Top 30 by "
        "suspicious-transaction risk score."),
    "st_mtool_084": (
        "Please rank the top 20 high-risk transactions and analyze the network of "
        "account 9000000000034076.",
        "Please rank 20 high-risk transactions, and also run a network analysis on "
        "account 9000000000034076."),
}
# The pairs the round created, which have to be under the limit when the pass is done.
RESOLVED_PAIRS = [("st_rrt_006", "st_rrt_019"), ("st_rrt_016", "st_rrt_037"),
                  ("st_rrt_019", "st_rrt_035"), ("st_rrt_019", "st_rrt_040"),
                  ("st_mtool_020", "st_mtool_084")]

# --------------------------------------------------------------------------- F10
ALTERNATIVE_CASE = "st_acif_034"
ALTERNATIVE = {
    "tools_must_include": ["analyze_cross_institution_flow"],
    "param_checks": {"analyze_cross_institution_flow": {"min_transactions": 0}},
}

# --------------------------------------------------------------------------- F11
FLUENCY_EN = {
    "st_an_irr_002": (
        "Does the first three digits of the account number represent the financial "
        "institution code?",
        "Do the first three digits of the account number represent the financial "
        "institution code?"),
    "st_strv_005": (
        "This STR draft also fills in the reporting officer and the transactor details. "
        "Please check it for missing required fields before it is filed: ",
        "This STR draft has the reporting officer and the transactor's details filled in "
        "as well. Please check it for missing required fields before it is filed: "),
}

JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)
NON_WORD = re.compile(r"[^0-9a-z가-힣]+")


def prose(question: str) -> str:
    """The question without its JSON payload, normalised, as `new_cases.verify` does it."""
    return NON_WORD.sub(" ", JSON_BLOCK.sub(" ", question).lower()).strip()


def grams(text: str) -> set[str]:
    text = re.sub(r"\s+", " ", text)
    return {text[i:i + 3] for i in range(max(len(text) - 2, 1))}


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def apply_questions(bench: Bench, lang: str, table: dict[str, tuple[str, str]],
                    issue: str, why: str, log: ChangeLog) -> None:
    """The tables hold the prose head; an STR draft follows it unchanged."""
    by_id = bench.by_id()
    for case_id, (before, after) in table.items():
        case = by_id.get(case_id)
        if case is None:
            raise SystemExit(f"{case_id}: absent from {bench.root.name}")
        head, brace, payload = case["question"].partition("{")
        if head == after:
            continue
        if head != before:
            raise SystemExit(f"{case_id} ({lang}): the question is neither the as-is nor the to-be")
        log.set_field(case, lang, "question", after + brace + payload, issue, why)


def add_alternative(kr: Bench, en: Bench, log: ChangeLog) -> None:
    why = ("min_transactions defaults to 10, so 'without any conditions' has to pin a value; "
           "0 and 1 both say no condition and the tool answers identically, so both are "
           "accepted (closeout verification F10).")
    for bench, lang in ((kr, "kr"), (en, "en")):
        case = bench.get(ALTERNATIVE_CASE)
        if case is None:
            raise SystemExit(f"{ALTERNATIVE_CASE}: absent from {bench.root.name}")
        expected = copy.deepcopy(case["expected"])
        alternatives = expected.get("alternatives") or []
        if any(a == ALTERNATIVE for a in alternatives):
            continue
        expected["alternatives"] = alternatives + [copy.deepcopy(ALTERNATIVE)]
        log.set_field(case, lang, "expected", expected, "L1-016", why)


def residue(en: Bench) -> list[str]:
    gram = {case["id"]: grams(prose(case["question"])) for _, case in en.cases()}
    out = []
    for a, b in RESOLVED_PAIRS:
        score = jaccard(gram[a], gram[b])
        if score >= SIMILARITY_LIMIT:
            out.append(f"{a}/{b}: still {score:.3f}")
    reworded = set(NEAR_DUPLICATE_EN)
    for a, b in itertools.combinations(sorted(gram), 2):
        if (a in reworded or b in reworded) and (a, b) not in RESOLVED_PAIRS:
            score = jaccard(gram[a], gram[b])
            if score >= SIMILARITY_LIMIT:
                out.append(f"{a}/{b}: rewording created a new pair at {score:.3f}")
    return out


def pair_count(en: Bench) -> int:
    gram = {case["id"]: grams(prose(case["question"])) for _, case in en.cases()}
    return sum(1 for a, b in itertools.combinations(sorted(gram), 2)
               if jaccard(gram[a], gram[b]) >= SIMILARITY_LIMIT)


def main() -> int:
    kr, en = both()
    log = ChangeLog("p26_closeout_nits",
                    "The low-severity closeout findings: five English near-duplicate "
                    "pairs, one over-pinned argument, two fluency nits (F9, F10, F11).")
    apply_questions(en, "en", NEAR_DUPLICATE_EN, "L1-023",
                    "p14 rewrote these onto one phrase and created an English "
                    "near-duplicate pair (closeout verification F9).", log)
    apply_questions(en, "en", FLUENCY_EN, "L2-015",
                    "English fluency, found in the closeout's fresh 50-pair read (F11).", log)
    add_alternative(kr, en, log)
    left = residue(en)
    if left:
        raise SystemExit("the near-duplicate pairs are not resolved:\n  " + "\n  ".join(left))
    kr.save()
    en.save()
    n = pair_count(en)
    log.note(f"English pairs at or above {SIMILARITY_LIMIT} Jaccard: {n} "
             f"(83 before this pass, 78 before the 2026-09-16 round).")
    log.note("The five pairs the round created are now 0.44 to 0.62, and no reworded "
             "question is within the limit of any other question.")
    print(log.report())
    print(f"English near-duplicate pairs >= {SIMILARITY_LIMIT}: {n}")
    print(f"log: {log.write()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
