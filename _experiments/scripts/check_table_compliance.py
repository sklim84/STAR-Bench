#!/usr/bin/env python3
"""HOFINET compliance check for the benchmark data.

Checks that every value the benchmark pins is a value HOFINET holds: accounts that
exist, amounts among the 48 the data carries, institution and code values from the
official tables, and gold keys that are properties of the tool they name.

The implementation is `_experiments.scripts.data_fixes.lint_benchmarks`, which runs
the same check over both language directories and exits non-zero on any violation.
This entry point is kept because the run scripts call the benchmark data gate by
this name.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from _experiments.scripts.data_fixes.lint_benchmarks import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
