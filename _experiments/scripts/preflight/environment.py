"""Gate 1: is this the machine and the checkout the rerun was pinned to?

The 2026 run was scored on a database whose columns had been renamed and on a
platform checkout nobody recorded, so 1,190 cases came back as model failures
(L5-001, L5-020, C1-004, C2-016, R2C-003). Every one of those facts is cheap to
read before a run, and none of them is recoverable afterwards.

The serving dependency stack is checked only with `--serving`, because the
machine that runs this suite is usually not the machine that serves the models.
"""

from __future__ import annotations

import json
import time

from .gate import Check, Context, GateResult, run_command

NUMBER = 1
KEY = "env"
TITLE = "environment"

EXPECTED_TOOL_COUNT = 23


def run(ctx: Context) -> GateResult:
    started = time.time()
    checks: list[Check] = []

    checks.append(_pins(ctx, serving=False))
    if ctx.check_serving_stack:
        checks.append(_pins(ctx, serving=True))

    probe = run_command([ctx.platform_python, "-m", "_experiments.scripts.preflight._probe"],
                        cwd=ctx.root, env=ctx.env, timeout=600)
    try:
        info = json.loads(probe.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        info = {}
        checks.append(Check("environment probe", False,
                            f"the probe produced no JSON: {probe.tail()}", probe.command))
    if info:
        checks.extend(_platform_checks(info, probe.command))
        checks.extend(_provenance_checks(info, probe.command))
    checks.append(_revisions(ctx))

    return GateResult(KEY, NUMBER, TITLE, checks, time.time() - started)


def _pins(ctx: Context, *, serving: bool) -> Check:
    argv = [ctx.python, "-m", "_experiments.env.check_env"] + (["--serving"] if serving else [])
    done = run_command(argv, cwd=ctx.root, env=ctx.env, timeout=300)
    name = f"{'serving' if serving else 'evaluation'} dependency pins"
    return Check(name, done.ok, done.tail(6) if not done.ok else done.stdout.strip(),
                 done.command)


def _platform_checks(info: dict, command: str) -> list[Check]:
    if info.get("platform_error"):
        return [Check("platform tool layer imports", False, info["platform_error"], command)]
    tools = info.get("tool_count")
    ok = tools == EXPECTED_TOOL_COUNT
    detail = f"{tools} tools from {info.get('platform_root')}"
    if not ok:
        detail = f"the platform exposes {tools} tools, expected {EXPECTED_TOOL_COUNT}"
    return [Check("platform tool layer imports", ok, detail, command,
                  {"tool_count": tools, "platform_root": info.get("platform_root")})]


def _provenance_checks(info: dict, command: str) -> list[Check]:
    platform = info.get("platform") or {}
    checks: list[Check] = []

    commit = platform.get("platform_commit")
    dirty = platform.get("platform_dirty")
    checks.append(Check(
        "platform commit is recorded and the tree is clean",
        bool(commit) and dirty is False,
        f"{(commit or 'unknown')[:12]}"
        + (", working tree has uncommitted changes" if dirty else ", clean"),
        command, {"platform_commit": commit, "platform_dirty": dirty}))

    sb_commit = info.get("star_bench_commit")
    sb_dirty = info.get("star_bench_dirty")
    checks.append(Check(
        "STAR-Bench commit is recorded and the tree is clean",
        bool(sb_commit) and not sb_dirty,
        f"{(sb_commit or 'unknown')[:12]}"
        + (", working tree has uncommitted changes" if sb_dirty else ", clean"),
        command, {"star_bench_commit": sb_commit, "star_bench_dirty": sb_dirty}))

    hashes = {key: platform.get(key) for key in
              ("data_sha256", "db_sha256", "model_file_sha256",
               "system_prompt_sha256", "tools_sha256")}
    missing = sorted(k for k, v in hashes.items() if not v)
    checks.append(Check(
        "parquet, database, model and prompt hashes are readable", not missing,
        f"parquet {(hashes['data_sha256'] or '?')[:12]}, db {(hashes['db_sha256'] or '?')[:12]}, "
        f"model {(hashes['model_file_sha256'] or '?')[:12]}"
        if not missing else f"no hash for {', '.join(missing)}",
        command, hashes))

    columns = info.get("hofinet_columns")
    expected = info.get("hofinet_columns_expected")
    checks.append(Check(
        "hofinet columns are the released English ones",
        columns is not None and columns == expected,
        f"{len(columns or [])} columns, {info.get('hofinet_rows')} rows"
        if columns == expected else f"columns are {columns}, expected {expected}",
        command, {"hofinet_columns": columns}))

    stubbed = platform.get("streamlit_stubbed")
    checks.append(Check(
        "Streamlit cache is stubbed", stubbed is True,
        "tool results are not memoised" if stubbed is True
        else f"streamlit_stubbed is {stubbed}; install requirements-tools.txt only, "
             f"or the cache returns a stale result for a repeated call",
        command, {"streamlit_stubbed": stubbed}))

    return checks


def _revisions(ctx: Context) -> Check:
    """Every configuration about to be run needs a pinned model snapshot (R2C-003)."""
    from .serving import load_registry

    registry, error = load_registry(ctx)
    if error:
        return Check("model revisions are pinned", False, error)
    wanted = ctx.configs or tuple(c.config_id for c in registry.CONFIGS)
    unpinned, unknown = [], []
    for config_id in wanted:
        try:
            cfg = registry.by_id(config_id)
        except KeyError:
            unknown.append(config_id)
            continue
        if cfg.revision is None:
            unpinned.append(f"{cfg.config_id} ({cfg.model})")
    ok = not unpinned and not unknown
    if unknown:
        detail = f"not a registry configuration: {', '.join(unknown)}"
    elif unpinned:
        detail = (f"{len(unpinned)} of {len(wanted)} configurations have no snapshot revision in "
                  f"_experiments/scripts/model_revisions.json; whoever downloads the model fills "
                  f"it and the runner refuses to serve without it: " + ", ".join(unpinned))
    else:
        detail = f"all {len(wanted)} configuration(s) pinned"
    return Check("model revisions are pinned", ok, detail,
                 "cat _experiments/scripts/model_revisions.json",
                 {"unpinned": unpinned, "requested": list(wanted)})
