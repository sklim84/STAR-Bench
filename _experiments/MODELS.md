# AML-Bench Evaluation Models

NeurIPS 2026 E&D 제출 기준 평가 대상 모델 + RQ별 매핑.
모든 HuggingFace 경로는 검증 완료 (2026-04-29).

## 1. 선정 원칙

| 카테고리 | 선정 기준 | 모델 수 |
|---|---|---|
| A. 일반 유명 모델 | 계열당 1 small + 1 large 원칙 (Qwen, Llama, Gemma, Mistral, Phi, gpt-oss, 도구특화) | 16 |
| B. 한국어 특화 | LG, SKT, KaKao 대표 (small+large 페어) | 6 |
| C. 금융 특화 | Llama-3 기반 최신 모델만 (옛 Llama-1/2 기반은 제외) | 2 |
| 합계 | | 24 (+ 5 thinking 변형 = 29 runs/mode) |

> **금융 특화 모델 선정**: 옛 FinGPT-v3 (Llama-2), FinMA-7B (Llama-1)는 base 모델이 outdated되어 제외. 2025 출시 Llama-3 기반 모델 (Salesforce/Llama-Fin-8b, TheFinAI/Fino1-8B)로 대체하여 Llama-3.x 동시대 모델과 fair comparison 가능. BloombergGPT 등은 비공개로 제외.

---

## 2. 모델 일람표

### A. 일반 유명 모델 (16개)

#### A1. Qwen 계열 (Alibaba) — 4개

| # | 모델 | HF 경로 | 크기 | 아키텍처 | tool-call-parser | think 변형 | 서버 | RQ |
|---|---|---|---|---|---|---|---|---|
| 1 | Qwen3.5-4B | `Qwen/Qwen3.5-4B` | 4B | Dense | qwen3_coder + reasoning_qwen3 | think+nothink | S1 | RQ1, RQ3, RQ2 |
| 2 | Qwen3.5-27B | `Qwen/Qwen3.5-27B` | 27B | Dense | qwen3_coder + enforce-eager | think+nothink | S2 | RQ1, RQ3, RQ2, RQ4 |
| 3 | Qwen3.6-27B | `Qwen/Qwen3.6-27B` | 27B | Dense | qwen3_xml ✅ | thinking-preservation | S2 | RQ1, RQ2, 세대비교 |
| 4 | Qwen3.6-35B-A3B | `Qwen/Qwen3.6-35B-A3B` | 35B | MoE (active 3B) | qwen3_xml + `--max-model-len 32768` ✅ | (확인 필요) | S2 | RQ1, RQ2, MoE 분석 |

#### A2. Llama 계열 (Meta) — 2개

| # | 모델 | HF 경로 | 크기 | tool-call-parser | think | 서버 | RQ |
|---|---|---|---|---|---|---|---|
| 5 | Llama-3.2-3B-Instruct | `meta-llama/Llama-3.2-3B-Instruct` | 3B Dense | llama3_json | n/a | S1 | RQ1, RQ2, RQ4 |
| 6 | Llama-3.3-70B-Instruct | `meta-llama/Llama-3.3-70B-Instruct` | 70B Dense | llama3_json (TP=2) | n/a | S2 | RQ1, RQ2, RQ4 |

#### A3. Gemma 계열 (Google) — 2개

| # | 모델 | HF 경로 | 크기 | tool-call-parser | think | 서버 | RQ |
|---|---|---|---|---|---|---|---|
| 7 | Gemma-4-E4B-it | `google/gemma-4-E4B-it` | eff 4B | **gemma4** | reasoning mode 내장 | S1 | RQ1, RQ2 |
| 8 | Gemma-4-31B-it | `google/gemma-4-31B-it` | 31B Dense | **gemma4** | reasoning mode 내장 | S2 | RQ1, RQ2 |

> **Gemma-4 호환성**: 공식 multimodal (`google/gemma-4-E4B-it`)는 vLLM 0.19.0 + transformers 5.7.0 + 전용 `gemma4` parser 조합으로 정상 동작 (smoke 검증: E4B 4/5, 31B 5/5). vLLM 0.17.0에서는 `Gemma4ClippableLinear input_max` 누락으로 적재 실패. hermes parser 사용 시 chat template 형식 (`<|tool_call>call:func{...}<tool_call|>`) 불일치로 called_tools 미생성. text-only 변형 (`principled-intelligence/...`)은 weight loading 버그가 별도로 존재해 사용 권장하지 않음.

#### A4. Mistral 계열 — 2개

| # | 모델 | HF 경로 | 크기 | tool-call-parser | think | 서버 | RQ |
|---|---|---|---|---|---|---|---|
| 9 | Ministral-3-3B-Instruct-2512 | `mistralai/Ministral-3-3B-Instruct-2512` | 3B Dense | mistral | n/a | S1 | RQ1, RQ2 |
| 10 | Mistral-Small-3.2-24B-Instruct-2506 | `mistralai/Mistral-Small-3.2-24B-Instruct-2506` | 24B Dense | mistral | n/a | S2 | RQ1, RQ2 |

#### A5. Phi 계열 (Microsoft) — 1개

| # | 모델 | HF 경로 | 크기 | tool-call-parser | think | 서버 | RQ |
|---|---|---|---|---|---|---|---|
| 11 | Phi-4-mini-instruct | `microsoft/Phi-4-mini-instruct` | 3.8B Dense | (검증 중: phi4_mini_json 0/5 → pythonic/hermes/llama3_json 시도) | n/a | S1 | RQ1 |

> phi-4 (14B)는 native function calling 미지원으로 제외 (스모크 결과 5/5 wrong_func, called_tools=[]). Phi-4-mini-instruct는 post-training으로 FC 학습 (Microsoft 공식 명시). 단 "function name hallucination" 한계 존재 (Microsoft 명시).

#### A6. OpenAI Open — 2개

| # | 모델 | HF 경로 | 크기 | tool-call-parser | think | 서버 | RQ |
|---|---|---|---|---|---|---|---|
| 12 | gpt-oss-20b | `openai/gpt-oss-20b` | 21B (active 3.6B MoE) | openai + reasoning_openai_gptoss | think+nothink | S2 | RQ1, RQ3 |
| 13 | gpt-oss-120b | `openai/gpt-oss-120b` | ~120B MoE | openai + reasoning_openai_gptoss (TP=4) | think+nothink | S2 | RQ1, RQ3 |

#### A7. 도구 호출 특화 — 3개

| # | 모델 | HF 경로 | 크기 | tool-call-parser | think | 서버 | RQ |
|---|---|---|---|---|---|---|---|
| 14 | xLAM-2-3b-fc-r | `Salesforce/xLAM-2-3b-fc-r` | 3B | xlam | n/a | S1 | RQ1, RQ5 |
| 15 | Llama-xLAM-2-70b-fc-r | `Salesforce/Llama-xLAM-2-70b-fc-r` | 70B (Llama3 base) | xlam (TP=2) | n/a | S2 | RQ1, RQ5 |
| 16 | Hermes-3-Llama-3.1-8B | `NousResearch/Hermes-3-Llama-3.1-8B` | 8B | hermes | n/a | S1 | RQ1, RQ5 |

---

### B. 한국어 특화 모델 (6개)

| # | 모델 | HF 경로 | 기관 | 크기 | tool-call-parser | think | 서버 | RQ |
|---|---|---|---|---|---|---|---|---|
| 17 | EXAONE-4.0-1.2B | `LGAI-EXAONE/EXAONE-4.0-1.2B` | LG | 1.2B Dense | hermes + trust-remote-code | n/a | S1 | RQ1, RQ2 |
| 18 | EXAONE-4.0-32B | `LGAI-EXAONE/EXAONE-4.0-32B` | LG | 32B Dense | hermes + trust-remote-code | n/a | S2 | RQ1, RQ2 |
| 19 | A.X-4.0-Light | `skt/A.X-4.0-Light` | SKT | 7B Dense | hermes | n/a | S1 | RQ1, RQ2 |
| 20 | A.X-4.0 | `skt/A.X-4.0` | SKT | 72B Dense | hermes (TP=2) | n/a | S2 | RQ1, RQ2, RQ4 |
| 21 | kanana-2-30b-a3b-instruct | `kakaocorp/kanana-2-30b-a3b-instruct` | KaKao | 30B MoE | hermes + 커스텀 plugin | nothink only | S2 | RQ1, RQ2 |
| 22 | kanana-2-30b-a3b-thinking-2601 | `kakaocorp/kanana-2-30b-a3b-thinking-2601` | KaKao | 30B MoE | hermes + reasoning_deepseek_r1 | think+nothink | S2 | RQ1, RQ3 |

---

### C. 금융 특화 모델 (2개) — Llama-3 기반 modern variants

| # | 모델 | HF 경로 | 크기 | base | tool-call-parser | think | 서버 | 비고 | RQ |
|---|---|---|---|---|---|---|---|---|---|
| 23 | Llama-Fin-8b (Salesforce) | `Salesforce/Llama-Fin-8b` | 8B | Llama-3-8B-Instruct | llama3_json (검증 필요) | n/a | S1 | Salesforce는 xLAM (FC SOTA) 개발사 → FC 가능성 高 | RQ1, **RQ6 (Finance vs General)** |
| 24 | Fino1-8B (TheFinAI) | `TheFinAI/Fino1-8B` | 8B | Llama-3.1-8B-Instruct | llama3_json (검증 필요) | n/a | S1 | financial reasoning 특화 (SFT + RL on FinQA) | RQ1, **RQ6** |

---

## 3. RQ별 모델 Subset 매핑 요약

| RQ | 대상 모델 수 | 선정 기준 |
|---|---|---|
| RQ1 (Model landscape) | 24 baseline | 전체 (nothink 변형만, 모델 간 공정 비교) |
| RQ2 (Language alignment, 4-way 2x2) | 6 대표 | 계열별 large + 한국어 특화 large (4축 cover, paired test n=6 power 확보) |
| RQ3 (Thinking mode) | 5 핵심 (think+nothink 페어) | think/nothink 변형 있는 모델만 (RQ3 ablation 전용) |
| RQ4 (Single-turn vs Multi-turn) | 24 baseline | 전체 (50 시나리오만 평가) |
| RQ5 (BFCL correlation) | 10~12 overlap | BFCL v4 직접 실행 가능한 모델만 |
| RQ6 (Domain specialization) | 10 비교군 | 한국어 특화 vs 일반 + 금융 특화 (Llama-3 기반) vs 일반 |

> **실제 실험 runs/mode = 24 baseline + 5 think 변형 = 29** (think 변형은 RQ3 ablation 위해 추가 실행되며, RQ1/RQ4는 baseline 1개만 사용해 모델 간 공정 비교 보장).

### RQ2 (Language Alignment) 6 대표

대표 6개로 4-way 2x2 ablation (KR-KR / EN-KR / KR-EN / EN-EN). 4축 모두 cover하며 paired test n=6은 large effect (d≈0.8) 검출 power 0.7+ 확보.

| # | 모델 | 카테고리 | 선정 이유 |
|---|---|---|---|
| 1 | Qwen3.5-27B | multilingual large 1 | KR baseline 1위 (이전 실험) |
| 2 | Qwen3.6-27B | multilingual large 2 | 최신 세대 (2026-04-22), 세대 비교 가능 |
| 3 | Llama-3.3-70B-Instruct | 영문 native large | 영문 우세 가설 검증 |
| 4 | Gemma-4-31B-it | multilingual large (Google) | 140+ 언어 강조, multilingual 별도 축 |
| 5 | EXAONE-4.0-32B | 한국어 특화 large (LG) | KR 우세 가설 핵심 |
| 6 | A.X-4.0 | 한국어 특화 large (SKT) | KR 우세 재현성 (LG와 별도 학습) |

→ **추가 실행: 6 모델 × 2 조건 (KR-EN, EN-EN) = 12 runs / mode** (KR-KR, EN-KR는 master에 자동 포함).

### RQ3 (Thinking Mode) 5 핵심 + 2 참고

| 핵심 (think+nothink 비교) | 비고 |
|---|---|
| Qwen3.5-4B | small Dense thinking |
| Qwen3.5-27B | large Dense thinking |
| gpt-oss-20b | OpenAI reasoning trace small |
| gpt-oss-120b | OpenAI reasoning trace large |
| kanana-2-30b-a3b-thinking-2601 | 한국어 thinking 유일 사례 |
| 참고 (자체 reasoning 또는 옵션) | |
| (Phi-4-mini-instruct) | small instruct, RQ3 thinking ablation 불가 (참고만) |
| Qwen3.6-27B | thinking-preservation 옵션 (검증 필요) |

### RQ5 (BFCL Correlation) 10~12 overlap

| 모델 | BFCL v4 실행 상태 |
|---|---|
| Qwen3.5-4B / Qwen3.5-27B | 직접 실행 결과 보유 |
| Llama-xLAM-2-70b-fc-r | 직접 실행 결과 보유 |
| xLAM-2-3b-fc-r | 직접 실행 결과 보유 |
| Hermes-3-Llama-3.1-8B | 직접 실행 결과 보유 |
| Qwen3.6-27B / Qwen3.6-35B-A3B | NEW, 신규 실행 필요 |
| Gemma-4-31B-it | NEW, 신규 실행 필요 |
| Phi-4-mini-instruct | NEW, 신규 실행 필요 |
| gpt-oss-120b | NEW, 신규 실행 필요 |

결과 위치: `_paper/_experiments/bfcl_results/score/<model>/`

### RQ6 (Domain Specialization) 비교군

| 비교 축 | 한국어 특화 | 일반 (large counterpart) |
|---|---|---|
| Korean | EXAONE-4.0-32B, A.X-4.0, kanana-2-30b-a3b-instruct | Llama-3.3-70B-Instruct, Qwen3.5-27B, Mistral-Small-3.2-24B |

| 비교 축 | 금융 특화 | 일반 (medium counterpart) |
|---|---|---|
| Finance | Salesforce/Llama-Fin-8b, TheFinAI/Fino1-8B (모두 Llama-3 기반 8B) | Llama-3.2-3B-Instruct, Hermes-3-Llama-3.1-8B, Ministral-3-3B |

→ 도메인 특화 효과: implicit (한국어, 학습 데이터 기반) vs explicit (금융, 도메인 fine-tuning) 비교.

---

## 4. NEW 모델 등록 작업 (8개)

| 모델 | HF 경로 | tool-call-parser | 우선순위 | 예상 risk |
|---|---|---|---|---|
| Gemma-4-E4B-it (text-only) | `principled-intelligence/gemma-4-E4B-it-text-only` | hermes | 高 | 공식 multimodal 변형은 vLLM 비호환 (audio_tower) → text-only 변형 사용 |
| Gemma-4-31B-it | `google/gemma-4-31B-it` | hermes | 高 | smoke 검증 중 (multimodal 여부 미확정) |
| Qwen3.6-27B | `Qwen/Qwen3.6-27B` | qwen3_xml | 高 | parser 검증 (2026-04-22 출시) |
| Qwen3.6-35B-A3B | `Qwen/Qwen3.6-35B-A3B` | qwen3_xml | 高 | 동일 |
| Phi-4-mini-instruct | `microsoft/Phi-4-mini-instruct` | hermes | 中 | post-training FC 학습 (Microsoft 공식). phi-4 (14B)는 FC 미지원으로 제외 |
| gpt-oss-120b | `openai/gpt-oss-120b` | openai + reasoning_openai_gptoss | 中 | TP=2 필요, 메모리 검증 |
| Salesforce/Llama-Fin-8b | `Salesforce/Llama-Fin-8b` | llama3_json | 中 | Llama-3 기반, FC 가능성 高 (Salesforce는 xLAM 개발사) |
| TheFinAI/Fino1-8B | `TheFinAI/Fino1-8B` | llama3_json | 中 | Llama-3.1 기반, financial reasoning SFT+RL |

검증 절차: 본격 실험 전 5분 스모크 테스트 (`BENCH_MAX_TOTAL=5`).

---

## 5. 이전 44개 → 26개 변경 요약

### 제외된 모델 (18개)

| 제외 | 사유 |
|---|---|
| Qwen2.5-1.5B-Instruct | Qwen3.5-4B로 small 대체 |
| Qwen3.5-0.8B / 2B / 9B | Qwen3.5-4B/27B로 small/large 대표 |
| Qwen3-4B-Instruct-2507 | Qwen3.5-4B와 사이즈/세대 중복 |
| Qwen3-4B-Thinking-2507 | Qwen3.5-4B의 think 변형으로 대체 |
| Qwen3-8B | Qwen3.5-4B로 Qwen 시리즈 small 대표 |
| Qwen3-Coder-30B | 코드 특화, off-domain |
| Qwen3-30B-A3B-Instruct-2507 | Qwen3.6-35B-A3B (MoE, 최신)로 대체 |
| Qwen3-30B-A3B-Thinking-2507 | Qwen3.5-27B의 thinking 변형으로 충분 |
| xLAM-1B / xLAM-8B / xLAM-32B | xLAM-3B + xLAM-70B 대표 |
| Llama-3.2-1B / Llama-3.1-8B | Llama-3.2-3B + Llama-3.3-70B 대표 |
| Ministral-8B / Ministral-14B / Mistral-Nemo | Ministral-3B + Mistral-Small-24B 대표 |
| GLM-4.7-Flash | 일반 medium은 Hermes-3-8B + Phi-4-mini가 커버 |
| Gemma-3 시리즈 | Gemma-4로 대체 |

### 추가된 모델 (8개)

| 추가 | 카테고리 |
|---|---|
| Qwen3.6-27B | A1 (NEW 세대 Dense) |
| Qwen3.6-35B-A3B | A1 (NEW 세대 MoE) |
| Gemma-4-E4B-it (text-only 변형) | A3 (NEW small, principled-intelligence/gemma-4-E4B-it-text-only) |
| Gemma-4-31B-it | A3 (NEW large) |
| Phi-4-mini-instruct | A5 (NEW small, FC 학습된 mini variant) |
| gpt-oss-120b | A6 (NEW large reasoning) |
| Salesforce/Llama-Fin-8b | C (신규 finance, Llama-3 기반) |
| TheFinAI/Fino1-8B | C (신규 finance, Llama-3.1 기반 reasoning) |

---

## 6. 변경 이력

| 일자 | 변경 |
|---|---|
| 2026-04-29 | 44 모델 → 24 모델 reduce. Qwen3 (2507) 시리즈 제거 (3.5+3.6으로 대체), Cloud API (gpt-4o-mini, claude-sonnet-4-5) 제거, phi-4 (14B, FC 미지원) → Phi-4-mini-instruct (3.8B, FC 지원) 교체. 8종 추가 (Qwen3.6 Dense+MoE, Gemma-4 E4B/31B-it, Phi-4-mini-instruct, gpt-oss-120b, Salesforce/Llama-Fin-8b, TheFinAI/Fino1-8B). 옛 FinGPT-v3 / FinMA (Llama-1/2 base)는 outdated로 제외. HF 경로 모두 검증. |
| 2026-04-29 (smoke 후속) | Gemma-4-E4B-it 공식판은 multimodal (audio_tower)로 vLLM 0.17.0 호환 X → `principled-intelligence/gemma-4-E4B-it-text-only` (drop-in replacement)로 교체. transformers 5.3.0 → 5.7.0 + mistral_common 1.9.1 → 1.11.1 업그레이드. Gemma-4-31B-it 호환성 검증 진행 중. |
| 2026-04-29 (vLLM 0.19 업그레이드 후) | vLLM 0.17.0 → 0.19.0 업그레이드로 Gemma-4 공식 multimodal 직접 지원. **Gemma-4-E4B-it 공식판 (`google/gemma-4-E4B-it`)으로 환원** (text-only 변형은 weight loading 버그 별도 발생). 전용 parser `gemma4` 사용 (hermes parser 사용 시 chat template 형식 불일치로 0/5 실패). Phi-4-mini-instruct는 전용 `phi4_mini_json` parser도 0/5 실패 → pythonic/hermes/llama3_json 대안 파서 검증 진행 중. |

---

## 7. 환경 요구사항 (Server 2 셋업 가이드)

Server 1에서 검증된 환경 사양. Server 2도 동일하게 맞춰야 신규 모델 (Gemma-4, Qwen3.6, Phi-4-mini-instruct) 호환.

### 7.1 패키지 버전

| 패키지 | 버전 | 비고 |
|---|---|---|
| vLLM | **0.19.0** | Gemma-4 day-one, qwen3_xml/gemma4/phi4_mini_json 전용 parser 추가 |
| transformers | **5.7.0** | Gemma-4 architecture 지원 (5.3.0 미지원). vLLM 0.19 설치 시 4.57.6으로 다운그레이드 → 5.7.0 재업그레이드 필요 (pip warning 무시) |
| mistral_common | 1.11.1 | Mistral 계열 |
| torch | 2.10.0 | flash_attn 시스템판은 비호환 → `/tmp/fake_flash_attn` 스텁 사용 (run_round1.sh 자동 생성) |

```bash
pip install --upgrade vllm==0.19.0
pip install --upgrade transformers==5.7.0 mistral_common==1.11.1  # vLLM dep warning 무시
pip cache purge  # 디스크 부족 시 (49GB tmpfs는 47GB 차면 install 실패)
```

### 7.2 신규 아키텍처 모델별 vLLM 인자

| 모델 | tool-call-parser | 추가 인자 | 검증 결과 |
|---|---|---|---|
| Gemma-4-E4B-it (multimodal) | **gemma4** | (기본) | 4/5 ✅ — `<\|tool_call>call:func{...}<tool_call\|>` 형식 자동 파싱 |
| Gemma-4-31B-it | **gemma4** | (기본) | 5/5 🌟 |
| Qwen3.6-27B | qwen3_xml | (기본) | 5/5 ✅ |
| Qwen3.6-35B-A3B | qwen3_xml | `--max-model-len 32768` | 5/5 ✅ — 기본 max-len 초과 방지 |
| Phi-4-mini-instruct | (검증 중) | (기본) | phi4_mini_json 0/5 ❌ → pythonic/hermes/llama3_json 시도 중 |
| Llama-Fin-8b | llama3_json (검증 필요) | `--max-model-len 8192` | max_position_embeddings=8192 강제 필요 |
| Fino1-8B | llama3_json (검증 필요) | (기본) | 1/5 (parser 변경 검토) |
| gpt-oss-120b | openai | `--tensor-parallel-size 4 --max-model-len 16384 --reasoning-parser openai_gptoss --enforce-eager` | TP=4, S2 전용 |

### 7.3 ⚠ 주의사항 (호환성 함정)

- **Gemma-4 + hermes parser 금지**: chat template이 `<\|tool_call>call:func{...}<tool_call\|>` 형식을 사용. hermes의 `<tool_call>{json}</tool_call>` pattern과 불일치하여 called_tools=[] 발생. 반드시 `gemma4` parser 사용.
- **Gemma-4-E4B-it text-only 변형 (`principled-intelligence/...-text-only`) 사용 금지**: vLLM 0.19에서 `model.layers.0.layer_scalar` weight loading 실패. 공식 multimodal (`google/gemma-4-E4B-it`) + `gemma4` parser 사용.
- **vLLM 0.19 + transformers 4.57.6 (자동 설치) 조합 금지**: Gemma-4 모델 적재 시 architecture 인식 실패. 반드시 transformers 5.7.0으로 재업그레이드.
- **Gemma-4-31B-it Q4_0 cache mode**: 일부 quantization 메타데이터 적재 시간이 길어 vLLM 기동 max_wait 600s 권장.
- **Qwen3.6 35B-A3B (MoE)**: 전체 35B parameter지만 active 3B만 forward — TP 없이 single-GPU 가능. 단 KV cache + MoE expert 적재로 `--max-model-len 32768` 명시 필요 (기본값 적용 시 OOM 또는 적재 거부).
- **`HF_TOKEN`**: `.env`에 `HF_TOKEN : hf_xxx` (콜론+스페이스, `=` 아님) 형식. Server 2도 동일하게 `.env` 작성하거나 export 필요.
- **VLLM_ATTENTION_BACKEND=XFORMERS 제거**: vLLM 0.17부터 미지원. TP=2 worker crash 유발하므로 환경변수에 남겨두지 말 것.

### 7.4 Server 2 셋업 명령 (요약)

```bash
# 1. 저장소 clone (서브모듈 + LFS 포함)
git clone --recurse-submodules https://github.com/<user>/KA-001-AML-Assistant.git
cd KA-001-AML-Assistant
git lfs pull  # _datasets 대용량 파일 (parquet/duckdb)

# 2. 환경 설정
echo "HF_TOKEN : hf_xxx" > .env
pip install --upgrade vllm==0.19.0
pip install --upgrade transformers==5.7.0 mistral_common==1.11.1

# 3. 스모크 검증 (S2 대상 13개 모델 전체 5건씩)
BENCH_MAX_TOTAL=5 bash _paper/_experiments/scripts/run_round1.sh \
    --gpu 0 --port 11434 --group S2_LARGE_L1 --mode kr

# 4. 본 실험 (마스터 오케스트레이터)
nohup bash _paper/_experiments/scripts/run_round1_master.sh \
    --server 2 --modes kr,en,mt > master_s2.log 2>&1 &
```

### 7.5 Server 2 분담 모델 호환성 사전 체크리스트

| 모델 | parser | 추가 인자 | Server 1 사전 검증 | 서버 2 추가 검증 필요 |
|---|---|---|---|---|
| Qwen3.5-27B | qwen3_coder | `--reasoning-parser qwen3 --enforce-eager` | ✅ Round 1 v3 통과 | (skip) |
| Qwen3.6-27B | qwen3_xml | (기본) | ✅ smoke 5/5 | (skip) |
| Qwen3.6-35B-A3B | qwen3_xml | `--max-model-len 32768` | ✅ smoke 5/5 | (skip) |
| Llama-3.3-70B-Instruct | llama3_json | TP=2, `--enforce-eager` | ✅ Round 1 v3 통과 | (skip) |
| Gemma-4-31B-it | gemma4 | (기본) | ✅ smoke 5/5 (vLLM 0.19) | **vLLM 0.19 + transformers 5.7.0 필수** |
| Mistral-Small-3.2-24B | mistral | (기본) | ✅ Round 1 v3 통과 | (skip) |
| EXAONE-4.0-32B | hermes | `--trust-remote-code` | ✅ Round 1 v3 통과 | (skip) |
| gpt-oss-20b | openai | `--reasoning-parser openai_gptoss` | ✅ Round 1 v3 통과 | (skip) |
| gpt-oss-120b | openai | TP=4, `--reasoning-parser openai_gptoss --enforce-eager --max-model-len 16384` | ❌ S1 GPU 부족 | **TP=4 메모리 검증 필수 (4× 80GB)** |
| xLAM-2-70b | xlam | TP=2, `--enforce-eager` | ✅ Round 1 v3 통과 | (skip) |
| A.X-4.0 | hermes | TP=2, `--enforce-eager` | ✅ Round 1 v3 통과 | (skip) |
| kanana-2-30b-a3b-instruct | hermes + kanana plugin | (기본) | ✅ Round 1 v3 통과 | kanana_tool_calls plugin 경로 확인 |
| kanana-2-30b-a3b-thinking-2601 | hermes + kanana plugin | `--reasoning-parser deepseek_r1` | ✅ Round 1 v3 통과 | 동일 |
