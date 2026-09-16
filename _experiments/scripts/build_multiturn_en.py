"""Retired. The English multi-turn file is written by the rebuild pass (C1-010).

This script used to derive `benchmarks_multiturn_en/` from `benchmarks_multiturn/`
by collecting the unique Korean strings of each field, sorting them, numbering
them F000/S000/C000/N000 and looking the number up in an embedded translation
table. The numbering therefore depended on the *set* of Korean strings: changing
one Korean turn renumbered everything after it, and the English file came out
with 167 turns attached to other scenarios while the script reported no missing
translations at all.

Both language files are now produced by one pass over one scenario spec, keyed by
scenario id and turn number:

    python -m _experiments.scripts.data_fixes.multiturn.build
    python -m _experiments.scripts.data_fixes.multiturn.verify

`verify` asserts that the two files carry the same ids in the same order, the
same turn counts and a byte-identical tool interface, so a drift of this kind
fails the check instead of passing quietly.
"""

from __future__ import annotations

_MESSAGE = (
    "_experiments.scripts.build_multiturn_en was retired (C1-010). Both multi-turn "
    "files are written by _experiments.scripts.data_fixes.multiturn.build; see the "
    "module docstring for why positional matching was not usable."
)


def __getattr__(name: str):
    raise AttributeError(f"{_MESSAGE} (attribute {name!r})")


if __name__ == "__main__":
    raise SystemExit(_MESSAGE)
