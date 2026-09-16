"""Checks the rebuilt multi-turn benchmark, and prints the distribution the paper reports.

    python -m _experiments.scripts.data_fixes.multiturn.verify

What it asserts:

* Korean and English carry the same scenario ids in the same order, the same
  turn counts, and a byte-identical tool interface (`tool_calls`, `tool_result`,
  `context_ref`, `reference_calls`); only `content`, `scenario`,
  `fraud_type_name` and `note` differ (C1-010).
* Every gold argument key is a property of that tool's schema, every required
  argument of a gold call is pinned, and every `query_transactions` turn carries
  an executable `reference_sql`.
* Every `context_ref` resolves inside the source turn's real `tool_result` and
  names an argument the gold call of its own turn takes (L2-013).
* No old crime name, no institution id outside the HOFINET ranges, and no
  account id that is not a HOFINET account (L2-006, L2-008, L3-018).
* Every stored `tool_result` is still exactly what the platform returns for that
  turn's gold call, so the injected history cannot drift from the tool layer (D03).
* No tool result is large enough to be truncated before it reaches the model.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
    __package__ = "_experiments.scripts.data_fixes.multiturn"

from .build import KR_DIR, EN_DIR, FILENAME, resolve_path
from .spec import CHECK_ONLY, KO_SOURCE

# Crime names the pre-audit data used, which HOFINET does not carry.
OLD_NAMES = ["자금세탁", "보이스피싱", "대포통장", "불법도박", "유사수신", "정액거래", "라운드 금액"]
# Institution ids the pre-audit data invented.
BAD_BANKS = {73, 88, 205, 305}
TOOL_RESULT_CHAR_BUDGET = 12000   # about 4,000 tokens of Korean-and-English JSON


def load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def tool_schemas() -> dict:
    from _experiments.scripts._platform import ensure_platform_on_path

    ensure_platform_on_path()
    from src.features.agent import TOOLS

    return {t["function"]["name"]: t["function"].get("parameters", {}) for t in TOOLS}


def hofinet_ids() -> tuple[set, set, set]:
    from src.data import db

    accounts = set(db.query("SELECT DISTINCT sender_acc AS a FROM hofinet")["a"]) | \
        set(db.query("SELECT DISTINCT receiver_acc AS a FROM hofinet")["a"])
    senders = set(db.query("SELECT DISTINCT sender_bank AS b FROM hofinet")["b"])
    receivers = set(db.query("SELECT DISTINCT receiver_bank AS b FROM hofinet")["b"])
    return accounts, senders, receivers


# `generate_str` answers in the language of the question (D13), and it echoes the
# summary it is given into VII_Narrative.SuspicionJudgmentReason, so those two places
# are language-dependent by design. They are blanked before the two arms are compared,
# and `check_summary_language` checks them on their own; everything else in the gold
# call and in the injected result still has to be identical.
LANGUAGE_DEPENDENT = ("SuspicionJudgmentReason",)


def normalise(value):
    if isinstance(value, dict):
        return {k: ("<summary>" if k in ("summary",) + LANGUAGE_DEPENDENT else normalise(v))
                for k, v in value.items()}
    if isinstance(value, list):
        return [normalise(v) for v in value]
    return value


def interface(scenario: dict) -> list:
    return [[normalise(t.get("tool_calls")), normalise(t.get("tool_result")),
             t.get("context_ref"), t.get("reference_calls"),
             t.get("expect_clarification"), t.get("turn")]
            for t in scenario["turns"]]


def check_parity(kr: list[dict], en: list[dict], fail):
    if [s["id"] for s in kr] != [s["id"] for s in en]:
        fail("KR and EN scenario ids differ")
        return
    for a, b in zip(kr, en):
        if len(a["turns"]) != len(b["turns"]):
            fail(f"{a['id']}: turn counts differ")
        if a["sub_category"] != b["sub_category"] or a["fraud_type"] != b["fraud_type"]:
            fail(f"{a['id']}: sub_category or fraud_type differs")
        if json.dumps(interface(a), sort_keys=True) != json.dumps(interface(b), sort_keys=True):
            fail(f"{a['id']}: the tool interface differs between KR and EN")
        for ta, tb in zip(a["turns"], b["turns"]):
            if ta["content"] == tb["content"] and not ta["content"].isdigit():
                fail(f"{a['id']} turn {ta['turn']}: the English turn was not translated")


HANGUL = re.compile(r"[가-힣]")


def summaries(scenarios: list[dict]):
    for sc in scenarios:
        for turn in sc["turns"]:
            for call in turn.get("tool_calls") or []:
                if call["name"] == "generate_str":
                    yield sc["id"], turn["turn"], call["arguments"].get("summary", "")


def check_summary_language(kr: list[dict], en: list[dict], fail):
    """The answer is written in the language of the question (D13).

    The `fraud_type` argument stays Korean in both arms: it is a §VI enum the platform
    only accepts in Korean. `summary` is free text, so it follows the question.
    """
    for scenario_id, turn, text in summaries(kr):
        if not HANGUL.search(text):
            fail(f"{scenario_id} turn {turn}: the Korean gold summary carries no Korean")
    for scenario_id, turn, text in summaries(en):
        if HANGUL.search(text):
            fail(f"{scenario_id} turn {turn}: the English gold summary carries Korean")


def check_gold(kr: list[dict], schemas: dict, fail):
    for sc in kr:
        turns = {t["turn"]: t for t in sc["turns"]}
        for turn in sc["turns"]:
            for call in turn.get("tool_calls") or []:
                tool, args = call["name"], call.get("arguments") or {}
                schema = schemas.get(tool)
                if schema is None:
                    fail(f"{sc['id']} turn {turn['turn']}: unknown tool {tool}")
                    continue
                props, required = schema.get("properties", {}), schema.get("required", [])
                for key in args:
                    if key not in props and key not in CHECK_ONLY:
                        fail(f"{sc['id']} turn {turn['turn']}: {tool}.{key} is not a schema property")
                pinned = set(args) | ({"sql"} if "sql_conditions" in args else set())
                for key in required:
                    if key not in pinned:
                        fail(f"{sc['id']} turn {turn['turn']}: {tool} gold omits required {key}")
                if tool == "query_transactions" and not call.get("reference_sql"):
                    fail(f"{sc['id']} turn {turn['turn']}: query_transactions has no reference_sql")
            ref = turn.get("context_ref")
            if not ref:
                continue
            source = turns.get(ref["from_turn"])
            if source is None or source.get("tool_result") is None:
                fail(f"{sc['id']} turn {turn['turn']}: context source has no result")
                continue
            try:
                value = resolve_path(source["tool_result"], ref["key"])
            except Exception:
                fail(f"{sc['id']} turn {turn['turn']}: {ref['key']} does not resolve")
                continue
            args = (turn["tool_calls"][0].get("arguments") or {})
            if ref["to_param"] == "sql":
                conds = args.get("sql_conditions") or []
                if not any(c.get("value") == value for c in conds):
                    fail(f"{sc['id']} turn {turn['turn']}: {value!r} is not a gold SQL condition")
            elif args.get(ref["to_param"]) != value:
                fail(f"{sc['id']} turn {turn['turn']}: gold {ref['to_param']} is not the referenced value")


def check_entities(kr: list[dict], en: list[dict], accounts, senders, receivers, fail):
    text = json.dumps(kr, ensure_ascii=False) + json.dumps(en, ensure_ascii=False)
    # The Korean renderings of the FIU catalog and the AML glossary are recorded in
    # spec.KO_SOURCE, and the glossary defines layering as a stage of 자금세탁. They are
    # taken out before the scan, so the gate still catches a crime name used as if it
    # were a HOFINET transaction type.
    for rendering in KO_SOURCE.values():
        text = text.replace(rendering, " ")
    for name in OLD_NAMES:
        if name in text:
            fail(f"old crime name {name!r} is still in the data")
    for scenarios in (kr, en):
        for sc in scenarios:
            for turn in sc["turns"]:
                blob = json.dumps([turn.get("tool_calls"), turn["content"]], ensure_ascii=False)
                for token in re.findall(r"\b9\d{15}\b", blob):
                    if int(token) not in accounts:
                        fail(f"{sc['id']} turn {turn['turn']}: {token} is not a HOFINET account")
                for call in turn.get("tool_calls") or []:
                    args = call.get("arguments") or {}
                    for key in ("sender_bank", "bank_id"):
                        if key in args and args[key] not in senders | receivers:
                            fail(f"{sc['id']} turn {turn['turn']}: {key}={args[key]} is not a HOFINET institution")
                    if "receiver_bank" in args and args["receiver_bank"] not in receivers:
                        fail(f"{sc['id']} turn {turn['turn']}: receiver_bank={args['receiver_bank']} is not a receiver")
                    for cond in args.get("sql_conditions") or []:
                        if cond["column"] in ("sender_bank", "receiver_bank") and \
                                cond["value"] in BAD_BANKS:
                            fail(f"{sc['id']} turn {turn['turn']}: invalid institution {cond['value']}")


def check_results_are_live(kr: list[dict], fail):
    """Re-execute every gold call and compare it with the stored result (D03)."""
    from .build import call_arguments, tool_executor
    from .spec import Turn

    execute = tool_executor()
    for sc in kr:
        for turn in sc["turns"]:
            for call in turn.get("tool_calls") or []:
                spec = Turn(kr="", en="", tool=call["name"])
                args = call.get("arguments") or {}
                sql = call.get("reference_sql")
                fresh = json.loads(execute(call["name"], call_arguments(spec, args, sql)))
                if fresh != turn.get("tool_result"):
                    fail(f"{sc['id']} turn {turn['turn']}: the stored result is no longer what "
                         f"{call['name']} returns")


def check_sizes(kr: list[dict], fail):
    for sc in kr:
        for turn in sc["turns"]:
            result = turn.get("tool_result")
            if result is None:
                continue
            size = len(json.dumps(result, ensure_ascii=False))
            if size > TOOL_RESULT_CHAR_BUDGET:
                fail(f"{sc['id']} turn {turn['turn']}: result of {size} chars would be truncated")


def narrative_coverage(kr: list[dict]) -> dict:
    """§VII section coverage of the gold STR summaries, with the analysis script's patterns."""
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "RQ_str_generation_quality.py"
    spec = importlib.util.spec_from_file_location("rq_str_quality", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = [module.section_coverage(call["arguments"]["summary"])
            for sc in kr for turn in sc["turns"] for call in turn.get("tool_calls") or []
            if call["name"] == "generate_str"]
    return {"n": len(rows),
            **{key: round(sum(r[key] for r in rows) / len(rows), 4) for key in rows[0]}}


def distribution(kr: list[dict]) -> dict:
    tools = Counter()
    kinds = Counter()
    for sc in kr:
        for turn in sc["turns"]:
            calls = turn.get("tool_calls") or []
            if turn.get("expect_clarification"):
                kinds["clarification"] += 1
            elif not calls:
                kinds["no-tool answer"] += 1
            else:
                kinds["tool call"] += 1
            for call in calls:
                tools[call["name"]] += 1
    return {
        "scenarios": len(kr),
        "turns": sum(len(s["turns"]) for s in kr),
        "turns_per_scenario": dict(sorted(Counter(len(s["turns"]) for s in kr).items())),
        "sub_category": dict(Counter(s["sub_category"] for s in kr)),
        "fraud_type": dict(sorted(Counter(s["fraud_type"] for s in kr).items())),
        "turn_kind": dict(kinds),
        "context_ref_turns": sum(1 for s in kr for t in s["turns"] if t.get("context_ref")),
        "tools": dict(sorted(tools.items(), key=lambda kv: (-kv[1], kv[0]))),
        "distinct_tools": len(tools),
    }


def main() -> int:
    kr = load(KR_DIR / FILENAME)
    en = load(EN_DIR / FILENAME)
    problems: list[str] = []
    fail = problems.append

    schemas = tool_schemas()
    accounts, senders, receivers = hofinet_ids()
    check_parity(kr, en, fail)
    check_summary_language(kr, en, fail)
    check_gold(kr, schemas, fail)
    check_entities(kr, en, accounts, senders, receivers, fail)
    check_results_are_live(kr, fail)
    check_sizes(kr, fail)

    report = distribution(kr)
    report["str_narrative_coverage"] = narrative_coverage(kr)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    if problems:
        print(f"\n{len(problems)} problems")
        for p in problems:
            print(" -", p)
        return 1
    print("\nno problems")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
