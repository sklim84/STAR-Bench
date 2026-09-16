"""Pass 27 - make three clarification cases turn on a missing argument, not a convention.

The lead's call on F13. D19 admits a clarification case when a schema-required argument,
or an unresolved reference to it, is missing. These three met that rule through the
reference alone, so a model could answer them without asking back and still be sensible:

  st_mp_005  "위험도가 높은 계좌를 평가해줘"          rank_risky_transactions needs no argument
  st_mp_014  "해당 규칙의 모니터링 알림을 확인해줘"    rule_id has an `all` value
  st_mp_026  "앞에서 말한 조회 모드로 CTR 대상 거래"   "CTR 대상 거래" reads as mode=high_value

Each question now names one target the tool cannot reach without the argument: a single
account for score_account_risk (account_id), a single rule for detect_monitoring_alerts
(rule_id, where `all` is the wrong answer), and a CTR query whose mode is explicitly not
decided (detect_ctr_candidates.mode). st_mp_005 also drops the rank_risky_transactions
alternative, which existed because the old wording admitted it.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import ChangeLog, both
from .p22_clarification_audit import schemas

REWRITE = {
    "st_mp_005": {
        "kr": ("위험도가 높은 계좌를 평가해줘",
               "특정 계좌 하나의 AML 위험 점수를 산출해줘"),
        "en": ("Please evaluate the accounts with a high risk level.",
               "Please compute the AML risk score for one particular account."),
        "tool": "score_account_risk",
        "argument": "account_id",
        "drop_alternatives": True,
    },
    "st_mp_014": {
        "kr": ("해당 규칙의 모니터링 알림을 확인해줘",
               "모니터링 규칙 하나만 골라서 그 규칙의 알림을 확인해줘"),
        "en": ("Please check the monitoring alerts for the relevant rules.",
               "Please pick one monitoring rule and check the alerts for that rule alone."),
        "tool": "detect_monitoring_alerts",
        "argument": "rule_id",
        "drop_alternatives": False,
    },
    "st_mp_026": {
        "kr": ("앞에서 말한 조회 모드로 CTR 대상 거래를 뽑아줘",
               "CTR 후보 거래를 뽑아줘. 어떤 조회 모드로 볼지는 아직 정하지 않았어"),
        "en": ("Please pull the CTR candidate transactions in the query mode we talked about.",
               "Please pull the CTR candidate transactions. We have not decided which query "
               "mode to use yet."),
        "tool": "detect_ctr_candidates",
        "argument": "mode",
        "drop_alternatives": False,
    },
}


def main() -> int:
    kr, en = both()
    log = ChangeLog("p27_clarification_gap",
                    "three clarification cases now turn on a missing required argument")
    required_by_tool = schemas()
    for case_id, spec in REWRITE.items():
        if required_by_tool is not None:
            required = required_by_tool.get(spec["tool"], [])
            if spec["argument"] not in required:
                raise SystemExit(f"{case_id}: {spec['tool']}.{spec['argument']} is not "
                                 "required by the schema, so the case cannot rest on it")
        for bench, lang in ((kr, "kr"), (en, "en")):
            case = bench.get(case_id)
            as_is, to_be = spec[lang]
            if case["question"] != as_is:
                raise SystemExit(f"{case_id} ({lang}): question is not the expected as-is")
            log.set_field(case, lang, "question", to_be, "F13",
                          f"the {spec['tool']}.{spec['argument']} gap is now in the question "
                          "itself, not in a reference to earlier context")
            if spec["drop_alternatives"] and "alternatives" in case["expected"]:
                removed = case["expected"].pop("alternatives")
                log.record(case_id, lang, "expected.alternatives", removed, None, "F13",
                           "the wording that admitted rank_risky_transactions is gone")
            if not case["expected"].get("expect_clarification"):
                raise SystemExit(f"{case_id} ({lang}): still has to be a clarification case")
    kr.save()
    en.save()
    log.write()
    print(log.report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
