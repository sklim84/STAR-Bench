"""Which cause an executed tool error is attributed to.

A call is attributed to exactly one cause, by the first rule that matches its
message, so a generic rule placed above a specific one takes its hits. That is
what happened to `platform_model_artifact`: the tool layer wraps most of its own
defects in "An unexpected error occurred during tool execution: ...", and the
rule matching that wrapper sat above the rule naming the model-artifact keys, so
142 `'predict_prob'` and 4 `__round__` messages were counted as generic.
Both causes are in the platform family, so the 863 / 281 / 180 split did not
move, but the cause table a caption quotes did.
"""

from __future__ import annotations

import json

import pytest

from _experiments.scripts.e2e_error_rates import RULES, classify, family_of

# One real message per cause, taken from the 5,550 executed calls of the
# end-to-end run. Each must be attributed to the cause it came from.
MESSAGES = {
    "graph_backend_absent": "Unable to find shortest path as Memgraph is not running.",
    "platform_nan": "Account profile retrieval error: cannot convert float NaN to integer",
    "platform_model_artifact":
        "An unexpected error occurred during tool execution: 'predict_prob'",
    "platform_key_error":
        "An unexpected error occurred during tool execution: 'str' object has no attribute 'get'",
    "entity_absent": "No transaction history for this account.",
    "model_unknown_tool": "Unknown tool: get_cross_institution_flow",
    "model_missing_argument": "Summary content for STR generation is empty.",
    "model_bad_argument": "Input parameter error",
    "model_bad_sql": "Query execution error: Conversion Error: Could not convert string "
                     "'2023-01-01' to INT32",
}


def _classify(message: str):
    return classify(json.dumps({"error": message}, ensure_ascii=False))


@pytest.mark.parametrize("cause,message", sorted(MESSAGES.items()))
def test_every_cause_wins_its_own_message(cause, message):
    """No rule is shadowed by one above it on the message it exists for."""
    status, found, _text = _classify(message)
    assert (status, found) == ("error", cause)


def test_the_model_artifact_keys_are_not_counted_as_the_generic_wrapper():
    for key in ("'predict_prob'", "__round__", "feature_names mismatch"):
        _status, cause, _text = _classify(
            f"An unexpected error occurred during tool execution: {key}")
        assert cause == "platform_model_artifact", key


def test_the_generic_wrapper_still_catches_what_no_rule_names():
    _status, cause, _text = _classify(
        "An unexpected error occurred during tool execution: 'NoneType' object is not iterable")
    assert cause == "platform_key_error"


def test_every_rule_has_a_family_and_an_unknown_cause_is_unattributed():
    assert {family_of(name) for name, _f, _p in RULES} <= {"platform", "data", "model"}
    assert family_of("something_new") == "unattributed"


def test_an_empty_result_is_not_an_error():
    assert classify(json.dumps({"total_count": 0, "result": []}))[:2] == ("empty", "no_rows")
    assert classify(json.dumps({"total_count": 2, "result": [{"a": 1}]}))[:2] == ("ok", "")
