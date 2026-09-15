"""Adapter from the pre-audit checkpoints to Contract 2 run records.

For comparison and regression only. New results are never produced this way:
the old checkpoints are what the audit found wanting, and two of their gaps
cannot be filled after the fact.

What survives the conversion
    single-turn  the called tool names, in order, per case; the legacy
                 error_type as a run error when it was a system failure
    multi-turn   the model's actual tool calls WITH arguments, and in the
                 end-to-end runs the executed results, per turn

What cannot be recovered
    single-turn arguments   never stored (benchmark.py wrote evaluator output
        only), so every parameter check is marked not-applicable: a is None for
        every converted single-turn case and only h, r, p, o and f1 compare.
    final text              never stored in either runner, so abstention and
        clarification are judged by "no tool call" alone, which is the pre-D19
        rule; those cases are flagged in the record.
    tool results (single)   never stored, so sql_valid is re-executed by the
        scorer (or fails when execution is off).

Usage:
    python -m _experiments.scripts.scoring.legacy --checkpoint _experiments/results_kr/checkpoint \
        --out <scratch>/legacy_records
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.scoring"

SYSTEM_ERROR_TYPES = {"connection_error", "timeout_error", "api_error", "parse_fail", "other_error"}


def _error_from_legacy(error_type: str | None) -> tuple[dict | None, str | None]:
    if error_type in SYSTEM_ERROR_TYPES:
        return {"type": error_type, "message": "reconstructed from a legacy checkpoint"}, "error"
    return None, None


def single_turn_record(row: dict, *, run_id: str) -> dict:
    """One legacy single-turn checkpoint row as a Contract 2 record (without arguments)."""
    calls = [{"id": f"legacy{i}", "name": name, "arguments": None, "arguments_raw": None,
              "source": "native", "valid_json": None, "arguments_recorded": False}
             for i, name in enumerate(row.get("called_tools") or [])]
    error, stop = _error_from_legacy(row.get("error_type"))
    return {
        "run_id": run_id,
        "case_id": row.get("case_id") or row.get("id"),
        "setting": "single",
        "config": {"model": row.get("model")},
        "rounds": [{"idx": 0, "content": "", "tool_calls": calls, "executed": [], "error": None}],
        "final_text": "",
        "stop_reason": stop,
        "error": error,
        "elapsed_s": row.get("elapsed_sec"),
        "legacy": {"arguments_recorded": False, "final_text_recorded": False,
                   "results_recorded": False, "legacy_error_type": row.get("error_type"),
                   "legacy_metrics": {k: row.get(k) for k in
                                      ("primary_tool_hit", "tool_recall", "tool_precision",
                                       "param_accuracy", "order_score", "score") if k in row}},
    }


def multiturn_records(row: dict, *, run_id: str) -> list[dict]:
    """One legacy multi-turn scenario row as one Contract 2 record per turn."""
    out = []
    setting = "e2e" if row.get("setting") == "real" else "oracle"
    for turn in row.get("turns") or []:
        calls, executed = [], []
        actual = turn.get("actual_tool_calls") or []
        results = turn.get("executed_results") or []
        for i, tc in enumerate(actual):
            call_id = tc.get("_id") or f"legacy{turn.get('turn')}_{i}"
            args = tc.get("arguments")
            calls.append({"id": call_id, "name": tc.get("name"), "arguments": args,
                          "arguments_raw": json.dumps(args, ensure_ascii=False, default=str),
                          "source": "fallback" if str(tc.get("_id", "")).startswith("parsed_") else "native",
                          "valid_json": isinstance(args, dict)})
            if i < len(results):
                executed.append({"tool_call_id": call_id, "name": results[i].get("name"),
                                 "arguments": results[i].get("arguments"),
                                 "result": results[i].get("result"), "error": None})
        out.append({
            "run_id": run_id,
            "case_id": row.get("id"),
            "turn": turn.get("turn"),
            "setting": setting,
            "config": {"model": row.get("model")},
            "rounds": [{"idx": 0, "content": "", "tool_calls": calls, "executed": executed, "error": None}],
            "final_text": "",
            "stop_reason": None,
            "error": None,
            "legacy": {"arguments_recorded": True, "final_text_recorded": False,
                       "results_recorded": bool(results),
                       "legacy_metrics": {k: turn.get(k) for k in
                                          ("tool_hit", "param_accuracy", "score", "context_hit",
                                           "clarification_hit") if k in turn}},
        })
    return out


def convert_file(path: Path, *, run_id: str | None = None) -> list[dict]:
    run_id = run_id or path.stem.replace("checkpoint_", "")
    records: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "turns" in row:
                records += multiturn_records(row, run_id=run_id)
            else:
                records.append(single_turn_record(row, run_id=run_id))
    return records


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--checkpoint", required=True, help="legacy checkpoint file or directory")
    ap.add_argument("--out", required=True, help="output directory for the converted JSONL records")
    args = ap.parse_args(argv)

    src = Path(args.checkpoint)
    files = [src] if src.is_file() else sorted(src.glob("*.jsonl"))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    for path in files:
        records = convert_file(path)
        target = out_dir / f"{path.stem.replace('checkpoint_', '')}.jsonl"
        with open(target, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        total += len(records)
        print(f"{path} -> {target} ({len(records)} records)")
    print(f"{total} records; single-turn records carry no arguments, so a is not applicable for them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
