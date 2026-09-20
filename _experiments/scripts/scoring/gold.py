"""Loading a benchmark directory of gold single-turn cases or multi-turn scenarios."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Benchmark:
    kind: str  # "single" | "multiturn"
    root: Path
    cases: dict[str, dict] = field(default_factory=dict)
    category: dict[str, str] = field(default_factory=dict)
    sha256: str = ""

    def category_of(self, case_id: str) -> str:
        return self.category.get(case_id, "")


def load_benchmark(root: str | Path) -> Benchmark:
    root = Path(root)
    files = sorted(root.glob("cases_*.json"))
    if not files:
        raise FileNotFoundError(f"no cases_*.json under {root}")
    cases: dict[str, dict] = {}
    category: dict[str, str] = {}
    digest = hashlib.sha256()
    kind = "single"
    for path in files:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
        entries = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(entries, dict):
            entries = entries.get("cases") or entries.get("scenarios") or []
        for entry in entries:
            case_id = entry.get("id")
            if case_id in cases:
                raise ValueError(f"duplicate case id {case_id} in {path}")
            cases[case_id] = entry
            category[case_id] = path.stem.replace("cases_", "")
            if "turns" in entry:
                kind = "multiturn"
    return Benchmark(kind=kind, root=root, cases=cases, category=category, sha256=digest.hexdigest())
