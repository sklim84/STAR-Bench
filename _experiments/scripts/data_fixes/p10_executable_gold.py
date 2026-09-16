"""Pass 10 - make every remaining gold call executable (L1-016, D19).

The gold self-test lists a gold call that omits a schema-required argument as an
advisory: the call cannot be executed, so it produces no oracle result and the
question does not pin the value down. Five multi-tool cases asked for a smurfing
network without a direction, one CTR case asked for two modes in one call, and
two chain cases left the account of the second call unpinned.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both

DIRECTION_WHY = ("detect_smurfing_network requires `direction`, and the question named none, so the "
                 "gold call could not be executed and the near-identical st_mp_009 is a clarification "
                 "case for exactly that gap (L1-016)")

EDITS = {
    "st_ctr_041": ("감독 기관에 미보고될 위험이 있는 거래를 사전에 걸러내야 해. 보고 기준 미만으로 쪼갠 구조화 의심 건을 확인해줘",
                   "We need to filter out transactions that risk going unreported to the regulator. "
                   "Please check for suspected structuring, split below the reporting threshold.",
                   {"primary_tool": "detect_ctr_candidates", "tools_must_include": ["detect_ctr_candidates"],
                    "param_checks": {"detect_ctr_candidates": {"mode": "structuring"}}},
                   "`mode` is required and the question asked for both values, which one call cannot "
                   "deliver; st_ctr_042 carries the high-value half"),
    "st_mtool_034": ("입금이 한 계좌로 모이는(inbound) 스머핑 네트워크를 탐지하고 전체 통계도 확인해줘",
                     "Please detect the inbound smurfing network, where funds collect into one account, "
                     "and also check the overall statistics.",
                     {"primary_tool": "detect_smurfing_network",
                      "tools_must_include": ["detect_smurfing_network", "get_statistics"],
                      "param_checks": {"detect_smurfing_network": {"direction": "inbound"}}},
                     DIRECTION_WHY),
    "st_mtool_039": ("입금이 모이는(inbound) 스머핑 네트워크를 탐지하고, 입금 상대가 많고 출금이 소수인 funnel 패턴도 함께 탐지해줘",
                     "Please detect the inbound smurfing network and also the funnel pattern with many "
                     "incoming and few outgoing counterparties.",
                     {"primary_tool": "detect_smurfing_network",
                      "tools_must_include": ["detect_smurfing_network", "detect_aml_patterns"],
                      "param_checks": {"detect_smurfing_network": {"direction": "inbound"},
                                       "detect_aml_patterns": {"pattern_type": "funnel"}}},
                     DIRECTION_WHY + "; the mule-account wording also blurred the funnel boundary (L1-003)"),
    "st_mtool_042": ("채널별 위험도를 분석하고, 고액거래를 CTR 대상으로 탐지하고, 입금이 모이는(inbound) 스머핑 네트워크도 탐지해줘",
                     "Analyze the risk by channel, detect high-value transactions as CTR candidates, and "
                     "also detect the inbound smurfing network.",
                     {"primary_tool": "analyze_channel_risk",
                      "tools_must_include": ["analyze_channel_risk", "detect_ctr_candidates",
                                             "detect_smurfing_network"],
                      "tool_order": ["analyze_channel_risk", "detect_ctr_candidates",
                                     "detect_smurfing_network"],
                      "param_checks": {"detect_ctr_candidates": {"mode": "high_value"},
                                       "detect_smurfing_network": {"direction": "inbound"}}},
                     DIRECTION_WHY),
    "st_mtool_045": ("휴면계좌 재활성화를 탐지하고, 입금이 모이는(inbound) 스머핑 네트워크도 함께 탐지해줘",
                     "Detect dormant account reactivations and also the inbound smurfing network.",
                     {"primary_tool": "detect_dormant_reactivation",
                      "tools_must_include": ["detect_dormant_reactivation", "detect_smurfing_network"],
                      "tool_order": ["detect_dormant_reactivation", "detect_smurfing_network"],
                      "param_checks": {"detect_smurfing_network": {"direction": "inbound"}}},
                     DIRECTION_WHY),
    "st_mtool_052": ("입금이 모이는(inbound) 스머핑 네트워크를 탐지하고, 탐지 결과를 바탕으로 계좌 9000000004388203의 위험도도 평가해줘",
                     "Detect the inbound smurfing network and, from what it finds, assess the risk of "
                     "account 9000000004388203.",
                     {"primary_tool": "detect_smurfing_network",
                      "tools_must_include": ["detect_smurfing_network", "score_account_risk"],
                      "tool_order": ["detect_smurfing_network", "score_account_risk"],
                      "param_checks": {"detect_smurfing_network": {"direction": "inbound"},
                                       "score_account_risk": {"account_id": 9000000004388203}}},
                     DIRECTION_WHY),
    "st_mtool_068": (None, None,
                     {"primary_tool": "detect_aml_patterns",
                      "tools_must_include": ["detect_aml_patterns", "score_account_risk"],
                      "param_checks": {"detect_aml_patterns": {"pattern_type": "shortest_path",
                                                               "account_a": 9000000000022515,
                                                               "account_b": 9000000000026712},
                                       "score_account_risk": {"account_id": 9000000000022515}},
                      "alternatives": [
                          {"tools_must_include": ["detect_aml_patterns", "score_account_risk"],
                           "param_checks": {"detect_aml_patterns": {"pattern_type": "shortest_path",
                                                                    "account_a": 9000000000022515,
                                                                    "account_b": 9000000000026712},
                                            "score_account_risk": {"account_id": 9000000000026712}}}]},
                     "score_account_risk requires account_id and the question names two accounts, so "
                     "either one is a correct call; the gold now pins one and accepts the other"),
    "st_mtool_001": (None, None,
                     {"primary_tool": "query_transactions",
                      "tools_must_include": ["query_transactions", "analyze_network"],
                      "tool_order": ["query_transactions", "analyze_network"],
                      "param_checks": {
                          "query_transactions": {
                              "sql_conditions": [{"column": "sender_bank", "op": "=", "value": 134},
                                                 {"column": "is_fraud", "op": "=", "value": 1}],
                              "sql_valid": True},
                          "analyze_network": {"account_id": 9000000000017028}},
                      "reference_calls": {"query_transactions": {
                          "sql": "SELECT sender_acc, COUNT(*) AS fraud_count FROM hofinet "
                                 "WHERE sender_bank = 134 AND is_fraud = 1 GROUP BY sender_acc "
                                 "ORDER BY fraud_count DESC LIMIT 10"}}},
                     "the second call's account comes from the first call's result; the reference SQL "
                     "returns 9000000000017028 (98 flagged transfers), so the chain is now checkable "
                     "and the gold call executable"),
}


def apply(kr: Bench, en: Bench, log: ChangeLog) -> None:
    kr_by, en_by = kr.by_id(), en.by_id()
    for case_id, (kr_text, en_text, gold, why) in EDITS.items():
        for bench_by, lang, text in ((kr_by, "kr", kr_text), (en_by, "en", en_text)):
            case = bench_by[case_id]
            if text:
                log.set_field(case, lang, "question", text, "L1-016/D19", why)
            log.set_field(case, lang, "expected", copy.deepcopy(gold), "L1-016/D19", why)
    log.note("st_mtool_084 keeps its advisory: the account of the second call is the top row of a "
             "rank_risky_transactions sample, which is not stable enough to pin")


def main() -> int:
    kr, en = both()
    log = ChangeLog("p10_executable_gold", "Pin the required arguments the gold calls still omitted "
                                           "(L1-016, D19).")
    apply(kr, en, log)
    kr.save()
    en.save()
    print(log.report())
    for n in log.notes:
        print("  " + n)
    print(f"log: {log.write()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
