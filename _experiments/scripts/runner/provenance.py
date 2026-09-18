"""What produced a run: commits, data hashes, schema hashes, environment.

Every record carries this block, and a run refuses to start when the platform
checkout, the HOFINET copy or the `hofinet` column list is not what the run was
configured against (L5-020, C1-004, C2-016, R2C-003).

The platform side of the guard lives in `src/provenance.py` and `src/data/db.py`
of STAR-Bench-Web: `get_connection()` refuses a DuckDB file that does not match
the released Parquet, and `get_provenance()` returns the hashes. This module
adds the STAR-Bench side (repository commit, schema arm hashes, chat template
hash, model revision) and the comparison against an expected pin.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

__all__ = ["EnvironmentMismatch", "collect", "star_bench_commit", "sha256_file",
           "sha256_text", "expected_pin", "check_pin", "benchmark_digest",
           "benchmark_file_hashes", "open_database", "working_tree_status"]

_ROOT = Path(__file__).resolve().parents[3]

# The `hofinet` columns the tools and the gold SQL are written against. A run on
# a database with the pre-2026-09 Korean column names is the L5-001 failure and
# must stop at startup rather than score 1,190 cases as model errors.
HOFINET_COLUMNS = (
    "date", "time_slot", "sender_bank", "sender_acc", "receiver_bank", "receiver_acc",
    "fund_type", "media_type", "amount", "is_fraud", "fraud_type", "fraud_description",
)


class EnvironmentMismatch(RuntimeError):
    """The environment is not the one the run was pinned to."""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path | str | None) -> str | None:
    if not path:
        return None
    path = Path(path)
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(root: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(root), *args],
                             capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


# Two tracked paths are written by the run procedure itself, so a run that
# follows the procedure always starts from a tree the gate would call dirty: the
# revision file is filled by whoever downloads the weights, and the preflight
# writes its own report. Neither changes what the model is asked or how the
# answer is scored, and both are recorded elsewhere -- the revision per config in
# `config.model_revision`, the report as its own artefact -- so they do not count
# towards `star_bench_dirty`. Everything else still does.
PROCEDURE_PATHS = (
    "_experiments/scripts/model_revisions.json",
    "_experiments/scripts/preflight/reports/",
)


def _split_procedure(status_output: str | None) -> tuple[list[str], list[str]]:
    """(paths the gate judges, paths the run procedure is allowed to write)."""
    judged, procedure = [], []
    for line in (status_output or "").splitlines():
        entry = _status_entry(line)
        if entry is None:
            continue
        name = entry[1]
        target = procedure if any(name == p or name.startswith(p)
                                  for p in PROCEDURE_PATHS) else judged
        target.append(name)
    return sorted(judged), sorted(procedure)


def star_bench_commit() -> dict:
    judged, procedure = _split_procedure(
        _git(_ROOT, "status", "--porcelain", "--untracked-files=no"))
    out = {"star_bench_commit": _git(_ROOT, "rev-parse", "HEAD"),
           "star_bench_dirty": bool(judged)}
    if procedure:
        out["star_bench_procedure_files"] = procedure
    return out


def working_tree_status(root: Path | str | None = None) -> dict:
    """Tracked modifications and untracked files, separately.

    `star_bench_dirty` in a run record means "a tracked file differs from the
    commit", which is what makes a run irreproducible, and it stays that. But the
    same question read with `--untracked-files=no` also hid 215 scratch files
    sitting inside the repository, so the gate says how many there are (V-10).
    """
    root = Path(root or _ROOT)
    out = _git(root, "status", "--porcelain", "--untracked-files=all")
    if out is None:
        return {"readable": False, "modified": [], "untracked": []}
    modified, untracked = [], []
    for line in out.splitlines():
        entry = _status_entry(line)
        if entry is None:
            continue
        code, name = entry
        (untracked if code == "??" else modified).append(name)
    return {"readable": True, "modified": sorted(modified), "untracked": sorted(untracked)}


_STATUS_LINE = re.compile(r"^\s*(\?\?|[A-Z!][A-Z ]?|[A-Z])\s+(.+)$")


def _status_entry(line: str) -> tuple[str, str] | None:
    """(status, path) from one `git status --porcelain` line.

    The status columns are not sliced by position: the command's output is read
    stripped, so the first line of a tree whose first entry is an unstaged
    change has already lost its leading blank and a fixed slice ate the first
    character of the path.
    """
    match = _STATUS_LINE.match(line.rstrip())
    if not match:
        return None
    code, name = match.group(1).strip() or "?", match.group(2).strip()
    if " -> " in name:                      # a rename: the new path is the one that exists
        name = name.split(" -> ", 1)[1]
    if name.startswith('"') and name.endswith('"'):
        name = name[1:-1]                   # git quotes a path with unusual characters
    return code, name


def benchmark_digest(cases_dir: Path | str | None) -> dict:
    """Hash of the case files a run read (C1-012).

    A run record said which platform commit and which database answered but not
    which benchmark files it was asked about, and the 2026 data was edited and
    reverted twice. The digest is over file name and bytes of every
    `cases_*.json` in name order, which is what `scoring.gold.load_benchmark`
    computes, so a record and an eval file can be compared.
    """
    if cases_dir is None:
        return {}
    root = Path(cases_dir)
    files = sorted(root.glob("cases_*.json"))
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return {"benchmark_dir": root.name, "benchmark_sha256": digest.hexdigest() if files else None,
            "benchmark_files": len(files)}


def benchmark_file_hashes(cases_dir: Path | str | None) -> list[dict]:
    """Per-file hashes for the run manifest; the record carries the combined one."""
    if cases_dir is None:
        return []
    return [{"name": path.name, "sha256": sha256_file(path)}
            for path in sorted(Path(cases_dir).glob("cases_*.json"))]


def open_database() -> str | None:
    """Opens the tool layer's connection, or returns why it could not be opened.

    `connection_info()` describes the connection that is open, and nothing had
    opened one when `collect()` ran, so `database.origin` and
    `database.build_info` were null in every record (C2-016).
    """
    try:
        from _experiments.scripts._platform import ensure_platform_on_path
        ensure_platform_on_path()
        from src.data import db
        db.get_connection()
        return None
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def _platform_provenance() -> dict:
    """`src.provenance.get_provenance()`, or the reason it could not be read."""
    try:
        from _experiments.scripts._platform import ensure_platform_on_path
        ensure_platform_on_path()
        from src.provenance import get_provenance
        return get_provenance()
    except Exception as exc:  # the caller decides whether that is fatal
        return {"error": f"{type(exc).__name__}: {exc}"}


def hofinet_columns() -> list[str] | None:
    try:
        from _experiments.scripts._platform import ensure_platform_on_path
        ensure_platform_on_path()
        from src.data import db
        rows = db.get_connection().execute("SELECT * FROM hofinet LIMIT 0").description
        return [r[0] for r in rows]
    except Exception:
        return None


def collect(*, arm, config: dict, check_columns: bool = True,
            cases_dir: Path | str | None = None) -> dict:
    """The Contract 2 provenance block for the current process.

    The database is opened first: everything the platform reports about it
    (`origin`, `build_info`) describes the connection that is open.
    """
    database_error = open_database()
    platform = _platform_provenance()
    record = {
        **star_bench_commit(),
        "platform_commit": platform.get("platform_commit"),
        "platform_dirty": platform.get("platform_dirty"),
        "data_sha256": platform.get("data_sha256"),
        "db_sha256": platform.get("db_sha256"),
        "model_file_sha256": platform.get("model_file_sha256"),
        "platform_prompt_sha256": platform.get("system_prompt_sha256"),
        "platform_tools_sha256": platform.get("tools_sha256"),
        "system_prompt_sha256": arm.prompt_sha256,
        "tools_sha256": arm.tools_sha256,
        "tools_lang": arm.lang,
        "prompt_variant": arm.prompt_variant,
        "streamlit_stubbed": platform.get("streamlit_stubbed"),
        "database": platform.get("database"),
        "library_versions": platform.get("library_versions"),
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if platform.get("error"):
        record["platform_error"] = platform["error"]
    if database_error:
        record["database_error"] = database_error
    record.update(benchmark_digest(cases_dir))
    if check_columns:
        record["hofinet_columns"] = hofinet_columns()
    for key in ("chat_template_sha256", "model_revision"):
        if config.get(key) is not None:
            record.setdefault(key, config[key])
    return record


def expected_pin(path: Path | str | None = None) -> dict | None:
    """The pinned environment, from `--pin` or `$STAR_BENCH_PIN`."""
    path = path or os.environ.get("STAR_BENCH_PIN")
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check_pin(record: dict, pin: dict | None, *, strict: bool = True) -> list[str]:
    """Compares the collected provenance with the pin; returns the differences.

    With `strict` the differences raise, which is what a rerun wants: a platform
    commit or a data hash that moved makes the results incomparable with the rest
    of the cohort (L5-020).
    """
    problems: list[str] = []
    if record.get("platform_error"):
        problems.append(f"platform tool layer did not load: {record['platform_error']}")
    columns = record.get("hofinet_columns")
    if columns is not None and tuple(columns) != HOFINET_COLUMNS:
        problems.append(f"hofinet columns are {columns}, expected {list(HOFINET_COLUMNS)}")
    if record.get("streamlit_stubbed") is False:
        problems.append("the Streamlit cache is live (STREAMLIT_IS_STUBBED is false); "
                        "install requirements-tools.txt only, so tool results are not cached")
    for key in ("platform_commit", "data_sha256", "db_sha256", "model_file_sha256",
                "platform_tools_sha256", "platform_prompt_sha256", "tools_sha256",
                "system_prompt_sha256"):
        want = (pin or {}).get(key)
        if want and record.get(key) != want:
            problems.append(f"{key} is {record.get(key)}, pinned to {want}")
    if not record.get("platform_error"):
        database = record.get("database") or {}
        if record.get("database_error"):
            problems.append(f"the tool layer database did not open: {record['database_error']}")
        elif not database.get("origin"):
            problems.append("the run record does not say which database object answered "
                            "(provenance.database.origin is empty)")
    if record.get("star_bench_dirty"):
        problems.append("the STAR-Bench working tree has uncommitted changes")
    if record.get("platform_dirty"):
        problems.append("the STAR-Bench-Web working tree has uncommitted changes")
    if problems and strict:
        raise EnvironmentMismatch(
            "the run environment is not the pinned one:\n  - " + "\n  - ".join(problems))
    return problems
