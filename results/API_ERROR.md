# API Error 분석 리포트

> 분석일: 2026-03-11 | 대상: vLLM 0.17.0 벤치마크 37개 모델, 1,258 케이스

## 요약

| 유형 | 건수 | 영향 모델 | 심각도 |
|------|------|----------|--------|
| Context Length 초과 | 311건 | 5개 모델 | HIGH |
| Single Tool-Call 제한 | 106건 | 1개 모델 | MEDIUM |
| Tool-Call JSON 파싱 실패 (400 BadRequest) | 35건 | 3개 모델 | LOW |
| Tool-Call JSON 파싱 실패 (400 BadRequest) | 4건 | 1개 모델 | LOW |
| **합계** | **456건** | **10개 모델** | |

- 에러 없는 모델: 27개 (전체의 73%)

---

## 1. Context Length 초과 (311건)

### 원인
`--max-model-len` 설정에서 output 토큰을 예약하면 input 상한이 부족해지는 문제.
일부 케이스에서 프롬프트(시스템 + 도구 정의 23개 + 사용자 질문)가 한도를 초과.

```
Error code: 400 - "You passed N input tokens and requested 4096 output tokens.
However, the model's context length is only M tokens"
```

### 영향 모델

| 모델 | 에러 건수 | max-model-len | 비고 |
|------|----------|---------------|------|
| meta-llama/Llama-3.3-70B-Instruct | 121건 | 16384 | TP=2 |
| Qwen/Qwen3-30B-A3B-Instruct-2507 | 108건 | 16384 | |
| Qwen/Qwen3-30B-A3B-Thinking-2507__think | 84건 | 16384 | |
| Qwen/Qwen3-30B-A3B-Thinking-2507__nothink | 74건 | 16384 | (별도 eval) |
| Qwen/Qwen3-8B | 1건 | 40960 | smurf_043 (input 36,865 토큰) |

※ Qwen3-30B nothink의 74건과 think의 84건은 별도 eval 파일

### 실패 케이스 패턴
116개 고유 케이스 ID가 반복적으로 실패. 주로 도구 정의가 많이 포함되는 카테고리:

- `acif_*` (analyze_cross_institution_flow)
- `acr_*` (analyze_channel_risk)
- `ctr_*` (detect_ctr_candidates)
- `mt_*` (multi_tool)
- `qt_*` (query_transactions)
- `rrt_*` (rank_risky_transactions)
- `mon_*` (detect_monitoring_alerts)

Qwen3-8B의 `smurf_043`은 특이 케이스: max-model-len 40960임에도 input 36,865 토큰으로 초과.

### 해결 방안
1. **`--max-model-len 32768` 이상으로 증가** — 가장 직접적. 단, VRAM 사용량 증가
2. **프롬프트 압축** — 도구 정의(23개)를 축약하거나 관련 도구만 선택적 주입
3. **`--max-tokens` 출력 토큰 축소** — 4096 → 2048로 줄이면 input 여유 확보

---

## 2. Single Tool-Call 제한 (106건)

### 원인
Llama-3.1-8B-Instruct의 tool-call 파서(`llama3_json`)가 병렬 tool-call을 지원하지 않음.
multi_tool 카테고리 등 복수 도구 호출이 필요한 케이스에서 실패.

```
Error: "This model only supports single tool-calls at once!"
```

### 영향 모델

| 모델 | 에러 건수 | 비고 |
|------|----------|------|
| meta-llama/Llama-3.1-8B-Instruct | 106건 | llama3_json 파서 |

### 실패 케이스 패턴
- `mt_*` (multi_tool): 73건 — 전체 multi_tool 케이스의 73%
- 기타 카테고리에서도 모델이 자발적으로 복수 도구를 호출하려는 경우 33건

### 근본 원인 (웹 조사 결과)

vLLM 공식 문서에 명시된 **Llama 3 계열의 구조적 한계**:
> "Parallel tool calls are **not supported for Llama 3**, but it is supported in Llama 4 models."

- `parallel_tool_calls` 파라미터는 OpenAI API 호환용으로만 존재하며, vLLM에서 **무시됨** ([vllm#9451](https://github.com/vllm-project/vllm/issues/9451))
- `llama3_json` 파서 자체는 세미콜론 구분 복수 JSON을 파싱할 수 있으나, Llama 3.1 모델이 그 포맷을 안정적으로 생성하지 못함 ([vllm#11592](https://github.com/vllm-project/vllm/issues/11592))
- `hermes` 파서로 변경하면 파싱은 가능하지만, Llama 3.1의 chat template과 호환되지 않아 전체 tool-call 품질이 저하됨

### 조치 결정: 재실험 없이 논문에 limitation으로 기술

| 방안 | 실현성 | 판정 |
|------|--------|------|
| `--max-model-len` 등 설정 변경 | 불가 | 파서/모델 한계이므로 해당 없음 |
| `hermes` 파서 사용 | 비권장 | chat template 불일치로 다른 케이스 품질 저하 |
| 논문에 limitation으로 기술 | **채택** | Llama 3 계열의 알려진 제약사항 |
| Llama-4-Scout으로 대체 비교 | 보완 | Llama 4는 parallel tool call 지원, TP=2 실험 예약됨 |

**논문 기술 방향**: Llama 3.x 계열은 parallel tool-call 미지원으로 `multi_tool` 카테고리에서 구조적 불이익 발생. Llama 4 (Scout) 결과와 비교하여 세대 간 차이를 논증.

참고 자료:
- [vLLM Tool Calling Docs](https://docs.vllm.ai/en/latest/features/tool_calling/)
- [vllm#11592: parallel tool calls in llama3.1](https://github.com/vllm-project/vllm/issues/11592)
- [vllm#9451: parallel_tool_calls parameter](https://github.com/vllm-project/vllm/issues/9451)
- [vLLM llama_tool_parser.py](https://github.com/vllm-project/vllm/blob/main/vllm/tool_parsers/llama_tool_parser.py)

---

## 3. Tool-Call JSON 파싱 실패 — vLLM 400 BadRequest (39건)

### 원인
모델이 생성한 tool-call JSON이 문법적으로 잘못되어 vLLM의 JSON 파서가 거부.
vLLM이 structured output을 강제하지만, 일부 모델은 유효하지 않은 JSON을 생성.

```
Error code: 400 - {'error': {'message': 'Expecting property name enclosed in
double quotes: line 1 column 19 (char 18)', 'type': 'BadRequestError'}}
```

### 영향 모델

| 모델 | 에러 건수 | 주요 에러 메시지 |
|------|----------|----------------|
| kakaocorp/kanana-1.5-2.1b-instruct-2505 | 16건 | `Expecting property name`, `Expecting ',' delimiter`, `Extra data`, `Expecting value` |
| kakaocorp/kanana-1.5-15.7b-a3b-instruct | 10건 | 동일 유형 |
| kakaocorp/kanana-1.5-8b-instruct-2505 | 9건 | 동일 유형 |
| mistralai/Mistral-Small-3.2-24B-Instruct-2506 | 4건 | `Expecting ',' delimiter`, `Unterminated string` (smurf_* 케이스만) |

### 실패 케이스 패턴
- **Kanana 시리즈**: `gs_*`, `qt_*`, `ap_*`, `mt_*` 등 다양한 카테고리에 분산. 커스텀 파서(`kanana_tool_calls/`) 사용으로 일부 JSON 생성 불안정
- **Mistral-Small**: `smurf_*` 카테고리 4건에 집중. `detect_smurfing_network` 도구의 복잡한 파라미터 구조에서 JSON 생성 실패

### 조치 결정

| 방안 | 판정 |
|------|------|
| Kanana 커스텀 파서 개선 | 가능하나, 모델 자체의 JSON 생성 능력 한계 |
| 재실험 | 동일 결과 예상 (결정론적 실패) |
| 논문에 모델 특성으로 기술 | **채택** — 소형 모델의 structured output 정확도 차이로 설명 |

---

## 4. 모델별 에러 현황 전체

| 모델 | API Error | 에러율 | 유형 |
|------|-----------|--------|------|
| Llama-3.3-70B-Instruct | 121 | 9.6% | context_length |
| Qwen3-30B-A3B-Instruct-2507 | 108 | 8.6% | context_length |
| Llama-3.1-8B-Instruct | 106 | 8.4% | single_tool_call |
| Qwen3-30B-A3B-Thinking-2507__think | 84 | 6.7% | context_length |
| Qwen3-30B-A3B-Thinking-2507__nothink | 74 | 5.9% | context_length |
| Kanana-2.1B | 16 | 1.3% | json_parse (400) |
| Kanana-15.7B | 10 | 0.8% | json_parse (400) |
| Kanana-8B | 9 | 0.7% | json_parse (400) |
| Mistral-Small-24B | 4 | 0.3% | json_parse (400) |
| Qwen3-8B | 1 | 0.1% | context_length |
| 기타 27개 모델 | 0 | 0% | — |

---

## 5. 재실험 권장 모델

| 모델 | 수정 사항 | 우선순위 | 비고 |
|------|----------|---------|------|
| Llama-3.3-70B | `--max-model-len 32768` | HIGH | 121건 해소 가능 |
| Qwen3-30B-Instruct | `--max-model-len 32768` | HIGH | 108건 해소 가능 |
| Qwen3-30B-Thinking | `--max-model-len 32768` | HIGH | 84+74건 해소 가능 |
| Llama-3.1-8B | 재실험 불가 | — | 모델 구조적 한계, limitation 기술 |
| Kanana 시리즈 | 재실험 불가 | — | JSON 생성 능력 한계, 결과 유지 |
| Mistral-Small | 재실험 불가 | — | smurf 4건만, 결과 유지 |
| Qwen3-8B | 재실험 불필요 | — | 1건만 (smurf_043 특이 케이스) |
