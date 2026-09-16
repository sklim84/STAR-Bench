"""Korean schema arm: the platform tool definitions with Korean prose.

GENERATED FILE. Edit `tools_kr_text.json` and run
`python -m _experiments.scripts.gen_tools_kr`; `--check` fails when this file is
stale, and `_experiments/scripts/tests_runner/test_schema_parity.py` fails when
the structure drifts from `agent.TOOLS`.

The structure is the platform schema, unchanged: same tool names, parameter
names, types, enums, defaults, `required` lists and item schemas (D16). Only the
descriptions and the system prompt are Korean, so a run on this arm executes the
model's arguments as they arrive, with no key or value rewriting (C2-006,
L5-015). The response-language rule is the same as in the English arm (D13).

Source: agent.TOOLS @ platform 1309117
"""

from __future__ import annotations

import json

TOOLS_KR: list[dict] = json.loads(r"""
[
 {
  "type": "function",
  "function": {
   "name": "query_transactions",
   "description": "HOFINET 데이터베이스에 읽기 전용 SQL 쿼리를 실행한다. 테이블명은 'hofinet'이고 컬럼은 date(거래일자, INTEGER yyyymmdd), time_slot(거래시간대), sender_bank(출금금융회사일련번호), sender_acc(출금계좌일련번호), receiver_bank(입금금융회사일련번호), receiver_acc(입금계좌일련번호), fund_type(자금구분), media_type(매체구분), amount(거래금액), is_fraud(이상거래여부), fraud_type(이상거래유형), fraud_description(이상거래설명)이다. total_count, returned_count와 처음 최대 100행을 반환한다.",
   "parameters": {
    "type": "object",
    "properties": {
     "sql": {
      "type": "string",
      "description": "실행할 SELECT SQL 쿼리(선행 WITH 절 허용). 'hofinet' 테이블에 대해 집계, 필터링, 그룹핑을 수행한다. date는 정수이므로 정수와 비교한다: date BETWEEN 20240101 AND 20241231."
     }
    },
    "required": [
     "sql"
    ]
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "predict_fraud",
   "description": "플랫폼의 XGBoost 모델로 거래 한 건을 채점한다. fraud_risk_score(0과 1 사이의 보정되지 않은 점수, 높을수록 위험하며 이상거래 확률이 아니다)와 위험 등급(High >= 0.7, Medium >= 0.3)을 반환한다.",
   "parameters": {
    "type": "object",
    "properties": {
     "time_slot": {
      "type": "integer",
      "description": "3시간 단위 거래시간대(0, 3, 6, 9, 12, 15, 18, 21 중 하나)"
     },
     "sender_bank": {
      "type": "integer"
     },
     "receiver_bank": {
      "type": "integer"
     },
     "fund_type": {
      "type": "integer",
      "description": "0, 1, 3, 4 중 하나"
     },
     "media_type": {
      "type": "integer",
      "description": "1~7 중 하나"
     },
     "amount": {
      "type": "integer",
      "description": "거래금액(원, 양의 정수)"
     }
    },
    "required": [
     "time_slot",
     "sender_bank",
     "receiver_bank",
     "fund_type",
     "media_type",
     "amount"
    ]
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "generate_str",
   "description": "전달된 분석 결과로 공식 양식(제I장~제VII장)의 의심거래보고서(STR) 초안을 생성한다. 'transactions'에 거래 레코드를 담으면 보고서의 계좌, 금액, 일자, 채널을 그 값으로 채우고, 없으면 요약 문장에서 가능한 범위까지 추출한다.",
   "parameters": {
    "type": "object",
    "properties": {
     "summary": {
      "type": "string",
      "description": "분석 결과와 의심 근거 요약(패턴, 수치 등을 구체적으로 기술)"
     },
     "fraud_type": {
      "type": "string",
      "description": "STR 양식 §VI 의심거래 분류 (FIU 공식). §VI-4 거래유형 16종(코드 15-30) + §VI-5 기타 자유기술(코드 31) = 17종. HOFINET 이상거래유형 매핑: 1→§VI-4 code 15, 3→18, 4→25, 5→20; 2(신규 수신처)/7(심야/새벽 대량)은 §VI-4 직접 대응 없어 §VI-5 code 31(기타)로 매핑.",
      "enum": [
       "갑작스러운 거래패턴의 변화",
       "원격지거래",
       "교환거래",
       "분할거래",
       "현금에 집착하는 거래",
       "거액 입금 후 당일/익일 인출",
       "무기명증서 관련거래",
       "계좌개설 없이 거액 환전/송금",
       "의심스러운 담보대출/보험약관대출",
       "주금 납입/잔액증명서 발급",
       "다중거래의 동시요청",
       "빈번한 입출금",
       "의심스러운 대여금고/보호예수",
       "법인/타인자산 담보 거래",
       "무관업종 보험청약",
       "테러자금으로 의심",
       "기타(자유기술)"
      ]
     },
     "transactions": {
      "type": "array",
      "description": "query_transactions 결과에서 가져온 관련 거래 레코드 목록. 계좌, 금액, 일자, 채널 자동 추출에 쓴다.",
      "items": {
       "type": "object",
       "properties": {
        "date": {
         "type": "integer"
        },
        "time_slot": {
         "type": "integer"
        },
        "sender_bank": {
         "type": "integer"
        },
        "sender_acc": {
         "type": "integer"
        },
        "receiver_bank": {
         "type": "integer"
        },
        "receiver_acc": {
         "type": "integer"
        },
        "fund_type": {
         "type": "integer"
        },
        "media_type": {
         "type": "integer"
        },
        "amount": {
         "type": "integer"
        },
        "fraud_type": {
         "type": "integer"
        }
       }
      }
     },
     "fraud_probability": {
      "type": "number",
      "description": "predict_fraud의 위험 점수(fraud_risk_score, 0.0~1.0). 의심 강도(1~5) 산정에 쓴다."
     },
     "aml_patterns": {
      "type": "array",
      "items": {
       "type": "string"
      },
      "description": "탐지된 AML 패턴 목록(예: ['Ring', 'Layering'])"
     },
     "tools_used": {
      "type": "array",
      "items": {
       "type": "string"
      },
      "description": "분석에 사용한 도구 목록(예: ['query_transactions', 'predict_fraud'])"
     }
    },
    "required": [
     "summary"
    ]
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "analyze_network",
   "description": "한 계좌 주변의 거래 네트워크를 분석한다. 연결된 계좌 수, 그 이웃의 거래 건수와 이상거래 건수, 이상거래 비율(%), 거래금액 합계를 반환한다.",
   "parameters": {
    "type": "object",
    "properties": {
     "account_id": {
      "type": "integer",
      "description": "분석할 계좌번호(sender_acc)"
     },
     "hops": {
      "type": "integer",
      "description": "탐색 깊이 1~5(기본 1). 1은 해당 계좌 자신의 거래를 뜻하고, 한 홉 늘릴 때마다 그때까지 도달한 계좌들의 거래를 더한다.",
      "default": 1
     }
    },
    "required": [
     "account_id"
    ]
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "get_statistics",
   "description": "데이터셋 전체 요약 통계를 조회한다: 총 거래 건수, 이상거래 건수와 비율(%), 서로 다른 출금 계좌 수와 입금 계좌 수, 서로 다른 출금 금융회사 수와 입금 금융회사 수, 총 거래금액, 이상거래유형별 거래 건수. 전체 데이터가 대상이며 필터를 받지 않는다.",
   "parameters": {
    "type": "object",
    "properties": {},
    "required": []
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "get_account_profile",
   "description": "한 계좌의 거래 프로파일을 조회한다. 그 계좌가 보낸 거래와 받은 거래를 모두 센다. 전체·출금·입금 건수, 총 거래금액, 이상거래 건수와 비율(%), 거래가 많은 시간대와 매체, 상위 5개 거래상대와 그 방향을 반환한다.",
   "parameters": {
    "type": "object",
    "properties": {
     "account_id": {
      "type": "integer",
      "description": "조회할 계좌번호(sender_acc 또는 receiver_acc)"
     }
    },
    "required": [
     "account_id"
    ]
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "get_fraud_type_summary",
   "description": "HOFINET 이상거래유형별 현황을 조회한다(갑작스러운 거래패턴의 변화, 신규 수신처 거래, 분할 거래 등). 건수·금액 통계와 상위 관련 금융회사를 반환한다. 코드 매핑: 1=갑작스러운 거래패턴의 변화, 2=신규 수신처 거래, 3=분할 거래, 4=다중거래의 동시 요청, 5=거액 입금 후 당일 인출, 7=심야/새벽 대량 거래 (코드 6 미사용)",
   "parameters": {
    "type": "object",
    "properties": {
     "fraud_type": {
      "type": "integer",
      "description": "이상거래유형 코드 (1~5, 7; 코드 6 미사용)",
      "enum": [
       1,
       2,
       3,
       4,
       5,
       7
      ]
     },
     "bank_id": {
      "type": "integer",
      "description": "출금 금융회사 기준 선택 필터."
     }
    },
    "required": [
     "fraud_type"
    ]
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "compare_periods",
   "description": "두 기간의 거래·이상거래 통계를 비교해 증감률을 반환한다. 거래 건수, 이상거래 건수, 평균 거래금액과 변화율을 계산한다.",
   "parameters": {
    "type": "object",
    "properties": {
     "period1_start": {
      "type": "integer",
      "description": "기간 1 시작일(YYYYMMDD 정수)"
     },
     "period1_end": {
      "type": "integer",
      "description": "기간 1 종료일(YYYYMMDD 정수)"
     },
     "period2_start": {
      "type": "integer",
      "description": "기간 2 시작일(YYYYMMDD 정수)"
     },
     "period2_end": {
      "type": "integer",
      "description": "기간 2 종료일(YYYYMMDD 정수)"
     }
    },
    "required": [
     "period1_start",
     "period1_end",
     "period2_start",
     "period2_end"
    ]
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "get_institution_report",
   "description": "금융회사 한 곳의 현황을 네트워크 양쪽에서 보고한다: 출금측(sender_bank)과 입금측(receiver_bank)의 거래 건수·금액·이상거래 비율(%), 방향별 상위 상대 금융회사, 이상거래유형별 분포, 분기별 추이.",
   "parameters": {
    "type": "object",
    "properties": {
     "bank_id": {
      "type": "integer",
      "description": "조회할 금융회사 일련번호(sender_bank 코드는 102~161, receiver_bank 코드는 101~160)"
     }
    },
    "required": [
     "bank_id"
    ]
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "rank_risky_transactions",
   "description": "데이터베이스 거래의 고정 표본을 XGBoost 모델로 채점해 위험 점수 상위 K건을 반환한다. 대량 선별과 우선순위 지정에 쓴다. 점수는 predict_fraud가 반환하는 것과 같은 보정되지 않은 fraud_risk_score이며, 실제 정답 라벨은 결과에 포함하지 않는다.",
   "parameters": {
    "type": "object",
    "properties": {
     "sample_size": {
      "type": "integer",
      "description": "채점할 거래 수(기본 1000, 최대 5000)",
      "default": 1000
     },
     "top_k": {
      "type": "integer",
      "description": "반환할 고위험 거래 수(기본 20, 최대 100)",
      "default": 20
     }
    },
    "required": []
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "detect_aml_patterns",
   "description": "이체 그래프에서 AML 패턴을 탐지한다. ring: 이상거래로 표시된 이체가 min_len~max_len개 이어져 출발 계좌로 돌아오는 순환. layering: 이상거래로 표시된 이체가 min_layers개 이상 연속되는 사슬. HOFINET의 이체 그래프에는 순환이 없으므로 이 데이터셋에서 ring과 layering은 결과를 내지 않는다. funnel: 서로 다른 계좌 min_inflow곳 이상에서 받아 1~max_outflow곳으로 내보내는 계좌(수집 계좌). HOFINET에서 받기도 하고 보내기도 하는 계좌는 최소 4곳으로 내보내므로 max_outflow가 4보다 작으면 아무것도 걸리지 않는다. shortest_path: 두 계좌 사이의 최단 이체 사슬(방향은 어느 쪽이든). risk_score: 자신과 거래상대의 이상거래 비중, 순환 참여, 입출금 불균형으로 계산한 계좌 그래프 위험 점수(0~1).",
   "parameters": {
    "type": "object",
    "properties": {
     "pattern_type": {
      "type": "string",
      "description": "탐지할 패턴 유형",
      "enum": [
       "ring",
       "layering",
       "funnel",
       "shortest_path",
       "risk_score"
      ]
     },
     "account_id": {
      "type": "integer",
      "description": "대상 계좌 ID(risk_score에 필수)"
     },
     "account_a": {
      "type": "integer",
      "description": "시작 계좌(shortest_path에 필수)"
     },
     "account_b": {
      "type": "integer",
      "description": "도착 계좌(shortest_path에 필수)"
     },
     "min_len": {
      "type": "integer",
      "description": "최소 순환 길이(기본 3)",
      "default": 3
     },
     "max_len": {
      "type": "integer",
      "description": "최대 순환 길이(기본 6)",
      "default": 6
     },
     "min_layers": {
      "type": "integer",
      "description": "최소 레이어링 단계 수(기본 3)",
      "default": 3
     },
     "min_inflow": {
      "type": "integer",
      "description": "funnel: 퍼널이 자금을 받는 서로 다른 계좌의 최소 수(기본 5)",
      "default": 5
     },
     "max_outflow": {
      "type": "integer",
      "description": "funnel: 퍼널이 자금을 내보내는 서로 다른 계좌의 최대 수. 내보내는 거래상대가 최소 한 곳은 있어야 한다(기본 5)",
      "default": 5
     },
     "limit": {
      "type": "integer",
      "description": "반환할 최대 결과 수(기본 20)",
      "default": 20
     }
    },
    "required": [
     "pattern_type"
    ]
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "detect_ctr_candidates",
   "description": "고액현금거래보고(CTR) 관련 건을 조회하거나 분할거래 패턴을 탐지한다. mode=high_value: 기준금액(기본 1,000만원) 이상인 단일 거래. mode=structuring: 하루 동안 개별 거래는 기준금액 미만이지만 합계가 기준금액 이상인 계좌.",
   "parameters": {
    "type": "object",
    "properties": {
     "mode": {
      "type": "string",
      "description": "조회 모드: high_value 또는 structuring",
      "enum": [
       "high_value",
       "structuring"
      ]
     },
     "date_from": {
      "type": "integer",
      "description": "시작일(YYYYMMDD 정수)"
     },
     "date_to": {
      "type": "integer",
      "description": "종료일(YYYYMMDD 정수)"
     },
     "threshold": {
      "type": "integer",
      "description": "보고 기준금액(원). 두 모드 모두에 적용된다(기본 1,000만원)",
      "default": 10000000
     },
     "limit": {
      "type": "integer",
      "description": "최대 결과 수(기본 20)",
      "default": 20
     }
    },
    "required": [
     "mode"
    ]
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "score_account_risk",
   "description": "계좌의 행동 위험 점수(0~100)를 5개 지표로 평가한다: 심야 시간대(21, 0, 3) 거래 비중, 평균 거래금액이 데이터셋 평균에서 벗어난 정도, 거래상대 다양성, 마지막 두 분기 사이의 거래량 변화, 이상거래 이력(HOFINET이 이상거래로 표시한 거래의 비중). 위험 등급(High >= 70, Medium >= 40, Low)과 지표별 점수·가중치를 반환한다. 보낸 거래와 받은 거래를 모두 센다.",
   "parameters": {
    "type": "object",
    "properties": {
     "account_id": {
      "type": "integer",
      "description": "평가할 계좌번호(sender_acc 또는 receiver_acc)"
     }
    },
    "required": [
     "account_id"
    ]
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "detect_monitoring_alerts",
   "description": "규칙 기반 거래 모니터링 규칙을 실행해 경보를 반환한다. R001 심야 대량 거래: 심야 시간대(21, 0, 3)의 500만원 이상 거래. R002 당일 단기 다발 거래: 하루에 10건 이상 거래한 계좌. R003 동일 금액 반복 송금: 같은 금액(200만원 이상)을 3회 이상 보낸 계좌. R004 기관 집중: 거래의 절반 이상을 한 입금 금융회사로 보낸 계좌. R005 거래 패턴 변화: 지정 기간의 거래량이 같은 길이의 직전 기간보다 3배 이상인 계좌. 날짜를 주지 않으면 데이터의 마지막 분기와 그 직전 분기를 비교한다. rule_id='all'은 다섯 규칙을 모두 실행한다. date_from, date_to, account_id는 모든 규칙에 적용된다.",
   "parameters": {
    "type": "object",
    "properties": {
     "rule_id": {
      "type": "string",
      "description": "실행할 규칙 ID",
      "enum": [
       "all",
       "R001",
       "R002",
       "R003",
       "R004",
       "R005"
      ]
     },
     "date_from": {
      "type": "integer",
      "description": "시작일(YYYYMMDD 정수)"
     },
     "date_to": {
      "type": "integer",
      "description": "종료일(YYYYMMDD 정수)"
     },
     "account_id": {
      "type": "integer",
      "description": "선택 계좌 필터(규칙이 기술하는 계좌: sender_acc, R001은 양쪽 모두)"
     },
     "limit": {
      "type": "integer",
      "description": "최대 결과 수(기본 20)",
      "default": 20
     }
    },
    "required": [
     "rule_id"
    ]
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "detect_dormant_reactivation",
   "description": "오랜 휴면 뒤 재활성화된 계좌를 탐지한다: dormant_days(기본 180일) 동안 거래가 없다가 min_reactivation_amount 이상인 거래가 발생한 경우. 마지막 활동일, 재활성화일, 휴면 기간의 길이, 재활성화 당일의 거래 건수와 금액을 반환한다.",
   "parameters": {
    "type": "object",
    "properties": {
     "dormant_days": {
      "type": "integer",
      "description": "휴면 판정 기준 일수(기본 180)",
      "default": 180
     },
     "min_reactivation_amount": {
      "type": "integer",
      "description": "재활성화로 볼 최소 거래금액(기본 500만원)",
      "default": 5000000
     },
     "limit": {
      "type": "integer",
      "description": "최대 결과 수(기본 20)",
      "default": 20
     }
    },
    "required": []
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "detect_smurfing_network",
   "description": "계좌별로 서로 다른 거래상대 수를 세어 기준 이상인 계좌를 반환한다. direction=inbound: 서로 다른 출금 계좌 min_counterparts곳 이상에서 받은 계좌(수집). direction=outbound: 서로 다른 입금 계좌 min_counterparts곳 이상으로 보낸 계좌(분산). 한 방향의 거래상대 수만 본다. 여러 곳에서 모아 소수에게 넘기는 계좌는 detect_aml_patterns의 pattern_type='funnel'을 쓴다.",
   "parameters": {
    "type": "object",
    "properties": {
     "account_id": {
      "type": "integer",
      "description": "선택 계좌 필터. 생략하면 전체를 훑는다."
     },
     "direction": {
      "type": "string",
      "description": "분석 방향: inbound 또는 outbound",
      "enum": [
       "inbound",
       "outbound"
      ]
     },
     "min_counterparts": {
      "type": "integer",
      "description": "최소 거래상대 수(기본 5)",
      "default": 5
     },
     "date_from": {
      "type": "integer",
      "description": "시작일(YYYYMMDD 정수)"
     },
     "date_to": {
      "type": "integer",
      "description": "종료일(YYYYMMDD 정수)"
     },
     "limit": {
      "type": "integer",
      "description": "최대 결과 수(기본 20)",
      "default": 20
     }
    },
    "required": [
     "direction"
    ]
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "get_trend_analysis",
   "description": "월별 또는 분기별 시계열 추이를 분석한다: 기간별 거래 건수, 이상거래 건수, 이상거래 비율(%), 총 거래금액과 평균 거래금액. 기간 이름은 '2024-07'(월별), '2024Q3'(분기별) 형식이다. 날짜 범위를 주지 않으면 전체 데이터(14개 분기, 2021-09~2024-12)가 대상이다.",
   "parameters": {
    "type": "object",
    "properties": {
     "unit": {
      "type": "string",
      "description": "집계 단위: monthly 또는 quarterly",
      "enum": [
       "monthly",
       "quarterly"
      ],
      "default": "monthly"
     },
     "date_from": {
      "type": "integer",
      "description": "시작일(YYYYMMDD 정수)"
     },
     "date_to": {
      "type": "integer",
      "description": "종료일(YYYYMMDD 정수)"
     }
    },
    "required": []
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "analyze_channel_risk",
   "description": "거래 매체(media_type)별 위험도를 분석한다: 1 PC 뱅킹, 2 인터넷 뱅킹, 3 전화, 4 휴대전화, 5 건별이체, 6 기타, 7 대량이체. 매체별 거래 건수와 이상거래 건수, 이상거래 비율(%)과 거래금액, 매체×거래시간대 교차 분석을 반환한다.",
   "parameters": {
    "type": "object",
    "properties": {
     "date_from": {
      "type": "integer",
      "description": "시작일(YYYYMMDD 정수)"
     },
     "date_to": {
      "type": "integer",
      "description": "종료일(YYYYMMDD 정수)"
     }
    },
    "required": []
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "get_receiving_account_profile",
   "description": "receiver_acc를 기준으로 자금을 받는 쪽에서 계좌를 프로파일링한다. 입금 거래 건수와 금액, 이상거래 건수와 비율(%), 서로 다른 송금 계좌 수와 송금 금융회사 수, 상위 5개 송금 계좌와 송금 금융회사를 반환한다.",
   "parameters": {
    "type": "object",
    "properties": {
     "account_id": {
      "type": "integer",
      "description": "조회할 계좌번호(receiver_acc)"
     }
    },
    "required": [
     "account_id"
    ]
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "analyze_cross_institution_flow",
   "description": "금융회사 쌍(출금 금융회사 → 입금 금융회사) 사이의 자금 흐름을 분석한다. 기관 간 거래 집중도, 이상거래 비율, 거래 규모를 파악한다. 특정 기관 사이에 이상거래가 몰리는 패턴을 찾는 데 쓴다.",
   "parameters": {
    "type": "object",
    "properties": {
     "date_from": {
      "type": "integer",
      "description": "시작일(YYYYMMDD 정수)"
     },
     "date_to": {
      "type": "integer",
      "description": "종료일(YYYYMMDD 정수)"
     },
     "min_transactions": {
      "type": "integer",
      "description": "최소 거래 건수(기본 10)",
      "default": 10
     },
     "limit": {
      "type": "integer",
      "description": "최대 결과 수(기본 20)",
      "default": 20
     }
    },
    "required": []
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "lookup_fiu_reference_types",
   "description": "FIU 의심거래 참고유형 카탈로그(발췌: 은행·증권 31건)를 검색한다. 카탈로그는 영어이고 검색어는 항목의 업권·분류·설명에 대소문자 구분 없이 부분 일치로 대조하므로 검색어도 영어여야 한다: 예를 들어 structuring, cash, non-face-to-face, virtual asset, dormancy, gambling, balance certificate. 검색어를 비우면 카탈로그 전체를 반환한다.",
   "parameters": {
    "type": "object",
    "properties": {
     "keyword": {
      "type": "string",
      "description": "영어 검색어(예: structuring, cash, non-face-to-face, virtual asset)"
     },
     "industry": {
      "type": "string",
      "description": "업권 필터: banking, securities, 또는 생략하면 전체",
      "enum": [
       "banking",
       "securities"
      ]
     }
    },
    "required": [
     "keyword"
    ]
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "validate_str_fields",
   "description": "STR 초안에 보고 양식이 요구하는 항목이 있는지 검사하고 무엇이 빠졌는지 보고한다. 필수: Header.ReportingDate; I_ReportingInstitution.WithdrawalInstitutionCode; II_Transactor.WithdrawalAccountNumber와 .ReceivingAccountNumber; III_TransactionDetails.TransactionPeriod, .TransactionCount, .TransactionChannel, .TotalAmount_KRW; VI_TransactionType.PrimarySuspicionType; VII_Narrative.SuspicionJudgmentReason. generate_str의 출력은 그대로 통과한다. 양식이 요구하지만 HOFINET에 없는 개인정보(성명, 실명확인증표, 연락처)는 선택 항목이며 missing_optional로 보고한다.",
   "parameters": {
    "type": "object",
    "properties": {
     "str_draft": {
      "type": "object",
      "description": "섹션별로 중첩된 STR 초안 객체(Header, I_ReportingInstitution, II_Transactor, III_TransactionDetails, VI_TransactionType, VII_Narrative). generate_str이 반환하는 형태 그대로다. 항목 이름은 대소문자와 밑줄을 무시하고 대조한다."
     }
    },
    "required": [
     "str_draft"
    ]
   }
  }
 },
 {
  "type": "function",
  "function": {
   "name": "get_aml_glossary",
   "description": "AML 용어의 정의를 반환한다. 용어집은 영어 13개 항목을 담고 있고 대소문자를 무시한 정확 일치로만 찾는다: CDD, EDD, SDD, STR, CTR, RBA, PEP, MLRO, FATF, FIU, KYE, Structuring, Layering. 한국어 항목은 없다.",
   "parameters": {
    "type": "object",
    "properties": {
     "term": {
      "type": "string",
      "description": "조회할 영어 용어(CDD, EDD, SDD, STR, CTR, RBA, PEP, MLRO, FATF, FIU, KYE, Structuring, Layering)"
     }
    },
    "required": [
     "term"
    ]
   }
  }
 }
]
""")

SYSTEM_PROMPT_KR: str = json.loads(r"""
"당신은 자금세탁방지(AML) 분석가입니다.\nHOFINET(전자금융공동망) 거래 데이터로 의심거래를 살피고 보고합니다.\n\n도구 정의는 API의 tools 필드로 제공됩니다. 각 도구의 이름, 설명, 파라미터 스키마는 그곳을 참고하세요.\n\nAML 용어집에 있는 용어의 정의나 비교를 묻는 요청은 get_aml_glossary로 답하고, 그 밖의 개념 설명은 도구 없이 답합니다.\n\n데이터:\n- hofinet 테이블, 거래 4,732,130건, 한 행이 이체 한 건입니다.\n- 컬럼: date, time_slot, sender_bank, sender_acc, receiver_bank, receiver_acc, fund_type, media_type, amount, is_fraud, fraud_type, fraud_description.\n- date는 yyyymmdd 형식의 INTEGER이고 20210901부터 20241231까지입니다(14개 분기). 정수로 비교하세요. 예: date BETWEEN 20240101 AND 20241231. '2024-01-01' 같은 문자열 날짜와 LIKE 패턴은 이 컬럼에 쓸 수 없습니다.\n- time_slot은 3시간 구간의 시작 시각입니다: 0, 3, 6, 9, 12, 15, 18, 21.\n- sender_acc와 receiver_acc는 16자리 계좌번호이고 9000000000000002부터 9000000004455021까지입니다. 출금계좌로 30,526개, 입금계좌로 422,698개가 나타나며 414개는 양쪽 모두입니다.\n- sender_bank 코드는 102~161(50개 기관), receiver_bank 코드는 101~160(54개 기관)입니다.\n- amount는 원 단위이고 1부터 500,000,000 사이의 48개 값만 나타납니다.\n- is_fraud는 의심거래로 표시된 14,490건이 1이고 나머지는 0입니다.\n- fraud_type은 정상 거래에서 NULL이고, fraud_description은 정상 거래에서 빈 문자열입니다. 그 밖에는 아래 한국어 명칭이 그대로 저장돼 있습니다.\n  1 = 갑작스러운 거래패턴의 변화 (1,955건)\n  2 = 신규 수신처 거래 (9,255건)\n  3 = 분할 거래 (2,073건)\n  4 = 다중거래의 동시 요청 (929건)\n  5 = 거액 입금 후 당일 인출 (243건)\n  7 = 심야/새벽 대량 거래 (35건)\n  코드 6은 쓰이지 않습니다.\n- media_type: 1=PC 뱅킹, 2=인터넷 뱅킹, 3=전화, 4=휴대전화, 5=건별이체, 6=기타, 7=대량이체.\n- fund_type: 0=일반, 1=급여, 3=기타, 4=타행 자동이체.\n\n사용자 질문의 언어로 답하세요. 도구가 돌려준 수치를 제시하고 그 수치가 무엇을 뒷받침하는지 밝히세요."
""")

__all__ = ["TOOLS_KR", "SYSTEM_PROMPT_KR"]
