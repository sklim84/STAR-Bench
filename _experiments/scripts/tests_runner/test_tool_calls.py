"""Parallel-call serialisation and the fallback parser."""

from __future__ import annotations

import json

import pytest

from _experiments.scripts import benchmark
from _experiments.scripts.runner import records, registry
from _experiments.scripts.runner.client import (ChatOptions, ModelClient, fallback_call_id,
                                                parse_fallback_calls, strip_reasoning_markup)
from _experiments.scripts.tests_runner.conftest import base_argv
from _experiments.scripts.tests_runner.mock_server import raw_content, text, tool_call


def _run(server, bench, out, executor, extra=()):
    argv = base_argv(server, out) + ["--cases-dir", str(bench)] + list(extra)
    benchmark.main(argv, executor=executor)
    return [rec for f in sorted(out.glob("*.jsonl")) for rec in records.read_records(f)]


# ---------------------------------------------------------------------------
# Parallel calls
# ---------------------------------------------------------------------------

def _client(serialize: bool) -> ModelClient:
    return ModelClient(object(), ChatOptions(model="m", serialize_parallel_calls=serialize))


def test_parallel_calls_become_consecutive_single_call_turns():
    client = _client(True)
    calls = parse_fallback_calls(
        '<tool_call>{"name": "a", "arguments": {}}</tool_call>'
        '<tool_call>{"name": "b", "arguments": {}}</tool_call>', 0)
    message = client.assistant_message("thinking out loud", None, calls)
    turns = client.history_turns(message, calls, {c.id: f"result-{c.name}" for c in calls})

    assert [t["role"] for t in turns] == ["assistant", "tool", "assistant", "tool"]
    assert all(len(t["tool_calls"]) == 1 for t in turns if t["role"] == "assistant")
    assert turns[0]["content"] == "thinking out loud"
    assert turns[1]["content"] == "result-a"
    assert turns[3]["content"] == "result-b"


def test_a_template_that_takes_parallel_calls_keeps_one_assistant_turn():
    client = _client(False)
    calls = parse_fallback_calls(
        '<tool_call>{"name": "a", "arguments": {}}</tool_call>'
        '<tool_call>{"name": "b", "arguments": {}}</tool_call>', 0)
    turns = client.history_turns(client.assistant_message("", None, calls), calls,
                                 {c.id: "r" for c in calls})
    assert [t["role"] for t in turns] == ["assistant", "tool", "tool"]
    assert len(turns[0]["tool_calls"]) == 2


def test_every_llama_configuration_serialises():
    llama = [c for c in registry.CONFIGS if c.parser == "llama3_json"]
    assert llama
    assert all(c.serialize_parallel_calls for c in llama)


def test_both_parallel_calls_are_executed_and_recorded(server, single_benchmark, tmp_path,
                                                       fake_tools):
    server.push(tool_call(("get_statistics", {}), ("get_account_profile", {"account_id": 1})),
                text("끝"))
    server.always(text("끝"))
    recs = {r["case_id"]: r for r in _run(server, single_benchmark, tmp_path / "r", fake_tools)}
    first = recs["st_001"]["rounds"][0]
    assert [c["name"] for c in first["tool_calls"]] == ["get_statistics", "get_account_profile"]
    assert len(first["executed"]) == 2
    assert [name for name, _ in fake_tools.calls] == ["get_statistics", "get_account_profile"]


# ---------------------------------------------------------------------------
# Fallback parser
# ---------------------------------------------------------------------------

def test_reasoning_is_stripped_before_anything_is_read_as_a_call():
    text_with_plan = ('<think>I could call {"name": "generate_str", "arguments": {}} here</think>'
                      '<tool_call>{"name": "get_statistics", "arguments": {}}</tool_call>')
    assert "generate_str" not in strip_reasoning_markup(text_with_plan)
    calls = parse_fallback_calls(text_with_plan, 0)
    assert [c.name for c in calls] == ["get_statistics"]


def test_an_unclosed_reasoning_block_is_stripped_to_the_end():
    assert parse_fallback_calls('<think>{"name": "a", "arguments": {}}', 0) == []


def test_a_json_object_in_prose_is_not_a_call():
    assert parse_fallback_calls('I will use {"name": "get_statistics", "arguments": {}} next.',
                                0) == []


@pytest.mark.parametrize("payload,expected", [
    ('<tool_call>{"name": "a", "arguments": {"x": 1}}</tool_call>', [("a", {"x": 1})]),
    ('[TOOL_CALLS] [{"name": "a", "arguments": {}}, {"name": "b", "arguments": {}}]',
     [("a", {}), ("b", {})]),
    ('functools[{"name": "a", "arguments": {"x": 1}}]', [("a", {"x": 1})]),
    ('<|python_tag|>{"name": "a", "parameters": {"x": 1}}', [("a", {"x": 1})]),
    ('<function=a>{"x": 1}</function>', [("a", {"x": 1})]),
])
def test_every_explicit_marker_is_read(payload, expected):
    calls = parse_fallback_calls(payload, 0)
    assert [(c.name, c.arguments) for c in calls] == expected


def test_all_calls_are_returned_not_just_the_first():
    calls = parse_fallback_calls(
        '<tool_call>{"name": "a", "arguments": {}}</tool_call>'
        '<tool_call>{"name": "b", "arguments": {}}</tool_call>'
        '<tool_call>{"name": "c", "arguments": {}}</tool_call>', 0)
    assert [c.name for c in calls] == ["a", "b", "c"]


def test_a_fallback_call_id_is_nine_alphanumeric_characters():
    # Mistral validates tool_call_id against ^[a-zA-Z0-9]{9}$; `fallback_000` broke it.
    for round_idx in range(6):
        for i in range(10):
            call_id = fallback_call_id(round_idx, i)
            assert len(call_id) == 9 and call_id.isalnum()


def test_a_fallback_call_is_marked_and_keeps_its_raw_text(server, single_benchmark, tmp_path,
                                                          fake_tools):
    server.push(raw_content('<tool_call>{"name": "get_statistics", "arguments": {"a": 1}}'
                            '</tool_call>'), text("끝"))
    server.always(text("끝"))
    recs = {r["case_id"]: r for r in _run(server, single_benchmark, tmp_path / "r", fake_tools)}
    call = recs["st_001"]["rounds"][0]["tool_calls"][0]
    assert call["source"] == "fallback"
    assert call["name"] == "get_statistics"
    assert json.loads(call["arguments_raw"]) == {"a": 1}
    assert call["id"].isalnum() and len(call["id"]) == 9


def test_a_native_call_is_marked_native(server, single_benchmark, tmp_path, fake_tools):
    server.push(tool_call("get_statistics", {}), text("끝"))
    server.always(text("끝"))
    recs = {r["case_id"]: r for r in _run(server, single_benchmark, tmp_path / "r", fake_tools)}
    assert recs["st_001"]["rounds"][0]["tool_calls"][0]["source"] == "native"


def test_the_tool_name_is_recorded_as_the_server_sent_it(server, single_benchmark, tmp_path,
                                                         fake_tools):
    # The scorer strips serving artefacts and reports them; the runner must not.
    server.push(tool_call("get_statistics<|channel|>commentary", {}), text("끝"))
    server.always(text("끝"))
    recs = {r["case_id"]: r for r in _run(server, single_benchmark, tmp_path / "r", fake_tools)}
    assert recs["st_001"]["rounds"][0]["tool_calls"][0]["name"] == \
        "get_statistics<|channel|>commentary"
