# H200 금키 재실행 오케스트레이션

2026-09-14 에 H200(공저자 홍광의 님과 공유하는 4×H200 NVL 장비)에서 금키 재실행
28설정 중 20설정을 돌릴 때 실제로 쓴 스크립트다. 웹콘솔 PTY 를 통해 원격 실행했다.

| 파일 | 역할 |
|---|---|
| `h200_pty_driver.py` | 웹콘솔 PTY 폴링 드라이버. 접속 정보는 환경변수로 받는다 |
| `goldfix_h200.sh` | 4레인 본 실행 (laneA~laneD) |
| `goldfix_moe.sh` · `goldfix_moe2.sh` | MoE 따라잡기 1·2차. 2차는 flashinfer 캐시를 지운다 |
| `goldfix_idle.sh` · `idle2.sh` | 유휴 GPU 투입 |
| `l1guard.sh` | 레인이 중복 모델로 넘어가기 직전 차단하는 감시자 |
| `patch_gf.py` · `patch_gf2.py` · `patch_gf3.py` | `run_benchmark.sh` 사본에 임시 그룹을 주입 |
| `finish_all.sh` | GPU 가 비는 대로 남은 설정을 물리는 큐 |

## 알아둘 것

**접속 정보는 코드에 없다.** `H200_BASE`·`H200_TOKEN`·`H200_COOKIE_JAR` 를 환경변수로
준다. Cloudflare 임시 터널이라 재시작마다 주소와 토큰이 바뀐다.

**경로가 그 장비에 고정돼 있다.** 셸 스크립트들은 `/home/mlp/hgyoo/bubble/codex/star-bench`
를 그대로 쓴다. 다른 장비에서 쓰려면 `R`·`VENV`·`HF_HOME` 을 고친다. 당시 실행을 그대로
남기려고 손대지 않았다.

**`run_benchmark.sh` 를 직접 고치지 않는다.** bash 는 스크립트를 실행하면서 읽으므로
돌고 있는 레인이 깨진다. `patch_gf*.py` 가 같은 디렉터리에 사본을 만들어 그것만 고치는
이유다.

**MoE·Qwen3.5/3.6 은 flashinfer JIT 캐시에 걸린다.** `CUDA_HOME` 이 12.x 를 가리키지
않으면 `build.ninja` 에 `cuda_home = /usr` 가 박혀 CUDA 11.5 가 불리고 `compute_90a`
빌드가 깨진다. 포트는 먼저 열려 "서버 준비 완료"가 찍히므로 증상이 감춰진다.
`goldfix_moe2.sh` 가 그 해법(환경변수 고정 + 캐시 삭제)을 담고 있다.

케이스 목록은 `_experiments/rerun_gold_fix/case_ids.txt` 를 쓴다(여기 사본을 두지 않는다).
실행 로그는 `.gitignore` 의 `**/logs/` 정책에 따라 추적하지 않는다.
