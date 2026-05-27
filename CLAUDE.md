# CLAUDE.md — STAR-Bench

STAR-Bench(논문 표기 `$TAR Bench`): AML 에이전트 function-calling 벤치마크. 케이스·평가 엔진·실험 결과를 담는 핵심 아티팩트 저장소.

## 구조

```
benchmarks/            — 싱글턴 KR 벤치마크 케이스 (1,258건, cases_<tool>.json 18개)
benchmarks_en/         — 영문 번역 케이스 (KR-EN ablation, 1,258건, 16개)
benchmarks_multiturn/  — 멀티턴 STR 시나리오 (50개, cases_str_workflow.json)
_experiments/          — 벤치마크 실행 코드 + 결과
  scripts/
    benchmark.py           — single-turn 벤치마크 엔진 (3개 프로바이더 레지스트리)
    benchmark_multiturn.py — 멀티턴 STR 벤치마크
    tools_en.py            — 영문 도구 정의 + SYSTEM_PROMPT_EN (--tools-lang en ablation)
    run_benchmark.sh       — per-GPU runner (S1_A/S1_B/S2_TP*/S2_LARGE_* 분담)
    run_master.sh          — 마스터 오케스트레이터 (--server 1|2, KR/EN/MT 순차)
    tool_chat_template_phi4_mini.jinja — Phi-4-mini-instruct FC 강제 chat template
    kanana_tool_calls/     — vLLM 커스텀 파서 플러그인
  results_kr/              — KR phase 결과 (eval/, checkpoint/, comparison_*.xlsx)
  results_en/              — EN phase 결과
  results_mt/              — MT phase 결과
  bfcl_results/            — RQ6 BFCL 직접 실행 결과 (score/<model>/)
  analysis/                — 후처리 분석 산출물
  logs/                    — 실행 로그
```

> 세션 핸드오프(현재 활성 작업 + 핵심 영구 규약)는 `.claude/SESSION_HANDOFF.md` 참조.

벤치마크 케이스 JSON 구조: `[{"question": "...", "expected_tool_call": {"name": "...", "arguments": {...}}}]`

## Commands

`_experiments`가 repo 루트에 있으므로 **`PYTHONPATH=.`**(repo 루트) 기준이다(구 모노repo의 `PYTHONPATH=_paper`에서 변경됨).

```bash
# 단일 모델 KR
PYTHONPATH=. python -m _experiments.scripts.benchmark --models Qwen/Qwen3-8B --output _experiments/results_kr/ --checkpoint --resume

# 영문 ablation (--cases-dir 추가)
PYTHONPATH=. python -m _experiments.scripts.benchmark --models Qwen/Qwen3-8B --output _experiments/results_en/ --cases-dir benchmarks_en/ --checkpoint --resume

# 멀티턴 STR 벤치마크
PYTHONPATH=. python -m _experiments.scripts.benchmark_multiturn --models Qwen/Qwen3-8B --output _experiments/results_mt/

# vLLM 자동화 (GPU 서버, 24-model 분담)
bash _experiments/scripts/run_benchmark.sh --gpu 0 --port 11434 --group S1_A --mode kr
nohup bash _experiments/scripts/run_master.sh --server 1 --modes kr,en,mt > master_s1.log 2>&1 &
BENCH_MAX_TOTAL=5 bash _experiments/scripts/run_benchmark.sh --gpu 0 --port 11434 --group SMOKE --mode kr  # 스모크
```

> ⚠️ 모노repo 분리 직후이므로, `run_*.sh` 등 스크립트 내부에 `_paper/` 접두 경로가 하드코딩돼 있으면 repo 루트 기준으로 정정해야 한다.

**환경 변수**: `OPENAI_API_KEY`(OpenAI 벤치마크), `ANTHROPIC_API_KEY`(Anthropic 벤치마크).

## 다중 모델 벤치마크 (`_experiments/scripts/benchmark.py`)

3개 프로바이더 레지스트리 (think/nothink 변형 분리 entry로 등록). 프로바이더별 주의사항:
- **OpenAI**: gpt-4o-mini, gpt-5-mini. 추론 모델(gpt-5, o1, o3, o4)은 `temperature=0` 미지원 → 자동 스킵. `max_completion_tokens` 사용 (not `max_tokens`)
- **Anthropic**: claude-haiku-4-5, claude-sonnet-4-5. 도구 스키마의 한글 프로퍼티 키를 영문으로 변환 필요 (`_KO_EN_KEY_MAP`). 응답의 영문 키는 한글로 역변환 (`_EN_KO_KEY_MAP`)
- **vLLM**: Qwen3/3.5, Kanana, EXAONE, Mistral, gpt-oss, A.X 등. 모델별 tool-call-parser 지정 필요 (hermes, mistral, qwen3_xml, qwen3_coder, llama3_json, xlam, glm47, openai). Kanana는 커스텀 파서 플러그인 사용. Thinking 모델은 think/nothink 두 entry로 ablation 분리 등록

**Native FC 모드**: vLLM tool-call-parser + OpenAI/Anthropic native `tools` 필드만 사용 (Prompting mode 미사용). 시스템 프롬프트는 도구 목록 중복 없이 워크플로우/STR 가이드/Data Schema만 포함.

**스케줄링** (24-model 서버 분담):
- Server 1 (2× H100): S1_A (GPU 0, 6 모델) + S1_B (GPU 1, 5 모델) 병렬
- Server 2 (6× H100): TP=4 1 (gpt-oss-120b) + TP=2 3 (70B+ 모델 페어) + Single-GPU Large 9 모델
- thinking 변형: 5 핵심 페어만 별도 등록 (Qwen3.5-4B/27B, gpt-oss-20b/120b, kanana-2-think)

**vLLM 자동화** (`_experiments/scripts/run_master.sh`):
- 마스터: `--server 1|2 --modes kr,en,mt`. 서버1은 S1_A+S1_B 병렬, 서버2는 α(TP=4+L1+L2) → β(TP=2 3 pair) → γ(L3) 단계별 진행
- 옵션: `--skip-tp2` `--skip-tp4` `--skip-thinking`
- 단일 그룹: `bash run_benchmark.sh --gpu <id> --port <port> --group <S1_A|S1_B|S2_TP4|S2_TP2_A|S2_LARGE_L1|...> --mode <kr|en|mt>`
- 환경변수: `BENCH_MAX_TOTAL=5` (스모크), `BENCH_SKIP_THINK=1` (think 변형 제외)

## 관련 저장소

- **STAR-Bench-paper**: 논문 원고. `figures/generate_*.py`가 본 repo의 `_experiments/` 결과에 의존한다.
- **STAR-Bench-Web**: 23개 도구가 도출된 레퍼런스 AML 플랫폼.
