# AML-Bench: A Function Calling Benchmark for Anti-Money Laundering Agents

## Overview

AML-Bench is a domain-specific function calling benchmark for evaluating LLMs as anti-money laundering (AML) agents. Unlike existing tool-use benchmarks targeting general-purpose APIs, AML-Bench evaluates 23 AML-specific tools extracted from a real operational AML agent platform.

## Key Features

- **1,258 expert-curated test cases** across 24 evaluation categories and 3 difficulty levels (Easy + irrelevance: 673 / Medium: 412 / Hard: 173)
- **29 models** from 12 families evaluated on vLLM (largest model comparison in domain-specific tool-calling benchmarks)
- **2×2 language ablation**: query language (KR/EN) × tool schema language (KR/EN) — controlled decomposition of language effects
- **Multi-turn STR benchmark**: 50 scenarios evaluating end-to-end suspicious transaction report generation
- **3-round reproducibility** (KR + EN): mean ± standard deviation reported for all metrics
- **BFCL correlation analysis**: direct measurement of general-benchmark vs domain-benchmark alignment (RQ6)

## Main Findings

1. Tool-calling accuracy does not scale with model size — 4B Qwen3.5 (think) outperforms Llama-3.3-70B and A.X-4.0 (72B)
2. Korean prompts yield higher accuracy than English for **84% of models (37/44)**; mean delta **+0.030**
3. Thinking mode effect is size-dependent: small Qwen3.5 models show significant degradation (−9.06pp at 0.8B, McNemar p<10⁻¹⁰), while larger models (≥4B) show neutral-to-positive effects
4. 2×2 ablation reveals query-language and tool-schema-language effects are similar in magnitude (−0.029 vs −0.039) with weak interaction
5. Multi-turn performance diverges sharply from single-turn — Mistral series ranks top-tier in single-turn but collapses to near-zero in multi-turn; Pearson r between single-turn and multi-turn composite scores is only 0.29 (p=0.16)
6. AML-specific tools (STR field validation, AML glossary lookup) show 0.608–0.622 accuracy even for top-tier general models — gap that general benchmarks (BFCL v3/v4) cannot detect

## Benchmark Structure

| Subdomain | Tools | Description |
|-----------|-------|-------------|
| Transaction Stats & Inquiry | 6 | Summary statistics, raw queries, account profiles, period comparison |
| AML Detection & Reporting | 5 | Network analysis, pattern detection, fraud prediction, STR generation |
| CTR, Risk & Monitoring | 3 | High-value transaction detection, risk scoring, rule-based monitoring |
| Flow, Trend & Channel | 6 | Dormant reactivation, smurfing, trend analysis, cross-institution flow |
| AML Reference | 3 | FIU reference lookup, STR validation, AML glossary |

## Repository Structure

```
_manuscript/          — Paper source (LaTeX, ACL/EMNLP format)
benchmarks/           — Single-turn benchmark cases (24 JSON files, 1,258 cases)
benchmarks_en/        — English-translated cases (for KR-EN ablation)
benchmarks_multiturn/ — Multi-turn STR benchmark scenarios (50 JSON)
figures/              — Paper figures (PNG/PDF)
tables/               — Comparison results (Excel)
results_repro/        — Reproducibility experiment results
```

> **Note**: 벤치마크 실행 스크립트와 실험 결과는 main repo의 `_experiments/` 디렉토리에서 관리됩니다.

## Evaluation Metrics

### Single-turn (1,258 cases)
- **Composite Score** (s ∈ [0, 1]): weighted combination of tool selection and parameter accuracy
- **Tool Selection Accuracy** (primary_tool_hit_rate): fraction of cases with correct primary tool
- **Parameter Accuracy** (avg_param_accuracy): key-value match accuracy for correctly selected tools

### Multi-turn STR (50 scenarios)
- **Average Score** (avg_score): per-turn tool selection + parameter accuracy averaged over all turns
- **Scenario Complete Rate**: fraction of 50 scenarios where all required tool calls were completed

---

## Experiment Results

### 1. Single-turn Tool Calling (KR, 1,258 cases × 29 models)

Results sorted by composite score. Mean ± std from 3-round reproducibility experiment.

| Rank | Model | Family | Size | Score | Tool Hit | Param Acc |
|------|-------|--------|------|-------|----------|-----------|
| 1 | Qwen3.5-27B (think) | Qwen | 27B | 0.9417±0.018 | 95.4% | 95.4% |
| 2 | Qwen3.5-27B (nothink) | Qwen | 27B | 0.9356±0.002 | 94.8% | 94.7% |
| 3 | Qwen3.5-9B (nothink) | Qwen | 9B | 0.9323±0.001 | 95.5% | 95.0% |
| 4 | xLAM-2-32b | Salesforce | 32B | 0.9333±0.000 | 93.8% | 91.6% |
| 5 | Qwen3-30B-Thinking (think) | Qwen | 30B | 0.9305±0.001 | 94.5% | 92.6% |
| 6 | Qwen3-30B-Thinking (nothink) | Qwen | 30B | 0.9300±0.001 | 94.5% | 92.5% |
| 7 | Ministral-3-14B | Mistral | 14B | 0.9266±0.002 | 93.2% | 92.1% |
| 8 | Qwen3-8B | Qwen | 8B | 0.9199±0.002 | 92.8% | 91.1% |
| 9 | Qwen3.5-4B (nothink) | Qwen | 4B | 0.9196±0.002 | 94.2% | 92.2% |
| 10 | Qwen3.5-4B (think) | Qwen | 4B | 0.9186±0.006 | 95.0% | 93.9% |
| 11 | kanana-2-30b-thinking (think) | Kakao | 30B | 0.9183±0.000 | 92.8% | 88.7% |
| 12 | Qwen3-Coder-30B | Qwen | 30B | 0.9182±0.002 | 93.8% | 91.5% |
| 13 | kanana-2-30b-thinking (nothink) | Kakao | 30B | 0.9178±0.000 | 92.7% | 88.7% |
| 14 | GLM-4.7-Flash | Zhipu | - | 0.9178±0.008 | 94.7% | 93.2% |
| 15 | Qwen3.5-9B (think) | Qwen | 9B | 0.9162±0.006 | 93.9% | 94.0% |
| 16 | EXAONE-4.0-32B | LG AI | 32B | 0.9141±0.000 | 91.4% | 90.1% |
| 17 | Ministral-3-8B | Mistral | 8B | 0.9101±0.001 | 92.8% | 89.1% |
| 18 | Qwen3-4B-Thinking (nothink) | Qwen | 4B | 0.9090±0.021 | 92.9% | 88.5% |
| 19 | Qwen3-4B-Thinking (think) | Qwen | 4B | 0.9086±0.021 | 92.9% | 88.4% |
| 20 | Llama-3.3-70B | Meta | 70B | 0.8984±0.001 | 91.6% | 87.1% |
| 21 | Qwen3-30B-Instruct | Qwen | 30B | 0.8958±0.001 | 93.0% | 90.6% |
| 22 | Ministral-3-3B | Mistral | 3B | 0.8949±0.007 | 90.3% | 87.7% |
| 23 | A.X-4.0 | SKT | - | 0.8915±0.000 | 89.9% | 84.6% |
| 24 | Qwen3-4B-Instruct | Qwen | 4B | 0.8861±0.001 | 90.5% | 88.4% |
| 25 | gpt-oss-20b (nothink) | OpenAI | 20B | 0.8858±0.007 | 88.9% | 87.6% |
| 26 | Mistral-Small-24B | Mistral | 24B | 0.8854±0.025 | 88.2% | 88.0% |
| 27 | gpt-oss-20b (think) | OpenAI | 20B | 0.8849±0.007 | 88.8% | 87.5% |
| 28 | xLAM-2-8b | Salesforce | 8B | 0.8547±0.000 | 85.1% | 81.2% |
| 29 | Qwen3.5-2B (nothink) | Qwen | 2B | 0.8116±0.015 | 85.1% | 80.7% |
| 30 | Llama-3.1-8B | Meta | 8B | 0.8071±0.001 | 81.8% | 78.9% |
| 31 | EXAONE-4.0-1.2B | LG AI | 1.2B | 0.8068±0.000 | 80.4% | 75.0% |
| 32 | Qwen3.5-0.8B (nothink) | Qwen | 0.8B | 0.7938±0.018 | 82.2% | 74.1% |
| 33 | xLAM-2-70b | Salesforce | 70B | 0.7900±0.000 | 73.1% | 78.0% |
| 34 | kanana-2-30b-instruct | Kakao | 30B | 0.7798±0.000 | 74.0% | 74.1% |
| 35 | Qwen3.5-2B (think) | Qwen | 2B | 0.7683±0.022 | 78.9% | 76.0% |
| 36 | Qwen2.5-1.5B | Qwen | 1.5B | 0.7376±0.000 | 73.9% | 65.7% |
| 37 | Llama-3.2-3B | Meta | 3B | 0.7237±0.001 | 74.1% | 69.4% |
| 38 | xLAM-2-3b | Salesforce | 3B | 0.7232±0.000 | 68.7% | 69.0% |
| 39 | Qwen3.5-0.8B (think) | Qwen | 0.8B | 0.7124±0.003 | 69.3% | 66.7% |
| 40 | Hermes-3-Llama-3.1-8B | NousResearch | 8B | 0.6892±0.000 | 62.4% | 65.2% |
| 41 | A.X-4.0-Light | SKT | - | 0.6592±0.004 | 58.1% | 60.2% |
| 42 | xLAM-2-1b | Salesforce | 1B | 0.5764±0.000 | 49.9% | 48.8% |
| 43 | Mistral-Nemo-12B | Mistral | 12B | 0.5647±0.000 | 46.5% | 50.6% |
| 44 | Llama-3.2-1B | Meta | 1B | 0.5207±0.003 | 56.8% | 28.4% |

**Overall mean**: 0.845 (KR) / 0.802 (EN)

### 2. Korean vs English Ablation (29 models × 1,258 cases)

동일 벤치마크 케이스를 한국어/영어로 실행하여 질문 언어에 따른 정확도 차이를 분석.

| Metric | Value |
|--------|-------|
| KR > EN (한국어가 더 높은 모델) | **37/44 (84%)** |
| Mean score delta (KR − EN) | **+0.030** |
| Max KR advantage | +0.178 (A.X-4.0-Light) |
| Max EN advantage | −0.113 (Mistral-Nemo) |

**주요 발견**: 대부분의 모델이 한국어 프롬프트에서 더 높은 정확도를 보임. 이는 벤치마크의 도구 스키마(파라미터명)가 한국어로 정의되어 있어, 한국어 질문 시 파라미터 매칭이 더 정확하기 때문으로 분석됨. 영어가 우세한 7개 모델은 대부분 영어 중심 학습 모델(Kanana-2-Instruct, Mistral-Nemo 등)이거나 비영어 도구 스키마 처리에 취약한 모델임.

### 2b. 2×2 Ablation: Query Language × Tool Schema Language (43 models, newly collected)

질의 언어 효과와 도구 스키마 언어 효과를 독립적으로 분해하는 2×2 통제 ablation.

| Configuration | Mean Composite Score | 효과 |
|---|---|---|
| KR–KR (baseline) | **0.838** | — |
| EN–KR (질의만 EN) | 0.809 | 질의 언어 효과 −0.029 |
| KR–EN (도구만 EN) | 0.798 | 도구 스키마 효과 −0.039 |
| EN–EN (모두 EN) | 0.793 | 관측 총효과 −0.045 |

- 두 개별 효과의 합 (−0.068) vs 관측 총효과 (−0.045) → **상호작용 약함**
- 극단 민감 모델: **Qwen3-Coder-30B** (KR-EN 0.574, EN-EN 0.195) — 도구 스키마 언어 변화에 치명적
- 99.99% 커버리지 (221,389/221,408) — Llama-3.3-70B 10건은 context-window-filling 특성으로 제외

### 3. Multi-turn STR Benchmark (50 scenarios × 29 models)

AML 에이전트가 다중 턴 대화를 통해 의심거래보고서(STR)를 작성하는 end-to-end 시나리오 평가. 3회 반복 실험의 mean±std 보고.

| Rank | Model | avg_score | Complete Rate |
|------|-------|-----------|---------------|
| 1 | xLAM-2-70b | 0.802±0.000 | 50.0% |
| 2 | kanana-2-30b-thinking (think) | 0.796±0.000 | 44.0% |
| 3 | kanana-2-30b-thinking (nothink) | 0.791±0.000 | 36.0% |
| 4 | xLAM-2-32b | 0.786±0.000 | 38.0% |
| 5 | xLAM-2-8b | 0.766±0.000 | 36.0% |
| 6 | A.X-4.0 | 0.760±0.000 | 38.0% |
| 7 | Qwen3-4B-Thinking (nothink) | 0.752±0.000 | 36.0% |
| 8 | Qwen3.5-27B (nothink) | 0.751±0.002 | 30.0% |
| 9 | Qwen3-30B-Thinking (nothink) | 0.750±0.000 | 28.0% |
| 10 | Qwen3-4B-Thinking (think) | 0.750±0.000 | 34.0% |
| 11 | Qwen3-30B-Thinking (think) | 0.749±0.000 | 28.0% |
| 12 | Qwen3-8B | 0.749±0.000 | 32.0% |
| 13 | Llama-3.1-8B | 0.732±0.000 | 30.0% |
| 14 | Qwen3.5-0.8B (nothink) | 0.730±0.000 | 22.0% |
| 15 | Qwen3.5-27B (think) | 0.714±0.004 | 12.0% |
| 16 | Llama-3.3-70B | 0.704±0.000 | 22.0% |
| 17 | Qwen3.5-4B (nothink) | 0.703±0.000 | 14.0% |
| 18 | EXAONE-4.0-32B | 0.699±0.000 | 12.0% |
| 19 | Qwen3.5-9B (nothink) | 0.698±0.000 | 18.0% |
| 20 | Qwen3.5-4B (think) | 0.688±0.000 | 20.0% |
| 21 | Qwen3-Coder-30B | 0.686±0.000 | 10.0% |
| 22 | GLM-4.7-Flash | 0.680±0.006 | 12.0% |
| 23 | gpt-oss-20b (think) | 0.673±0.001 | 16.7% |
| 24 | gpt-oss-20b (nothink) | 0.666±0.011 | 9.3% |
| 25 | Qwen3.5-2B (nothink) | 0.663±0.003 | 22.0% |
| 26 | Qwen3-30B-Instruct | 0.653±0.000 | 8.0% |
| 27 | Qwen3.5-9B (think) | 0.651±0.000 | 8.0% |
| 28 | Qwen3-4B-Instruct | 0.650±0.000 | 10.0% |
| 29 | Llama-3.2-3B | 0.642±0.009 | 10.7% |
| 30 | Qwen2.5-1.5B | 0.623±0.000 | 10.0% |
| 31 | kanana-2-30b-instruct | 0.620±0.000 | 4.0% |
| 32 | Hermes-3-Llama-3.1-8B | 0.604±0.000 | 16.0% |
| 33 | EXAONE-4.0-1.2B | 0.586±0.000 | 10.0% |
| 34 | xLAM-2-3b | 0.559±0.000 | 10.0% |
| 35 | Qwen3.5-2B (think) | 0.504±0.009 | 0.7% |
| 36 | A.X-4.0-Light | 0.493±0.000 | 2.0% |
| 37 | xLAM-2-1b | 0.452±0.000 | 0.0% |
| 38 | Qwen3.5-0.8B (think) | 0.439±0.000 | 0.0% |
| 39 | Llama-3.2-1B | 0.333±0.005 | 0.0% |
| 40 | Ministral-3-8B | 0.244±0.000 | 0.0% |
| 41 | Mistral-Small-24B | 0.238±0.000 | 0.0% |
| 42 | Ministral-3-3B | 0.238±0.000 | 0.0% |
| 43 | Ministral-3-14B | 0.217±0.000 | 0.0% |
| 44 | Mistral-Nemo-12B | 0.180±0.000 | 0.0% |

**Overall mean**: avg_score=0.617, scenario complete=16.8%

### 4. Single-turn vs Multi-turn 비교 분석

| 관찰 | 내용 |
|------|------|
| **싱글턴-멀티턴 역전** | xLAM-2-70b는 싱글턴 33위(0.790) → 멀티턴 1위(0.802). Ministral-14B는 싱글턴 7위(0.927) → 멀티턴 43위(0.217) |
| **Mistral 계열 멀티턴 붕괴** | Mistral 전 모델이 멀티턴에서 complete rate 0%, avg_score 0.18~0.24. 멀티턴 대화 유지 능력 부재 |
| **xLAM 계열 멀티턴 강세** | xLAM-70b, 32b, 8b 모두 멀티턴 Top 5. 도구 호출 특화 학습의 멀티턴 전이 효과 |
| **Kakao kanana-2 선전** | kanana-2-30b-thinking이 멀티턴 2~3위. 한국어 도메인 특화 + thinking 모드 시너지 |
| **모델 크기 무관** | 멀티턴에서도 4B(Qwen3-4B-Thinking)가 30B~70B 모델을 상회 |

### 5. Reproducibility

| 실험 | Round 1 | Round 2 | Round 3 | 상태 |
|------|---------|---------|---------|------|
| Singleturn KR (29 models) | ✅ | ✅ | ✅ | 완료 |
| Singleturn EN (29 models) | ✅ | ✅ | ✅ | 완료 |
| Multiturn STR (29 models) | ✅ | ✅ | ✅ | 완료 |
| 2×2 Ablation (C1 KR-EN, C3 EN-EN, 43 models) | ✅ (1회) | — | — | 완료 (단일 라운드) |

**싱글턴 KR**: 3회 반복 완료. `repro_mean_std.json`에 29개 모델 mean±std 수록. 4개 모델은 3회 모두 동일 점수 (완전 결정론적).

**멀티턴**: 3회 반복 결과 매우 안정적 (mean score 0.617±0.001, complete rate 16.8%±0.1%). 변동 모델: Qwen3.5-2B think (±0.019), gpt-oss-20b nothink (±0.018), GLM-4.7-Flash (±0.012).

**Bootstrap ranking stability**: 케이스 수준 10,000회 재표집 결과, 원본 대비 Kendall τ 평균 0.929 (95% CI [0.888, 0.960]); 100% 반복에서 τ>0.8.

### 5b. BFCL v4 Correlation (RQ6, ongoing)

범용 function calling 벤치마크 BFCL v4 (10,417 케이스)를 44 모델 중 중복 모델에 대해 직접 실행하여 AML-Bench와의 상관관계를 측정 중.

| Phase | Models Covered | Status |
|---|---|---|
| Phase A (BFCL 레지스트리 기등록) | xLAM-2 family (5), Qwen3-8B, Qwen3-30B-A3B-Instruct, Qwen3-4B-Instruct-2507 | ✅ 완료 (8 모델) |
| Phase B (커스텀 등록) | Qwen3.5-9B, Qwen3.5-4B | ✅ 완료 |
| Phase B Part 2 | Qwen3.5-27B (AML Top 1-2) | 🔄 진행 중 (TP=2) |
| Phase C (선택) | Thinking variants | ⏳ 평가 후 결정 |

현 단계 (n=10) BFCL Top scores: xLAM-2-32b (48.97%), xLAM-2-70b (48.06%), xLAM-2-8b (45.77%), Qwen3-8B (37.96%), Qwen3.5-9B (35.97%), Qwen3-4B-Instruct-2507 (33.54%), Qwen3-30B-Instruct-2507 (33.30%), Qwen3.5-4B (30.71%), xLAM-2-1b (29.81%), xLAM-2-3b (40.88%).

**예비 관찰**: BFCL 상위 xLAM 계열이 AML-Bench에서는 중위권 (xLAM-2-32b: AML 3위 / BFCL 1위; xLAM-2-70b: AML 33위 / BFCL 2위) — 상관관계가 낮아 AML-Bench의 domain-specificity 뒷받침.

### 6. Excluded Models (vLLM incompatible / OOM)

| Model | Reason |
|-------|--------|
| gpt-oss-120b | OOM (bf16 240GB, exceeds 2×H100 80GB) |
| HyperCLOVAX-SEED-Think-14B/32B | `HCXVisionV2ForCausalLM` architecture unsupported |
| Solar-Open-100B | bf16 205GB, TP=2 insufficient |
| Llama-4-Scout-17B-16E | MoE 109B total (~218GB bf16), bitsandbytes TP=2 incompatible |
| gemma-3-12b/27b (tool-calling) | tool-call parser incompatibility (pythonic parser) |
| EXAONE-Deep-7.8B/32B | Thinking architecture incompatible with tool-call parsing |
| Phi-4-mini-reasoning | Reasoning model incompatible with tool-call parsing |

---

## Evaluated Models (29 models, 12 families)

| Family | Models | Parameters | Runtime |
|--------|--------|------------|---------|
| Qwen 3 | Qwen3-4B-Instruct, Qwen3-4B-Thinking, Qwen3-8B, Qwen3-30B-Instruct, Qwen3-30B-Thinking, Qwen3-Coder-30B | 4B–30B | vLLM |
| Qwen 3.5 | Qwen3.5-0.8B, 2B, 4B, 9B, 27B (think/nothink each) | 0.8B–27B | vLLM |
| Qwen 2.5 | Qwen2.5-1.5B-Instruct | 1.5B | vLLM |
| Salesforce xLAM | xLAM-2-1b, 3b, 8b, 32b, 70b | 1B–70B | vLLM |
| Kakao kanana | kanana-2-30b-instruct, kanana-2-30b-thinking (think/nothink) | 30B | vLLM |
| Meta Llama | Llama-3.2-1B, 3B, Llama-3.1-8B, Llama-3.3-70B | 1B–70B | vLLM |
| Mistral | Ministral-3-3B, 8B, 14B, Mistral-Small-24B, Mistral-Nemo-12B | 3B–24B | vLLM |
| LG AI EXAONE | EXAONE-4.0-1.2B, EXAONE-4.0-32B | 1.2B–32B | vLLM |
| OpenAI gpt-oss | gpt-oss-20b (think/nothink) | 20B | vLLM |
| SKT A.X | A.X-4.0, A.X-4.0-Light | - | vLLM |
| Zhipu GLM | GLM-4.7-Flash | - | vLLM |
| NousResearch | Hermes-3-Llama-3.1-8B | 8B | vLLM |

## Evaluation Metrics

### Single-turn (1,258 cases)
- **Composite Score** (s ∈ [0, 1]): weighted combination of tool selection and parameter accuracy
- **Tool Selection Accuracy** (primary_tool_hit_rate): fraction of cases with correct primary tool
- **Parameter Accuracy** (avg_param_accuracy): key-value match accuracy for correctly selected tools

### Multi-turn STR (50 scenarios)
- **Average Score** (avg_score): per-turn tool selection + parameter accuracy averaged over all turns
- **Scenario Complete Rate**: fraction of scenarios where all required tool calls were completed
- **Context Accuracy**: ability to maintain conversation context across turns

## Citation

```bibtex
@inproceedings{lim2026amlbench,
  title={AML-Bench: A Function Calling Benchmark for Anti-Money Laundering Agents},
  author={Lim, Seonkyu and Hong, Gwangui and Lim, KyungTae},
  booktitle={Advances in Neural Information Processing Systems (NeurIPS), Datasets and Benchmarks Track},
  year={2026}
}
```

> 제출 예정: NeurIPS 2026 Evaluations & Datasets (E&D) Track (Abstract 2026-05-05, Full 2026-05-06, double-blind).

## License

This benchmark is released for research purposes.
