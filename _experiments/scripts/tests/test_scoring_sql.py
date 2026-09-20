"""SQL predicate matching: conditions must actually restrict the query."""

from __future__ import annotations

import json

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


# ---------------------------------------------------------------------------
# Subqueries in the WHERE clause
#
# The fallback used to skip any clause whose text contained SELECT, so
# st_qt_025 and st_qt_039 - both `... WHERE col = v AND amount >= (SELECT ...)`
# - lost the predicate beside the subquery and failed their own gold self-test
# in a sqlglot-less environment, while passing everywhere else.
# ---------------------------------------------------------------------------

ST_QT_025 = ("SELECT date, sender_bank, receiver_bank, amount FROM hofinet "
             "WHERE fraud_type = 5 AND amount >= "
             "(SELECT AVG(amount) FROM hofinet WHERE fraud_type = 5) "
             "ORDER BY amount DESC LIMIT 100")
ST_QT_039 = ("SELECT COUNT(*) AS fraud_count FROM hofinet WHERE sender_bank = 134 "
             "AND date BETWEEN 20230101 AND 20230630 AND is_fraud = 1 AND amount >= "
             "(SELECT AVG(amount) FROM hofinet WHERE sender_bank = 134 "
             "AND date BETWEEN 20230101 AND 20230630 AND is_fraud = 1)")


def test_a_predicate_beside_a_scalar_subquery_is_read(parser):
    assert passes(ST_QT_025, [{"column": "fraud_type", "op": "=", "value": 5}])
    assert passes(ST_QT_039, [{"column": "sender_bank", "op": "=", "value": 134},
                              {"column": "is_fraud", "op": "=", "value": 1},
                              {"column": "date", "op": "BETWEEN",
                               "value": [20230101, 20230630]}])


def test_a_predicate_the_subquery_alone_carries_does_not_satisfy_the_outer_query(parser):
    sql = ("SELECT * FROM hofinet WHERE amount >= "
           "(SELECT AVG(amount) FROM hofinet WHERE fraud_type = 4) AND sender_bank = 1")
    assert passes(sql, [{"column": "sender_bank", "op": "=", "value": 1}])
    # fraud_type = 4 restricts the subquery, and sqlglot reads subquery clauses
    # too, so both parsers must agree on whether it counts.
    assert extract_atoms(sql)[0].count(("fraud_type", "=", 4)) == 1


def test_an_or_inside_a_subquery_does_not_silence_the_outer_clause(parser):
    sql = ("SELECT * FROM hofinet WHERE fraud_type = 4 AND amount > "
           "(SELECT AVG(amount) FROM hofinet WHERE sender_bank = 1 OR sender_bank = 2)")
    assert passes(sql)


def test_a_clause_end_keyword_inside_a_subquery_does_not_end_the_outer_clause(parser):
    sql = ("SELECT * FROM hofinet WHERE fraud_type = 4 AND sender_acc IN "
           "(SELECT sender_acc FROM hofinet GROUP BY sender_acc HAVING COUNT(*) > 3) "
           "AND time_slot = 21")
    atoms, _ = extract_atoms(sql)
    assert ("fraud_type", "=", 4) in atoms and ("time_slot", "=", 21) in atoms


def test_a_predicate_under_a_top_level_or_still_does_not_count_with_a_subquery(parser):
    sql = ("SELECT * FROM hofinet WHERE fraud_type = 4 OR amount > "
           "(SELECT AVG(amount) FROM hofinet)")
    assert not passes(sql)


def test_a_parenthesised_or_group_does_not_hide_its_and_siblings(parser):
    sql = "SELECT * FROM hofinet WHERE (time_slot = 1 OR time_slot = 2) AND fraud_type = 4"
    assert passes(sql)


def test_a_cast_column_is_the_column_for_both_parsers(parser):
    """`CAST(col AS INTEGER) = 4` restricts the query whichever parser reads it."""
    assert passes("SELECT * FROM hofinet WHERE CAST(fraud_type AS INTEGER) = 4")
    assert passes("SELECT * FROM hofinet WHERE fraud_type::INTEGER = 4")
    assert passes("SELECT * FROM hofinet WHERE CAST(fraud_type AS INTEGER) = CAST('4' AS INTEGER)")
    assert not passes("SELECT * FROM hofinet WHERE CAST(fraud_type AS INTEGER) = 7")


def test_a_cast_inside_a_string_literal_is_left_alone(parser):
    assert passes("SELECT * FROM hofinet WHERE fraud_description = 'CAST(x AS y)' "
                  "AND fraud_type = 4")
    assert passes("SELECT * FROM hofinet WHERE fraud_description = 'CAST(x AS y)'",
                  [{"column": "fraud_description", "op": "=", "value": "CAST(x AS y)"}])


def test_a_where_inside_a_string_literal_is_not_a_clause(parser):
    assert not passes("SELECT 'WHERE fraud_type = 4' AS note FROM hofinet")


# ---------------------------------------------------------------------------
# A check that fails because sqlglot is absent says so
# ---------------------------------------------------------------------------

def test_the_fallback_reports_the_terms_it_could_not_read():
    """A gold self-test must never differ by environment without saying so."""
    sql_module_sqlglot = sql_module.sqlglot
    try:
        sql_module.sqlglot = None
        result = check_sql_conditions(
            "SELECT * FROM hofinet WHERE date_trunc('month', ts) = '2024-01-01' "
            "AND fraud_type = 4", [{"column": "fraud_type", "op": "=", "value": 4},
                                   {"column": "ts", "op": "=", "value": "2024-01-01"}])
        assert not result["passed"]
        assert result["parser"] == "fallback"
        assert result["unreadable"], "the unreadable term is reported"
        assert "could not read" in result["reason"] and "install sqlglot" in result["reason"]
    finally:
        sql_module.sqlglot = sql_module_sqlglot


def test_a_readable_statement_reports_no_gap(parser):
    from _experiments.scripts.scoring.sql import extract_atoms_detailed

    atoms, name, unreadable = extract_atoms_detailed(
        "SELECT * FROM hofinet WHERE fraud_type = 4 AND amount BETWEEN 1 AND 2")
    assert name == parser and unreadable == []
    assert len(atoms) == 2
    assert "unreadable" not in check_sql_conditions(
        "SELECT * FROM hofinet WHERE fraud_type = 4", FRAUD4)


def test_both_parsers_read_the_same_atoms_from_statements_with_subqueries():
    pytest.importorskip("sqlglot")
    statements = [
        ST_QT_025,
        ST_QT_039,
        "SELECT * FROM hofinet WHERE fraud_type = 4 AND amount > (SELECT AVG(amount) FROM hofinet)",
        "SELECT * FROM (SELECT * FROM hofinet WHERE fraud_type = 4) t WHERE t.amount >= 10",
        "WITH per_bank AS (SELECT sender_bank, COUNT(*) AS n FROM hofinet WHERE is_fraud = 1 "
        "GROUP BY sender_bank) SELECT * FROM per_bank WHERE n > 5",
        "SELECT * FROM hofinet WHERE sender_acc IN (SELECT sender_acc FROM hofinet "
        "WHERE fraud_type = 7) AND time_slot = 21",
        "SELECT * FROM hofinet WHERE fraud_type = 4 AND amount > (SELECT AVG(amount) "
        "FROM hofinet WHERE sender_bank = 1 OR sender_bank = 2)",
        "SELECT sender_acc, COUNT(*) FROM hofinet WHERE fraud_type = 4 GROUP BY sender_acc "
        "HAVING COUNT(*) >= 3",
        "SELECT * FROM hofinet WHERE CAST(fraud_type AS INTEGER) = 4 AND amount::BIGINT >= 10",
        "SELECT * FROM hofinet WHERE fraud_description = 'CAST(x AS y)' AND fraud_type = 4",
    ]
    with_sqlglot = [extract_atoms(s)[0] for s in statements]
    saved = sql_module.sqlglot
    try:
        sql_module.sqlglot = None
        without = [extract_atoms(s)[0] for s in statements]
    finally:
        sql_module.sqlglot = saved
    for statement, a, b in zip(statements, with_sqlglot, without):
        assert sorted(map(str, a)) == sorted(map(str, b)), statement


def test_both_parsers_read_every_reference_statement_of_the_benchmark_the_same_way():
    """The measurement that found the defect, as a test: all four directories."""
    pytest.importorskip("sqlglot")
    import glob
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    statements = []
    for name in ("benchmarks", "benchmarks_en"):
        for path in sorted(glob.glob(str(root / name / "cases_*.json"))):
            for case in json.loads(Path(path).read_text(encoding="utf-8")):
                for ref in ((case.get("expected") or {}).get("reference_calls") or {}).values():
                    statement = ref.get("sql") or ref.get("reference_sql")
                    if statement:
                        statements.append((case["id"], statement))
    assert len(statements) > 50, "the benchmark should carry reference SQL"
    saved = sql_module.sqlglot
    try:
        for case_id, statement in statements:
            sql_module.sqlglot = saved
            a = sorted(map(str, extract_atoms(statement)[0]))
            sql_module.sqlglot = None
            b = sorted(map(str, extract_atoms(statement)[0]))
            assert a == b, case_id
    finally:
        sql_module.sqlglot = saved
