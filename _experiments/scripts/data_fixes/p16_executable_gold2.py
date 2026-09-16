"""Pass 16 - the last gold call that could not be executed (L1-016, D19).

`st_mtool_084` asked to rank the top 20 high-risk transactions and then analyse the
network of the account in first place, and its gold called `analyze_network` with no
`account_id`: executing it returns `{'error': 'account_id is required.'}`. It was the
only non-executable gold in the benchmark, the one self-test advisory and the one call
the platform harness skipped.

`rank_risky_transactions` scores a random sample, so the account in first place cannot
be pinned (that is why `p10_executable_gold` left the advisory). Dropping the second
call would turn the case into a plain `rank_risky_transactions` question, of which the
benchmark already has 55, so the account is named in the question instead: the case
stays a two-tool case, and both calls execute.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import AUDIT, ChangeLog, both, dump_json, load_json

CASE = "st_mtool_084"
ACCOUNT = 9000000000034076
KR = f"고위험 거래 20건을 랭킹하고, 계좌 {ACCOUNT}의 네트워크도 분석해줘"
EN = (f"Please rank the top 20 high-risk transactions and analyze the network of account "
      f"{ACCOUNT}.")
GOLD = {
    "primary_tool": "rank_risky_transactions",
    "tools_must_include": ["rank_risky_transactions", "analyze_network"],
    "param_checks": {
        "rank_risky_transactions": {"top_k": 20},
        "analyze_network": {"account_id": ACCOUNT},
    },
}
NOTE = (f"Expects rank_risky_transactions (top_k=20), analyze_network "
        f"(account_id={ACCOUNT}).")
WHY = ("analyze_network carried no account_id, so the gold call could not be executed; the "
       "account the question leaves to the first call's own result is named instead, which "
       "keeps the case a two-tool case (L1-016, D19).")

ALLOW_EMPTY = (Path(__file__).resolve().parents[2] / "scripts" / "preflight" / "allow_empty.json")


def drop_from_allow_list(log: ChangeLog) -> None:
    """The skip entry goes away with the defect it recorded."""
    entries = load_json(ALLOW_EMPTY)
    rows = entries["entries"] if isinstance(entries, dict) else entries
    keep = [e for e in rows if not (e.get("case_id") == CASE and e.get("status") == "skipped")]
    if len(keep) == len(rows):
        return
    entries["_why"] = entries["_why"].replace(
        "Gold calls that answer nothing, and the one that cannot be executed at all, listed",
        "Gold calls that answer nothing, listed")
    log.note(f"{ALLOW_EMPTY.name}: the skipped entry for {CASE} removed; the call executes now")
    if isinstance(entries, dict):
        entries["entries"] = keep
        dump_json(ALLOW_EMPTY, entries)
    else:
        dump_json(ALLOW_EMPTY, keep)


def main() -> int:
    kr, en = both()
    log = ChangeLog("p16_executable_gold2",
                    "The one gold call that could not be executed now carries its account "
                    "(L1-016, D19).")
    for bench, lang, text in ((kr, "kr", KR), (en, "en", EN)):
        case = bench.get(CASE)
        if case is None:
            raise SystemExit(f"{CASE}: absent from {bench.root.name}")
        log.set_field(case, lang, "question", text, "L1-016/D19", WHY)
        log.set_field(case, lang, "expected", copy.deepcopy(GOLD), "L1-016/D19", WHY)
        log.set_field(case, lang, "note", NOTE, "L1-016/D19", WHY)
    kr.save()
    en.save()
    drop_from_allow_list(log)
    print(log.report())
    print(f"log: {log.write()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
