"""Build the account map: one real HOFINET account per account id a question names.

Every account a question names has to be an account HOFINET holds, and it has to
carry the history the question presumes. An id that is not in the data makes every
account-level gold call return an empty result and every "that account" premise
false, so no model can reproduce the gold.

This script reads HOFINET read-only, collects the role each account id has to play
(sender history, receiver history, a neighbourhood, enough counterparties for a
smurfing threshold, fraud history behind "high-risk" wording, a real path to its
partner in a shortest_path case) and picks one real account per id that satisfies
every role it appears in. The result is committed as ``account_map.json``, so the
assignment can be read and checked without a database.

    python -m _experiments.scripts.data_fixes.build_account_map
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, KR, dump_json

MAP_PATH = Path(__file__).resolve().parent / "account_map.json"
ACCOUNT_KEYS = ("account_id", "account_a", "account_b")
# Wording that presumes the account has something suspicious about it.
RISKY = re.compile(r"위험|의심|이상거래|고위험|자금세탁|대포통장|보이스피싱|사기|스머핑|알림")

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
SELECT acc,
       COALESCE(sent, 0) AS sent, COALESCE(out_cp, 0) AS out_cp,
       COALESCE(recv, 0) AS recv, COALESCE(in_cp, 0) AS in_cp,
       COALESCE(sent_fraud, 0) + COALESCE(recv_fraud, 0) AS fraud
FROM sent FULL OUTER JOIN recv USING (acc)
"""


def requirements(bench: Bench) -> tuple[dict[int, dict], list[dict]]:
    """Role requirements per invented account id, and the shortest_path pairs."""
    need: dict[int, dict] = defaultdict(lambda: {"roles": set(), "smurf_in": 0, "smurf_out": 0,
                                                 "hops": 1, "uses": 0, "cases": []})
    pairs = []
    for _, case in bench.cases():
        risky = bool(RISKY.search(case["question"]))
        for tool, checks in (case["expected"].get("param_checks") or {}).items():
            if not isinstance(checks, dict):
                continue
            ids = {k: v for k, v in checks.items() if k in ACCOUNT_KEYS}
            if not ids:
                continue
            pattern, direction = checks.get("pattern_type"), checks.get("direction")
            counterparts = int(checks.get("min_counterparts") or 5)
            hops = int(checks.get("hops_min") or checks.get("hops_max") or 1)
            for key, value in ids.items():
                entry = need[value]
                entry["uses"] += 1
                entry["cases"].append(f"{case['id']}.{tool}.{key}")
                if risky:
                    entry["roles"].add("fraud")
                if tool in ("get_account_profile", "score_account_risk"):
                    entry["roles"].add("sender")
                elif tool == "get_receiving_account_profile":
                    entry["roles"].add("receiver")
                elif tool == "analyze_network":
                    entry["roles"].add("network")
                    entry["hops"] = max(entry["hops"], hops)
                elif tool == "detect_smurfing_network":
                    if direction == "outbound":
                        entry["roles"].add("smurf_out")
                        entry["smurf_out"] = max(entry["smurf_out"], counterparts)
                    else:
                        entry["roles"].add("smurf_in")
                        entry["smurf_in"] = max(entry["smurf_in"], counterparts)
                elif tool == "detect_aml_patterns":
                    if pattern == "risk_score":
                        entry["roles"].add("history")
                    elif pattern == "shortest_path":
                        entry["roles"].add("path")
            if pattern == "shortest_path" and "account_a" in ids and "account_b" in ids:
                pairs.append({"case_id": case["id"], "a": ids["account_a"], "b": ids["account_b"]})
    # Accounts named in the question text but never in the gold. Only numbers introduced as an
    # account are taken, so a date or an amount is never mistaken for one.
    account_run = re.compile(r"계좌(?:번호)?\s*((?:\d{8,16})(?:\s*(?:,|와|과|및)\s*\d{8,16})*)")
    for _, case in bench.cases():
        risky = bool(RISKY.search(case["question"]))
        tokens = [t for run in account_run.findall(case["question"]) for t in re.findall(r"\d{8,16}", run)]
        for token in tokens:
            value = int(token)
            if value in need:
                continue
            need[value]["uses"] += 1
            need[value]["cases"].append(f"{case['id']}.question")
            need[value]["roles"].add("sender")
            if risky:
                need[value]["roles"].add("fraud")
    return {k: {**v, "roles": sorted(v["roles"])} for k, v in need.items()}, pairs


def fits(row, req: dict, floor: int = 10) -> bool:
    """``floor`` is the minimum activity that keeps the gold answer substantial.

    It is relaxed to 1 for the few ids whose combined roles no busy account satisfies.
    """
    roles = set(req["roles"])
    if "sender" in roles and row.sent < floor:
        return False
    if "receiver" in roles and row.recv < floor:
        return False
    if "history" in roles and row.sent + row.recv < floor:
        return False
    if "fraud" in roles and row.fraud < 1:
        return False
    if "smurf_in" in roles and row.in_cp < req["smurf_in"]:
        return False
    if "smurf_out" in roles and row.out_cp < req["smurf_out"]:
        return False
    if "path" in roles and (row.out_cp < 3 or row.in_cp < 3 or row.out_cp + row.in_cp < 20):
        # A thin or one-directional account sits where the bidirectional search cannot cross.
        return False
    if "network" in roles:
        degree = row.out_cp + row.in_cp
        if degree < 3:
            return False
        # A deep ego walk on a hub would expand into most of the graph.
        if req["hops"] >= 3 and degree > 80:
            return False
    return True


def largest_component(query) -> set[int]:
    """Account ids of the biggest weakly connected component of the transfer graph.

    HOFINET splits into two components of almost the same size, so two accounts picked
    independently have an even chance of having no transfer path at all.
    """
    import numpy as np  # noqa: PLC0415

    edges = query("SELECT DISTINCT sender_acc AS s, receiver_acc AS r FROM hofinet")
    nodes = np.unique(np.concatenate([edges.s.to_numpy(), edges.r.to_numpy()]))
    index = {int(v): i for i, v in enumerate(nodes)}
    parent = list(range(len(nodes)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in zip(edges.s.to_numpy(), edges.r.to_numpy()):
        ra, rb = find(index[int(a)]), find(index[int(b)])
        if ra != rb:
            parent[ra] = rb
    roots = [find(i) for i in range(len(nodes))]
    from collections import Counter  # noqa: PLC0415

    top = Counter(roots).most_common(1)[0][0]
    return {int(nodes[i]) for i in range(len(nodes)) if roots[i] == top}


def difficulty(req: dict) -> tuple:
    return (-len(req["roles"]), -max(req["smurf_in"], req["smurf_out"]), -req["hops"], -req["uses"])


def main() -> int:
    from _experiments.scripts._platform import ensure_platform_on_path  # noqa: PLC0415

    root = ensure_platform_on_path()
    db = Path(root) / "_datasets" / "transactions.duckdb"
    from src.data.db import query  # noqa: PLC0415

    stats = query(STATS_SQL).sort_values("acc").reset_index(drop=True)

    bench = Bench.load(KR, "kr")
    need, pairs = requirements(bench)
    if any(f > 10 ** 12 for f in need):
        raise SystemExit("the benchmark already carries HOFINET account ids; the map is derived "
                         "from the ids the questions name, so rebuilding it here would remap "
                         "accounts that are already correct")
    print(f"{len(need)} invented account ids, {len(pairs)} shortest_path pairs")

    # Candidates: prefer accounts that are neither the busiest nor the thinnest, so a
    # gold call returns a readable result and a deep walk still terminates.
    stats["degree"] = stats.out_cp + stats.in_cp
    order = stats.sort_values(["degree", "acc"]).itertuples(index=False)
    candidates = list(order)

    component = largest_component(query)
    print(f"largest transfer component: {len(component)} accounts")

    taken: set[int] = set()
    chosen: dict[int, dict] = {}

    relaxed: list[int] = []

    def allocate(fake: int, pool, floor: int = 10) -> bool:
        req = need[fake]
        for row in pool:
            if row.acc in taken or not fits(row, req, floor):
                continue
            taken.add(row.acc)
            chosen[fake] = {"real": int(row.acc), "roles": req["roles"], "uses": req["uses"],
                            "sent": int(row.sent), "recv": int(row.recv), "out_cp": int(row.out_cp),
                            "in_cp": int(row.in_cp), "fraud": int(row.fraud), "cases": req["cases"]}
            return True
        return False

    path_ids = sorted({p["a"] for p in pairs} | {p["b"] for p in pairs},
                      key=lambda f: (difficulty(need[f]), f))
    for fake in path_ids:
        pool = [row for row in candidates if int(row.acc) in component]
        if allocate(fake, pool):
            continue
        if not allocate(fake, pool, floor=1):
            raise SystemExit(f"no connected HOFINET account satisfies {fake} ({need[fake]['roles']})")
        relaxed.append(fake)
    for fake in sorted(need, key=lambda f: (difficulty(need[f]), f)):
        if fake in chosen or allocate(fake, candidates):
            continue
        if not allocate(fake, candidates, floor=1):
            raise SystemExit(f"no HOFINET account satisfies {fake} ({need[fake]['roles']})")
        relaxed.append(fake)

    # shortest_path: the pair has to be connected, so repair the looser end when it is not.
    from src.features.network import find_shortest_path  # noqa: PLC0415

    repaired = []
    for attempt in range(6):
        broken = []
        for pair in pairs:
            a, b = chosen[pair["a"]]["real"], chosen[pair["b"]]["real"]
            result = find_shortest_path(a, b, max_hops=6)
            pair.update(real_a=a, real_b=b, hops=result["hops"] if result["path"] else None)
            if not result["path"]:
                broken.append(pair)
        if not broken:
            break
        # Repairing one pair can break a pair that shares an account, so repeat until stable.
        for pair in broken:
            loose = pair["b"] if need[pair["b"]]["uses"] <= need[pair["a"]]["uses"] else pair["a"]
            anchor = chosen[pair["a"]]["real"] if loose == pair["b"] else chosen[pair["b"]]["real"]
            replacement, tried = None, 0
            for row in candidates:
                if int(row.acc) in taken or int(row.acc) not in component:
                    continue
                if not fits(row, need[loose], floor=1):
                    continue
                tried += 1
                if tried > 300:
                    break
                if find_shortest_path(anchor, int(row.acc), max_hops=6)["path"]:
                    replacement = int(row.acc)
                    break
            if replacement is None:
                raise SystemExit(f"{pair['case_id']}: no connected partner for {loose}")
            taken.discard(chosen[loose]["real"])
            taken.add(replacement)
            row = stats[stats.acc == replacement].iloc[0]
            chosen[loose].update(real=int(replacement), sent=int(row.sent), recv=int(row.recv),
                                 out_cp=int(row.out_cp), in_cp=int(row.in_cp), fraud=int(row.fraud),
                                 repaired_for=pair["case_id"])
            repaired.append(loose)
    else:
        raise SystemExit(f"shortest_path pairs did not settle: {[p['case_id'] for p in broken]}")

    payload = {
        "source": {"database": str(db), "sha256": hashlib.sha256(db.read_bytes()).hexdigest(),
                   "benchmark": str(KR)},
        "rule": ("one real account per invented id, satisfying every role the id plays; candidates are "
                 "ordered by degree so a gold call returns a readable result and a deep ego walk "
                 "terminates; shortest_path pairs are repaired until a path of at most 6 hops exists"),
        "n_accounts": len(chosen),
        "relaxed_activity_floor": sorted(relaxed),
        "repaired_for_path": sorted(repaired),
        "map": {str(k): v for k, v in sorted(chosen.items())},
        "shortest_path_pairs": pairs,
    }
    dump_json(MAP_PATH, payload)
    print(f"map: {MAP_PATH}")
    print(f"path pairs: {[ (p['case_id'], p['hops']) for p in pairs ]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
