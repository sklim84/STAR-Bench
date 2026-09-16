# Domain review of the 143 new single-turn cases (2026-09-16)

The reviewer (the project lead, an AML practitioner) went through all 143 cases on the review page.
Verdicts: 123 "좋음", 20 "고쳐야 함", 0 "빼기". The notes cluster into four asks; treat every ask as applying to
the WHOLE dataset (1,258 cases), not only to the case it was written on.

## A. Terminology must be spelled one way everywhere
- st_ctr_047: "구조화(structuring)와 structuring이 혼합되어 사용되는데, 각 인스턴스를 통일해줘. 깔때기(funnel)를
  funnel로 표현한다면 이것도 structuring이라고만 표기해야 할 것 같아."
- st_ctr_049: "st_ctr_047과 마찬가지로 점검해줘."
- st_mtool_122: "깔때기(funnel)을 그냥 funnel이라고 표기하면 안 되는지 점검해줘."
Decide ONE convention for each pattern term (structuring, funnel, smurfing, layering, ring) in Korean questions,
apply it to every case in both languages and to the tool descriptions/prompt that name the same patterns, and write
the convention down. The English arm keeps the English term.

## B. Re-check every clarification ("no tool call") case
On st_mp_026 ~ st_mp_044 the reviewer repeated: "이게 (no tool call)이 맞는지 다시 점검해줘."
Re-derive for each: is a schema-required argument genuinely unresolved (D19), or could the tool run with defaults?
Cases that fail that test become tool cases or get a genuinely missing argument. Report the outcome per id.
(ok-with-note: st_mp_026, 027, 028, 029; fix: st_mp_030 ~ st_mp_044.)

## C. Wording that reads unnaturally
- st_mp_030: "상위 관련 기관이란 표현이 잘 이해가 안 되"
- st_mp_032: "입출금 양방향 현황이란 표현보다 입출금 자금흐름 현황이란 표현이 더 적절하지 않을까?"
- st_mp_044: "상위 행이 어떤 의미인지 잘 이해가 안 되"
Rewrite these in the phrasing an AML analyst would use, then sweep the dataset for the same stiff constructions
("상위 관련 기관", "양방향 현황", "상위 행", and anything else that reads like a translation of a column name).

## D. Parameter hints in the question
- st_ctr_048: "질문에 (high_value) 표기가 필요한 건지 점검해줘."
Decide whether an enum value belongs in the question text as a parenthesis. Rule of thumb: state the CONDITION in
natural language and let the model map it to the enum; only name the enum when the schema gives no other way to
disambiguate. Apply the rule to every case that puts a raw parameter value in parentheses.
