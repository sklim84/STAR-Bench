"""Starts the vLLM server for one registry configuration, or prints its arguments.

    python -m _experiments.scripts.serve --config qwen35-27b-t --gpu 2,3 --port 11435
    python -m _experiments.scripts.serve --config qwen35-27b-t --print-only

The launcher used to build the command in the shell and pin every TP=2 model to
GPUs 0 and 1 whatever `--gpu` said, so two lanes fought over the same cards, the
second lane's server failed to start, the model was skipped and the script still
reported `rc=0`. Here the devices come from `--gpu`, the count has to
match the configuration's tensor-parallel size, and a server that does not come
up exits non-zero.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from _experiments.scripts.runner import registry  # noqa: E402


def wait_for_server(port: int, timeout_s: int, process: subprocess.Popen | None) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if process is not None and process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3):
                return True
        except (urllib.error.URLError, OSError):
            time.sleep(5)
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True, help="serving configuration id")
    ap.add_argument("--gpu", default=os.environ.get("CUDA_VISIBLE_DEVICES", "0"),
                    help="comma-separated CUDA device ids for this server")
    ap.add_argument("--port", type=int, default=11434)
    ap.add_argument("--setting", choices=("single", "oracle", "e2e"), default="single")
    ap.add_argument("--host-profile", choices=("48g", "80g"), default="48g",
                    help="which tensor-parallel plan to use")
    ap.add_argument("--allow-unpinned-revision", action="store_true")
    ap.add_argument("--print-only", action="store_true", help="print the command and exit")
    ap.add_argument("--print-json", action="store_true", help="print the config block and exit")
    ap.add_argument("--wait", type=int, default=900, help="seconds to wait for /health")
    ap.add_argument("--log", type=Path, help="file for the server log")
    args = ap.parse_args(argv)

    cfg = registry.by_id(args.config)
    if args.print_json:
        print(json.dumps(registry.config_block(cfg, setting=args.setting), ensure_ascii=False,
                         indent=1))
        return 0

    devices = [d for d in args.gpu.split(",") if d.strip()]
    tp = cfg.tp_80g if args.host_profile == "80g" and cfg.tp_80g else cfg.tp
    if len(devices) != tp:
        print(f"{cfg.config_id} needs tensor-parallel-size {tp} on the {args.host_profile} "
              f"profile, but --gpu names {len(devices)} device(s): {args.gpu}", file=sys.stderr)
        return 2

    vllm = registry.vllm_args(cfg, setting=args.setting, port=args.port,
                              require_revision=not args.allow_unpinned_revision)
    # The tensor-parallel size follows the host profile, not the 48 GB default.
    vllm[vllm.index("--tensor-parallel-size") + 1] = str(tp)
    command = [sys.executable, "-m", "vllm.entrypoints.openai.api_server", *vllm]
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=",".join(devices))

    if args.print_only:
        print(f"CUDA_VISIBLE_DEVICES={','.join(devices)} " + shlex.join(command))
        return 0

    log = open(args.log, "w", encoding="utf-8") if args.log else None
    try:
        process = subprocess.Popen(command, env=env, stdout=log or None,
                                   stderr=subprocess.STDOUT if log else None)
        if not wait_for_server(args.port, args.wait, process):
            print(f"{cfg.config_id}: the server did not come up on port {args.port}",
                  file=sys.stderr)
            if args.log:
                print(f"  see {args.log}", file=sys.stderr)
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
            return 1
        print(f"{cfg.config_id}: ready on port {args.port} (pid {process.pid}, "
              f"CUDA_VISIBLE_DEVICES={','.join(devices)})")
        return process.wait()
    finally:
        if log is not None:
            log.close()


if __name__ == "__main__":
    raise SystemExit(main())
