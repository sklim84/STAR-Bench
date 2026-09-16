"""The repaired chat templates render the history the model is trained on."""

from __future__ import annotations

import json

import pytest

from _experiments.scripts.runner import registry

jinja2 = pytest.importorskip("jinja2")


@pytest.fixture(scope="module")
def env():
    from jinja2.sandbox import ImmutableSandboxedEnvironment

    environment = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)
    environment.policies["json.dumps_kwargs"] = {"ensure_ascii": False}

    def raise_exception(message):
        raise RuntimeError(message)

    environment.globals["raise_exception"] = raise_exception
    return environment


TOOLS = [{"type": "function", "function": {
    "name": "query_transactions", "description": "d",
    "parameters": {"type": "object", "properties": {"sql": {"type": "string"}},
                   "required": ["sql"]}}}]

HISTORY = [
    {"role": "system", "content": "SYSTEM"},
    {"role": "user", "content": "질문"},
    {"role": "assistant", "content": "먼저 조회합니다", "tool_calls": [
        {"id": "a", "type": "function",
         "function": {"name": "query_transactions", "arguments": '{"sql": "SELECT 1"}'}},
        {"id": "b", "type": "function",
         "function": {"name": "get_statistics", "arguments": "{}"}}]},
    {"role": "tool", "tool_call_id": "a", "content": '[{"date": 20241015, "amount": 5}]'},
    {"role": "tool", "tool_call_id": "b", "content": '{"total_count": 3}'},
]


def _render(env, name: str) -> str:
    template = env.from_string((registry.TEMPLATE_DIR / name).read_text(encoding="utf-8"))
    return template.render(messages=list(HISTORY), tools=TOOLS, add_generation_prompt=True,
                           bos_token="<|begin_of_text|>")


def test_the_llama_template_does_not_double_encode_a_tool_result(env):
    out = _render(env, "llama3_tools.jinja")
    assert '[{"date": 20241015, "amount": 5}]' in out
    assert '\\"date\\"' not in out


def test_the_llama_template_takes_parallel_calls_without_raising(env):
    out = _render(env, "llama3_tools.jinja")
    assert out.count("<|start_header_id|>assistant<|end_header_id|>") >= 3
    assert "query_transactions" in out and "get_statistics" in out


def test_the_llama_template_keeps_the_assistant_text(env):
    assert "먼저 조회합니다" in _render(env, "llama3_tools.jinja")


def test_the_phi4_template_renders_a_tool_result_at_all(env):
    out = _render(env, "phi4_mini_tools.jinja")
    assert '{"result": [{"date": 20241015, "amount": 5}]}' in out


def test_the_phi4_template_renders_history_calls_in_the_format_it_demands(env):
    out = _render(env, "phi4_mini_tools.jinja")
    assert "functools[" in out
    assert '{"name": "query_transactions", "arguments": {"sql": "SELECT 1"}}' in out
    assert "'sql':" not in out, "arguments must not be a Python dict repr"


def test_the_phi4_template_keeps_the_assistant_text(env):
    assert "먼저 조회합니다" in _render(env, "phi4_mini_tools.jinja")


def test_the_hashes_file_matches_the_files(env):
    hashes = json.loads((registry.TEMPLATE_DIR / "hashes.json").read_text(encoding="utf-8"))
    for name in ("llama3_tools.jinja", "phi4_mini_tools.jinja"):
        assert hashes[name] == registry.template_sha256(registry.TEMPLATE_DIR / name)
