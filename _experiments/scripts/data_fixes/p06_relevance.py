"""Pass 06 - what counts as a no-tool request (D10; L1-001, L6-009, L3-011).

The abstention cases were written per tool file ("nothing to do with THIS tool"),
but the evaluation gives the model all 23 tools, so 14 of them were answerable by
another tool and a model that answered correctly scored zero. A blind re-review
of the 36 disputed cases (round2/A/d1_decisions.json) split them into 16 clear
mislabels (14 here, 2 in the clarification pass), 14 defensible-either-way cases
and 6 the gold already had right.

D10 also fixes the contradiction L6-009 found: a definition request for a term the
glossary holds is a tool case, any other concept explanation is not. The glossary
and FIU questions are rewritten so they ask for what the catalog holds, which is
what makes the tool necessary.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both

# Mislabelled abstention cases: the question asks for something a shared tool answers.
# (kr question, en question, gold, why)
MISLABEL = {
    "st_an_irr_006": (None, None,
        {"primary_tool": "get_statistics", "tools_must_include": ["get_statistics"], "param_checks": {}},
        "get_statistics returns the fraud type distribution the question asks for; 20 of 28 "
        "configurations called a tool and were scored wrong"),
    "st_cp_irr_002": (None, None,
        {"primary_tool": "get_statistics", "tools_must_include": ["get_statistics"], "param_checks": {}},
        "'the overall status instead of a period comparison' is exactly the get_statistics output "
        "(24 of 28 called it); the case's own note said so"),
    "st_cp_irr_007": (
        "2024년 한 해의 이상거래 현황을 월별 추이로 요약해줘",
        "Please summarize the suspicious transactions of the whole of 2024 as a monthly trend.",
        {"primary_tool": "get_trend_analysis", "tools_must_include": ["get_trend_analysis"],
         "param_checks": {"get_trend_analysis": {"unit": "monthly", "date_from": 20240101, "date_to": 20241231}}},
        "get_statistics cannot filter by year, so the year in the question makes this a trend request; "
        "27 of 28 configurations called a tool"),
    "st_ap_irr_006": (None, None,
        {"primary_tool": "get_statistics", "tools_must_include": ["get_statistics"], "param_checks": {}},
        "get_statistics returns fraud_ratio_percent directly (26 of 28 called it)"),
    "st_ap_irr_007": (None, None,
        {"primary_tool": "query_transactions", "tools_must_include": ["query_transactions"],
         "param_checks": {"query_transactions": {"sql_contains": ["sender_acc", "9000000000017070"],
                                                 "sql_valid": True}}},
        "the question asks for a SQL query over one account, which is what query_transactions is for "
        "(24 of 28 called it)"),
    "st_gir_irr_006": (None, None,
        {"primary_tool": "query_transactions", "tools_must_include": ["query_transactions"],
         "param_checks": {"query_transactions": {"sql_contains": ["sender_bank", "is_fraud"], "sql_valid": True}}},
        "ranking institutions by fraud count is a GROUP BY over sender_bank; the case's own note said "
        "query_transactions suits it"),
    "st_gs_irr_004": (None, None,
        {"primary_tool": "analyze_network", "tools_must_include": ["analyze_network"],
         "param_checks": {"analyze_network": {"account_id": 9000000004388203}}},
        "a network analysis of one account is analyze_network (27 of 28 called it); the note said so"),
    "st_pf_irr_007": (
        "계좌 9000000000036484의 거래 통계 프로파일을 조회해줘",
        "Please look up the transaction statistics profile of account 9000000000036484.",
        {"primary_tool": "get_account_profile", "tools_must_include": ["get_account_profile"],
         "param_checks": {"get_account_profile": {"account_id": 9000000000036484}}},
        "the account's history is what get_account_profile returns; the as-is wording split the "
        "configurations between two tools, so the question now names the profile"),
    "st_qt_irr_005": (
        "HOFINET 전체 거래 건수와 이상거래 비율을 요약해줘",
        "Please summarize the total transaction count and the suspicious transaction ratio of HOFINET.",
        {"primary_tool": "get_statistics", "tools_must_include": ["get_statistics"], "param_checks": {}},
        "the case's own note said get_statistics suits it; the wording now differs from st_an_irr_006, "
        "which asks for the distribution by type"),
    "st_qt_irr_007": (None, None,
        {"primary_tool": "analyze_network", "tools_must_include": ["analyze_network"],
         "param_checks": {"analyze_network": {"account_id": 9000000000036484}}},
        "a network analysis of one account is analyze_network (27 of 28 called it); the note said so"),
    "st_sar_irr_007": (None, None,
        {"primary_tool": "get_aml_glossary", "tools_must_include": ["get_aml_glossary"],
         "param_checks": {"get_aml_glossary": {"term": "PEP"}}},
        "PEP is in the glossary and its entry answers the definition and the handling rule, so under "
        "D10 this is a glossary case like its twin st_gl_005"),
    "st_gap_irr_007": (
        "강화된 고객확인(EDD)이 무엇이고 언제 필요한지 용어집에서 확인해줘",
        "Please look up in the glossary what enhanced due diligence (EDD) is and when it is required.",
        {"primary_tool": "get_aml_glossary", "tools_must_include": ["get_aml_glossary"],
         "param_checks": {"get_aml_glossary": {"term": "EDD"}}},
        "the glossary entry for EDD states when it applies; under D10 a listed term is a glossary case, "
        "and the question now names the term instead of CDD"),
    "st_ctr_irr_002": (None, None,
        {"primary_tool": "get_aml_glossary", "tools_must_include": ["get_aml_glossary"],
         "param_checks": {"get_aml_glossary": {"term": "CTR"}}},
        "the glossary entry for CTR carries the 30-day deadline the question asks for"),
    "st_ap_irr_002": (None, None,
        {"primary_tool": "get_aml_glossary", "tools_must_include": ["get_aml_glossary"],
         "param_checks": {"get_aml_glossary": {"term": "STR"}}},
        "the glossary entry for STR states that the threshold was abolished in Aug 2013, which is the "
        "answer to the question"),
}

# Defensible either way: abstaining stays the primary gold, the tool answer is accepted too.
AMBIGUOUS = {
    "st_gap_irr_006": ({"tools_must_include": ["get_statistics"]},
        "the statistic is in scope but 'today' lies outside the data range, so reporting no data and "
        "declining are both defensible"),
    "st_pf_irr_006": ({"tools_must_include": ["get_statistics"]},
        "same out-of-range 'today' as st_gap_irr_006; 25 of 28 called get_statistics"),
    "st_sar_irr_002": ({"tools_must_include": ["get_aml_glossary"],
                        "param_checks": {"get_aml_glossary": {"term": "RBA"}}},
        "the glossary entry gives the definition and names FATF Recommendation 1, a partial answer to "
        "'the international standard'"),
    "st_sar_irr_005": ({"tools_must_include": ["get_aml_glossary"],
                        "param_checks": {"get_aml_glossary": {"term": "CDD"}}},
        "the glossary entry lists three elements of CDD, not the four steps the question asks for"),
    "st_grap_irr_001": ({"tools_must_include": ["get_aml_glossary"],
                         "param_checks": {"get_aml_glossary": {"term": "CDD"}}},
        "the glossary entry gives the definition and the legal source but not the obligations in full"),
    "st_smurf_irr_005": ({"tools_must_include": ["get_aml_glossary"],
                          "param_checks": {"get_aml_glossary": {"term": "Layering"}}},
        "the glossary defines layering but holds no entry for smurfing, so the tool answers half"),
    "st_acr_irr_006": ({"tools_must_include": ["lookup_fiu_reference_types"],
                        "param_checks": {"lookup_fiu_reference_types": {"keyword": "Non-face-to-face"}}},
        "the FIU catalog returns nine non-face-to-face suspicious transaction types, close to but not "
        "the same as the question's 'types of financial fraud'"),
    "st_smurf_irr_004": ({"tools_must_include": ["get_aml_glossary"],
                          "param_checks": {"get_aml_glossary": {"term": "Structuring"}}},
        "the glossary defines structuring but says nothing about how FATF regulates it"),
}

# D10: the glossary and FIU questions ask for what the catalog holds, so the tool is necessary.
CATALOG_QUESTION = {
    "st_gl_001": ("AML 용어집에서 CDD 항목의 정의와 출처를 찾아줘",
                  "Please find the definition and the source of the CDD entry in the AML glossary."),
    "st_gl_002": ("AML 용어집에 등록된 STR의 정의와 출처를 알려줘",
                  "Please give the definition and the source of STR as the AML glossary records it."),
    "st_gl_003": ("AML 용어집에서 CTR 항목을 찾아 보고 기준과 기한을 확인해줘",
                  "Please look up the CTR entry in the AML glossary and check its reporting threshold and deadline."),
    "st_gl_004": ("AML 용어집에 등록된 RBA의 정의와 근거 문서를 조회해줘",
                  "Please look up the definition of RBA in the AML glossary and the document it cites."),
    "st_gl_005": ("AML 용어집에서 PEP 항목의 정의와 출처를 확인해줘",
                  "Please check the definition and the source of the PEP entry in the AML glossary."),
    "st_gl_006": ("AML 용어집의 EDD 항목과 SDD 항목을 비교해서 차이를 설명해줘",
                  "Please compare the EDD entry with the SDD entry in the AML glossary and explain the difference."),
    "st_gl_007": ("AML 용어집에서 FIU 항목의 정의와 출처를 찾아줘",
                  "Please find the definition and the source of the FIU entry in the AML glossary."),
    "st_gl_008": ("AML 용어집에서 구조화(Structuring) 항목의 정의와 출처를 확인해줘",
                  "Please check the definition and the source of the Structuring entry in the AML glossary."),
    "st_fiu_002": ("심야 시간대 대량거래에 해당하는 FIU 의심거래 참고유형을 catalog에서 찾아줘",
                   "Please find the FIU suspicious-transaction reference types for bulk transactions during "
                   "late-night hours."),
    "st_fiu_003": ("은행업 비대면 거래에 해당하는 FIU 의심거래 참고유형 목록을 조회해줘",
                   "Please look up the list of FIU suspicious-transaction reference types for non-face-to-face "
                   "banking transactions."),
    "st_fiu_006": ("휴면 계좌나 장기 미사용 계좌에 해당하는 FIU 의심거래 참고유형을 검색해줘",
                   "Please search the FIU suspicious-transaction reference types for dormant or long-unused accounts."),
    "st_fiu_008": ("법인과 대표자 개인계좌 간 거래에 해당하는 FIU 의심거래 참고유형을 찾아줘",
                   "Please find the FIU suspicious-transaction reference types for transactions between a corporation "
                   "and the personal account of its representative."),
}

GLOSSARY_WHY = ("D10: a request for a term the glossary holds is a tool case, so the question asks for "
                "the entry the catalog stores (definition and source) rather than for a general "
                "explanation a model can give from memory (L6-009)")
FIU_WHY = ("D10: the question names the FIU reference-type catalog, so the answer has to come from "
           "lookup_fiu_reference_types rather than from general knowledge")


def apply(kr: Bench, en: Bench, log: ChangeLog) -> None:
    kr_by, en_by = kr.by_id(), en.by_id()

    for case_id, (kr_text, en_text, gold, why) in MISLABEL.items():
        for bench_by, lang, text in ((kr_by, "kr", kr_text), (en_by, "en", en_text)):
            case = bench_by[case_id]
            if text:
                log.set_field(case, lang, "question", text, "L1-001/D10", why)
            log.set_field(case, lang, "expected", copy.deepcopy(gold), "L1-001/D10", why)

    for case_id, (alternative, why) in AMBIGUOUS.items():
        for bench_by, lang in ((kr_by, "kr"), (en_by, "en")):
            case = bench_by[case_id]
            gold = copy.deepcopy(case["expected"])
            gold["alternatives"] = [copy.deepcopy(alternative)]
            log.set_field(case, lang, "expected", gold, "L1-001/D10", why + "; abstaining stays the "
                          "primary gold and the tool answer is accepted as an alternative")

    for case_id, (kr_text, en_text) in CATALOG_QUESTION.items():
        why = GLOSSARY_WHY if case_id.startswith("st_gl_") else FIU_WHY
        log.set_field(kr_by[case_id], "kr", "question", kr_text, "L6-009/D10", why)
        log.set_field(en_by[case_id], "en", "question", en_text, "L6-009/D10", why)

    # L3-011: the glossary holds "Structuring", never the Korean "구조화".
    for bench_by, lang in ((kr_by, "kr"), (en_by, "en")):
        case = bench_by["st_gl_008"]
        gold = copy.deepcopy(case["expected"])
        gold["param_checks"]["get_aml_glossary"]["term"] = "Structuring"
        log.set_field(case, lang, "expected", gold, "L3-011",
                      "the gold term '구조화' returns \"Term '구조화' not found\": the catalog holds 13 "
                      "English terms and no Korean alias, so the gold now uses Structuring")
        # st_gl_006 compares two entries, so either entry is a correct call.
        case = bench_by["st_gl_006"]
        gold = copy.deepcopy(case["expected"])
        gold["alternatives"] = [{"tools_must_include": ["get_aml_glossary"],
                                 "param_checks": {"get_aml_glossary": {"term": "SDD"}}}]
        log.set_field(case, lang, "expected", gold, "L1-001/D10",
                      "the question compares the EDD and SDD entries, so looking up either one is a "
                      "correct call; the case note said so but the gold could not express it")

    log.note(f"{len(MISLABEL)} mislabelled abstention cases became tool cases (the other 2 of the 16 are "
             f"missing-parameter cases, fixed in the clarification pass)")
    log.note(f"{len(AMBIGUOUS)} defensible-either-way cases keep the abstention gold and accept the tool "
             f"answer as an alternative (the other 6 of the 14 are missing-parameter cases)")
    log.note(f"{len(CATALOG_QUESTION)} glossary and FIU questions now ask for catalog content")


def main() -> int:
    kr, en = both()
    log = ChangeLog("p06_relevance", "D10: what a no-tool request is, the 16 mislabels, the 14 "
                                     "defensible-either-way cases and the glossary catalog (L1-001, "
                                     "L6-009, L3-011).")
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
