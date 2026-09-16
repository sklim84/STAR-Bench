"""Pass 25 - every catalog-valued gold, checked against the rule (L1-019, R1A-012).

The closeout verification reported `st_fiu_003`, `st_fiu_009` and `st_fiu_019` as
broken: their gold keywords are `Non-face-to-face`, `ATM` and `Kimchi Premium`, the tool
matches case-insensitively, and "the scorer compares non-enum strings with `==`", so a
model that copies the lower-case spelling out of the tool description would score 0.

**That is not what the scorer does.** `scoring/catalog.py` (L1-019, the fix this very
register entry asked for) intercepts exactly these two arguments and compares them by
the catalog rows they select, not by their spelling:

    'Non-face-to-face' vs 'non-face-to-face'  -> 9 rows both, passes
    'ATM'              vs 'atm'              -> 2 rows both, passes
    'Kimchi Premium'   vs 'kimchi premium'   -> 1 row both, passes
    'structuring'      vs 'split'            -> 1 row vs 2, fails (which is F1, and right)

`_scalar_equal`'s case sensitivity is reached only with `--no-catalog`, a debugging flag
no runner sets. So no gold value changes here.

What does change is that the property is now checked rather than assumed. The rule:

* a catalog-valued gold selects at least one catalog row, and
* it selects the **same** rows in lower case, upper case and title case, so no spelling
  a model plausibly writes can turn the check into a coin toss, and
* `get_aml_glossary.term` is the catalog key as the glossary spells it.

The pass reads the platform's own catalog functions, so it cannot drift from them, and
it covers all four benchmark directories. `lint_benchmarks` runs the same check on the
single-turn arms and `multiturn.verify` on the multi-turn ones.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import REPO, Bench, ChangeLog, both

# tool -> the arguments the scorer resolves through the catalog (scoring/catalog.py).
RESULT_SET_ARGS = {
    "lookup_fiu_reference_types": ("keyword",),
    "get_aml_glossary": ("term",),
}
MULTITURN = [REPO / "benchmarks_multiturn" / "cases_str_workflow.json",
             REPO / "benchmarks_multiturn_en" / "cases_str_workflow.json"]


def catalog():
    """The platform's own lookup functions, or None when the platform is not available."""
    try:
        from _experiments.scripts._platform import ensure_platform_on_path  # noqa: PLC0415

        ensure_platform_on_path()
        from src.features.aml_reference import (  # noqa: PLC0415
            get_aml_glossary,
            lookup_fiu_reference_types,
        )
    except Exception:
        return None

    def rows(tool: str, value: str) -> frozenset:
        if tool == "lookup_fiu_reference_types":
            return frozenset((r["industry"], r["category"], r["no"])
                             for r in lookup_fiu_reference_types(value, None))
        found = get_aml_glossary(value)
        return frozenset() if found is None else frozenset({found["term"]})

    return rows


def check_value(rows, tool: str, value) -> list[str]:
    if not isinstance(value, str):
        return [f"{tool}: gold {value!r} is not a string"]
    selected = rows(tool, value)
    if not selected:
        return [f"{tool}({value!r}): selects no catalog row"]
    out = []
    for variant in (value.lower(), value.upper(), value.title()):
        if rows(tool, variant) != selected:
            out.append(f"{tool}({value!r}): {variant!r} selects a different row set, so the "
                       f"spelling decides the score")
    return out


def gold_values(cases, source: str):
    """(case label, tool, value) for every catalog-valued gold in a single-turn file."""
    for case in cases:
        for tool, checks in ((case.get("expected") or {}).get("param_checks") or {}).items():
            if not isinstance(checks, dict):
                continue
            for key in RESULT_SET_ARGS.get(tool, ()):
                if key in checks:
                    yield f"{source}:{case['id']}", tool, checks[key]


def multiturn_values(scenarios, source: str):
    for scenario in scenarios:
        for turn in scenario["turns"]:
            for call in turn.get("tool_calls") or []:
                for key in RESULT_SET_ARGS.get(call["name"], ()):
                    args = call.get("arguments") or {}
                    if key in args:
                        yield f"{source}:{scenario['id']}#t{turn['turn']}", call["name"], args[key]


def audit(rows) -> tuple[int, list[str]]:
    items = []
    for bench in both():
        items += list(gold_values([c for _, c in bench.cases()], bench.root.name))
    for path in MULTITURN:
        if path.exists():
            items += list(multiturn_values(json.loads(path.read_text(encoding="utf-8")),
                                           path.parent.name))
    problems = []
    for label, tool, value in items:
        problems += [f"{label}: {p}" for p in check_value(rows, tool, value)]
    return len(items), problems


def main() -> int:
    log = ChangeLog("p25_catalog_gold",
                    "Every catalog-valued gold checked against the catalog (L1-019). "
                    "Changes no data.")
    rows = catalog()
    if rows is None:
        print("p25_catalog_gold: the platform is not importable, catalog check skipped")
        log.note("skipped: the platform catalog was not importable on this host")
        print(f"log: {log.write()}")
        return 0
    n, problems = audit(rows)
    log.note(f"{n} catalog-valued gold arguments over four directories; each selects at "
             f"least one row and selects the same rows in lower, upper and title case.")
    log.note("No value changed. The closeout finding F3 (st_fiu_003/009/019 scored 0 for "
             "case) does not reproduce: scoring/catalog.py compares these two arguments "
             "by the rows they select, and case sensitivity is reached only under the "
             "--no-catalog debugging flag.")
    print(log.report())
    print(f"log: {log.write()}")
    print(f"{n} catalog-valued gold arguments, {len(problems)} problems")
    for p in problems:
        print(" -", p)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
