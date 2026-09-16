"""Measures the prompt budget of every configuration on the Korean arm.

Runs in its own process because loading the Korean arm pulls in the platform tool
layer, and because a tokenizer that can be loaded offline stays out of the
suite's memory.

    python -m _experiments.scripts.preflight._budget_driver
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.preflight"


def main() -> int:
    from _experiments.scripts.runner import arms, preflight, registry
    from .data import load_cases
    from .gate import STAR_BENCH_ROOT

    arm = arms.load_arm("kr")
    cases, _ = load_cases(STAR_BENCH_ROOT / "benchmarks")
    rows = []
    for cfg in registry.CONFIGS:
        for setting in ("single", "e2e"):
            budget = preflight.measure(arm=arm, cases=cases, model=cfg.model,
                                       revision=cfg.revision,
                                       max_model_len=cfg.context_for(setting),
                                       max_tokens=cfg.max_tokens)
            rows.append({"config_id": cfg.config_id, "setting": setting,
                         **budget.as_dict()})
    print(json.dumps({"min_headroom": preflight.MIN_HEADROOM, "rows": rows},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
