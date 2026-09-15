"""Pass 04 - put real HOFINET accounts into the questions and the gold (D03, L3-007).

`account_map.json` (built by `build_account_map.py` against the database) says
which real account replaces each invented one and why it fits the role. This
pass only replays that map: it rewrites the account numbers in the KR and EN
question text and in every `account_id` / `account_a` / `account_b` gold check,
and refuses to finish if a mapped id survives anywhere.
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both, load_json

MAP_PATH = Path(__file__).resolve().parent / "account_map.json"
ACCOUNT_KEYS = ("account_id", "account_a", "account_b")


def spelling(fake: int) -> re.Pattern:
    """Matches the id as written, including a zero-padded form such as 0022884466."""
    return re.compile(r"(?<![\d.])0*" + str(fake) + r"(?!\d)")


def substitute(text: str, mapping: dict[int, int]) -> tuple[str, list[int]]:
    hit = []
    for fake in sorted(mapping, reverse=True):
        pattern = spelling(fake)
        if pattern.search(text):
            text = pattern.sub(str(mapping[fake]), text)
            hit.append(fake)
    return text, hit


def apply(kr: Bench, en: Bench, log: ChangeLog) -> dict:
    payload = load_json(MAP_PATH)
    mapping = {int(k): v["real"] for k, v in payload["map"].items()}
    evidence = {int(k): v for k, v in payload["map"].items()}
    why_of = {}
    for fake, entry in evidence.items():
        why_of[fake] = (f"invented account {fake} is not in HOFINET, so the gold call returned an empty "
                        f"result; {entry['real']} plays the same role "
                        f"({', '.join(entry['roles'])}: {entry['sent']} sent, {entry['recv']} received, "
                        f"{entry['out_cp']} outgoing and {entry['in_cp']} incoming counterparties, "
                        f"{entry['fraud']} flagged)")
    touched = {"question": 0, "gold": 0}
    for bench in (kr, en):
        for _, case in bench.cases():
            text, hit = substitute(case["question"], mapping)
            if hit:
                log.set_field(case, bench.lang, "question", text, "L3-007/D03",
                              " | ".join(why_of[f] for f in hit))
                touched["question"] += 1
            checks = case["expected"].get("param_checks") or {}
            changed = []
            before = copy.deepcopy(case["expected"])
            for spec in checks.values():
                if not isinstance(spec, dict):
                    continue
                for key in ACCOUNT_KEYS:
                    if key in spec and spec[key] in mapping:
                        changed.append(spec[key])
                        spec[key] = mapping[spec[key]]
                # A SQL substring check can name an account too.
                terms = spec.get("sql_contains")
                if isinstance(terms, list):
                    for i, term in enumerate(terms):
                        if str(term).isdigit() and int(term) in mapping:
                            changed.append(int(term))
                            terms[i] = str(mapping[int(term)])
            if changed:
                log.record(case["id"], bench.lang, "expected", before, case["expected"], "L3-007/D03",
                           " | ".join(why_of[f] for f in changed))
                touched["gold"] += 1
    leftovers = []
    for bench in (kr, en):
        for _, case in bench.cases():
            for fake in mapping:
                if spelling(fake).search(case["question"]):
                    leftovers.append(f"{case['id']} ({bench.lang}) still names {fake}")
            for spec in (case["expected"].get("param_checks") or {}).values():
                if not isinstance(spec, dict):
                    continue
                if any(spec.get(k) in mapping for k in ACCOUNT_KEYS):
                    leftovers.append(f"{case['id']} ({bench.lang}) gold still uses an invented account")
                terms = spec.get("sql_contains") or []
                if any(str(t).isdigit() and int(t) in mapping for t in terms):
                    leftovers.append(f"{case['id']} ({bench.lang}) gold SQL check still names an invented account")
    if leftovers:
        raise SystemExit("invented accounts survived:\n  " + "\n  ".join(leftovers))
    log.note(f"{len(mapping)} invented account ids replaced by real HOFINET accounts; "
             f"{touched['question']} question texts and {touched['gold']} gold blocks changed")
    log.note(f"activity floor relaxed for {payload['relaxed_activity_floor']}; "
             f"re-picked so a shortest_path pair is connected: {payload['repaired_for_path']}")
    return payload


def main() -> int:
    kr, en = both()
    log = ChangeLog("p04_accounts", "Replace every invented account id with a role-appropriate real "
                                    "HOFINET account (D03, L3-007).")
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
