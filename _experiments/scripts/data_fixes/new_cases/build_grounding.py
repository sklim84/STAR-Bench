"""Collect the HOFINET facts the new cases are written against (WS-G).

The authoring modules must not invent an account, an amount or a bank code, and a
reviewer has to be able to see where every value came from. This script reads
HOFINET and the platform catalog read-only and writes `grounding.json`: the STR
draft sources, the accounts picked per role, the FIU keywords that select rows,
and the fraud-type/institution pairs that carry data. The authoring pass then
replays that file without a database, the way `p04_accounts` replays
`account_map.json`.

    python -m _experiments.scripts.data_fixes.new_cases.build_grounding
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
    __package__ = "_experiments.scripts.data_fixes.new_cases"

from ..common import Bench, KR, dump_json

GROUNDING = Path(__file__).resolve().parent / "grounding.json"

STATS_SQL = """
WITH sent AS (
    SELECT sender_acc AS acc, COUNT(*)::BIGINT AS sent,
           COUNT(DISTINCT receiver_acc)::BIGINT AS out_cp,
           COALESCE(SUM(is_fraud), 0)::BIGINT AS sent_fraud
    FROM hofinet GROUP BY 1
), recv AS (
    SELECT receiver_acc AS acc, COUNT(*)::BIGINT AS recv,
           COUNT(DISTINCT sender_acc)::BIGINT AS in_cp,
           COALESCE(SUM(is_fraud), 0)::BIGINT AS recv_fraud
    FROM hofinet GROUP BY 1
)
SELECT acc, COALESCE(sent, 0) AS sent, COALESCE(out_cp, 0) AS out_cp,
       COALESCE(recv, 0) AS recv, COALESCE(in_cp, 0) AS in_cp,
       COALESCE(sent_fraud, 0) + COALESCE(recv_fraud, 0) AS fraud
FROM sent FULL OUTER JOIN recv USING (acc)
"""

# One STR draft per row: a real transfer pair, in a real window, with the real
# count and the real total for that pair and window.
STR_SQL = """
SELECT sender_acc, receiver_acc, sender_bank, receiver_bank, media_type, fraud_type,
       (date // 100) AS ym, COUNT(*)::BIGINT AS n, MIN(date) AS d0, MAX(date) AS d1,
       SUM(amount)::BIGINT AS total
FROM hofinet WHERE is_fraud = 1
GROUP BY 1, 2, 3, 4, 5, 6, 7
HAVING COUNT(*) >= 2
ORDER BY fraud_type, n DESC, sender_acc, receiver_acc
"""

FIU_KEYWORDS = [
    "structuring", "cash", "ATM", "gambling", "balance certificate", "virtual asset",
    "dormancy", "shell corporation", "borrowed names", "prepaid card", "internet banking",
    "minors", "stock", "representative", "wire transfer", "tax evasion", "split",
    "multiple accounts", "unknown counterparties", "third party", "Kimchi Premium",
    "corporate", "non-face-to-face", "24-hour", "others' names", "customer information",
    "price differences", "liquidation", "closure", "refusal", "unrelated to business",
]

# Roles the new cases need. Each entry: how many accounts, and the filter over the
# per-account statistics. The comment says which tool the role feeds.
ROLES = {
    # get_account_profile, score_account_risk, analyze_network: real outbound history
    "sender_active": dict(n=8, sent=(30, 300), out_cp=(10, 70), fraud=(1, None), recv=(None, None)),
    # get_receiving_account_profile: real inbound history with several senders
    "receiver_active": dict(n=8, recv=(40, 600), in_cp=(10, 80), fraud=(1, None), sent=(None, None)),
    # detect_smurfing_network direction=outbound
    "smurf_out": dict(n=6, sent=(20, 200), out_cp=(15, 60), fraud=(1, None), recv=(None, None)),
    # detect_smurfing_network direction=inbound
    "smurf_in": dict(n=6, recv=(20, 400), in_cp=(15, 60), fraud=(None, None), sent=(None, None)),
}


def stat_rows(query):
    return query(STATS_SQL).sort_values("acc").reset_index(drop=True)


def used_accounts() -> set[int]:
    """Accounts the existing cases already pin, so the new ones widen the coverage."""
    out = set()
    bench = Bench.load(KR, "kr")
    for _, case in bench.cases():
        for checks in (case["expected"].get("param_checks") or {}).values():
            if not isinstance(checks, dict):
                continue
            for key in ("account_id", "account_a", "account_b"):
                if isinstance(checks.get(key), int):
                    out.add(checks[key])
    return out


def pick_accounts(stats, used: set[int]) -> dict:
    free = stats[~stats.acc.isin(used)]
    picked: dict[str, list[dict]] = {}
    taken: set[int] = set()
    for role, spec in ROLES.items():
        frame = free
        for column in ("sent", "recv", "out_cp", "in_cp", "fraud"):
            low, high = spec.get(column, (None, None))
            if low is not None:
                frame = frame[frame[column] >= low]
            if high is not None:
                frame = frame[frame[column] <= high]
        frame = frame[~frame.acc.isin(taken)]
        order = "in_cp" if role.endswith("_in") or role.startswith("receiver") else "out_cp"
        frame = frame.sort_values([order, "fraud"], ascending=False)
        rows = []
        for row in frame.head(spec["n"]).itertuples():
            taken.add(int(row.acc))
            rows.append({"account_id": int(row.acc), "sent": int(row.sent), "out_cp": int(row.out_cp),
                         "recv": int(row.recv), "in_cp": int(row.in_cp), "fraud": int(row.fraud)})
        picked[role] = rows
    return picked


def pick_str_sources(query, per_type: int = 5) -> list[dict]:
    """Real transfer aggregates, round robin over the six fraud types.

    At most two per (fraud type, channel) and at most two per sending account, so the
    drafts do not all describe the same institution.
    """
    frame = query(STR_SQL)
    by_type: dict[int, list[dict]] = {}
    channel_seen: dict[tuple, int] = {}
    sender_seen: dict[int, int] = {}
    for row in frame.itertuples():
        fraud_type, media, sender = int(row.fraud_type), int(row.media_type), int(row.sender_acc)
        if int(row.d1) - int(row.d0) > 1200:  # a draft covers a reporting window, not three years
            continue
        if channel_seen.get((fraud_type, media), 0) >= 2 or sender_seen.get(sender, 0) >= 2:
            continue
        if len(by_type.get(fraud_type, [])) >= per_type:
            continue
        channel_seen[(fraud_type, media)] = channel_seen.get((fraud_type, media), 0) + 1
        sender_seen[sender] = sender_seen.get(sender, 0) + 1
        by_type.setdefault(fraud_type, []).append(
            {"sender_acc": sender, "receiver_acc": int(row.receiver_acc),
             "sender_bank": int(row.sender_bank), "receiver_bank": int(row.receiver_bank),
             "media_type": media, "fraud_type": fraud_type,
             "count": int(row.n), "date_from": int(row.d0), "date_to": int(row.d1),
             "total_amount": int(row.total)})
    return [row for fraud_type in sorted(by_type) for row in by_type[fraud_type]]


def monitoring_accounts(execute) -> dict:
    """One account per monitoring rule whose alert survives the account filter."""
    out: dict[str, list[int]] = {}
    for rule in ("R001", "R002", "R003", "R004", "R005"):
        payload = json.loads(execute("detect_monitoring_alerts", {"rule_id": rule, "limit": 10}))
        found = []
        for row in payload.get("result", []) or []:
            account = row.get("sender_acc") or row.get("account_id")
            if account is None:
                continue
            check = json.loads(execute("detect_monitoring_alerts",
                                       {"rule_id": rule, "account_id": int(account)}))
            if check.get("count") and int(account) not in found:
                found.append(int(account))
            if len(found) >= 3:
                break
        out[rule] = found
    return out


def funnel_accounts(query) -> dict:
    """The accounts the funnel scan finds at the tool defaults (HOFINET.MD section 7)."""
    rows = query("""
        WITH sent AS (SELECT sender_acc AS acc, COUNT(DISTINCT receiver_acc) AS out_cp FROM hofinet GROUP BY 1),
             recv AS (SELECT receiver_acc AS acc, COUNT(DISTINCT sender_acc) AS in_cp FROM hofinet GROUP BY 1)
        SELECT acc, in_cp, out_cp FROM sent JOIN recv USING (acc)
        WHERE in_cp >= 5 AND out_cp BETWEEN 1 AND 5 ORDER BY in_cp DESC
    """)
    return {"min_inflow": 5, "max_outflow": 5,
            "accounts": [{"account_id": int(r.acc), "in_cp": int(r.in_cp), "out_cp": int(r.out_cp)}
                         for r in rows.itertuples()]}


def main() -> int:
    from _experiments.scripts._platform import ensure_platform_on_path  # noqa: PLC0415

    root = ensure_platform_on_path()
    from src.data.db import query  # noqa: PLC0415
    from src.features.agent import _execute_tool  # noqa: PLC0415
    from src.features.aml_reference import (  # noqa: PLC0415
        glossary_terms, lookup_fiu_reference_types,
    )

    stats = stat_rows(query)
    used = used_accounts()

    fraud_bank = query("""
        SELECT fraud_type, sender_bank, COUNT(*)::BIGINT AS n FROM hofinet WHERE is_fraud = 1
        GROUP BY 1, 2 HAVING COUNT(*) >= 10 ORDER BY fraud_type, n DESC
    """)

    payload = {
        "source": {"platform": str(root), "database": str(Path(root) / "_datasets" / "HOFINET.duckdb")},
        "note": "Facts the 2026-09 expansion cases are written against. Rebuild with build_grounding.py.",
        "accounts": pick_accounts(stats, used),
        "monitoring_accounts": monitoring_accounts(_execute_tool),
        "funnel": funnel_accounts(query),
        "str_sources": pick_str_sources(query),
        "glossary_terms": glossary_terms(),
        "fiu_keywords": {k: {"all": len(lookup_fiu_reference_types(k)),
                             "banking": len(lookup_fiu_reference_types(k, "banking")),
                             "securities": len(lookup_fiu_reference_types(k, "securities"))}
                         for k in FIU_KEYWORDS},
        "fraud_type_by_bank": [{"fraud_type": int(r.fraud_type), "bank_id": int(r.sender_bank),
                                "n": int(r.n)} for r in fraud_bank.itertuples()],
    }
    dump_json(GROUNDING, payload)
    print(f"grounding: {GROUNDING}")
    for role, rows in payload["accounts"].items():
        print(f"  {role}: {len(rows)} accounts")
    print(f"  str_sources: {len(payload['str_sources'])}")
    print(f"  fiu_keywords: {sum(1 for v in payload['fiu_keywords'].values() if v['all'])} select rows")
    print(f"  fraud_type_by_bank: {len(payload['fraud_type_by_bank'])} pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
