"""SQL checks: predicate extraction for ``sql_conditions`` and read-only execution for ``sql_valid``.

Predicates are taken from every WHERE and HAVING clause of the statement
(subqueries and CTEs included), but only along AND-only paths: a comparison
under OR or NOT (other than NOT col = v) does not restrict the result, so it
never satisfies a condition. When sqlglot cannot parse the text, a regex
fallback reads the same atoms: it finds every WHERE and HAVING outside string
literals, delimits each clause by depth (a clause inside a subquery ends at the
parenthesis that closes it), and splits on AND at parenthesis depth 0, so
``col IN (1, 2)`` and ``col BETWEEN a AND b`` survive intact. It drops a single
term it cannot read rather than the whole clause, and gives up on a clause whose
OR is at the clause's own top level, because AND binds tighter and a term next
to such an OR does not restrict the result.

The fallback used to skip any clause whose text contained SELECT, so the two
cases whose reference SQL puts a scalar subquery in the WHERE clause
(`st_qt_025`, `st_qt_039`) silently lost their sibling predicates and the gold
self-test read 1256/1258 in a sqlglot-less environment (V-05). Terms the
fallback still cannot read are now reported: `extract_atoms_detailed` returns
them and `check_sql_conditions` names them in the reason of a failing check, so
a check that fails because of the environment says so instead of looking like a
data defect.

`sqlglot` is pinned in `_experiments/env/requirements-eval.txt` and gate 1
checks it. Without it the fallback answers, and the fallback is the conservative
reading of the same predicates: it never reports a condition met that sqlglot
would report unmet.
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
_CLAUSE_END = re.compile(r"(GROUP\s+BY|ORDER\s+BY|LIMIT|OFFSET|HAVING|UNION|EXCEPT|INTERSECT"
                         r"|WINDOW|QUALIFY)(?![\w])", re.I)
_RE_NOT = re.compile(r"^NOT\s+(.*)$", re.I | re.S)


def _fallback_literal(text: str) -> Any:
    if text.startswith("'"):
        return text[1:-1].replace("''", "'")
    try:
        return int(text)
    except ValueError:
        return float(text)


def _skip_literal(text: str, i: int) -> int:
    """Index just past the string literal that starts at `i`, '' escapes included."""
    i += 1
    while i < len(text):
        if text[i] == "'":
            if text[i + 1: i + 2] == "'":
                i += 2
                continue
            return i + 1
        i += 1
    return i


def _strip_outer_parens(text: str) -> str:
    """Removes parentheses that wrap the whole term, and only those."""
    while text.startswith("(") and text.endswith(")"):
        depth = 0
        for i, ch in enumerate(text):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i != len(text) - 1:
                    return text
        text = text[1:-1].strip()
    return text


def _word_at(text: str, i: int, word: str) -> bool:
    if text[i: i + len(word)].upper() != word:
        return False
    before = text[i - 1: i]
    after = text[i + len(word): i + len(word) + 1]
    return not (before.isalnum() or before == "_") and not (after.isalnum() or after == "_")


def _clause_starts(text: str) -> list[int]:
    """Where each WHERE/HAVING clause body begins, ignoring string literals."""
    starts, i = [], 0
    while i < len(text):
        if text[i] == "'":
            i = _skip_literal(text, i)
            continue
        for word in ("WHERE", "HAVING"):
            if _word_at(text, i, word):
                starts.append(i + len(word))
                i += len(word)
                break
        else:
            i += 1
    return starts


def _clause_body(text: str, start: int) -> str:
    """One clause: to the keyword that ends it, to `;`, or to the `)` that closes it.

    A clause inside a subquery ends at that subquery's closing parenthesis, which
    is what lets the outer clause of `... WHERE a = 1 AND b >= (SELECT ... WHERE
    c = 2) ORDER BY x` and the inner one be read separately.
    """
    depth, i = 0, start
    while i < len(text):
        ch = text[i]
        if ch == "'":
            i = _skip_literal(text, i)
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                return text[start:i]
            depth -= 1
        elif ch == ";":
            return text[start:i]
        elif depth == 0 and ch.isalpha() and not (text[i - 1: i].isalnum() or text[i - 1: i] == "_"):
            if _CLAUSE_END.match(text, i):
                return text[start:i]
        i += 1
    return text[start:]


def _has_top_level_or(text: str) -> bool:
    """An OR at the clause's own level: AND binds tighter, so nothing restricts."""
    depth, i = 0, 0
    while i < len(text):
        ch = text[i]
        if ch == "'":
            i = _skip_literal(text, i)
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and _word_at(text, i, "OR"):
            return True
        i += 1
    return False


def _split_and(text: str) -> list[str]:
    """Splits on AND at parenthesis depth 0, outside string literals.

    The AND of a BETWEEN belongs to the BETWEEN, so it does not split: one
    `BETWEEN` at this depth consumes the next `AND` at this depth.
    """
    parts, depth, start, i, between = [], 0, 0, 0, 0
    while i < len(text):
        ch = text[i]
        if ch == "'":
            i = _skip_literal(text, i)
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and _word_at(text, i, "BETWEEN"):
            between += 1
            i += 7
            continue
        elif depth == 0 and _word_at(text, i, "AND"):
            if between:
                between -= 1
            else:
                parts.append(text[start:i])
                start = i + 3
            i += 3
            continue
        i += 1
    parts.append(text[start:])
    return [p.strip() for p in parts if p.strip()]


def _conjuncts_fallback(text: str) -> list[str]:
    """Every AND-ed term of a clause, parenthesised groups flattened."""
    out: list[str] = []
    for part in _split_and(text):
        stripped = _strip_outer_parens(part)
        if stripped != part and len(_split_and(stripped)) > 1:
            out.extend(_conjuncts_fallback(stripped))
        else:
            out.append(stripped)
    return out


_RE_CAST = re.compile(r"\b(?:TRY_)?CAST\s*\(\s*([^()]*?)\s+AS\s+[A-Za-z_][\w ]*\s*\)", re.I)
_RE_DOUBLE_COLON = re.compile(r"::\s*[A-Za-z_][\w]*")


def _mask_literals(text: str) -> tuple[str, list[str]]:
    """Replaces every string literal with a placeholder, so a rewrite cannot reach inside it."""
    out, kept, i, start = [], [], 0, 0
    while i < len(text):
        if text[i] == "'":
            out.append(text[start:i])
            end = _skip_literal(text, i)
            out.append(f"\x00{len(kept)}\x00")
            kept.append(text[i:end])
            i = start = end
            continue
        i += 1
    out.append(text[start:])
    return "".join(out), kept


def _unmask_literals(text: str, kept: list[str]) -> str:
    for index, literal in enumerate(kept):
        text = text.replace(f"\x00{index}\x00", literal)
    return text


def _unwrap_casts(part: str) -> str:
    """`CAST(col AS INTEGER)` and `col::INTEGER` are the column, as sqlglot reads them."""
    masked, kept = _mask_literals(part)
    previous = None
    while previous != masked:
        previous = masked
        masked = _RE_CAST.sub(r"\1", masked)
    masked = _RE_DOUBLE_COLON.sub("", masked)
    return _unmask_literals(masked, kept).strip()


def _fallback_atom(part: str) -> tuple[tuple | None, bool]:
    """(atom, unreadable) for one AND-ed term.

    `unreadable` is True only when the fallback does not recognise the text at
    all. A term it recognises and drops on purpose - anything under NOT, an IN
    whose values are not literals - is not a gap: sqlglot drops those too.
    """
    part = _unwrap_casts(part)
    if match := _RE_NOT.match(part):
        # NOT binds tighter than AND. `NOT col = v` is `col != v`; anything else
        # under NOT (NOT IN, NOT BETWEEN, NOT (...)) is dropped, the way sqlglot
        # drops it, and its AND-siblings are kept.
        inner = _strip_outer_parens(match.group(1).strip())
        cmp_match = _RE_CMP.match(inner)
        if cmp_match and cmp_match.group(2) == "=":
            return (cmp_match.group(1).lower(), "!=", _fallback_literal(cmp_match.group(3))), False
        return None, False
    if re.search(r"\bNOT\b", part, re.I):
        return None, False                # col NOT IN (...), col IS NOT NULL
    if m := _RE_BETWEEN.match(part):
        return (m.group(1).lower(), "BETWEEN",
                [_fallback_literal(m.group(2)), _fallback_literal(m.group(3))]), False
    if m := _RE_IN.match(part):
        vals = [v.strip() for v in m.group(2).split(",") if v.strip()]
        if vals and all(re.fullmatch(_LIT, v) for v in vals):
            return (m.group(1).lower(), "IN", [_fallback_literal(v) for v in vals]), False
        return None, False
    if m := _RE_LIKE.match(part):
        return (m.group(1).lower(), m.group(2).upper(), _fallback_literal(m.group(3))), False
    if m := _RE_CMP.match(part):
        op = "!=" if m.group(2) == "<>" else m.group(2)
        return (m.group(1).lower(), op, _fallback_literal(m.group(3))), False
    if m := _RE_CMP_REV.match(part):
        op = "!=" if m.group(2) == "<>" else m.group(2)
        return (m.group(3).lower(), _FLIP[op], _fallback_literal(m.group(1))), False
    if re.fullmatch(r"[\w.\"]+\s+IS\s+NULL", part, re.I):
        return None, False
    return None, True


def _atoms_fallback(sql: str) -> tuple[list[tuple], list[str]]:
    text = re.sub(r"--[^\n]*", " ", sql)
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    atoms: list[tuple] = []
    unreadable: list[str] = []
    for start in _clause_starts(text):
        body = _clause_body(text, start).strip()
        if not body:
            continue
        if _has_top_level_or(body):
            # AND binds tighter than OR, so a term next to an OR at this level
            # does not restrict the result on its own. sqlglot reads the clause
            # the same way.
            continue
        for part in _conjuncts_fallback(body):
            atom, gap = _fallback_atom(part)
            if atom is not None:
                atoms.append(atom)
            elif gap:
                unreadable.append(" ".join(part.split())[:120])
    return atoms, unreadable


def extract_atoms_detailed(sql: str) -> tuple[list[tuple], str, list[str]]:
    """(atoms, parser, unreadable terms). The parser is 'sqlglot' or 'fallback'.

    Only the fallback reports unreadable terms; sqlglot either parses the
    statement or hands it to the fallback.
    """
    if sqlglot is not None:
        try:
            return _atoms_sqlglot(sql), "sqlglot", []
        except Exception:
            pass
    atoms, unreadable = _atoms_fallback(sql)
    return atoms, "fallback", unreadable


def extract_atoms(sql: str) -> tuple[list[tuple], str]:
    """Return (atoms, parser) where parser is 'sqlglot' or 'fallback'."""
    atoms, parser, _unreadable = extract_atoms_detailed(sql)
    return atoms, parser


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
    atoms, parser, unreadable = extract_atoms_detailed(sql)
    per = []
    for cond in conditions:
        ok = isinstance(cond, dict) and str(cond.get("op", "")).upper() in _OPS | {"<>"} and _condition_met(cond, atoms)
        per.append({"condition": cond, "met": ok})
    passed = all(p["met"] for p in per)
    reason = "" if passed else "unmet: " + json.dumps(
        [p["condition"] for p in per if not p["met"]], ensure_ascii=False)
    if unreadable and not passed:
        # Say when the environment, not the data, is what failed the check: with
        # sqlglot installed this statement is read by the parser (V-05).
        reason += (f"; the regex fallback could not read {json.dumps(unreadable, ensure_ascii=False)}"
                   f" - install sqlglot {SQLGLOT_PIN} "
                   f"(_experiments/scripts/scoring/requirements.txt) to score this statement with "
                   f"the parser")
    out = {"passed": passed, "parser": parser, "conditions": per, "reason": reason}
    if unreadable:
        out["unreadable"] = unreadable
    return out


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
