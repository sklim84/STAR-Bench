# OpenRouter 한국어 도구 스키마 실험 — 실행 드라이버

`benchmark_openrouter.py` 를 실제로 어떤 인자로 돌렸는지 남긴 셸 스크립트다.
`run_benchmark.sh` 와 달리 vLLM 을 띄우지 않고 OpenRouter API 만 쓴다.

| 스크립트 | 내용 |
|---|---|
| `or_kr2arm.sh` | KR 도구 스키마 × 두 팔(KR 질의 / EN 질의). 병렬 10 |
| `or_extra.sh` | 추가 6설정 — qwen3.6-35b-a3b, llama-3.2-3b, gpt-oss 120b/20b(T/NT). 병렬 6 |
| `or_2x2_driver.sh` | 2×2 네 팔(질의 언어 × 도구 언어) 전체 실행 |
| `or_extra_guard.sh` | 감시자 |

API 키는 저장소에 없다. 세 스크립트 모두 `.env` 의 `OPENROUTER_API_KEY` 를 환경변수로 읽는다.

경로도 저장소에 없다. 저장소 루트는 스크립트 위치에서 구하고(`run_benchmark.sh`·
`run_master.sh` 와 같은 방식), 인터프리터는 `$BENCH_PYTHON`(기본 `python3`), 병렬도는
`$BENCH_CONCURRENCY`, 감시자의 로그·pid 경로는 `$OR_RUN_DIR`·`$OR_LOG`·`$OR_PIDFILE` 로 받는다.

```
BENCH_PYTHON=.venv-eval/bin/python bash _experiments/scripts/openrouter/or_kr2arm.sh
```

결과: `_experiments/results_or_kr_tools_kr/` (KR 질의) · `_experiments/results_or_en_tools_kr/` (EN 질의).
실행 로그는 `.gitignore` 의 `**/logs/` 정책에 따라 추적하지 않는다.
