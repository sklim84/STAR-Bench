"""Fixtures for the runner tests: a mock server, a fake tool layer, tiny benchmarks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from _experiments.scripts.tests_runner.mock_server import MockOpenAIServer  # noqa: E402


@pytest.fixture
def server():
    with MockOpenAIServer() as mock:
        yield mock


@pytest.fixture
def fake_tools():
    """A tool layer that records what it was asked and answers deterministically."""
    calls: list[tuple[str, dict]] = []

    def execute(name: str, arguments: dict) -> str:
        calls.append((name, dict(arguments)))
        if name == "explodes":
            raise RuntimeError("tool blew up")
        return json.dumps({"tool": name, "arguments": arguments,
                           "total_count": 1, "result": [{"ok": True}]}, ensure_ascii=False)

    execute.calls = calls
    return execute


SINGLE_CASES = [
    {"id": "st_001", "question": "지난달 이상거래 건수를 알려줘",
     "expected": {"tools_must_include": ["get_statistics"]}},
    {"id": "st_002", "question": "계좌 9000000000000002 프로파일을 보여줘",
     "expected": {"tools_must_include": ["get_account_profile"]}},
    {"id": "st_003", "question": "자금세탁이 무엇인지 설명해줘", "expected": {}},
]

SCENARIOS = [
    {"id": "mt_001", "scenario": "STR workflow", "sub_category": "str",
     "turns": [
         # As the rebuilt data has it: the arguments hold the CHECKS and the
         # executable query is the reference.
         {"turn": 1, "content": "이 계좌의 최근 거래를 조회해줘",
          "tool_calls": [{"name": "query_transactions",
                          "arguments": {"sql_conditions": [{"column": "sender_acc", "op": "=",
                                                            "value": 9000000000000002}],
                                        "sql_valid": True},
                          "reference_sql": "SELECT amount FROM hofinet "
                                           "WHERE sender_acc = 9000000000000002"}],
          "tool_result": {"total_count": 2, "result": [{"amount": 5000000}]}},
         {"turn": 2, "content": "그 계좌의 위험도를 평가해줘",
          "tool_calls": [{"name": "score_account_risk",
                          "arguments": {"account_id": 9000000000000002}}],
          "tool_result": {"risk_score": 71}},
         {"turn": 3, "content": "어떤 계좌를 말하는 거야?", "note": "되묻기"},
     ]},
]


@pytest.fixture
def single_benchmark(tmp_path) -> Path:
    path = tmp_path / "benchmarks"
    path.mkdir()
    # One file, so the case order is the list order and a scripted response lands
    # on the case the test means.
    (path / "cases_multi_tool.json").write_text(
        json.dumps(SINGLE_CASES, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def split_benchmark(tmp_path) -> Path:
    """The same cases spread over two files, to check they are all collected."""
    path = tmp_path / "benchmarks_split"
    path.mkdir()
    (path / "cases_get_account_profile.json").write_text(
        json.dumps(SINGLE_CASES[1:], ensure_ascii=False), encoding="utf-8")
    (path / "cases_get_statistics.json").write_text(
        json.dumps(SINGLE_CASES[:1], ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def multiturn_benchmark(tmp_path) -> Path:
    path = tmp_path / "benchmarks_multiturn"
    path.mkdir()
    (path / "cases_str_workflow.json").write_text(
        json.dumps(SCENARIOS, ensure_ascii=False), encoding="utf-8")
    return path


def base_argv(server, out: Path, *, tools_lang: str = "kr", concurrency: int = 1) -> list[str]:
    """The options every runner test passes: mock endpoint, no environment pins.

    Concurrency is pinned to 1 here so a scripted response queue lands on the case
    the test means; the parallel behaviour has its own tests.
    """
    return ["--model", "mock-model", "--tools-lang", tools_lang,
            "--base-url", server.url, "--out", str(out),
            "--max-model-len", "32768", "--max-tokens", "1024",
            "--no-env-check", "--max-retries", "0", "--concurrency", str(concurrency)]
