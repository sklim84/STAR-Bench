#!/usr/bin/env python3
"""Agreement between the automatic STR checker and the expert raters.

The checker in ``RQ_str_generation_quality.py`` scores a report by regular
expression. This step asks a different question of the same reports: does what
the checker reports track what a practitioner reading the report sees? It pairs
each rated draft's human score with the checker's score on three matched
dimensions and reports rank agreement, plus agreement between the raters.

  required fields   human ``field``       vs  checker ``field``    (§VII coverage)
  evidence match    human ``grounding``   vs  checker ``grounding``
  regulatory register human ``terminology`` vs checker ``term``
  overall           human ``overall``     vs  checker ``overall``

Spearman's rho is the statistic: the human scale is five ordered levels and the
checker's is continuous, so only the ordering is comparable. ``grounding`` is
undefined for a report the entity extractor finds no figures in; those drafts
are dropped from that dimension alone and the n is reported.

The ratings arrive as the evaluation page's ``ratings`` documents, exported to
JSON as ``{"<slot>__<code>": {...}}`` or as the page's own export shape
``{"slot": ..., "ratings": {"<code>": {...}}}``; both are accepted, and several
files combine.

Usage:  python _experiments/scripts/analysis/str_human_agreement.py \
            --mapping _experiments/human_eval/round2/str_eval_mapping.json \
            --ratings _experiments/human_eval/round2/A.json ...
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scipy import stats

DIMENSIONS = [("field", "field", "required fields"),
              ("grounding", "grounding", "evidence match"),
              ("terminology", "term", "regulatory register"),
              ("overall", "overall", "overall")]


def load_ratings(path: Path) -> dict[str, dict[str, dict]]:
    """-> {slot: {code: scores}}, accepting either export shape."""
    blob = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, dict]] = {}
    if "ratings" in blob and isinstance(blob["ratings"], dict):
        slot = blob.get("slot") or path.stem
        for code, scores in blob["ratings"].items():
            out.setdefault(slot, {})[code] = scores
        return out
    for key, scores in blob.items():
        slot, _, code = key.partition("__")
        if code:
            out.setdefault(slot, {})[code] = scores
    return out


def spearman(pairs: list[tuple[float, float]]):
    if len(pairs) < 3:
        return None, None, len(pairs)
    human, auto = zip(*pairs)
    if len(set(human)) < 2 or len(set(auto)) < 2:
        return None, None, len(pairs)
    rho, p = stats.spearmanr(human, auto)
    return rho, p, len(pairs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mapping", required=True, type=Path)
    ap.add_argument("--ratings", required=True, nargs="+", type=Path)
    ap.add_argument("--out", type=Path, help="write the numbers as JSON")
    args = ap.parse_args()

    mapping = {row["code"]: row for row in json.loads(
        args.mapping.read_text(encoding="utf-8"))["items"]}
    slots: dict[str, dict[str, dict]] = {}
    for path in args.ratings:
        for slot, rated in load_ratings(path).items():
            slots.setdefault(slot, {}).update(rated)

    report = {"slots": {}, "inter_rater": {}}
    for slot in sorted(slots):
        rated = slots[slot]
        unknown = sorted(set(rated) - set(mapping))
        print(f"\n=== rater {slot} — {len(rated)} rated"
              + (f", {len(unknown)} codes not in the mapping: {unknown[:5]}" if unknown else "") + " ===")
        report["slots"][slot] = {"n_rated": len(rated), "unknown_codes": unknown, "dimensions": {}}
        for human_key, auto_key, label in DIMENSIONS:
            pairs = []
            for code, scores in rated.items():
                row = mapping.get(code)
                if row is None:
                    continue
                human, auto = scores.get(human_key), row["checker"].get(auto_key)
                if human in (None, 0) or auto is None:
                    continue           # 0 is the page's "not yet scored"
                pairs.append((float(human), float(auto)))
            rho, p, n = spearman(pairs)
            report["slots"][slot]["dimensions"][human_key] = {"rho": rho, "p": p, "n": n}
            shown = "n/a" if rho is None else f"rho={rho:+.3f}  p={p:.4f}"
            print(f"  {label:<20} {shown:<26} n={n}")

    names = sorted(slots)
    if len(names) == 2:
        a, b = names
        print(f"\n=== rater {a} vs rater {b} ===")
        for human_key, _auto, label in DIMENSIONS:
            pairs = [(float(slots[a][c][human_key]), float(slots[b][c][human_key]))
                     for c in sorted(set(slots[a]) & set(slots[b]))
                     if slots[a][c].get(human_key) and slots[b][c].get(human_key)]
            rho, p, n = spearman(pairs)
            report["inter_rater"][human_key] = {"rho": rho, "p": p, "n": n}
            shown = "n/a" if rho is None else f"rho={rho:+.3f}  p={p:.4f}"
            print(f"  {label:<20} {shown:<26} n={n}")

    if args.out:
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
