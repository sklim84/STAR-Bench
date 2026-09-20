"""Retired. The English schema arm is the platform schema itself.

Neither arm may carry a hand-written copy of the tool list. A second copy drifts
from the platform, and a tool list that differs in its enums, its defaults or its
`required` lists changes what the model is asked to do rather than what language
it is asked in, so a language comparison run on it measures two tool interfaces
instead of two languages. A parameter renamed away from the platform name is
worse still: the tool layer rejects the call, and the failure is scored as the
model's.

The English arm is `runner.arms.load_arm("en")`: `agent.TOOLS` and
`agent.SYSTEM_PROMPT`, straight from the platform. The Korean arm is
`tools_kr.py`, generated from the same schema (`gen_tools_kr.py`), so the two
arms differ in prose and in nothing else.

`EN_KO_PARAM_MAP` is gone with the module. Both arms carry the platform
parameter names, so nothing is renamed before execution or before scoring.
"""

from __future__ import annotations

_MESSAGE = (
    "_experiments.scripts.tools_en was retired. Use "
    "runner.arms.load_arm('en') for the platform schema or load_arm('kr') for the "
    "Korean mirror; see the module docstring for why an arm is not a hand-written "
    "tool list."
)


def __getattr__(name: str):
    raise AttributeError(f"{_MESSAGE} (attribute {name!r})")
