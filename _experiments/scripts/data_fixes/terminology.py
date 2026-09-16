"""One spelling per AML pattern term, and the screen that keeps it that way.

`TERMINOLOGY.md` next to this file is the prose version; this module is the
executable copy, and it is what the passes and the verifiers actually run. Both
`p23_terminology_residue` (single-turn) and `multiturn.verify` call `screen()`,
so the convention is enforced over all four benchmark directories rather than
over the two the original pass happened to load.

Two rules.

**One spelling per pattern.** `CONVENTION` names it. `BANNED_KR` and `BANNED_EN`
list the spellings that must therefore not appear in a question, whichever pass
would have introduced them.

**No collision with the HOFINET fraud type (L1-010).** 분할 거래 / "split
transaction" is HOFINET fraud type 3, a value of `fraud_type`. `structuring` is
the pattern `detect_ctr_candidates(mode='structuring')`,
`lookup_fiu_reference_types(keyword='structuring')` and the `Structuring`
glossary entry are about. They are not the same thing and they are not answered
by the same tool, so a question whose gold selects one must not name the other.
The 2026-09-16 review left five places that did (`mt_str_010#t3`,
`mt_str_039#t3`, `mt_str_049#t3`, `st_fiu_001`, `st_mtool_106`): for the two
single-turn cases the literal reading of both arms is `keyword='split'`, which
returns two catalog rows against the gold's one and scores 0.

Scope: the screen reads the text a model sees as the user's message, with any
JSON payload removed. Gold argument values are out of scope by construction, and
deliberately so: `generate_str(fraud_type='분할거래')` is a §VI enum the platform
only accepts in Korean, and an STR narrative quotes the Korean name a tool's own
result carries.
"""

from __future__ import annotations

import re

# pattern -> the one spelling each arm uses for it.
CONVENTION = {
    "ring": {"kr": "순환거래", "en": "circular transaction"},
    "layering": {"kr": "레이어링", "en": "layering"},
    "funnel": {"kr": "funnel", "en": "funnel"},
    "structuring": {"kr": "structuring", "en": "structuring"},
    "smurfing": {"kr": "스머핑", "en": "smurfing"},
    # Not a pattern the tools detect but the HOFINET fraud type the questions name,
    # kept here because it is the term `structuring` collides with.
    "hofinet fraud type 3": {"kr": "분할 거래", "en": "split transaction"},
}

# A question that asks for a catalog or glossary entry names it by its key, which the
# catalog holds in English ("Structuring 항목", "the Structuring entry"). That is the
# entry's name, not the pattern term, so the Korean screen looks for the lower-case
# pattern tokens only.
BANNED_KR: list[tuple[str, str]] = [
    (r"구조화", "structuring is written `structuring`; 구조화 reads as a synonym of 분할 거래"),
    (r"깔때기", "funnel is written `funnel`"),
    (r"퍼널", "funnel is written `funnel`"),
    (r"집금", "funnel is written `funnel`; 집금/집결 is the wording detect_smurfing_network uses"),
    (r"대포통장", "not a HOFINET transaction type"),
    (r"(?<![A-Za-z])ring(?![A-Za-z])", "the ring pattern is written 순환거래"),
    (r"(?<![A-Za-z])layering(?![A-Za-z])", "layering is written 레이어링"),
    (r"(?<![A-Za-z])smurfing(?![A-Za-z])", "smurfing is written 스머핑"),
    (r"circular transaction", "the ring pattern is written 순환거래"),
]

BANNED_EN: list[tuple[str, str]] = [
    (r"circular transaction rings", "the ring pattern is written `circular transaction`"),
    (r"(?<![-\w])rings?(?![-\w])", "the ring pattern is written `circular transaction`"),
    (r"mule accounts?", "not a HOFINET transaction type"),
    (r"\(funnel\)", "no cross-language gloss in brackets"),
    (r"\(collection\)", "no cross-language gloss in brackets"),
    (r"structured transaction", "structuring is written `structuring`"),
    (r"구조화|깔때기|집금|퍼널|순환거래|레이어링|스머핑",
     "a Korean pattern term in an English question"),
]

# Gold argument values that select the structuring pattern, and the HOFINET fraud type
# it is confused with. `lookup_fiu_reference_types(keyword='split')` is deliberately not
# in the first table: that gold IS the catalog's split-transaction rows, so a question
# that names 분할 거래 for it is right.
STRUCTURING_VALUES = {
    ("detect_ctr_candidates", "mode"): {"structuring"},
    ("detect_aml_patterns", "pattern"): {"structuring"},
    ("lookup_fiu_reference_types", "keyword"): {"structuring"},
    ("get_aml_glossary", "term"): {"structuring"},
}
TYPE3_VALUES = {
    ("get_fraud_type_summary", "fraud_type"): {3},
    ("generate_str", "fraud_type"): {"분할거래"},
}

# What a question must not say once its gold has picked a side.
TYPE3_TOKENS = {
    "kr": [r"분할\s*거래"],
    "en": [r"split[-\s]transactions?"],
}
STRUCTURING_TOKENS = {
    "kr": [r"(?<![A-Za-z])structuring(?![A-Za-z])", r"구조화"],
    "en": [r"(?<![-\w])structuring(?![-\w])"],
}

JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def prose(text: str) -> str:
    """The user's message without any JSON payload it pastes in.

    An STR draft carries `"PrimarySuspicionType": "Split Transaction"` as data, which
    is the §VI classification of the report and not the question's own wording.
    """
    return JSON_BLOCK.sub(" ", text or "")


def _hits(text: str, table: list[tuple[str, str]]) -> list[str]:
    return [f"{pattern!r} ({why})" for pattern, why in table if re.search(pattern, text)]


def _side(calls) -> tuple[bool, bool]:
    """(the gold selects structuring, the gold selects HOFINET fraud type 3)."""
    structuring = type3 = False
    for tool, args in calls:
        for key, value in (args or {}).items():
            token = value.strip().lower() if isinstance(value, str) else value
            if token in STRUCTURING_VALUES.get((tool, key), ()):
                structuring = True
            if value in TYPE3_VALUES.get((tool, key), ()):
                type3 = True
    return structuring, type3


def screen_text(text: str, lang: str, calls=()) -> list[str]:
    """Every convention violation in one question or turn message.

    `calls` is (tool, arguments) for the gold of that question or that turn; it decides
    which side of the structuring / fraud-type-3 collision the text has to stay on.
    """
    body = prose(text)
    found = _hits(body, BANNED_KR if lang == "kr" else BANNED_EN)
    structuring, type3 = _side(calls)
    if structuring and not type3:
        found += [f"{p!r} (the gold selects the structuring pattern, so the question "
                  f"names `structuring`, not HOFINET fraud type 3)"
                  for p in TYPE3_TOKENS[lang] if re.search(p, body, re.I)]
    if type3 and not structuring:
        found += [f"{p!r} (the gold selects HOFINET fraud type 3, so the question names "
                  f"it, not the structuring pattern)"
                  for p in STRUCTURING_TOKENS[lang] if re.search(p, body, re.I)]
    return found


def single_turn_calls(case: dict):
    for tool, checks in ((case.get("expected") or {}).get("param_checks") or {}).items():
        if isinstance(checks, dict):
            yield tool, checks


def screen_single_turn(bench, lang: str) -> list[str]:
    """`bench` is a `common.Bench`."""
    out = []
    for _, case in bench.cases():
        for hit in screen_text(case["question"], lang, list(single_turn_calls(case))):
            out.append(f"{case['id']} ({lang}): {hit}")
    return out


def screen_multiturn(scenarios: list[dict], lang: str) -> list[str]:
    out = []
    for scenario in scenarios:
        for turn in scenario["turns"]:
            calls = [(c["name"], c.get("arguments") or {})
                     for c in (turn.get("tool_calls") or [])]
            for hit in screen_text(turn.get("content", ""), lang, calls):
                out.append(f"{scenario['id']}#t{turn['turn']} ({lang}): {hit}")
    return out


def convention_table() -> str:
    rows = ["| pattern | Korean question | English question |", "|---|---|---|"]
    rows += [f"| `{name}` | {spell['kr']} | {spell['en']} |" for name, spell in CONVENTION.items()]
    return "\n".join(rows)
