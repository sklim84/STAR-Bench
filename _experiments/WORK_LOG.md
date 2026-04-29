# Experiment Session Log

다른 서버의 claude code 인스턴스가 컨텍스트를 빠르게 복원하기 위한 세션 결정 로그.
시간 역순(최신 → 과거)으로 추가하며, 코드/벤치마크에 영구 반영된 결정만 기록.

---

## 2026-04-29: HOFINET 정합성 정정 + 시스템 프롬프트 간소화 + 스케줄링 재배치

### 핵심 변경사항

**(1) HOFINET 공식 코드표 적용 (R1~R7 + 추가 정정)**

KFTC D-테스트베드 공식 PDF 기반 정확한 코드 매핑 적용. 영문 라벨 통일:

| 코드 | fraud_type (HOFINET 공식 EN) | media_type | fund_type |
|---|---|---|---|
| 1 | Sudden Change in Transaction Pattern | PC Banking | General |
| 2 | Transaction with New Counterparty | Internet Banking | Salary |
| 3 | Split Transaction | Phone | — |
| 4 | Concurrent Multiple Transactions | Mobile Phone | Other |
| 5 | Same-Day Withdrawal after Large Deposit | Per-transaction Transfer | Inter-bank Auto Transfer |
| 6 | (unused) | Other | — |
| 7 | Late-Night/Early-Morning Bulk Transactions | Bulk Transfer | — |

- 코드 6은 HOFINET에 미존재 → benchmark에서 7로 재할당
- 옛 매핑 (`Money Laundering`, `Voice Phishing` 등) 모두 제거
- 정정 영향: 코드(`agent.py`, `tools_en.py`, `main.tex` Appendix F.1) + 벤치마크 케이스 (KR/EN 1,258 + MT 50)

**(2) 시스템 프롬프트 간소화 (Native FC 원칙)**

23개 도구 목록의 SYSTEM_PROMPT 내 중복 제거. 도구 정의는 API `tools` 필드(권위 source)에만 존재.
- 본문 추가: `"Tool definitions are provided via the API tools field; refer to each tool's name, description, and parameter schema there."`
- SYSTEM_PROMPT 길이: 3,475 → 1,785 chars (~50% 감축)
- 보존: Recommended Analysis Flow, STR Generation Notes, Data Schema, Persona

**(3) 벤치마크 정합성 위반 정정 (~454건)**

| 위반 종류 | 정정 건수 | 매핑 방식 |
|---|---|---|
| time_slot 비표준 값 (예: 14, 17) | 38 | 가장 가까운 유효 3h 단위 (0/3/6/9/12/15/18/21) |
| sender_bank 무효 코드 (예: 89, 200) | 127 | hash-based deterministic 매핑 (HOFINET 50개 출금은행 중) |
| receiver_bank 무효 코드 | 146 | 동일 (HOFINET 54개 입금은행) |
| KR question 옛 라벨 → HOFINET 라벨 | 125 | 1:1 (자금세탁→갑작스러운 거래패턴의 변화 등) |
| code 6 → 7 재할당 | 12 | KR 6 + EN 6 |
| Multi-turn 라벨 (scenario/fraud_type_name/turn.content) | 120 | 동일 매핑 |

**(4) 스케줄링 (γ + TP=2/thinking 분리)**

- `qwen3-4b-think`를 GROUP_A → GROUP_B 끝으로 이동 (thinking 9h+ 점유 → GPU 1 마지막에 단독)
- TP=2 (70B+ 3 모델: Llama-3.3-70B, xLAM-70B, A.X-4.0): **별도 서버에서 진행** (현 master에서 제외)
- thinking 모드 (think=True 변형 9개): **별도 ablation으로 진행** (현 master에서 제외)
- 현재 master는 nothink + 비-TP=2 모델만 → 약 25% 시간 절감

### 진행 중 / 다음 단계

- **현재 v6 master 종료 → v7 fresh start** (TP=2 + thinking 제외 적용)
- v7 master는 `--skip-tp2 --skip-thinking` 옵션으로 KR/EN/MT × {nothink only, non-70B} 변형만 실행
- TP=2 + thinking은 다른 GPU 서버에서 별도 실행 후 결과만 머지

### 영구 규약

- **용어**: 영어는 `single-turn` / `multi-turn`. 한국어는 `싱글턴` / `멀티턴` (음역). `singleton` 사용 금지 (design pattern 제외).
- **Native FC**: vLLM tool-call-parser + OpenAI/Anthropic tools 필드 사용. Prompting mode (system prompt에 tools JSON 박기) 미사용.
- **HOFINET 공식 매핑**: 위 표 기준. `_datasets/HOFINET.MD` 참조.
- **벤치마크 케이스 ↔ HOFINET**: 모든 정수 코드 (fraud_type, media_type, fund_type, time_slot, sender/receiver_bank)는 HOFINET 유효 값만 사용.

### 인증 commit hash

| Repo | Commit | 내용 |
|---|---|---|
| `_paper` (submodule) | `4477e49` | 벤치마크 정정 + 시스템 프롬프트 간소화 + singleton→single-turn |
| Main repo | `5ae7758` | agent.py + tests + README + submodule pointer |

---

## 다른 서버에서 컨텍스트 복원 절차

```bash
git pull --recurse-submodules
# CLAUDE.md + 이 WORK_LOG.md를 읽고 시작
# 추가로 git log -10으로 최근 commit 의도 파악
```

claude code 시작 메시지 예시:
```
이 repo의 CLAUDE.md와 _paper/_experiments/WORK_LOG.md를 읽고 컨텍스트 복원해줘.
직전 세션은 4/29에 HOFINET 정합성 정정 + 시스템 프롬프트 간소화를 끝냈고,
TP=2 + thinking ablation을 별도 서버에서 진행할 예정이야.
