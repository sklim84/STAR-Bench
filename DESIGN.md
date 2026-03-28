# 연구 설계 문서 — AML Assistant 에이전트 성능 평가

> 이 문서는 AML Assistant 프로젝트의 연구 목적, 도메인 전제, 시스템 설계, 가설, 벤치마크 구조를
> 단일 문서로 정리한다. 코드 개발 지침은 `../CLAUDE.md` 참조.

---

## 0. 프로젝트 개요 — 5단계 파이프라인

```
_docs/ (AML 규제 자료 8종 PDF)
    ↓  [도메인 지식 추출: 업무 영역·용어·보고서 구조]
src/features/ + _pages/ (웹서비스 8개 기능)
    ↓  [에이전트 도구화: function calling 스키마 정의]
src/features/agent.py (23개 도구, 최대 5라운드 tool calling)
    ↓  [성능 평가: 한국어 자연어 → 도구 선택 + 파라미터 추출]
_paper/benchmarks/ (1,258건 벤치마크 케이스)
    ↓  [LLM 비교: GPT·Claude·Qwen·Kanana·Mistral·Phi 등 다중 모델 정량 비교]
_paper/ (논문)
```

---

## 1. 연구 배경 및 문제 정의

### 1.1 배경

금융기관 AML(자금세탁방지) 담당자는 대규모 거래 데이터에서 의심거래를 선별하고,
STR(의심거래보고서)을 작성하는 정형화된 분석 업무를 수행한다.
이 업무는 반복적이고 규칙 기반이지만, 분석 대상 데이터 규모(수백만 건)와
한국어 규제 문서 해석 능력을 동시에 요구한다.

### 1.2 연구 질문

> **LLM 에이전트가 한국어 자연어 지시를 받아 AML 분석 도구를 정확히 선택하고
> 파라미터를 추출할 수 있는가?**
>
> — 분석 결과의 내용·정확성이 아닌, **도구 선택과 파라미터 추출의 정확도**를 평가 대상으로 한다.

### 1.3 기존 벤치마크와의 차별점

| 기준 | BFCL (Berkeley) | OrchestrationBench | 본 연구 |
|------|-----------------|-------------------|---------|
| 도메인 | 범용 | 범용 | AML 금융 특화 |
| 언어 | 영어 | 영어 | **한국어** |
| 도구 수 | 수백 | 수십 | 23개 (도메인 밀도 높음) |
| 케이스 수 | 5,551건 | 1,436건 | **1,258건** |
| 평가 단위 | 단일 호출 | 체이닝 | 단일 + 체이닝 혼합 |

---

## 2. 도메인 전제 — AML 업무 범위

`_docs/` 규제 자료 8종에서 도출된 AML 담당자의 핵심 업무 영역:

| 업무 영역 | 설명 | 근거 자료 |
|-----------|------|---------|
| **거래 조회·분석** | 조건 기반 의심거래 필터링, 기간별/유형별 통계 집계, 시계열 추세 분석 | 실무 5편 (STR 제도) |
| **네트워크 분석** | 자금 흐름 추적, 레이어링·순환거래·대포통장 탐지, 스머핑·기관간 흐름 분석 | 실무 1~2편 (위험평가) |
| **위험 평가** | 거래별 이상거래 확률 예측, 계좌 행위 위험도 평가, 고위험 계좌·기관 식별 | 실무 2편 (위험평가제도) |
| **CTR·모니터링** | 고액현금거래보고 대상 탐지, 분할거래 패턴, 규칙 기반 모니터링 | 실무 4편 (CTR 제도) |
| **STR 작성** | 혐의거래보고서(I~VII 섹션) 초안 자동 생성 | 실무 5편 + STR 서식 |

이 5개 업무 영역은 아래 23개 도구로 매핑된다.

---

## 3. 시스템 설계 전제

### 3.1 에이전트 아키텍처

- **모델**: 단일 LLM + OpenAI function calling (기준 모델: `gpt-4o-mini`)
- **최대 라운드**: 5라운드 tool calling (단일 요청 내 다중 도구 순차 실행)
- **언어**: 사용자 입력은 한국어 자연어; 에이전트가 도구 선택·파라미터 추출 자율 수행

### 3.2 23개 도구와 업무 영역 매핑

| # | 도구명 | 업무 영역 | 설명 |
|---|--------|---------|------|
| 1 | `query_transactions` | 거래 조회 | 조건 기반 거래 레코드 필터링 |
| 2 | `get_statistics` | 거래 분석 | 전체 거래 통계·이상거래 분포 조회 |
| 3 | `get_fraud_type_summary` | 거래 분석 | 이상거래 유형별 상세 통계 |
| 4 | `compare_periods` | 거래 분석 | 두 기간 거래 지표 비교 |
| 5 | `get_institution_report` | 거래 분석 | 금융기관별 거래 현황 보고 |
| 6 | `rank_risky_transactions` | 위험 평가 | 고위험 거래 순위 조회 |
| 7 | `predict_fraud` | 위험 평가 | XGBoost 모델 기반 이상거래 확률 예측 |
| 8 | `get_account_profile` | 위험 평가 | 출금계좌별 거래 프로파일 조회 |
| 9 | `analyze_network` | 네트워크 분석 | 계좌 거래 네트워크 중심성·연결 분석 |
| 10 | `detect_aml_patterns` | 네트워크 분석 | 순환거래·레이어링·대포통장 패턴 탐지 |
| 11 | `generate_str` | STR 작성 | I~VII 섹션 혐의거래보고서 초안 생성 |
| 12 | `detect_ctr_candidates` | CTR·모니터링 | CTR 대상 고액거래 및 분할거래 탐지 |
| 13 | `score_account_risk` | 위험 평가 | 5개 행위 지표 기반 계좌 위험도 0~100점 산출 |
| 14 | `detect_monitoring_alerts` | CTR·모니터링 | 5개 규칙 기반 모니터링 알림 탐지 |
| 15 | `detect_dormant_reactivation` | CTR·모니터링 | 장기 휴면 계좌 재활성화 탐지 |
| 16 | `detect_smurfing_network` | 네트워크 분석 | 자금 수집/분산(스머핑) 패턴 탐지 |
| 17 | `get_trend_analysis` | 거래 분석 | 월별/분기별 시계열 추세 분석 |
| 18 | `analyze_channel_risk` | 위험 평가 | 채널(매체)별 위험도 분석 |
| 19 | `get_receiving_account_profile` | 위험 평가 | 입금계좌별 거래 프로파일 조회 |
| 20 | `analyze_cross_institution_flow` | 네트워크 분석 | 기관간 자금 흐름 및 이상거래율 분석 |
| 21 | `lookup_fiu_reference_types` | STR 작성 | FIU 의심거래 참고유형 검색 |
| 22 | `validate_str_fields` | STR 작성 | STR 필수 필드 점검 |
| 23 | `get_aml_glossary` | STR 작성 | AML 용어 정의 조회 |

### 3.3 평가 범위

- **IN**: 자연어 → 도구 선택 정확도, 파라미터 추출 정확도
- **OUT**: 도구 실행 결과의 내용 품질, 법적·규제 적합성

### 3.4 데이터

- **출처**: HOFINET 전자금융공동망 이상거래탐지 데이터셋
- **규모**: 4,732,130건 (2021 Q4 ~ 2024 Q4, 13분기)
- **클래스 불균형**: 325.6:1 (정상 99.69% / 이상 0.31%)
- **이상거래 유형**: 1=자금세탁, 2=신규거래처, 3=대포통장, 4=보이스피싱, 5=불법도박, 6=유사수신, 7=기타

---

## 4. 핵심 가설

| 가설 | 내용 | 검증 지표 | 합격 임계값 |
|------|------|---------|-----------|
| H1 | 단일 도구 과제에서 LLM이 정답 도구를 선택한다 | primary_tool_hit_rate | ≥ 0.80 |
| H2 | 다중 도구 체이닝 과제에서 필요 도구를 모두 호출한다 | avg_tool_recall | ≥ 0.65 |
| H3 | Irrelevance 질문에서 도구를 잘못 호출하지 않는다 | irrelevance_accuracy | ≥ 0.90 |
| H4 | 도구 파라미터를 정확히 추출한다 | avg_param_accuracy | ≥ 0.75 |
| H5 | 모델 크기·계열에 따라 성능 차이가 유의미하게 나타난다 | 모델 간 score 비교 | — |

**임계값 근거**: `_paper/benchmarks/bench_agent_behavior.py`의 `_THRESHOLDS` 딕셔너리와 동기화.

```
_THRESHOLDS = {
    "get_statistics":          0.85,   # H1: 단순 통계 조회, 미끼 도구 없음 → 높게 설정
    "query_transactions":      0.75,   # H1+H4: 다양한 필터 파라미터 조합
    "analyze_network":         0.75,   # H1+H4: 계좌 식별자 추출 난이도
    "predict_fraud":           0.80,   # H1: 예측 도구, 유사 도구(rank) 혼동 위험
    "detect_aml_patterns":     0.75,   # H1: 패턴 탐지, analyze_network와 혼동 위험
    "multi_tool":              0.65,   # H2: 다중 도구 체이닝, 가장 낮은 임계값
    "get_account_profile":     0.80,   # H1+H4: 계좌 식별자 정확 추출
    "get_fraud_type_summary":  0.80,   # H1: get_statistics와 혼동 위험
    "compare_periods":         0.80,   # H1+H4: 날짜 파라미터 2개 추출
    "get_institution_report":  0.80,   # H1+H4: 기관 코드 추출
    "rank_risky_transactions": 0.75,   # H1+H4: limit 파라미터 추출
    "detect_ctr_candidates":   0.80,   # H1+H4: mode 파라미터 추출
    "score_account_risk":      0.80,   # H1+H4: account_id 추출
    "detect_monitoring_alerts": 0.75,  # H1+H4: rule_id 추출, 간접 표현 다수
    "detect_dormant_reactivation": 0.75, # H1: 유사 도구 혼동 위험 (monitoring)
    "detect_smurfing_network": 0.75,   # H1+H4: direction 파라미터 추출
    "get_trend_analysis":      0.80,   # H1+H4: unit/metric 파라미터 조합
    "analyze_channel_risk":    0.75,   # H1: 단순 호출, 파라미터 적음
    "get_receiving_account_profile": 0.80, # H1+H4: account_id, 출금/입금 혼동
    "analyze_cross_institution_flow": 0.75, # H1: 기관간 분석 유도
}
```

---

## 5. 범위와 한계

### IN (평가 범위)

- 한국어 자연어 → 도구 선택 + 파라미터 추출 (싱글턴 평가)
- 최대 3-hop 다중 도구 체이닝 (multi_tool 카테고리)
- Irrelevance 탐지 (도구 미호출이 정답인 시나리오)
- STR 초안 생성 도구(`generate_str`)의 파라미터 추출 정확도

### OUT (평가 제외)

- 실시간 스트리밍·모니터링
- 모델 재학습 또는 파인튜닝
- 외부 시스템(KoFIU, SWIFT 등) 연동
- 분석 결과의 법적·규제 적합성 보장
- 에이전트 응답 품질(생성된 STR 내용, 거래 해석의 전문성)

### 비교 대상 LLM

| 계열 | 모델 | 파라미터 규모 | 실행 환경 | vLLM 파서 |
|------|------|-------------|---------|----------|
| GPT-OSS | gpt-oss-20b, gpt-oss-120b | 20B, 120B | vLLM 로컬 | openai |
| Qwen3 | Qwen3-4B-Instruct, Qwen3-4B-Thinking | 4B | vLLM 로컬 | qwen3_xml |
| Mistral | Mistral-Small-3.2-24B-Instruct | 24B | vLLM 로컬 | mistral |
| Llama | Llama-3.1-8B-Instruct | 8B | vLLM 로컬 | llama3_json |
| Kanana | kanana-1.5-2.1b, 8b, 15.7b-a3b | 2.1B, 8B, 15.7B(3B active) | vLLM 로컬 | functionary (커스텀) |
| EXAONE | EXAONE-3.5-7.8B, 32B | 7.8B, 32B | vLLM 로컬 | hermes |
| Gemma | gemma-3-12b-it, 27b-it | 12B, 27B | vLLM 로컬 | pythonic→hermes |
| Granite | granite-3.1-8b-instruct | 8B | vLLM 로컬 | granite→hermes |
| Phi | Phi-4-mini-instruct | 14B | vLLM 로컬 | phi4_mini_json |

> Thinking 모델은 think/nothink 두 가지 설정으로 실험. 총 18개 모델 구성 (8개 계열, 14개 모델).
> EXAONE, Gemma, Granite는 초기 파서 설정 오류로 재실험 진행 중 (hermes 파서로 변경).

---

## 6. 벤치마크 구조

### 6.1 방법론

- BFCL(Berkeley Function-Calling Leaderboard) + OrchestrationBench 방법론 채택
- 참고 구현: `_paper/ref_notes.md` (KA-008-KFInABen 프로젝트)
- 참조 논문 PDF: `_paper/references/` (BFCL ICML 2025, OrchestrationBench ICLR 2026)

#### 참조 벤치마크 규모 비교

| 벤치마크 | 총 케이스 | 도구 수 | 특이사항 |
|----------|---------|--------|---------|
| BFCL V3 (ICML 2025) | **5,551건** | 수백 | 단일·다중 턴, 15개 언어, 40개 도메인 |
| OrchestrationBench (ICLR 2026) | **1,436건** (한국어 730) | ~100 | 17개 도메인, 한/영 이중언어 |
| KFinEval-Pilot (2025) | **1,145건** | — | 한국어 금융 특화, 11개 LLM 비교 |
| **본 연구 (v1)** | 142건 | 11 | AML 특화, 도구당 ~13건 |
| **본 연구 (v2)** | 330건 | 11 | 도구당 30건 |
| **본 연구 (v3)** | 420건 | 14 | 도구당 30건, CTR/위험평가/모니터링 추가 |
| **본 연구 (v4)** | 1,036건 | 20 | 도구당 50~65건, 20개 카테고리 |
| **본 연구 (v6 현재)** | **1,258건** | **23** | v5 + AML 참조 3개(lookup_fiu, validate_str, get_aml_glossary) 19건 |

> **현황**: v6에서 총 1,258건. multi_tool 100건, 단일 도구 19개 카테고리 58~66건, missing_parameters 25건, AML 참조 3개 카테고리 19건.

### 6.2 케이스 구성 목표

#### 현재 구현 (v5 — P1 고도화 반영)

| 구분 | 케이스 수 | 설명 |
|------|---------|------|
| 단일 도구 (19개 카테고리) | 1,089건 | 도구당 58~66건 (easy/medium/hard/irrelevance) |
| 다중 도구 (multi_tool) | 100건 | 2~3개 도구 체이닝, 23개 도구 조합 |
| Missing Parameters | 25건 | 정보 부족 시 도구 미호출(질문 유도) 평가 |
| AML 참조 (3개 카테고리) | 19건 | lookup_fiu 8건, validate_str 3건, get_aml_glossary 8건 |
| **합계** | **1,258건** | normal 1,099건 + irrelevance 134건 + missing_params 25건 |

#### 난이도 분포 (도구당 50건 기준)

| 난이도 | 비율 | 설명 |
|--------|------|------|
| easy | ~40% (20건) | 직접 지시형 (도구명·파라미터 명시적) |
| medium | ~36% (18건) | 맥락 내 추론형 (간접 표현, 파라미터 변환 필요) |
| hard | ~12% (6건) | 비즈니스 언어형 (업무 맥락에서 도구 추론) |
| irrelevance | ~12% (6건) | 도구 미호출이 정답 (도메인 키워드 포함) |

케이스 다양화 전략:
- 동일 도구에 대해 표현 방식(직접 지시형/맥락 내 추론형/비즈니스 언어형) 3종 변형
- 파라미터 값 분포: 경계값(최소·최대), 빈번값, 희소값 균형 포함
- Irrelevance: 도메인 내 관련 키워드를 포함하지만 도구 호출이 불필요한 시나리오 (BFCL 기준 ~13%)

### 6.3 도구 3분류 체계

| 분류 | 기호 | 설계 의도 |
|------|------|---------|
| 정답 도구 | ① | 핵심 업무 목적을 충족하는 필수 호출 |
| 유사 기능 도구 | ② | 동일 유형이나 대상·범위·조건이 달라 목적 미충족 |
| 인접·미끼 도구 | ③ | 동일 도메인 키워드 공유, 다른 행동 수행 |

**미끼 도구 설계 원칙**: ③은 ①의 반환 데이터 부분집합이어선 안 됨.
동일 파라미터를 받더라도 반환 목적이 근본적으로 달라야 함.

### 6.4 평가 지표

| 지표 | 설명 |
|------|------|
| `primary_tool_hit_rate` | 정답 도구를 1순위로 호출한 비율 (H1) |
| `avg_tool_recall` | 다중 도구 과제에서 필요 도구 전체 호출 비율 (H2) |
| `irrelevance_accuracy` | 도구 미호출이 정답인 케이스에서 미호출 비율 (H3) |
| `avg_param_accuracy` | GT 필수 파라미터 중 값 일치 비율 (H4) |
| `avg_param_key_accuracy` | 파라미터 키 명칭 정확도 |
| `avg_order_score` | 다중 도구 실행 순서 정확도 |

### 6.5 실행 방법

```bash
# mock 기반 (빠름, API 키 불필요)
pytest _paper/benchmarks/ -v -m "not integration and not memgraph"

# 단일 모델 벤치마크 (API 모델)
python _paper/benchmarks/run_multi_model.py --models gpt-4o-mini --checkpoint --output _paper/results/
python _paper/benchmarks/run_multi_model.py --models claude-haiku-4-5-20251001 --output _paper/results/

# vLLM 로컬 모델 자동화 (GPU 서버, 11개 모델 그룹 순차 실행)
bash _paper/benchmarks/scripts/run_all_models.sh

# 기존 결과로 비교 리포트만
python _paper/benchmarks/run_multi_model.py --comparison-only --output _paper/results/
```

> vLLM 자동화 스크립트는 모델별 vLLM 서버 기동 → 1,258건 벤치마크 → 서버 종료를 반복한다.
> 모델별 tool-call-parser 설정(hermes, mistral, phi4_mini_json 등)과 커스텀 플러그인(Kanana용 functionary_v3_llama_31)을 자동 적용한다.

---

## 7. 선행 실험 결과 (Pilot Study)

### 7.1 KFinABen 파일럿 실험 (2026-02-23)

AML 벤치마크 설계 전, 전자금융공동망(KFTC) 이체거래 조회 도메인에서
동일한 방법론으로 파일럿 실험을 수행했다. 결과는 `_paper/results/outdated/`에 보존.

**실험 조건**: 36건, 5개 서브도메인, 4개 모델

| 모델 | 함수 정확도 | 파라미터 정확도 | 종합 정확도 | 환각 파라미터 | 평균 응답시간 |
|------|----------|-------------|----------|-----------|----------|
| gpt-4o-mini | **100.0%** | **97.2%** | **94.4%** | 0건 | **1.6s** |
| qwen2.5:1.5b | 80.6% | 86.6% | 75.0% | 9건 | 14.1s |
| qwen2.5:0.5b | 72.2% | 74.5% | 47.2% | 11건 | 8.6s |
| qwen3:0.6b | 69.4% | 69.9% | 47.2% | 6건 | 41.7s |

**주요 시사점**:
1. **GPT와 Qwen의 성능 격차**: gpt-4o-mini는 함수 선택에서 완벽한 정확도를 보인 반면, Qwen 모델들은 69~80% 수준에 머물렀다.
2. **파라미터 추출 vs 함수 선택**: qwen2.5:0.5b와 qwen3:0.6b는 함수 선택 정확도(72%, 69%)보다 종합 정확도(47%)가 크게 낮아 파라미터 환각이 심각했다.
3. **모델 크기 효과**: qwen2.5 계열에서 1.5b가 0.5b 대비 종합 정확도 약 28pp 우수. 그러나 qwen3-0.6b는 최신 버전임에도 qwen2.5-0.5b와 동등한 수준으로, 소형 모델에서 버전 업그레이드 효과가 제한적임을 시사.
4. **응답 시간**: Qwen 로컬 모델은 GPT 대비 5~26배 느림. 특히 qwen3-0.6b는 41.7s로 실무 적용 한계 노출.

### 7.2 현재 벤치마크 상태 (v6, 2026-03-06)

23개 도구, 1,258건 케이스, 18개 모델 구성(14개 모델, 8개 계열). mock 테스트 전체 통과.

```
pytest _paper/benchmarks/ -v -m "not integration and not memgraph"  → 54 passed
pytest tests/ -v                                                     → 779 passed
```

**다중 모델 벤치마크 결과** (2026-03-06, 18개 구성 완료):

| 순위 | 모델 | 종합점수 | 도구% | 파라% | 비고 |
|------|------|---------|------|------|------|
| 1 | Qwen3-4B-Thinking (think) | 0.927 | 94.7% | 90.0% | |
| 2 | Qwen3-4B-Thinking (nothink) | 0.927 | 94.7% | 90.1% | |
| 3 | gpt-oss-120b (think) | 0.912 | 92.3% | 92.5% | |
| 4 | gpt-oss-120b (nothink) | 0.909 | 92.1% | 92.0% | |
| 5 | Mistral-Small-3.2-24B | 0.900 | 89.5% | 89.5% | |
| 6 | gpt-oss-20b (nothink) | 0.892 | 89.6% | 88.4% | |
| 7 | gpt-oss-20b (think) | 0.891 | 89.5% | 88.4% | |
| 8 | Qwen3-4B-Instruct | 0.887 | 90.5% | 88.1% | |
| 9 | Llama-3.1-8B-Instruct | 0.809 | 81.9% | 79.1% | |
| 10 | Kanana-1.5-8B | 0.771 | 74.6% | 73.0% | |
| 11 | Kanana-1.5-15.7B | 0.717 | 66.2% | 68.5% | |
| 12 | Granite-3.1-8B | 0.326 | 12.9% | 23.4% | 파서 호환 문제 |
| 13 | EXAONE-3.5-7.8B | 0.325 | 12.6% | 23.4% | 파서 호환 문제 |
| 14 | Gemma-3-12B | 0.325 | 12.6% | 23.4% | 파서 호환 문제 |
| 15 | Gemma-3-27B | 0.325 | 12.6% | 23.4% | 파서 호환 문제 |
| 16 | Phi-4-mini | 0.225 | 8.3% | 13.8% | 323건 parse_fail |
| 17 | Kanana-1.5-2.1B | 0.224 | 22.1% | 21.4% | 898건 parse_fail |
| 18 | EXAONE-3.5-32B | 0.072 | 2.1% | 6.5% | 981건 connection_error |

**주요 발견**:
- 상위 8개 모델(Qwen3, gpt-oss, Mistral)은 H1(도구선택 ≥80%) 및 H4(파라미터 ≥75%) 임계값을 충족
- Llama-3.1-8B은 H1 충족(81.9%), H4 근접(79.1%)으로 준수한 성능
- Kanana 8B/15.7B는 한국어 모델로서 도구 호출 지원하나 상위 모델 대비 성능 격차
- Granite, EXAONE, Gemma, Phi는 vLLM tool-call parser 호환 문제로 tool_calls 추출 실패 → 파서 변경 재실험 진행 중

**미완료 실험**:
- Llama-3.3-70B, Llama-4-Scout: TP=2(2xGPU) 필요, 단일 GPU 할당 오류로 미실행
- EXAONE/Gemma/Granite: hermes 파서로 재실험 진행 중 (2026-03-06)

---

## 8. 기대 기여

| 기여 | 설명 |
|------|------|
| **도메인 특화 벤치마크** | AML 업무 특화 LLM function calling 벤치마크 최초 공개 |
| **한국어 금융 평가** | 한국어 금융 도메인에서 주요 LLM 성능 정량 비교 데이터셋 |
| **설계 가이드라인** | 에이전트 기반 AML 보조 시스템 구축을 위한 도구 설계 원칙 |
| **오픈소스 가용성** | Qwen3·Kanana·Mistral·Llama·EXAONE·Gemma·Granite·gpt-oss 등 8개 계열 오픈소스 LLM의 AML 도메인 적용 가능성 검토 |

---

*최종 수정: 2026-03-06 (v6: 도구 23개, 벤치마크 1,258건, 18개 모델 구성 비교 실험 완료)*
