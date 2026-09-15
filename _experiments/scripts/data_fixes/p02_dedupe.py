"""Pass 02 - delete the `*_ex01..08` duplicate cases (D09, L1-023).

143 cases repeat the question and the gold of the `*_001` case of the same file,
so 19 questions carry 6-9 times the weight of every other question. D09 deletes
them. The pass checks that each one really is a duplicate of its base case
before removing it, and writes the resulting composition table.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both, dump_json, CHANGELOG

EX = re.compile(r"^(?P<base>st_[a-z]+)_ex\d+$")


def duplicates(bench: Bench) -> dict[str, str]:
    """ex case id -> the `*_001` case it repeats."""
    by_id = bench.by_id()
    out = {}
    for case_id in by_id:
        m = EX.match(case_id)
        if m:
            out[case_id] = f"{m.group('base')}_001"
    return out


def composition(bench: Bench) -> dict:
    per_file = {name: len(cases) for name, cases in sorted(bench.files.items())}
    per_diff = Counter(c.get("difficulty") for _, c in bench.cases())
    per_tool: Counter = Counter()
    for _, case in bench.cases():
        tools = case["expected"].get("tools_must_include") or []
        if not tools:
            per_tool["(no tool)"] += 1
        for t in tools:
            per_tool[t] += 1
    return {"n": bench.n_cases(), "per_category": per_file,
            "per_difficulty": dict(sorted(per_diff.items())),
            "per_tool": dict(sorted(per_tool.items()))}


def apply(kr: Bench, en: Bench, log: ChangeLog) -> set[str]:
    dup = duplicates(kr)
    kr_by, en_by = kr.by_id(), en.by_id()
    identical_en = 0
    for case_id, base in sorted(dup.items()):
        case, base_case = kr_by[case_id], kr_by.get(base)
        if base_case is None:
            raise SystemExit(f"{case_id}: base case {base} is missing")
        if case["question"] != base_case["question"] or case["expected"] != base_case["expected"]:
            raise SystemExit(f"{case_id}: not a duplicate of {base}, refusing to delete")
        if en_by[case_id]["question"] == en_by[base]["question"]:
            identical_en += 1
        log.record(case_id, "kr+en", "case", {"question": case["question"], "expected": case["expected"],
                                              "difficulty": case["difficulty"]}, None,
                   "L1-023/D09", f"duplicate of {base}; 6-9 copies of one question weighted the easy "
                                 f"questions 6-9 times (D09 deletes them)")
    kr.drop(set(dup))
    en.drop(set(dup))
    log.note(f"{len(dup)} duplicates removed, {len(set(dup.values()))} base questions kept; "
             f"{identical_en} had a word-for-word identical EN question, the rest paraphrases")
    return set(dup)


def main() -> int:
    kr, en = both()
    log = ChangeLog("p02_dedupe", "Delete the 143 `*_ex01..08` duplicates of the `*_001` cases (D09).")
    before = {"kr": composition(kr), "en": composition(en)}
    apply(kr, en, log)
    kr.save()
    en.save()
    after = {"kr": composition(kr), "en": composition(en)}
    dump_json(CHANGELOG / "p02_composition.json", {"before": before, "after": after})
    print(log.report())
    print(f"cases: {before['kr']['n']} -> {after['kr']['n']} (KR), {before['en']['n']} -> {after['en']['n']} (EN)")
    print(f"log: {log.write()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
