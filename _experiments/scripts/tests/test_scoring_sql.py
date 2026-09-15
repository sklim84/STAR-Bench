"""SQL predicate matching (L4-015): conditions must actually restrict the query."""

from __future__ import annotations

import pytest

from _experiments.scripts.scoring.sql import check_sql_conditions, extract_atoms

FRAUD4 = [{"column": "fraud_type", "op": "=", "value": 4}]


def passes(sql, conditions=FRAUD4):
    return check_sql_conditions(sql, conditions)["passed"]


@pytest.mark.parametrize("sql", [
    "SELECT * FROM hofinet WHERE fraud_type = 4",
    "SELECT * FROM hofinet WHERE amount > 1000 AND fraud_type = 4",
    "SELECT * FROM hofinet h WHERE h.fraud_type = 4 LIMIT 10",
    "SELECT * FROM hofinet WHERE 4 = fraud_type",
    "SELECT * FROM hofinet WHERE fraud_type IN (4)",
    "SELECT * FROM hofinet WHERE CAST(fraud_type AS INTEGER) = 4",
    "SELECT * FROM hofinet WHERE fraud_type = '4'",
    "SELECT count(*) FROM (SELECT * FROM hofinet WHERE fraud_type = 4) t",
    "select sender_acc, count(*) from hofinet where fraud_type=4 group by sender_acc having count(*) > 3",
])
def test_restricting_predicates_pass(sql):
    assert passes(sql)


@pytest.mark.parametrize("sql", [
    "SELECT * FROM hofinet WHERE date >= 20240101 AND fraud_type = 1 LIMIT 4",
    "SELECT * FROM hofinet WHERE fraud_type = 7",
    "SELECT 4",
    "SELECT * FROM hofinet WHERE fraud_type = 4 OR amount > 0",
    "SELECT * FROM hofinet WHERE NOT fraud_type = 4",
    "SELECT * FROM hofinet WHERE fraud_type <> 4",
    "SELECT * FROM hofinet WHERE fraud_type IN (4, 7)",
    "SELECT '4 fraud_type' AS x",
    "SELECT * FROM hofinet -- fraud_type = 4",
    "SELECT * FROM hofinet WHERE fraud_type = 40",
])
def test_non_restricting_text_fails(sql):
    assert not passes(sql)


def test_every_condition_must_hold():
    conds = [{"column": "fraud_type", "op": "=", "value": 4}, {"column": "time_slot", "op": "=", "value": 21}]
    assert not passes("SELECT * FROM hofinet WHERE fraud_type = 4", conds)
    assert passes("SELECT * FROM hofinet WHERE fraud_type = 4 AND time_slot = 21", conds)


def test_comparison_operators():
    assert passes("SELECT * FROM hofinet WHERE amount >= 10000000", [{"column": "amount", "op": ">=", "value": 10000000}])
    assert not passes("SELECT * FROM hofinet WHERE amount > 10000000", [{"column": "amount", "op": ">=", "value": 10000000}])
    assert passes("SELECT * FROM hofinet WHERE date BETWEEN 20240101 AND 20241231",
                  [{"column": "date", "op": ">=", "value": 20240101}])
    assert passes("SELECT * FROM hofinet WHERE date >= 20240101 AND date <= 20241231",
                  [{"column": "date", "op": "BETWEEN", "value": [20240101, 20241231]}])
    assert passes("SELECT * FROM hofinet WHERE fraud_description LIKE '%night%'",
                  [{"column": "fraud_description", "op": "LIKE", "value": "%night%"}])
    assert passes("SELECT * FROM hofinet WHERE fraud_type IN (4, 7)",
                  [{"column": "fraud_type", "op": "IN", "value": [7, 4]}])


def test_unparsable_sql_falls_back_conservatively():
    atoms, parser = extract_atoms("SELCT * FRM hofinet WHERE fraud_type = 4 AND amount > 5")
    assert parser == "fallback"
    assert ("fraud_type", "=", 4) in atoms
    assert check_sql_conditions("SELCT * FRM hofinet WHERE fraud_type = 4", FRAUD4)["parser"] == "fallback"
    assert not check_sql_conditions("SELCT * FRM hofinet WHERE fraud_type = 4 OR 1 = 1", FRAUD4)["passed"]


def test_missing_or_malformed_sql_fails():
    assert not passes(None)
    assert not passes("")
    assert not check_sql_conditions("SELECT * FROM hofinet WHERE fraud_type = 4", [])["passed"]
