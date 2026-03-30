# AML-Bench Multi-Turn Schema

## 개요

STR(의심거래보고서) 작성 워크플로우 기반 멀티턴 벤치마크.
싱글턴 1,258건과 동일한 23개 도구를 사용하며, STR 작성까지의 조사 과정을 다턴 대화로 평가한다.

## sub_category (3종)

| sub_category | 정의 | 턴 수 |
|---|---|---|
| base | 정보가 모두 주어지며 순차적으로 도구를 호출 | 3~5턴 |
| missing_parameter | 필수 정보 누락 → 에이전트가 되물음 → 재시도 | 4~6턴 |
| long_context | 이전 턴 tool_result의 값이 다음 턴 arguments에 연결 | 4~6턴 |

## JSON 스키마

```json
{
  "id": "string — mt_str_{nnn}",
  "scenario": "string — 시나리오 한 줄 설명",
  "sub_category": "base | missing_parameter | long_context",
  "fraud_type": "integer — 이상거래유형 코드 (1~7)",
  "fraud_type_name": "string — 자금세탁 | 대포통장 | 보이스피싱 | ...",
  "turns": [
    {
      "turn": "integer — 1부터 시작",
      "content": "string — 사용자 발화",
      "tool_calls": [
        {
          "name": "string — 도구명",
          "arguments": {
            "key": "value — 기대하는 파라미터 (param_checks 역할)"
          }
        }
      ],
      "tool_result": "object | null — 다음 턴에 전달할 mock 응답",
      "context_ref": {
        "from_turn": "integer — 참조하는 이전 턴 번호",
        "key": "string — tool_result 내 참조 키",
        "to_param": "string — 이번 턴 arguments의 대상 키"
      },
      "expect_clarification": "boolean — true면 도구 호출 없이 되물음이 정답",
      "note": "string — 평가 포인트 설명 (optional)"
    }
  ]
}
```

## 필드 설명

### tool_calls
- 해당 턴에서 모델이 호출해야 하는 도구와 기대 파라미터
- 빈 배열 `[]`: 도구를 호출하지 않는 것이 정답 (missing_parameter 되묻기 턴)
- 복수 도구: 한 턴에서 여러 도구를 호출해야 하는 경우

### tool_result
- 평가 시스템이 모델에게 돌려줄 mock 응답 (HOFINET 기반 현실적 값)
- 다음 턴의 context_ref가 참조하는 원천 데이터
- `null`: 되묻기 턴 등 도구 호출이 없는 경우

### context_ref
- long_context 유형에서만 사용
- 이전 턴 tool_result의 특정 값이 이번 턴 arguments에 정확히 전달되었는지 평가
- 없으면 문맥 참조 평가 대상이 아닌 턴

### expect_clarification
- `true`: 모델이 도구를 호출하지 않고 사용자에게 되물어야 정답
- missing_parameter 유형의 첫 턴에서 사용

## 평가 메트릭

### 턴별 (싱글턴과 동일 공식)
- `h`: tool selection accuracy (tool_calls[].name 일치)
- `a`: parameter accuracy (tool_calls[].arguments 일치)
- `s`: composite score (기존 가중합 공식)

### 시나리오별 (멀티턴 고유)
- `avg_s`: 턴별 s의 평균 — 싱글턴 s와 직접 비교 가능
- `context_accuracy`: context_ref가 있는 턴에서 참조값 정확도
- `scenario_complete`: 모든 턴 s > 0.5이면 완수 (boolean)

## 실행 방식

1. 시스템 프롬프트 + 23개 도구 정의 전송
2. 턴1 user content 전송
3. 모델 응답 수신 → tool_calls 평가
4. 정답 tool_result를 대화 이력에 주입 (scripted evaluation)
5. 턴2 user content 전송 (이전 대화 이력 포함)
6. 반복...
