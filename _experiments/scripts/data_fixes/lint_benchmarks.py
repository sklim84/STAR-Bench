"""Pre-flight data linter for the single-turn benchmark (C1-011).

The old `check_hofinet_compliance.py` read Korean parameter keys that the data had
not used since the April re-keying, so it reported "0 violations" both for HEAD
and for a copy with the keys put back in Korean, and it never checked whether an
account exists, whether an amount is one of the 48 HOFINET holds, or whether a
gold key is a property of the tool at all. This replaces it. It exits non-zero on
any violation, so it can gate a re-run.

    python -m _experiments.scripts.data_fixes.lint_benchmarks
    python -m _experiments.scripts.data_fixes.lint_benchmarks --benchmark benchmarks --no-db

Checks, per benchmark directory:

  schema_key          every gold key is a schema property of that tool or a known check
  english_key         no Korean key anywhere in the gold
  tool_name           every gold tool exists in the platform schema
  required_enum       an enum-valued gold argument is one of the schema's values
  bound               sample_size <= 5000, top_k <= 100, limit <= 100, hops <= 5
  hofinet_value       bank ids, time slots, fund and media types, fraud types, dates and
                      predict_fraud amounts are values HOFINET holds, and no predict_fraud
                      gold asks for the fraud risk of fund type 4
  account_exists      every account argument appears in HOFINET (needs the database)
  sql_column          every sql_conditions column is a column of `hofinet`
  reference_sql       every query_transactions case carries an executable reference SQL
  clarification       a clarification case expects no tool and no parameter checks
  alternatives        alternatives are a list of {abstain} / {expect_clarification} /
                      {tools_must_include, param_checks} blocks
  obsolete_name       a question naming an official fraud type does not name a different one
  duplicate_question  no two cases in one language ask the same question
  kr_en_parity        the two directories hold the same ids, gold, difficulty and notes
  terminology         one spelling per pattern term, and a question whose gold selects the
                      structuring pattern does not name HOFINET fraud type 3, or the other
                      way round (`terminology.py`, L1-010)
  catalog_gold        an FIU keyword or glossary term the gold pins selects at least one
                      catalog row, and the same rows however it is capitalised, so its
                      spelling cannot decide the score (L1-019)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = "_experiments.scripts.data_fixes"

from . import terminology
from .common import Bench, EN, KR, dump_json

SENDER_BANKS = {102, 103, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120,
                121, 122, 123, 124, 125, 128, 129, 130, 131, 132, 133, 134, 135, 136, 143, 144, 145,
                146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161}
RECEIVER_BANKS = {101, 102, 103, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118,
                  119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135,
                  136, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157,
                  158, 159, 160}
TIME_SLOTS = {0, 3, 6, 9, 12, 15, 18, 21}
FUND_TYPES = {0, 1, 3, 4}
MEDIA_TYPES = {1, 2, 3, 4, 5, 6, 7}
FRAUD_TYPES = {1, 2, 3, 4, 5, 7}
AMOUNTS = {1, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 20000, 30000, 40000, 50000,
           60000, 90000, 100000, 200000, 300000, 400000, 500000, 600000, 700000, 900000, 1000000,
           2000000, 3000000, 4000000, 5000000, 6000000, 7000000, 8000000, 9000000, 10000000, 20000000,
           30000000, 40000000, 50000000, 60000000, 70000000, 80000000, 90000000, 100000000, 200000000,
           300000000, 400000000, 500000000}
COLUMNS = {"date", "time_slot", "sender_bank", "sender_acc", "receiver_bank", "receiver_acc",
           "fund_type", "media_type", "amount", "is_fraud", "fraud_type", "fraud_description"}
DATE_RANGE = (20210901, 20241231)
BOUNDS = {("rank_risky_transactions", "sample_size"): 5000, ("rank_risky_transactions", "top_k"): 100,
          ("analyze_network", "hops_min"): 5, ("analyze_network", "hops_max"): 5}
LIMIT_MAX = 100
CHECK_KEYS = {"sql_conditions", "sql_valid", "sql_contains", "hops_min", "hops_max", "result_contains",
              "result_row_count_min", "result_row_count_max"}
GOLD_KEYS = {"primary_tool", "tools_must_include", "param_checks", "tool_order", "alternatives",
             "expect_clarification", "reference_calls"}
FRAUD_LABEL = {1: "갑작스러운 거래패턴의 변화", 2: "신규 수신처 거래", 3: "분할 거래",
               4: "다중거래의 동시 요청", 5: "거액 입금 후 당일 인출", 7: "심야/새벽 대량 거래"}
DATE_KEYS = {"date_from", "date_to", "period1_start", "period1_end", "period2_start", "period2_end"}
HANGUL = re.compile(r"[가-힣]")


class Report:
    def __init__(self):
        self.violations: list[dict] = []
        self.skipped: list[str] = []

    def add(self, check: str, case_id: str, lang: str, detail: str) -> None:
        self.violations.append({"check": check, "case_id": case_id, "lang": lang, "detail": detail})

    def by_check(self) -> dict[str, int]:
        out: dict[str, int] = defaultdict(int)
        for v in self.violations:
            out[v["check"]] += 1
        return dict(sorted(out.items()))


def account_ids(bench: Bench) -> set[int]:
    out = set()
    for _, case in bench.cases():
        for checks in (case["expected"].get("param_checks") or {}).values():
            if not isinstance(checks, dict):
                continue
            for key in ("account_id", "account_a", "account_b"):
                if isinstance(checks.get(key), int):
                    out.add(checks[key])
    return out


def known_accounts(ids: set[int]):
    """Accounts of `ids` that appear in HOFINET, or None when no database is available."""
    if not ids:
        return set()
    try:
        from _experiments.scripts._platform import ensure_platform_on_path  # noqa: PLC0415

        ensure_platform_on_path()
        from src.data.db import query  # noqa: PLC0415
    except Exception:
        return None
    listed = ", ".join(str(int(i)) for i in sorted(ids))
    rows = query(f"SELECT DISTINCT sender_acc AS acc FROM hofinet WHERE sender_acc IN ({listed}) "
                 f"UNION SELECT DISTINCT receiver_acc FROM hofinet WHERE receiver_acc IN ({listed})")
    return {int(v) for v in rows["acc"].tolist()}


# The arguments the scorer resolves through the platform catalog (scoring/catalog.py).
CATALOG_ARGS = {"lookup_fiu_reference_types": ("keyword",), "get_aml_glossary": ("term",)}


def catalog_rows():
    """The platform's catalog lookups, or None when the platform is not importable."""
    try:
        from _experiments.scripts._platform import ensure_platform_on_path  # noqa: PLC0415

        ensure_platform_on_path()
        from src.features.aml_reference import (  # noqa: PLC0415
            get_aml_glossary,
            lookup_fiu_reference_types,
        )
    except Exception:
        return None

    def rows(tool: str, value: str) -> frozenset:
        if tool == "lookup_fiu_reference_types":
            return frozenset((r["industry"], r["category"], r["no"])
                             for r in lookup_fiu_reference_types(value, None))
        found = get_aml_glossary(value)
        return frozenset() if found is None else frozenset({found["term"]})

    return rows


def catalog_problems(rows, tool: str, value) -> list[str]:
    if not isinstance(value, str):
        return [f"{tool}: gold {value!r} is not a string"]
    selected = rows(tool, value)
    if not selected:
        return [f"{tool}({value!r}) selects no catalog row"]
    return [f"{tool}({value!r}): {variant!r} selects a different row set, so the spelling "
            f"decides the score"
            for variant in (value.lower(), value.upper(), value.title())
            if rows(tool, variant) != selected]


def check_value(report: Report, case_id: str, lang: str, tool: str, key: str, value) -> None:
    if key in ("sender_bank",) and value not in SENDER_BANKS:
        report.add("hofinet_value", case_id, lang, f"{tool}.{key}={value} is not a HOFINET sender bank")
    if key == "bank_id" and value not in SENDER_BANKS | RECEIVER_BANKS:
        report.add("hofinet_value", case_id, lang, f"{tool}.{key}={value} is not a HOFINET bank")
    if key == "receiver_bank" and value not in RECEIVER_BANKS:
        report.add("hofinet_value", case_id, lang, f"{tool}.{key}={value} is not a HOFINET receiver bank")
    if key == "time_slot" and value not in TIME_SLOTS:
        report.add("hofinet_value", case_id, lang, f"{tool}.{key}={value} is not a HOFINET time slot")
    if key == "fund_type" and value not in FUND_TYPES:
        report.add("hofinet_value", case_id, lang, f"{tool}.{key}={value} is not a HOFINET fund type")
    if key == "media_type" and value not in MEDIA_TYPES:
        report.add("hofinet_value", case_id, lang, f"{tool}.{key}={value} is not a HOFINET media type")
    if key == "fraud_type" and value not in FRAUD_TYPES:
        report.add("hofinet_value", case_id, lang, f"{tool}.{key}={value} is not a HOFINET fraud type")
    if tool == "predict_fraud" and key == "amount" and value not in AMOUNTS:
        report.add("hofinet_value", case_id, lang,
                   f"{tool}.{key}={value} is not one of the 48 amounts HOFINET holds")
    if tool == "predict_fraud" and key == "fund_type" and value == 4:
        report.add("hofinet_value", case_id, lang,
                   f"{tool}.{key}=4 carries no fraud label anywhere in HOFINET, so a fraud-risk "
                   f"question about it has no possible answer (C1-003)")
    if key in DATE_KEYS and isinstance(value, int) and not DATE_RANGE[0] <= value <= DATE_RANGE[1]:
        report.add("hofinet_value", case_id, lang, f"{tool}.{key}={value} is outside 20210901-20241231")
    if key == "limit" and isinstance(value, int) and value > LIMIT_MAX:
        report.add("bound", case_id, lang, f"{tool}.{key}={value} exceeds the maximum of {LIMIT_MAX}")
    bound = BOUNDS.get((tool, key))
    if bound is not None and isinstance(value, int) and value > bound:
        report.add("bound", case_id, lang, f"{tool}.{key}={value} exceeds the schema maximum {bound}")


def check_spec(report: Report, schemas, case_id: str, lang: str, spec: dict, label: str) -> None:
    tools = list(spec.get("tools_must_include") or [])
    primary = spec.get("primary_tool") or ""
    if primary and primary not in tools:
        tools.insert(0, primary)
    for tool in tools:
        if schemas is not None and tool not in schemas:
            report.add("tool_name", case_id, lang, f"{label}{tool} is not a platform tool")
    checks = spec.get("param_checks") or {}
    if not isinstance(checks, dict):
        report.add("schema_key", case_id, lang, f"{label}param_checks is not an object")
        return
    for tool, spec_checks in checks.items():
        if tool not in tools:
            report.add("schema_key", case_id, lang, f"{label}param_checks names {tool}, which is not a gold tool")
        if not isinstance(spec_checks, dict):
            report.add("schema_key", case_id, lang, f"{label}param_checks.{tool} is not an object")
            continue
        schema = schemas.get(tool) if schemas is not None else None
        for key, value in spec_checks.items():
            if HANGUL.search(key):
                report.add("english_key", case_id, lang, f"{label}{tool}.{key} is a Korean key")
            if key in CHECK_KEYS:
                bound = BOUNDS.get((tool, key))
                if bound is not None and isinstance(value, int) and value > bound:
                    report.add("bound", case_id, lang,
                               f"{label}{tool}.{key}={value} exceeds the schema maximum {bound}")
                if key == "sql_contains":
                    report.add("schema_key", case_id, lang,
                               f"{label}{tool}.sql_contains is the pre-Contract-1 substring check")
                if key == "sql_conditions":
                    for cond in value if isinstance(value, list) else []:
                        column = str((cond or {}).get("column", ""))
                        if column not in COLUMNS:
                            report.add("sql_column", case_id, lang,
                                       f"{label}sql_conditions names {column!r}, not a hofinet column")
                continue
            if schema is not None and key not in schema.properties:
                report.add("schema_key", case_id, lang, f"{label}{tool}.{key} is not a property of {tool}")
                continue
            prop = schema.prop(key) if schema is not None else {}
            if "enum" in prop and value not in prop["enum"]:
                report.add("required_enum", case_id, lang,
                           f"{label}{tool}.{key}={value!r} is not one of {prop['enum']}")
            check_value(report, case_id, lang, tool, key, value)


def lint_terminology(bench: Bench, report: Report) -> None:
    """One spelling per pattern, and no structuring / fraud-type-3 collision (L1-010)."""
    for _, case in bench.cases():
        for hit in terminology.screen_text(case["question"], bench.lang,
                                           list(terminology.single_turn_calls(case))):
            report.add("terminology", case["id"], bench.lang, hit)


def lint_catalog_gold(bench: Bench, rows, report: Report) -> None:
    """An FIU keyword or glossary term the gold pins cannot be decided by its case (L1-019)."""
    if rows is None:
        return
    for _, case in bench.cases():
        for tool, checks in (case["expected"].get("param_checks") or {}).items():
            if not isinstance(checks, dict):
                continue
            for key in CATALOG_ARGS.get(tool, ()):
                if key in checks:
                    for detail in catalog_problems(rows, tool, checks[key]):
                        report.add("catalog_gold", case["id"], bench.lang, detail)


def lint(bench: Bench, schemas, accounts, report: Report) -> None:
    lang = bench.lang
    seen_questions: dict[str, str] = {}
    for _, case in bench.cases():
        case_id = case["id"]
        expected = case.get("expected") or {}
        for key in expected:
            if key not in GOLD_KEYS:
                report.add("schema_key", case_id, lang, f"expected.{key} is not a Contract 1 field")
        check_spec(report, schemas, case_id, lang, expected, "")

        if expected.get("expect_clarification"):
            if expected.get("tools_must_include") or expected.get("primary_tool"):
                report.add("clarification", case_id, lang, "a clarification case expects a tool call")
            if expected.get("param_checks"):
                report.add("clarification", case_id, lang, "a clarification case carries parameter checks")

        alternatives = expected.get("alternatives")
        if alternatives is not None:
            if not isinstance(alternatives, list) or not alternatives:
                report.add("alternatives", case_id, lang, "alternatives is not a non-empty list")
            else:
                for alt in alternatives:
                    if not isinstance(alt, dict):
                        report.add("alternatives", case_id, lang, "an alternative is not an object")
                    elif alt.get("abstain") or alt.get("expect_clarification"):
                        continue
                    elif not alt.get("tools_must_include"):
                        report.add("alternatives", case_id, lang,
                                   "an alternative has neither abstain nor tools_must_include")
                    else:
                        check_spec(report, schemas, case_id, lang, alt, "alternative: ")

        checks = expected.get("param_checks") or {}
        wants_sql = "query_transactions" in checks
        reference = (expected.get("reference_calls") or {}).get("query_transactions") or {}
        if wants_sql and not str(reference.get("sql", "")).strip():
            report.add("reference_sql", case_id, lang,
                       "a query_transactions case has no expected.reference_calls.query_transactions.sql")
        if not wants_sql and reference:
            report.add("reference_sql", case_id, lang, "reference_calls holds SQL for a case with no SQL check")

        if accounts is not None:
            for tool, spec_checks in checks.items():
                if not isinstance(spec_checks, dict):
                    continue
                for key in ("account_id", "account_a", "account_b"):
                    value = spec_checks.get(key)
                    if isinstance(value, int) and value not in accounts:
                        report.add("account_exists", case_id, lang,
                                   f"{tool}.{key}={value} is not an account in HOFINET")

        code = (checks.get("get_fraud_type_summary") or {}).get("fraud_type")
        if code in FRAUD_LABEL:
            squashed = case["question"].replace(" ", "")
            wrong = [c for c, label in FRAUD_LABEL.items()
                     if c != code and label.replace(" ", "") in squashed]
            if wrong and FRAUD_LABEL[code].replace(" ", "") not in squashed:
                report.add("obsolete_name", case_id, lang,
                           f"gold fraud_type {code} but the question names type {wrong}")

        question = case["question"].strip()
        if question in seen_questions:
            report.add("duplicate_question", case_id, lang,
                       f"same question as {seen_questions[question]}")
        else:
            seen_questions[question] = case_id


def lint_parity(kr: Bench, en: Bench, report: Report) -> None:
    kr_by, en_by = kr.by_id(), en.by_id()
    for case_id in sorted(set(kr_by) ^ set(en_by)):
        report.add("kr_en_parity", case_id, "kr+en", "the case exists in only one language")
    for case_id in sorted(set(kr_by) & set(en_by)):
        a, b = kr_by[case_id], en_by[case_id]
        if a["expected"] != b["expected"]:
            report.add("kr_en_parity", case_id, "kr+en", "the gold differs between the two languages")
        if a.get("difficulty") != b.get("difficulty"):
            report.add("kr_en_parity", case_id, "kr+en", "the difficulty differs between the two languages")
        if a.get("note") != b.get("note"):
            report.add("kr_en_parity", case_id, "kr+en", "the note differs between the two languages")
        if kr.file_of()[case_id] != en.file_of()[case_id]:
            report.add("kr_en_parity", case_id, "kr+en", "the case sits in a different file per language")
        if HANGUL.search(b["question"]):
            report.add("kr_en_parity", case_id, "en", "the English question carries Korean text")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pre-flight data linter for the single-turn benchmark.")
    ap.add_argument("--benchmark", default=str(KR))
    ap.add_argument("--benchmark-en", default=str(EN))
    ap.add_argument("--no-db", action="store_true", help="skip the account existence check")
    ap.add_argument("--out")
    args = ap.parse_args(argv)

    kr = Bench.load(args.benchmark, "kr")
    en = Bench.load(args.benchmark_en, "en")
    report = Report()

    try:
        from _experiments.scripts.scoring.schema import load_tool_schemas  # noqa: PLC0415

        schemas = load_tool_schemas()
    except Exception as exc:
        schemas = None
        report.skipped.append(f"tool schema unavailable ({exc}); schema_key and required_enum not checked")

    accounts = None
    if args.no_db:
        report.skipped.append("account existence not checked (--no-db)")
    else:
        accounts = known_accounts(account_ids(kr) | account_ids(en))
        if accounts is None:
            report.skipped.append("account existence not checked (no HOFINET database)")

    rows = catalog_rows()
    if rows is None:
        report.skipped.append("catalog-valued gold not checked (platform not importable)")

    lint(kr, schemas, accounts, report)
    lint(en, schemas, accounts, report)
    lint_parity(kr, en, report)
    for bench in (kr, en):
        lint_terminology(bench, report)
        lint_catalog_gold(bench, rows, report)

    payload = {"benchmark": args.benchmark, "benchmark_en": args.benchmark_en,
               "n_cases": kr.n_cases(), "n_violations": len(report.violations),
               "by_check": report.by_check(), "skipped": report.skipped,
               "violations": report.violations}
    if args.out:
        dump_json(args.out, payload)
    print(f"{kr.n_cases()} cases, {len(report.violations)} violations")
    for check, n in report.by_check().items():
        print(f"  {check}: {n}")
    for row in report.violations[:60]:
        print(f"    {row['case_id']} ({row['lang']}) {row['check']}: {row['detail']}")
    for note in report.skipped:
        print(f"  skipped: {note}")
    return 1 if report.violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
