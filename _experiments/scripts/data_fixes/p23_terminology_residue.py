"""Pass 23 - the terminology collision `p20` left behind (L1-010, review ask A).

`p20_terminology` gave every pattern one spelling, but its residue screen banned only
구조화/깔때기/집금/ring/layering and it only ever loaded the two single-turn directories.
Five places therefore survived, all of them the same collision: the Korean names HOFINET
fraud type 3 (분할 거래) where the gold calls a `structuring` tool.

| place | gold | what the Korean said |
|---|---|---|
| `st_fiu_001` | `lookup_fiu_reference_types(keyword='structuring')` | 분할거래 |
| `st_mtool_106` | `lookup_fiu_reference_types(keyword='structuring')` | 분할 거래 |
| `mt_str_010#t3` | `detect_ctr_candidates(mode='structuring')` | 분할거래 |
| `mt_str_039#t3` | `detect_ctr_candidates(mode='structuring')` | 분할거래 |
| `mt_str_049#t3` | `detect_ctr_candidates(mode='structuring')` | 분할거래 |

For the two single-turn cases it costs a correct model the case: the literal reading of
both arms is `keyword='split'`, which returns two catalog rows (`Banking Deposits-Split
17` and `Securities In/Out 2`) against the gold's one, so the check fails and the case
scores 0. The three multi-turn turns are the same wording defect without that cost,
because their English arm already said structuring.

This pass rewords the two single-turn cases. The three multi-turn turns are fixed in
`multiturn/scenarios.py` and `multiturn/scenarios_c.py`, because the multi-turn data is
built from that spec and carries no hand edits.

What stops the class from coming back is `terminology.py`: one screen, run here over
both single-turn arms and over both multi-turn files, and run again by
`lint_benchmarks` and by `multiturn.verify`. It knows the whole term list and it knows
which side of the structuring / fraud-type-3 line each case's gold is on.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from . import terminology
from .common import REPO, Bench, ChangeLog, both

ISSUE = "L1-010"
WHY = ("the gold calls a structuring tool, so the question names structuring; 분할 거래 / "
       "split transaction is HOFINET fraud type 3, which a different tool answers "
       "(domain review 2026-09-16, ask A).")

MULTITURN = [(REPO / "benchmarks_multiturn" / "cases_str_workflow.json", "kr"),
             (REPO / "benchmarks_multiturn_en" / "cases_str_workflow.json", "en")]

KR = {
    "st_fiu_001":
        ("분할거래에 해당하는 FIU 참고유형을 검색해줘",
         "structuring에 해당하는 FIU 참고유형을 검색해줘"),
    "st_mtool_106":
        ("아래 STR 초안의 필수 항목을 검증하고, 초안의 의심 유형인 분할 거래에 대응하는 FIU 참고유형도 찾아줘: ",
         "아래 STR 초안의 필수 항목을 검증하고, 초안이 기술한 structuring에 해당하는 FIU 참고유형도 찾아줘: "),
}
EN = {
    "st_fiu_001":
        ("Please search for the FIU reference types related to split transactions.",
         "Please search for the FIU reference types related to structuring."),
    "st_mtool_106":
        ("Please validate the required fields of the STR draft below, and find the FIU "
         "reference type that corresponds to split transactions, the suspicion type the "
         "draft records: ",
         "Please validate the required fields of the STR draft below, and find the FIU "
         "reference type for the structuring the draft describes: "),
}


def apply_one(bench: Bench, lang: str, table: dict[str, tuple[str, str]], log: ChangeLog) -> None:
    """The tables hold the prose head of the question; an STR draft follows it unchanged.

    Splitting on the first `{` keeps the draft out of the table, so a draft that a later
    pass rebuilds does not silently invalidate this one.
    """
    by_id = bench.by_id()
    for case_id, (before, after) in table.items():
        case = by_id.get(case_id)
        if case is None:
            raise SystemExit(f"{case_id}: absent from {bench.root.name}")
        question = case["question"]
        head, brace, payload = question.partition("{")
        if head == after:
            continue                       # already applied
        if head != before:
            raise SystemExit(f"{case_id} ({lang}): the question is neither the as-is nor the to-be")
        log.set_field(case, lang, "question", after + brace + payload, ISSUE, WHY)


def screen(kr: Bench, en: Bench) -> list[str]:
    left = terminology.screen_single_turn(kr, "kr") + terminology.screen_single_turn(en, "en")
    for path, lang in MULTITURN:
        if not path.exists():
            continue
        left += terminology.screen_multiturn(json.loads(path.read_text(encoding="utf-8")), lang)
    return left


def main() -> int:
    kr, en = both()
    log = ChangeLog("p23_terminology_residue",
                    "The terminology collision p20 left behind, and one screen over all "
                    "four benchmark directories (L1-010).")
    apply_one(kr, "kr", KR, log)
    apply_one(en, "en", EN, log)
    left = screen(kr, en)
    if left:
        raise SystemExit("the terminology convention is still broken:\n  " + "\n  ".join(left))
    kr.save()
    en.save()
    log.note("The three multi-turn turns are fixed in the scenario spec, because the "
             "multi-turn files are built from it: mt_str_010#t3 (scenarios.py), "
             "mt_str_039#t3 and mt_str_049#t3 (scenarios_c.py).")
    log.note("The screen now covers all four directories and the whole term list "
             "(terminology.py). lint_benchmarks and multiturn.verify run it too.")
    print(log.report())
    print(f"screened: 4 directories, 0 residues")
    print(f"log: {log.write()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
