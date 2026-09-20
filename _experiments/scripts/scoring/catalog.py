"""Free-string reference arguments scored by the rows the platform catalog returns.

``lookup_fiu_reference_types(keyword)`` and ``get_aml_glossary(term)`` are pure
functions of a static catalog, so "did the model ask for the same thing" is the
row set they return, not the spelling of the argument. The catalog
functions are imported from the platform; no database is involved.
"""

from __future__ import annotations

from typing import Any

RESULT_SET_ARGS = {
    "lookup_fiu_reference_types": {"keyword"},
    "get_aml_glossary": {"term"},
}


class Catalog:
    def __init__(self):
        self._fiu = None
        self._glossary = None
        self.source = None

    def _load(self):
        if self._fiu is not None:
            return
        from _experiments.scripts._platform import ensure_platform_on_path

        root = ensure_platform_on_path()
        from src.features.aml_reference import (  # noqa: PLC0415
            get_aml_glossary,
            lookup_fiu_reference_types,
        )

        self._fiu = lookup_fiu_reference_types
        self._glossary = get_aml_glossary
        self.source = f"{root}/src/features/aml_reference.py"

    def rows(self, tool: str, value: Any) -> frozenset | None:
        """Row identities the catalog returns for this argument value, or None if not comparable."""
        if not isinstance(value, str):
            return None
        self._load()
        if tool == "lookup_fiu_reference_types":
            found = self._fiu(value, None)
            return frozenset((r["industry"], r["category"], r["no"]) for r in found)
        if tool == "get_aml_glossary":
            found = self._glossary(value)
            return frozenset() if found is None else frozenset({found["term"]})
        return None


def normalized_equal(a: Any, b: Any) -> bool:
    return isinstance(a, str) and isinstance(b, str) and a.strip().casefold() == b.strip().casefold()


def compare_result_set(catalog: Catalog, tool: str, actual: Any, expected: Any) -> dict:
    """Pass when the model's value selects the same catalog rows as the gold value.

    An empty gold row set means the gold string itself finds nothing, so the
    comparison falls back to case-insensitive string equality and the case is
    flagged for the data owners.
    """
    gold_rows = catalog.rows(tool, expected)
    if gold_rows is None:
        return {"passed": normalized_equal(actual, expected), "mode": "string",
                "reason": "gold value is not a string"}
    if not gold_rows:
        return {"passed": normalized_equal(actual, expected), "mode": "string",
                "gold_empty_result": True,
                "reason": f"gold value {expected!r} returns no catalog rows"}
    actual_rows = catalog.rows(tool, actual)
    if actual_rows is None:
        return {"passed": False, "mode": "result_set", "reason": f"argument is not a string: {actual!r}"}
    passed = actual_rows == gold_rows
    return {
        "passed": passed,
        "mode": "result_set",
        "n_rows_gold": len(gold_rows),
        "n_rows_actual": len(actual_rows),
        "reason": "" if passed else f"{actual!r} returns {len(actual_rows)} rows, gold {expected!r} returns {len(gold_rows)}",
    }
