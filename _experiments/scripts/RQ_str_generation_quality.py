#!/usr/bin/env python3
"""STR generation quality — three diagnostic dimensions, per configuration.

The benchmark's value is diagnostic: it shows where and why a model breaks down
while writing the STR, not which model wins. The multi-turn task culminates in
``generate_str``; this step characterises the report the model actually wrote,
along three axes:

  D1  Field coverage   — how well the model's STR narrative covers the seven Korean
                         FIU STR (Article VII) sub-sections, using the SAME keyword
                         patterns as the ground-truth coverage analysis (Appendix B),
                         applied to the MODEL-generated ``summary``.
  D2  Hallucination    — fraction of concrete entities (account serials, amounts,
                         percentages, probabilities) in the model summary that are
                         NOT present in the injected prior-turn ``tool_result`` facts.
  D3  Grounding        — fraction of those entities that ARE traceable to the injected
                         prior-turn ``tool_result`` facts (the complement view of D2).

Because the oracle setting INJECTS the ground-truth ``tool_result`` at every turn,
the set of facts the STR should be grounded on is known exactly, making D2/D3
measurable without an external judge (entity level). Qualitative-claim
faithfulness would need an LLM judge and is left as an optional extension.

WHERE THE TEXT COMES FROM
-------------------------
The eval files hold scores, not what the model wrote, so the summary comes from
the Contract 2 run records through ``load.calls("oracle")``: one row per tool
call with its arguments. A scenario counts as produced when the model called
``generate_str`` at the turn the gold case puts it at. A call whose arguments
never parsed into an object has no ``summary`` field; it counts as produced with
an empty narrative, which scores 0 on every axis, and the count is reported as
``n_unparsed_arguments``.

Ported to the scored rerun (see `analysis/PORTING.md`): the `EXCLUDE` list is
gone and the cohort is the serving registry (rule 3); the output carries
`n_configs` and the ids that are not scored (rule 4); every rate carries the n
it was taken over (rule 2). The JSON is an object rather than a bare list so it
can hold that cohort block, with the per-configuration rows under `rows`.

Per configuration, statistics run over the scenarios whose GOLD case has a
``generate_str`` turn; ``str_production_rate`` (how often an STR was produced at
all) is itself reported, since "did not produce an STR" is a primary failure mode.

Usage:  PYTHONPATH=. python _experiments/scripts/RQ_str_generation_quality.py
        python -m _experiments.scripts.RQ_str_generation_quality
Output: _experiments/results_RQ3/str_generation_quality.{json,csv}
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _experiments.scripts.analysis import load  # noqa: E402

CASES = ROOT / "benchmarks_multiturn" / "cases_str_workflow.json"
OUT_DIR = ROOT / "_experiments" / "results_RQ3"

# ── §VII section keyword patterns (identical to the ground-truth Appendix B analysis) ──
SECTION_PATTERNS = {
    "VII.1 subjects": [r"계좌\s*\d+", r"출금계좌|입금계좌", r"사업자|법인|개인"],
    "VII.2 date": [r"202\d년", r"20\d{6}", r"\d+분기|\d+월|상반기|하반기",
                   r"\d{1,2}~\d{1,2}시|\d{1,2}시|심야|새벽|오전|오후|저녁|당일|익일"],
    "VII.3 place": [r"출금금융회사|입금금융회사|금융회사\s*\d+", r"지점|영업점|기관"],
    "VII.4 instrument": [r"현금|수표|주식|채권|외환|이체|대체|전자화폐|유가증권",
                         r"자금구분|매체구분", r"PC뱅킹|인터넷뱅킹|ATM|모바일|콜센터"],
    "VII.5 method": [r"심야|새벽|연속|반복|다수|복수|동시", r"분할|구조화|스머핑|smurfing",
                     r"거액|고액|급격|급증|급변|패턴|이상", r"다중|chain|체인"],
    "VII.6 grounds": [r"AI|예측|모델|확률|prob", r"이상거래|이상\s*확률|위험도|risk",
                      r"네트워크|연결\s*계좌|군집|클러스터", r"\d+\.?\d*\s*%|\d+%"],
}
WH_PATTERNS = {  # VII.7 종합의견: 6-W, averaged
    "who": [r"계좌\s*\d+|사업자|법인|개인|거래자"],
    "when": [r"202\d년|20\d{6}|분기|월|시|심야|새벽|당일|익일"],
    "where": [r"금융회사|지점|영업점|기관"],
    "what": [r"거래|이체|입금|출금|송금|예금|환전|매수|매도"],
    "how": [r"분할|구조화|structuring|반복|다수|연속|심야|현금|이체|패턴"],
    "why": [r"의심|혐의|자금세탁|범죄|불법|탈세|구조화|회피"],
}

# ── regulatory terminology (FATF/FIU STR domain), category-grouped; score = fraction
#    of categories the model's STR narrative invokes. Measures whether the report is
#    written in the register a compliance officer expects, not just factually. ──
TERM_PATTERNS = {
    "str_report": [r"의심거래보고|의심\s*거래|STR|혐의거래|보고대상|보고\s*의무"],
    "money_laundering": [r"자금\s*세탁|money\s*laundering|범죄수익|불법\s*자금|탈세"],
    "cdd_kyc": [r"고객\s*확인|CDD|KYC|실소유자|실제\s*소유자|beneficial\s*owner|신원\s*확인"],
    "aml_cft": [r"자금세탁방지|AML|CFT|테러\s*자금|FIU|금융정보분석원|특정금융정보법|특금법"],
    "typology": [r"구조화|분할\s*거래|스머핑|structuring|smurfing|차명|대포통장|자금\s*흐름"],
    "risk": [r"위험\s*기반|risk[-\s]*based|고위험|위험도|이상\s*거래|모니터링"],
}


def cohort(*settings: str) -> tuple[list[str], list[str], int]:
    """(scored, not scored, cohort size) for the settings this step reads."""
    todo = load.missing()
    have = todo[list(settings)].all(axis=1)
    return (todo.loc[have, "config_id"].tolist(),
            todo.loc[~have, "config_id"].tolist(), len(todo))


def terminology_score(summary):
    """Fraction of regulatory-terminology categories present in the STR narrative (0-1)."""
    return round(sum(_match_any(summary, p) for p in TERM_PATTERNS.values()) / len(TERM_PATTERNS), 4)


def _match_any(text, patterns):
    return 1.0 if any(re.search(p, text) for p in patterns) else 0.0


def section_coverage(summary):
    """Return per-section 0/1 (VII.7 is the 6-W mean) and the overall mean."""
    cov = {sec: _match_any(summary, pats) for sec, pats in SECTION_PATTERNS.items()}
    wh = sum(_match_any(summary, p) for p in WH_PATTERNS.values()) / len(WH_PATTERNS)
    cov["VII.7 6W summary"] = round(wh, 4)
    cov["overall"] = round(sum(cov.values()) / len(cov), 4)
    return cov


# ── entity extraction (digit-based, objectively checkable) ──
_ENT = [
    re.compile(r"\d[\d,]*\s*(?:만원|억원|원)"),   # amounts
    re.compile(r"\d+\.?\d*\s*%"),                  # percentages
    re.compile(r"0\.\d+"),                          # probabilities
    re.compile(r"(?<!\d)\d{4,7}(?!\d)"),           # account/institution serials
    #            ^ digit-boundary lookarounds (not \b): Korean particles like
    #              "330021로/에서/의" follow digits directly, so \b would miss them.
]


def extract_entities(text):
    ents = set()
    for rx in _ENT:
        for m in rx.findall(text):
            digits = re.sub(r"[^\d]", "", m)
            if digits:
                ents.add(digits)
    return ents


def gold_str_turns(cases: list[dict]) -> dict[str, int]:
    """case id -> the turn whose gold call is generate_str, for the cases that have one."""
    turns = {}
    for case in cases:
        turn = next((t["turn"] for t in case["turns"]
                     if any(tc["name"] == "generate_str" for tc in (t.get("tool_calls") or ()))),
                    None)
        if turn is not None:
            turns[case["id"]] = turn
    return turns


def written_summaries() -> tuple[dict[tuple[str, str, int], str], int]:
    """(config, case, turn) -> the summary the model passed to generate_str."""
    calls = load.calls("oracle")
    calls = calls[calls["tool"] == "generate_str"]
    summaries, unparsed = {}, 0
    for call in calls.itertuples():
        key = (call.config_id, call.case_id, call.turn)
        if key in summaries:
            continue        # the first generate_str of the turn is the report
        arguments = call.arguments
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except (json.JSONDecodeError, ValueError):
                arguments = None
        if not isinstance(arguments, dict):
            unparsed += 1
            summaries[key] = ""
            continue
        summaries[key] = str(arguments.get("summary") or "")
    return summaries, unparsed


def main() -> int:
    gold = {case["id"]: case for case in json.loads(CASES.read_text(encoding="utf-8"))}
    str_turn = gold_str_turns(list(gold.values()))
    scenarios, _turns = load.multiturn("oracle")
    summaries, n_unparsed = written_summaries()
    scored, absent, n_configs = cohort("oracle")
    labels = load.configs()

    rows = []
    for config_id, frame in scenarios.groupby("config_id", sort=True):
        label = labels.loc[config_id, "label"] if config_id in labels.index else config_id
        n_with_str_turn = 0      # scenarios whose GOLD case has a generate_str turn
        n_produced = 0           # of those, the model actually called generate_str
        n_empty_summary = 0
        d1_list, halluc_list, ground_list, term_list = [], [], [], []
        sec_acc = {}
        for scenario_id in sorted(frame["scenario_id"]):
            case = gold.get(scenario_id)
            gs_turn_no = str_turn.get(scenario_id)
            if case is None or gs_turn_no is None:
                continue
            n_with_str_turn += 1

            summary = summaries.get((config_id, scenario_id, gs_turn_no))
            if summary is None:
                continue     # the model did not produce an STR at that turn
            n_produced += 1
            if not summary:
                n_empty_summary += 1

            # D1: field coverage
            cov = section_coverage(summary)
            d1_list.append(cov["overall"])
            for key, value in cov.items():
                sec_acc.setdefault(key, []).append(value)

            # D4: regulatory terminology register
            term_list.append(terminology_score(summary))

            # source facts = injected prior-turn tool_results (turns before generate_str)
            facts = json.dumps([t.get("tool_result") for t in case["turns"]
                                if t["turn"] < gs_turn_no and t.get("tool_result") is not None],
                               ensure_ascii=False)
            fact_digits = set(re.sub(r"[^\d]", "", x) for x in re.findall(r"\d[\d,]*", facts))
            ents = extract_entities(summary)
            if ents:
                grounded = sum(1 for e in ents if e in facts or e in fact_digits)
                ground_list.append(grounded / len(ents))
                halluc_list.append(1 - grounded / len(ents))

        base = {"config_id": config_id, "label": label,
                "group": labels.loc[config_id, "group"] if config_id in labels.index else "",
                "n_str_turn": n_with_str_turn, "n_produced": n_produced,
                "n_empty_summary": n_empty_summary, "n_entity_scored": len(ground_list)}
        if n_produced == 0:
            rows.append(base | {"str_production_rate": 0.0, "field_coverage": None,
                                "grounding": None, "terminology": None,
                                "hallucination": None, "str_overall": None,
                                "field_cond": None, "grounding_cond": None,
                                "terminology_cond": None, "hallucination_cond": None})
            continue

        # PENALIZED scoring (default): a scenario where the model failed to call
        # generate_str when it should have is a genuine failure (it called the wrong
        # tool / re-ran analysis), so it scores 0 on every quality axis. Field/Ground/
        # Term are therefore summed over produced STRs but divided by ALL n_with_str_turn
        # STR-expected scenarios (non-produced contribute 0). Hallucination is the
        # complement of grounding under this convention (penalized fidelity).
        def pen(values):
            return round(sum(values) / n_with_str_turn, 4) if n_with_str_turn else None
        field_cov = pen(d1_list)
        grounding = pen(ground_list)
        term = pen(term_list)
        # Penalized hallucination = 1 - penalized fidelity, where fidelity sums per-STR
        # (1 - halluc) over produced and divides by all STR-expected scenarios. A scenario
        # with no STR contributes 0 fidelity -> it raises the hallucination figure.
        fidelity = pen([1 - h for h in halluc_list])  # produced fidelity, penalized
        halluc = round(1 - fidelity, 4) if fidelity is not None else None
        # Overall = mean of Field, Ground., Term (all penalized, higher=better).
        # Fidelity is deliberately NOT averaged in: hallucination is defined as the
        # complement of grounding, so fidelity == grounding and including both would
        # weight grounding twice. Hallucination stays in the row as a diagnostic column.
        comps = [c for c in (field_cov, grounding, term) if c is not None]
        str_overall = round(sum(comps) / len(comps), 4) if comps else None

        # conditional (produced-only) quality kept for reference / sensitivity analysis
        def cavg(values):
            return round(sum(values) / len(values), 4) if values else None
        row = base | {
            "str_production_rate": round(n_produced / n_with_str_turn, 4) if n_with_str_turn else 0.0,
            "field_coverage": field_cov,
            "grounding": grounding,
            "terminology": term,
            "hallucination": halluc,
            "str_overall": str_overall,
            # produced-only (conditional) — reference columns
            "field_cond": cavg(d1_list),
            "grounding_cond": cavg(ground_list),
            "terminology_cond": cavg(term_list),
            "hallucination_cond": cavg(halluc_list),
        }
        for key, values in sec_acc.items():
            row[f"cov::{key}"] = round(sum(values) / len(values), 4)
        rows.append(row)

    if not any(r["n_produced"] for r in rows):
        print("NO STR CALLS: no configuration called generate_str at the gold turn in the "
              "oracle run records. Check that the records under "
              f"{load.DEFAULT_RUN_ROOT / 'mt_oracle'} belong to the scored runs.")
        return 1

    payload = {
        "n_configs": n_configs,
        "n_scored": len(rows),
        "missing_config_ids": absent,
        "n_str_scenarios": len(str_turn),
        "n_scenarios": int(scenarios["scenario_id"].nunique()),
        "n_unparsed_arguments": n_unparsed,
        "note": ("field_coverage, grounding and terminology are penalized: summed over the "
                 "STRs the model produced and divided by every scenario whose gold case has a "
                 "generate_str turn (n_str_turn). *_cond are the produced-only means over "
                 "n_produced. hallucination = 1 - penalized fidelity."),
        "rows": rows,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "str_generation_quality.json", "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    base_cols = ["config_id", "label", "group", "n_str_turn", "n_produced", "n_empty_summary",
                 "n_entity_scored", "str_production_rate", "field_coverage", "grounding",
                 "terminology", "hallucination", "str_overall"]
    sec_cols = sorted({k for r in rows for k in r if k.startswith("cov::")})
    with open(OUT_DIR / "str_generation_quality.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=base_cols + sec_cols)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in base_cols + sec_cols})

    print(f"[STR-quality] {len(rows)} of {n_configs} configurations, "
          f"{len(str_turn)} of {payload['n_scenarios']} scenarios end in generate_str")
    if absent:
        print(f"  not scored: {', '.join(absent)}")
    if n_unparsed:
        print(f"  {n_unparsed} generate_str call(s) had arguments that never parsed into an "
              f"object; they count as produced with an empty narrative")
    for row in sorted(rows, key=lambda r: -(r["str_production_rate"] or 0)):
        print(f"  {row['label'][:26]:26s} produced {row['n_produced']:>2}/{row['n_str_turn']:<2} "
              f"({row['str_production_rate']:.2f})  field={row['field_coverage']} "
              f"ground={row['grounding']} term={row['terminology']} "
              f"halluc={row['hallucination']} overall={row['str_overall']}")
    print(f"  written: {OUT_DIR / 'str_generation_quality.json'}, "
          f"{OUT_DIR / 'str_generation_quality.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
