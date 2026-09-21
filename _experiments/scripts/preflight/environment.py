"""Gate 1: is this the machine and the checkout the run is pinned to?

A run scored on a database whose columns had been renamed, against a platform
checkout nobody recorded, returned 1,190 cases as model failures. Every one of
those facts is cheap to read before a run, and none of them is recoverable
afterwards.

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
    checks.append(_sql_parser(ctx))

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


_SQL_PROBE = (
    "import json;"
    "from _experiments.scripts.scoring import sql;"
    "print(json.dumps({'version': sql.sqlglot_version(), 'pin': sql.SQLGLOT_PIN,"
    " 'parser': sql.extract_atoms("
    '"SELECT * FROM hofinet WHERE fraud_type IN (1, 2) AND amount BETWEEN 3 AND 4")[1],'
    " 'atoms': sql.extract_atoms("
    '"SELECT * FROM hofinet WHERE fraud_type IN (1, 2) AND amount BETWEEN 3 AND 4")[0]}))'
)


def _sql_parser(ctx: Context) -> Check:
    """The scorer reads `sql_conditions` with sqlglot; the fallback is the reserve.

    Without sqlglot the gold self-test lost two `query_transactions` cases,
    because the regex fallback dropped IN lists. Both parsers now read the same
    atoms, and this check says which one the scoring environment will use and
    whether it is the pinned version.
    """
    done = run_command([ctx.python, "-c", _SQL_PROBE], cwd=ctx.root, env=ctx.env, timeout=300)
    try:
        info = json.loads(done.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Check("the scorer parses SQL with sqlglot", False,
                     f"the SQL probe produced no JSON: {done.tail(4)}", done.command)
    atoms = [tuple(a) for a in info["atoms"]]
    wanted = [("fraud_type", "IN", [1, 2]), ("amount", "BETWEEN", [3, 4])]
    read_ok = all(tuple(a[:2]) in [(w[0], w[1]) for w in wanted] for a in atoms) and len(atoms) == 2
    ok = info["version"] == info["pin"] and info["parser"] == "sqlglot" and read_ok
    if info["version"] is None:
        detail = ("sqlglot is not installed; the scorer would fall back to the regex parser. "
                  "Install the evaluation pins (_experiments/env/requirements-eval.txt)")
    elif info["version"] != info["pin"]:
        detail = f"sqlglot {info['version']} is installed, {info['pin']} is pinned"
    elif not read_ok:
        detail = f"the parser read {atoms} from an IN plus BETWEEN statement"
    else:
        detail = f"sqlglot {info['version']}, IN and BETWEEN predicates read"
    return Check("the scorer parses SQL with sqlglot", ok, detail, done.command,
                 {"sqlglot_version": info["version"], "parser": info["parser"]})


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

    checks.append(_star_bench_tree(info, command))

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

    columns = info.get("table_columns")
    expected = info.get("table_columns_expected")
    checks.append(Check(
        "hofinet columns are the released English ones",
        columns is not None and columns == expected,
        f"{len(columns or [])} columns, {info.get('hofinet_rows')} rows"
        if columns == expected else f"columns are {columns}, expected {expected}",
        command, {"table_columns": columns}))

    stubbed = platform.get("streamlit_stubbed")
    checks.append(Check(
        "Streamlit cache is stubbed", stubbed is True,
        "tool results are not memoised" if stubbed is True
        else f"streamlit_stubbed is {stubbed}; install requirements-tools.txt only, "
             f"or the cache returns a stale result for a repeated call",
        command, {"streamlit_stubbed": stubbed}))

    return checks


def _report_files() -> tuple[str, ...]:
    """The files this command itself writes with `--report`, as git names them.

    A run that regenerates the report leaves them modified, which is not the kind
    of dirty tree this check is about; it still says so rather than hiding it.
    """
    from . import report
    from .gate import STAR_BENCH_ROOT

    return tuple(str(path.relative_to(STAR_BENCH_ROOT))
                 for path in (report.REPORT_PATH, report.JSON_PATH))


def _star_bench_tree(info: dict, command: str) -> Check:
    """The commit, the tracked modifications, and how many untracked files there are.

    Untracked files never made it into this check, because the underlying
    `git status` ran with `--untracked-files=no`: 215 scratch files sat inside
    the repository and the gate called the tree clean. They are a warning,
    not a failure - they cannot change what a tracked script does - but the count
    and the first few names are in the detail and the full list is in the data.
    """
    commit = info.get("star_bench_commit")
    status = info.get("star_bench_status") or {}
    report_files = _report_files()
    modified = [m for m in status.get("modified") or [] if m not in report_files]
    report_only = [m for m in status.get("modified") or [] if m in report_files]
    untracked = status.get("untracked") or []
    if not status.get("readable"):
        # No git status to read: fall back to what the record itself carries.
        modified = ["(unreadable)"] if info.get("star_bench_dirty") else []
    ok = bool(commit) and not modified
    detail = (commit or "unknown")[:12]
    if modified:
        detail += (f", {len(modified)} tracked file(s) modified: "
                   + ", ".join(modified[:4]))
    else:
        detail += ", no tracked file modified"
    if report_only:
        detail += (f"; the pre-flight report itself is regenerated and uncommitted "
                   f"({len(report_only)} file(s))")
    if untracked:
        detail += (f"; warning: {len(untracked)} untracked file(s) inside the repository "
                   f"({', '.join(untracked[:3])}"
                   + (", ..." if len(untracked) > 3 else "") + ")")
    return Check("STAR-Bench commit is recorded and the tree is clean", ok, detail, command,
                 {"star_bench_commit": commit, "star_bench_dirty": bool(modified),
                  "modified": modified, "report_files_modified": report_only,
                  "untracked_count": len(untracked), "untracked": untracked[:50]})


def _revisions(ctx: Context) -> Check:
    """Every configuration about to be run needs a pinned model snapshot."""
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
