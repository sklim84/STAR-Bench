"""Generates `tools_kr.py` from the platform schema and the Korean prose file.

The Korean schema arm must be the platform schema with Korean prose and nothing
else: same tool names, parameter names, types, enums, defaults, `required` lists
and item schemas. A schema maintained by hand drifts from the platform, and a run
on a drifted arm measures two tool interfaces rather than two languages, so the
arm is generated:

    python -m _experiments.scripts.gen_tools_kr            # rewrite tools_kr.py
    python -m _experiments.scripts.gen_tools_kr --check    # fail if it is stale

Structure comes from `src.features.agent.TOOLS`; prose comes from
`tools_kr_text.json`. A description in one and not the other is an error, so a
platform tool or parameter added without a Korean text stops the generator
instead of silently shipping an English description in the Korean arm.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = "_experiments.scripts"

from ._platform import ensure_platform_on_path

_HERE = Path(__file__).resolve().parent
TEXT_PATH = _HERE / "tools_kr_text.json"
OUT_PATH = _HERE / "tools_kr.py"

_HEADER = '''"""Korean schema arm: the platform tool definitions with Korean prose.

GENERATED FILE. Edit `tools_kr_text.json` and run
`python -m _experiments.scripts.gen_tools_kr`; `--check` fails when this file is
stale, and `_experiments/scripts/tests_runner/test_schema_arms.py` fails when
the structure drifts from `agent.TOOLS`.

The structure is the platform schema, unchanged: same tool names, parameter
names, types, enums, defaults, `required` lists and item schemas. Only the
descriptions and the system prompt are Korean, so a run on this arm executes the
model's arguments as they arrive, with no key or value rewriting, and a
difference between the two arms is a difference in language and in nothing else.
The response-language rule is the same as in the English arm.

Source: agent.TOOLS @ platform {commit}
"""

from __future__ import annotations

import json

TOOLS_KR: list[dict] = json.loads(r"""
{tools_json}
""")

SYSTEM_PROMPT_KR: str = json.loads(r"""
{prompt_json}
""")

__all__ = ["TOOLS_KR", "SYSTEM_PROMPT_KR"]
'''


def _platform_tools():
    ensure_platform_on_path()
    from src.features import agent
    return agent.TOOLS


def _platform_commit() -> str:
    import subprocess
    root = ensure_platform_on_path()
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def build(tools: list[dict], text: dict) -> tuple[list[dict], list[str]]:
    """Returns the Korean tool list and the problems found while building it."""
    problems: list[str] = []
    entries = text["tools"]
    platform_names = [t["function"]["name"] for t in tools]
    for name in sorted(set(entries) - set(platform_names)):
        problems.append(f"{name}: Korean text for a tool the platform does not have")
    out = []
    for tool in tools:
        tool = copy.deepcopy(tool)
        func = tool["function"]
        name = func["name"]
        entry = entries.get(name)
        if entry is None:
            problems.append(f"{name}: no Korean text; add it to tools_kr_text.json")
            out.append(tool)
            continue
        func["description"] = entry["description"]
        props = (func.get("parameters") or {}).get("properties") or {}
        texts = entry.get("params") or {}
        for key in sorted(set(texts) - set(props)):
            problems.append(f"{name}.{key}: Korean text for a parameter the platform does not have")
        for key, prop in props.items():
            if "description" not in prop:
                if key in texts:
                    problems.append(f"{name}.{key}: the platform has no description, "
                                    f"so the Korean arm must not add one")
                continue
            if key not in texts:
                problems.append(f"{name}.{key}: no Korean text; add it to tools_kr_text.json")
                continue
            prop["description"] = texts[key]
        out.append(tool)
    return out, problems


def render(tools_kr: list[dict], prompt: str, commit: str) -> str:
    tools_json = json.dumps(tools_kr, ensure_ascii=False, indent=1)
    prompt_json = json.dumps(prompt, ensure_ascii=False)
    for blob in (tools_json, prompt_json):
        # A raw triple-quoted string holds backslash escapes as they are, which is
        # what json.loads wants back; it cannot hold the delimiter or end on a backslash.
        if '"""' in blob or blob.endswith("\\"):
            raise ValueError("generated JSON contains a delimiter the raw string cannot hold")
    return _HEADER.format(commit=commit, tools_json=tools_json, prompt_json=prompt_json)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="exit non-zero when tools_kr.py is stale")
    ap.add_argument("--out", type=Path, default=OUT_PATH)
    args = ap.parse_args(argv)

    text = json.loads(TEXT_PATH.read_text(encoding="utf-8"))
    tools_kr, problems = build(_platform_tools(), text)
    if problems:
        print("the Korean prose does not line up with the platform schema:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 2
    rendered = render(tools_kr, text["system_prompt"], _platform_commit())
    if args.check:
        current = args.out.read_text(encoding="utf-8") if args.out.exists() else ""
        # The source line carries the platform commit, which moves on its own.
        def body(s: str) -> str:
            return "\n".join(l for l in s.splitlines() if not l.startswith("Source: agent.TOOLS"))
        if body(current) != body(rendered):
            print(f"{args.out} is stale; run python -m _experiments.scripts.gen_tools_kr",
                  file=sys.stderr)
            return 1
        print(f"{args.out} is up to date ({len(tools_kr)} tools)")
        return 0
    args.out.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.out} ({len(tools_kr)} tools)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
