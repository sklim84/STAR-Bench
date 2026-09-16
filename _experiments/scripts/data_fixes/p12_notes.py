"""Pass 12 - regenerate the case notes from the final gold (L1-026).

The notes shipped with the data contradicted the gold: st_pf_039 said "11 pm =
time slot 23" where the gold is 21, st_gfs_039 named fraud_type 6, st_gl_006
promised that either EDD or SDD passes although nothing implemented that, and
several abstention notes said which tool was needed. Notes are never shown to a
model, but they are published with the data, so they are rebuilt from the final
`expected` block and say only what the gold actually requires.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from .common import Bench, ChangeLog, both

SPECIAL_TEXT = {
    "sql_conditions": None,  # rendered separately
    "sql_valid": "the SQL must run without an error",
    "hops_min": "hops at least {value}",
    "hops_max": "hops at most {value}",
    "result_row_count_min": "at least {value} rows",
    "result_row_count_max": "at most {value} rows",
    "result_contains": "the result must contain {value}",
}


def render_conditions(conditions) -> str:
    parts = []
    for c in conditions:
        value, op = c["value"], str(c["op"]).upper()
        if isinstance(value, list):
            joiner = " and " if op == "BETWEEN" else ", "
            text = joiner.join(str(v) for v in value)
            if op == "IN":
                text = f"({text})"
        else:
            text = str(value)
        parts.append(f"{c['column']} {c['op']} {text}")
    return "must restrict " + " and ".join(parts)


def render_checks(tool: str, checks: dict) -> str:
    if not isinstance(checks, dict) or not checks:
        return ""
    parts = []
    for key, value in checks.items():
        if key == "sql_conditions":
            parts.append(render_conditions(value))
        elif key in SPECIAL_TEXT:
            template = SPECIAL_TEXT[key]
            if template:
                parts.append(template.format(value=value))
        elif isinstance(value, dict):
            parts.append(f"{key} as given in the question")
        else:
            parts.append(f"{key}={value}")
    return f" ({'; '.join(parts)})" if parts else ""


def render_tools(spec: dict) -> str:
    tools = list(spec.get("tools_must_include") or [])
    primary = spec.get("primary_tool") or ""
    if primary and primary not in tools:
        tools.insert(0, primary)
    checks = spec.get("param_checks") or {}
    rendered = [t + render_checks(t, checks.get(t, {})) for t in tools]
    order = spec.get("tool_order") or []
    joined = ", ".join(rendered)
    if order:
        joined += f"; called in the order {' -> '.join(order)}"
    return joined


def note_for(case: dict) -> str:
    expected = case.get("expected") or {}
    alternatives = expected.get("alternatives") or []
    if expected.get("expect_clarification"):
        head = ("Expects a clarification, not a call: a schema-required argument is unresolved in the "
                "question (D19).")
    elif not (expected.get("tools_must_include") or expected.get("primary_tool")):
        head = "Expects no tool call: the question is answered without the data or the catalog (D10)."
    else:
        head = f"Expects {render_tools(expected)}."
    for alt in alternatives:
        if alt.get("abstain"):
            head += " Answering without a tool call is also accepted."
        elif alt.get("expect_clarification"):
            head += " Asking back is also accepted."
        else:
            head += f" Also accepted: {render_tools(alt)}."
    if "reference_calls" in expected:
        head += (" expected.reference_calls carries the SQL the reference answer runs, so the gold call "
                 "is executable.")
    return head


def apply(kr: Bench, en: Bench, log: ChangeLog) -> None:
    kr_by, en_by = kr.by_id(), en.by_id()
    why = ("the shipped note contradicted the gold (old code mappings, rules that were never "
           "implemented, abstention notes naming the tool that was needed); it is regenerated from the "
           "final expected block (L1-026)")
    for case_id, case in kr_by.items():
        text = note_for(case)
        log.set_field(case, "kr", "note", text, "L1-026", why)
        log.set_field(en_by[case_id], "en", "note", text, "L1-026", why)
    log.note(f"{len(kr_by)} notes regenerated from the final gold, in both languages")


def main() -> int:
    kr, en = both()
    log = ChangeLog("p12_notes", "Regenerate every case note from the final gold (L1-026).")
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
