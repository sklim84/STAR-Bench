# 벤치마크 제외 모델 (2026-03-13)

총 11개 모델을 AML tool-calling 벤치마크(1,258건) 완료 후 논문 실험에서 제외함.
모두 **tool call을 전혀(또는 거의) 생성하지 못함**.

## 1차 제외 (5개) — tool-calling 미지원 모델

모두 동일한 증상: `called_tools = []`, `wrong_func = 1099`, `correct = 159`(irr 134 + missing_params 25).
5개 서로 다른 vLLM 파서(hermes, pythonic, phi4_mini_json)를 사용했으므로 파서 문제가 아닌 **모델 한계**.

| 모델 | 파서 | 점수 | 제외 사유 |
|------|------|------|-----------|
| google/gemma-3-12b-it | pythonic | 0.3248 | tool-calling 자체를 지원하지 않는 모델 |
| google/gemma-3-27b-it | pythonic | 0.3248 | tool-calling 자체를 지원하지 않는 모델 |
| LGAI-EXAONE/EXAONE-Deep-7.8B | hermes | 0.3248 | 추론(reasoning) 특화 모델, tool-calling용이 아님 |
| LGAI-EXAONE/EXAONE-Deep-32B | hermes | 0.3248 | 추론(reasoning) 특화 모델, tool-calling용이 아님 |
| microsoft/Phi-4-mini-reasoning | phi4_mini_json | 0.3248 | 추론 특화 변형, Phi-4-mini-instruct와 동일 결과 |

## 2차 제외 (5개) — 공식 지원이나 실질적 tool call 미생성

1차에서 "재확인 필요"로 보류했던 모델들. 각 모델의 공식/권장 파서를 사용했으나
tool call을 거의 생성하지 못함 (최대 2/1,258건). 파서 호환 문제가 아닌 **모델 한계** 확인.

| 모델 | 파서 | 점수 | tool calls | 제외 사유 |
|------|------|------|-----------|-----------|
| LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct | hermes | 0.3248 | 0/1258 | 공식 지원이나 tool call 전혀 미생성 |
| LGAI-EXAONE/EXAONE-3.5-32B-Instruct | hermes | 0.3248 | 0/1258 | 공식 지원이나 tool call 전혀 미생성 |
| ibm-granite/granite-3.1-8b-instruct | granite | 0.3258 | 2/1258 | 1,258건 중 2건만 tool call 생성 (0.16%) |
| microsoft/Phi-4-mini-instruct | phi4_mini_json | 0.3253 | 1/1258 | 1,258건 중 1건만 tool call 생성 (0.08%) |
| internlm/internlm3-8b-instruct | internlm | 0.3211 | 0/1258 | 공식 지원이나 tool call 전혀 미생성 |

## 3차 제외 (1개) — 벤치마크 후 확인

| 모델 | 파서 | 점수 | tool calls | 제외 사유 |
|------|------|------|-----------|-----------|
| microsoft/Phi-4 (14B) | hermes | 0.3248 | 0/1258 | tool call 전혀 미생성, 2차 제외 모델과 동일 패턴 |

## 삭제된 파일

- eval, checkpoint, vLLM/bench 로그 파일 (11개 모델 모두)
- HF 모델 캐시 (~174GB: 1차 157GB + 2차 17GB)
- benchmark.py 레지스트리에서 주석 처리
- visualize_results.py short_name 매핑 제거
