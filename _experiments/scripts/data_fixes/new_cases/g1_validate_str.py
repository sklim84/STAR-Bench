"""Group 1 - `validate_str_fields` cases (3 -> 25).

Every case carries a full STR draft in the question. The draft is built from
one real HOFINET transfer aggregate in `grounding.json`: the two account numbers,
the withdrawal institution code, the channel, the window, the transaction count and
the total amount are the values that pair actually has in that window, so a reviewer
can check the draft against the data.

The 22 drafts differ in the defect the validator has to find: complete drafts, one
missing required field per required field, a whole missing section, a placeholder
value, an empty string, two fields missing at once, the section names earlier drafts
used, field names written in another style, and drafts with no sections at all.
"""

from __future__ import annotations

import calendar
import json

FRAUD_LABEL = {
    1: "Sudden Change in Transaction Pattern",
    2: "Transaction with New Counterparty",
    3: "Split Transaction",
    4: "Concurrent Multiple Transactions",
    5: "Same-Day Withdrawal after Large Deposit",
    7: "Late-Night/Early-Morning Bulk Transactions",
}
CHANNEL = {1: "PC Banking", 2: "Internet Banking", 3: "Phone", 4: "Mobile Phone",
           5: "Per-transaction Transfer", 6: "Other", 7: "Bulk Transfer"}
NARRATIVE = {
    1: "{n} transfers totalling {amount} KRW left the account between {d0} and {d1}, "
       "far above its usual volume for the channel.",
    2: "{n} transfers totalling {amount} KRW went between {d0} and {d1} to a receiving "
       "account with no earlier transaction history with this customer.",
    3: "{n} transfers totalling {amount} KRW were sent to the same receiving account "
       "between {d0} and {d1}, each one below the reporting threshold.",
    4: "{n} transfers totalling {amount} KRW to the same receiving account were requested "
       "together between {d0} and {d1}.",
    5: "Funds of {amount} KRW received between {d0} and {d1} were moved out again the same "
       "day over {n} transfers.",
    7: "{n} transfers totalling {amount} KRW were made in the 21:00-24:00 slot between "
       "{d0} and {d1}.",
}
ALIAS_SECTIONS = {"I_ReportingInstitution": "I_Reporting_Institution", "II_Transactor": "II_Trader",
                  "III_TransactionDetails": "III_Transaction_Details",
                  "VI_TransactionType": "VI_Transaction_Type", "VII_Narrative": "VII_Narrative_Description"}
LOOSE_FIELDS = {"ReportingDate": "reporting_date", "WithdrawalInstitutionCode": "withdrawal_institution_code",
                "WithdrawalAccountNumber": "withdrawal_account_number",
                "ReceivingAccountNumber": "receiving_account_number",
                "TransactionPeriod": "transaction_period", "TransactionCount": "transaction_count",
                "TransactionChannel": "transaction_channel", "TotalAmount_KRW": "total_amount_krw",
                "PrimarySuspicionType": "primary_suspicion_type",
                "SuspicionJudgmentReason": "suspicion_judgment_reason"}

OPTIONAL_FULL = {
    "I_ReportingInstitution": {"InstitutionName": "Reporting Bank", "MLROName": "Reporting Officer",
                               "OfficerName": "AML Analyst", "OfficerPhone": "02-0000-0000"},
    "II_Transactor": {"Name": "Account Holder", "IdType": "Resident Registration Number",
                      "IdNumber": "000000-0000000", "Nationality": "KR"},
    "III_TransactionDetails": {"TransactionType": "Wire Transfer"},
    "VII_Narrative": {"OverallOpinion": "Recommended for reporting to the FIU.",
                      "SuspicionIntensity_1to5": 4},
}
OPTIONAL_PARTIAL = {
    "I_ReportingInstitution": {"InstitutionName": "Reporting Bank", "MLROName": "Reporting Officer"},
    "VII_Narrative": {"SuspicionIntensity_1to5": 3},
}


def reporting_date(date_to: int) -> str:
    """The last day of the month the window ends in, capped at the end of the data."""
    year, month = divmod(date_to // 100, 100)
    last = calendar.monthrange(year, month)[1]
    return str(min(year * 10000 + month * 100 + last, 20241231))


def money(value: int) -> str:
    return f"{value:,}"


def base_draft(row: dict) -> dict:
    d0, d1 = str(row["date_from"]), str(row["date_to"])
    return {
        "Header": {"ReportingDate": reporting_date(row["date_to"])},
        "I_ReportingInstitution": {"WithdrawalInstitutionCode": row["sender_bank"]},
        "II_Transactor": {"WithdrawalAccountNumber": str(row["sender_acc"]),
                          "ReceivingAccountNumber": str(row["receiver_acc"])},
        "III_TransactionDetails": {"TransactionPeriod": f"{d0}-{d1}", "TransactionCount": row["count"],
                                   "TransactionChannel": CHANNEL[row["media_type"]],
                                   "TotalAmount_KRW": row["total_amount"]},
        "VI_TransactionType": {"PrimarySuspicionType": FRAUD_LABEL[row["fraud_type"]]},
        "VII_Narrative": {"SuspicionJudgmentReason": NARRATIVE[row["fraud_type"]].format(
            n=row["count"], amount=money(row["total_amount"]), d0=d0, d1=d1)},
    }


def drop(draft: dict, *paths: str) -> dict:
    for path in paths:
        section, field = path.split(".")
        draft[section].pop(field, None)
    return draft


def drop_section(draft: dict, section: str) -> dict:
    draft.pop(section, None)
    return draft


def set_value(draft: dict, path: str, value) -> dict:
    section, field = path.split(".")
    draft[section][field] = value
    return draft


def merge_optional(draft: dict, extra: dict) -> dict:
    for section, fields in extra.items():
        draft.setdefault(section, {}).update(fields)
    return draft


def alias(draft: dict) -> dict:
    return {ALIAS_SECTIONS.get(k, k): v for k, v in draft.items()}


def loose(draft: dict) -> dict:
    return {section: {LOOSE_FIELDS.get(k, k): v for k, v in fields.items()}
            for section, fields in draft.items()}


def flatten(draft: dict) -> dict:
    out = {}
    for fields in draft.values():
        out.update(fields)
    return out


# id suffix, how the draft is shaped, the Korean ask, the English ask, the rationale.
VARIANTS = [
    ("004", lambda d: d,
     "다음 STR 초안이 FIU 양식의 필수 항목을 모두 갖췄는지 검증해줘",
     "Please check whether the following STR draft carries every field the FIU form requires",
     "complete draft; the validator has to report that nothing required is missing"),
    ("005", lambda d: merge_optional(d, OPTIONAL_FULL),
     "보고 담당자와 거래자 인적사항까지 채운 STR 초안이야. 제출 전에 필수 항목 누락 여부를 점검해줘",
     "This STR draft also fills in the reporting officer and the transactor details. "
     "Please check it for missing required fields before it is filed",
     "complete draft with the optional personal fields filled in as well"),
    ("006", lambda d: merge_optional(d, OPTIONAL_PARTIAL),
     "아래 STR 초안에서 필수 항목과 선택 항목 중 비어 있는 것을 정리해줘",
     "Please list which required and optional items are still empty in the STR draft below",
     "complete draft with two optional fields filled; exercises missing_optional"),
    ("007", lambda d: drop(d, "Header.ReportingDate"),
     "다음 의심거래보고서 초안의 필수 필드 누락 여부를 확인해줘",
     "Please check the following suspicious transaction report draft for missing required fields",
     "Header.ReportingDate removed"),
    ("008", lambda d: drop(d, "I_ReportingInstitution.WithdrawalInstitutionCode"),
     "이 STR 초안을 양식 기준으로 검증해서 빠진 항목을 알려줘",
     "Please validate this STR draft against the form and tell me which items are missing",
     "I_ReportingInstitution.WithdrawalInstitutionCode removed"),
    ("009", lambda d: drop(d, "II_Transactor.WithdrawalAccountNumber"),
     "아래 초안에서 거래자 정보가 제대로 채워졌는지 필수 항목 기준으로 점검해줘",
     "Please check, against the required fields, whether the transactor details in the draft "
     "below are complete",
     "II_Transactor.WithdrawalAccountNumber removed"),
    ("010", lambda d: drop(d, "II_Transactor.ReceivingAccountNumber"),
     "다음 STR 초안에 필수 항목이 빠진 곳이 있는지 확인해줘",
     "Please check whether anything required is missing from the following STR draft",
     "II_Transactor.ReceivingAccountNumber removed"),
    ("011", lambda d: drop(d, "III_TransactionDetails.TransactionPeriod"),
     "거래내역 항목이 양식 요건을 충족하는지 아래 STR 초안으로 검증해줘",
     "Please validate the STR draft below and say whether the transaction detail section "
     "meets the form requirements",
     "III_TransactionDetails.TransactionPeriod removed"),
    ("012", lambda d: drop(d, "III_TransactionDetails.TransactionCount"),
     "이 초안 그대로 제출해도 되는지 필수 항목 검증을 돌려줘",
     "Please run the required-field validation and tell me whether this draft can be filed as it is",
     "III_TransactionDetails.TransactionCount removed"),
    ("013", lambda d: drop(d, "III_TransactionDetails.TransactionChannel"),
     "아래 STR 초안에서 보완해야 할 필수 항목을 짚어줘",
     "Please point out the required items that still have to be filled in the STR draft below",
     "III_TransactionDetails.TransactionChannel removed"),
    ("014", lambda d: drop(d, "III_TransactionDetails.TotalAmount_KRW"),
     "다음 STR 초안의 거래금액 관련 필수 항목이 채워졌는지 검증해줘",
     "Please validate whether the amount-related required items of the following STR draft "
     "are filled in",
     "III_TransactionDetails.TotalAmount_KRW removed"),
    ("015", lambda d: drop(d, "VI_TransactionType.PrimarySuspicionType"),
     "의심거래 분류까지 포함해서 이 초안의 필수 항목을 점검해줘",
     "Please check the required items of this draft, the suspicion classification included",
     "VI_TransactionType.PrimarySuspicionType removed"),
    ("016", lambda d: drop(d, "VII_Narrative.SuspicionJudgmentReason"),
     "아래 초안이 STR 양식 필수 요건을 만족하는지 확인해줘",
     "Please confirm whether the draft below satisfies the required items of the STR form",
     "VII_Narrative.SuspicionJudgmentReason removed"),
    ("017", lambda d: drop_section(d, "VII_Narrative"),
     "이 STR 초안에서 통째로 빠진 항목이 있는지 검증해줘",
     "Please validate whether a whole section is missing from this STR draft",
     "the VII_Narrative section is absent altogether"),
    ("018", lambda d: set_value(d, "III_TransactionDetails.TransactionChannel", "unknown"),
     "다음 STR 초안에 값이 제대로 들어가지 않은 필수 항목이 있는지 점검해줘",
     "Please check the following STR draft for required items whose value was not really filled in",
     "TransactionChannel carries the placeholder 'unknown', which does not count as filled"),
    ("019", lambda d: set_value(d, "VII_Narrative.SuspicionJudgmentReason", ""),
     "빈 값으로 남은 필수 항목이 있는지 아래 STR 초안을 검증해줘",
     "Please validate the STR draft below for required items left empty",
     "SuspicionJudgmentReason is an empty string"),
    ("020", lambda d: drop(d, "Header.ReportingDate", "VI_TransactionType.PrimarySuspicionType"),
     "이 STR 초안에서 누락된 필수 항목을 모두 찾아줘",
     "Please find every required item missing from this STR draft",
     "two required fields removed: ReportingDate and PrimarySuspicionType"),
    ("021", lambda d: drop(d, "II_Transactor.ReceivingAccountNumber",
                           "III_TransactionDetails.TotalAmount_KRW"),
     "아래 초안을 제출하기 전에 필수 항목 누락을 확인하고 보완할 항목을 알려줘",
     "Before the draft below is filed, please check it for missing required items and say what "
     "has to be added",
     "two required fields removed: ReceivingAccountNumber and TotalAmount_KRW"),
    ("022", lambda d: alias(d),
     "예전 양식 이름으로 작성된 STR 초안인데, 필수 항목 기준으로 검증해줘",
     "This STR draft uses the older section names. Please validate it against the required fields",
     "the section names earlier drafts used; the validator resolves them"),
    ("023", lambda d: loose(d),
     "필드 이름 표기가 다른 STR 초안이야. 필수 항목이 다 들어갔는지 확인해줘",
     "This STR draft spells the field names differently. Please check whether every required "
     "item is there",
     "field names in snake_case; the validator matches ignoring case and underscores"),
    ("024", lambda d: flatten(d),
     "섹션 구분 없이 평평하게 작성된 STR 초안의 필수 항목을 점검해줘",
     "Please check the required items of this STR draft, which is written flat with no sections",
     "a flat draft with no section nesting"),
    ("025", lambda d: flatten(drop(d, "III_TransactionDetails.TransactionChannel")),
     "섹션 없이 작성된 아래 초안에서 빠진 필수 항목을 알려줘",
     "Please tell me which required items are missing from the draft below, which has no sections",
     "a flat draft that is also missing TransactionChannel"),
]


def build(grounding: dict) -> list[dict]:
    rows = grounding["str_sources"]
    cases = []
    for index, (suffix, shape, ask_kr, ask_en, rationale) in enumerate(VARIANTS):
        draft = shape(base_draft(rows[index % len(rows)]))
        text = json.dumps(draft, ensure_ascii=False)
        cases.append({
            "id": f"st_strv_{suffix}",
            "file": "cases_validate_str_fields.json",
            "question": f"{ask_kr}: {text}",
            "question_en": f"{ask_en}: {text}",
            "expected": {
                "primary_tool": "validate_str_fields",
                "tools_must_include": ["validate_str_fields"],
                "param_checks": {"validate_str_fields": {"str_draft": draft}},
            },
            "rationale": rationale,
        })
    return cases
