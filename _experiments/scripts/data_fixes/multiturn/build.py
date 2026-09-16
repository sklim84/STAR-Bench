"""Build `benchmarks_multiturn/` and `benchmarks_multiturn_en/` from the scenario specs.

Every gold call is executed on the platform and its real output becomes the
turn's `tool_result` (D03, L3-004). Every `context_ref` is resolved against that
real output while the scenario is being built, so a reference can only survive
if the value is actually in the source turn's result and the receiving gold
argument really carries it (L2-013).

    python -m _experiments.scripts.data_fixes.multiturn.build
    python -m _experiments.scripts.data_fixes.multiturn.build --check   # no write

The English file is produced in the same pass, keyed by scenario id and turn
number, so the two files cannot drift apart the way positional matching let them
(C1-010).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
    __package__ = "_experiments.scripts.data_fixes.multiturn"

from .spec import (CHECK_ONLY, FRAUD_TYPE_EN, FRAUD_TYPE_KR, Ref, Scenario, Turn)

REPO = Path(__file__).resolve().parents[4]
KR_DIR = REPO / "benchmarks_multiturn"
EN_DIR = REPO / "benchmarks_multiturn_en"
FILENAME = "cases_str_workflow.json"
CHANGELOG = Path(__file__).resolve().parent / "rebuild_log.json"


# ---------------------------------------------------------------------------
# Platform
# ---------------------------------------------------------------------------

def tool_executor():
    from _experiments.scripts._platform import ensure_platform_on_path

    ensure_platform_on_path()
    from src.features.agent import _execute_tool

    return _execute_tool


class BuildError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Reference resolution
# ---------------------------------------------------------------------------

def resolve_path(obj, path: str):
    """`a.b[0].c` inside a tool result; the scorer resolves references the same way."""
    cur = obj
    for idx, name in re.findall(r"\[(\d+)\]|([^.\[\]]+)", path):
        if idx:
            if not isinstance(cur, list) or int(idx) >= len(cur):
                raise BuildError(f"{path}: index {idx} missing")
            cur = cur[int(idx)]
        else:
            if not isinstance(cur, dict) or name not in cur:
                raise BuildError(f"{path}: key {name!r} missing")
            cur = cur[name]
    return cur


_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z_0-9]*)(:[^}]*)?\}")

# Korean particles pick their form from the sound the value ends on. Written out
# once here rather than by hand in 50 scenarios, which is where the 4/28 bulk
# substitution left "분할 거래이" and "변화으로" behind (L2-010).
_PARTICLES = {"은는": ("은", "는"), "이가": ("이", "가"), "을를": ("을", "를"),
              "과와": ("과", "와"), "으로로": ("으로", "로"), "copula": ("이", "")}
# How each digit is read: 0 영, 1 일, 2 이, 3 삼, 4 사, 5 오, 6 육, 7 칠, 8 팔, 9 구.
_DIGIT_FINAL = {"0": "ㅇ", "1": "ㄹ", "2": "", "3": "ㅁ", "4": "",
                "5": "", "6": "ㄱ", "7": "ㄹ", "8": "ㄹ", "9": ""}


def _final_consonant(text: str) -> str:
    """The closing consonant of the last syllable, '' when the sound ends on a vowel."""
    for char in reversed(text):
        if char.isdigit():
            return _DIGIT_FINAL[char]
        code = ord(char) - 0xAC00
        if 0 <= code < 11172:
            jong = code % 28
            return "" if jong == 0 else "ㄹ" if jong == 8 else "X"
        if char.isalpha():
            return "X"
    return ""


def particle(text: str, pair: str) -> str:
    after_consonant, after_vowel = _PARTICLES[pair]
    final = _final_consonant(text)
    if pair == "으로로":   # 로 also follows ㄹ
        return after_vowel if final in ("", "ㄹ") else after_consonant
    return after_vowel if final == "" else after_consonant


def _date(value) -> str:
    text = str(int(value))
    return f"{text[:4]}년 {int(text[4:6])}월 {int(text[6:8])}일"


def fill(text: str, values: dict) -> str:
    """`{name}`, `{name:,}`, `{name:date}` and `{name:은는}` from the scenario's values.

    Turn texts carry JSON drafts, so a plain ``str.format`` is not usable here.
    """

    def one(match):
        name, spec = match.group(1), (match.group(2) or "")[1:]
        if name not in values:
            return match.group(0)
        value = values[name]
        spec, _, pair = spec.partition("|")
        if spec in _PARTICLES:
            spec, pair = "", spec
        if spec == "date":
            rendered = _date(value)
        elif isinstance(value, list):
            rendered = ", ".join(str(v) for v in value) or "없음"
        elif isinstance(value, bool):
            rendered = "충족" if value else "미충족"
        else:
            if spec == "," and isinstance(value, float):
                spec = ",.0f"
            rendered = format(value, spec)
        return rendered + (particle(rendered, pair) if pair else "")

    return _PLACEHOLDER.sub(one, text)


def resolve(value, results: dict[int, dict], values: dict):
    """Ref -> the real value; str -> formatted with the scenario's values."""
    if isinstance(value, Ref):
        if value.turn not in results:
            raise BuildError(f"reference to turn {value.turn}, which has no result yet")
        return resolve_path(results[value.turn], value.path)
    if isinstance(value, str):
        whole = _PLACEHOLDER.fullmatch(value)
        if whole and not whole.group(2) and whole.group(1) in values:
            return values[whole.group(1)]   # a gold argument keeps its type
        return fill(value, values)
    if isinstance(value, dict):
        return {k: resolve(v, results, values) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        out = [resolve(v, results, values) for v in value]
        return tuple(out) if isinstance(value, tuple) else out
    return value


# ---------------------------------------------------------------------------
# One turn
# ---------------------------------------------------------------------------

def gold_arguments(turn: Turn, args: dict, conds: list) -> dict:
    """The gold `arguments` block: real tool arguments plus the SQL checks."""
    gold = dict(args)
    if turn.tool == "query_transactions":
        gold.pop("sql", None)
        gold["sql_conditions"] = [{"column": c, "op": op, "value": v} for c, op, v in conds]
        gold["sql_valid"] = True
    return gold


def call_arguments(turn: Turn, args: dict, sql: str | None) -> dict:
    """The arguments the gold call is executed with."""
    if turn.tool == "query_transactions":
        return {"sql": sql}
    return {k: v for k, v in args.items() if k not in CHECK_ONLY}


def note(turn: Turn, lang: str) -> str:
    point = turn.point_kr if lang == "kr" else turn.point_en
    if point:
        return point
    if turn.clarify:
        return ("스키마 필수 인자가 없어 되묻기가 정답" if lang == "kr"
                else "a required argument is missing, so asking back is correct")
    if turn.abstain:
        return ("도구 호출 없이 판단을 답하는 것이 정답" if lang == "kr"
                else "answering without a tool call is correct")
    if turn.ctx:
        source, path, param = turn.ctx
        return (f"정답 도구 {turn.tool}. 턴 {source} 결과의 {path} 값을 {param}으로 이어가야 한다"
                if lang == "kr" else
                f"gold tool {turn.tool}; {path} from turn {source} has to be carried into {param}")
    return (f"정답 도구 {turn.tool}" if lang == "kr" else f"gold tool {turn.tool}")


def build_scenario(sc: Scenario, execute) -> tuple[dict, dict, list[dict]]:
    """Returns (Korean scenario, English scenario, changelog rows)."""
    results: dict[int, dict] = {}
    values = dict(sc.vars)
    kr_turns, en_turns, log = [], [], []

    for number, turn in enumerate(sc.turns, start=1):
        args = resolve(turn.args, results, values)
        conds = [resolve(c, results, values) for c in turn.conds]
        sql = resolve(turn.sql, results, values) if turn.sql else None

        entry_kr = {"turn": number, "content": resolve(turn.kr, results, values)}
        entry_en = {"turn": number, "content": resolve(turn.en, results, values)}

        if turn.tool is None:
            entry_kr["tool_calls"] = entry_en["tool_calls"] = []
            entry_kr["tool_result"] = entry_en["tool_result"] = None
            if turn.clarify:
                entry_kr["expect_clarification"] = entry_en["expect_clarification"] = True
        else:
            gold = gold_arguments(turn, args, conds)
            call = call_arguments(turn, args, sql)
            raw = execute(turn.tool, dict(call))
            try:
                result = json.loads(raw)
            except ValueError as exc:
                raise BuildError(f"{sc.id} turn {number}: result is not JSON ({exc})") from exc
            if isinstance(result, dict) and "error" in result:
                raise BuildError(f"{sc.id} turn {number}: {turn.tool} -> {result['error']}")
            results[number] = result

            gold_call = {"name": turn.tool, "arguments": gold}
            if sql is not None:
                gold_call["reference_sql"] = sql
            entry_kr["tool_calls"] = entry_en["tool_calls"] = [gold_call]
            if sql is not None:
                # The platform's gold-call harness looks for the SQL under this shape.
                entry_kr["reference_calls"] = entry_en["reference_calls"] = {
                    "query_transactions": {"sql": sql}}
            entry_kr["tool_result"] = entry_en["tool_result"] = result

        if turn.ctx:
            from_turn, path, to_param = turn.ctx
            expected = resolve_path(results[from_turn], path)
            check = args.get(to_param)
            if to_param == "sql":
                if not any(v == expected for _, _, v in conds):
                    raise BuildError(f"{sc.id} turn {number}: context value {expected!r} is not "
                                     f"a gold SQL condition")
                if str(expected) not in (sql or ""):
                    raise BuildError(f"{sc.id} turn {number}: context value {expected!r} is not "
                                     f"in the reference SQL")
            elif check != expected:
                raise BuildError(f"{sc.id} turn {number}: context_ref expects {expected!r} but the "
                                 f"gold {to_param} is {check!r}")
            ref = {"from_turn": from_turn, "key": path, "to_param": to_param}
            entry_kr["context_ref"] = entry_en["context_ref"] = ref

        entry_kr["note"] = note(turn, "kr")
        entry_en["note"] = note(turn, "en")
        kr_turns.append(entry_kr)
        en_turns.append(entry_en)

        for name, ref in turn.bind.items():
            values[name] = resolve_path(results[ref.turn], ref.path)

        log.append({"scenario": sc.id, "turn": number, "tool": turn.tool,
                    "arguments": entry_kr["tool_calls"][0]["arguments"] if turn.tool else None,
                    "context_ref": entry_kr.get("context_ref"),
                    "result_keys": sorted(results[number]) if number in results else None})

    kr = {"id": sc.id, "scenario": resolve(sc.kr, results, values), "sub_category": sc.sub,
          "fraud_type": sc.ft, "fraud_type_name": FRAUD_TYPE_KR[sc.ft], "turns": kr_turns}
    en = {"id": sc.id, "scenario": resolve(sc.en, results, values), "sub_category": sc.sub,
          "fraud_type": sc.ft, "fraud_type_name": FRAUD_TYPE_EN[sc.ft], "turns": en_turns}
    return kr, en, log


# ---------------------------------------------------------------------------
# Whole benchmark
# ---------------------------------------------------------------------------

def build(scenarios: list[Scenario]) -> tuple[list[dict], list[dict], list[dict]]:
    execute = tool_executor()
    kr_all, en_all, log = [], [], []
    for sc in scenarios:
        kr, en, rows = build_scenario(sc, execute)
        kr_all.append(kr)
        en_all.append(en)
        log.extend(rows)
    return kr_all, en_all, log


def write(path: Path, payload) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode()).hexdigest()


def all_scenarios() -> list[Scenario]:
    from .scenarios import SCENARIOS
    from .scenarios_b import SCENARIOS_B
    from .scenarios_c import SCENARIOS_C

    return SCENARIOS + SCENARIOS_B + SCENARIOS_C


def main(argv=None) -> int:

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="build in memory, write nothing")
    ap.add_argument("--only", help="build one scenario id")
    args = ap.parse_args(argv)

    scenarios = [s for s in all_scenarios() if not args.only or s.id == args.only]
    kr, en, log = build(scenarios)
    turns = sum(len(s["turns"]) for s in kr)
    print(f"{len(kr)} scenarios, {turns} turns")
    if args.check or args.only:
        print(json.dumps(kr[0], ensure_ascii=False, indent=1)[:4000])
        return 0
    kr_sha = write(KR_DIR / FILENAME, kr)
    en_sha = write(EN_DIR / FILENAME, en)
    CHANGELOG.write_text(json.dumps(
        {"scenarios": len(kr), "turns": turns,
         "kr_sha256": kr_sha, "en_sha256": en_sha,
         "why": [{"scenario": s.id, "entities": s.vars, "why": s.why} for s in scenarios],
         "calls": log}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{KR_DIR / FILENAME}  {kr_sha[:12]}")
    print(f"{EN_DIR / FILENAME}  {en_sha[:12]}")
    print(f"{CHANGELOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
