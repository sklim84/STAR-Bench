"""One entry per serving configuration.

A row of the main table is one entry here, and nothing else decides how that row
is served: model id and pinned revision, tokenizer/chat template with its hash,
tool-call parser, reasoning parser and the single labelled reasoning mode (D05),
context length, output budget, temperature, seed, concurrency and tensor-parallel
size (D07). The shell launcher asks this module for the vLLM arguments, so a
configuration cannot differ between the launcher and the record (L5-017, R1-R3).
Concurrency is the one field a run may override, and the override is recorded.

Sizing targets the rerun hardware: hosts with 2 or 4 NVIDIA L40S 48 GB cards,
plus on-demand hosts with 80 GB cards. `tp` is the 48 GB plan and `tp_80g` the
80 GB one; `needs_four_gpu_host` marks the four entries that do not fit on a
two-card host. The 70B-class weights are 140 GB in bf16, which two 80 GB cards
cannot hold together with a 32k window, so those three entries are four cards on
either host (measured, not sized on paper).

`max_model_len_e2e` is the cohort's 65536 only where the model's own window
reaches it. Kanana-2 stops at 32768 and Qwen-Open-Finance-R at 40960, so those
entries carry their own value and the appendix reports the e2e window per row.
A.X-4.0-Light stops at 16384, below L5-012's single context, so it is the one
entry that also carries its own base window and output budget.

Decisions carried here: D05 (one labelled mode per model; T/NT only for Qwen3.5
`enable_thinking` and gpt-oss `reasoning_effort` high/low), D07 (one stack,
concurrency 1, >= 32k context), D21 (vendor formats, repaired templates),
C2-001 (Phi-4-mini back to 32768), L5-006 (16k output for reasoning configs),
L5-010 (Qwen3-8B family on hermes), L5-008 (Kanana-2-Think on its own template
with a reasoning parser), L5-009 (Qwen3.6 with a reasoning parser and an
explicit mode), L5-012 (one context budget), L5-025 (Mistral vendor format).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["ServingConfig", "CONFIGS", "by_id", "main_table_configs", "vllm_args",
           "client_kwargs", "chat_options", "config_block", "TEMPLATE_DIR", "UnpinnedRevision"]

_SCRIPTS = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = _SCRIPTS / "chat_templates"
REVISIONS_PATH = _SCRIPTS / "model_revisions.json"
# Paths are kept relative to _experiments/scripts so the registry, the record and
# the serving table read the same on every checkout.
KANANA_PARSER_PLUGIN = "kanana_tool_calls/kanana_tool_calls/functionary_kanana_tool_parser.py"
KANANA_TEMPLATE = "kanana_tool_calls/kanana_tool_calls/lmalign_v1.jinja"

SEED = 20260925
TEMPERATURE = 0.0
# Cases in flight per configuration. The tool layer is thread-safe (per-call
# DuckDB cursors), so the benchmark runs several cases at once; the rerun does
# not fit its deadline one request at a time. `--concurrency` overrides it, and
# the value actually used is what goes into the record and the manifest.
CONCURRENCY = 8
CONTEXT = 32768          # D07: every configuration gets at least 32k
CONTEXT_E2E = 65536      # L5-012: the end-to-end setting reads more tool output
BUDGET_PLAIN = 8192
BUDGET_REASONING = 16384  # D05, L5-006

# How the labelled reasoning mode is sent to the server.
#   none               the model has no reasoning mode
#   always_on          the model always reasons and offers no switch
#   chat_template_kwargs   enable_thinking true/false (Qwen3.5, EXAONE-4.0, Gemma-4)
#   reasoning_effort   high/low (gpt-oss; the paper's (T)/(NT) for these rows)
REASONING_CONTROLS = ("none", "always_on", "chat_template_kwargs", "reasoning_effort")


class UnpinnedRevision(RuntimeError):
    """A configuration was asked to serve without a pinned model revision."""


def _revisions() -> dict:
    if REVISIONS_PATH.exists():
        return json.loads(REVISIONS_PATH.read_text(encoding="utf-8")).get("revisions", {})
    return {}


def _resolve(name: str | None) -> Path | None:
    if not name:
        return None
    path = Path(name)
    if path.is_absolute():
        return path
    return (_SCRIPTS / name) if "/" in name else (TEMPLATE_DIR / name)


def template_sha256(path: Path | None) -> str | None:
    if path is None or not Path(path).is_file():
        return None
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class ServingConfig:
    config_id: str
    label: str
    model: str
    group: str
    parser: str
    tp: int = 1
    tp_80g: int | None = None
    reasoning_mode: str = "none"          # none | always_on | think | nothink | effort_high | effort_low
    reasoning_control: str = "none"
    reasoning_parser: str | None = None
    # A bare file name is under chat_templates/; a name with a directory is
    # relative to _experiments/scripts.
    chat_template: str | None = None
    # `max_position_embeddings` from the model's own config, filled in only where it
    # is under one of the cohort windows. It is what makes a smaller context here a
    # recorded fact instead of a silent exception, and the gate checks against it.
    model_window: int | None = None
    max_model_len: int = CONTEXT
    max_model_len_e2e: int | None = None
    max_tokens: int = BUDGET_PLAIN
    gpu_memory_utilization: float = 0.90
    extra_args: tuple[str, ...] = ()
    tool_parser_plugin: str | None = None
    # Templates trained on one call per assistant turn. The runner sends parallel
    # calls as consecutive single-call turns for these (D21, L5-005).
    serialize_parallel_calls: bool = False
    needs_four_gpu_host: bool = False
    smoke_required: str | None = None     # what a GPU smoke test must confirm
    notes: str = ""

    # -- derived ---------------------------------------------------------
    @property
    def template_path(self) -> Path | None:
        return _resolve(self.chat_template)

    @property
    def tool_parser_plugin_path(self) -> Path | None:
        return _resolve(self.tool_parser_plugin)

    @property
    def revision(self) -> str | None:
        return _revisions().get(self.model)

    @property
    def reasoning_history_key(self) -> str | None:
        """Key the chat template reads a previous turn's reasoning back from (C2-004)."""
        return "reasoning_content" if self.reasoning_parser else None

    @property
    def is_reasoning(self) -> bool:
        return self.reasoning_mode not in ("none", "nothink") or self.reasoning_parser is not None

    def context_for(self, setting: str) -> int:
        if setting == "e2e" and self.max_model_len_e2e:
            return self.max_model_len_e2e
        return self.max_model_len


def _cfg(**kw) -> ServingConfig:
    return ServingConfig(**kw)


# ---------------------------------------------------------------------------
# The 28 main-table configurations (D07). Order follows the manuscript table.
# ---------------------------------------------------------------------------

CONFIGS: tuple[ServingConfig, ...] = (
    # -- Korean-specialised ------------------------------------------------
    _cfg(config_id="ax-light", label="A.X-4.0-Light (7B)", model="skt/A.X-4.0-Light",
         group="Korean-Specialized", parser="hermes", tp=1, tp_80g=1,
         model_window=16384, max_model_len=16384, max_tokens=3072,
         max_model_len_e2e=16384,
         notes="the only entry under D07's 32768, because the model stops at 16384 "
               "and the 2026-09 round served it there too. Its own tokenizer puts "
               "the Korean system prompt and 23 tool schemas at 6177 tokens and the "
               "longest question at 334, so 3072 of output still leaves 6801 for "
               "tool results. 3072 covers the 99th percentile of what the same "
               "family generates (A.X-4.0: p99 3200 over 10049 rounds); the cost is "
               "7 of 1258 single-turn cases and 4 of 50 e2e scenarios whose history "
               "outgrows the window"),
    _cfg(config_id="ax-4.0", label="A.X-4.0 (72B)", model="skt/A.X-4.0",
         group="Korean-Specialized", parser="hermes", tp=4, tp_80g=4,
         gpu_memory_utilization=0.95, needs_four_gpu_host=True,
         max_model_len_e2e=CONTEXT_E2E),
    _cfg(config_id="exaone-1.2b", label="EXAONE-4.0-1.2B", model="LGAI-EXAONE/EXAONE-4.0-1.2B",
         group="Korean-Specialized", parser="hermes", tp=1, tp_80g=1,
         reasoning_mode="nothink", reasoning_control="chat_template_kwargs",
         extra_args=("--trust-remote-code",), max_model_len_e2e=CONTEXT_E2E,
         notes="hybrid reasoning model; D05 gives it one labelled mode, thinking off"),
    _cfg(config_id="exaone-32b", label="EXAONE-4.0-32B", model="LGAI-EXAONE/EXAONE-4.0-32B",
         group="Korean-Specialized", parser="hermes", tp=2, tp_80g=1,
         reasoning_mode="nothink", reasoning_control="chat_template_kwargs",
         extra_args=("--trust-remote-code",), max_model_len_e2e=CONTEXT_E2E,
         notes="hybrid reasoning model; D05 gives it one labelled mode, thinking off"),
    _cfg(config_id="kanana-2-inst", label="Kanana-2-Instruct",
         model="kakaocorp/kanana-2-30b-a3b-instruct", group="Korean-Specialized",
         parser="functionary_kanana", tp=2, tp_80g=1,
         chat_template=KANANA_TEMPLATE, tool_parser_plugin=KANANA_PARSER_PLUGIN,
         model_window=32768, max_model_len_e2e=32768),
    _cfg(config_id="kanana-2-think", label="Kanana-2-Think",
         model="kakaocorp/kanana-2-30b-a3b-thinking-2601", group="Korean-Specialized",
         parser="hermes", tp=2, tp_80g=1,
         reasoning_mode="always_on", reasoning_control="always_on",
         reasoning_parser="deepseek_r1", chat_template=None,
         max_tokens=BUDGET_REASONING,
         model_window=32768, max_model_len_e2e=32768,
         smoke_required="reasoning tokens appear and tool calls survive the reasoning parser",
         notes="L5-008: served on its own template (the model's, not the instruct "
               "functionary one) with a reasoning parser"),
    # -- Finance-specialised ----------------------------------------------
    _cfg(config_id="dragon-llama-fin", label="Llama-Open-Finance-8B",
         model="DragonLLM/Llama-Open-Finance-8B", group="Finance-Specialized",
         parser="llama3_json", tp=1, tp_80g=1, chat_template="llama3_tools.jinja",
         serialize_parallel_calls=True, max_model_len_e2e=CONTEXT),
    _cfg(config_id="dragon-qwen-fin", label="Qwen-Open-Finance-R-8B",
         model="DragonLLM/Qwen-Open-Finance-R-8B", group="Finance-Specialized",
         parser="hermes", tp=1, tp_80g=1, reasoning_mode="always_on",
         reasoning_control="always_on", reasoning_parser="qwen3",
         max_tokens=BUDGET_REASONING, model_window=40960, max_model_len_e2e=40960,
         smoke_required="native tool calls, not the fallback parser",
         notes="L5-010: the template emits Hermes <tool_call> JSON, so qwen3_xml "
               "never matched and every call came from the text fallback"),
    # -- General purpose ---------------------------------------------------
    _cfg(config_id="gpt-oss-20b-nt", label="gpt-oss-20B (NT)", model="openai/gpt-oss-20b",
         group="General-Purpose", parser="openai", tp=1, tp_80g=1,
         reasoning_mode="effort_low", reasoning_control="reasoning_effort",
         reasoning_parser="openai_gptoss", max_tokens=BUDGET_REASONING,
         max_model_len_e2e=CONTEXT_E2E),
    _cfg(config_id="gpt-oss-20b-t", label="gpt-oss-20B (T)", model="openai/gpt-oss-20b",
         group="General-Purpose", parser="openai", tp=1, tp_80g=1,
         reasoning_mode="effort_high", reasoning_control="reasoning_effort",
         reasoning_parser="openai_gptoss", max_tokens=BUDGET_REASONING,
         max_model_len_e2e=CONTEXT_E2E),
    _cfg(config_id="gpt-oss-120b-nt", label="gpt-oss-120B (NT)", model="openai/gpt-oss-120b",
         group="General-Purpose", parser="openai", tp=4, tp_80g=2,
         reasoning_mode="effort_low", reasoning_control="reasoning_effort",
         reasoning_parser="openai_gptoss", max_tokens=BUDGET_REASONING,
         gpu_memory_utilization=0.95, needs_four_gpu_host=True,
         max_model_len_e2e=CONTEXT_E2E, notes="MXFP4 weights"),
    _cfg(config_id="gpt-oss-120b-t", label="gpt-oss-120B (T)", model="openai/gpt-oss-120b",
         group="General-Purpose", parser="openai", tp=4, tp_80g=2,
         reasoning_mode="effort_high", reasoning_control="reasoning_effort",
         reasoning_parser="openai_gptoss", max_tokens=BUDGET_REASONING,
         gpu_memory_utilization=0.95, needs_four_gpu_host=True,
         max_model_len_e2e=CONTEXT_E2E, notes="MXFP4 weights"),
    _cfg(config_id="llama-3.2-3b", label="Llama-3.2-3B", model="meta-llama/Llama-3.2-3B-Instruct",
         group="General-Purpose", parser="llama3_json", tp=1, tp_80g=1,
         chat_template="llama3_tools.jinja", serialize_parallel_calls=True,
         max_model_len_e2e=CONTEXT_E2E,
         notes="C2-007, L5-005: repaired template, and the runner serialises parallel calls"),
    _cfg(config_id="llama-3.3-70b", label="Llama-3.3-70B", model="meta-llama/Llama-3.3-70B-Instruct",
         group="General-Purpose", parser="llama3_json", tp=4, tp_80g=4,
         chat_template="llama3_tools.jinja", serialize_parallel_calls=True,
         gpu_memory_utilization=0.95, needs_four_gpu_host=True,
         max_model_len_e2e=CONTEXT_E2E),
    _cfg(config_id="hermes-3-8b", label="Hermes-3-8B", model="NousResearch/Hermes-3-Llama-3.1-8B",
         group="General-Purpose", parser="hermes", tp=1, tp_80g=1,
         max_model_len_e2e=CONTEXT),
    _cfg(config_id="ministral-3b", label="Ministral-3-3B",
         model="mistralai/Ministral-3-3B-Instruct-2512", group="General-Purpose",
         parser="mistral", tp=1, tp_80g=1,
         extra_args=("--tokenizer-mode", "mistral", "--config-format", "mistral",
                     "--load-format", "mistral"),
         max_model_len_e2e=CONTEXT_E2E,
         notes="L5-025: vendor tokenizer/config/load format, which also fixes the "
               "9-character tool_call_id rule"),
    _cfg(config_id="mistral-small", label="Mistral-Small-24B",
         model="mistralai/Mistral-Small-3.2-24B-Instruct-2506", group="General-Purpose",
         parser="mistral", tp=2, tp_80g=1,
         extra_args=("--tokenizer-mode", "mistral", "--config-format", "mistral",
                     "--load-format", "mistral"),
         max_model_len_e2e=CONTEXT_E2E, notes="L5-025: vendor format"),
    _cfg(config_id="phi-4-mini", label="Phi-4-mini", model="microsoft/Phi-4-mini-instruct",
         group="General-Purpose", parser="phi4_mini_json", tp=1, tp_80g=1,
         chat_template="phi4_mini_tools.jinja", max_model_len_e2e=CONTEXT_E2E,
         notes="C2-001: back to 32768; C2-018: repaired template"),
    _cfg(config_id="qwen35-4b-nt", label="Qwen3.5-4B (NT)", model="Qwen/Qwen3.5-4B",
         group="General-Purpose", parser="qwen3_coder", tp=1, tp_80g=1,
         reasoning_mode="nothink", reasoning_control="chat_template_kwargs",
         reasoning_parser="qwen3", max_tokens=BUDGET_REASONING, max_model_len_e2e=CONTEXT_E2E,
         notes="the NT half of the pair keeps the T half's output budget, so the two "
               "rows differ in the mode and not in the budget (L5-006)"),
    _cfg(config_id="qwen35-4b-t", label="Qwen3.5-4B (T)", model="Qwen/Qwen3.5-4B",
         group="General-Purpose", parser="qwen3_coder", tp=1, tp_80g=1,
         reasoning_mode="think", reasoning_control="chat_template_kwargs",
         reasoning_parser="qwen3", max_tokens=BUDGET_REASONING, max_model_len_e2e=CONTEXT_E2E),
    _cfg(config_id="qwen35-27b-nt", label="Qwen3.5-27B (NT)", model="Qwen/Qwen3.5-27B",
         group="General-Purpose", parser="qwen3_coder", tp=2, tp_80g=1,
         reasoning_mode="nothink", reasoning_control="chat_template_kwargs",
         reasoning_parser="qwen3", max_tokens=BUDGET_REASONING, max_model_len_e2e=CONTEXT_E2E,
         notes="the NT half of the pair keeps the T half's output budget (L5-006)"),
    _cfg(config_id="qwen35-27b-t", label="Qwen3.5-27B (T)", model="Qwen/Qwen3.5-27B",
         group="General-Purpose", parser="qwen3_coder", tp=2, tp_80g=1,
         reasoning_mode="think", reasoning_control="chat_template_kwargs",
         reasoning_parser="qwen3", max_tokens=BUDGET_REASONING, max_model_len_e2e=CONTEXT_E2E),
    _cfg(config_id="qwen36-27b", label="Qwen3.6-27B", model="Qwen/Qwen3.6-27B",
         group="General-Purpose", parser="qwen3_xml", tp=2, tp_80g=1,
         reasoning_mode="think", reasoning_control="chat_template_kwargs",
         reasoning_parser="qwen3", max_tokens=BUDGET_REASONING, max_model_len_e2e=CONTEXT_E2E,
         notes="L5-009: reasoning parser added and the mode is labelled, not implicit"),
    _cfg(config_id="qwen36-35b-a3b", label="Qwen3.6-35B-A3B", model="Qwen/Qwen3.6-35B-A3B",
         group="General-Purpose", parser="qwen3_xml", tp=2, tp_80g=1,
         reasoning_mode="think", reasoning_control="chat_template_kwargs",
         reasoning_parser="qwen3", max_tokens=BUDGET_REASONING, max_model_len_e2e=CONTEXT_E2E,
         notes="L5-009"),
    _cfg(config_id="xlam-3b", label="xLAM-2-3B", model="Salesforce/xLAM-2-3b-fc-r",
         group="General-Purpose", parser="xlam", tp=1, tp_80g=1,
         max_model_len_e2e=CONTEXT),
    _cfg(config_id="xlam-70b", label="xLAM-2-70B", model="Salesforce/Llama-xLAM-2-70b-fc-r",
         group="General-Purpose", parser="xlam", tp=4, tp_80g=4,
         gpu_memory_utilization=0.95, needs_four_gpu_host=True, max_model_len_e2e=CONTEXT),
    _cfg(config_id="gemma-4-e4b", label="Gemma-4-E4B", model="google/gemma-4-E4B-it",
         group="General-Purpose", parser="gemma4", tp=1, tp_80g=1,
         reasoning_mode="nothink", reasoning_control="chat_template_kwargs",
         max_model_len_e2e=CONTEXT_E2E,
         notes="toggle model; D05 gives it one labelled mode, thinking off"),
    _cfg(config_id="gemma-4-31b", label="Gemma-4-31B", model="google/gemma-4-31B-it",
         group="General-Purpose", parser="gemma4", tp=2, tp_80g=1,
         reasoning_mode="nothink", reasoning_control="chat_template_kwargs",
         gpu_memory_utilization=0.92, max_model_len_e2e=CONTEXT_E2E,
         notes="toggle model; D05 gives it one labelled mode, thinking off"),
)

_BY_ID = {c.config_id: c for c in CONFIGS}


def by_id(config_id: str) -> ServingConfig:
    try:
        return _BY_ID[config_id]
    except KeyError:
        raise KeyError(f"unknown serving configuration {config_id!r}; "
                       f"known: {', '.join(sorted(_BY_ID))}") from None


def main_table_configs() -> tuple[ServingConfig, ...]:
    return CONFIGS


# ---------------------------------------------------------------------------
# Serving and client sides of one configuration
# ---------------------------------------------------------------------------

def vllm_args(cfg: ServingConfig, *, setting: str = "single", port: int = 11434,
              require_revision: bool = True) -> list[str]:
    """The full vLLM server argument list for this configuration."""
    revision = cfg.revision
    if revision is None and require_revision:
        raise UnpinnedRevision(
            f"{cfg.config_id}: no snapshot revision pinned for {cfg.model}. Add it to "
            f"{REVISIONS_PATH.name} (R2C-003) or pass --allow-unpinned-revision for a smoke run.")
    args = ["--model", cfg.model, "--port", str(port),
            "--max-model-len", str(cfg.context_for(setting)),
            "--gpu-memory-utilization", str(cfg.gpu_memory_utilization),
            "--tensor-parallel-size", str(cfg.tp),
            "--seed", str(SEED),
            "--enable-auto-tool-choice", "--tool-call-parser", cfg.parser]
    if revision:
        args += ["--revision", revision, "--tokenizer-revision", revision]
    if cfg.reasoning_parser:
        args += ["--reasoning-parser", cfg.reasoning_parser]
    if cfg.tool_parser_plugin:
        args += ["--tool-parser-plugin", str(cfg.tool_parser_plugin_path)]
    if cfg.template_path:
        args += ["--chat-template", str(cfg.template_path)]
    args += list(cfg.extra_args)
    return args


def client_kwargs(cfg: ServingConfig) -> dict:
    """Request-side options the runner applies to every call of this configuration."""
    out: dict = {"temperature": TEMPERATURE, "seed": SEED, "max_tokens": cfg.max_tokens}
    if cfg.reasoning_control == "chat_template_kwargs":
        out["chat_template_kwargs"] = {"enable_thinking": cfg.reasoning_mode == "think"}
    elif cfg.reasoning_control == "reasoning_effort":
        out["reasoning_effort"] = "high" if cfg.reasoning_mode == "effort_high" else "low"
    return out


def chat_options(cfg: ServingConfig, *, timeout_s: float = 300.0, max_retries: int = 2,
                 provider: dict | None = None, served_model_name: str | None = None):
    """The `client.ChatOptions` for this configuration."""
    from .client import ChatOptions

    kwargs = client_kwargs(cfg)
    return ChatOptions(
        model=served_model_name or cfg.model,
        max_tokens=kwargs["max_tokens"],
        temperature=kwargs["temperature"],
        seed=kwargs["seed"],
        chat_template_kwargs=kwargs.get("chat_template_kwargs"),
        reasoning_effort=kwargs.get("reasoning_effort"),
        reasoning_history_key=cfg.reasoning_history_key,
        serialize_parallel_calls=cfg.serialize_parallel_calls,
        max_retries=max_retries,
        timeout_s=timeout_s,
        provider=provider,
    )


def config_block(cfg: ServingConfig, *, setting: str = "single",
                 engine: str = "vllm", engine_version: str | None = None) -> dict:
    """The Contract 2 `config` block for this configuration."""
    return {
        "config_id": cfg.config_id,
        "label": cfg.label,
        "model": cfg.model,
        "model_revision": cfg.revision,
        "engine": engine,
        "engine_version": engine_version,
        "parser": cfg.parser,
        "reasoning_parser": cfg.reasoning_parser,
        "reasoning_mode": cfg.reasoning_mode,
        "reasoning_control": cfg.reasoning_control,
        "chat_template": cfg.chat_template,
        "chat_template_sha256": template_sha256(cfg.template_path),
        "max_model_len": cfg.context_for(setting),
        "max_tokens": cfg.max_tokens,
        "temperature": TEMPERATURE,
        "seed": SEED,
        "concurrency": CONCURRENCY,
        "tensor_parallel_size": cfg.tp,
    }
