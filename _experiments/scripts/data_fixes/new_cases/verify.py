"""Verify the 2026-09 expansion cases and write the domain-expert review sheet (WS-G).

Three checks, all of which have to pass before the cases ship:

1. **Executable gold.** Every gold call of every new case is run through the platform's
   own tool layer, and its result is summarised (row counts, or the key fields a
   reviewer needs). A call that errors, or that answers nothing without a reason
   recorded in `EXPECTED_EMPTY`, fails the gate.
2. **Not a near-duplicate.** Each new question is compared with all 1,258 questions of
   the same language by character 3-gram Jaccard. The JSON payload of an STR draft is
   compared separately, as an exact-match check over the drafts, because two drafts
   that differ in one field would otherwise look almost identical as text.
3. **Both languages agree.** The Korean and the English case must carry the same id,
   the same gold, the same difficulty and the same note; the question differs.

    python -m _experiments.scripts.data_fixes.new_cases.verify --gate
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
    __package__ = "_experiments.scripts.data_fixes.new_cases"

from ..common import Bench, EN, KR, dump_json, load_json

MANIFEST = Path(__file__).resolve().parent / "new_cases.json"
REVIEW_SHEET = (Path(__file__).resolve().parents[4] / "_experiments" / "dataset_fix_20260915"
                / "impl" / "WS-G_review_sheet.json")
SPECIAL = {"sql_conditions", "sql_valid", "sql_contains", "hops_min", "hops_max",
           "result_contains", "result_row_count_min", "result_row_count_max"}
# Gold calls that are allowed to answer nothing, with the reason.
EXPECTED_EMPTY: dict[str, str] = {}
SIMILARITY_LIMIT = 0.75
JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)
NON_WORD = re.compile(r"[^0-9a-z가-힣]+")


# --------------------------------------------------------------------------- execution
def gold_calls(case: dict):
    """(tool, arguments) for every gold call of one case, as a perfect model would send it."""
    expected = case["expected"]
    for tool, checks in (expected.get("param_checks") or {}).items():
        if not isinstance(checks, dict):
            continue
        args = {k: v for k, v in checks.items() if k not in SPECIAL}
        if "hops_min" in checks:
            args["hops"] = checks["hops_min"]
        reference = (expected.get("reference_calls") or {}).get(tool) or {}
        if reference.get("sql"):
            args["sql"] = reference["sql"]
        yield tool, args


def summarise(tool: str, raw: str) -> dict:
    """What the reviewer needs to see: how much came back, and the fields that identify it."""
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {"kind": "text", "chars": len(raw), "empty": not raw.strip()}
    if isinstance(payload, list):
        return {"kind": "list", "rows": len(payload), "empty": not payload}
    if not isinstance(payload, dict):
        return {"kind": type(payload).__name__, "empty": payload is None}
    out: dict = {"kind": "object"}
    if payload.get("error"):
        return {"kind": "error", "error": str(payload["error"])[:300], "empty": True}
    rows = payload.get("result") or payload.get("results")
    if isinstance(rows, list):
        out["rows"] = len(rows)
    for key in ("total_count", "returned_count", "count", "notice", "criteria", "filters",
                "rule_name", "keyword", "industry", "term", "valid", "missing_required",
                "missing_optional", "bank_filter", "fraud_type", "risk_level", "risk_score",
                "fraud_risk_score", "unique_senders", "connected_accounts", "period"):
        if key in payload:
            out[key] = payload[key]
    if tool in ("get_account_profile", "get_receiving_account_profile", "score_account_risk"):
        for key in ("account_id", "total_count", "outbound_count", "inbound_count",
                    "fraud_ratio_percent", "total_amount"):
            if key in payload:
                out[key] = payload[key]
    empty = False
    if out.get("rows") == 0 or payload.get("total_count") == 0:
        empty = True
    if isinstance(payload.get("notice"), str) and out.get("rows") in (0, None) and "rows" in out:
        empty = True
    out["empty"] = empty
    return out


def execute_all(cases: list[dict], execute) -> dict[str, list[dict]]:
    results: dict[str, list[dict]] = {}
    for case in cases:
        rows = []
        for tool, args in gold_calls(case):
            try:
                raw = execute(tool, dict(args))
                error = None
            except Exception as exc:  # a gold call must never raise
                raw, error = "", f"{type(exc).__name__}: {exc}"
            summary = summarise(tool, raw) if error is None else {"kind": "exception", "empty": True}
            shown = dict(args)
            if isinstance(shown.get("str_draft"), dict):
                # The draft is already in the question; repeating it doubles the sheet.
                shown["str_draft"] = "<the draft in the question>"
            rows.append({"tool": tool, "arguments": shown, "error": error, "result": summary})
        results[case["id"]] = rows
    return results


# --------------------------------------------------------------------------- similarity
def prose(question: str) -> str:
    """The question without its JSON payload, normalised for comparison."""
    stripped = JSON_BLOCK.sub(" ", question)
    return NON_WORD.sub(" ", stripped.lower()).strip()


def grams(text: str) -> set[str]:
    text = re.sub(r"\s+", " ", text)
    return {text[i:i + 3] for i in range(max(len(text) - 2, 1))}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def nearest(bench: Bench, new_ids: set[str]) -> dict[str, dict]:
    items = [(case["id"], grams(prose(case["question"]))) for _, case in bench.cases()]
    out = {}
    for case_id, gram in items:
        if case_id not in new_ids:
            continue
        best_id, best = "", 0.0
        for other_id, other in items:
            if other_id == case_id:
                continue
            score = jaccard(gram, other)
            if score > best:
                best_id, best = other_id, score
        out[case_id] = {"nearest": best_id, "similarity": round(best, 3)}
    return out


def draft_clashes(bench: Bench) -> list[dict]:
    """Two cases carrying the same STR draft would be the same question twice."""
    seen: dict[str, str] = {}
    out = []
    for _, case in bench.cases():
        checks = (case["expected"].get("param_checks") or {}).get("validate_str_fields") or {}
        draft = checks.get("str_draft")
        if not isinstance(draft, dict):
            continue
        key = json.dumps(draft, ensure_ascii=False, sort_keys=True)
        if key in seen:
            out.append({"case_id": case["id"], "same_draft_as": seen[key]})
        else:
            seen[key] = case["id"]
    return out


# --------------------------------------------------------------------------- review sheet
def review_rows(manifest: list[dict], kr: Bench, en: Bench, executed, similarity) -> list[dict]:
    en_by = en.by_id()
    rows = []
    for entry in manifest:
        expected = entry["expected"]
        tools = list(expected.get("tools_must_include") or [])
        primary = expected.get("primary_tool") or ""
        if primary and primary not in tools:
            tools.insert(0, primary)
        rows.append({
            "id": entry["id"],
            "tool": tools or ["(no tool call)"],
            "category": entry["category"],
            "difficulty": entry["difficulty"],
            "difficulty_points": entry["difficulty_points"],
            "question_ko": entry["question"],
            "question_en": en_by[entry["id"]]["question"],
            "gold": expected,
            "executed": executed.get(entry["id"], []),
            "rationale": entry["rationale"],
            "note": entry["note"],
            "nearest_existing_question": similarity.get(entry["id"], {}),
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gate", action="store_true", help="exit non-zero on any problem")
    ap.add_argument("--out", default=str(REVIEW_SHEET))
    args = ap.parse_args(argv)

    manifest = load_json(MANIFEST)["cases"]
    kr, en = Bench.load(KR, "kr"), Bench.load(EN, "en")
    kr_by, en_by = kr.by_id(), en.by_id()
    new_ids = {entry["id"] for entry in manifest}

    problems: list[dict] = []
    for entry in manifest:
        case_id = entry["id"]
        if case_id not in kr_by or case_id not in en_by:
            problems.append({"check": "present", "case_id": case_id, "detail": "not in both directories"})
            continue
        a, b = kr_by[case_id], en_by[case_id]
        if a["expected"] != b["expected"] or a["difficulty"] != b["difficulty"] or a["note"] != b["note"]:
            problems.append({"check": "parity", "case_id": case_id, "detail": "gold/difficulty/note differ"})
        if a.get("source") != "2026-09 expansion" or b.get("source") != "2026-09 expansion":
            problems.append({"check": "source", "case_id": case_id, "detail": "source tag missing"})

    from _experiments.scripts._platform import ensure_platform_on_path  # noqa: PLC0415

    ensure_platform_on_path()
    from src.features.agent import _execute_tool  # noqa: PLC0415

    executed = execute_all([kr_by[i] for i in new_ids if i in kr_by], _execute_tool)
    n_calls = 0
    for case_id, rows in executed.items():
        for row in rows:
            n_calls += 1
            if row["error"]:
                problems.append({"check": "gold_call", "case_id": case_id,
                                 "detail": f"{row['tool']} raised: {row['error']}"})
            elif row["result"].get("kind") == "error":
                problems.append({"check": "gold_call", "case_id": case_id,
                                 "detail": f"{row['tool']} returned an error: {row['result']['error']}"})
            elif row["result"].get("empty") and case_id not in EXPECTED_EMPTY:
                problems.append({"check": "empty_result", "case_id": case_id,
                                 "detail": f"{row['tool']} answered nothing"})

    similarity = nearest(kr, new_ids)
    similarity_en = nearest(en, new_ids)
    for case_id, row in similarity.items():
        worst = max(row["similarity"], similarity_en.get(case_id, {}).get("similarity", 0.0))
        if worst >= SIMILARITY_LIMIT:
            problems.append({"check": "near_duplicate", "case_id": case_id,
                             "detail": f"{worst} similar to {row['nearest']}"})
    for clash in draft_clashes(kr):
        problems.append({"check": "duplicate_draft", "case_id": clash["case_id"],
                         "detail": f"same STR draft as {clash['same_draft_as']}"})

    rows = review_rows(manifest, kr, en, executed, similarity)
    by_tool: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_tool[", ".join(row["tool"])].append(row)

    payload = {
        "source": "2026-09 expansion",
        "n_cases": len(rows),
        "n_gold_calls_executed": n_calls,
        "similarity_limit": SIMILARITY_LIMIT,
        "how_to_read": ("One entry per new case, grouped by the gold tool set. `executed` is the "
                        "result of running the gold call on the fixed platform; `nearest_existing_"
                        "question` is the most similar question in the same language, by character "
                        "3-gram Jaccard over the question with any JSON payload removed."),
        "problems": problems,
        "groups": [{"tools": tools, "n": len(items), "cases": items}
                   for tools, items in sorted(by_tool.items())],
    }
    dump_json(args.out, payload)
    print(f"{len(rows)} new cases, {n_calls} gold calls executed, {len(problems)} problems")
    for row in problems[:40]:
        print(f"  {row['check']} {row['case_id']}: {row['detail']}")
    top = sorted(similarity.items(), key=lambda kv: -kv[1]["similarity"])[:5]
    print("  most similar new questions: " +
          ", ".join(f"{k} {v['similarity']} ({v['nearest']})" for k, v in top))
    print(f"  review sheet: {args.out}")
    return 1 if (args.gate and problems) else 0


if __name__ == "__main__":
    raise SystemExit(main())
