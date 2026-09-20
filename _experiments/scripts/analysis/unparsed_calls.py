"""How often did a model name the right tool in text that never became a call?

A configuration whose h is low because the serving stack could not parse what the
model wrote is not a result about the model. Phi-4-mini recorded 124 tool calls
over 1,258 cases while 911 of its answers carried a JSON function-call structure
in the text, so its h reports the parser and not the model.

For every case with no parsed call, this reads the final text and asks whether
the gold tool is named in it. The `recoverable` column is the share of scored
cases where the gold tool was named but no call was recorded, and `h_ceiling` is
what h would be if every one of those had parsed. A configuration with a large
gap between h and h_ceiling has a serving problem to fix before its row means
anything.

    python -m _experiments.scripts.analysis.unparsed_calls
    python -m _experiments.scripts.analysis.unparsed_calls --configs phi-4-mini,gemma-4-e4b
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from _experiments.scripts.analysis import load  # noqa: E402

RUN_ROOT = _ROOT / "_experiments" / "results_2026rerun"
# Shapes a model reaches for when it cannot produce a native call. The first is an
# OpenAI tool-call or tool-definition object, the second Phi's documented marker,
# the third a special token the template rendered as text.
SHAPES = {
    "json_call": re.compile(r'"(?:name|function)"\s*:\s*"?[A-Za-z_]'),
    "functools": re.compile(r"functools\s*[\[\(]"),
    "broken_token": re.compile(r"\[_?FUNCTIO|<\|tool", re.I),
}


def _records(config_id: str) -> dict[str, dict]:
    directory = RUN_ROOT / "single" / config_id
    files = [p for p in sorted(directory.glob("*.jsonl")) if "partial" not in p.name]
    out = {}
    for path in files:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                out[record["case_id"]] = record
    return out


def audit(config_id: str, cases) -> dict:
    records = _records(config_id)
    rows = cases[cases["config_id"] == config_id].set_index("case_id")
    n_scored = len(rows)
    recoverable = shapes = no_call = 0
    shape_counts = {k: 0 for k in SHAPES}
    for case_id, record in records.items():
        if case_id not in rows.index:
            continue
        row = rows.loc[case_id]
        called = {c.get("name") for r in record.get("rounds") or ()
                  for c in r.get("tool_calls") or ()}
        gold = set(row["gold_tools"])
        if not gold or gold <= called:
            continue
        no_call += 1 if not called else 0
        text = record.get("final_text") or ""
        for name, pattern in SHAPES.items():
            if pattern.search(text):
                shape_counts[name] += 1
        if any(p.search(text) for p in SHAPES.values()):
            shapes += 1
        if all(re.search(r'["\[\s(]%s["\],\s(]' % re.escape(t), text) for t in gold):
            recoverable += 1
    h = float(rows["h"].mean())
    return {"config_id": config_id, "n": n_scored, "h": h,
            "h_ceiling": h + recoverable / n_scored if n_scored else h,
            "recoverable": recoverable, "call_shaped_text": shapes,
            "no_call_at_all": no_call, **shape_counts}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--configs", help="comma-separated ids; default every scored one")
    args = parser.parse_args(argv)

    cases = load.single()
    ids = ([c.strip() for c in args.configs.split(",")] if args.configs
           else sorted(cases["config_id"].unique()))
    rows = [audit(config_id, cases) for config_id in ids]
    rows.sort(key=lambda r: -(r["h_ceiling"] - r["h"]))

    print(f"{'config':<18}{'n':>6}{'h':>7}{'h_ceiling':>10}{'gap':>7}"
          f"{'recover':>8}{'call-text':>10}{'json':>6}{'ftools':>7}{'token':>6}")
    print("-" * 85)
    for r in rows:
        print(f"{r['config_id']:<18}{r['n']:>6}{r['h']:>7.3f}{r['h_ceiling']:>10.3f}"
              f"{r['h_ceiling'] - r['h']:>7.3f}{r['recoverable']:>8}{r['call_shaped_text']:>10}"
              f"{r['json_call']:>6}{r['functools']:>7}{r['broken_token']:>6}")
    worst = [r for r in rows if r["h_ceiling"] - r["h"] >= 0.05]
    print(f"\ngap >= .05: {len(worst)} configuration(s)"
          + (": " + ", ".join(r["config_id"] for r in worst) if worst else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
