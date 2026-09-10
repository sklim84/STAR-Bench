# H200 E2E 재실행 스크립트

`results_mt_{oracle,real}` 28설정을 DuckDB 락 없이 다시 돌리기 위해 쓴 스크립트다.
논문의 `run_oracle_vs_real.sh` 와 목적은 같으나, 가용 장비가 H100 클러스터가 아니라
H200 NVL 4장이어서 스케줄링과 환경 구성을 새로 짰다.

## 실행 순서

| 스크립트 | 역할 |
|---|---|
| `setup312.sh` | Python 3.12 에 논문 핀(vLLM 0.20.1 · torch 2.11.0 · transformers 5.7.0) 설치 |
| `fix_nccl.sh` | `nvidia-nccl-cu13` 제거 후 `cu12` 복원 — tensor-parallel 이 이것 없이는 뜨지 않는다 |
| `nccl_probe.sh` · `nccl_test.py` | GPU 2장 `all_reduce` 로 NCCL 동작 검증 |
| `dl_par.sh` · `dl_gated.sh` · `dl_gemma.sh` | 코호트 24개 모델 다운로드(병렬 3워커 / gated 별도) |
| `e2e_sched.sh` | 1단계 — 단일 GPU 모델 20개를 GPU 4장에 워커로 분배, 받는 대로 실행 |
| `run_phase2.sh` | 2단계 — tensor-parallel 이 필요한 대형 모델 순차 실행 |
| `e2e_analyze.py` · `check_lock.py` | 락·에러 집계와 45 부분집합 기준 재집계 |

## 이 환경에서 필요했던 우회

**PyPI 기본 휠을 쓸 수 없다.** vLLM·torch 모두 CUDA 13 빌드라 `libcudart.so.13` 을 요구하는데
드라이버가 12.8 이다. vLLM 은 `wheels.vllm.ai` 의 cu129, torch 계열은 cu128 을 쓴다.

**NCCL 도 같은 문제가 있다.** `nvidia-nccl-cu12` 와 `cu13` 이 `nvidia/nccl/lib/libnccl.so.2`
같은 경로를 공유해 cu13 이 덮어쓴다. 단일 GPU 는 NCCL 을 쓰지 않아 모델 19개가 멀쩡히 돌고
tensor-parallel 만 실패하므로 원인을 찾기 어렵다.

**`flash_attn` 스텁을 쓰지 않는다.** 논문 스크립트는 Gemma·Kanana 경로를 위해 스텁을 주입하지만
transformers 5.7.0 은 배포 메타데이터를 요구해 `KeyError: 'flash_attn'` 으로 깨진다.
스텁 없이 Gemma-4 2종과 Kanana 2종 모두 정상 동작함을 확인했다.

**gated 모델은 `HF_HUB_OFFLINE=1` 로 띄운다.** 가중치가 완비돼 있어도 vLLM 이 `tokenizer.model`
같은 선택적 파일을 허브에서 찾다가 401 을 받고 죽는다.

**`gpt-oss-120b` 는 TP4 로 두 번 실패했다**(30/50, 32/50 부근에서 워커 사망). MXFP4 라
가중치가 약 65GB 여서 H200 두 장이면 충분하므로 TP2 로 낮춰 완주했다.

## 주의

`e2e_sched.sh` 의 `reap_gpu` 는 잔존 GPU 프로세스를 걷어낸다. `VLLM::EngineCore` 는 부모가
죽어도 살아남아 GPU 를 131GB 씩 붙잡기 때문이다. 다만 **실행 중인 서버의 자손은 보호해야 한다**
— 그러지 않으면 정상 진행 중인 다른 모델을 죽인다(`run_phase2.sh` 의 `reap_gpu <keep-pid>`).

모델별 실행 전에 체크포인트를 지운다. 엔진이 중간에 죽으면 벤치가 `Connection error` 로 채운
체크포인트를 남기고, `--resume` 이 그것을 재사용해 결과가 오염된다.
