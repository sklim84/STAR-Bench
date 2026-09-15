"""SQL checks: predicate extraction for ``sql_conditions`` and read-only execution for ``sql_valid``.

Predicates are taken from every WHERE and HAVING clause of the statement
(subqueries and CTEs included), but only along AND-only paths: a comparison
under OR or NOT (other than NOT col = v) does not restrict the result, so it
never satisfies a condition. When sqlglot cannot parse the text, a regex
fallback reads ``col op literal`` terms from the WHERE clause and gives up on any
clause that contains OR or NOT.
"""

from __future__ import annotations

import json
import re
import threading
from typing import Any

try:
    import sqlglot
    from sqlglot import exp
except ImportError:  # pragma: no cover - the fallback still works
    sqlglot = None
    exp = None

SQLGLOT_PIN = "30.18.0"

_FLIP = {">": "<", ">=": "<=", "<": ">", "<=": ">=", "=": "=", "!=": "!="}
_OPS = {"=", "!=", ">", ">=", "<", "<=", "IN", "BETWEEN", "LIKE"}


def sqlglot_version() -> str | None:
    return getattr(sqlglot, "__version__", None) if sqlglot else None


# ---------------------------------------------------------------------------
# Atom extraction
# ---------------------------------------------------------------------------

class _NotLiteral(Exception):
    pass


def _literal(node) -> Any:
    while isinstance(node, (exp.Paren, exp.Cast, exp.TryCast)):
        node = node.this
    if isinstance(node, exp.Neg):
        val = _literal(node.this)
        if isinstance(val, (int, float)):
            return -val
        raise _NotLiteral
    if isinstance(node, exp.Literal):
        if node.is_string:
            return node.this
        text = node.this
        try:
            return int(text)
        except ValueError:
            return float(text)
    if isinstance(node, exp.Boolean):
        return bool(node.this)
    raise _NotLiteral


def _column(node) -> str | None:
    while isinstance(node, (exp.Paren, exp.Cast, exp.TryCast)):
        node = node.this
    if isinstance(node, exp.Column) and isinstance(node.this, exp.Identifier):
        return node.name.lower()
    return None


_BINARY = {}
if exp is not None:
    _BINARY = {exp.EQ: "=", exp.NEQ: "!=", exp.GT: ">", exp.GTE: ">=", exp.LT: "<", exp.LTE: "<="}


def _conjuncts(node) -> list:
    while isinstance(node, exp.Paren):
        node = node.this
    if isinstance(node, exp.And):
        return _conjuncts(node.this) + _conjuncts(node.expression)
    return [node]


def _atom(node) -> tuple | None:
    negate = False
    if isinstance(node, exp.Not):
        negate = True
        node = node.this
        while isinstance(node, exp.Paren):
            node = node.this
    try:
        for cls, op in _BINARY.items():
            if type(node) is cls:
                left, right = _column(node.this), _column(node.expression)
                if left is not None and right is None:
                    atom = (left, op, _literal(node.expression))
                elif right is not None and left is None:
                    atom = (right, _FLIP[op], _literal(node.this))
                else:
                    return None
                if negate:
                    return (atom[0], "!=", atom[2]) if atom[1] == "=" else None
                return atom
        if negate:
            return None
        if isinstance(node, exp.In):
            col = _column(node.this)
            if col is None or node.args.get("query") is not None:
                return None
            return (col, "IN", [_literal(e) for e in node.expressions])
        if isinstance(node, exp.Between):
            col = _column(node.this)
            if col is None:
                return None
            return (col, "BETWEEN", [_literal(node.args["low"]), _literal(node.args["high"])])
        if isinstance(node, (exp.Like, exp.ILike)):
            col = _column(node.this)
            if col is None:
                return None
            return (col, "LIKE" if isinstance(node, exp.Like) else "ILIKE", _literal(node.expression))
    except _NotLiteral:
        return None
    return None


def _atoms_sqlglot(sql: str) -> list[tuple]:
    statements = [s for s in sqlglot.parse(sql, dialect="duckdb") if s is not None]
    atoms: list[tuple] = []
    for stmt in statements:
        for clause in stmt.find_all(exp.Where, exp.Having):
            for conj in _conjuncts(clause.this):
                atom = _atom(conj)
                if atom is not None:
                    atoms.append(atom)
    return atoms


_LIT = r"('(?:[^']|'')*'|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
_COL = r"(?:\w+\.)?\"?(\w+)\"?"
_RE_BETWEEN = re.compile(rf"^{_COL}\s+BETWEEN\s+{_LIT}\s+AND\s+{_LIT}$", re.I)
_RE_IN = re.compile(rf"^{_COL}\s+IN\s*\(([^()]*)\)$", re.I)
_RE_LIKE = re.compile(rf"^{_COL}\s+(I?LIKE)\s+{_LIT}$", re.I)
_RE_CMP = re.compile(rf"^{_COL}\s*(=|!=|<>|>=|<=|>|<)\s*{_LIT}$", re.I)
_RE_CMP_REV = re.compile(rf"^{_LIT}\s*(=|!=|<>|>=|<=|>|<)\s*{_COL}$", re.I)
_CLAUSE_END = re.compile(r"\b(GROUP\s+BY|ORDER\s+BY|LIMIT|HAVING|UNION|WINDOW|QUALIFY)\b|;", re.I)


def _fallback_literal(text: str) -> Any:
    if text.startswith("'"):
        return text[1:-1].replace("''", "'")
    try:
        return int(text)
    except ValueError:
        return float(text)


def _atoms_fallback(sql: str) -> list[tuple]:
    text = re.sub(r"--[^\n]*", " ", sql)
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    atoms: list[tuple] = []
    for match in re.finditer(r"\b(WHERE|HAVING)\b", text, re.I):
        body = text[match.end():]
        end = _CLAUSE_END.search(body)
        body = body[: end.start()] if end else body
        if re.search(r"\b(OR|NOT)\b|\bSELECT\b", body, re.I):
            continue
        body = body.strip().strip("()").strip()
        protected = re.sub(r"\bBETWEEN\s+(\S+)\s+AND\s+", r"BETWEEN \1 _BAND_ ", body, flags=re.I)
        for part in re.split(r"\bAND\b", protected, flags=re.I):
            part = part.replace("_BAND_", "AND").strip().strip("()").strip()
            if m := _RE_BETWEEN.match(part):
                atoms.append((m.group(1).lower(), "BETWEEN", [_fallback_literal(m.group(2)), _fallback_literal(m.group(3))]))
            elif m := _RE_IN.match(part):
                vals = [v.strip() for v in m.group(2).split(",") if v.strip()]
                if all(re.fullmatch(_LIT, v) for v in vals):
                    atoms.append((m.group(1).lower(), "IN", [_fallback_literal(v) for v in vals]))
            elif m := _RE_LIKE.match(part):
                atoms.append((m.group(1).lower(), m.group(2).upper(), _fallback_literal(m.group(3))))
            elif m := _RE_CMP.match(part):
                op = "!=" if m.group(2) == "<>" else m.group(2)
                atoms.append((m.group(1).lower(), op, _fallback_literal(m.group(3))))
            elif m := _RE_CMP_REV.match(part):
                op = "!=" if m.group(2) == "<>" else m.group(2)
                atoms.append((m.group(3).lower(), _FLIP[op], _fallback_literal(m.group(1))))
    return atoms


def extract_atoms(sql: str) -> tuple[list[tuple], str]:
    """Return (atoms, parser) where parser is 'sqlglot' or 'fallback'."""
    if sqlglot is not None:
        try:
            return _atoms_sqlglot(sql), "sqlglot"
        except Exception:
            pass
    return _atoms_fallback(sql), "fallback"


# ---------------------------------------------------------------------------
# Condition matching
# ---------------------------------------------------------------------------

def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip())
        except ValueError:
            return None
    return None


def literal_equal(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    na, nb = _num(a), _num(b)
    if na is not None and nb is not None and not (isinstance(a, str) and isinstance(b, str)):
        return na == nb
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    return False


def _condition_met(cond: dict, atoms: list[tuple]) -> bool:
    col = str(cond.get("column", "")).lower()
    op = str(cond.get("op", "")).upper()
    if op == "<>":
        op = "!="
    value = cond.get("value")
    mine = [a for a in atoms if a[0] == col]
    if op in ("=", "!=", ">", ">=", "<", "<="):
        for _, a_op, a_val in mine:
            if a_op == op and literal_equal(a_val, value):
                return True
            if op == "=" and a_op == "IN" and len(a_val) == 1 and literal_equal(a_val[0], value):
                return True
            if a_op == "BETWEEN" and ((op == ">=" and literal_equal(a_val[0], value))
                                     or (op == "<=" and literal_equal(a_val[1], value))):
                return True
        return False
    if op == "IN":
        wanted = value if isinstance(value, list) else [value]
        for _, a_op, a_val in mine:
            got = a_val if a_op == "IN" else [a_val] if a_op == "=" else None
            if got is None or len(got) != len(wanted):
                continue
            if all(any(literal_equal(g, w) for g in got) for w in wanted) and \
                    all(any(literal_equal(g, w) for w in wanted) for g in got):
                return True
        return False
    if op == "BETWEEN":
        if not (isinstance(value, list) and len(value) == 2):
            return False
        lo, hi = value
        for _, a_op, a_val in mine:
            if a_op == "BETWEEN" and literal_equal(a_val[0], lo) and literal_equal(a_val[1], hi):
                return True
        has_lo = any(a_op == ">=" and literal_equal(a_val, lo) for _, a_op, a_val in mine)
        has_hi = any(a_op == "<=" and literal_equal(a_val, hi) for _, a_op, a_val in mine)
        return has_lo and has_hi
    if op == "LIKE":
        return any(a_op in ("LIKE", "ILIKE") and isinstance(a_val, str) and a_val == value
                   for _, a_op, a_val in mine)
    return False


def check_sql_conditions(sql: Any, conditions: list[dict]) -> dict:
    """Every condition must appear as a restricting predicate of the SQL."""
    if not isinstance(sql, str) or not sql.strip():
        return {"passed": False, "reason": "sql argument missing or not a string", "conditions": []}
    if not isinstance(conditions, list) or not conditions:
        return {"passed": False, "reason": "gold sql_conditions is empty or malformed", "conditions": []}
    atoms, parser = extract_atoms(sql)
    per = []
    for cond in conditions:
        ok = isinstance(cond, dict) and str(cond.get("op", "")).upper() in _OPS | {"<>"} and _condition_met(cond, atoms)
        per.append({"condition": cond, "met": ok})
    passed = all(p["met"] for p in per)
    return {
        "passed": passed,
        "parser": parser,
        "conditions": per,
        "reason": "" if passed else "unmet: " + json.dumps([p["condition"] for p in per if not p["met"]], ensure_ascii=False),
    }


# ---------------------------------------------------------------------------
# Legacy sql_contains (pre-Contract-1 data only)
# ---------------------------------------------------------------------------

def check_sql_contains_legacy(sql: Any, keywords: Any) -> dict:
    """Whole-token, case-insensitive keyword test outside comments. Kept only to score old data."""
    if not isinstance(sql, str):
        return {"passed": False, "reason": "sql argument missing or not a string", "legacy": True}
    text = re.sub(r"--[^\n]*", " ", sql)
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    kws = keywords if isinstance(keywords, list) else [keywords]
    missing = []
    for kw in kws:
        pattern = r"(?<![\w.])" + re.escape(str(kw)) + r"(?![\w.])"
        if not re.search(pattern, text, re.I):
            missing.append(kw)
    return {"passed": not missing, "reason": f"missing tokens: {missing}" if missing else "", "legacy": True}


# ---------------------------------------------------------------------------
# Read-only execution through the platform tool
# ---------------------------------------------------------------------------

def result_is_error(result: Any) -> bool:
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except (json.JSONDecodeError, ValueError):
            return True
    return isinstance(result, dict) and "error" in result


class SqlExecutor:
    """Runs model SQL with the platform's own query_transactions tool (read-only DuckDB)."""

    def __init__(self, timeout_s: float = 60.0):
        self.timeout_s = timeout_s
        self._cache: dict[str, str] = {}
        self._tool = None
        self.source = None

    def _load(self):
        if self._tool is not None:
            return
        from _experiments.scripts._platform import ensure_platform_on_path

        root = ensure_platform_on_path()
        from src.features.agent import _tool_query_transactions  # noqa: PLC0415

        self._tool = _tool_query_transactions
        self.source = f"{root}/src/features/agent.py:_tool_query_transactions"

    def run(self, sql: str) -> str:
        if sql in self._cache:
            return self._cache[sql]
        self._load()
        box: dict[str, str] = {}

        def target():
            try:
                box["out"] = self._tool({"sql": sql})
            except Exception as exc:  # the tool catches its own errors; be safe anyway
                box["out"] = json.dumps({"error": f"executor exception: {exc}"})

        worker = threading.Thread(target=target, daemon=True)
        worker.start()
        worker.join(self.timeout_s)
        if worker.is_alive():
            try:
                from src.data.db import get_connection  # noqa: PLC0415

                get_connection().interrupt()
            except Exception:
                pass
            worker.join(10)
            out = json.dumps({"error": f"scorer timeout after {self.timeout_s}s"})
        else:
            out = box.get("out", json.dumps({"error": "no output"}))
        self._cache[sql] = out
        return out
