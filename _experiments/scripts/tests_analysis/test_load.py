"""The analysis reader returns the fixed metrics and nothing invented."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from _experiments.scripts.analysis import load  # noqa: E402
from _experiments.scripts.runner import registry  # noqa: E402

pytestmark = pytest.mark.skipif(not load.DEFAULT_EVAL_ROOT.is_dir(),
                                reason="no scored runs in this checkout")


@pytest.fixture(scope="module")
def cases():
    return load.single()


def test_the_pre_audit_keys_are_not_resurrected(cases):
    """removed these names with their definitions; a column of the same name
    over the new numbers would bring the definitions back."""
    gone = {"primary_tool_hit", "tool_recall", "tool_precision", "param_accuracy",
            "param_key_accuracy", "order_score", "score"}
    assert gone.isdisjoint(cases.columns)


def test_every_scored_configuration_is_in_the_registry(cases):
    known = {cfg.config_id for cfg in registry.CONFIGS}
    assert set(cases["config_id"]) <= known


def test_one_row_per_case_per_configuration(cases):
    counts = cases.groupby("config_id")["case_id"].agg(["size", "nunique"])
    assert (counts["size"] == counts["nunique"]).all()
    assert counts["size"].nunique() == 1, "the columns hold different case counts"


def test_a_is_missing_rather_than_one_where_there_is_nothing_to_check(cases):
    """`a` used to be 1.0 for a case with no parameter checks, which flattered
    every model that called the right tool with no arguments."""
    no_checks = cases[cases["n_checks"] == 0]
    assert len(no_checks) > 0
    assert no_checks["a"].isna().all()


def test_the_scenario_and_turn_tables_agree(_setting="oracle"):
    scenarios, turns = load.multiturn(_setting)
    per_scenario = turns.groupby(["config_id", "scenario_id"]).size()
    declared = scenarios.set_index(["config_id", "scenario_id"])["n_turns"]
    assert (per_scenario == declared.reindex(per_scenario.index)).all()


def test_the_aggregate_matches_a_mean_over_the_rows(cases):
    """A figure may take either, so the two have to be the same number."""
    scored = load.aggregates("single")
    for config_id, aggregate in scored.items():
        rows = cases[cases["config_id"] == config_id]
        assert aggregate["h"]["n"] == len(rows)
        assert abs(aggregate["h"]["mean"] - rows["h"].mean()) < 5e-6, config_id
        a_rows = rows["a"].dropna()
        assert aggregate["a"]["n"] == len(a_rows), config_id
        assert abs(aggregate["a"]["mean"] - a_rows.mean()) < 5e-6, config_id


def test_missing_names_the_configurations_still_to_run():
    table = load.missing()
    assert len(table) == len(registry.CONFIGS)
    assert table["single"].sum() == load.single()["config_id"].nunique()
