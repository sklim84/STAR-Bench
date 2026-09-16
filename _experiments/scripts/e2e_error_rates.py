"""End-to-end tool error and empty-result rates, attributed by cause (L3-001).

    python -m _experiments.scripts.e2e_error_rates
    python -m _experiments.scripts.e2e_error_rates --results _experiments/results_2026rerun/e2e
    python -m _experiments.scripts.e2e_error_rates --out _experiments/results_RQ3 --list-unmatched

The appendix caption said "5,550 calls, 30 errors (0.5%)" and read the E2E drop
as errors propagating from the model. Both numbers came from a reader that
looked for an error object at the top level while the tool layer returns its
result as a JSON *string*, so an error inside that string was invisible. Read
properly, 1,324 of the same 5,550 calls carried an error (23.9%) and most of
them were the platform's own defects, not the model's: NaN conversions in
`get_account_profile`, a missing `predict_prob` key, a Memgraph host that was
not running.

The distinction is what the caption needs. A call is attributed to exactly one
cause, by the first rule that matches its message, and the rules are grouped
into two families:

  platform / environment   a defect or a missing dependency on our side. These
                           disappear when the platform is fixed and say nothing
                           about the model.
  model                    the model asked for something the tool refuses: a
                           missing required argument, an out-of-enum value, an
                           un-executable SQL statement, a tool that does not
                           exist.

Empty results are counted separately and are not errors: a query that runs and
returns no row is a property of the data plus the model's filter, and 'No data
found' was 21.2% of the 2026 calls.

Input is either the Contract 2 run records of an end-to-end run (`*.jsonl` with
`rounds[].executed[]`) or the older multi-turn eval files
(`multiturn_*.json` with `turns[].executed_results[]`); both are read the same
way, so the number can be recomputed after the rerun with one command.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# (cause, family, pattern). First match wins, so the specific rules come first.
RULES: tuple[tuple[str, str, str], ...] = (
    ("graph_backend_absent", "platform", r"memgraph|bolt://|neo4j"),
    ("database_lock", "platform", r"could not set lock|database is locked"),
    ("platform_nan", "platform", r"cannot convert float nan to integer"),
    ("platform_key_error", "platform", r"unexpected error occurred during tool execution"),
    ("platform_model_artifact", "platform", r"feature_names mismatch|'predict_prob'|__round__"),
    ("entity_absent", "data", r"no transaction history|not found in (the )?hofinet|"
                              r"account .* does not exist|no such account"),
    ("model_unknown_tool", "model", r"^unknown tool\b"),
    ("model_missing_argument", "model", r"is required|\brequires \w|must be provided|"
                                        r"missing required|is empty\.?$"),
    ("model_bad_argument", "model", r"must be one of|must be an integer|must be '|"
                                    r"unknown pattern type|invalid literal for int|"
                                    r"input parameter error|out of range|invalid date range"),
    ("model_bad_sql", "model", r"binder error|parser error|catalog error|table or column not found|"
                               r"query execution error|syntax error|only select queries"),
)

EMPTY_PATTERNS = (r"no data found", r"no results", r"조회된 거래가 없습니다")


def _as_object(result):
    """The tool layer returns a JSON string; the old reader never looked inside it."""
    if isinstance(result, str):
        try:
            return json.loads(result)
        except (json.JSONDecodeError, ValueError):
            return result
    return result


def classify(result) -> tuple[str, str, str]:
    """Returns (status, cause, message). status is ok | empty | error."""
    obj = _as_object(result)
    if obj is None:
        return "error", "no_result_recorded", ""
    if isinstance(obj, dict) and obj.get("error") is not None:
        message = str(obj["error"])
        low = message.lower()
        for cause, family, pattern in RULES:
            if re.search(pattern, low):
                return "error", cause, message
        return "error", "other", message
    text = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    low = text.lower()
    if any(re.search(p, low) for p in EMPTY_PATTERNS):
        return "empty", "no_rows", ""
    if isinstance(obj, dict):
        rows = obj.get("result")
        if isinstance(rows, list) and not rows:
            return "empty", "no_rows", ""
        if obj.get("total_count") == 0:
            return "empty", "no_rows", ""
    if isinstance(obj, list) and not obj:
        return "empty", "no_rows", ""
    return "ok", "", ""


def family_of(cause: str) -> str:
    for name, family, _pattern in RULES:
        if name == cause:
            return family
    return "unattributed"


def _calls_from_eval(payload: dict):
    """The older multi-turn eval file: scenarios -> turns -> executed_results."""
    model = payload.get("model") or payload.get("model_id") or "?"
    for scenario in payload.get("scenarios", []):
        for turn in scenario.get("turns", []):
            for entry in turn.get("executed_results") or []:
                yield model, scenario.get("id"), turn.get("turn"), \
                    entry.get("name"), entry.get("result")


def _calls_from_records(path: Path):
    """Contract 2 run records: one JSON object per line, rounds -> executed."""
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            model = (record.get("config") or {}).get("config_id") \
                or (record.get("config") or {}).get("model") or "?"
            for round_record in record.get("rounds") or []:
                for entry in round_record.get("executed") or []:
                    result = entry.get("result")
                    if entry.get("error") is not None:
                        result = {"error": entry["error"].get("message", entry["error"])}
                    yield model, record.get("case_id"), record.get("turn"), \
                        entry.get("name"), result


def read_calls(results_dir: Path):
    files = sorted(results_dir.rglob("multiturn_*.json")) + sorted(results_dir.rglob("*.jsonl"))
    if not files:
        raise SystemExit(f"no multiturn_*.json or *.jsonl under {results_dir}")
    for path in files:
        if any(part.startswith("_") for part in path.relative_to(results_dir).parts[:-1]):
            continue      # _invalid_*, _contaminated_*, _backup
        if path.suffix == ".jsonl":
            yield from _calls_from_records(path)
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
            yield from _calls_from_eval(payload)


def summarise(calls) -> dict:
    total = 0
    by_status = Counter()
    by_cause = Counter()
    by_family = Counter()
    per_model = defaultdict(Counter)
    per_tool = defaultdict(Counter)
    examples: dict[str, str] = {}
    for model, _case, _turn, tool, result in calls:
        total += 1
        status, cause, message = classify(result)
        by_status[status] += 1
        per_model[model][status] += 1
        per_tool[tool or "?"][status] += 1
        if status == "error":
            by_cause[cause] += 1
            by_family[family_of(cause)] += 1
            per_model[model][f"cause:{cause}"] += 1
            per_tool[tool or "?"][f"cause:{cause}"] += 1
            examples.setdefault(cause, message[:160])

    def rate(n: int) -> float:
        return round(n / total, 4) if total else 0.0

    return {
        "total_calls": total,
        "ok": by_status["ok"], "empty": by_status["empty"], "error": by_status["error"],
        "error_rate": rate(by_status["error"]), "empty_rate": rate(by_status["empty"]),
        "by_cause": dict(by_cause.most_common()),
        "by_family": dict(by_family.most_common()),
        "family_rate": {family: rate(n) for family, n in by_family.items()},
        "examples": examples,
        "per_model": {m: dict(c) for m, c in sorted(per_model.items())},
        "per_tool": {t: dict(c) for t, c in sorted(per_tool.items())},
    }


def markdown(report: dict, results_dir: Path) -> str:
    total = report["total_calls"]
    lines = [f"# End-to-end tool error and empty-result rates",
             "",
             f"Source: `{results_dir}`. {total:,} executed tool calls.",
             "",
             f"| outcome | calls | share |",
             f"|---|---:|---:|",
             f"| answered | {report['ok']:,} | {report['ok'] / total:.1%} |",
             f"| empty result | {report['empty']:,} | {report['empty_rate']:.1%} |",
             f"| error | {report['error']:,} | {report['error_rate']:.1%} |",
             "",
             "## Errors by cause",
             "",
             "| cause | family | calls | share of all calls |",
             "|---|---|---:|---:|"]
    for cause, n in report["by_cause"].items():
        lines.append(f"| `{cause}` | {family_of(cause)} | {n:,} | {n / total:.1%} |")
    lines += ["", "## Errors by family", "",
              "| family | calls | share of all calls |", "|---|---:|---:|"]
    for family, n in report["by_family"].items():
        lines.append(f"| {family} | {n:,} | {n / total:.1%} |")
    lines += ["",
              "`platform` and `data` causes are ours, not the model's: a caption that reads the "
              "end-to-end drop as error propagation has to subtract them.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", default="_experiments/results_mt_real",
                    help="directory of end-to-end records or eval files")
    ap.add_argument("--out", default="_experiments/results_RQ3",
                    help="directory for e2e_error_rates.json and .md")
    ap.add_argument("--list-unmatched", action="store_true",
                    help="print the error messages that fell through to `other`")
    args = ap.parse_args(argv)

    results_dir = Path(args.results)
    if not results_dir.is_absolute():
        results_dir = ROOT / results_dir
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    calls = list(read_calls(results_dir))
    report = summarise(calls)
    report["results_dir"] = str(results_dir)
    (out_dir / "e2e_error_rates.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "e2e_error_rates.md").write_text(markdown(report, results_dir), encoding="utf-8")

    total = report["total_calls"]
    print(f"{total:,} executed calls: {report['ok']:,} answered, "
          f"{report['empty']:,} empty ({report['empty_rate']:.1%}), "
          f"{report['error']:,} error ({report['error_rate']:.1%})")
    for family, n in report["by_family"].items():
        print(f"  {family:14s} {n:6,} ({n / total:.1%})")
    if args.list_unmatched:
        for _model, _case, _turn, _tool, result in calls:
            status, cause, message = classify(result)
            if status == "error" and cause == "other":
                print(f"  unmatched: {message[:120]}")
    print(f"written: {out_dir / 'e2e_error_rates.json'}, {out_dir / 'e2e_error_rates.md'}")
    return 0


if __name__ == "__main__":
    if __package__ in (None, ""):
        sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
