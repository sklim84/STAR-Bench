"""Schema arms: the tool definitions and the system prompt a run shows the model.

Two arms, and only two:

    en  the platform's own `agent.TOOLS` and `agent.SYSTEM_PROMPT`
    kr  `tools_kr.TOOLS_KR` and `tools_kr.SYSTEM_PROMPT_KR`, generated from
        `agent.TOOLS` so the structure is identical and only the prose is Korean

The old `tools_en.py` is retired: it was not a translation of the platform
schema but a second, divergent schema that dropped every enum, default and item
schema and changed five `required` lists.

Because both arms carry the same parameter names, the runner executes what the
model sent without rewriting anything. The value-normalisation map that turned
Korean FIU keywords into the English ones the catalog holds is gone with it: it
gave the Korean arm free parameter accuracy on nine cases that no other arm
could get.

The response-language rule is the same sentence in both arms: answer in the
language of the user's question.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path

__all__ = ["Arm", "load_arm", "ARM_NAMES", "schema_signature", "parity_problems",
           "PROMPT_VARIANT_DIR", "prompt_variants"]

ARM_NAMES = ("kr", "en")
PROMPT_VARIANT_DIR = Path(__file__).resolve().parents[1] / "prompt_variants"


def _sha256(obj) -> str:
    text = obj if isinstance(obj, str) else json.dumps(
        obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Arm:
    lang: str
    tools: list[dict]
    system_prompt: str
    tools_sha256: str
    prompt_sha256: str
    prompt_variant: str = "baseline"

    @property
    def tool_names(self) -> list[str]:
        return [t["function"]["name"] for t in self.tools]


def _platform():
    from _experiments.scripts._platform import ensure_platform_on_path
    ensure_platform_on_path()
    from src.features import agent
    return agent


def prompt_variants() -> list[str]:
    names = {"baseline"}
    for path in PROMPT_VARIANT_DIR.glob("*.*.txt"):
        names.add(path.name.split(".")[0])
    return sorted(names)


def load_arm(lang: str, *, prompt_variant: str = "baseline") -> Arm:
    if lang not in ARM_NAMES:
        raise ValueError(f"unknown schema arm {lang!r}; expected one of {ARM_NAMES}")
    if lang == "en":
        agent = _platform()
        tools, prompt = agent.TOOLS, agent.SYSTEM_PROMPT
    else:
        from _experiments.scripts import tools_kr
        tools, prompt = tools_kr.TOOLS_KR, tools_kr.SYSTEM_PROMPT_KR
    if prompt_variant != "baseline":
        path = PROMPT_VARIANT_DIR / f"{prompt_variant}.{lang}.txt"
        if not path.is_file():
            raise ValueError(f"no prompt variant {prompt_variant!r} for the {lang} arm; "
                             f"expected {path}")
        prompt = prompt.rstrip() + "\n\n" + path.read_text(encoding="utf-8").strip()
    return Arm(lang=lang, tools=tools, system_prompt=prompt, tools_sha256=_sha256(tools),
               prompt_sha256=_sha256(prompt), prompt_variant=prompt_variant)


# ---------------------------------------------------------------------------
# Structural parity: the arms differ in prose and in nothing else.
# ---------------------------------------------------------------------------

def _prop_signature(prop: dict) -> dict:
    sig = {k: prop[k] for k in ("type", "enum", "default") if k in prop}
    items = prop.get("items")
    if isinstance(items, dict):
        sig["items"] = _prop_signature(items)
        if isinstance(items.get("properties"), dict):
            sig["items"]["properties"] = {
                k: _prop_signature(v) for k, v in items["properties"].items()}
    return sig


def schema_signature(tools: list[dict]) -> dict:
    """Everything about a tool list except the human-readable strings."""
    out = {}
    for tool in tools:
        func = tool["function"]
        params = func.get("parameters") or {}
        out[func["name"]] = {
            "type": params.get("type"),
            "required": sorted(params.get("required") or []),
            "properties": {name: _prop_signature(prop)
                           for name, prop in (params.get("properties") or {}).items()},
        }
    return out


def parity_problems(a: list[dict], b: list[dict], *, names=("en", "kr")) -> list[str]:
    """Differences between two arms, as sentences a test can print."""
    sa, sb = schema_signature(a), schema_signature(b)
    problems = []
    for name in sorted(set(sa) - set(sb)):
        problems.append(f"{name}: present in {names[0]}, missing from {names[1]}")
    for name in sorted(set(sb) - set(sa)):
        problems.append(f"{name}: present in {names[1]}, missing from {names[0]}")
    for name in sorted(set(sa) & set(sb)):
        ta, tb = sa[name], sb[name]
        if ta["required"] != tb["required"]:
            problems.append(f"{name}.required: {names[0]}={ta['required']} {names[1]}={tb['required']}")
        pa, pb = ta["properties"], tb["properties"]
        for key in sorted(set(pa) - set(pb)):
            problems.append(f"{name}.{key}: present in {names[0]}, missing from {names[1]}")
        for key in sorted(set(pb) - set(pa)):
            problems.append(f"{name}.{key}: present in {names[1]}, missing from {names[0]}")
        for key in sorted(set(pa) & set(pb)):
            if pa[key] != pb[key]:
                problems.append(f"{name}.{key}: {names[0]}={pa[key]} {names[1]}={pb[key]}")
    if list(sa) != list(sb):
        problems.append(f"tool order differs: {names[0]}={list(sa)} {names[1]}={list(sb)}")
    return problems
