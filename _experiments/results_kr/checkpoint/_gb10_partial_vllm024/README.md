# GB10 부분 실행 (미완주 · 참고용)

`meta-llama/Llama-3.1-8B-Instruct` 단일턴 KR 실행 중 1,189/1,258 에서 중단된 산출물이다.
정식 결과가 아니며, 스택 간 차이를 비교할 때만 참고한다.

| | |
|---|---|
| 장비 | NVIDIA GB10 (aarch64, 통합메모리 121.7GiB, 다른 사용자와 공유) |
| vLLM | 0.24.0 (aarch64에서 0.20.1 빌드 불가 — python3.12-dev 부재) |
| 중단 사유 | 2026-09-09 13:48 장비 재부팅 |
| 진행 | 1,189 / 1,258 (94.5%) — 규제보고 3종 19건 미실행 |

정식 결과는 상위 디렉터리의 H200 + vLLM 0.20.1 전량 실행분이다.

## 함께 보존한 비교표

파생 집계물(comparison·eval)은 미실행 카테고리가 0.0%로 들어가 오독을 부르므로
저장소에 넣지 않는다. 로컬 `results_kr/_gb10_partial_vllm024/` 에만 있다.

중단된 GB10 실행이 자동 생성한 것으로, **미실행 카테고리가 0.0% 로 집계돼 있다.**
`analyze_cross_institution_flow` · `lookup_fiu_reference_types` · `validate_str_fields` ·
`get_aml_glossary` 등이 그렇다. 어떤 분석에도 사용하지 말 것.

유효한 비교표는 상위 디렉터리의 `comparison_20260909_175424.*` 다.
