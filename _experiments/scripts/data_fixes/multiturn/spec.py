"""The scenario description language the multi-turn rebuild is written in.

A scenario is a list of turns. A turn names the gold tool and the arguments the
gold call carries; the builder executes that call on the platform and stores the
real output as the turn's ``tool_result``. Nothing in the data is written by
hand, so a scenario cannot claim a number its own tool results do not carry.

``Ref`` is how a later turn reads a value out of an earlier turn's real result.
It is resolved at build time, so a ``context_ref`` always points at a value that
is really there, and the gold argument that receives it is really that value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Check keys that live in a gold `arguments` block but are not tool arguments.
CHECK_ONLY = {"sql_conditions", "sql_valid", "hops_min", "hops_max",
              "result_contains", "result_row_count_min", "result_row_count_max"}


@dataclass(frozen=True)
class Bi:
    """One gold argument whose value is written in the language of the question (D13).

    `generate_str` echoes its `summary` into the report it returns, so the two arms
    execute the call separately and each stores the report in its own language.
    """

    kr: str
    en: str


@dataclass(frozen=True)
class Ref:
    """A value read out of the executed result of an earlier turn."""

    turn: int
    path: str


# The FIU catalog and the AML glossary are English-only in the platform, and so is the
# notice detect_aml_patterns returns when a scan finds nothing. A Korean summary that
# pastes those sentences in is not Korean prose, so `{name:ko}` renders the Korean the
# row says (L2-012). The build fails on a value that is not in this table, so the
# rendering cannot drift away from the result it came from.
KO_SOURCE = {
    "Excessive number of transactions and bulk operations via internet banking throughout "
    "the day, including night/early morning hours":
        "심야·새벽을 포함해 하루 종일 인터넷뱅킹으로 거래 건수가 과다하거나 대량 이체가 이뤄지는 유형",
    "Transactions split among multiple people or structured below threshold to avoid "
    "reporting (structuring)":
        "보고를 피하려고 여러 사람에게 나누거나 기준 금액 아래로 쪼개 거래하는 유형(structuring)",
    "Depositing large funds, issuing a balance certificate, and withdrawing the full amount "
    "the next day":
        "거액을 입금한 뒤 잔액증명서를 발급받고 다음 날 전액을 인출하는 유형",
    "24-hour bulk transactions via internet banking with parties unrelated to business":
        "업무와 관계없는 상대와 인터넷뱅킹으로 24시간 대량 거래를 하는 유형",
    "Transferring funds received from unknown counterparties to a third party":
        "출처를 알 수 없는 상대에게서 받은 자금을 제3자에게 다시 이체하는 유형",
    "Non-face-to-face": "비대면",
    "Creating complex transaction paths to conceal the source of funds. The second stage of "
    "money laundering.":
        "자금 출처를 숨기려고 복잡한 거래 경로를 만드는 행위이며 자금세탁의 두 번째 단계다",
    "Dividing cash transactions below the reporting threshold to avoid CTR. Subject to STR "
    "reporting.":
        "CTR 보고를 피하려고 현금 거래를 보고 기준 미만으로 나누는 행위이며 STR 보고 대상이다",
    "No chain of 3 or more consecutive fraud transfers found. The longest such chain in "
    "HOFINET is 2 transfers.":
        "연속된 이상거래 이체가 3단계 이상인 사슬은 없고 HOFINET에서 가장 긴 사슬은 2단계다",
}


@dataclass
class Turn:
    kr: str                       # the user's message, Korean
    en: str                       # the same message in English
    tool: str | None = None       # gold tool, None for a clarification or a no-tool turn
    args: dict = field(default_factory=dict)   # gold arguments (parameter checks)
    sql: str | None = None        # executable reference SQL for query_transactions
    conds: list[tuple] = field(default_factory=list)   # (column, op, value) sql_conditions
    ctx: tuple | None = None      # (from_turn, path, to_param)
    bind: dict = field(default_factory=dict)   # name -> Ref, read from THIS turn's result
    clarify: bool = False         # asking back is the correct behaviour (D19)
    abstain: bool = False         # answering without a tool call is correct
    point_kr: str = ""            # what the turn tests, for the note
    point_en: str = ""


@dataclass
class Scenario:
    id: str
    sub: str                      # base | missing_parameter | long_context
    ft: int                       # HOFINET fraud type the scenario concludes on
    kr: str                       # one-line scenario description
    en: str
    turns: list[Turn]
    vars: dict = field(default_factory=dict)   # literals the turn texts and gold share
    why: str = ""                 # why these entities carry this story (report + changelog)


# HOFINET fraud types, as the platform names them.
FRAUD_TYPE_KR = {
    1: "갑작스러운 거래패턴의 변화",
    2: "신규 수신처 거래",
    3: "분할 거래",
    4: "다중거래의 동시 요청",
    5: "거액 입금 후 당일 인출",
    7: "심야/새벽 대량 거래",
}

FRAUD_TYPE_EN = {
    1: "Sudden Change in Transaction Pattern",
    2: "Transaction with New Counterparty",
    3: "Split Transaction",
    4: "Concurrent Multiple Transactions",
    5: "Same-Day Withdrawal after Large Deposit",
    7: "Late-Night/Early-Morning Bulk Transactions",
}

# HOFINET type -> the STR form §VI classification `generate_str` accepts
# (_datasets/HOFINET.MD §4.2). Types 2 and 7 map to the form's catch-all.
STR_SECTION_VI = {
    1: "갑작스러운 거래패턴의 변화",
    2: "기타(자유기술)",
    3: "분할거래",
    4: "다중거래의 동시요청",
    5: "거액 입금 후 당일/익일 인출",
    7: "기타(자유기술)",
}

# HOFINET media_type -> channel name, as `analyze_channel_risk` returns it.
MEDIA_KR = {1: "PC뱅킹", 2: "인터넷뱅킹", 3: "전화", 4: "휴대전화",
            5: "건별이체", 6: "기타", 7: "대량이체"}
MEDIA_EN = {1: "PC Banking", 2: "Internet Banking", 3: "Phone", 4: "Mobile Phone",
            5: "Per-transaction Transfer", 6: "Other", 7: "Bulk Transfer"}

# Transaction time slots are 3-hour buckets; 21, 0 and 3 are the night slots the
# R001 monitoring rule covers.
SLOT_KR = {0: "0~3시", 3: "3~6시", 6: "6~9시", 9: "9~12시",
           12: "12~15시", 15: "15~18시", 18: "18~21시", 21: "21~24시"}
