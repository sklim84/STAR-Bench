# _invalid_pre_2026-05-08 — Invalidated T/NT 결과 archive

## 사유 (2026-05-08 결정)
아래 모델들의 T/NT eval 결과는 ablation으로 무효 처리됩니다. 정정된 메커니즘으로 재실험한 결과는 같은 디렉토리의 다른 위치에 저장됩니다.

### 무효 모델 + 사유

| 모델 | 무효 사유 | 정정 메커니즘 |
|------|----------|-------------|
| `openai/gpt-oss-20b` (T+NT) | `chat_template_kwargs.enable_thinking`은 gpt-oss에 silent no-op. vLLM이 Harmony 포맷을 내부 처리하므로 chat template kwargs 무시. T/NT 양쪽 모두 default `medium` reasoning effort로 실행됨 | `reasoning_effort: "high"` (T) / `"low"` (NT) — top-level API 파라미터 |
| `openai/gpt-oss-120b` (T+NT) | 동일 | 동일 |
| `kakaocorp/kanana-2-30b-a3b-thinking-2601` (T+NT) | always-thinking 모델로 `enable_thinking=False` 미지원. T/NT 양쪽 모두 thinking 모드로 실행됨 | sibling-variant 비교: `kanana-2-30b-a3b-instruct-2601` (NT) ↔ `kanana-2-30b-a3b-thinking-2601` (T) |

### 검증 근거
T와 NT runs 사이 error_type 분포가 거의 완전 일치 (예: gpt-oss-120b: T={correct:243, wrong_func:194} ≈ NT={correct:239, wrong_func:188}; kanana-thinking: T={correct:183} ≈ NT={correct:182}).

### 참조 문서
- gpt-oss reasoning 제어: https://huggingface.co/openai/gpt-oss-20b/discussions/86, https://huggingface.co/openai/gpt-oss-20b/discussions/47
- kanana-2 모델 카드: https://huggingface.co/kakaocorp/kanana-2-30b-a3b-thinking-2601
- vLLM Qwen3.5 Recipe: https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html

## 보존 이유
재현성/감사 추적을 위해 삭제하지 않고 archive. 미래의 reviewer/저자가 "왜 이 결과가 invalidated되었는가"를 명확히 추적할 수 있도록 함.
