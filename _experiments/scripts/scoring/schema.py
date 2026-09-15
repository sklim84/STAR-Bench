"""Tool schemas used by the scorer: property names, types, enums and defaults.

The schema is read from the platform (``src.features.agent.TOOLS``). Importing
the agent module pulls in the whole tool layer, so when that import fails the
``TOOLS = [...]`` literal is read from ``agent.py`` with ``ast`` instead. A JSON
file with the same list can be passed explicitly (``load_tool_schemas(path)``).
"""

from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolSchema:
    name: str
    properties: dict[str, dict] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)

    def prop(self, key: str) -> dict:
        return self.properties.get(key, {})

    def defaults(self) -> dict[str, Any]:
        return {k: p["default"] for k, p in self.properties.items() if "default" in p}


class SchemaSet:
    """Tool name -> ToolSchema, plus where the schema came from."""

    def __init__(self, tools: list[dict], source: str):
        self.source = source
        self.tools: dict[str, ToolSchema] = {}
        for t in tools:
            fn = t.get("function", t)
            params = fn.get("parameters") or {}
            self.tools[fn["name"]] = ToolSchema(
                name=fn["name"],
                properties=dict(params.get("properties") or {}),
                required=list(params.get("required") or []),
            )
        canon = json.dumps(tools, ensure_ascii=False, sort_keys=True)
        self.sha256 = hashlib.sha256(canon.encode("utf-8")).hexdigest()

    def get(self, name: str) -> ToolSchema | None:
        return self.tools.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self.tools

    def names(self) -> list[str]:
        return list(self.tools)


def _tools_from_agent_source(agent_py: Path) -> list[dict]:
    tree = ast.parse(agent_py.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "TOOLS" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise ValueError(f"no literal TOOLS assignment in {agent_py}")


def load_tool_schemas(path: str | Path | None = None) -> SchemaSet:
    if path is not None:
        path = Path(path)
        return SchemaSet(json.loads(path.read_text(encoding="utf-8")), f"file:{path}")

    from _experiments.scripts._platform import ensure_platform_on_path

    root = ensure_platform_on_path()
    try:
        from src.features.agent import TOOLS  # noqa: PLC0415

        return SchemaSet(TOOLS, f"import:{root}/src/features/agent.py")
    except Exception:  # the tool layer's own dependencies may be missing
        agent_py = root / "src" / "features" / "agent.py"
        return SchemaSet(_tools_from_agent_source(agent_py), f"ast:{agent_py}")
