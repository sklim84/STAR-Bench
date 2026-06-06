#!/usr/bin/env python3
"""STR generation quality analysis — three diagnostic dimensions (per model).

Motivation (advisor direction): the benchmark's value is diagnostic — showing *where*
and *why* models break down when producing the STR, not a performance leaderboard.
The multi-turn task culminates in ``generate_str``; this script characterizes the
quality of the STR the model actually writes, along three axes:

  D1  Field coverage   — how well the model's STR narrative covers the seven Korean
                         FIU STR (Article VII) sub-sections, using the SAME keyword
                         patterns as the ground-truth coverage analysis (Appendix B),
                         applied to the MODEL-generated ``summary``.
  D2  Hallucination    — fraction of concrete entities (account serials, amounts,
                         percentages, probabilities) in the model summary that are
                         NOT present in the injected prior-turn ``tool_result`` facts.
  D3  Grounding        — fraction of those entities that ARE traceable to the injected
                         prior-turn ``tool_result`` facts (the complement view of D2).

Because the benchmark INJECTS ground-truth ``tool_result`` at every turn, the set of
facts the STR should be grounded on is known exactly, making D2/D3 measurable without
an external judge (entity level). Qualitative-claim faithfulness would need an
LLM-judge and is left as an optional extension.

DATA REQUIREMENT
----------------
Reads multi-turn eval JSONs that contain per-turn ``actual_tool_calls`` (the model's
generated arguments, incl. the ``generate_str`` ``summary``). These are produced only
by ``benchmark_multiturn.py`` AFTER the logging update; older eval files store scores
only. If no captured summaries are found, the script says so and exits (re-run needed).

Per model, statistics are computed only over scenarios where the model actually called
``generate_str``; the ``str_production_rate`` (how often an STR was produced at all) is
itself reported, since "did not produce an STR" is a primary failure mode.

Usage:  PYTHONPATH=. python _experiments/scripts/RQ_str_generation_quality.py
Output: _experiments/results_RQ3/str_generation_quality.{json,csv}
"""
import json
import re
import csv
import glob
from pathlib import Path

SB = Path(__file__).resolve().parents[2]
EVAL_DIR = SB / "_experiments" / "results_mt" / "eval"
CASES = SB / "benchmarks_multiturn" / "cases_str_workflow.json"
OUT_DIR = SB / "_experiments" / "results_RQ3"

# Canonical 28-model cohort filter (drop non-cohort variants + redundant Instruct-2601).
EXCLUDE = {
    "Qwen_Qwen3-30B-A3B-Instruct-2507", "Qwen_Qwen3-4B-Instruct-2507", "Qwen_Qwen3-8B",
    "Qwen_Qwen3_5-9B__nothink", "Qwen_Qwen3_5-9B__think",
    "Salesforce_Llama-xLAM-2-8b-fc-r", "Salesforce_xLAM-2-1b-fc-r", "Salesforce_xLAM-2-32b-fc-r",
    "kakaocorp_kanana-2-30b-a3b-instruct-2601",
}

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
    "how": [r"분할|반복|다수|연속|심야|현금|이체|패턴"],
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


def main():
    cases = {c["id"]: c for c in json.load(open(CASES, encoding="utf-8"))}

    rows = []
    no_capture = True
    for f in sorted(EVAL_DIR.glob("multiturn_*.json")):
        stem = f.stem.replace("multiturn_", "")
        if stem in EXCLUDE:
            continue
        d = json.load(open(f, encoding="utf-8"))
        model = d.get("model", stem)
        n_with_str_turn = 0      # scenarios whose GT has a generate_str turn
        n_produced = 0           # of those, model actually called generate_str
        d1_list, halluc_list, ground_list, term_list = [], [], [], []
        sec_acc = {}
        for sc in d.get("scenarios", []):
            gt = cases.get(sc["id"])
            if not gt:
                continue
            gt_turns = gt["turns"]
            gs_turn_no = next((t["turn"] for t in gt_turns
                               if any(tc["name"] == "generate_str" for tc in (t.get("tool_calls") or []))), None)
            if gs_turn_no is None:
                continue
            n_with_str_turn += 1

            # model's actual generate_str call at that turn (needs captured actual_tool_calls)
            mturn = next((t for t in sc.get("turns", []) if t.get("turn") == gs_turn_no), None)
            calls = (mturn or {}).get("actual_tool_calls")
            if calls is None:
                continue  # no capture in this eval file
            no_capture = False
            gs_call = next((c for c in calls if c.get("name") == "generate_str"), None)
            if not gs_call:
                continue  # model did not produce an STR
            n_produced += 1
            summary = str(gs_call.get("arguments", {}).get("summary", "")) or ""

            # D1: field coverage
            cov = section_coverage(summary)
            d1_list.append(cov["overall"])
            for k, v in cov.items():
                sec_acc.setdefault(k, []).append(v)

            # D4: regulatory terminology register
            term_list.append(terminology_score(summary))

            # source facts = injected prior-turn tool_results (turns before generate_str)
            facts = json.dumps([t.get("tool_result") for t in gt_turns
                                if t["turn"] < gs_turn_no and t.get("tool_result") is not None],
                               ensure_ascii=False)
            fact_digits = set(re.sub(r"[^\d]", "", x) for x in re.findall(r"\d[\d,]*", facts))
            ents = extract_entities(summary)
            if ents:
                grounded = sum(1 for e in ents if e in facts or e in fact_digits)
                ground_list.append(grounded / len(ents))
                halluc_list.append(1 - grounded / len(ents))

        if n_produced == 0:
            rows.append({"model": model, "n_str_turn": n_with_str_turn, "n_produced": 0,
                         "str_production_rate": 0.0, "field_coverage": None,
                         "grounding": None, "terminology": None,
                         "hallucination": None, "str_overall": None})
            continue

        def avg(x):
            return round(sum(x) / len(x), 4) if x else None
        field_cov = avg(d1_list)
        grounding = avg(ground_list)
        halluc = avg(halluc_list)
        term = avg(term_list)
        # Overall (Table VII): mean of Field, Ground., Term, and (1 - Halluc.) — all
        # oriented so higher is better. Reported only when the components exist.
        comps = [c for c in (field_cov, grounding, term,
                             (1 - halluc) if halluc is not None else None) if c is not None]
        str_overall = round(sum(comps) / len(comps), 4) if comps else None
        row = {
            "model": model,
            "n_str_turn": n_with_str_turn,
            "n_produced": n_produced,
            "str_production_rate": round(n_produced / n_with_str_turn, 4) if n_with_str_turn else 0.0,
            "field_coverage": field_cov,
            "grounding": grounding,
            "terminology": term,
            "hallucination": halluc,
            "str_overall": str_overall,
        }
        for k, v in sec_acc.items():
            row[f"cov::{k}"] = round(sum(v) / len(v), 4)
        rows.append(row)

    if no_capture:
        print("NO CAPTURED SUMMARIES: eval files lack per-turn 'actual_tool_calls'.")
        print("Re-run benchmark_multiturn.py (with the logging update) to capture model")
        print("generate_str outputs, then re-run this analysis.")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json.dump(rows, open(OUT_DIR / "str_generation_quality.json", "w"),
              ensure_ascii=False, indent=2)
    base_cols = ["model", "n_str_turn", "n_produced", "str_production_rate",
                 "field_coverage", "grounding", "terminology", "hallucination", "str_overall"]
    sec_cols = sorted({k for r in rows for k in r if k.startswith("cov::")})
    with open(OUT_DIR / "str_generation_quality.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=base_cols + sec_cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in base_cols + sec_cols})

    print(f"[STR-quality] {len(rows)} models analyzed")
    for r in sorted(rows, key=lambda x: -(x["str_production_rate"] or 0)):
        print(f"  {r['model'][:34]:34s} produced {r['n_produced']:>2}/{r['n_str_turn']:<2} "
              f"({r['str_production_rate']:.2f})  field={r['field_coverage']} "
              f"ground={r['grounding']} term={r.get('terminology')} "
              f"halluc={r['hallucination']} overall={r.get('str_overall')}")


if __name__ == "__main__":
    main()
