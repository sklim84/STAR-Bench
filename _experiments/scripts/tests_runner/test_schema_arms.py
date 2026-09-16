"""The two schema arms differ in prose and in nothing else (D16, D13, C2-006)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from _experiments.scripts.runner import arms

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS = _ROOT / "_experiments" / "scripts"


@pytest.fixture(scope="module")
def both():
    return arms.load_arm("en"), arms.load_arm("kr")


def test_the_structures_are_identical(both):
    en, kr = both
    problems = arms.parity_problems(en.tools, kr.tools)
    assert problems == [], "\n".join(problems)


def test_the_tool_names_and_their_order_match(both):
    en, kr = both
    assert kr.tool_names == en.tool_names
    assert len(kr.tool_names) == 23


def test_every_description_is_actually_translated(both):
    en, kr = both
    hangul = re.compile(r"[가-힣]")
    for en_tool, kr_tool in zip(en.tools, kr.tools):
        name = en_tool["function"]["name"]
        kr_desc = kr_tool["function"]["description"]
        assert kr_desc != en_tool["function"]["description"], name
        assert hangul.search(kr_desc), f"{name} has no Korean description"


def test_the_korean_arm_uses_the_platform_parameter_names(both):
    en, kr = both
    for en_tool, kr_tool in zip(en.tools, kr.tools):
        en_props = (en_tool["function"].get("parameters") or {}).get("properties") or {}
        kr_props = (kr_tool["function"].get("parameters") or {}).get("properties") or {}
        assert list(en_props) == list(kr_props), en_tool["function"]["name"]


def test_both_prompts_carry_the_same_response_language_rule(both):
    en, kr = both
    assert "language of the user's question" in en.system_prompt
    assert "사용자 질문의 언어로" in kr.system_prompt
    for prompt in (en.system_prompt, kr.system_prompt):
        assert "Respond in English" not in prompt
        assert "한국어로 응답하세요" not in prompt


def test_the_korean_prompt_states_the_real_column_names_and_fraud_labels(both):
    _en, kr = both
    for column in ("date", "time_slot", "sender_bank", "sender_acc", "amount",
                   "is_fraud", "fraud_type", "fraud_description"):
        assert column in kr.system_prompt
    assert "갑작스러운 거래패턴의 변화" in kr.system_prompt
    assert "코드 6은 쓰이지 않습니다" in kr.system_prompt
    # The invented code table (1=자금세탁, 매체 2=ATM, ...) is gone; the only
    # remaining "자금세탁" is the name of the discipline in the first line.
    assert "1=자금세탁" not in kr.system_prompt
    assert "보이스피싱" not in kr.system_prompt
    assert "대포통장" not in kr.system_prompt
    assert "ATM" not in kr.system_prompt


def test_the_korean_query_tool_describes_english_columns(both):
    _en, kr = both
    tool = next(t for t in kr.tools if t["function"]["name"] == "query_transactions")
    text = tool["function"]["description"] + json.dumps(tool["function"]["parameters"],
                                                        ensure_ascii=False)
    assert "sender_acc" in text and "fraud_description" in text
    assert "거래금액 FROM" not in text


def test_the_r003_rule_carries_the_agreed_korean_label(both):
    _en, kr = both
    tool = next(t for t in kr.tools if t["function"]["name"] == "detect_monitoring_alerts")
    description = tool["function"]["description"]
    assert "동일 금액 반복" in description
    assert "정액" not in description and "라운드 금액" not in description


def test_the_fraud_type_enum_dropped_the_unused_code(both):
    en, kr = both
    for arm in (en, kr):
        tool = next(t for t in arm.tools if t["function"]["name"] == "get_fraud_type_summary")
        assert tool["function"]["parameters"]["properties"]["fraud_type"]["enum"] == [1, 2, 3, 4, 5, 7]


def test_tools_en_is_retired():
    from _experiments.scripts import tools_en
    with pytest.raises(AttributeError, match="retired"):
        tools_en.TOOLS_EN
    with pytest.raises(AttributeError, match="retired"):
        tools_en.EN_KO_PARAM_MAP


def test_there_is_no_value_normalisation_map_left():
    source = (_SCRIPTS / "tools_kr.py").read_text(encoding="utf-8")
    assert "KR_TO_EXEC_VALUE" not in source
    assert "KR_TO_EXEC_KEY" not in source
    assert "normalize_args" not in source


def test_the_generated_arm_is_up_to_date():
    out = subprocess.run([sys.executable, "-m", "_experiments.scripts.gen_tools_kr", "--check"],
                         cwd=_ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr or out.stdout
