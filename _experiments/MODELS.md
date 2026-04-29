# AML-Bench Evaluation Models

NeurIPS 2026 E&D 제출 기준 평가 대상 모델 + RQ별 매핑. 최종 갱신 2026-04-30.

## 1. 선정 원칙

| 카테고리 | 선정 기준 | 모델 수 |
|---|---|---|
| A. 일반 유명 모델 | 계열당 1 small + 1 large 원칙 (Qwen, Llama, Gemma, Mistral, Phi, gpt-oss, 도구특화) | 16 |
| B. 한국어 특화 | LG, SKT, KaKao 대표 (small+large 페어) | 6 |
| C. 금융 특화 | FC 보존 의도된 modern finance LLM (DragonLLM Open Finance Suite) | 2 |
| 합계 | | 24 (+ 5 thinking 변형 = 29 runs/mode) |

> **금융 특화 모델 선정**: 옛 FinGPT-v3 (Llama-2), FinMA-7B (Llama-1)는 base outdated. domain SFT가 FC 능력을 손상시킨 모델 (Salesforce/Llama-Fin-8b, TheFinAI/Fino1-8B)도 smoke 0/5로 제외. 최종 후보는 DragonLLM Open Finance Suite — base capability 보존을 명시적 학습 목표로 설정한 2025-11 출시 8B 2종. BloombergGPT 등 비공개 제외.

---

## 2. 모델 일람표

### A. 일반 유명 모델 (16개)

#### A1. Qwen 계열 (Alibaba) — 4개

| # | 모델 | HF 경로 | 크기 | 아키텍처 | tool-call-parser | think 변형 | 서버 | RQ |
|---|---|---|---|---|---|---|---|---|
| 1 | Qwen3.5-4B | `Qwen/Qwen3.5-4B` | 4B | Dense | qwen3_coder + reasoning_qwen3 | think+nothink | S1 | RQ1, RQ3, RQ2 |
| 2 | Qwen3.5-27B | `Qwen/Qwen3.5-27B` | 27B | Dense | qwen3_coder + enforce-eager | think+nothink | S2 | RQ1, RQ3, RQ2, RQ4 |
| 3 | Qwen3.6-27B | `Qwen/Qwen3.6-27B` | 27B | Dense | qwen3_xml ✅ | thinking-preservation | S2 | RQ1, RQ2, 세대비교 |
| 4 | Qwen3.6-35B-A3B | `Qwen/Qwen3.6-35B-A3B` | 35B | MoE (active 3B) | qwen3_xml + `--max-model-len 32768` ✅ | thinking-preservation | S2 | RQ1, RQ2, MoE 분석 |

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

> Gemma-4: 공식 multimodal + `gemma4` parser. 호환성 detail은 Section 7 참조.

#### A4. Mistral 계열 — 2개

| # | 모델 | HF 경로 | 크기 | tool-call-parser | think | 서버 | RQ |
|---|---|---|---|---|---|---|---|
| 9 | Ministral-3-3B-Instruct-2512 | `mistralai/Ministral-3-3B-Instruct-2512` | 3B Dense | mistral | n/a | S1 | RQ1, RQ2 |
| 10 | Mistral-Small-3.2-24B-Instruct-2506 | `mistralai/Mistral-Small-3.2-24B-Instruct-2506` | 24B Dense | mistral | n/a | S2 | RQ1, RQ2 |

#### A5. Phi 계열 (Microsoft) — 1개

| # | 모델 | HF 경로 | 크기 | tool-call-parser | think | 서버 | RQ |
|---|---|---|---|---|---|---|---|
| 11 | Phi-4-mini-instruct | `microsoft/Phi-4-mini-instruct` | 3.8B Dense | **phi4_mini_json + 공식 jinja** ✅ | n/a | S1 | RQ1 |

> phi-4 (14B)는 FC 미지원으로 제외. Phi-4-mini-instruct는 post-training FC 학습 (Microsoft 공식). chat template 필수 — Section 7 참조.

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

### C. 금융 특화 모델 (2개) — DragonLLM Open Finance Suite (FC 보존)

| # | 모델 | HF 경로 | 크기 | base | tool-call-parser | think | 서버 | 비고 | RQ |
|---|---|---|---|---|---|---|---|---|---|
| 23 | Llama-Open-Finance-8B (DragonLLM) | `DragonLLM/Llama-Open-Finance-8B` | 8B | Llama-3.1-8B | llama3_json | n/a | S1 (GPU 0) | AGEFI+Dragon LLM, FC 의도 보존. smoke 3/5 score 0.78. parallel TC 미지원 (single-tool만) | RQ1, RQ6 (Finance vs General) |
| 24 | Qwen-Open-Finance-R-8B (DragonLLM) | `DragonLLM/Qwen-Open-Finance-R-8B` | 8B | Qwen3-8B | qwen3_xml + `--reasoning-parser qwen3` | n/a (R = reasoning preserved) | S1 (GPU 1) | reasoning + FC 보존. smoke 3/5 score 0.73, 시간 133s/5건 (think on by default) | RQ1, RQ6 |

> DragonLLM (LLM Open Finance Initiative): AGEFI + Dragon LLM, base FC 능력 보존 의도. gated=auto repo — 첫 사용 시 HF UI에서 access 클릭 필요.

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
| Qwen3.6-27B | thinking-preservation 옵션 (think+nothink 두 entry로 분리 등록 가능) |

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
| Finance | DragonLLM/Llama-Open-Finance-8B (Llama-3.1 base), DragonLLM/Qwen-Open-Finance-R-8B (Qwen-3 base) | Llama-3.2-3B-Instruct, Hermes-3-Llama-3.1-8B, Ministral-3-3B |

→ 도메인 특화 효과: implicit (한국어, 학습 데이터 기반) vs explicit (금융, 도메인 fine-tuning) 비교.

---

## 4. 이전 44개 → 24개 변경 요약

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
| DragonLLM/Llama-Open-Finance-8B | C (finance, Llama-3.1 base, FC 보존) |
| DragonLLM/Qwen-Open-Finance-R-8B | C (finance, Qwen-3 base, reasoning + FC 보존) |

---

## 5. 변경 이력

| 일자 | 변경 |
|---|---|
| 2026-04-29 | 44 → 24 모델 reduce. Qwen3 (2507) 시리즈 제거, Cloud API 제거, phi-4 (14B, FC 미지원) → Phi-4-mini-instruct 교체. 신규 추가: Qwen3.6 Dense+MoE, Gemma-4 E4B/31B-it, Phi-4-mini-instruct, gpt-oss-120b, finance 후보 (Llama-Fin-8b/Fino1-8B). 옛 FinGPT-v3/FinMA outdated 제외. |
| 2026-04-29 | vLLM 0.17.0 → 0.19.0 + transformers 5.3.0 → 5.7.0 + mistral_common 1.11.1 업그레이드. Gemma-4 공식 multimodal 적재 가능, 전용 `gemma4` parser 등록. |
| 2026-04-30 | Phi-4-mini-instruct chat template 문제 해결: vLLM 공식 `tool_chat_template_phi4_mini.jinja` (functools[...] 형식) 저장소 포함 + `--chat-template` 인자 필수. 4종 parser 단독 0/5 → template 적용 시 2/5 ✅. 스크립트 rename: `run_round1.sh` → `run_benchmark.sh`, `run_round1_master.sh` → `run_master.sh`. |
| 2026-04-30 | finance 카테고리 swap: Llama-Fin-8b / Fino1-8B (3종 parser ablation 0/5, domain SFT가 native FC 손상)를 DragonLLM Open Finance 8B 2종 (FC 보존 설계)으로 교체. 24-model 카운트 유지. |
| 2026-04-30 | RQ2 4-way ablation 인프라 추가: `run_benchmark.sh --tools-lang en` + `GROUP_RQ2_REPS` (6 representatives) + `run_master.sh --rq2-ablation`. KR-EN/EN-EN 결과는 별도 디렉토리 `results_{kr,en}_tools_en/`에 분리. |

---

## 6. 환경 요구사항 + 스모크 검증 결과

Server 1에서 검증된 환경 사양. Server 2도 동일하게 맞춰야 신규 모델 (Gemma-4, Qwen3.6, Phi-4-mini-instruct) 호환.

### 6.1 패키지 버전

| 패키지 | 버전 | 비고 |
|---|---|---|
| vLLM | **0.19.0** | Gemma-4 day-one, qwen3_xml/gemma4/phi4_mini_json 전용 parser 추가 |
| transformers | **5.7.0** | Gemma-4 architecture 지원 (5.3.0 미지원). vLLM 0.19 설치 시 4.57.6으로 다운그레이드 → 5.7.0 재업그레이드 필요 (pip warning 무시) |
| mistral_common | 1.11.1 | Mistral 계열 |
| torch | 2.10.0 | flash_attn 시스템판은 비호환 → `/tmp/fake_flash_attn` 스텁 사용 (run_benchmark.sh 자동 생성) |

```bash
pip install --upgrade vllm==0.19.0
pip install --upgrade transformers==5.7.0 mistral_common==1.11.1  # vLLM dep warning 무시
pip cache purge  # 디스크 부족 시 (49GB tmpfs는 47GB 차면 install 실패)
```

### 6.2 신규 아키텍처 모델별 vLLM 인자 + 스모크 결과

5건 스모크 (`BENCH_MAX_TOTAL=5`) 기준.

| 모델 | parser | 추가 인자 | 스모크 (3/5+ = 정식 포함) |
|---|---|---|---|
| Gemma-4-E4B-it | gemma4 | (기본) | 4/5, 0.86 ✅ |
| Gemma-4-31B-it | gemma4 | (기본) | 5/5, 0.95 ✅ |
| Qwen3.6-27B | qwen3_xml | (기본) | 5/5, 0.83 ✅ |
| Qwen3.6-35B-A3B | qwen3_xml | `--max-model-len 32768` | 5/5, 0.83 ✅ |
| Phi-4-mini-instruct | phi4_mini_json | `--chat-template _paper/_experiments/scripts/tool_chat_template_phi4_mini.jinja` | 2/5, 0.65 ✅ (small 한계) |
| DragonLLM/Llama-Open-Finance-8B | llama3_json | (기본) | 3/5, 0.78 ✅ (parallel TC 미지원) |
| DragonLLM/Qwen-Open-Finance-R-8B | qwen3_xml + `--reasoning-parser qwen3` | (기본) | 3/5, 0.73 ✅ (reasoning preserved, ~27s/case) |
| gpt-oss-120b | openai | TP=4, `--reasoning-parser openai_gptoss --enforce-eager --max-model-len 16384` | (S2에서 검증) ⏳ |

### 6.3 호환성 함정

- **Gemma-4 + hermes parser 금지**: chat template이 `<\|tool_call>call:func{...}<tool_call\|>` 형식을 사용. hermes의 `<tool_call>{json}</tool_call>` pattern과 불일치하여 called_tools=[] 발생. 반드시 `gemma4` parser 사용.
- **Gemma-4-E4B-it text-only 변형 (`principled-intelligence/...-text-only`) 사용 금지**: vLLM 0.19에서 `model.layers.0.layer_scalar` weight loading 실패. 공식 multimodal (`google/gemma-4-E4B-it`) + `gemma4` parser 사용.
- **vLLM 0.19 + transformers 4.57.6 (자동 설치) 조합 금지**: Gemma-4 모델 적재 시 architecture 인식 실패. 반드시 transformers 5.7.0으로 재업그레이드.
- **Gemma-4-31B-it Q4_0 cache mode**: 일부 quantization 메타데이터 적재 시간이 길어 vLLM 기동 max_wait 600s 권장.
- **Qwen3.6 35B-A3B (MoE)**: 전체 35B parameter지만 active 3B만 forward — TP 없이 single-GPU 가능. 단 KV cache + MoE expert 적재로 `--max-model-len 32768` 명시 필요 (기본값 적용 시 OOM 또는 적재 거부).
- **Phi-4-mini-instruct chat template 필수**: Microsoft 공식 chat template 형식과 vLLM `phi4_mini_json` parser 형식 불일치로 0/5 실패. `--chat-template _paper/_experiments/scripts/tool_chat_template_phi4_mini.jinja` 인자 필수 (저장소에 포함). hermes/pythonic/llama3_json 등 대체 parser도 0/5 (기본 template으로는 어떤 parser도 작동 안 함).
- **`HF_TOKEN`**: `.env`에 `HF_TOKEN : hf_xxx` (콜론+스페이스, `=` 아님) 형식. Server 2도 동일하게 `.env` 작성하거나 export 필요.
- **VLLM_ATTENTION_BACKEND=XFORMERS 제거**: vLLM 0.17부터 미지원. TP=2 worker crash 유발하므로 환경변수에 남겨두지 말 것.

### 6.4 Server 2 초기 셋업

```bash
git clone --recurse-submodules https://github.com/<user>/KA-001-AML-Assistant.git
cd KA-001-AML-Assistant && git lfs pull
echo "HF_TOKEN : hf_xxx" > .env
pip install --upgrade vllm==0.19.0
pip install --upgrade transformers==5.7.0 mistral_common==1.11.1
```

DragonLLM 2종은 gated=auto repo — 첫 사용 전 HF UI에서 access 클릭 필요:
- https://huggingface.co/DragonLLM/Llama-Open-Finance-8B
- https://huggingface.co/DragonLLM/Qwen-Open-Finance-R-8B

스모크 검증 명령 + 본 실험 실행은 Section 7 참조.

### 6.5 Server 2 분담 모델 호환성 체크리스트

Server 2 분담 13개 모델은 모두 사전 실험에서 동일 parser/인자 조합으로 통과한 상태. parser/인자는 Section 2 모델 일람표 + run_benchmark.sh의 GROUP_S2_* entry 참조.

Server 2에서만 추가 검증이 필요한 항목:

| 모델 | 검증 항목 |
|---|---|
| Gemma-4-31B-it | vLLM 0.19 + transformers 5.7.0 환경 확인 |
| gpt-oss-120b | TP=4 (4× 80GB) 메모리 적재 검증 — 본 실험 전 스모크 권장 |
| kanana-2 (instruct/thinking) | `_paper/_experiments/scripts/kanana_tool_calls/` plugin 경로 확인 (저장소 포함됨) |

---

## 7. RQ별 실험 실행 가이드

| RQ | 평가 대상 | 실행 명령 | 서버 | 결과 위치 |
|---|---|---|---|---|
| **RQ1** Model landscape | 24 baseline | master 기본 실행 (KR mode 결과) | S1 + S2 | `results_kr/` |
| **RQ2** Language alignment 4-way | 6 reps × {KR-KR, EN-KR, KR-EN, EN-EN} | (기본 KR-KR/EN-KR) + `--rq2-ablation` (KR-EN/EN-EN) | S2 only | `results_{kr,en}/` + `results_{kr,en}_tools_en/` |
| **RQ3** Thinking mode | 5 think+nothink 페어 | master 기본 실행 (think 변형 자동 포함) | S1 + S2 | `results_{kr,en,mt}/` (think 변형은 별도 entry) |
| **RQ4** Single vs Multi-turn | 24 baseline | master `--modes mt` 포함 | S1 + S2 | `results_mt/` |
| **RQ5** BFCL correlation | 10~12 BFCL overlap | (별도) BFCL v4 직접 실행 | manual | `bfcl_results/score/<model>/` |
| **RQ6** Domain specialization | 10 비교군 | RQ1 결과의 후처리 분석 | (post-hoc) | `analysis/` |

### 7.1 Server 1 (이 서버, 2× H100)

11 모델 × {KR, EN, MT} baseline:
```bash
# 한 번에 다 (KR → EN → MT 순차)
nohup bash _paper/_experiments/scripts/run_master.sh --server 1 --modes kr,en,mt \
    > master_s1.log 2>&1 &

# 단일 mode
bash _paper/_experiments/scripts/run_master.sh --server 1 --modes kr
```

Server 1은 RQ1·RQ3·RQ4·RQ6의 small/medium 데이터 기여. RQ2 representatives는 모두 Server 2 large/TP=2 모델이므로 **Server 1은 RQ2 ablation에 참여하지 않음**.

### 7.2 Server 2 (다른 서버, 6× H100)

13 모델 × {KR, EN, MT} baseline:
```bash
nohup bash _paper/_experiments/scripts/run_master.sh --server 2 --modes kr,en,mt \
    > master_s2.log 2>&1 &
```

Server 2 baseline 완료 후 **RQ2 ablation** (6 reps × {KR-EN, EN-EN} = 12 runs):
```bash
nohup bash _paper/_experiments/scripts/run_master.sh --server 2 --rq2-ablation --modes kr,en \
    > master_s2_rq2.log 2>&1 &
```

옵션:
- `--skip-tp4`: gpt-oss-120b 제외 (TP=4 메모리 검증 후 활성화 권장)
- `--skip-tp2`: 70B+ 모델 3종 제외
- `--skip-thinking`: think=True 변형 제외

### 7.3 RQ2 / RQ3 / RQ5 추가 메모

**RQ2 4-way 2x2** (Server 2 전용). 6 reps × 4 차원:

| 차원 | cases | tools | 실행 명령 |
|---|---|---|---|
| KR-KR | KR | KR (default) | `--modes kr` master baseline에 자동 포함 |
| EN-KR | EN | KR (default) | `--modes en` master baseline에 자동 포함 |
| KR-EN | KR | EN | `--rq2-ablation --modes kr` |
| EN-EN | EN | EN | `--rq2-ablation --modes en` |

**RQ3 (Thinking mode)**: `benchmark.py` registry에 think+nothink 두 entry로 등록된 5 페어가 master 기본 실행 시 양쪽 모두 자동 평가. 제외 시 `--skip-thinking` 또는 `BENCH_SKIP_THINK=1`.

**RQ5 (BFCL correlation)**: master 흐름 외부. BFCL v4 직접 실행 → `bfcl_results/score/<model>/`. 사후 분석 단계에서 AML-Bench score와 매핑.

**RQ1, RQ4, RQ6**: 별도 실행 불필요. RQ1/RQ4는 master baseline에 자동 포함, RQ6는 RQ1 결과의 카테고리 후처리 분석.
