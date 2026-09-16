"""Command-line pieces both runners share: options, guards, arm, writer.

The two runners take the same options with the same meaning and the same
defaults, so a run command that is right for one is right for the other. The
schema arm has no default that depends on the runner: `--tools-lang` is required,
because the pre-audit default was documented as Korean and was in fact the
English platform schema (C2-015).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import arms, preflight, provenance, records, registry

__all__ = ["add_common_arguments", "resolve", "RunSetup"]

_ROOT = Path(__file__).resolve().parents[3]


def add_common_arguments(ap: argparse.ArgumentParser) -> None:
    g = ap.add_argument_group("configuration")
    g.add_argument("--config", help="serving configuration id from runner/registry.py")
    g.add_argument("--model", help="model id to send, when the run is not a registry entry")
    g.add_argument("--served-model-name", help="name the endpoint knows the model by")
    g.add_argument("--tools-lang", required=True, choices=arms.ARM_NAMES,
                   help="schema arm: kr (tools_kr.py) or en (platform agent.TOOLS)")
    g.add_argument("--prompt-variant", default="baseline",
                   help="system-prompt variant from _experiments/scripts/prompt_variants "
                        "(default: baseline, which is what the main table runs)")
    g.add_argument("--query-lang", choices=("kr", "en"),
                   help="language of the questions (default: from the benchmark directory)")
    g.add_argument("--max-tokens", type=int, help="override the output budget")
    g.add_argument("--max-model-len", type=int, help="override the context length for the record")
    g.add_argument("--max-rounds", type=int, default=None, help="tool-calling rounds per case")
    g.add_argument("--concurrency", type=int, default=registry.CONCURRENCY,
                   help=f"cases (or scenarios) in flight; turns inside a scenario stay "
                        f"sequential (default {registry.CONCURRENCY}, 1 runs inline)")
    g.add_argument("--max-retries", type=int, default=2,
                   help="retries per request; a deterministic 4xx is never retried")
    g.add_argument("--allow-unpinned-revision", action="store_true",
                   help="run a model whose snapshot revision is not pinned (smoke runs only)")

    g = ap.add_argument_group("endpoint")
    g.add_argument("--base-url", default=os.environ.get("VLLM_BASE_URL"),
                   help="OpenAI-compatible endpoint (default: $VLLM_BASE_URL)")
    g.add_argument("--api-key-env", default=None, help="environment variable holding the API key")
    g.add_argument("--timeout", type=float, default=float(os.environ.get("BENCH_TIMEOUT", "300")))
    g.add_argument("--provider-order", help="comma-separated provider order (OpenRouter)")
    g.add_argument("--provider-quantizations", help="comma-separated allowed quantizations")
    g.add_argument("--allow-provider-fallbacks", action="store_true",
                   help="let the gateway fall back to another provider (off by default)")

    g = ap.add_argument_group("run")
    g.add_argument("--out", required=True, type=Path,
                   help="output directory for the Contract 2 records (fresh directory)")
    g.add_argument("--run-id", help="run identifier (default: <config>-<timestamp>-<hex>)")
    g.add_argument("--resume", action="store_true",
                   help="skip cases this output directory already holds a record for")
    g.add_argument("--case-ids", help="comma-separated case ids; requires --partial")
    g.add_argument("--case-ids-file", type=Path, help="file of case ids, one per line")
    g.add_argument("--partial", action="store_true",
                   help="this run covers a subset; its records are written to a .partial file")
    g.add_argument("--limit", type=int, help="run only the first N cases (smoke runs)")

    g = ap.add_argument_group("guards")
    g.add_argument("--pin", type=Path, help="JSON file of expected provenance values")
    g.add_argument("--no-env-check", action="store_true",
                   help="record the environment but do not refuse a mismatch")
    g.add_argument("--no-preflight", action="store_true", help="skip the prompt budget check")
    g.add_argument("--preflight-only", action="store_true",
                   help="report the prompt budget and exit without calling the model")


class RunSetup:
    """Everything a runner needs after the options have been resolved."""

    def __init__(self, *, args, arm, config_block, chat_options, writer, run_id,
                 query_lang, provenance_block, serving=None):
        self.concurrency = args.concurrency
        self.args = args
        self.arm = arm
        self.config = config_block
        self.chat_options = chat_options
        self.writer = writer
        self.run_id = run_id
        self.query_lang = query_lang
        self.provenance = provenance_block
        self.serving = serving


def _case_filter(args) -> set[str] | None:
    ids: set[str] = set()
    if args.case_ids:
        ids |= {c.strip() for c in args.case_ids.split(",") if c.strip()}
    if args.case_ids_file:
        ids |= {line.strip() for line in args.case_ids_file.read_text(encoding="utf-8").splitlines()
                if line.strip()}
    if not ids:
        return None
    if not args.partial:
        raise SystemExit(
            "--case-ids/--case-ids-file selects a subset, so the run must be marked --partial. "
            "A subset written into a full eval file is what produced the eval files with "
            "total_cases = 0 (C2-014).")
    return ids


def _provider(args) -> dict | None:
    if not (args.provider_order or args.provider_quantizations):
        return None
    provider: dict = {"allow_fallbacks": bool(args.allow_provider_fallbacks),
                      "require_parameters": True}
    if args.provider_order:
        provider["order"] = [p.strip() for p in args.provider_order.split(",") if p.strip()]
    if args.provider_quantizations:
        provider["quantizations"] = [q.strip() for q in args.provider_quantizations.split(",")
                                     if q.strip()]
    return provider


def resolve(args, *, cases: list[dict], setting: str, query_lang_default: str,
            engine: str = "vllm") -> RunSetup:
    """Applies the options, runs the guards and opens the record writer."""
    if not args.config and not args.model:
        raise SystemExit("pass --config <registry id> or --model <model id>")

    arm = arms.load_arm(args.tools_lang, prompt_variant=args.prompt_variant)
    query_lang = args.query_lang or query_lang_default

    if args.config:
        serving = registry.by_id(args.config)
        if serving.revision is None and not args.allow_unpinned_revision:
            raise SystemExit(
                f"{serving.config_id}: no snapshot revision is pinned for {serving.model}. Fill "
                f"_experiments/scripts/model_revisions.json (R2C-003) or pass "
                f"--allow-unpinned-revision for a smoke run.")
        config = registry.config_block(serving, setting=setting, engine=engine)
        options = registry.chat_options(serving, timeout_s=args.timeout,
                                        max_retries=args.max_retries, provider=_provider(args),
                                        served_model_name=args.served_model_name)
        run_prefix = args.config
    else:
        serving = None
        config = {"config_id": args.model, "label": args.model, "model": args.model,
                  "model_revision": None, "engine": engine, "engine_version": None,
                  "parser": None, "reasoning_parser": None, "reasoning_mode": "none",
                  "reasoning_control": "none", "chat_template": None,
                  "chat_template_sha256": None, "max_model_len": args.max_model_len,
                  "max_tokens": args.max_tokens or registry.BUDGET_PLAIN,
                  "temperature": registry.TEMPERATURE, "seed": registry.SEED,
                  "concurrency": registry.CONCURRENCY, "tensor_parallel_size": None}
        from .client import ChatOptions
        options = ChatOptions(model=args.served_model_name or args.model,
                              max_tokens=config["max_tokens"], temperature=registry.TEMPERATURE,
                              seed=registry.SEED, max_retries=args.max_retries,
                              timeout_s=args.timeout, provider=_provider(args))
        run_prefix = args.model.replace("/", "_")

    if args.max_tokens:
        options.max_tokens = args.max_tokens
        config["max_tokens"] = args.max_tokens
    if args.max_model_len:
        config["max_model_len"] = args.max_model_len
    if args.concurrency < 1:
        raise SystemExit("--concurrency must be at least 1")
    config["concurrency"] = args.concurrency

    config["prompt_variant"] = arm.prompt_variant
    prov = provenance.collect(arm=arm, config=config)
    problems = provenance.check_pin(prov, provenance.expected_pin(args.pin),
                                    strict=not args.no_env_check)
    if problems:
        print("environment differences (recorded, not fatal because of --no-env-check):",
              file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)

    if not args.no_preflight and config.get("max_model_len"):
        budget = preflight.measure(arm=arm, cases=cases, model=config["model"],
                                   revision=config.get("model_revision"),
                                   max_model_len=config["max_model_len"],
                                   max_tokens=config["max_tokens"])
        print(f"preflight: {json.dumps(dict(budget.as_dict(), concurrency=args.concurrency), ensure_ascii=False)}")
        preflight.check(budget)
        prov["preflight"] = dict(budget.as_dict(), concurrency=args.concurrency)
    if args.preflight_only:
        raise SystemExit(0)

    suffix = "" if arm.prompt_variant == "baseline" else f"-{arm.prompt_variant}"
    run_id = args.run_id or records.new_run_id(
        f"{run_prefix}-{args.tools_lang}-{setting}{suffix}")
    writer = records.RecordWriter(args.out, run_id, partial=args.partial)
    return RunSetup(args=args, arm=arm, config_block=config, chat_options=options, writer=writer,
                    run_id=run_id, query_lang=query_lang, provenance_block=prov, serving=serving)


def select_cases(cases: list[dict], args, *, keys, out_dir: Path) -> list[dict]:
    """Applies --case-ids, --limit and --resume to the case list."""
    wanted = _case_filter(args)
    if wanted is not None:
        known = {c["id"] for c in cases}
        missing = sorted(wanted - known)
        if missing:
            raise SystemExit(f"--case-ids names {len(missing)} case(s) the benchmark does not "
                             f"contain: {missing[:5]}")
        cases = [c for c in cases if c["id"] in wanted]
    if args.limit:
        cases = cases[:args.limit]
    if args.resume:
        done = records.resume_state(out_dir, keys, allow_partial=args.partial)
        cases = [c for c in cases if not all(k in done for k in keys_of(c, keys))]
        print(f"resume: {len(done)} record(s) already present, {len(cases)} case(s) to run")
    return cases


def keys_of(case: dict, all_keys) -> list[str]:
    prefix = case["id"]
    return [k for k in all_keys if k == prefix or k.startswith(f"{prefix}#")]


def client_pool(args, options):
    """One model client per worker thread, sharing the read-only request options."""
    from .client import ModelClient
    from .parallel import ClientPool

    return ClientPool(lambda: ModelClient(open_client(args, options), options))


def open_client(args, options):
    """The OpenAI-compatible client, with the library's own silent retries off."""
    from openai import OpenAI

    api_key = os.environ.get(args.api_key_env, "EMPTY") if args.api_key_env else "EMPTY"
    kwargs = {"api_key": api_key, "timeout": options.timeout_s, "max_retries": 0}
    if args.base_url:
        kwargs["base_url"] = args.base_url
    return OpenAI(**kwargs)
