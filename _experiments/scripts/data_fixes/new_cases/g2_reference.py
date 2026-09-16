"""Group 2 - the two catalog tools: `get_aml_glossary` (8 -> 25) and
`lookup_fiu_reference_types` (8 -> 25).

D10: these questions ask for what the catalog holds, not for a concept explanation.
Every glossary term is one of the 13 entries `aml_reference._AML_GLOSSARY` defines and
every FIU keyword selects at least one catalog row (checked against `grounding.json`,
which records the row counts). The keyword cases that name an industry need the catalog
rather than model knowledge, because the catalog is an excerpt: which rows it holds for
"balance certificate" in securities is not something a model can recall.

Half of the glossary questions write the term out and half name the concept the term
abbreviates, so the model has to resolve it; the D23 rule turns that into the easy /
medium split.
"""

from __future__ import annotations

# term, Korean question, English question, alternative term (a comparison case), rationale
GLOSSARY = [
    ("MLRO", "MLRO가 AML 용어집에 어떻게 정의돼 있고 근거 문서는 무엇인지 확인해줘",
     "Please check how the AML glossary defines MLRO and which document it cites.",
     None, "catalog entry the glossary holds; the term is written out"),
    ("FATF", "FATF는 AML 용어집에 어떤 설명으로 등록돼 있어? 출처도 같이 알려줘",
     "How does the AML glossary describe FATF? Please give its source as well.",
     None, "catalog entry the glossary holds; the term is written out"),
    ("KYE", "AML 용어집에서 KYE 항목의 정의와 근거 문서를 찾아줘",
     "Please find the definition of the KYE entry in the AML glossary and the document it cites.",
     None, "catalog entry the glossary holds; the term is written out"),
    ("Layering", "AML 용어집에서 Layering 항목의 정의와 출처를 조회해줘",
     "Please look up the definition and the source of the Layering entry in the AML glossary.",
     None, "catalog entry the glossary holds; the term is written out"),
    ("SDD", "AML 용어집에 등록된 SDD 항목의 정의와 출처를 확인해줘",
     "Please check the definition and the source of the SDD entry as the AML glossary records it.",
     None, "catalog entry the glossary holds; the term is written out"),
    ("EDD", "AML 용어집의 EDD 항목이 어떤 문서를 근거로 삼고 있는지 확인해줘",
     "Please check which document the EDD entry of the AML glossary cites as its source.",
     None, "asks for the source field of one catalog entry"),
    ("STR", "AML 용어집의 STR 항목과 CTR 항목을 비교해서 보고 대상과 기한 차이를 설명해줘",
     "Please compare the STR entry with the CTR entry in the AML glossary and explain how the "
     "reporting subject and the deadline differ.",
     "CTR", "comparison of two entries the glossary holds; either lookup is the first step (D10)"),
    ("Structuring", "AML 용어집에 등록된 Structuring 항목과 Layering 항목의 정의를 비교해줘",
     "Please compare the definitions of the Structuring entry and the Layering entry in the "
     "AML glossary.",
     "Layering", "comparison of two entries the glossary holds"),
    ("CDD", "AML 용어집의 CDD 항목과 EDD 항목을 비교해서 적용 대상이 어떻게 다른지 알려줘",
     "Please compare the CDD entry with the EDD entry in the AML glossary and tell me how the "
     "customers they apply to differ.",
     "EDD", "comparison of two entries the glossary holds"),
    ("CDD", "고객확인제도를 가리키는 약어 항목을 AML 용어집에서 찾아 정의와 출처를 알려줘",
     "Please find the entry for the abbreviation that stands for customer due diligence in the "
     "AML glossary and give its definition and source.",
     None, "the term has to be resolved from the concept before the catalog can be queried"),
    ("MLRO", "자금세탁방지 업무를 총괄하는 보고책임자를 가리키는 약어 항목의 정의와 출처를 "
             "AML 용어집에서 확인해줘",
     "Please check, in the AML glossary, the definition and the source of the entry for the "
     "abbreviation that names the officer in charge of anti-money-laundering work.",
     None, "the term has to be resolved from the concept before the catalog can be queried"),
    ("FATF", "국제자금세탁방지기구를 가리키는 약어 항목의 정의와 출처를 AML 용어집에서 찾아줘",
     "Please find, in the AML glossary, the definition and the source of the entry for the "
     "abbreviation that names the international anti-money-laundering standard setter.",
     None, "the term has to be resolved from the concept before the catalog can be queried"),
    ("KYE", "임직원의 적격성과 신뢰성을 확인하는 절차를 가리키는 약어 항목을 AML 용어집에서 조회해줘",
     "Please look up, in the AML glossary, the entry for the abbreviation that names the "
     "procedure for checking the suitability and trustworthiness of employees.",
     None, "the term has to be resolved from the concept before the catalog can be queried"),
    ("SDD", "저위험 고객에게 적용하는 간소화된 고객확인을 가리키는 약어 항목의 정의를 "
            "AML 용어집에서 확인해줘",
     "Please check, in the AML glossary, the definition of the entry for the abbreviation that "
     "names the simplified due diligence applied to low-risk customers.",
     None, "the term has to be resolved from the concept before the catalog can be queried"),
    ("PEP", "정치적 주요인물을 가리키는 약어 항목의 정의와 출처를 AML 용어집에서 알려줘",
     "Please give, from the AML glossary, the definition and the source of the entry for the "
     "abbreviation that names politically exposed persons.",
     None, "the term has to be resolved from the concept before the catalog can be queried"),
    ("CTR", "고액현금거래보고를 가리키는 약어 항목이 정한 보고 기한을 AML 용어집에서 확인해줘",
     "Please check, in the AML glossary, the reporting deadline recorded in the entry for the "
     "abbreviation that names the currency transaction report.",
     None, "the term has to be resolved from the concept before the catalog can be queried"),
    ("Layering", "자금세탁 2단계에 해당하는 용어 항목의 정의와 출처를 AML 용어집에서 찾아줘",
     "Please find, in the AML glossary, the definition and the source of the entry for the term "
     "that names the second stage of money laundering.",
     None, "the term has to be resolved from the concept before the catalog can be queried"),
]

# keyword, industry, Korean question, English question, rationale
FIU = [
    ("ATM", None, "ATM을 이용한 입금이나 출금과 관련된 FIU 의심거래 참고유형을 검색해줘",
     "Please search the FIU suspicious-transaction reference types for deposits or withdrawals "
     "made through an ATM.",
     "two catalog rows mention ATMs; the keyword is the English word the question already uses"),
    ("gambling", None, "불법 도박 사이트와 연계된 것으로 의심되는 거래의 FIU 참고유형을 조회해줘",
     "Please look up the FIU reference type for transactions suspected of involving illegal "
     "gambling sites.",
     "selects the one banking non-face-to-face row about gambling sites"),
    ("balance certificate", None,
     "잔액증명서 발급을 목적으로 한 입출금에 해당하는 FIU 의심거래 참고유형을 업권 구분 없이 찾아줘",
     "Please find, across both industries, the FIU suspicious-transaction reference types for "
     "deposits and withdrawals made to obtain a balance certificate.",
     "the catalog holds one banking and one securities row; the question asks for both"),
    ("balance certificate", "securities",
     "증권업에서 실제 거래 의사 없이 잔액증명서 발급만을 위한 입출금에 해당하는 FIU 참고유형을 조회해줘",
     "Please look up the FIU reference type in the securities industry for deposits and "
     "withdrawals made solely to obtain a balance certificate with no real transaction intent.",
     "needs the catalog excerpt: which of the two balance-certificate rows is the securities one"),
    ("shell corporation", None,
     "페이퍼컴퍼니 계좌를 이용한 거래에 해당하는 FIU 의심거래 참고유형을 검색해줘",
     "Please search the FIU suspicious-transaction reference types for transactions that use "
     "shell corporation accounts.",
     "selects the one corporate-related row about shell corporations"),
    ("prepaid card", None,
     "선불카드나 상품권 잔액 환불 거래에 해당하는 FIU 참고유형을 찾아줘",
     "Please find the FIU reference type for prepaid card or gift certificate balance refund "
     "transactions.",
     "selects the one banking deposits-misc row about prepaid cards"),
    ("minors", None,
     "미성년자나 고령자 등 타인 명의 계좌를 이용한 거래의 FIU 의심거래 참고유형을 조회해줘",
     "Please look up the FIU suspicious-transaction reference type for transactions that use "
     "accounts in the name of another person such as a minor or an elderly customer.",
     "the row names minors explicitly; the keyword picks it out of the two others'-names rows"),
    ("tax evasion", None,
     "탈세 혐의가 의심되는 입금 거래에 해당하는 FIU 참고유형을 검색해줘",
     "Please search the FIU reference types for deposits suspected of tax evasion.",
     "selects the one banking deposits-cash row about tax evasion"),
    ("internet banking", "banking",
     "인터넷뱅킹을 통해 이뤄진 의심거래에 해당하는 FIU 참고유형을 은행업 기준으로 찾아줘",
     "Please find the FIU reference types for suspicious transactions carried out through "
     "internet banking, restricted to the banking industry.",
     "needs the catalog: two banking rows mention internet banking, in different categories"),
    ("unknown counterparties", None,
     "출처를 알 수 없는 상대방에게서 받은 자금과 관련된 FIU 의심거래 참고유형을 조회해줘",
     "Please look up the FIU suspicious-transaction reference types for funds received from "
     "unknown counterparties.",
     "selects the two non-face-to-face rows about funds from unknown counterparties"),
    ("Kimchi Premium", None,
     "국가 간 가격 차이를 이용한 자금세탁 의심거래 FIU 참고유형을 찾아줘",
     "Please find the FIU suspicious-transaction reference type for money laundering that uses "
     "price differences between countries.",
     "the catalog names this pattern explicitly in the virtual asset category"),
    ("borrowed names", "securities",
     "차명계좌를 이용하거나 타인 계좌로 이체하는 증권업 의심거래 FIU 참고유형을 조회해줘",
     "Please look up the FIU reference type in the securities industry for transactions that use "
     "borrowed-name accounts or transfer to another person's account.",
     "needs the catalog: this wording is a securities in/out row, not the banking disguise row"),
    ("liquidation", "securities",
     "특정 종목을 집중 매매한 뒤 전량 매도하는 증권업 의심거래 FIU 참고유형을 찾아줘",
     "Please find the FIU reference type in the securities industry for concentrated trading of "
     "a specific stock followed by full liquidation.",
     "needs the catalog: the securities trading category holds exactly this row"),
    ("multiple accounts", "securities",
     "단기간에 비대면으로 다수 계좌를 개설하는 증권업 의심거래 FIU 참고유형을 조회해줘",
     "Please look up the FIU reference type in the securities industry for opening multiple "
     "accounts non-face-to-face within a short period.",
     "needs the catalog: the banking catalog has a similar row in a different category"),
    ("refusal", None,
     "고객 정보 제공을 거부하거나 제공한 정보가 일치하지 않는 경우의 FIU 참고유형을 찾아줘",
     "Please find the FIU reference type for refusing to provide customer information or for "
     "information that does not match.",
     "selects the one banking deposits-misc row about refusal and inconsistency"),
    ("representative", "banking",
     "법인 계좌와 대표자 개인 계좌 사이 거래를 은행업 FIU 참고유형에서 조회해줘",
     "Please look up, in the banking FIU reference types, transactions between a corporate "
     "account and the personal account of its representative.",
     "needs the catalog: two corporate-related rows mention the representative"),
    ("cash", "banking",
     "현금 입출금과 관련된 은행업 FIU 의심거래 참고유형 목록을 뽑아줘",
     "Please list the banking FIU suspicious-transaction reference types that involve cash "
     "deposits or withdrawals.",
     "needs the catalog: cash appears in six banking rows across three categories"),
]


def build(grounding: dict) -> list[dict]:
    terms = set(grounding["glossary_terms"])
    counts = grounding["fiu_keywords"]
    cases = []
    for index, (term, question, question_en, other, rationale) in enumerate(GLOSSARY, start=9):
        if term not in terms or (other and other not in terms):
            raise ValueError(f"glossary term not in the catalog: {term} / {other}")
        expected = {
            "primary_tool": "get_aml_glossary",
            "tools_must_include": ["get_aml_glossary"],
            "param_checks": {"get_aml_glossary": {"term": term}},
        }
        if other:
            expected["alternatives"] = [{
                "tools_must_include": ["get_aml_glossary"],
                "param_checks": {"get_aml_glossary": {"term": other}},
            }]
        cases.append({"id": f"st_gl_{index:03d}", "file": "cases_get_aml_glossary.json",
                      "question": question, "question_en": question_en,
                      "expected": expected, "rationale": rationale})

    for index, (keyword, industry, question, question_en, rationale) in enumerate(FIU, start=9):
        row = counts.get(keyword)
        if row is None or not row["all"]:
            raise ValueError(f"FIU keyword selects no catalog row: {keyword}")
        if industry and not row[industry]:
            raise ValueError(f"FIU keyword selects no {industry} row: {keyword}")
        checks = {"keyword": keyword}
        if industry:
            checks["industry"] = industry
        cases.append({"id": f"st_fiu_{index:03d}", "file": "cases_lookup_fiu_reference_types.json",
                      "question": question, "question_en": question_en,
                      "expected": {"primary_tool": "lookup_fiu_reference_types",
                                   "tools_must_include": ["lookup_fiu_reference_types"],
                                   "param_checks": {"lookup_fiu_reference_types": checks}},
                      "rationale": rationale})
    return cases
