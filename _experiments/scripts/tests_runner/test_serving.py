"""The serving registry, the prompt budget preflight and the repaired templates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from _experiments.scripts.runner import arms, preflight, registry

_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Registry (D05, D07, D21, C2-001, L5-006 ... L5-014, L5-025)
# ---------------------------------------------------------------------------

def test_there_is_one_entry_per_main_table_row():
    assert len(registry.CONFIGS) == 28
    assert len({c.config_id for c in registry.CONFIGS}) == 28
    assert len({c.label for c in registry.CONFIGS}) == 28


def test_every_configuration_has_a_context_of_at_least_32k_and_an_output_budget():
    for cfg in registry.CONFIGS:
        assert cfg.max_model_len >= 32768, cfg.config_id
        assert cfg.max_tokens >= 8192, cfg.config_id
        assert cfg.context_for("e2e") >= cfg.max_model_len, cfg.config_id


def test_every_reasoning_configuration_gets_the_16k_output_budget():
    """D05, L5-006. Both halves of a T/NT pair get it, so the pair differs only in mode."""
    for cfg in registry.CONFIGS:
        if cfg.reasoning_parser:
            assert cfg.max_tokens == registry.BUDGET_REASONING, cfg.config_id
        else:
            assert cfg.max_tokens == registry.BUDGET_PLAIN, cfg.config_id


def test_both_halves_of_a_pair_share_every_setting_except_the_mode():
    by_model = {}
    for cfg in registry.CONFIGS:
        by_model.setdefault(cfg.model, []).append(cfg)
    for cfgs in by_model.values():
        if len(cfgs) < 2:
            continue
        a, b = cfgs
        for field in ("parser", "reasoning_parser", "chat_template", "max_model_len",
                      "max_tokens", "tp", "gpu_memory_utilization", "extra_args"):
            assert getattr(a, field) == getattr(b, field), f"{a.config_id}/{b.config_id}.{field}"
        assert a.reasoning_mode != b.reasoning_mode


def test_every_configuration_is_deterministic_and_carries_the_default_concurrency():
    for cfg in registry.CONFIGS:
        block = registry.config_block(cfg)
        assert block["temperature"] == 0.0
        assert block["seed"] == registry.SEED
        # The registry holds the default; a run records the value it actually used.
        assert block["concurrency"] == registry.CONCURRENCY
    assert registry.CONCURRENCY >= 1


def test_only_qwen35_and_gpt_oss_have_two_modes():
    """D05: one labelled mode per model, T/NT pairs only for those two families."""
    by_model = {}
    for cfg in registry.CONFIGS:
        by_model.setdefault(cfg.model, []).append(cfg)
    paired = {model for model, cfgs in by_model.items() if len(cfgs) > 1}
    assert paired == {"Qwen/Qwen3.5-4B", "Qwen/Qwen3.5-27B",
                      "openai/gpt-oss-20b", "openai/gpt-oss-120b"}
    for model in ("Qwen/Qwen3.5-4B", "Qwen/Qwen3.5-27B"):
        assert {c.reasoning_mode for c in by_model[model]} == {"think", "nothink"}
        assert {c.reasoning_control for c in by_model[model]} == {"chat_template_kwargs"}
    for model in ("openai/gpt-oss-20b", "openai/gpt-oss-120b"):
        assert {c.reasoning_mode for c in by_model[model]} == {"effort_high", "effort_low"}
        assert {c.reasoning_control for c in by_model[model]} == {"reasoning_effort"}


def test_every_mode_is_labelled_and_explicitly_sent():
    for cfg in registry.CONFIGS:
        assert cfg.reasoning_mode in ("none", "always_on", "think", "nothink",
                                      "effort_high", "effort_low"), cfg.config_id
        kwargs = registry.client_kwargs(cfg)
        if cfg.reasoning_control == "chat_template_kwargs":
            assert "enable_thinking" in kwargs["chat_template_kwargs"], cfg.config_id
        if cfg.reasoning_control == "reasoning_effort":
            assert kwargs["reasoning_effort"] in ("high", "low"), cfg.config_id


def test_phi_4_mini_is_back_to_32768():
    cfg = registry.by_id("phi-4-mini")
    assert cfg.max_model_len == 32768
    assert cfg.chat_template == "phi4_mini_tools.jinja"


def test_the_qwen3_8b_family_and_the_finance_qwen_use_the_hermes_parser():
    assert registry.by_id("dragon-qwen-fin").parser == "hermes"
    assert registry.by_id("dragon-qwen-fin").reasoning_parser == "qwen3"


def test_kanana_think_has_its_own_template_and_a_reasoning_parser():
    think = registry.by_id("kanana-2-think")
    instruct = registry.by_id("kanana-2-inst")
    assert think.chat_template is None
    assert think.reasoning_parser
    assert instruct.chat_template != think.chat_template
    assert instruct.reasoning_parser is None


def test_qwen36_has_a_reasoning_parser_and_an_explicit_mode():
    for config_id in ("qwen36-27b", "qwen36-35b-a3b"):
        cfg = registry.by_id(config_id)
        assert cfg.reasoning_parser == "qwen3"
        assert cfg.reasoning_mode == "think"


def test_the_mistral_models_are_served_with_the_vendor_format():
    for config_id in ("ministral-3b", "mistral-small"):
        extra = registry.by_id(config_id).extra_args
        assert "--tokenizer-mode" in extra and "mistral" in extra
        assert "--config-format" in extra and "--load-format" in extra


def test_the_kanana_parser_plugin_path_resolves():
    for config_id in ("kanana-2-inst", "kanana-2-think"):
        cfg = registry.by_id(config_id)
        assert cfg.tool_parser_plugin_path.is_file(), config_id
        args = registry.vllm_args(cfg, require_revision=False)
        assert str(cfg.tool_parser_plugin_path) in args


def test_the_serving_arguments_carry_the_pinned_revision_seed_and_parser():
    cfg = registry.by_id("dragon-llama-fin")
    args = registry.vllm_args(cfg)
    assert "--revision" in args and "--tokenizer-revision" in args
    assert args[args.index("--seed") + 1] == str(registry.SEED)
    assert args[args.index("--tool-call-parser") + 1] == "llama3_json"
    assert args[args.index("--tensor-parallel-size") + 1] == "1"


def test_an_unpinned_revision_refuses_to_serve():
    cfg = registry.by_id("phi-4-mini")
    assert cfg.revision is None
    with pytest.raises(registry.UnpinnedRevision, match="model_revisions"):
        registry.vllm_args(cfg)
    assert registry.vllm_args(cfg, require_revision=False)


def test_every_referenced_chat_template_exists_and_is_hashed():
    hashes = json.loads((registry.TEMPLATE_DIR / "hashes.json").read_text(encoding="utf-8"))
    for cfg in registry.CONFIGS:
        if cfg.chat_template is None:
            continue
        path = cfg.template_path
        assert path.is_file(), cfg.config_id
        digest = registry.template_sha256(path)
        assert digest
        assert not Path(cfg.chat_template).is_absolute(), "template paths stay repo-relative"
        key = cfg.chat_template.replace("kanana_tool_calls/kanana_tool_calls/",
                                        "kanana_tool_calls/")
        assert hashes[key] == digest, cfg.config_id


def test_the_four_gpu_entries_are_the_ones_that_do_not_fit_on_two_cards():
    four = {c.config_id for c in registry.CONFIGS if c.needs_four_gpu_host}
    assert four == {"ax-4.0", "llama-3.3-70b", "xlam-70b",
                    "gpt-oss-120b-t", "gpt-oss-120b-nt"}
    for cfg in registry.CONFIGS:
        assert cfg.tp in (1, 2, 4)
        assert (cfg.tp == 4) == cfg.needs_four_gpu_host
        assert cfg.tp_80g is not None and cfg.tp_80g <= cfg.tp


# ---------------------------------------------------------------------------
# Prompt budget (C2-001)
# ---------------------------------------------------------------------------

def _cases(question: str) -> list[dict]:
    return [{"id": "x", "question": question}]


def test_the_preflight_reports_the_headroom_for_both_arms():
    for lang in ("kr", "en"):
        arm = arms.load_arm(lang)
        budget = preflight.measure(arm=arm, cases=_cases("계좌 프로파일을 보여줘" * 40),
                                   model="mock", revision=None, max_model_len=32768,
                                   max_tokens=16384)
        assert budget.prompt_tokens > 1000
        assert budget.ok, budget.as_dict()
        preflight.check(budget)


def test_the_preflight_refuses_the_context_that_was_registered_for_phi_4_mini():
    arm = arms.load_arm("kr")
    budget = preflight.measure(arm=arm, cases=_cases("계좌 프로파일을 보여줘"),
                               model="mock", revision=None, max_model_len=12288,
                               max_tokens=4096)
    assert not budget.ok
    with pytest.raises(RuntimeError, match="tokens for tool results"):
        preflight.check(budget)


def test_a_tool_result_is_truncated_to_the_same_budget_in_every_arm():
    long_result = json.dumps([{"date": 20240101, "amount": 5000000}] * 4000, ensure_ascii=False)
    sent, cut = preflight.truncate(long_result)
    assert cut
    assert preflight.estimate_tokens(sent) <= preflight.TOOL_RESULT_TOKENS
    assert "truncated by the benchmark runner" in sent
    short, cut = preflight.truncate('{"total_count": 3}')
    assert not cut and short == '{"total_count": 3}'


def test_every_configuration_clears_the_preflight_on_the_korean_arm():
    arm = arms.load_arm("kr")
    cases = _cases("계좌 9000000000000002 의 최근 6개월 거래를 모두 조회하고 위험도를 평가해줘" * 6)
    for cfg in registry.CONFIGS:
        budget = preflight.measure(arm=arm, cases=cases, model=cfg.model, revision=cfg.revision,
                                   max_model_len=cfg.max_model_len, max_tokens=cfg.max_tokens)
        assert budget.ok, f"{cfg.config_id}: {budget.as_dict()}"
