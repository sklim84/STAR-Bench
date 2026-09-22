#!/usr/bin/env python3
"""Build the blind item set for the expert evaluation of generated STRs.

The automatic STR checker (``RQ_str_generation_quality.py``) scores a report by
regular expression. Whether those scores track what a compliance practitioner
sees in the same report is a separate question, and answering it needs the same
reports read by a person. This script produces the package that evaluation runs
on: one blind item per (configuration, scenario) draft, carrying the evidence
the rater needs to judge grounding, and a private mapping that puts the model
name back.

SELECTION
---------
Configurations: three, spanning the checker's range at the draft level -- the
run's high, middle and low tiers. Scenarios: stratified by ``sub_category`` over
those where all three configurations wrote a non-empty report, so every scenario
contributes one draft per tier and the strata keep the benchmark's proportions.
A draft whose ``generate_str`` arguments never parsed is not a report and is
excluded; that failure is already reported as ``n_unparsed_arguments``.

Codes S01..Snn are assigned by a seeded shuffle, so neither the model nor the
tier is recoverable from an item's position.

Re-running with the same seed on the same run records reproduces the package;
a re-run of the benchmark changes the drafts, and the package must then be
rebuilt and re-rated -- ratings are tied to the drafts they were given.

Usage:  PYTHONPATH=. python _experiments/scripts/build_str_human_eval.py
Output: _experiments/human_eval/<round>/str_eval_{items,mapping}.json  (git-ignored)
"""
from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _experiments.scripts import RQ_str_generation_quality as Q  # noqa: E402
from _experiments.scripts.analysis import load  # noqa: E402

OUT_DIR = ROOT / "_experiments" / "human_eval"
STRATA = {"base": 4, "missing_parameter": 4, "long_context": 7}


def written_calls() -> dict[tuple[str, str, int], dict]:
    """(config, case, turn) -> the whole argument object the model passed to generate_str.

    The checker reads the narrative ``summary``; a rater reads the report, which is
    the call as written, so the package carries the full object.
    """
    calls = load.calls("oracle")
    calls = calls[calls["tool"] == "generate_str"]
    out = {}
    for call in calls.itertuples():
        key = (call.config_id, call.case_id, call.turn)
        if key in out:
            continue
        arguments = call.arguments
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except (json.JSONDecodeError, ValueError):
                arguments = None
        out[key] = arguments if isinstance(arguments, dict) else {}
    return out


def draft_scores(summary: str, case: dict, str_turn: int) -> dict:
    """The checker's four numbers for one written report."""
    cov = Q.section_coverage(summary)
    facts = json.dumps([t.get("tool_result") for t in case["turns"]
                        if t["turn"] < str_turn and t.get("tool_result") is not None],
                       ensure_ascii=False)
    fact_digits = {re.sub(r"[^\d]", "", x) for x in re.findall(r"\d[\d,]*", facts)}
    entities = Q.extract_entities(summary)
    grounding = (sum(1 for e in entities if e in facts or e in fact_digits) / len(entities)
                 if entities else None)
    term = Q.terminology_score(summary)
    overall = statistics.mean([v for v in (cov["overall"], grounding, term) if v is not None])
    return {"field": round(cov["overall"], 4),
            "grounding": None if grounding is None else round(grounding, 4),
            "term": round(term, 4),
            "halluc": None if grounding is None else round(1 - grounding, 4),
            "overall": round(overall, 4)}


def tiers(summaries, gold, str_turn, labels) -> list[str]:
    """The high, middle and low configuration by mean draft-level overall score."""
    ranked = []
    for config_id in labels.index:
        scores = [draft_scores(s, gold[sid], turn)["overall"]
                  for sid, turn in str_turn.items()
                  if (s := summaries.get((config_id, sid, turn)))]
        if len(scores) >= 20:          # a tier needs enough drafts to be one
            ranked.append((statistics.mean(scores), config_id))
    ranked.sort(reverse=True)
    return [ranked[0][1], ranked[len(ranked) // 2][1], ranked[-1][1]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", default="round2")
    ap.add_argument("--seed", type=int, default=20260923)
    ap.add_argument("--configs", nargs=3, help="labels to override the automatic tiers")
    args = ap.parse_args()

    gold = {case["id"]: case for case in json.loads(Q.CASES.read_text(encoding="utf-8"))}
    str_turn = Q.gold_str_turns(list(gold.values()))
    summaries, _ = Q.written_summaries()
    drafts = written_calls()
    labels = load.configs()

    if args.configs:
        by_label = {row["label"]: index for index, row in labels.iterrows()}
        chosen = [by_label[label] for label in args.configs]
    else:
        chosen = tiers(summaries, gold, str_turn, labels)

    written = [sid for sid, turn in str_turn.items()
               if all((summaries.get((c, sid, turn)) or "").strip() for c in chosen)]
    rng = random.Random(args.seed)
    picked = []
    for stratum, want in STRATA.items():
        pool = sorted(s for s in written if gold[s]["sub_category"] == stratum)
        if len(pool) < want:
            raise SystemExit(f"{stratum}: {len(pool)} scenarios available, {want} wanted")
        picked += rng.sample(pool, want)

    pairs = [(config_id, sid) for sid in sorted(picked) for config_id in chosen]
    rng.shuffle(pairs)

    items, mapping = [], []
    for position, (config_id, sid) in enumerate(pairs, start=1):
        code = f"S{position:02d}"
        case, turn = gold[sid], str_turn[sid]
        summary = summaries[(config_id, sid, turn)]
        checker = draft_scores(summary, case, turn)
        items.append({
            "code": code,
            "category": case["sub_category"],
            "fraud_type": case["fraud_type_name"],
            "scenario": case["scenario"],
            "turns": [{"turn": t["turn"], "user": t["content"], "result": t.get("tool_result")}
                      for t in case["turns"] if t["turn"] < turn],
            "draft": drafts.get((config_id, sid, turn)) or {"summary": summary},
            "checker": checker,
        })
        mapping.append({"code": code, "config_id": config_id,
                        "model_name": labels.loc[config_id, "label"],
                        "scenario_id": sid, "checker": checker})

    out = OUT_DIR / args.round
    out.mkdir(parents=True, exist_ok=True)
    (out / "str_eval_items.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "str_eval_mapping.json").write_text(json.dumps(
        {"note": f"S code -> model. Not shown to raters. seed={args.seed}, "
                 f"tiers={[labels.loc[c, 'label'] for c in chosen]}",
         "items": mapping}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(items)} items -> {out}")
    print("tiers:", ", ".join(labels.loc[c, "label"] for c in chosen))
    print("scenarios:", len(picked), "of", len(written), "with a report from all three")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
