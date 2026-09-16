"""The written report, the allow-list and the gate framework itself."""

from __future__ import annotations

import json

from _experiments.scripts.preflight import gold, report
from _experiments.scripts.preflight.gate import Check, GateResult


def _result(ok: bool) -> GateResult:
    return GateResult("demo", 1, "demo gate", [
        Check("first check", True, "fine", "python -m demo.first"),
        Check("second check", ok, "st_x: the gold names a tool that does not exist",
              "python -m demo.second"),
    ], 1.5)


def test_a_failing_gate_makes_the_line_say_fail():
    assert _result(False).line().startswith("[FAIL]")
    assert _result(True).line().startswith("[PASS]")
    assert "1/2" in _result(False).line()


def test_a_skipped_gate_counts_as_passing_but_says_skip():
    skipped = GateResult("demo", 6, "canary run", [], 0.0, skipped=True)
    assert skipped.ok
    assert skipped.line().startswith("[SKIP]")


def test_the_report_names_the_failing_check_and_its_command(tmp_path):
    path = report.write_markdown([_result(False)], command="preflight --all",
                                 versions={"star_bench_commit": "abc123",
                                           "platform_commit": "def456",
                                           "star_bench_root": "/repo"},
                                 path=tmp_path / "preflight_report.md")
    text = path.read_text(encoding="utf-8")
    assert "FAILED" in text
    assert "## What failed" in text
    assert "python -m demo.second" in text
    assert "st_x: the gold names a tool that does not exist" in text
    assert "abc123" in text and "def456" in text


def test_the_report_carries_the_per_tool_table(tmp_path):
    result = GateResult("gold", 4, "gold answers", [
        Check("gold calls execute on benchmarks", True, "ok", "cmd",
              {"per_tool": {"get_statistics": {"ok": 70, "empty": 0, "error": 0, "skipped": 0}}}),
    ], 1.0)
    path = report.write_markdown([result], command="preflight --all", versions={},
                                 path=tmp_path / "r.md")
    text = path.read_text(encoding="utf-8")
    assert "| get_statistics | 70 | 0 | 0 | 0 |" in text


def test_the_json_report_carries_every_gate_and_its_checks():
    payload = report.as_json([_result(False)], command="preflight --all", versions={})
    assert payload["ok"] is False
    assert payload["gates"][0]["checks"][1]["command"] == "python -m demo.second"


def test_every_allow_list_entry_says_why():
    doc = json.loads(gold.ALLOW_PATH.read_text(encoding="utf-8"))
    assert doc["entries"], "the allow-list is empty"
    for entry in doc["entries"]:
        assert entry["kind"] in ("single", "multiturn")
        assert entry["status"] in ("empty", "skipped")
        assert entry["reason"].strip()
        assert not entry["reason"].startswith(("TO BE EXPLAINED", "UNCLASSIFIED")), entry


def test_the_allow_list_only_covers_ring_layering_and_the_chained_call():
    """Anything else answering nothing is a data defect, not a fact about HOFINET."""
    doc = json.loads(gold.ALLOW_PATH.read_text(encoding="utf-8"))
    for entry in doc["entries"]:
        if entry["status"] == "empty":
            assert entry["pattern_type"] in ("ring", "layering"), entry
        else:
            assert entry["tool"] == "analyze_network", entry


def test_a_gold_self_test_report_with_a_defect_is_read_as_a_defect():
    body = {"single": {"n": 2, "n_perfect": 1,
                       "defects": [{"case_id": "st_x", "error_type": "wrong_func",
                                    "render_problems": [], "failed_checks": []}],
                       "advisories": [{"case_id": "st_y"}]}}
    defects = gold._defects(body)
    assert [d["case_id"] for d in defects] == ["st_x"]
    assert gold._describe(defects[0]) == "st_x: wrong_func"


def test_an_advisory_is_not_a_defect():
    body = {"oracle": {"defects": [], "advisories": [{"case_id": "st_y"}]},
            "e2e": {"defects": [], "advisories": []}}
    assert gold._defects(body) == []


# ---------------------------------------------------------------------------
# Gate 2: a skipped test is not a passing test
# ---------------------------------------------------------------------------

from _experiments.scripts.preflight import code_tests  # noqa: E402

_JINJA_SKIP = ("SKIPPED [1] _experiments/scripts/tests_runner/test_templates.py:11: "
               "could not import 'jinja2': No module named 'jinja2'")
_NEO4J_SKIP = ("SKIPPED [8] tests/test_graph_db.py:31: neo4j driver not installed "
               "(optional: the tool layer never needs it)")


def test_a_skip_for_a_missing_package_is_not_allowed():
    found = code_tests.unexplained_skips(_JINJA_SKIP + "\n1 passed, 1 skipped in 0.1s\n")
    assert [w for _c, w, _r in found] == ["_experiments/scripts/tests_runner/test_templates.py:11"]


def test_the_release_skips_are_allowed():
    assert code_tests.unexplained_skips(_NEO4J_SKIP + "\n1 passed, 8 skipped\n") == []


def test_every_allowed_reason_says_why():
    for entry in code_tests.allowed_reasons():
        assert entry["reason_contains"].strip()
        assert entry["why"].strip()


def test_a_suite_that_skips_for_a_missing_package_fails_the_check(monkeypatch):
    from _experiments.scripts.preflight import gate

    def fake_run_command(argv, **kwargs):
        return gate.CommandRun(" ".join(argv), 0, "1 passed, 1 skipped in 0.1s\n"
                               + _JINJA_SKIP + "\n", "", 0.1)

    monkeypatch.setattr(code_tests, "run_command", fake_run_command)
    check = code_tests._pytest(gate.Context(), "runner test suite", ["-q"])
    assert not check.ok, "an exit status of 0 with a skipped test must not pass gate 2"
    assert "test_templates.py" in check.detail


def test_a_suite_with_only_allowed_skips_passes_the_check(monkeypatch):
    from _experiments.scripts.preflight import gate

    def fake_run_command(argv, **kwargs):
        return gate.CommandRun(" ".join(argv), 0, "495 passed, 8 skipped in 1s\n"
                               + _NEO4J_SKIP + "\n", "", 0.1)

    monkeypatch.setattr(code_tests, "run_command", fake_run_command)
    check = code_tests._pytest(gate.Context(), "platform test suite", ["-q"])
    assert check.ok
