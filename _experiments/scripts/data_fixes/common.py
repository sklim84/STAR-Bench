"""Benchmark IO and the change log shared by every data-fix pass."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
KR = REPO / "benchmarks"
EN = REPO / "benchmarks_en"
CHANGELOG = Path(__file__).resolve().parent / "changelog"
AUDIT = REPO / "_experiments" / "dataset_fix_20260915"


def load_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump_json(path: str | Path, payload) -> None:
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@dataclass
class Bench:
    """One benchmark directory, kept as file -> list of cases so order survives."""

    root: Path
    lang: str
    files: dict[str, list[dict]] = field(default_factory=dict)

    @classmethod
    def load(cls, root: str | Path, lang: str) -> "Bench":
        root = Path(root)
        files = {p.name: load_json(p) for p in sorted(root.glob("cases_*.json"))}
        return cls(root=root, lang=lang, files=files)

    def save(self) -> None:
        for name, cases in self.files.items():
            dump_json(self.root / name, cases)

    # -- lookups ----------------------------------------------------------
    def cases(self):
        for name, cases in self.files.items():
            for case in cases:
                yield name, case

    def by_id(self) -> dict[str, dict]:
        return {c["id"]: c for _, c in self.cases()}

    def file_of(self) -> dict[str, str]:
        return {c["id"]: name for name, c in self.cases()}

    def get(self, case_id: str) -> dict | None:
        return self.by_id().get(case_id)

    def category(self, case_id: str) -> str:
        return self.file_of()[case_id][len("cases_"):-len(".json")]

    def drop(self, case_ids: set[str]) -> None:
        for name, cases in self.files.items():
            self.files[name] = [c for c in cases if c["id"] not in case_ids]

    def add(self, file_name: str, case: dict) -> None:
        self.files.setdefault(file_name, []).append(case)

    def n_cases(self) -> int:
        return sum(len(v) for v in self.files.values())


class ChangeLog:
    """Before/after record of one pass, written next to the pass scripts."""

    def __init__(self, pass_name: str, description: str):
        self.pass_name = pass_name
        self.description = description
        self.entries: list[dict] = []
        self.notes: list[str] = []

    def record(self, case_id: str, lang: str, field: str, before, after, issue: str, why: str) -> None:
        if before == after:
            return
        self.entries.append({
            "case_id": case_id, "lang": lang, "field": field, "issue": issue,
            "why": why, "before": copy.deepcopy(before), "after": copy.deepcopy(after),
        })

    def note(self, text: str) -> None:
        self.notes.append(text)

    def set_field(self, case: dict, lang: str, field: str, value, issue: str, why: str) -> bool:
        before = case.get(field)
        if before == value:
            return False
        self.record(case["id"], lang, field, before, value, issue, why)
        case[field] = value
        return True

    def delete_field(self, case: dict, lang: str, field: str, issue: str, why: str) -> bool:
        if field not in case:
            return False
        self.record(case["id"], lang, field, case[field], None, issue, why)
        del case[field]
        return True

    def counts(self) -> dict:
        by_issue: dict[str, int] = {}
        for e in self.entries:
            by_issue[e["issue"]] = by_issue.get(e["issue"], 0) + 1
        return by_issue

    def write(self) -> Path:
        CHANGELOG.mkdir(parents=True, exist_ok=True)
        path = CHANGELOG / f"{self.pass_name}.json"
        cases = sorted({e["case_id"] for e in self.entries})
        dump_json(path, {
            "pass": self.pass_name,
            "description": self.description,
            "n_changes": len(self.entries),
            "n_cases": len(cases),
            "by_issue": self.counts(),
            "notes": self.notes,
            "changes": self.entries,
        })
        return path

    def report(self) -> str:
        head = f"{self.pass_name}: {len(self.entries)} changes over " \
               f"{len({e['case_id'] for e in self.entries})} cases"
        body = "\n".join(f"  {k}: {v}" for k, v in sorted(self.counts().items()))
        return head + ("\n" + body if body else "")


def both() -> tuple[Bench, Bench]:
    return Bench.load(KR, "kr"), Bench.load(EN, "en")
