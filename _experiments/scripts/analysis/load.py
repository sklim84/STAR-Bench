"""One reader over the scored rerun, for every analysis script.

The analysis was written against the pre-audit checkpoints, where each case row
carried `primary_tool_hit`, `tool_recall`, `tool_precision`, `param_accuracy`,
`order_score` and a weighted `score`. Those keys are gone on purpose (D02): p and
o were 1.0 for a model that called nothing, a was 1.0 for a case with no checks,
and the weighted score has no definition in the paper. An adapter that put the
old names back over the new numbers would put those definitions back with them,
so the analysis reads the fixed metrics here instead:

    h r p a o f1_tools abstain_ok clarification_ok error_type error_flag

and, for the multi-turn settings, c and context_accuracy.

Everything comes from the eval files `scoring/score_runs.py` writes, joined to
the serving registry so a row knows its label, group and reasoning mode. Nothing
is recomputed here: an aggregate in a figure is the one the scorer wrote, or a
mean over the rows this module returns, never a third definition.

    from _experiments.scripts.analysis import load
    cases = load.single()                    # every configuration, Korean arm
    cases = load.single(column="entools_krq")
    scen, turns = load.multiturn("oracle")

Columns are named for what varies, not for the directory they sit in:
`single` is the main-table arm (Korean schema, Korean questions) and the other
three are the 2x2 arms. `load.COLUMNS` maps each to the directory it reads.
"""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from _experiments.scripts.runner import registry  # noqa: E402

__all__ = ["COLUMNS", "DEFAULT_EVAL_ROOT", "configs", "single", "multiturn", "aggregates",
           "missing"]

DEFAULT_EVAL_ROOT = _ROOT / "_experiments" / "results_2026rerun" / "eval"

# arm name -> (directory under the eval root, tool schema language, question language)
COLUMNS = {
    "single": ("single", "kr", "kr"),
    "entools_krq": ("single_entools_krq", "en", "kr"),
    "krtools_enq": ("single_krtools_enq", "kr", "en"),
    "entools_enq": ("single_entools_enq", "en", "en"),
}
SETTINGS = {"oracle": "mt_oracle", "e2e": "mt_e2e"}

# Per-case fields the scorer writes that an analysis may read. A field absent from
# a given case is None, never filled in: `a` is None for a case with no parameter
# checks, and a mean over it has to say how many cases it covered.
CASE_FIELDS = ("h", "r", "p", "a", "o", "f1_tools", "abstain_ok", "clarification_ok",
               "error_type", "error_flag", "stop_reason", "matched",
               "n_calls", "n_gold_calls", "n_checks", "hallucinated_param_count",
               "parser_artifacts", "malformed_arg_calls", "fallback_parsed_calls",
               "final_text_ok", "round_errors")
LIST_FIELDS = ("called_tools", "gold_tools", "extra_tools")
TURN_FIELDS = ("h", "r", "p", "a", "f1_tools", "context_hit", "clarification_ok",
               "matched", "n_calls", "n_gold_calls", "n_checks")


@lru_cache(maxsize=1)
def configs() -> pd.DataFrame:
    """The serving registry as a table, keyed by config_id."""
    rows = []
    for cfg in registry.CONFIGS:
        rows.append({
            "config_id": cfg.config_id, "label": cfg.label, "model": cfg.model,
            "group": cfg.group, "parser": cfg.parser,
            "reasoning_mode": cfg.reasoning_mode, "is_reasoning": cfg.is_reasoning,
            "max_model_len": cfg.max_model_len, "max_tokens": cfg.max_tokens,
            "model_window": cfg.model_window, "tp": cfg.tp,
        })
    return pd.DataFrame(rows).set_index("config_id", drop=False)


def _eval_files(directory: Path) -> list[tuple[str, Path]]:
    """(config_id, eval file) for every scored configuration under a column."""
    out = []
    for config_dir in sorted(p for p in directory.glob("*") if p.is_dir()):
        files = sorted(config_dir.glob("eval_*.json"))
        if not files:
            continue
        if len(files) > 1:
            raise RuntimeError(f"{config_dir} holds {len(files)} eval files; the column has to "
                               f"name one run per configuration")
        out.append((config_dir.name, files[0]))
    return out


def _meta_row(meta: dict) -> dict:
    provenance = meta.get("provenance") or {}
    config = meta.get("config") or {}
    return {
        "run_id": meta.get("run_id"), "setting": meta.get("setting"),
        "tools_lang": meta.get("tools_lang"), "query_lang": meta.get("query_lang"),
        "model_revision": config.get("model_revision"),
        "benchmark_sha256": provenance.get("benchmark_sha256"),
        "star_bench_commit": provenance.get("star_bench_commit"),
    }


def single(column: str = "single", *, eval_root: Path | str | None = None,
           configs_only: list[str] | None = None) -> pd.DataFrame:
    """One row per (configuration, case) for a single-turn arm."""
    if column not in COLUMNS:
        raise ValueError(f"unknown column {column!r}; one of {sorted(COLUMNS)}")
    directory = Path(eval_root or DEFAULT_EVAL_ROOT) / COLUMNS[column][0]
    if not directory.is_dir():
        raise FileNotFoundError(f"{directory} does not exist; score the runs first")
    meta_cols = configs()
    rows = []
    for config_id, path in _eval_files(directory):
        if configs_only and config_id not in configs_only:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        meta = _meta_row(payload["meta"])
        registry_row = meta_cols.loc[config_id] if config_id in meta_cols.index else None
        for case in payload["results"]:
            row = {"config_id": config_id, "column": column,
                   "tools_lang_arm": COLUMNS[column][1], "query_lang_arm": COLUMNS[column][2],
                   "case_id": case.get("case_id"), "category": case.get("category"),
                   "difficulty": case.get("difficulty")}
            row.update({k: case.get(k) for k in CASE_FIELDS})
            row.update({k: tuple(case.get(k) or ()) for k in LIST_FIELDS})
            row["n_hallucinated_params"] = len(case.get("hallucinated_params") or ())
            row.update(meta)
            if registry_row is not None:
                row.update({"label": registry_row["label"], "group": registry_row["group"],
                            "model": registry_row["model"],
                            "reasoning_mode": registry_row["reasoning_mode"],
                            "is_reasoning": registry_row["is_reasoning"]})
            rows.append(row)
    if not rows:
        raise FileNotFoundError(f"{directory} holds no scored configuration")
    return pd.DataFrame(rows)


def multiturn(setting: str = "oracle", *, eval_root: Path | str | None = None,
              configs_only: list[str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(one row per scenario, one row per turn) for a multi-turn setting."""
    if setting not in SETTINGS:
        raise ValueError(f"unknown setting {setting!r}; one of {sorted(SETTINGS)}")
    directory = Path(eval_root or DEFAULT_EVAL_ROOT) / SETTINGS[setting]
    if not directory.is_dir():
        raise FileNotFoundError(f"{directory} does not exist; score the runs first")
    meta_cols = configs()
    scenarios, turns = [], []
    for config_id, path in _eval_files(directory):
        if configs_only and config_id not in configs_only:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        meta = _meta_row(payload["meta"])
        registry_row = meta_cols.loc[config_id] if config_id in meta_cols.index else None
        extra = {}
        if registry_row is not None:
            extra = {"label": registry_row["label"], "group": registry_row["group"],
                     "model": registry_row["model"],
                     "reasoning_mode": registry_row["reasoning_mode"],
                     "is_reasoning": registry_row["is_reasoning"]}
        for scenario in payload["results"]:
            base = {"config_id": config_id, "setting": setting,
                    "scenario_id": scenario.get("case_id"),
                    "sub_category": scenario.get("sub_category")}
            scenarios.append(base | {
                "c": scenario.get("c"), "h_mean": scenario.get("h_mean"),
                "a_mean": scenario.get("a_mean"),
                "context_accuracy": scenario.get("context_accuracy"),
                "n_turns": scenario.get("n_turns"),
                "n_turns_with_checks": scenario.get("n_turns_with_checks"),
                "n_context_turns": scenario.get("n_context_turns"),
                "error_flag": scenario.get("error_flag"),
                "n_missing_turns": len(scenario.get("missing_turns") or ()),
            } | meta | extra)
            for turn in scenario.get("turns") or ():
                row = base | {"turn": turn.get("turn")}
                row.update({k: turn.get(k) for k in TURN_FIELDS})
                row.update({k: tuple(turn.get(k) or ()) for k in ("called_tools", "gold_tools")})
                turns.append(row | extra)
    if not scenarios:
        raise FileNotFoundError(f"{directory} holds no scored configuration")
    return pd.DataFrame(scenarios), pd.DataFrame(turns)


def aggregates(column_or_setting: str = "single", *,
               eval_root: Path | str | None = None) -> dict[str, dict]:
    """The scorer's own aggregate per configuration, for figures that want it whole."""
    if column_or_setting in COLUMNS:
        name = COLUMNS[column_or_setting][0]
    elif column_or_setting in SETTINGS:
        name = SETTINGS[column_or_setting]
    else:
        raise ValueError(f"unknown column or setting {column_or_setting!r}; one of "
                         f"{sorted(COLUMNS)} or {sorted(SETTINGS)}")
    directory = Path(eval_root or DEFAULT_EVAL_ROOT) / name
    return {config_id: json.loads(path.read_text(encoding="utf-8"))["aggregate"]
            for config_id, path in _eval_files(directory)}


def missing(*, eval_root: Path | str | None = None) -> pd.DataFrame:
    """Which of the 28 configurations are not scored yet, per column.

    A figure drawn while the cohort is incomplete has to say so, and a step that
    silently drops a row is the failure this table exists to prevent.
    """
    root = Path(eval_root or DEFAULT_EVAL_ROOT)
    rows = []
    for cfg in registry.CONFIGS:
        row = {"config_id": cfg.config_id, "label": cfg.label, "group": cfg.group}
        for name, (directory, _, _) in COLUMNS.items():
            row[name] = (root / directory / cfg.config_id).is_dir()
        for setting, directory in SETTINGS.items():
            row[setting] = (root / directory / cfg.config_id).is_dir()
        rows.append(row)
    return pd.DataFrame(rows)


# --- run records ------------------------------------------------------------
# The eval files hold scores, not what the model wrote. Two steps need the calls
# themselves: the STR quality table reads the report text the model passed to
# `validate_str_fields`, and the end-to-end error rates read what the tools
# answered. Both come from the Contract 2 records the runner wrote.

RECORD_DIRS = {
    "single": "single", "entools_krq": "single_entools_krq",
    "krtools_enq": "single_krtools_enq", "entools_enq": "single_entools_enq",
    "oracle": "mt_oracle", "e2e": "mt_e2e",
}
DEFAULT_RUN_ROOT = _ROOT / "_experiments" / "results_2026rerun"


def _record_files(directory: Path) -> list[tuple[str, Path]]:
    out = []
    for config_dir in sorted(p for p in directory.glob("*") if p.is_dir()):
        files = [p for p in sorted(config_dir.glob("*.jsonl")) if "partial" not in p.name]
        if files:
            out.append((config_dir.name, files[-1]))
    return out


def calls(column_or_setting: str = "single", *, run_root: Path | str | None = None,
          configs_only: list[str] | None = None) -> pd.DataFrame:
    """One row per tool call, with its arguments and what the tool answered.

    `source` says whether the gateway or the server parsed the call natively or
    the text fallback did (L5-010): a column whose calls are all `fallback` is a
    serving problem and not a model result, and a figure over it has to say so.
    """
    name = RECORD_DIRS.get(column_or_setting)
    if name is None:
        raise ValueError(f"unknown column or setting {column_or_setting!r}; one of "
                         f"{sorted(RECORD_DIRS)}")
    directory = Path(run_root or DEFAULT_RUN_ROOT) / name
    if not directory.is_dir():
        raise FileNotFoundError(f"{directory} does not exist")
    rows = []
    for config_id, path in _record_files(directory):
        if configs_only and config_id not in configs_only:
            continue
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                executed = {}
                for round_record in record.get("rounds") or ():
                    for item in round_record.get("executed") or ():
                        executed[item.get("tool_call_id")] = item
                for round_record in record.get("rounds") or ():
                    for call in round_record.get("tool_calls") or ():
                        result = executed.get(call.get("id")) or {}
                        rows.append({
                            "config_id": config_id, "column": column_or_setting,
                            "case_id": record.get("case_id"), "turn": record.get("turn"),
                            "round": round_record.get("idx"),
                            "tool": call.get("name"), "arguments": call.get("arguments"),
                            "source": call.get("source"), "valid_json": call.get("valid_json"),
                            "result": result.get("result"), "result_error": result.get("error"),
                            "finish_reason": round_record.get("finish_reason"),
                            "stop_reason": record.get("stop_reason"),
                        })
    if not rows:
        raise FileNotFoundError(f"{directory} holds no run records")
    return pd.DataFrame(rows)
