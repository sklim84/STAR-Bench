"""Gate 3: the benchmark files a run will read.

Three of these checks live with the data they check and are called here rather
than reimplemented: the single-turn linter, `data_fixes.multiturn.verify` and
`new_cases.verify --gate`. The suite adds what sits between them: that
the two languages carry the same cases in the same order with the same gold,
that the counts are the ones the manuscript reports, and that no two cases ask
the same question.

Counts live in `expected_counts.json`. Adding or removing cases updates that
file in the same commit, so the number in the paper and the number on disk
cannot drift apart unnoticed.
"""

from __future__ import annotations

import json
import re
import tempfile
import time
from collections import defaultdict
from pathlib import Path

from .gate import (Check, Context, GateResult, MULTI_TURN_DIRS, SINGLE_TURN_DIRS,
                   run_command)

NUMBER = 3
KEY = "data"
TITLE = "benchmark data"

COUNTS_PATH = Path(__file__).resolve().parent / "expected_counts.json"

# Fields that must be identical in the Korean and the English case of one id.
SHARED_FIELDS = ("expected", "difficulty", "note", "source")


def run(ctx: Context) -> GateResult:
    started = time.time()
    checks = [
        _cli(ctx, "single-turn linter",
             ["-m", "_experiments.scripts.data_fixes.lint_benchmarks"]),
        _cli(ctx, "multi-turn rebuild verification",
             ["-m", "_experiments.scripts.data_fixes.multiturn.verify"]),
        _new_cases(ctx),
    ]
    checks.append(_parity(ctx))
    checks.append(_counts(ctx))
    checks.extend(_duplicates(ctx))
    return GateResult(KEY, NUMBER, TITLE, checks, time.time() - started)


def _cli(ctx: Context, name: str, args: list[str]) -> Check:
    done = run_command([ctx.python, *args], cwd=ctx.root, env=ctx.env, timeout=ctx.timeout_s)
    return Check(name, done.ok, done.tail(6) if not done.ok else _verdict(done.stdout),
                 done.command)


def _verdict(output: str) -> str:
    """The line a verifier ends on, ignoring the detail it indents underneath."""
    lines = [line for line in output.splitlines()
             if line.strip() and not line.startswith((" ", "\t"))]
    return lines[-1] if lines else ""


def _new_cases(ctx: Context) -> Check:
    """The expansion-case verifier writes a review sheet, so it is pointed at a scratch file."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
        sheet = Path(handle.name)
    try:
        return _cli(ctx, "expansion cases",
                    ["-m", "_experiments.scripts.data_fixes.new_cases.verify", "--gate",
                     "--out", str(sheet)])
    finally:
        sheet.unlink(missing_ok=True)


def load_cases(directory: Path) -> tuple[list[dict], dict[str, str]]:
    """Every case of a benchmark directory in file order, plus the file each came from."""
    cases: list[dict] = []
    source: dict[str, str] = {}
    for path in sorted(directory.glob("cases_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("cases", [])
        for case in payload:
            cases.append(case)
            source[case["id"]] = path.name
    return cases, source


def _normalise(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _parity(ctx: Context) -> Check:
    """The two languages are one benchmark: same ids, same order, same gold."""
    problems: list[str] = []
    for kr_name, en_name in (SINGLE_TURN_DIRS, MULTI_TURN_DIRS):
        kr, _ = load_cases(ctx.root / kr_name)
        en, _ = load_cases(ctx.root / en_name)
        kr_ids = [c["id"] for c in kr]
        en_ids = [c["id"] for c in en]
        if kr_ids != en_ids:
            only_kr = sorted(set(kr_ids) - set(en_ids))[:5]
            only_en = sorted(set(en_ids) - set(kr_ids))[:5]
            problems.append(f"{kr_name}/{en_name}: case ids differ "
                            f"({len(kr_ids)} vs {len(en_ids)}; only KR {only_kr}, only EN {only_en})")
            continue
        by_en = {c["id"]: c for c in en}
        for case in kr:
            other = by_en[case["id"]]
            if "turns" in case:
                if len(case["turns"]) != len(other.get("turns", [])):
                    problems.append(f"{case['id']}: {len(case['turns'])} turns in {kr_name}, "
                                    f"{len(other.get('turns', []))} in {en_name}")
                continue
            for field in SHARED_FIELDS:
                if case.get(field) != other.get(field):
                    problems.append(f"{case['id']}.{field} differs between {kr_name} and {en_name}")
    return Check("Korean and English carry the same cases and the same gold", not problems,
                 "; ".join(problems[:6]) if problems
                 else "same ids in the same order, same gold, same difficulty, same note",
                 None, {"problems": problems})


def counts(ctx: Context) -> dict:
    out: dict = {}
    for name in SINGLE_TURN_DIRS:
        cases, _ = load_cases(ctx.root / name)
        out[name] = {"cases": len(cases)}
    for name in MULTI_TURN_DIRS:
        cases, _ = load_cases(ctx.root / name)
        out[name] = {"cases": len(cases),
                     "turns": sum(len(c.get("turns") or []) for c in cases)}
    return out


def _counts(ctx: Context) -> Check:
    expected = json.loads(COUNTS_PATH.read_text(encoding="utf-8"))["counts"]
    actual = counts(ctx)
    problems = []
    for name, want in expected.items():
        have = actual.get(name)
        if have is None:
            problems.append(f"{name}: directory missing")
            continue
        for key, value in want.items():
            if have.get(key) != value:
                problems.append(f"{name}: {have.get(key)} {key}, expected {value}")
    summary = ", ".join(f"{name} {v['cases']} cases"
                        + (f"/{v['turns']} turns" if "turns" in v else "")
                        for name, v in actual.items())
    return Check("case counts are the ones the write-up reports", not problems,
                 "; ".join(problems) if problems else summary,
                 f"cat {COUNTS_PATH.relative_to(ctx.root)}", actual)


def _duplicates(ctx: Context) -> list[Check]:
    """Two cases that ask the same question are one case counted twice."""
    checks = []
    for name in SINGLE_TURN_DIRS:
        cases, source = load_cases(ctx.root / name)
        groups: dict[str, list[str]] = defaultdict(list)
        for case in cases:
            groups[_normalise(case.get("question"))].append(case["id"])
        dupes = {q: ids for q, ids in groups.items() if len(ids) > 1}
        detail = (f"{len(cases)} distinct questions" if not dupes else
                  "; ".join(f"{ids} ({source[ids[0]]}): {q[:60]}"
                            for q, ids in list(dupes.items())[:5]))
        checks.append(Check(f"no duplicate question in {name}", not dupes, detail,
                            None, {"duplicates": {q: ids for q, ids in dupes.items()}}))

    for name in MULTI_TURN_DIRS:
        cases, _ = load_cases(ctx.root / name)
        groups = defaultdict(list)
        for case in cases:
            key = " | ".join(_normalise(t.get("content")) for t in case.get("turns") or [])
            groups[key].append(case["id"])
        dupes = {q: ids for q, ids in groups.items() if len(ids) > 1}
        # A single user turn repeats across scenarios on purpose ("score the first
        # transaction in that result" means a different transaction in each one),
        # so the unit here is the whole scenario.
        checks.append(Check(f"no duplicate scenario in {name}", not dupes,
                            f"{len(cases)} distinct scenarios" if not dupes
                            else "; ".join(str(ids) for ids in list(dupes.values())[:5]),
                            None, {"duplicates": list(dupes.values())}))
    return checks
