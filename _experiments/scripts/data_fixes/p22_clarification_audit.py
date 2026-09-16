"""Pass 22 - re-derive every clarification case against D19 (domain review, ask B).

The reviewer asked, on st_mp_026 to st_mp_044, whether "no tool call" is really right.
D19 says a clarification case is one where a schema-required argument, or an unresolved
reference to it, is missing, so the tool cannot be called at all: not one where the tool
would run on its defaults and return something less useful.

This pass carries the derivation, one line per case: the tool the question points at and
the argument it leaves unresolved. It checks each of those against the tool's own schema
and fails if the argument is not required, so the table cannot drift away from the
platform. It changes no data; it is the record that the 40 cases were re-derived.

`detect_aml_patterns` is the one tool whose JSON schema cannot express what it enforces:
`required` holds `pattern_type` alone, while the `account_a` and `account_b` descriptions
say "required for shortest_path" and the tool returns an error without them. Those two
are listed in `ENUM_CONDITIONAL`, and when the platform is importable the pass executes
the call to confirm the tool really refuses it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both

# Arguments a tool enforces for one enum value although the JSON schema cannot say so.
ENUM_CONDITIONAL = {
    ("detect_aml_patterns", "account_a"): "pattern_type=shortest_path",
    ("detect_aml_patterns", "account_b"): "pattern_type=shortest_path",
}

# case id -> (tool the question points at, the required arguments it leaves unresolved)
DERIVATION: dict[str, tuple[str, tuple[str, ...]]] = {
    "st_gir_irr_002": ("get_institution_report", ("bank_id",)),
    "st_mp_001": ("get_aml_glossary", ("term",)),
    "st_mp_002": ("analyze_network", ("account_id",)),
    "st_mp_003": ("get_institution_report", ("bank_id",)),
    "st_mp_004": ("lookup_fiu_reference_types", ("keyword",)),
    "st_mp_005": ("score_account_risk", ("account_id",)),
    "st_mp_006": ("get_account_profile", ("account_id",)),
    "st_mp_007": ("compare_periods", ("period1_start", "period1_end",
                                      "period2_start", "period2_end")),
    "st_mp_008": ("get_institution_report", ("bank_id",)),
    "st_mp_009": ("detect_smurfing_network", ("direction",)),
    "st_mp_010": ("get_fraud_type_summary", ("fraud_type",)),
    "st_mp_011": ("detect_aml_patterns", ("account_a", "account_b")),
    "st_mp_014": ("detect_monitoring_alerts", ("rule_id",)),
    "st_mp_015": ("validate_str_fields", ("str_draft",)),
    "st_mp_016": ("compare_periods", ("period1_start", "period1_end",
                                      "period2_start", "period2_end")),
    "st_mp_017": ("predict_fraud", ("time_slot", "sender_bank", "receiver_bank",
                                    "fund_type", "media_type", "amount")),
    "st_mp_018": ("detect_aml_patterns", ("account_a", "account_b")),
    "st_mp_020": ("get_receiving_account_profile", ("account_id",)),
    "st_mp_022": ("detect_aml_patterns", ("pattern_type",)),
    "st_mp_024": ("detect_smurfing_network", ("direction",)),
    "st_mp_025": ("get_institution_report", ("bank_id",)),
    "st_mp_026": ("detect_ctr_candidates", ("mode",)),
    "st_mp_027": ("score_account_risk", ("account_id",)),
    "st_mp_028": ("predict_fraud", ("time_slot", "sender_bank", "receiver_bank",
                                    "fund_type", "media_type", "amount")),
    "st_mp_029": ("query_transactions", ("sql",)),
    "st_mp_030": ("get_fraud_type_summary", ("fraud_type",)),
    "st_mp_031": ("compare_periods", ("period1_start", "period1_end",
                                      "period2_start", "period2_end")),
    "st_mp_032": ("get_institution_report", ("bank_id",)),
    "st_mp_033": ("detect_aml_patterns", ("account_b",)),
    "st_mp_034": ("get_aml_glossary", ("term",)),
    "st_mp_035": ("lookup_fiu_reference_types", ("keyword",)),
    "st_mp_036": ("validate_str_fields", ("str_draft",)),
    "st_mp_037": ("analyze_network", ("account_id",)),
    "st_mp_038": ("get_account_profile", ("account_id",)),
    "st_mp_039": ("get_receiving_account_profile", ("account_id",)),
    "st_mp_040": ("detect_smurfing_network", ("direction",)),
    "st_mp_041": ("detect_monitoring_alerts", ("rule_id",)),
    "st_mp_042": ("detect_aml_patterns", ("pattern_type",)),
    "st_mp_043": ("predict_fraud", ("sender_bank", "receiver_bank", "fund_type")),
    "st_mp_044": ("query_transactions", ("sql",)),
}


def schemas() -> dict[str, list[str]] | None:
    """tool -> required arguments, from the platform; None when it is not importable."""
    try:
        from _experiments.scripts._platform import ensure_platform_on_path  # noqa: PLC0415

        ensure_platform_on_path()
        from src.features.agent import TOOLS  # noqa: PLC0415
    except Exception:                          # noqa: BLE001 - the pass still runs without it
        return None
    return {t["function"]["name"]: list(t["function"]["parameters"].get("required") or [])
            for t in TOOLS}


def enum_conditional_really_refuses() -> str | None:
    """Evidence that detect_aml_patterns refuses shortest_path without its accounts."""
    try:
        from _experiments.scripts._platform import ensure_platform_on_path  # noqa: PLC0415

        ensure_platform_on_path()
        from src.features.agent import _execute_tool  # noqa: PLC0415

        payload = json.loads(_execute_tool("detect_aml_patterns",
                                           {"pattern_type": "shortest_path"}))
    except Exception:                          # noqa: BLE001
        return None
    return str(payload.get("error") or "")


def audit(kr: Bench) -> tuple[list[dict], list[str]]:
    required = schemas()
    rows, problems = [], []
    declared = {case["id"] for _, case in kr.cases()
                if case["expected"].get("expect_clarification")}
    if declared != set(DERIVATION):
        missing = sorted(declared - set(DERIVATION))
        extra = sorted(set(DERIVATION) - declared)
        if missing:
            problems.append(f"clarification cases with no derivation: {missing}")
        if extra:
            problems.append(f"derivations for cases that are not clarifications: {extra}")
    by_id = kr.by_id()
    for case_id, (tool, missing_args) in sorted(DERIVATION.items()):
        case = by_id.get(case_id)
        if case is None:
            problems.append(f"{case_id}: absent from the benchmark")
            continue
        kinds = []
        for arg in missing_args:
            if required is not None and arg in required.get(tool, []):
                kinds.append("schema-required")
            elif (tool, arg) in ENUM_CONDITIONAL:
                kinds.append(f"required for {ENUM_CONDITIONAL[(tool, arg)]}")
            elif required is None:
                kinds.append("unchecked (platform not importable)")
            else:
                problems.append(f"{case_id}: {tool}.{arg} is not required, so the tool would "
                                f"run without it and D19 does not hold")
                kinds.append("NOT REQUIRED")
        rows.append({"case_id": case_id, "tool": tool, "unresolved": list(missing_args),
                     "kind": kinds, "question": case["question"]})
    return rows, problems


def main() -> int:
    kr, _ = both()
    rows, problems = audit(kr)
    log = ChangeLog("p22_clarification_audit",
                    "Every expect_clarification case re-derived against D19 (review ask B).")
    log.note(f"{len(rows)} clarification cases; each leaves a required argument of the tool "
             f"the question points at unresolved, so the tool cannot be called.")
    refusal = enum_conditional_really_refuses()
    if refusal is not None:
        log.note(f"detect_aml_patterns(pattern_type=shortest_path) without accounts -> {refusal!r}")
    for row in rows:
        log.note(f"{row['case_id']}: {row['tool']} needs {', '.join(row['unresolved'])} "
                 f"({', '.join(sorted(set(row['kind'])))})")
    print(log.report())
    print(f"log: {log.write()}")
    for row in rows:
        print(f"  {row['case_id']:16s} {row['tool']:32s} {', '.join(row['unresolved'])}")
    if problems:
        print("\nproblems:")
        for p in problems:
            print(" -", p)
        return 1
    print(f"\n{len(rows)} clarification cases, 0 problems")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
