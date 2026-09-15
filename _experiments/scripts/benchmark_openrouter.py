"""Single-turn runner over an OpenRouter endpoint: a preset for `benchmark.py`.

D07 puts all 28 configurations and all four cells of the 2x2 on one pinned local
vLLM stack, so nothing in the paper comes through this path any more. It stays
for the rows a co-author cannot serve locally, and it now pins what the gateway
does instead of leaving it to the gateway (L5-014):

  * `allow_fallbacks` is off and `require_parameters` is on, so a request that
    the chosen provider cannot honour fails instead of being silently rerouted;
  * `--provider-order` and `--provider-quantizations` pin provider and weights;
  * the provider, the model the gateway says it used and the usage block are
    recorded on every round.

    PYTHONPATH=. python -m _experiments.scripts.benchmark_openrouter \
        --model qwen/qwen3.5-27b --tools-lang kr \
        --provider-order deepinfra --provider-quantizations bf16 \
        --out _experiments/results_2026rerun/single/qwen35-27b-openrouter

A run through this path is a different serving stack from the local one and must
be reported as such; it is not interchangeable with a registry configuration.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_STARBENCH_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_STARBENCH_ROOT))

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main(argv: list[str] | None = None) -> int:
    _load_dotenv(_STARBENCH_ROOT / ".env")
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY is not set; put it in .env or the environment",
              file=sys.stderr)
        return 1
    # A local endpoint in the environment would silently take over the run.
    os.environ.pop("VLLM_BASE_URL", None)

    from _experiments.scripts.benchmark import main as run_single

    argv = list(sys.argv[1:] if argv is None else argv)
    if not any(a.startswith("--base-url") for a in argv):
        argv += ["--base-url", OPENROUTER_BASE_URL]
    if not any(a.startswith("--api-key-env") for a in argv):
        argv += ["--api-key-env", "OPENROUTER_API_KEY"]
    if not any(a.startswith("--allow-unpinned-revision") for a in argv):
        # A gateway does not expose a snapshot revision; the provider pins take its place.
        argv += ["--allow-unpinned-revision"]
    return run_single(argv)


if __name__ == "__main__":
    raise SystemExit(main())
