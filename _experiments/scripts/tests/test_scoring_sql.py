"""SQL predicate matching (L4-015): conditions must actually restrict the query."""

from __future__ import annotations

import pytest

from _experiments.scripts.scoring import sql as sql_module
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


# ---------------------------------------------------------------------------
# IN, NOT IN and BETWEEN, with and without sqlglot
#
# Without sqlglot the fallback used to strip the closing parenthesis off the
# whole WHERE clause (`body.strip().strip("()")`), so `fraud_type IN (1, 2)`
# never matched an IN condition and st_qt_013 and st_qt_037 failed their own
# gold self-test. The two parsers must read these three operators the same way.
# ---------------------------------------------------------------------------

@pytest.fixture(params=["sqlglot", "fallback"])
def parser(request, monkeypatch):
    if request.param == "fallback":
        monkeypatch.setattr(sql_module, "sqlglot", None)
    else:
        pytest.importorskip("sqlglot")
    return request.param


def test_the_parser_is_the_one_the_fixture_asked_for(parser):
    assert extract_atoms("SELECT * FROM hofinet WHERE fraud_type = 4")[1] == parser


def test_an_in_list_matches_an_in_condition(parser):
    cond = [{"column": "fraud_type", "op": "IN", "value": [1, 2, 3]}]
    assert passes("SELECT * FROM hofinet WHERE fraud_type IN (1, 2, 3)", cond)
    assert passes("SELECT * FROM hofinet WHERE fraud_type IN (3,2,1) AND amount > 5", cond)
    assert not passes("SELECT * FROM hofinet WHERE fraud_type IN (1, 2)", cond)


def test_an_in_list_of_strings_matches(parser):
    cond = [{"column": "fund_type", "op": "IN", "value": ["a", "b"]}]
    assert passes("SELECT * FROM hofinet WHERE fund_type IN ('a', 'b')", cond)


def test_an_in_list_next_to_another_condition_leaves_it_readable(parser):
    atoms, _ = extract_atoms(
        "SELECT * FROM hofinet WHERE fraud_type IN (1, 2) AND time_slot = 21")
    assert ("fraud_type", "IN", [1, 2]) in atoms
    assert ("time_slot", "=", 21) in atoms


def test_not_in_never_satisfies_an_in_condition(parser):
    cond = [{"column": "fraud_type", "op": "IN", "value": [1, 2]}]
    assert not passes("SELECT * FROM hofinet WHERE fraud_type NOT IN (1, 2)", cond)
    assert not passes("SELECT * FROM hofinet WHERE fraud_type NOT IN (1, 2) AND amount > 5", cond)


def test_not_in_does_not_hide_the_conditions_beside_it(parser):
    atoms, _ = extract_atoms(
        "SELECT * FROM hofinet WHERE fraud_type NOT IN (1, 2) AND time_slot = 21")
    assert ("time_slot", "=", 21) in atoms
    assert not any(a[0] == "fraud_type" for a in atoms)


def test_between_matches_a_between_condition(parser):
    cond = [{"column": "date", "op": "BETWEEN", "value": [20240101, 20241231]}]
    assert passes("SELECT * FROM hofinet WHERE date BETWEEN 20240101 AND 20241231", cond)
    assert passes("SELECT * FROM hofinet WHERE date BETWEEN 20240101 AND 20241231 "
                  "AND fraud_type = 4", cond)
    assert not passes("SELECT * FROM hofinet WHERE date BETWEEN 20240102 AND 20241231", cond)


def test_between_on_strings_and_beside_an_in_list(parser):
    conds = [{"column": "date", "op": "BETWEEN", "value": ["20240101", "20241231"]},
             {"column": "media_type", "op": "IN", "value": [1, 2]}]
    assert passes("SELECT * FROM hofinet WHERE date BETWEEN '20240101' AND '20241231' "
                  "AND media_type IN (1, 2)", conds)


def test_not_between_never_satisfies_a_between_condition(parser):
    cond = [{"column": "amount", "op": "BETWEEN", "value": [100, 200]}]
    assert not passes("SELECT * FROM hofinet WHERE amount NOT BETWEEN 100 AND 200", cond)


def test_a_predicate_under_or_still_does_not_count(parser):
    cond = [{"column": "fraud_type", "op": "IN", "value": [1, 2]}]
    assert not passes("SELECT * FROM hofinet WHERE fraud_type IN (1, 2) OR amount > 0", cond)


def test_both_parsers_read_the_same_atoms_from_the_same_statements():
    pytest.importorskip("sqlglot")
    statements = [
        "SELECT * FROM hofinet WHERE fraud_type IN (1, 2, 3) AND amount >= 5",
        "SELECT * FROM hofinet WHERE fraud_type NOT IN (1, 2) AND amount >= 5",
        "SELECT * FROM hofinet WHERE amount BETWEEN 100 AND 200 AND fraud_type = 7",
        "SELECT * FROM hofinet WHERE (date = 20240101 AND time_slot = 21) "
        "AND media_type IN ('a', 'b')",
        "SELECT * FROM hofinet WHERE NOT fraud_type = 4 AND amount <= 10",
        "SELECT * FROM hofinet WHERE sender_acc IS NOT NULL AND fraud_type = 4",
        "SELECT * FROM hofinet WHERE fraud_description LIKE '%night%' AND 5 < amount",
    ]
    with_sqlglot = [extract_atoms(s)[0] for s in statements]
    saved = sql_module.sqlglot
    try:
        sql_module.sqlglot = None
        without = [extract_atoms(s)[0] for s in statements]
    finally:
        sql_module.sqlglot = saved
    for statement, a, b in zip(statements, with_sqlglot, without):
        assert a == b, statement
