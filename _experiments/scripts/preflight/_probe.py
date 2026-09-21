"""Reads the environment the run would execute in, and prints it as JSON.

It runs in its own process so a platform import error is a gate failure with a
message rather than a traceback that takes the whole suite down, and so the
platform stack may live in a different interpreter than the suite
(`--platform-python`).

    python -m _experiments.scripts.preflight._probe
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.preflight"


def main() -> int:
    out: dict = {}
    try:
        from _experiments.scripts.runner import provenance
        out.update(provenance.star_bench_commit())
        out["star_bench_status"] = provenance.working_tree_status()
        out["table_columns_expected"] = list(provenance.HOFINET_COLUMNS)
    except Exception as exc:
        out["star_bench_error"] = f"{type(exc).__name__}: {exc}"

    try:
        from _experiments.scripts._platform import ensure_platform_on_path
        out["platform_root"] = str(ensure_platform_on_path())
        from src.features import agent
        out["tool_count"] = len(agent.TOOLS)
        out["tool_names"] = [t["function"]["name"] for t in agent.TOOLS]
        from src.provenance import get_provenance
        out["platform"] = get_provenance()
        from src.data import db
        described = db.get_connection().execute("SELECT * FROM hofinet LIMIT 0").description
        out["table_columns"] = [row[0] for row in described]
        out["hofinet_rows"] = db.get_connection().execute(
            "SELECT COUNT(*) FROM hofinet").fetchone()[0]
    except Exception as exc:
        out["platform_error"] = f"{type(exc).__name__}: {exc}"

    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
