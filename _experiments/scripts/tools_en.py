"""Retired. The English schema arm is the platform schema itself (D16).

This module used to hold a second, hand-written English tool list. It was not a
translation of `agent.TOOLS`: it dropped all seven string enums and the integer
enum, dropped every default and every array item schema, changed five `required`
lists (so `get_fraud_type_summary` needed no argument at all, which turned a
clarification case into a pass) and renamed `predict_fraud` parameters to names
the tool layer does not accept, so every call of that tool failed and the models
retried it four times per case (C2-005, L5-015).

The English arm is now `runner.arms.load_arm("en")`: `agent.TOOLS` and
`agent.SYSTEM_PROMPT`, straight from the platform. The Korean arm is
`tools_kr.py`, generated from the same schema (`gen_tools_kr.py`), so the two
arms differ in prose and in nothing else.

`EN_KO_PARAM_MAP` is gone with the module. Both arms carry the platform
parameter names, so nothing is renamed before execution or before scoring.
"""

from __future__ import annotations

_MESSAGE = (
    "_experiments.scripts.tools_en was retired (D16). Use "
    "runner.arms.load_arm('en') for the platform schema or load_arm('kr') for the "
    "Korean mirror; see the module docstring for why the old list was not usable."
)


def __getattr__(name: str):
    raise AttributeError(f"{_MESSAGE} (attribute {name!r})")
