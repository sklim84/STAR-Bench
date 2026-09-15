"""Pass 01 - apply the approved single-turn fix table v3 (register K4).

`fix_table_data.json` holds, per case, the as-is question and gold and the
approved to-be values: `kr_tobe` for the Korean question, `en_tobe` for the
English one and `gold_tobe` for the shared `expected` block. The pass refuses to
run when an as-is value no longer matches the data, so a later pass can never be
silently overwritten by an earlier fix table.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import AUDIT, Bench, ChangeLog, both, load_json

FIX_TABLE = AUDIT / "fix_table_data.json"


def verify_asis(kr: Bench, en: Bench, cases: list[dict]) -> list[str]:
    kr_by, en_by = kr.by_id(), en.by_id()
    stale = []
    for entry in cases:
        cid = entry["id"]
        k, e = kr_by.get(cid), en_by.get(cid)
        if k is None or e is None:
            stale.append(f"{cid}: absent from the benchmark")
            continue
        if entry.get("kr_tobe") and k["question"] != entry["kr_asis"]:
            stale.append(f"{cid}: KR question is not the v3 as-is")
        if entry.get("en_tobe") and e["question"] != entry["en_asis"]:
            stale.append(f"{cid}: EN question is not the v3 as-is")
        if entry.get("gold_tobe") and k["expected"] != entry["gold_asis"]:
            stale.append(f"{cid}: gold is not the v3 as-is")
    return stale


def apply(kr: Bench, en: Bench, log: ChangeLog) -> None:
    table = load_json(FIX_TABLE)
    cases = table["cases"]
    stale = verify_asis(kr, en, cases)
    if stale:
        raise SystemExit("fix table v3 does not match the data:\n  " + "\n  ".join(stale))
    kr_by, en_by = kr.by_id(), en.by_id()
    for entry in cases:
        cid = entry["id"]
        groups = "+".join(entry["groups"])
        why = " ".join(entry["reasons"])
        if entry.get("kr_tobe"):
            log.set_field(kr_by[cid], "kr", "question", entry["kr_tobe"], f"K4/{groups}", why)
        if entry.get("en_tobe"):
            log.set_field(en_by[cid], "en", "question", entry["en_tobe"], f"K4/{groups}", why)
        if entry.get("gold_tobe"):
            log.set_field(kr_by[cid], "kr", "expected", entry["gold_tobe"], f"K4/{groups}", why)
            log.set_field(en_by[cid], "en", "expected", entry["gold_tobe"], f"K4/{groups}", why)
    log.note(f"fix table v3: {len(cases)} cases reviewed, "
             f"{sum(1 for c in cases if c.get('kr_tobe'))} KR questions, "
             f"{sum(1 for c in cases if c.get('en_tobe'))} EN questions, "
             f"{sum(1 for c in cases if c.get('gold_tobe'))} golds to-be")


def main() -> int:
    kr, en = both()
    log = ChangeLog("p01_apply_v3", "Approved fix table v3 applied to the KR and EN single-turn data (K4).")
    apply(kr, en, log)
    kr.save()
    en.save()
    print(log.report())
    print(f"log: {log.write()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
