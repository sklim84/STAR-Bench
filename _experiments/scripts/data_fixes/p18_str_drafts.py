"""Pass 18 - the three pre-existing STR drafts are rebuilt on real aggregates (L1-014).

`p08_clarification` wrote a draft into each of the three `validate_str_fields` questions
so the tool had something to validate (D19), but the figures were invented: the account
pairs never transact, the periods and counts describe nothing, and the
`WithdrawalInstitutionCode` was not the sender's bank. The 22 drafts WS-G added are
built from real HOFINET transfer aggregates (`new_cases/grounding.json`), and these
three are now built the same way, by the same code, so the draft can be checked against
the data.

Each case keeps the defect it was written to test: `st_strv_001` an empty
`VII_Narrative`, `st_strv_002` a missing `TransactionChannel`, `st_strv_003` an empty
`VI_TransactionType`. The grounding row of each is one no WS-G variant uses with the
same defect, so no two cases carry the same draft.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both, load_json
from .new_cases.g1_validate_str import base_draft, drop

GROUNDING = Path(__file__).resolve().parent / "new_cases" / "grounding.json"
ISSUE = "L1-014/D19"
WHY = ("the draft stated a period, a count and a total for an account pair that never "
       "transacts, at an institution that is not the sender's bank; it is rebuilt from the "
       "HOFINET aggregate the same way the 22 expansion drafts are.")

# case id -> (grounding row, the field the case is written to leave out, Korean ask, English ask)
CASES = {
    "st_strv_001": (10, "VII_Narrative.SuspicionJudgmentReason",
                    "다음 STR 초안의 필수 필드가 모두 채워졌는지 점검해줘",
                    "Please check whether every required field of this STR draft is filled in"),
    "st_strv_002": (15, "III_TransactionDetails.TransactionChannel",
                    "다음 STR 보고서 초안에 필수 항목이 누락되었는지 검증해줘",
                    "Please verify whether any required item is missing from this draft STR report"),
    "st_strv_003": (19, "VI_TransactionType.PrimarySuspicionType",
                    "다음 초안이 의심거래보고서 양식의 필수 필드를 갖췄는지 확인해줘",
                    "Please check whether this draft carries the required fields of the "
                    "suspicious transaction report form"),
}


def drafts() -> dict[str, dict]:
    rows = load_json(GROUNDING)["str_sources"]
    out = {}
    for case_id, (index, field, _, _) in CASES.items():
        out[case_id] = drop(base_draft(rows[index]), field)
    return out


def clashes(kr: Bench, built: dict[str, dict]) -> list[str]:
    """No other case may carry the same draft: that would be the same question twice."""
    key = lambda d: json.dumps(d, ensure_ascii=False, sort_keys=True)  # noqa: E731
    existing: dict[str, str] = {}
    for _, case in kr.cases():
        checks = (case["expected"].get("param_checks") or {}).get("validate_str_fields") or {}
        draft = checks.get("str_draft")
        if isinstance(draft, dict) and case["id"] not in built:
            existing.setdefault(key(draft), case["id"])
    out = []
    for case_id, draft in built.items():
        other = existing.get(key(draft))
        if other:
            out.append(f"{case_id}: the same draft as {other}")
    return out


def main() -> int:
    kr, en = both()
    built = drafts()
    bad = clashes(kr, built)
    if bad:
        raise SystemExit("rebuilt drafts collide:\n  " + "\n  ".join(bad))
    log = ChangeLog("p18_str_drafts",
                    "The three pre-existing validate_str_fields drafts rebuilt from real "
                    "HOFINET aggregates (L1-014).")
    for case_id, (_, _, ask_kr, ask_en) in CASES.items():
        draft = built[case_id]
        text = json.dumps(draft, ensure_ascii=False)
        gold = {
            "primary_tool": "validate_str_fields",
            "tools_must_include": ["validate_str_fields"],
            "param_checks": {"validate_str_fields": {"str_draft": copy.deepcopy(draft)}},
        }
        for bench, lang, ask in ((kr, "kr", ask_kr), (en, "en", ask_en)):
            case = bench.get(case_id)
            if case is None:
                raise SystemExit(f"{case_id}: absent from {bench.root.name}")
            log.set_field(case, lang, "question", f"{ask}: {text}", ISSUE, WHY)
            log.set_field(case, lang, "expected", copy.deepcopy(gold), ISSUE, WHY)
    kr.save()
    en.save()
    log.note("grounding rows 10, 15 and 19 of new_cases/grounding.json; each draft keeps the "
             "required field its case was written to miss.")
    print(log.report())
    print(f"log: {log.write()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
