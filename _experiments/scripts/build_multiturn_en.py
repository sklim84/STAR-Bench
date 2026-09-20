"""Retired. Both multi-turn language files are written by one build.

Deriving the English file from the Korean one by collecting, sorting and numbering
the unique Korean strings matches the two arms by position, and a positional match
holds only as long as the set of Korean strings does not change. Reword or add one
turn and the numbering shifts, so translations attach themselves to other
scenarios while the script still reports nothing missing.

Both language files are produced by one build over one scenario spec, keyed by
scenario id and turn number:

    python -m _experiments.scripts.data_fixes.multiturn.build
    python -m _experiments.scripts.data_fixes.multiturn.verify

`verify` asserts that the two files carry the same ids in the same order, the
same turn counts and a byte-identical tool interface, so a drift of this kind
fails the check instead of passing quietly.
"""

from __future__ import annotations

_MESSAGE = (
    "_experiments.scripts.build_multiturn_en was retired. Both multi-turn "
    "files are written by _experiments.scripts.data_fixes.multiturn.build; see the "
    "module docstring for why positional matching is not usable."
)


def __getattr__(name: str):
    raise AttributeError(f"{_MESSAGE} (attribute {name!r})")


if __name__ == "__main__":
    raise SystemExit(_MESSAGE)
