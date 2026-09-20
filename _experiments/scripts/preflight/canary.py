"""Gate 6: a small real run against a served model, and the anomaly gates on it.

The cheapest way to find out that a configuration is broken is to run forty cases
through it and look at the shape of the output, not at the score. Every gate here
exists because the failure it names has already happened unnoticed: Llama-3.2-3B
answered 16.1% of its cases with an HTTP error that was scored as a zero;
Phi-4-mini produced no tool call on 31.2% of its cases because its registered
context was smaller than the prompt; the finance Qwen's calls all arrived through
the fallback parser because it was served with the wrong tool parser.

    python -m _experiments.scripts.preflight.run canary --config qwen35-4b-nt \
        --base-url http://127.0.0.1:11434/v1
    python -m _experiments.scripts.preflight.run canary --mock      # no GPU, for testing

Thresholds and where each number comes from: `thresholds.json`. The sample is
fixed in `canary_sample.json`, so two configurations are compared on the same
cases.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from .data import load_cases
from .gate import Check, Context, GateResult, run_command

NUMBER = 6
KEY = "canary"
TITLE = "canary run"

SAMPLE_PATH = Path(__file__).resolve().parent / "canary_sample.json"
DEFAULT_CONTEXT = 32768   # the pinned context, for a canary run that names a model rather than a config
THRESHOLDS_PATH = Path(__file__).resolve().parent / "thresholds.json"


# ---------------------------------------------------------------------------
# The sample
# ---------------------------------------------------------------------------

def build_sample(root: Path, *, size: int = 40, scenarios: int = 3) -> dict:
    """Picks the fixed sample by a rule, so it can be rebuilt and argued about.

    Every tool gets a case, because a parser that drops one tool's calls is
    exactly what this is for; then the three case shapes whose failure mode is
    different (clarification, no-tool, multi-tool); then the lowest-id remainder.
    """
    cases, source = load_cases(root / "benchmarks")
    chosen: list[str] = []

    def take(case_id: str) -> None:
        if case_id not in chosen:
            chosen.append(case_id)

    per_tool: dict[str, str] = {}
    for case in sorted(cases, key=lambda c: c["id"]):
        tools = case["expected"].get("tools_must_include") or []
        if len(tools) == 1 and tools[0] not in per_tool:
            per_tool[tools[0]] = case["id"]
    for tool in sorted(per_tool):
        take(per_tool[tool])

    def lowest(predicate, n: int) -> list[str]:
        return [c["id"] for c in sorted(cases, key=lambda c: c["id"]) if predicate(c)][:n]

    for case_id in lowest(lambda c: c["expected"].get("expect_clarification"), 3):
        take(case_id)
    for case_id in lowest(lambda c: not c["expected"].get("tools_must_include")
                          and not c["expected"].get("expect_clarification"), 3):
        take(case_id)
    for case_id in lowest(lambda c: len(c["expected"].get("tools_must_include") or []) > 1, 5):
        take(case_id)
    for case_id in lowest(lambda c: c.get("difficulty") == "hard", size):
        if len(chosen) >= size:
            break
        take(case_id)
    for case in sorted(cases, key=lambda c: c["id"]):
        if len(chosen) >= size:
            break
        take(case["id"])

    scenario_cases, _ = load_cases(root / "benchmarks_multiturn")
    by_sub: dict[str, str] = {}
    for scenario in sorted(scenario_cases, key=lambda c: c["id"]):
        by_sub.setdefault(scenario.get("sub_category", "base"), scenario["id"])
    scenario_ids = sorted(by_sub[key] for key in sorted(by_sub))[:scenarios]

    covered = set(per_tool)
    for scenario in scenario_cases:
        if scenario["id"] in scenario_ids:
            for turn in scenario.get("turns") or []:
                covered.update(call.get("name") for call in turn.get("tool_calls") or [])

    return {
        "_why": (
            "The fixed canary sample: one single-turn case per gold tool, then the "
            "three case shapes whose failure mode differs (clarification, no-tool, "
            "multi-tool), then the lowest-id hard cases up to 40, plus one multi-turn "
            "scenario per sub-category. Fixed so two configurations are compared on "
            "the same cases and so a canary is cheap: 40 cases plus 3 scenarios is "
            "about 13 minutes on the slowest configuration."),
        "_rebuild": "python -m _experiments.scripts.preflight.run canary --rebuild-sample",
        "cases": sorted(chosen),
        "tools_covered": sorted(covered),
        "scenarios": scenario_ids,
        "case_files": sorted({source[c] for c in chosen}),
    }


def load_sample() -> dict:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def load_thresholds(path: Path | None = None) -> dict:
    doc = json.loads((path or THRESHOLDS_PATH).read_text(encoding="utf-8"))
    return {key: value["value"] for key, value in doc["thresholds"].items()}


# ---------------------------------------------------------------------------
# Reading a canary run
# ---------------------------------------------------------------------------

@dataclass
class Metric:
    name: str
    value: float | None
    limit: float
    direction: str            # "max" or "min"
    detail: str = ""
    offenders: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        if self.value is None:
            return True
        return self.value <= self.limit if self.direction == "max" else self.value >= self.limit

    def as_dict(self) -> dict:
        return {"name": self.name, "value": self.value, "limit": self.limit,
                "direction": self.direction, "ok": self.ok, "detail": self.detail,
                "offenders": self.offenders[:10]}


_CLASSIFY = None


def _classify(result) -> str:
    """ok / empty / error for one executed tool result, the platform's own rule."""
    global _CLASSIFY
    if _CLASSIFY is None:
        from _experiments.scripts._platform import ensure_platform_on_path
        ensure_platform_on_path()
        from scripts.gold_calls import classify
        _CLASSIFY = classify

    payload = result
    if isinstance(result, str):
        try:
            payload = json.loads(result)
        except ValueError:
            return "ok" if result.strip() else "empty"
    return _CLASSIFY(payload)[0]


def evaluate(records: list[dict], *, gold: dict, thresholds: dict,
             baseline_empty_share: float) -> list[Metric]:
    """Turns a canary run into the anomaly metrics, one per gate."""
    expect_tool, no_call = 0, []
    errors, lengths = [], []
    calls_total, fallback = 0, []
    executed_total, empty_results = 0, []
    headroom: float | None = None
    latencies: list[tuple[str, float]] = []

    for record in records:
        case_id = record.get("case_id", "?")
        key = case_id if record.get("turn") is None else f"{case_id}#{record['turn']}"
        rounds = record.get("rounds") or []
        made_a_call = any(r.get("tool_calls") for r in rounds)
        if gold.get(key, {}).get("expects_tool"):
            expect_tool += 1
            if not made_a_call:
                no_call.append(key)
        if record.get("error") or record.get("stop_reason") == "error":
            errors.append(f"{key}: {(record.get('error') or {}).get('type', 'error')}")
        if record.get("stop_reason") == "length" or any(
                r.get("finish_reason") == "length" for r in rounds):
            lengths.append(key)
        for a_round in rounds:
            for call in a_round.get("tool_calls") or []:
                calls_total += 1
                if call.get("source") == "fallback":
                    fallback.append(key)
            for done in a_round.get("executed") or []:
                executed_total += 1
                if done.get("error"):
                    if done["error"].get("type") != "result_truncated":
                        empty_results.append(f"{key}: {done['error'].get('type')}")
                    continue
                if _classify(done.get("result")) != "ok":
                    empty_results.append(f"{key}: {done.get('name')} returned nothing")
            usage = a_round.get("usage") or {}
            budget = record.get("config", {})
            prompt_tokens = usage.get("prompt_tokens")
            if prompt_tokens and budget.get("max_model_len"):
                left = budget["max_model_len"] - prompt_tokens - (budget.get("max_tokens") or 0)
                headroom = left if headroom is None else min(headroom, left)
        if record.get("elapsed_s") is not None:
            latencies.append((key, float(record["elapsed_s"])))

    n = len(records) or 1
    metrics = [
        Metric("no-tool-call rate", len(no_call) / (expect_tool or 1),
               thresholds["no_tool_call_rate_max"], "max",
               f"{len(no_call)} of {expect_tool} cases whose gold expects a tool", no_call),
        Metric("system-error rate", len(errors) / n, thresholds["system_error_rate_max"], "max",
               f"{len(errors)} of {n} records", errors),
        Metric("finish_reason length share", len(lengths) / n,
               thresholds["length_finish_rate_max"], "max",
               f"{len(lengths)} of {n} records hit the output budget", lengths),
        Metric("fallback-parser share",
               (len(fallback) / calls_total) if calls_total else None,
               thresholds["fallback_share_max"], "max",
               f"{len(fallback)} of {calls_total} tool calls did not arrive natively",
               sorted(set(fallback))),
        Metric("empty tool-result share",
               (len(empty_results) / executed_total) if executed_total else None,
               max(thresholds["empty_result_share_margin"] + baseline_empty_share,
                   thresholds["empty_result_share_floor"]), "max",
               f"{len(empty_results)} of {executed_total} executed calls answered nothing; "
               f"the gold calls of this sample answer nothing on "
               f"{baseline_empty_share:.1%} of theirs", empty_results),
        Metric("prompt headroom (tokens)", headroom,
               thresholds["prompt_headroom_min"], "min",
               "smallest context left after the prompt and the output budget, "
               "measured from the server's own usage counts", []),
    ]
    metrics.extend(_latency_metrics(latencies, thresholds))
    return metrics


def _latency_metrics(latencies: list[tuple[str, float]], thresholds: dict) -> list[Metric]:
    if not latencies:
        return [Metric("per-case latency", None, thresholds["latency_case_max_s"], "max",
                       "no latency recorded")]
    values = sorted(v for _k, v in latencies)
    middle = values[len(values) // 2]
    slow = [f"{k}: {v:.0f}s" for k, v in latencies if v > thresholds["latency_case_max_s"]]
    spread = [f"{k}: {v:.0f}s vs median {middle:.0f}s" for k, v in latencies
              if middle > 0 and v > middle * thresholds["latency_outlier_factor"]
              and v > thresholds["latency_outlier_floor_s"]]
    return [
        Metric("per-case latency ceiling", max(values), thresholds["latency_case_max_s"], "max",
               f"median {middle:.2f}s over {len(values)} records", slow),
        Metric("per-case latency spread",
               max(values) / middle if middle else None,
               thresholds["latency_outlier_factor"], "max",
               f"slowest {max(values):.2f}s against a median of {middle:.2f}s", spread),
    ]


def gold_index(root: Path, sample: dict) -> dict:
    """What the sample's gold expects, keyed the way records are keyed."""
    index: dict[str, dict] = {}
    cases, _ = load_cases(root / "benchmarks")
    wanted = set(sample["cases"])
    for case in cases:
        if case["id"] in wanted:
            expected = case.get("expected") or {}
            index[case["id"]] = {"expects_tool": bool(expected.get("tools_must_include"))}
    scenarios, _ = load_cases(root / "benchmarks_multiturn")
    for scenario in scenarios:
        if scenario["id"] not in set(sample["scenarios"]):
            continue
        for turn in scenario.get("turns") or []:
            index[f"{scenario['id']}#{turn.get('turn')}"] = {
                "expects_tool": bool(turn.get("tool_calls"))}
    return index


def baseline_empty_share(root: Path, sample: dict) -> float:
    """How often the sample's own gold calls answer nothing, from the allow-list.

    The empty share of a real run is only meaningful against this: the ring and
    layering scans return nothing whatever the model does.
    """
    from .gold import ALLOW_PATH

    allowed = json.loads(ALLOW_PATH.read_text(encoding="utf-8"))["entries"]
    empty_ids = {e["case_id"] for e in allowed if e["kind"] == "single"}
    scenario_empty = {e["case_id"] for e in allowed if e["kind"] == "multiturn"}
    cases, _ = load_cases(root / "benchmarks")
    calls = 0
    empty = 0
    for case in cases:
        if case["id"] not in set(sample["cases"]):
            continue
        tools = case["expected"].get("tools_must_include") or []
        calls += len(tools)
        if case["id"] in empty_ids:
            empty += 1
    scenarios, _ = load_cases(root / "benchmarks_multiturn")
    for scenario in scenarios:
        if scenario["id"] not in set(sample["scenarios"]):
            continue
        for turn in scenario.get("turns") or []:
            calls += len(turn.get("tool_calls") or [])
        if scenario["id"] in scenario_empty:
            empty += 1
    return (empty / calls) if calls else 0.0


# ---------------------------------------------------------------------------
# Running one
# ---------------------------------------------------------------------------

def read_records(out_dir: Path) -> list[dict]:
    rows = []
    for path in sorted(out_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def runner_commands(ctx: Context, *, out_dir: Path, base_url: str, config_id: str | None,
                    model: str | None, sample: dict, ids_file: Path,
                    allow_unpinned: bool, no_env_check: bool,
                    setting: str = "oracle") -> list[tuple[str, list[str]]]:
    # Without a registry entry there is no context length, and the headroom gate
    # has nothing to measure against, so a bare --model run states one.
    target = (["--config", config_id] if config_id
              else ["--model", model, "--max-model-len", str(DEFAULT_CONTEXT)])
    common = [*target, "--tools-lang", "kr", "--base-url", base_url, "--partial",
              "--concurrency", "1"]
    if allow_unpinned:
        common.append("--allow-unpinned-revision")
    if no_env_check:
        common.append("--no-env-check")
    return [
        ("single-turn sample",
         [ctx.python, "-m", "_experiments.scripts.benchmark",
          "--cases-dir", "benchmarks", "--case-ids-file", str(ids_file),
          "--out", str(out_dir / "single"), *common]),
        ("multi-turn sample",
         [ctx.python, "-m", "_experiments.scripts.benchmark_multiturn",
          "--cases-dir", "benchmarks_multiturn", "--setting", setting,
          "--case-ids", ",".join(sample["scenarios"]),
          "--out", str(out_dir / "multiturn"), *common]),
    ]


def run(ctx: Context, *, base_url: str, out_dir: Path, config_id: str | None = None,
        model: str | None = None, allow_unpinned: bool = False,
        no_env_check: bool = False, thresholds_path: Path | None = None,
        setting: str = "oracle") -> GateResult:
    started = time.time()
    sample = load_sample()
    thresholds = load_thresholds(thresholds_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    ids_file = out_dir / "case_ids.txt"
    ids_file.write_text("\n".join(sample["cases"]) + "\n", encoding="utf-8")

    checks: list[Check] = []
    for label, argv in runner_commands(ctx, out_dir=out_dir, base_url=base_url,
                                       config_id=config_id, model=model, sample=sample,
                                       ids_file=ids_file, allow_unpinned=allow_unpinned,
                                       no_env_check=no_env_check, setting=setting):
        done = run_command(argv, cwd=ctx.root, env=ctx.env, timeout=ctx.timeout_s)
        checks.append(Check(f"{label} ran", done.ok,
                            done.tail(5) if not done.ok else "runner exited 0", done.command))

    records = read_records(out_dir / "single") + read_records(out_dir / "multiturn")
    if not records:
        checks.append(Check("canary produced records", False,
                            f"no record under {out_dir}; the anomaly gates cannot be applied"))
        return GateResult(KEY, NUMBER, TITLE, checks, time.time() - started)

    metrics = evaluate(records, gold=gold_index(ctx.root, sample), thresholds=thresholds,
                       baseline_empty_share=baseline_empty_share(ctx.root, sample))
    for metric in metrics:
        value = "n/a" if metric.value is None else (
            f"{metric.value:.3f}" if metric.value < 100 else f"{metric.value:.0f}")
        detail = f"{value} against a {metric.direction} of {metric.limit} ({metric.detail})"
        if not metric.ok and metric.offenders:
            detail += "; " + ", ".join(str(o) for o in metric.offenders[:5])
        checks.append(Check(metric.name, metric.ok, detail, None, metric.as_dict()))

    result = GateResult(KEY, NUMBER, TITLE, checks, time.time() - started)
    result.note = f"{len(records)} records from {out_dir}"
    return result
