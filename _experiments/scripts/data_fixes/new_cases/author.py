"""Author the 2026-09 expansion cases into `benchmarks/` and `benchmarks_en/` (WS-G).

The five group modules hold the questions and the gold; this pass adds the fields the
rest of the data derives rather than states:

* `difficulty` from the rule, by calling `difficulty.points` -- the same code
  that labelled the 1,115 existing cases, so the two sets are labelled by one rule;
* `note` from `case_notes.note_for`, so the note is a rendering of the final gold;
* `"source": "2026-09 expansion"`, which marks the case as authored in this round so
  the review sheet and the paper can describe the composition.

The pass is idempotent: it drops every case already carrying that source tag before it
adds them again, so re-running it reproduces the same files. It writes
`new_cases.json`, the manifest the verification pass and the review sheet read.

    python -m _experiments.scripts.data_fixes.new_cases.author
    python -m _experiments.scripts.data_fixes.new_cases.author --check   # no write
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
    __package__ = "_experiments.scripts.data_fixes.new_cases"

from ..common import Bench, EN, KR, dump_json, load_json
from ..difficulty import label, points
from ..case_notes import note_for
from . import g1_validate_str, g2_reference, g3_clarification, g4_single_tool, g5_multi_tool

SOURCE = "2026-09 expansion"
GROUNDING = Path(__file__).resolve().parent / "grounding.json"
MANIFEST = Path(__file__).resolve().parent / "new_cases.json"
GROUPS = [g1_validate_str, g2_reference, g3_clarification, g4_single_tool, g5_multi_tool]


def build_all(grounding: dict) -> list[dict]:
    cases: list[dict] = []
    for module in GROUPS:
        cases.extend(module.build(grounding))
    ids = Counter(case["id"] for case in cases)
    repeated = [case_id for case_id, n in ids.items() if n > 1]
    if repeated:
        raise ValueError(f"the new cases repeat an id: {repeated}")
    return cases


def rendered(case: dict) -> tuple[dict, dict]:
    """The Korean and the English case, with difficulty and note derived from the gold."""
    total, parts = points({"question": case["question"], "expected": case["expected"]})
    difficulty = label(total)
    note = note_for({"expected": case["expected"]})
    kr = {"id": case["id"], "question": case["question"], "expected": case["expected"],
          "difficulty": difficulty, "note": note, "source": SOURCE}
    en = dict(kr, question=case["question_en"])
    return kr, en, {"points": total, **parts}


def drop_previous(bench: Bench) -> int:
    removed = 0
    for name, cases in bench.files.items():
        keep = [c for c in cases if c.get("source") != SOURCE]
        removed += len(cases) - len(keep)
        bench.files[name] = keep
    return removed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="build and report, write nothing")
    args = ap.parse_args(argv)

    grounding = load_json(GROUNDING)
    cases = build_all(grounding)

    kr, en = Bench.load(KR, "kr"), Bench.load(EN, "en")
    before = kr.n_cases() - drop_previous(kr)
    drop_previous(en)
    existing = set(kr.by_id())
    clash = sorted(existing & {case["id"] for case in cases})
    if clash:
        raise ValueError(f"the new cases reuse an existing id: {clash}")

    manifest = []
    for case in cases:
        kr_case, en_case, score = rendered(case)
        kr.add(case["file"], kr_case)
        en.add(case["file"], en_case)
        manifest.append({"id": case["id"], "file": case["file"],
                         "category": case["file"][len("cases_"):-len(".json")],
                         "question": case["question"], "question_en": case["question_en"],
                         "expected": case["expected"], "difficulty": kr_case["difficulty"],
                         "note": kr_case["note"], "rationale": case["rationale"],
                         "difficulty_points": score})

    by_category = Counter(row["category"] for row in manifest)
    by_difficulty = Counter(row["difficulty"] for row in manifest)
    by_tool: Counter = Counter()
    for row in manifest:
        tools = list(row["expected"].get("tools_must_include") or [])
        primary = row["expected"].get("primary_tool") or ""
        if primary and primary not in tools:
            tools.insert(0, primary)
        for tool in tools or ["(no tool call)"]:
            by_tool[tool] += 1

    print(f"{len(cases)} new cases; {before} existing; {kr.n_cases()} total")
    print("  by category: " + ", ".join(f"{k} {v}" for k, v in sorted(by_category.items())))
    print("  by difficulty: " + ", ".join(f"{k} {v}" for k, v in sorted(by_difficulty.items())))
    print("  by gold tool: " + ", ".join(f"{k} {v}" for k, v in sorted(by_tool.items())))
    if args.check:
        return 0

    kr.save()
    en.save()
    dump_json(MANIFEST, {"source": SOURCE, "n": len(manifest),
                         "by_category": dict(sorted(by_category.items())),
                         "by_difficulty": dict(sorted(by_difficulty.items())),
                         "by_gold_tool": dict(sorted(by_tool.items())),
                         "cases": manifest})
    print(f"manifest: {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
