"""Which configuration runs on which cards, and the table for the write-up.

    python -m _experiments.scripts.runner.plan --host-gpus 4
    python -m _experiments.scripts.runner.plan --format markdown

The plan is derived from the registry, so the shell orchestrator cannot invent a
device assignment of its own: the old one pinned every TP=2 model to cards 0 and
1 whatever the lane asked for.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.runner"

from . import registry


def lanes(host_gpus: int, profile: str) -> list[dict]:
    """Assigns each configuration a device list on a host with `host_gpus` cards."""
    jobs = []
    for cfg in registry.CONFIGS:
        tp = cfg.tp_80g if profile == "80g" and cfg.tp_80g else cfg.tp
        if tp > host_gpus:
            jobs.append({"config_id": cfg.config_id, "tp": tp, "gpu": None,
                         "reason": f"needs {tp} cards, host has {host_gpus}"})
            continue
        jobs.append({"config_id": cfg.config_id, "tp": tp,
                     "gpu": ",".join(str(i) for i in range(tp)), "reason": None})
    return jobs


def table_rows() -> list[dict]:
    rows = []
    for cfg in registry.CONFIGS:
        rows.append({
            "config_id": cfg.config_id, "label": cfg.label, "group": cfg.group,
            "model": cfg.model, "revision": cfg.revision or "-",
            "tp_48g": cfg.tp, "tp_80g": cfg.tp_80g, "four_gpu_host": cfg.needs_four_gpu_host,
            "context": cfg.max_model_len, "context_e2e": cfg.context_for("e2e"),
            "output_budget": cfg.max_tokens, "parser": cfg.parser,
            "reasoning_parser": cfg.reasoning_parser or "-",
            "reasoning_mode": cfg.reasoning_mode,
            "template": cfg.chat_template or "model's own",
            "template_sha256": (registry.template_sha256(cfg.template_path) or "-")[:12],
            "smoke_required": cfg.smoke_required or "",
        })
    return rows


_COLUMNS = [("label", "Configuration"), ("model", "Model"), ("reasoning_mode", "Mode"),
            ("parser", "Tool parser"), ("reasoning_parser", "Reasoning parser"),
            ("template", "Template"), ("template_sha256", "Template sha"),
            ("tp_48g", "TP 48G"), ("tp_80g", "TP 80G"), ("context", "Context"),
            ("context_e2e", "Context E2E"), ("output_budget", "Output")]


def markdown() -> str:
    rows = table_rows()
    head = "| " + " | ".join(title for _key, title in _COLUMNS) + " |"
    rule = "|" + "|".join("---" for _ in _COLUMNS) + "|"
    body = ["| " + " | ".join(str(row[key]) for key, _title in _COLUMNS) + " |" for row in rows]
    return "\n".join([head, rule, *body])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host-gpus", type=int, help="print a device assignment for this host")
    ap.add_argument("--host-profile", choices=("48g", "80g"), default="48g")
    ap.add_argument("--format", choices=("tsv", "json", "markdown"), default="tsv")
    args = ap.parse_args(argv)

    if args.host_gpus:
        jobs = lanes(args.host_gpus, args.host_profile)
        if args.format == "json":
            print(json.dumps(jobs, ensure_ascii=False, indent=1))
        else:
            for job in jobs:
                print(f"{job['config_id']}\t{job['tp']}\t{job['gpu'] or '-'}\t"
                      f"{job['reason'] or ''}")
        return 0
    if args.format == "markdown":
        print(markdown())
    elif args.format == "json":
        print(json.dumps(table_rows(), ensure_ascii=False, indent=1))
    else:
        for row in table_rows():
            print("\t".join(str(row[key]) for key, _title in _COLUMNS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
