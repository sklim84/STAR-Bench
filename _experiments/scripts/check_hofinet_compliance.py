#!/usr/bin/env python3
"""HOFINET compliance check for the benchmark data.

The implementation is `_experiments.scripts.data_fixes.lint_benchmarks`; this entry
point is kept because the old one was referenced by the paper and the run scripts.

The previous version of this file read Korean parameter keys the data had not used
since the April re-keying, so it reported "0 violations" both for the real data and
for a copy with the keys put back in Korean, and it never checked account existence,
the 48 HOFINET amounts, fund type 4 in a fraud context, or the tool schema. Do not
quote its "0 violations" (C1-011).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from _experiments.scripts.data_fixes.lint_benchmarks import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
