#!/usr/bin/env python3
"""The figures the paper states in prose rather than in a table.

The generated tables carry most of the paper's numbers, but a benchmark paper
also argues in sentences: a range, a share of failures, a correlation, a split
of the cases. Those numbers had been computed once and typed in, which is how
two of them outlived a rerun. This step computes each one from the scored
records and writes them to one file, keyed by where the paper states them, so a
number in the prose has an artefact behind it like a number in a table.

Conventions follow the paper. A case is correct when h == 1. Multi-turn h-bar is
the mean over turns. "Failures" are the cases with h == 0, split by the scorer's
error type. A case's kind comes from the case file, never from a scored record:
its gold tools are primary_tool together with tools_must_include, it asks for a
missing argument when expect_clarification is set, and it accepts an alternative
when alternatives is non-empty. The scored gold-tool set cannot serve, because
for a case whose only accepted call is an alternative the scorer records the
alternative when a model makes that call and nothing when it does not, so the set
differs from one configuration to the next.

Usage:  PYTHONPATH=. python -m _experiments.scripts.analysis.text_figures
Output: _experiments/results_RQ1/text_figures.json
"""
from __future__ import annotations

import collections
import json
import statistics
import sys
from pathlib import Path

from scipy import stats

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _experiments.scripts.analysis import load  # noqa: E402

OUT = ROOT / "_experiments" / "results_RQ1" / "text_figures.json"
STR_QUALITY = ROOT / "_experiments" / "results_RQ3" / "str_generation_quality.json"
SUBDOMAINS = ROOT / "_experiments" / "results_RQ5" / "finance_specialization.json"
HUMAN = ROOT / "_experiments" / "human_eval" / "round2"
GAP = ROOT / "_experiments" / "results_RQ2" / "regulatory_vs_analysis_gap.json"
MULTI = ROOT / "benchmarks_multiturn" / "cases_str_workflow.json"
BENCH = ROOT / "benchmarks"
BAND_WIDTH = 0.07  # "within seven points of one another on single-turn tool hit"


def _share(frame, column: str) -> dict:
    counts = frame[column].value_counts()
    total = int(counts.sum())
    return {"n_failures": total,
            **{str(k): round(100 * v / total, 1) for k, v in counts.items()}}


def _pct(series) -> float:
    return round(100 * float(series.astype(float).mean()), 1)


def _same_turn_by_scenario(turns, is_str, cases, turn: int) -> dict:
    """STR turns against the other turns at one position, with the scenario as the unit.

    Every configuration runs the same scenarios, so pooling turns over
    configurations does not add independent scenarios. Each scenario's hit is
    averaged over configurations first; the interval resamples scenarios.
    """
    import numpy as np
    kind = {case["id"]: case["sub_category"] for case in cases}
    at = turns.assign(is_str=is_str)
    at = at[at["turn"] == turn]
    per = at.groupby(["scenario_id", "is_str"])["h"].mean().reset_index()
    report, other = per[per["is_str"]]["h"].to_numpy(), per[~per["is_str"]]["h"].to_numpy()
    rng = np.random.default_rng(0)
    gaps = [rng.choice(other, len(other)).mean() - rng.choice(report, len(report)).mean()
            for _ in range(10_000)]
    low, high = np.percentile(gaps, [2.5, 97.5])
    by_kind = {}
    for name in sorted(set(kind.values())):
        rows = per[per["scenario_id"].map(kind) == name]
        r, o = rows[rows["is_str"]]["h"], rows[~rows["is_str"]]["h"]
        if len(r) and len(o):
            by_kind[name] = {"n_str": int(len(r)), "n_other": int(len(o)),
                             "str": round(float(r.mean()), 3), "other": round(float(o.mean()), 3)}
    return {"n_str_scenarios": int(len(report)), "n_other_scenarios": int(len(other)),
            "str": round(float(report.mean()), 3), "other": round(float(other.mean()), 3),
            "gap_points": round(100 * float(other.mean() - report.mean()), 1),
            "gap_ci95_points": [round(100 * float(low), 1), round(100 * float(high), 1)],
            "mann_whitney_p": float(stats.mannwhitneyu(report, other).pvalue),
            "by_scenario_type": by_kind}


def _same_turn_context(turns, is_str, cases, turn: int) -> dict:
    """What else differs between STR and other turns at one position.

    Prompt and completion tokens come from the oracle run records the scorer
    read (the latest record file per configuration, as load does). The gap is
    re-estimated with prompt length held fixed inside each configuration: both
    the hit and the prompt length are centred per configuration, and the hit is
    regressed on the STR indicator and the prompt length in thousands of tokens.
    """
    import numpy as np
    import pandas as pd
    usage = []
    for config_id, path in load._record_files(load.DEFAULT_RUN_ROOT / load.RECORD_DIRS["oracle"]):
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                if record.get("turn") != turn:
                    continue
                rounds = record.get("rounds") or []
                first = (rounds[0].get("usage") or {}) if rounds else {}
                usage.append({"config_id": config_id, "scenario_id": record.get("case_id"),
                              "prompt": first.get("prompt_tokens"),
                              "completion": sum((r.get("usage") or {}).get("completion_tokens") or 0
                                                for r in rounds)})
    at = turns.assign(is_str=is_str)
    at = at[at["turn"] == turn][["config_id", "scenario_id", "h", "is_str"]]
    at = at.merge(pd.DataFrame(usage), on=["config_id", "scenario_id"], how="inner").dropna()
    arguments = {case["id"]: sum(len(call.get("arguments") or {})
                                 for t in case["turns"] if t["turn"] == turn
                                 for call in (t.get("tool_calls") or ()))
                 for case in cases}
    per = at.groupby(["scenario_id", "is_str"]).agg(prompt=("prompt", "median"),
                                                     completion=("completion", "median")).reset_index()
    per["arguments"] = per["scenario_id"].map(arguments)
    x, y = [], []
    for _, group in at.groupby("config_id"):
        x.append(np.c_[group["is_str"].astype(float) - group["is_str"].mean(),
                       (group["prompt"] - group["prompt"].mean()) / 1000])
        y.append(group["h"] - group["h"].mean())
    coef = np.linalg.lstsq(np.vstack(x), np.concatenate(y), rcond=None)[0]
    def median(column, flag):
        return float(per[per["is_str"] == flag][column].median())
    return {"n_turn_records": int(len(at)),
            "median_prompt_tokens": {"str": median("prompt", True), "other": median("prompt", False)},
            "median_gold_arguments": {"str": median("arguments", True), "other": median("arguments", False)},
            "median_completion_tokens": {"str": median("completion", True),
                                         "other": median("completion", False)},
            "gap_points_holding_prompt_length": round(-100 * float(coef[0]), 1),
            "hit_change_per_1k_prompt_tokens": round(float(coef[1]), 3)}


def _calls_written_as_text(config_id: str) -> dict:
    """Single-turn records where no call was parsed but the reply spells one out.

    A reply counts when the interface returned no tool call and the final text
    carries a JSON object with both a "name" and an "arguments" key, the shape of
    a function call written out as text rather than emitted as one.
    """
    import re
    shape = re.compile(r'"name"\s*:.*?"arguments"\s*:', re.S)
    path = dict(load._record_files(load.DEFAULT_RUN_ROOT / load.RECORD_DIRS["single"]))[config_id]
    total = written = 0
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            total += 1
            parsed = any(r.get("tool_calls") for r in record.get("rounds") or ())
            if not parsed and shape.search(record.get("final_text") or ""):
                written += 1
    return {"config": config_id, "n_cases": total, "calls_written_as_text": written,
            "pct": round(100 * written / total, 1)}


def main() -> int:
    single = load.single("single")
    groups = json.loads(GAP.read_text(encoding="utf-8"))
    analysis_tools = set(groups["analysis_categories"])
    reporting_tools = set(groups["regulatory_categories"])
    out: dict = {}

    # Section 4.2: the single-turn range and the per-tool spread.
    by_config = single.groupby("config_id")["h"].mean()
    by_tool = single[single["category"].isin(analysis_tools | reporting_tools)] \
        .groupby("category")["h"].mean().sort_values()
    out["sec4_2"] = {
        "single_turn_h_min": round(float(by_config.min()), 3),
        "single_turn_h_max": round(float(by_config.max()), 3),
        "per_tool_h_min": {by_tool.index[0]: round(float(by_tool.iloc[0]), 3)},
        "per_tool_h_max": {by_tool.index[-1]: round(float(by_tool.iloc[-1]), 3)},
    }

    # Section 4.3: how the failures (h == 0) divide by error type.
    failures = single[single["h"] == 0]
    out["sec4_3_failure_composition_pct"] = {
        "analysis_tools": _share(failures[failures["category"].isin(analysis_tools)], "error_type"),
        **{tool: _share(failures[failures["category"] == tool], "error_type")
           for tool in sorted(reporting_tools)},
    }

    # Section 4.4: single-turn hit against completion, and where the workflow breaks.
    scenarios, turns = load.multiturn("oracle")
    completion = scenarios.groupby("config_id")["c"].mean()
    turn_hit = turns.groupby("config_id")["h"].mean()
    rho_single = stats.spearmanr(by_config[completion.index], completion)
    rho_turn = stats.spearmanr(turn_hit[completion.index], completion)
    cases = json.loads(MULTI.read_text(encoding="utf-8"))
    str_turn = {case["id"]: next((t["turn"] for t in case["turns"]
                                  if any(c["name"] == "generate_str"
                                         for c in (t.get("tool_calls") or ()))), None)
                for case in cases}
    is_str = [str_turn.get(s) == t for s, t in zip(turns["scenario_id"], turns["turn"])]
    by_kind = turns.assign(is_str=is_str).groupby("is_str")["h"].mean()
    # The STR turn sits late in each scenario, so compare it with the other turns
    # at the same turn position. This holds position fixed only: the length of
    # the earlier tool outputs, and so the context, still differs between them.
    by_position = turns.assign(is_str=is_str).groupby(["turn", "is_str"])["h"].mean()
    # The band Figure 1 draws and Section 4.4 states: every configuration within
    # seven points of the highest single-turn hit, so all of them are within seven
    # points of one another. The window is fixed; the membership follows from it.
    top = float(by_config.max())
    band = [k for k in completion.index if by_config[k] >= top - BAND_WIDTH]
    band_c = completion[band]
    out["sec4_4_band"] = {
        "width": BAND_WIDTH, "n": len(band),
        "h_range": [round(float(by_config[band].min()), 3), round(top, 3)],
        "c_range": [round(float(band_c.min()), 2), round(float(band_c.max()), 2)],
        "c_spread_points": round(100 * float(band_c.max() - band_c.min())),
        "configs": sorted(band),
    }
    out["sec4_4"] = {
        "spearman_single_h_vs_completion": {"rho": round(float(rho_single.statistic), 4),
                                            "p": round(float(rho_single.pvalue), 4),
                                            "n": int(len(completion))},
        "spearman_turn_h_vs_completion": round(float(rho_turn.statistic), 4),
        "mean_hit_by_turn": {int(k): round(float(v), 3)
                             for k, v in turns.groupby("turn")["h"].mean().items()},
        "scenarios_with_str_at_turn_4": sum(1 for v in str_turn.values() if v == 4),
        "n_scenarios": len(cases),
        "str_turn_gap_points": round(100 * float(by_kind[False] - by_kind[True]), 1),
        "str_turn_4_by_scenario": _same_turn_by_scenario(turns, is_str, cases, turn=4),
        "str_turn_4_context": _same_turn_context(turns, is_str, cases, turn=4),
        "hit_at_same_position": {
            int(t): {"str": round(float(by_position[(t, True)]), 3),
                     "other": round(float(by_position[(t, False)]), 3)}
            for t in sorted({t for t, _ in by_position.index})
            if (t, True) in by_position.index and (t, False) in by_position.index},
    }

    # Appendix A: what the single-turn cases are and how each kind is answered,
    # with every case's kind fixed from the case file.
    kind = {}
    for path in sorted(BENCH.glob("cases_*.json")):
        for case in json.loads(path.read_text(encoding="utf-8")):
            expected = case.get("expected") or {}
            gold = set(expected.get("tools_must_include") or [])
            if expected.get("primary_tool"):
                gold.add(expected["primary_tool"])
            kind[case["id"]] = {"n_gold": len(gold),
                                "asks": bool(expected.get("expect_clarification")),
                                "alternative": bool(expected.get("alternatives")),
                                "difficulty": case.get("difficulty")}
    no_gold = [k for k, v in kind.items() if v["n_gold"] == 0]
    asks = [k for k in no_gold if kind[k]["asks"]]
    out_of_scope = [k for k in no_gold if not kind[k]["asks"]]
    with_gold = [k for k, v in kind.items() if v["n_gold"] > 0]
    def correct(ids) -> float:
        return _pct(single[single["case_id"].isin(set(ids))]["h"])
    out["appendix_a"] = {
        "gold_tool_count": {int(k): int(v) for k, v in
                            sorted(collections.Counter(v["n_gold"] for v in kind.values()).items())},
        "no_gold_out_of_scope": len(out_of_scope),
        "no_gold_asks_for_argument": len(asks),
        "accepts_alternative": {
            "out_of_scope": sum(kind[k]["alternative"] for k in out_of_scope),
            "with_gold": sum(kind[k]["alternative"] for k in with_gold),
            "asks_for_argument": sum(kind[k]["alternative"] for k in asks)},
        "difficulty": dict(collections.Counter(v["difficulty"] for v in kind.values())),
        "no_gold_difficulty": dict(collections.Counter(kind[k]["difficulty"] for k in no_gold)),
        "correct_pct": {
            "out_of_scope": correct(out_of_scope),
            "out_of_scope_without_alternative": correct(
                [k for k in out_of_scope if not kind[k]["alternative"]]),
            "asks_for_argument": correct(asks),
            "no_gold_pooled": correct(no_gold),
            **{f"{d}_with_gold": correct([k for k in with_gold if kind[k]["difficulty"] == d])
               for d in ("easy", "medium", "hard")},
        },
        "multi_turn_lengths": {int(k): int(v) for k, v in sorted(
            collections.Counter(len(case["turns"]) for case in cases).items())},
        "multi_turn_total_turns": sum(len(case["turns"]) for case in cases),
    }

    # Appendix C (question diversity): median query length by subdomain and case type.
    tool_to_subdomain = {tool: name for name, tools in
                         json.loads(SUBDOMAINS.read_text(encoding="utf-8"))["sub_domain_tools"].items()
                         for tool in tools}
    lengths = collections.defaultdict(list)
    for path in sorted(BENCH.glob("cases_*.json")):
        category = path.stem[len("cases_"):]
        for case in json.loads(path.read_text(encoding="utf-8")):
            lengths[tool_to_subdomain.get(category, category)].append(len(case["question"]))
    out["appendix_c_question_length_median"] = {k: float(statistics.median(v))
                                                for k, v in sorted(lengths.items())}
    out["appendix_c_multi_turn_categories"] = dict(collections.Counter(c["sub_category"] for c in cases))
    out["appendix_c_multi_turn_fraud_types"] = len({c["fraud_type"] for c in cases})

    # Appendix F: the counts the expert-agreement prose states.
    mapping = json.loads((HUMAN / "str_eval_mapping.json").read_text(encoding="utf-8"))["items"]
    ratings = {slot: json.loads((HUMAN / f"{slot}.json").read_text(encoding="utf-8"))["ratings"]
               for slot in ("A", "B")}
    undefined = [row["code"] for row in mapping if row["checker"].get("grounding") is None]
    out["appendix_f"] = {
        "n_reports": len(mapping),
        "n_scenarios": len({row["scenario_id"] for row in mapping}),
        "grounding_undefined": len(undefined),
        "undefined_rated_1_overall": {slot: sum(1 for c in undefined if ratings[slot][c]["overall"] == 1)
                                      for slot in ratings},
        "terminology_rated_1": {slot: sum(1 for v in ratings[slot].values() if v["terminology"] == 1)
                                for slot in ratings},
    }

    # Appendix H: how the STR ordering moves under other ways of combining the dimensions.
    rows = [r for r in json.loads(STR_QUALITY.read_text(encoding="utf-8"))["rows"] if r["n_produced"]]
    f, g, t = ([r[k] for r in rows] for k in ("field_coverage", "grounding", "terminology"))
    reported = [(a + b + c) / 3 for a, b, c in zip(f, g, t)]
    alternatives = {"grounding_twice": [(a + 2 * b + c) / 4 for a, b, c in zip(f, g, t)],
                    "field_and_grounding": [(a + b) / 2 for a, b in zip(f, g)],
                    "grounding_only": list(g)}
    def leaders(scores, k=3):
        return [rows[i]["label"] for i in sorted(range(len(rows)), key=lambda i: -scores[i])[:k]]
    out["appendix_h_str_sensitivity"] = {
        "n_configs_with_a_report": len(rows),
        "spearman_vs_reported": {k: round(float(stats.spearmanr(reported, v).statistic), 4)
                                 for k, v in alternatives.items()},
        "top3_reported": leaders(reported),
        **{f"top3_{k}": leaders(v) for k, v in alternatives.items()},
    }

    # Appendix I: how unevenly the end-to-end cost falls.
    oracle_hit = {k: v["h"]["mean"] for k, v in load.aggregates("oracle").items()}
    e2e_hit = {k: v["h"]["mean"] for k, v in load.aggregates("e2e").items()}
    delta = {k: e2e_hit[k] - oracle_hit[k] for k in e2e_hit if k in oracle_hit}
    labels = load.configs()["label"]
    ranked = sorted(oracle_hit, key=lambda k: -oracle_hit[k])
    worst, best = min(delta, key=delta.get), max(delta, key=delta.get)
    out["appendix_i_e2e"] = {
        "delta_h_min": {labels[worst]: round(delta[worst], 3)},
        "delta_h_max": {labels[best]: round(delta[best], 3),
                        "oracle_rank": ranked.index(best) + 1, "of": len(ranked)},
        "losing_more_than_5_points": sum(v < -0.05 for v in delta.values()),
        "moving_less_than_1_point": sum(abs(v) < 0.01 for v in delta.values()),
        "improving": sum(v > 0 for v in delta.values()),
        "oracle_h_range": [round(min(oracle_hit.values()), 3), round(max(oracle_hit.values()), 3)],
        "e2e_h_range": [round(min(e2e_hit.values()), 3), round(max(e2e_hit.values()), 3)],
        "mean_delta_h": round(sum(delta.values()) / len(delta), 3),
    }

    # Appendix H: why one model's rank falls so far from BFCL. Its BFCL score was
    # taken in prompt mode, which parses a call written as text; here it is served
    # through its native tool-calling interface, which does not.
    out["appendix_h_text_calls"] = _calls_written_as_text("phi-4-mini")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1)[:1800])
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
