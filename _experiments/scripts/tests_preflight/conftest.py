"""Fixtures for the pre-flight tests: a tiny two-language benchmark on disk."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _case(case_id: str, question: str, tool: str | None, **extra) -> dict:
    expected = {"primary_tool": tool or "", "tools_must_include": [tool] if tool else []}
    expected.update(extra.pop("expected", {}))
    return {"id": case_id, "question": question, "expected": expected,
            "difficulty": "easy", "note": "", **extra}


def _scenario(scenario_id: str, turns: list[str]) -> dict:
    return {"id": scenario_id, "scenario": "s", "sub_category": "base", "fraud_type": 1,
            "fraud_type_name": "sudden", "turns": [
                {"turn": i + 1, "content": text,
                 "tool_calls": [{"name": "get_statistics", "arguments": {}}],
                 "tool_result": {"total_count": 1}}
                for i, text in enumerate(turns)]}


def write_benchmark(root: Path, *, kr_cases, en_cases, kr_scenarios, en_scenarios) -> None:
    for name, payload in (("benchmarks", kr_cases), ("benchmarks_en", en_cases)):
        directory = root / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "cases_demo.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    for name, payload in (("benchmarks_multiturn", kr_scenarios),
                          ("benchmarks_multiturn_en", en_scenarios)):
        directory = root / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "cases_str_workflow.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def benchmark(tmp_path):
    """A four-directory benchmark that passes every structural check."""
    cases = [_case("st_a_001", "첫 번째 질문", "get_statistics"),
             _case("st_a_002", "두 번째 질문", "query_transactions")]
    english = [_case("st_a_001", "the first question", "get_statistics"),
               _case("st_a_002", "the second question", "query_transactions")]
    scenarios = [_scenario("mt_str_001", ["첫 턴", "둘째 턴"])]
    english_scenarios = [_scenario("mt_str_001", ["first turn", "second turn"])]
    write_benchmark(tmp_path, kr_cases=cases, en_cases=english,
                    kr_scenarios=scenarios, en_scenarios=english_scenarios)
    return tmp_path


@pytest.fixture
def case_factory():
    return _case


@pytest.fixture
def scenario_factory():
    return _scenario
