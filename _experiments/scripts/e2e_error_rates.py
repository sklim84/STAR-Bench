"""End-to-end tool error and empty-result rates, attributed by cause (L3-001).

    python -m _experiments.scripts.e2e_error_rates
    python -m _experiments.scripts.e2e_error_rates --results _experiments/runs
    python -m _experiments.scripts.e2e_error_rates --out _experiments/results_RQ3 --list-unmatched

The appendix caption said "5,550 calls, 30 errors (0.5%)" and read the E2E drop
as errors propagating from the model. Both numbers came from a reader that
looked for an error object at the top level while the tool layer returns its
result as a JSON *string*, so an error inside that string was invisible. Read
properly, 1,324 of the same 5,550 pre-audit calls carried an error (23.9%) and
most of them were the platform's own defects, not the model's: NaN conversions
in `get_account_profile`, a missing `predict_prob` key, a Memgraph host that was
not running. This step recomputes the caption over the scored rerun.

The distinction is what the caption needs. A call is attributed to exactly one
cause, by the first rule that matches its message, and the rules are grouped
into two families:

  platform / environment   a defect or a missing dependency on our side. These
                           disappear when the platform is fixed and say nothing
                           about the model.
  model                    the model asked for something the tool refuses: a
                           missing required argument, an out-of-enum value, an
                           un-executable SQL statement, arguments that are not an
                           object, a tool or a glossary term that does not exist.

Empty results are counted separately and are not errors: a query that runs and
returns no row is a property of the data plus the model's filter, and 'No data
found' was 21.2% of the 2026 calls.

Ported to the scored rerun (see `analysis/PORTING.md`). The input is
`load.calls("e2e")` and nothing else: one row per tool call with `result` and
`result_error`, read from the Contract 2 records the runner wrote. `--results`
now names the run root that holds `mt_e2e/`, not a directory of eval files.

Two things the new records carry that the old reader did not know about:

  - `result_truncated` on an executed call is a delivery note, not an error. The
    result is there and is classified like any other; the count is reported as
    `truncated`.
  - a call whose arguments never parsed into an object was never executed. It
    has no result, and it is the model's failure, so it is attributed to
    `model_malformed_arguments` rather than to a missing result.

Only the end-to-end setting has executed results. The oracle setting injects the
gold tool result instead of calling the tool, so there is nothing there to count
and this step does not read it.

The output carries `n_configs` and the configurations that are not scored
(PORTING rule 4): 15 of the 28 have an end-to-end run today.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _experiments.scripts.analysis import load  # noqa: E402

# (cause, family, pattern). First match wins, so the specific rules come first.
#
# `platform_key_error` matches the tool layer's generic wrapper text, which is
# what most of the specific platform defects are wrapped in, so it has to come
# after every rule that names one of them: with it above, the 142 'predict_prob'
# and 4 __round__ messages were counted as generic and platform_model_artifact
# saw only `feature_names mismatch` (V-09). The family is `platform` either way,
# so the 863 / 281 / 180 split does not move; the cause table does.
RULES: tuple[tuple[str, str, str], ...] = (
    ("graph_backend_absent", "platform", r"memgraph|bolt://|neo4j"),
    ("database_lock", "platform", r"could not set lock|database is locked"),
    ("platform_nan", "platform", r"cannot convert float nan to integer"),
    ("platform_model_artifact", "platform", r"feature_names mismatch|'predict_prob'|__round__"),
    ("platform_key_error", "platform", r"unexpected error occurred during tool execution"),
    ("entity_absent", "data", r"no transaction history|not found in (the )?hofinet|"
                              r"account .* does not exist|no such account"),
    # The call never reached the tool: the model emitted a JSON string or a list
    # where the schema asks for an object.
    ("model_malformed_arguments", "model", r"^arguments are \w+, not an object"),
    ("model_unknown_tool", "model", r"^unknown tool\b"),
    # The AML glossary is keyed in Korean; a model that asks it for "cash" or
    # "virtual asset" gets this back.
    ("model_unknown_term", "model", r"^term '.*' not found"),
    ("model_missing_argument", "model", r"is required|\brequires \w|must be provided|"
                                        r"missing required|is empty\.?$"),
    ("model_bad_argument", "model", r"must be one of|must be an integer|must be a date|"
                                    r"must be '|unknown pattern type|invalid literal for int|"
                                    r"input parameter error|out of range|invalid date range"),
    ("model_bad_sql", "model", r"binder error|parser error|catalog error|table or column not found|"
                               r"query execution error|syntax error|only select queries"),
)

EMPTY_PATTERNS = (r"no data found", r"no results", r"조회된 거래가 없습니다")

# An executed call whose envelope carries this type still has its result: the
# tool answered and the runner shortened what it put back into the history.
TRUNCATION = "result_truncated"


def _as_object(result):
    """The tool layer returns a JSON string; the old reader never looked inside it."""
    if isinstance(result, str):
        try:
            return json.loads(result)
        except (json.JSONDecodeError, ValueError):
            return result
    return result


def _attribute(message: str) -> tuple[str, str, str]:
    low = message.lower()
    for cause, _family, pattern in RULES:
        if re.search(pattern, low):
            return "error", cause, message
    return "error", "other", message


def classify(result) -> tuple[str, str, str]:
    """Returns (status, cause, message). status is ok | empty | error."""
    obj = _as_object(result)
    if obj is None:
        return "error", "no_result_recorded", ""
    if isinstance(obj, dict) and obj.get("error") is not None:
        return _attribute(str(obj["error"]))
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


def classify_call(result, result_error) -> tuple[str, str, str, bool]:
    """(status, cause, message, truncated) for one recorded call."""
    envelope = result_error if isinstance(result_error, dict) else None
    if envelope is not None and envelope.get("type") != TRUNCATION:
        status, cause, message = _attribute(str(envelope.get("message") or envelope.get("type")))
        return status, cause, message, False
    truncated = envelope is not None and envelope.get("type") == TRUNCATION
    status, cause, message = classify(result)
    return status, cause, message, truncated


def family_of(cause: str) -> str:
    for name, family, _pattern in RULES:
        if name == cause:
            return family
    return "unattributed"


def cohort(setting: str) -> tuple[list[str], list[str], int]:
    """(scored, not scored, cohort size) for the setting this step reads."""
    todo = load.missing()
    return (todo.loc[todo[setting], "config_id"].tolist(),
            todo.loc[~todo[setting], "config_id"].tolist(), len(todo))


def read_calls(run_root: Path):
    """(config_id, case_id, turn, tool, result, result_error) per recorded call."""
    frame = load.calls("e2e", run_root=run_root)
    for call in frame.itertuples():
        yield (call.config_id, call.case_id, call.turn, call.tool,
               call.result, call.result_error)


def summarise(calls) -> dict:
    total = 0
    truncated_calls = 0
    by_status = Counter()
    by_cause = Counter()
    by_family = Counter()
    per_model = defaultdict(Counter)
    per_tool = defaultdict(Counter)
    examples: dict[str, str] = {}
    for model, _case, _turn, tool, result, result_error in calls:
        total += 1
        status, cause, message, truncated = classify_call(result, result_error)
        truncated_calls += truncated
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
        "truncated": truncated_calls, "truncated_rate": rate(truncated_calls),
        "by_cause": dict(by_cause.most_common()),
        "by_family": dict(by_family.most_common()),
        "family_rate": {family: rate(n) for family, n in by_family.items()},
        "examples": examples,
        "per_model": {m: dict(c) for m, c in sorted(per_model.items())},
        "per_tool": {t: dict(c) for t, c in sorted(per_tool.items())},
    }


def markdown(report: dict, results_dir: Path | str) -> str:
    total = report["total_calls"]
    lines = [f"# End-to-end tool error and empty-result rates",
             "",
             f"Source: `{results_dir}`, end-to-end setting. {total:,} executed tool calls "
             f"from {report['n_scored']} of {report['n_configs']} configurations.",
             "",
             f"| outcome | calls | share |",
             f"|---|---:|---:|",
             f"| answered | {report['ok']:,} | {report['ok'] / total:.1%} |",
             f"| empty result | {report['empty']:,} | {report['empty_rate']:.1%} |",
             f"| error | {report['error']:,} | {report['error_rate']:.1%} |",
             "",
             f"{report['truncated']:,} answered calls ({report['truncated_rate']:.1%}) were "
             f"shortened before they went back into the history. That is a delivery note, not "
             f"an error.",
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
    if report["missing_config_ids"]:
        lines += [f"{len(report['missing_config_ids'])} of {report['n_configs']} configurations "
                  f"have no end-to-end run and are not in these counts: "
                  f"{', '.join(report['missing_config_ids'])}.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", default=str(load.DEFAULT_RUN_ROOT),
                    help="run root holding the end-to-end records (mt_e2e/)")
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
    scored, absent, n_configs = cohort("e2e")
    report["setting"] = "e2e"
    report["n_configs"] = n_configs
    report["n_scored"] = len(report["per_model"])
    report["missing_config_ids"] = absent
    report["scored_config_ids"] = sorted(report["per_model"])
    # Relative to the repository root: the report is committed and a checkout
    # path is a property of the machine.
    report["results_dir"] = str(results_dir.relative_to(ROOT)) \
        if results_dir.is_relative_to(ROOT) else str(results_dir)
    (out_dir / "e2e_error_rates.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "e2e_error_rates.md").write_text(
        markdown(report, report["results_dir"]), encoding="utf-8")

    total = report["total_calls"]
    print(f"{total:,} executed calls from {report['n_scored']} of {n_configs} configurations: "
          f"{report['ok']:,} answered, "
          f"{report['empty']:,} empty ({report['empty_rate']:.1%}), "
          f"{report['error']:,} error ({report['error_rate']:.1%})")
    for family, n in report["by_family"].items():
        print(f"  {family:14s} {n:6,} ({n / total:.1%})")
    print(f"  truncated      {report['truncated']:6,} ({report['truncated_rate']:.1%}) "
          f"answered, shortened before going back into the history")
    if absent:
        print(f"  no end-to-end run: {', '.join(absent)}")
    if args.list_unmatched:
        for _model, _case, _turn, _tool, result, result_error in calls:
            status, cause, message, _truncated = classify_call(result, result_error)
            if status == "error" and cause == "other":
                print(f"  unmatched: {message[:120]}")
    print(f"written: {out_dir / 'e2e_error_rates.json'}, {out_dir / 'e2e_error_rates.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
