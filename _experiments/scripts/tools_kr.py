"""번역 이전(2026-04-21 `6c024d9` 이전)의 한국어 도구 정의 — KR/EN 스키마 언어 ablation용.

STAR-Bench-Web 커밋 `6c024d9`("Translate Kor to Eng")가 도구 계층을 영문화하면서
기본 도구 정의가 영어가 됐다. 그 결과 `--tools-lang en`과 기본 실행이 모두 영어가 되어
2×2의 둘째 축이 "한국어 대 영어"가 아니라 "영어 표현 두 벌"이 됐다.

이 모듈은 `6c024d9^`의 TOOLS와 SYSTEM_PROMPT를 그대로 복원해 진짜 KR 팔을 만든다.
도구 **이름**은 번역 전후 모두 영어이고 집합·순서도 동일하므로(23개) 실행 디스패치는
그대로 동작한다. 달라지는 것은 모델이 읽는 설명문과 파라미터 **이름**뿐이다.

실행·채점 정규화
----------------
모델은 한글 인자명(`거래시간대`)을 내지만 실행부 `_tool_predict_fraud`는 영문
(`time_slot`)을 기대하고, 정답도 영문으로 동기화돼 있다. 따라서 파싱 직후·실행 직전에
KR_TO_EXEC_KEY로 키를 정규화한다. `benchmark._KO_EN_KEY_MAP`은 `tools_en.py` 계열
이름(`transaction_time_zone`)이라 이 용도로 쓸 수 없다.

값 수준 의존은 두 도구뿐이다. FIU 참조 데이터와 용어집이 영문화됐으므로 한글 검색어는
0건을 반환한다. KR_TO_EXEC_VALUE가 그 9건을 실행 직전에 변환한다.
"""
from __future__ import annotations

# 한글 인자명 → 실행부/정답이 쓰는 영문 인자명.
# 영문화 커밋 전후의 agent.py를 도구별로 대조해 도출했다(손으로 정하지 않았다).
KR_TO_EXEC_KEY: dict[str, str] = {
    "거래시간대": "time_slot",
    "거래일자": "date",
    "거래금액": "amount",
    "매체구분": "media_type",
    "자금구분": "fund_type",
    "이상거래유형": "fraud_type",
    "출금금융회사일련번호": "sender_bank",
    "출금계좌일련번호": "sender_acc",
    "입금금융회사일련번호": "receiver_bank",
    "입금계좌일련번호": "receiver_acc",
    "금융회사일련번호": "bank_id",
}

# 값 수준 변환: 참조 데이터가 영문화되어 한글 검색어로는 0건이 반환된다.
# 각 대응은 aml_reference.lookup_fiu_reference_types()로 결과가 나오는지 확인했다.
KR_TO_EXEC_VALUE: dict[str, dict[str, str]] = {
    "lookup_fiu_reference_types": {
        "keyword": {
            "분할거래": "structuring",
            "분할": "split",
            "심야": "24-hour",
            "비대면": "Non-face-to-face",
            "가상자산": "virtual asset",
            "타인명의": "others' names",
            "휴면": "dormancy",
            "법인": "corporate",
        }
    },
    "get_aml_glossary": {"term": {"구조화": "structuring"}},
}


def normalize_args(tool_name: str, args: dict) -> dict:
    """KR 스키마로 받은 인자를 실행·채점이 쓰는 형태로 정규화한다.

    키는 전역으로, 값은 지정된 (도구, 키)에 한해서만 변환한다. 중첩 구조도 따라간다.
    """
    if not isinstance(args, dict):
        return args
    vmap = KR_TO_EXEC_VALUE.get(tool_name, {})
    out: dict = {}
    for k, v in args.items():
        nk = KR_TO_EXEC_KEY.get(k, k)
        if isinstance(v, dict):
            out[nk] = normalize_args(tool_name, v)
        elif isinstance(v, list):
            out[nk] = [normalize_args(tool_name, x) if isinstance(x, dict) else x for x in v]
        else:
            out[nk] = vmap.get(k, {}).get(v, v) if k in vmap else v
    return out


TOOLS_KR = [
    {
        "type": "function",
        "function": {
            "name": "query_transactions",
            "description": (
                "HOFINET 데이터베이스에 SQL 쿼리를 실행하여 거래 데이터를 조회한다. "
                "테이블명은 hofinet이고 컬럼은 거래일자, 거래시간대, 출금금융회사일련번호, "
                "출금계좌일련번호, 입금금융회사일련번호, 입금계좌일련번호, 자금구분, 매체구분, "
                "거래금액, 이상거래여부, 이상거래유형, 이상거래설명이다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": (
                            "실행할 SELECT SQL 쿼리. hofinet 테이블에 대해 "
                            "집계, 필터링, 그룹핑 등을 수행한다."
                        ),
                    }
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "predict_fraud",
            "description": "학습된 XGBoost 모델로 거래의 이상거래 확률을 예측한다. 거래 정보를 입력하면 0~1 사이의 확률을 반환한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "거래시간대": {
                        "type": "integer",
                        "description": "3시간 단위 (0, 3, 6, 9, 12, 15, 18, 21 중 하나)",
                    },
                    "출금금융회사일련번호": {"type": "integer"},
                    "입금금융회사일련번호": {"type": "integer"},
                    "자금구분": {
                        "type": "integer",
                        "description": "0, 1, 3, 4 중 하나",
                    },
                    "매체구분": {
                        "type": "integer",
                        "description": "1~7 중 하나",
                    },
                    "거래금액": {
                        "type": "integer",
                        "description": "원 단위 금액 (양의 정수)",
                    },
                },
                "required": [
                    "거래시간대",
                    "출금금융회사일련번호",
                    "입금금융회사일련번호",
                    "자금구분",
                    "매체구분",
                    "거래금액",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_str",
            "description": (
                "분석 결과를 기반으로 의심거래보고서(STR) 공식 양식(I~VII섹션)에 맞게 작성한다. "
                "STR 작성 전에 반드시 query_transactions로 관련 거래 데이터를 먼저 조회하고, "
                "조회한 거래 레코드를 transactions 파라미터에 포함하여 호출할 것."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "분석 결과 요약 및 혐의 판단 사유 (의심 사유, 거래 패턴, 수치 등 구체적으로 기술)",
                    },
                    "fraud_type": {
                        "type": "string",
                        "description": "HOFINET 이상거래유형 분류",
                        "enum": ["자금세탁", "대포통장", "보이스피싱", "불법도박", "유사수신", "신규거래처", "기타"],
                    },
                    "transactions": {
                        "type": "array",
                        "description": "query_transactions 결과에서 가져온 관련 거래 레코드 목록. 계좌·금액·날짜·채널 자동 추출에 사용됨.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "거래일자": {"type": "integer"},
                                "거래시간대": {"type": "integer"},
                                "출금금융회사일련번호": {"type": "integer"},
                                "출금계좌일련번호": {"type": "integer"},
                                "입금금융회사일련번호": {"type": "integer"},
                                "입금계좌일련번호": {"type": "integer"},
                                "자금구분": {"type": "integer"},
                                "매체구분": {"type": "integer"},
                                "거래금액": {"type": "integer"},
                                "이상거래유형": {"type": "integer"},
                            },
                        },
                    },
                    "fraud_probability": {
                        "type": "number",
                        "description": "predict_fraud 도구로 예측한 이상거래 확률 (0.0~1.0). 의심 강도(1~5) 산출에 사용됨.",
                    },
                    "aml_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "detect_aml_patterns로 탐지된 AML 패턴 목록 (예: ['순환거래', '레이어링'])",
                    },
                    "tools_used": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "분석에 사용된 도구 목록 (예: ['query_transactions', 'predict_fraud', 'analyze_network'])",
                    },
                },
                "required": ["summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_network",
            "description": "특정 계좌의 거래 네트워크를 분석한다. 계좌 번호를 입력하면 연결된 계좌 수, 거래 횟수, 이상거래 관련 여부를 반환한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "integer",
                        "description": "분석할 계좌 번호 (출금계좌일련번호)",
                    },
                    "hops": {
                        "type": "integer",
                        "description": "탐색 범위 (1~5). 기본값은 1. 3 이상은 Memgraph 필요.",
                        "default": 1,
                    },
                },
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_statistics",
            "description": "대시보드 요약 통계를 조회한다. 전체 거래 건수, 이상거래 건수/비율, 이상거래 유형별 분포 등 기본 통계를 반환한다.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_account_profile",
            "description": (
                "특정 계좌의 거래 통계 프로파일을 조회한다. "
                "총 거래 건수/금액, 이상거래 건수/비율, 주요 거래 시간대, "
                "주 사용 매체, 상위 거래 상대 계좌 5개를 반환한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "integer",
                        "description": "조회할 계좌 번호 (출금계좌일련번호 기준)",
                    }
                },
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fraud_type_summary",
            "description": (
                "이상거래 유형별(자금세탁/보이스피싱/대포통장 등) 현황을 조회한다. "
                "유형 이름 또는 코드(1~7)로 필터하면 건수·금액 통계와 상위 금융회사를 반환한다. "
                "코드 매핑: 1=자금세탁, 2=신규거래처, 3=대포통장, 4=보이스피싱, 5=불법도박, 6=유사수신, 7=기타"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fraud_type": {
                        "type": "integer",
                        "description": "이상거래유형 코드 (1~7)",
                        "enum": [1, 2, 3, 4, 5, 6, 7],
                    },
                    "bank_id": {
                        "type": "integer",
                        "description": "출금금융회사일련번호 필터 (선택). 지정 시 해당 금융회사의 거래만 조회.",
                    },
                },
                "required": ["fraud_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_periods",
            "description": (
                "두 기간의 거래·이상거래 통계를 비교하고 변화율(delta)을 반환한다. "
                "기간별 거래 건수, 이상거래 건수, 평균 거래금액과 증감률을 산출한다. "
                "분기 비교, 월간 비교, 특정 이벤트 전후 비교에 활용한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "period1_start": {
                        "type": "integer",
                        "description": "첫 번째 기간 시작일 (YYYYMMDD 정수, 예: 20240101)",
                    },
                    "period1_end": {
                        "type": "integer",
                        "description": "첫 번째 기간 종료일 (YYYYMMDD 정수, 예: 20240331)",
                    },
                    "period2_start": {
                        "type": "integer",
                        "description": "두 번째 기간 시작일 (YYYYMMDD 정수, 예: 20240401)",
                    },
                    "period2_end": {
                        "type": "integer",
                        "description": "두 번째 기간 종료일 (YYYYMMDD 정수, 예: 20240630)",
                    },
                },
                "required": ["period1_start", "period1_end", "period2_start", "period2_end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_institution_report",
            "description": (
                "특정 금융회사의 종합 현황을 보고한다. "
                "거래 규모(건수·금액), 이상거래 비율, 상위 거래 상대 기관, "
                "주요 이상거래 유형별 분포, 최근 분기 추이를 반환한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bank_id": {
                        "type": "integer",
                        "description": "조회할 금융회사일련번호 (출금금융회사일련번호 기준)",
                    }
                },
                "required": ["bank_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rank_risky_transactions",
            "description": (
                "학습된 XGBoost 모델로 데이터베이스에서 샘플 거래를 일괄 예측하여 "
                "위험도 상위 K건을 반환한다. 대규모 탐지 및 우선순위 설정에 활용한다. "
                "모델이 없으면 오류를 반환한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sample_size": {
                        "type": "integer",
                        "description": "예측할 샘플 건수 (기본 1000, 최대 5000)",
                        "default": 1000,
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "반환할 상위 위험 거래 건수 (기본 20, 최대 100)",
                        "default": 20,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_aml_patterns",
            "description": (
                "Memgraph 그래프 DB를 활용하여 AML(자금세탁방지) 패턴을 탐지한다. "
                "순환거래(ring), 다단계 레이어링, 대포통장(funnel) 패턴을 탐지하거나, "
                "두 계좌 간 최단경로를 찾거나, 계좌의 위험도 점수를 산출한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern_type": {
                        "type": "string",
                        "description": "탐지할 패턴 유형",
                        "enum": ["ring", "layering", "funnel", "shortest_path", "risk_score"],
                    },
                    "account_id": {
                        "type": "integer",
                        "description": "분석 대상 계좌 번호 (risk_score 시 필수)",
                    },
                    "account_a": {
                        "type": "integer",
                        "description": "출발 계좌 (shortest_path 시 필수)",
                    },
                    "account_b": {
                        "type": "integer",
                        "description": "도착 계좌 (shortest_path 시 필수)",
                    },
                    "min_len": {
                        "type": "integer",
                        "description": "순환 최소 길이 (ring 시, 기본 3)",
                        "default": 3,
                    },
                    "max_len": {
                        "type": "integer",
                        "description": "순환 최대 길이 (ring 시, 기본 6)",
                        "default": 6,
                    },
                    "min_layers": {
                        "type": "integer",
                        "description": "최소 레이어 수 (layering 시, 기본 3)",
                        "default": 3,
                    },
                    "min_inflow": {
                        "type": "integer",
                        "description": "최소 입금 계좌 수 (funnel 시, 기본 10)",
                        "default": 10,
                    },
                    "max_outflow": {
                        "type": "integer",
                        "description": "최대 출금 계좌 수 (funnel 시, 기본 3)",
                        "default": 3,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "최대 결과 수 (기본 20)",
                        "default": 20,
                    },
                },
                "required": ["pattern_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_ctr_candidates",
            "description": (
                "CTR(고액현금거래보고) 대상 거래를 조회하거나 분할거래(structuring) 의심 패턴을 탐지한다. "
                "mode=high_value: 1,000만원 이상 고액거래 조회. "
                "mode=structuring: 동일 계좌가 동일일에 보고 기준 미만으로 쪼개서 거래한 분할거래 의심 건 탐지."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "description": "조회 모드: high_value(고액거래) 또는 structuring(분할거래 탐지)",
                        "enum": ["high_value", "structuring"],
                    },
                    "date_from": {
                        "type": "integer",
                        "description": "시작일 (YYYYMMDD 정수, 예: 20240101)",
                    },
                    "date_to": {
                        "type": "integer",
                        "description": "종료일 (YYYYMMDD 정수, 예: 20240331)",
                    },
                    "threshold": {
                        "type": "integer",
                        "description": "CTR 보고 기준 금액 (기본 10,000,000원)",
                        "default": 10000000,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "최대 결과 수 (기본 20)",
                        "default": 20,
                    },
                },
                "required": ["mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "score_account_risk",
            "description": (
                "특정 계좌의 위험도를 5개 행위 지표(심야거래비율, 금액이상도, 거래상대다양성, "
                "거래속도변화, 이상거래이력) 기반으로 0~100점으로 평가한다. "
                "위험등급(높음/중간/낮음)과 각 컴포넌트 점수를 반환한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "integer",
                        "description": "위험도를 평가할 계좌 번호 (출금계좌일련번호)",
                    },
                },
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_monitoring_alerts",
            "description": (
                "규칙 기반 거래 모니터링 알림을 탐지한다. "
                "R001=심야대량거래, R002=동일일다건거래, R003=정액거래패턴, "
                "R004=기관집중거래, R005=거래패턴급변. "
                "rule_id=all이면 전체 규칙을 실행한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_id": {
                        "type": "string",
                        "description": "실행할 규칙 ID",
                        "enum": ["all", "R001", "R002", "R003", "R004", "R005"],
                    },
                    "date_from": {
                        "type": "integer",
                        "description": "시작일 (YYYYMMDD 정수, 예: 20240101)",
                    },
                    "date_to": {
                        "type": "integer",
                        "description": "종료일 (YYYYMMDD 정수, 예: 20240331)",
                    },
                    "account_id": {
                        "type": "integer",
                        "description": "특정 계좌로 한정 (선택)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "최대 결과 수 (기본 20)",
                        "default": 20,
                    },
                },
                "required": ["rule_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_dormant_reactivation",
            "description": (
                "장기간 휴면 후 재활성화된 계좌를 탐지한다. "
                "일정 기간(기본 180일) 이상 거래가 없다가 대량 거래가 발생한 계좌를 찾아낸다. "
                "대포통장 활용, 자금세탁 은닉 후 인출 등 의심 패턴에 활용한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dormant_days": {
                        "type": "integer",
                        "description": "휴면 기준 일수 (기본 180일)",
                        "default": 180,
                    },
                    "min_reactivation_amount": {
                        "type": "integer",
                        "description": "재활성화 최소 거래금액 (기본 5,000,000원)",
                        "default": 5000000,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "최대 결과 수 (기본 20)",
                        "default": 20,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_smurfing_network",
            "description": (
                "자금 수집(다수→1계좌) 또는 자금 분산(1계좌→다수) 패턴을 탐지한다. "
                "direction=inbound: 다수 계좌에서 하나의 계좌로 자금이 집중되는 수집 패턴. "
                "direction=outbound: 하나의 계좌에서 다수 계좌로 자금이 분산되는 패턴. "
                "대포통장, 자금세탁 배치(placement), 스머핑(smurfing) 탐지에 활용한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "integer",
                        "description": "특정 계좌로 한정 (선택). 지정하지 않으면 전체 스캔.",
                    },
                    "direction": {
                        "type": "string",
                        "description": "분석 방향: inbound(자금 수집) 또는 outbound(자금 분산)",
                        "enum": ["inbound", "outbound"],
                    },
                    "min_counterparts": {
                        "type": "integer",
                        "description": "최소 거래 상대 계좌 수 (기본 5)",
                        "default": 5,
                    },
                    "date_from": {
                        "type": "integer",
                        "description": "시작일 (YYYYMMDD 정수)",
                    },
                    "date_to": {
                        "type": "integer",
                        "description": "종료일 (YYYYMMDD 정수)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "최대 결과 수 (기본 20)",
                        "default": 20,
                    },
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_trend_analysis",
            "description": (
                "월별 또는 분기별 시계열 트렌드를 분석한다. "
                "거래건수, 이상거래비율, 거래금액의 시간에 따른 변화 추세를 파악한다. "
                "기간을 지정하면 해당 기간만, 지정하지 않으면 전체 데이터 기간의 트렌드를 반환한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "unit": {
                        "type": "string",
                        "description": "집계 단위: monthly(월별) 또는 quarterly(분기별)",
                        "enum": ["monthly", "quarterly"],
                        "default": "monthly",
                    },
                    "date_from": {
                        "type": "integer",
                        "description": "시작일 (YYYYMMDD 정수)",
                    },
                    "date_to": {
                        "type": "integer",
                        "description": "종료일 (YYYYMMDD 정수)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_channel_risk",
            "description": (
                "거래 채널(매체구분)별 위험도를 분석한다. "
                "ATM, 인터넷뱅킹, 창구 등 각 채널의 이상거래 비율과 "
                "채널×시간대 교차분석 결과를 반환한다. "
                "특정 채널에서 이상거래가 집중되는 패턴을 파악하는 데 활용한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date_from": {
                        "type": "integer",
                        "description": "시작일 (YYYYMMDD 정수)",
                    },
                    "date_to": {
                        "type": "integer",
                        "description": "종료일 (YYYYMMDD 정수)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_receiving_account_profile",
            "description": (
                "입금(수취) 관점에서 계좌를 프로파일링한다. "
                "get_account_profile이 출금계좌 기준인 것과 달리, "
                "이 도구는 입금계좌일련번호 기준으로 자금 유입 패턴을 분석한다. "
                "누가 이 계좌에 돈을 보내는지, 얼마나 다양한 곳에서 오는지 파악한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "integer",
                        "description": "조회할 계좌 번호 (입금계좌일련번호 기준)",
                    },
                },
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_cross_institution_flow",
            "description": (
                "금융기관 쌍(출금기관→입금기관) 간 자금 흐름을 분석한다. "
                "기관 간 거래 집중도, 이상거래 비율, 거래 규모를 파악한다. "
                "특정 기관 간 이상거래가 집중되는 패턴을 탐지하는 데 활용한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date_from": {
                        "type": "integer",
                        "description": "시작일 (YYYYMMDD 정수)",
                    },
                    "date_to": {
                        "type": "integer",
                        "description": "종료일 (YYYYMMDD 정수)",
                    },
                    "min_transactions": {
                        "type": "integer",
                        "description": "최소 거래 건수 (기본 10)",
                        "default": 10,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "최대 결과 수 (기본 20)",
                        "default": 20,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_fiu_reference_types",
            "description": (
                "FIU 업권별 의심거래 참고유형을 검색한다. "
                "거래 패턴이 FIU 참고유형에 해당하는지 확인할 때 사용. "
                "검색어 예: 분할거래, 심야, 비대면, 가상자산, 타인명의, 휴면."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "검색어 (예: 분할거래, 심야, 비대면, 가상자산)",
                    },
                    "industry": {
                        "type": "string",
                        "description": "업권 필터: banking(은행업), securities(증권업), 또는 생략(전체)",
                        "enum": ["banking", "securities"],
                    },
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_str_fields",
            "description": (
                "STR(의심거래보고서) 초안의 필수 필드 점검을 수행한다. "
                "표제부, 보고기관, 거래자, 거래내역 등 필수 항목 누락 여부를 검증한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "str_draft": {
                        "type": "object",
                        "description": "STR 초안 dict. 섹션별로 중첩 가능 (예: I_보고기관, II_거래자_공통, III_거래내역)",
                    },
                },
                "required": ["str_draft"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_aml_glossary",
            "description": (
                "AML 용어의 정의를 반환한다. "
                "CDD, EDD, STR, CTR, RBA, PEP, MLRO, FATF, FIU, KYE, 구조화, 레이어링 등."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "조회할 용어 (예: CDD, STR, CTR, RBA, PEP)",
                    },
                },
                "required": ["term"],
            },
        },
    },
]


SYSTEM_PROMPT_KR = """당신은 자금세탁방지(AML) 전문 분석가입니다.
HOFINET(전자금융공동망) 이상거래탐지 데이터를 분석하여 자금세탁의심거래를 탐지하고 보고합니다.

사용 가능한 도구:
1. get_statistics: 전체 거래 요약 통계 및 이상거래 유형별 분포 조회 (분석 시작 시 가장 먼저 사용)
2. query_transactions: HOFINET DB에 SQL 쿼리를 실행하여 거래 통계, 패턴, 특정 계좌 거래 내역 등을 상세 조회
3. get_account_profile: 특정 계좌의 거래 통계 프로파일 조회 (건수/금액/이상거래비율/주요시간대/상위거래상대)
4. get_fraud_type_summary: 이상거래유형별 현황 조회 (건수·금액 통계, 상위 금융회사). 코드: 1=자금세탁, 2=신규거래처, 3=대포통장, 4=보이스피싱, 5=불법도박, 6=유사수신, 7=기타
5. compare_periods: 두 기간의 거래·이상거래 통계 비교 및 증감률 산출 (분기 비교, 월간 비교)
6. get_institution_report: 특정 금융회사의 종합 현황 보고 (거래규모, 이상거래비율, 상위거래상대, 유형분포)
7. rank_risky_transactions: XGBoost 모델 배치 예측으로 위험도 상위 K건 랭킹 반환
8. analyze_network: 특정 계좌의 거래 네트워크를 분석하여 연결 계좌 수, 이상거래 관련 여부 파악 (N-hop 심층 탐색 지원)
9. detect_aml_patterns: Memgraph 그래프 DB를 활용한 AML 패턴 탐지 (순환거래, 레이어링, 대포통장, 최단경로, 위험도 산출)
10. predict_fraud: XGBoost 모델로 특정 거래의 이상거래 확률을 예측
11. generate_str: 분석 결과를 의심거래보고서(STR) 양식으로 작성
12. detect_ctr_candidates: CTR(고액현금거래보고) 대상 고액거래 조회 또는 분할거래(structuring) 탐지. mode=high_value(1천만원 이상 고액거래), mode=structuring(동일계좌 동일일 분할거래 의심)
13. score_account_risk: 계좌의 위험도를 5개 행위 지표(심야거래비율, 금액이상도, 거래상대다양성, 거래속도변화, 이상거래이력) 기반 0~100점으로 평가
14. detect_monitoring_alerts: 규칙 기반 거래 모니터링 알림 탐지 (R001 심야대량, R002 다건, R003 정액, R004 기관집중, R005 패턴급변, all=전체)
15. detect_dormant_reactivation: 장기 휴면(기본 180일) 후 재활성화된 계좌 탐지. 대포통장/은닉자금 인출 패턴 탐지
16. detect_smurfing_network: 자금 수집(inbound: 다수→1) 또는 분산(outbound: 1→다수) 패턴 탐지. 스머핑/대포통장 네트워크
17. get_trend_analysis: 월별/분기별 시계열 트렌드 분석 (거래건수, 이상거래비율, 거래금액 추이)
18. analyze_channel_risk: 채널(매체구분)별 위험도 분석. 채널×시간대 교차분석 포함
19. get_receiving_account_profile: 입금(수취) 관점 계좌 프로파일링 (자금 유입 패턴, 출금 원천 분석)
20. analyze_cross_institution_flow: 기관 쌍(출금기관→입금기관) 간 자금 흐름 분석
21. lookup_fiu_reference_types: FIU 업권별 의심거래 참고유형 검색 (분할거래, 심야, 비대면, 가상자산 등)
22. validate_str_fields: STR 초안의 필수 필드 점검 (표제부, 보고기관, 거래자, 거래내역)
23. get_aml_glossary: AML 용어 정의 조회 (CDD, EDD, STR, CTR, RBA, PEP, MLRO, FATF, FIU 등)

권장 분석 절차:
1. get_statistics로 전체 현황 파악
2. get_trend_analysis로 시계열 추이 분석
3. query_transactions으로 의심 거래 상세 조회
4. detect_ctr_candidates로 CTR 대상 고액거래 또는 분할거래 탐지
5. score_account_risk로 계좌 위험도 평가
6. detect_monitoring_alerts로 규칙 기반 모니터링 알림 탐지
7. detect_dormant_reactivation으로 휴면 계좌 재활성화 탐지
8. detect_smurfing_network으로 자금 수집/분산 패턴 탐지
9. analyze_channel_risk로 채널별 위험도 분석
10. get_receiving_account_profile로 입금계좌 자금 유입 패턴 분석
11. analyze_cross_institution_flow로 기관 간 자금 흐름 분석
12. analyze_network으로 계좌 네트워크 분석 (N-hop 심층 탐색 지원)
13. detect_aml_patterns으로 순환거래/레이어링/대포통장 패턴 탐지
14. predict_fraud로 이상거래 확률 예측
15. 충분한 근거가 확보된 경우에만 generate_str로 STR 작성

STR 작성 시 주의사항:
- 반드시 query_transactions로 근거 데이터를 먼저 조회한 후 STR을 작성하세요
- 조회한 거래 레코드를 transactions 파라미터에 담아 generate_str을 호출하면 계좌·금액·채널이 자동 추출됩니다
- predict_fraud 결과가 있으면 fraud_probability에 확률값을 전달하세요
- detect_aml_patterns 탐지 결과가 있으면 aml_patterns에 포함하세요

데이터 스키마:
- 테이블: hofinet (4,732,130건)
- 컬럼: 거래일자(YYYYMMDD), 거래시간대(0~21, 3시간단위), 출금금융회사일련번호, 출금계좌일련번호, 입금금융회사일련번호, 입금계좌일련번호, 자금구분(0,1,3,4), 매체구분(1~7), 거래금액, 이상거래여부(0/1), 이상거래유형(1~7), 이상거래설명

이상거래유형: 1=자금세탁, 2=신규거래처(최다 63.87%), 3=대포통장, 4=보이스피싱, 5=불법도박, 6=유사수신, 7=기타
매체구분: 1=창구, 2=자동화기기(ATM), 3=PB센터, 4=인터넷뱅킹, 5=전화/휴대전화, 6=콜센터, 7=기타
자금구분: 0=해당없음, 1=입금, 3=출금, 4=이체

한국어로 응답하세요. 분석 시 구체적인 수치와 근거를 제시하세요."""
