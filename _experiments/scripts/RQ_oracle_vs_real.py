#!/usr/bin/env python3
"""Oracle vs. real end-to-end comparison for the multi-turn STR workflow.

The default multi-turn evaluation is an ORACLE setting: at every turn the ground-truth
tool call and ground-truth tool_result are injected into the history, so each turn is
scored against a perfect prior context (the model never sees its own mistakes). The
``real`` setting (benchmark_multiturn.py --setting real) instead executes the model's
OWN tool calls on the live HOFINET backend and feeds the real results forward, so
errors propagate across turns — an end-to-end run.

This script loads the two result directories and reports, per model, the standard
multi-turn metrics under each setting and the oracle->real drop. The point is
diagnostic (where/why the workflow breaks), not a leaderboard: a large oracle->real
gap localizes how much performance depends on perfect upstream context.

Usage:
  PYTHONPATH=. python _experiments/scripts/RQ_oracle_vs_real.py \
      --oracle _experiments/results_mt_oracle/eval --real _experiments/results_mt_real/eval
Output: _experiments/results_RQ3/oracle_vs_real.{json,csv}
"""
import json
import csv
import argparse
from pathlib import Path

SB = Path(__file__).resolve().parents[2]
OUT_DIR = SB / "_experiments" / "results_RQ3"

EXCLUDE = {
    "Qwen_Qwen3-30B-A3B-Instruct-2507", "Qwen_Qwen3-4B-Instruct-2507", "Qwen_Qwen3-8B",
    "Qwen_Qwen3_5-9B__nothink", "Qwen_Qwen3_5-9B__think",
    "Salesforce_Llama-xLAM-2-8b-fc-r", "Salesforce_xLAM-2-1b-fc-r", "Salesforce_xLAM-2-32b-fc-r",
    "kakaocorp_kanana-2-30b-a3b-instruct-2601",
}

METRICS = ["avg_tool_hit", "avg_param_accuracy", "context_accuracy", "scenario_complete_rate"]


def load_dir(d):
    """model_key -> overall metrics dict, from eval/multiturn_*.json files."""
    out = {}
    for f in sorted(Path(d).glob("multiturn_*.json")):
        stem = f.stem.replace("multiturn_", "")
        if stem in EXCLUDE:
            continue
        data = json.load(open(f, encoding="utf-8"))
        scs = data.get("scenarios", [])
        if not scs:
            continue
        # recompute overall from scenarios (robust to schema)
        def mean(key):
            vals = [s[key] for s in scs if s.get(key) is not None]
            return round(sum(vals) / len(vals), 4) if vals else None
        comp = [1.0 if s.get("scenario_complete") else 0.0 for s in scs]
        out[stem] = {
            "model": data.get("model", stem),
            "avg_tool_hit": mean("avg_tool_hit"),
            "avg_param_accuracy": mean("avg_param_accuracy"),
            "context_accuracy": mean("context_accuracy"),
            "scenario_complete_rate": round(sum(comp) / len(comp), 4) if comp else None,
            "n": len(scs),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oracle", default=str(SB / "_experiments/results_mt_oracle/eval"))
    ap.add_argument("--real", default=str(SB / "_experiments/results_mt_real/eval"))
    args = ap.parse_args()

    oracle = load_dir(args.oracle)
    real = load_dir(args.real)
    if not real:
        print(f"NO REAL RESULTS in {args.real}.")
        print("Run: PYTHONPATH=. python -m _experiments.scripts.benchmark_multiturn \\")
        print("       --models <3 models> --setting real --output _experiments/results_mt_real/")
        print("(oracle results are the default run in _experiments/results_mt_oracle/).")
        return

    rows = []
    for k in sorted(set(oracle) & set(real)):
        o, r = oracle[k], real[k]
        row = {"model": o["model"], "n": o["n"]}
        for m in METRICS:
            ov, rv = o.get(m), r.get(m)
            row[f"oracle_{m}"] = ov
            row[f"real_{m}"] = rv
            row[f"drop_{m}"] = round(ov - rv, 4) if (ov is not None and rv is not None) else None
        rows.append(row)

    if not rows:
        print("No overlapping models between oracle and real result dirs.")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json.dump(rows, open(OUT_DIR / "oracle_vs_real.json", "w"), ensure_ascii=False, indent=2)
    cols = ["model", "n"] + [f"{p}_{m}" for m in METRICS for p in ("oracle", "real", "drop")]
    with open(OUT_DIR / "oracle_vs_real.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    print(f"[oracle-vs-real] {len(rows)} models")
    print(f"  {'model':30s} {'h̄ orac→real':>16s} {'complete orac→real':>20s}")
    for r in rows:
        print(f"  {r['model'][:30]:30s} "
              f"{str(r['oracle_avg_tool_hit'])+'→'+str(r['real_avg_tool_hit']):>16s} "
              f"{str(r['oracle_scenario_complete_rate'])+'→'+str(r['real_scenario_complete_rate']):>20s}")


if __name__ == "__main__":
    main()
