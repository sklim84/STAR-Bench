"""Gate 5: could every configuration actually be served and fit its prompt?

No GPU is touched. Everything here is a property of the registry, the templates
and the Korean arm, and every one of them was a real 2026 failure: Phi-4-mini was
registered at 12,288 tokens, which left the Korean prompt about 100 tokens of
headroom and scored its 866 tool cases as model failures (C2-001); the
orchestrator pinned every two-card model to devices 0 and 1 whatever lane asked
(L5-017); two rows of the multi-turn table were the same configuration run twice
(C2-012).

`run_plan.json` is the list of configurations the rerun covers. The gate fails
when the registry and the plan disagree in either direction, so a configuration
cannot quietly leave the table.

It also carries the one deliberate deviation from a final decision: D07 says
concurrency 1 and the registry runs 8. The deviation is allowed only while the
plan says what measures it, so the gate fails when the registry default is not
the decision value and the plan holds no batching-agreement run.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .gate import Check, Context, GateResult, run_command

NUMBER = 5
KEY = "serving"
TITLE = "serving readiness"

PLAN_PATH = Path(__file__).resolve().parent / "run_plan.json"

MIN_CONTEXT = 32768
REASONING_BUDGET = 16384
KNOWN_MODES = ("none", "always_on", "think", "nothink", "effort_high", "effort_low")


def load_registry(ctx: Context):
    """The runner registry, imported into this process; the import itself is a check."""
    import sys
    if str(ctx.root) not in sys.path:
        sys.path.insert(0, str(ctx.root))
    try:
        from _experiments.scripts.runner import registry
        return registry, ""
    except Exception as exc:
        return None, f"the serving registry does not import: {type(exc).__name__}: {exc}"


def run(ctx: Context) -> GateResult:
    started = time.time()
    registry, error = load_registry(ctx)
    if error:
        return GateResult(KEY, NUMBER, TITLE, [Check("registry imports", False, error)],
                          time.time() - started)

    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    checks = [
        _plan_matches_registry(registry, plan),
        _concurrency_deviation(registry, plan),
        _registry_complete(registry),
        _template_hashes(ctx, registry),
        _host_profiles(registry, plan),
        _prompt_budget(ctx),
    ]
    return GateResult(KEY, NUMBER, TITLE, checks, time.time() - started)


def _plan_matches_registry(registry, plan: dict) -> Check:
    planned = [row["config_id"] for row in plan["configurations"]]
    known = [cfg.config_id for cfg in registry.CONFIGS]
    missing = [c for c in known if c not in planned]
    extra = [c for c in planned if c not in known]
    duplicates = sorted({c for c in planned if planned.count(c) > 1})
    problems = []
    if missing:
        problems.append(f"in the registry but not in the run plan: {', '.join(missing)}")
    if extra:
        problems.append(f"in the run plan but not in the registry: {', '.join(extra)}")
    if duplicates:
        problems.append(f"listed twice in the run plan: {', '.join(duplicates)}")
    return Check("no configuration is missing from the run plan", not problems,
                 "; ".join(problems) if problems
                 else f"{len(planned)} configurations, {len(plan['columns'])} columns "
                      f"({', '.join(plan['columns'])})",
                 f"python -m _experiments.scripts.runner.plan --format tsv",
                 {"configurations": planned, "columns": plan["columns"]})


def _concurrency_deviation(registry, plan: dict) -> Check:
    """A default that is not D07's 1 has to be declared and measured, not silent."""
    block = plan.get("concurrency")
    if not isinstance(block, dict):
        return Check("the concurrency deviation is declared and measured", False,
                     "run_plan.json has no `concurrency` block; D07 pins concurrency 1 and "
                     f"the registry default is {registry.CONCURRENCY}")
    default = registry.CONCURRENCY
    decision = block.get("decision_value")
    problems = []
    if block.get("registry_default") != default:
        problems.append(f"the plan says the registry default is {block.get('registry_default')} "
                        f"and runner/registry.py says {default}")
    if not str(block.get("_why", "")).strip():
        problems.append("the deviation carries no reason")
    run = block.get("agreement_run") or {}
    if default != decision:
        known = {cfg.config_id for cfg in registry.CONFIGS}
        runs = run.get("runs") or []
        values = sorted(r.get("concurrency") for r in runs)
        if run.get("config_id") not in known:
            problems.append(f"the batching-agreement run names {run.get('config_id')!r}, "
                            f"which is not a registry configuration")
        if run.get("column") not in plan.get("columns", []):
            problems.append(f"the batching-agreement run covers column {run.get('column')!r}, "
                            f"which the plan does not list")
        if values != sorted([decision, default, default]):
            problems.append(f"the batching-agreement run is {values}, expected one run at "
                            f"{decision} and two at {default}")
        if len({r.get("label") for r in runs}) != len(runs):
            problems.append("the batching-agreement runs do not have distinct labels")
    detail = "; ".join(problems) if problems else (
        f"concurrency {default} (D07 says {decision}), measured by {run.get('config_id')} "
        f"{run.get('column')} run " + " and ".join(
            f"{sum(1 for r in run.get('runs', []) if r.get('concurrency') == n)}x at {n}"
            for n in sorted({r.get("concurrency") for r in run.get("runs", [])}, reverse=True))
        if default != decision else f"concurrency {default}, which is what D07 asks for")
    return Check("the concurrency deviation is declared and measured", not problems, detail,
                 "bash _experiments/scripts/run_master.sh --agreement-only --host-gpus 2 "
                 "--tools-lang kr --out-root <fresh dir>",
                 {"registry_default": default, "decision_value": decision,
                  "agreement_run": run})


def _registry_complete(registry) -> Check:
    problems = []
    for cfg in registry.CONFIGS:
        where = cfg.config_id
        if not cfg.parser:
            problems.append(f"{where}: no tool-call parser")
        if cfg.reasoning_mode not in KNOWN_MODES:
            problems.append(f"{where}: reasoning mode {cfg.reasoning_mode!r} is not one of "
                            f"{KNOWN_MODES}")
        if cfg.reasoning_control not in registry.REASONING_CONTROLS:
            problems.append(f"{where}: reasoning control {cfg.reasoning_control!r} is unknown")
        if cfg.max_model_len < MIN_CONTEXT:
            problems.append(f"{where}: context {cfg.max_model_len} is below the {MIN_CONTEXT} "
                            f"every configuration gets (D07)")
        if cfg.is_reasoning and cfg.max_tokens < REASONING_BUDGET:
            problems.append(f"{where}: reasoning configuration with a {cfg.max_tokens}-token "
                            f"output budget, expected {REASONING_BUDGET} (D05, L5-006)")
        if cfg.reasoning_control == "reasoning_effort" and cfg.reasoning_mode not in (
                "effort_high", "effort_low"):
            problems.append(f"{where}: reasoning_effort control with mode {cfg.reasoning_mode!r}")
        if cfg.chat_template and not cfg.template_path.is_file():
            problems.append(f"{where}: chat template {cfg.chat_template} is not in the repository")
        if cfg.tool_parser_plugin and not cfg.tool_parser_plugin_path.is_file():
            problems.append(f"{where}: tool parser plugin {cfg.tool_parser_plugin} is missing")
        if cfg.tp < 1:
            problems.append(f"{where}: tensor-parallel size {cfg.tp}")
    pairs = {}
    for cfg in registry.CONFIGS:
        key = (cfg.model, cfg.reasoning_mode)
        if key in pairs:
            problems.append(f"{cfg.config_id} and {pairs[key]} are the same model in the same "
                            f"mode, which is how the 2026 table got two identical rows (C2-012)")
        pairs[key] = cfg.config_id
    return Check("every registry entry is complete and distinct", not problems,
                 "; ".join(problems[:5]) if problems
                 else f"{len(registry.CONFIGS)} configurations, each with a parser, one labelled "
                      f"mode, >= {MIN_CONTEXT} context and its own model/mode pair",
                 None, {"problems": problems})


def _template_hashes(ctx: Context, registry) -> Check:
    """A repaired template is only reproducible if its hash is published (D21).

    The check is on the templates the rerun actually serves: each file exists and
    its sha256 is one of the published values. `hashes.json` names a vendor
    template by a shortened path, so the file is resolved by name rather than by
    the key being a path that opens.
    """
    hashes_path = registry.TEMPLATE_DIR / "hashes.json"
    if not hashes_path.is_file():
        return Check("repaired chat templates match their published hashes", False,
                     f"{hashes_path} is missing")
    published = json.loads(hashes_path.read_text(encoding="utf-8"))
    problems, served = [], []
    for cfg in registry.CONFIGS:
        if not cfg.chat_template:
            continue
        path = cfg.template_path
        if path is None or not path.is_file():
            problems.append(f"{cfg.config_id}: chat template {cfg.chat_template} is not in "
                            f"the repository")
            continue
        have = registry.template_sha256(path)
        served.append((cfg.config_id, path.name, have))
        if have not in published.values():
            problems.append(f"{cfg.config_id}: {path.name} is {have[:12]}, which "
                            f"{hashes_path.name} does not publish")

    for name, want in published.items():
        if name.startswith("("):
            continue
        matches = [p for p in registry.TEMPLATE_DIR.parent.rglob(Path(name).name)
                   if registry.template_sha256(p) == want]
        if not matches:
            problems.append(f"{hashes_path.name} publishes {name} = {want[:12]} and no file "
                            f"under _experiments/scripts has that hash")

    return Check("repaired chat templates match their published hashes", not problems,
                 "; ".join(problems[:4]) if problems
                 else f"{len(set(n for _c, n, _h in served))} served template(s) and "
                      f"{len([k for k in published if not k.startswith('(')])} published hash(es) "
                      f"agree",
                 f"cat {hashes_path.relative_to(ctx.root)}",
                 {"problems": problems, "served": served})


def _host_profiles(registry, plan: dict) -> Check:
    """Every configuration has to fit one of the hosts the rerun actually has."""
    from _experiments.scripts.runner import plan as plan_module

    hosts = plan["hosts"]
    problems, placement = [], {}
    for cfg in registry.CONFIGS:
        fits = []
        for host in hosts:
            tp = cfg.tp_80g if host["profile"] == "80g" and cfg.tp_80g else cfg.tp
            if tp <= host["gpus"]:
                fits.append(f"{host['name']} (tp={tp})")
        placement[cfg.config_id] = fits
        if not fits:
            problems.append(f"{cfg.config_id} needs {cfg.tp} cards and no listed host has that many")
        if cfg.needs_four_gpu_host != (cfg.tp > 2):
            problems.append(f"{cfg.config_id}: needs_four_gpu_host is {cfg.needs_four_gpu_host} "
                            f"but the 48 GB plan asks for {cfg.tp} cards")
    for host in hosts:
        lanes = plan_module.lanes(host["gpus"], host["profile"])
        unservable = [row["config_id"] for row in lanes if row["gpu"] is None]
        covered = {row["config_id"] for row in lanes if row["gpu"] is not None}
        if not covered:
            problems.append(f"{host['name']} can serve nothing")
        host["unservable"] = unservable
    return Check("every configuration fits a host the rerun has", not problems,
                 "; ".join(problems[:4]) if problems
                 else "; ".join(f"{h['name']}: {len(registry.CONFIGS) - len(h['unservable'])}"
                                f"/{len(registry.CONFIGS)} configurations" for h in hosts),
                 "python -m _experiments.scripts.runner.plan --host-gpus 4 --host-profile 48g",
                 {"placement": placement})


def _prompt_budget(ctx: Context) -> Check:
    """The Korean arm is the longest prompt, and it is the arm every column runs (D17)."""
    done = run_command([ctx.python, "-m", "_experiments.scripts.preflight._budget_driver"],
                       cwd=ctx.root, env=ctx.env, timeout=ctx.timeout_s)
    try:
        report = json.loads(done.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Check("the Korean prompt fits every configuration", False,
                     f"the budget driver produced no JSON: {done.tail(6)}", done.command)
    tight = [row for row in report["rows"] if not row["ok"]]
    worst = min(report["rows"], key=lambda r: r["headroom"])
    return Check("the Korean prompt fits every configuration", not tight,
                 "; ".join(f"{r['config_id']}: {r['headroom']} tokens left in the {r['setting']} "
                           f"context ({r['prompt_tokens']} prompt + {r['max_tokens']} output "
                           f"against {r['max_model_len']})" for r in tight[:4]) if tight
                 else f"tightest is {worst['config_id']} {worst['setting']} with "
                      f"{worst['headroom']} tokens of headroom, measured with "
                      f"{worst['tokenizer']}",
                 done.command, {"rows": report["rows"]})
