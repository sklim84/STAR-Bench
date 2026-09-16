"""Gate 5 on the real registry, and on registries built to be wrong."""

from __future__ import annotations

import json
from types import SimpleNamespace

from _experiments.scripts.preflight import serving
from _experiments.scripts.preflight.gate import Context
from _experiments.scripts.runner import registry as real_registry


def _fake(*configs):
    return SimpleNamespace(CONFIGS=tuple(configs),
                           REASONING_CONTROLS=real_registry.REASONING_CONTROLS,
                           TEMPLATE_DIR=real_registry.TEMPLATE_DIR,
                           template_sha256=real_registry.template_sha256)


def _cfg(**kwargs):
    base = {"config_id": "demo", "label": "Demo", "model": "vendor/demo", "group": "g",
            "parser": "hermes", "max_model_len": real_registry.CONTEXT,
            "max_tokens": real_registry.BUDGET_PLAIN}
    base.update(kwargs)
    return real_registry.ServingConfig(**base)


def test_the_real_registry_is_complete():
    assert serving._registry_complete(real_registry).ok


def test_the_real_registry_and_the_run_plan_agree():
    plan = json.loads(serving.PLAN_PATH.read_text(encoding="utf-8"))
    check = serving._plan_matches_registry(real_registry, plan)
    assert check.ok, check.detail


def test_a_configuration_missing_from_the_run_plan_is_named():
    plan = json.loads(serving.PLAN_PATH.read_text(encoding="utf-8"))
    plan["configurations"] = plan["configurations"][:-1]
    check = serving._plan_matches_registry(real_registry, plan)
    assert not check.ok
    assert "not in the run plan" in check.detail


def test_the_same_model_in_the_same_mode_twice_is_refused():
    """The 2026 multi-turn (T)/(NT) rows were one configuration run twice (C2-012)."""
    registry = _fake(_cfg(config_id="a"), _cfg(config_id="b"))
    check = serving._registry_complete(registry)
    assert not check.ok
    assert "same model in the same mode" in check.detail


def test_a_context_below_the_agreed_floor_is_refused():
    registry = _fake(_cfg(max_model_len=12288))
    check = serving._registry_complete(registry)
    assert not check.ok
    assert "12288" in check.detail


def test_a_reasoning_configuration_with_a_small_output_budget_is_refused():
    registry = _fake(_cfg(reasoning_mode="always_on", reasoning_parser="deepseek_r1",
                          max_tokens=8192))
    check = serving._registry_complete(registry)
    assert not check.ok
    assert "output budget" in check.detail


def test_a_named_template_that_is_not_in_the_repository_is_refused():
    registry = _fake(_cfg(chat_template="no_such_template.jinja"))
    check = serving._registry_complete(registry)
    assert not check.ok
    assert "not in the repository" in check.detail


def test_every_served_template_hash_is_published():
    check = serving._template_hashes(Context(), real_registry)
    assert check.ok, check.detail


def test_a_configuration_that_fits_no_host_is_named():
    plan = json.loads(serving.PLAN_PATH.read_text(encoding="utf-8"))
    registry = _fake(_cfg(tp=8, needs_four_gpu_host=True))
    check = serving._host_profiles(registry, plan)
    assert not check.ok
    assert "no listed host" in check.detail
