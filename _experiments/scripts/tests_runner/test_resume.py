"""Fresh output directories, resume refusals and partial runs (C2-014, C2-015, L5-027)."""

from __future__ import annotations

import json

import pytest

from _experiments.scripts import benchmark
from _experiments.scripts.runner import records
from _experiments.scripts.tests_runner.conftest import base_argv
from _experiments.scripts.tests_runner.mock_server import text


def _argv(server, bench, out, extra=()):
    return base_argv(server, out) + ["--cases-dir", str(bench)] + list(extra)


def test_resume_refuses_when_every_case_is_already_there(server, single_benchmark, tmp_path,
                                                        fake_tools):
    server.always(text("끝"))
    out = tmp_path / "r"
    benchmark.main(_argv(server, single_benchmark, out), executor=fake_tools)
    with pytest.raises(records.ResumeRefused, match="all 3 expected records"):
        benchmark.main(_argv(server, single_benchmark, out, ["--resume"]), executor=fake_tools)


def test_resume_runs_only_the_cases_that_are_missing(server, single_benchmark, tmp_path,
                                                     fake_tools):
    server.always(text("끝"))
    out = tmp_path / "r"
    benchmark.main(_argv(server, single_benchmark, out, ["--limit", "1"]), executor=fake_tools)
    assert len(list(out.glob("*.jsonl"))) == 1
    benchmark.main(_argv(server, single_benchmark, out, ["--resume"]), executor=fake_tools)
    recs = [r for f in sorted(out.glob("*.jsonl")) for r in records.read_records(f)]
    assert sorted(r["case_id"] for r in recs) == ["st_001", "st_002", "st_003"]
    assert len({r["run_id"] for r in recs}) == 2, "each run keeps its own id"


def test_resume_refuses_a_directory_that_belongs_to_another_benchmark(
        server, single_benchmark, multiturn_benchmark, tmp_path, fake_tools):
    server.always(text("끝"))
    out = tmp_path / "r"
    benchmark.main(_argv(server, single_benchmark, out, ["--limit", "1"]), executor=fake_tools)
    other = json.loads((single_benchmark / "cases_multi_tool.json").read_text(encoding="utf-8"))
    other[0]["id"] = "st_999"
    (single_benchmark / "cases_multi_tool.json").write_text(json.dumps(other), encoding="utf-8")
    with pytest.raises(records.ResumeRefused, match="does not contain"):
        benchmark.main(_argv(server, single_benchmark, out, ["--resume"]), executor=fake_tools)


def test_a_case_filter_without_partial_is_refused(server, single_benchmark, tmp_path, fake_tools):
    server.always(text("끝"))
    with pytest.raises(SystemExit, match="--partial"):
        benchmark.main(_argv(server, single_benchmark, tmp_path / "r",
                             ["--case-ids", "st_001"]), executor=fake_tools)


def test_a_partial_run_writes_its_own_file_and_is_not_verified_as_complete(
        server, single_benchmark, tmp_path, fake_tools, capsys):
    server.always(text("끝"))
    out = tmp_path / "r"
    benchmark.main(_argv(server, single_benchmark, out,
                         ["--case-ids", "st_001,st_002", "--partial"]), executor=fake_tools)
    files = list(out.glob("*.jsonl"))
    assert len(files) == 1 and files[0].name.endswith(".partial.jsonl")
    assert "INCOMPLETE" not in capsys.readouterr().out
    manifest = json.loads(next(out.glob("*.manifest.json")).read_text(encoding="utf-8"))
    assert manifest["partial"] is True


def test_resume_refuses_a_directory_that_holds_a_partial_file(server, single_benchmark, tmp_path,
                                                              fake_tools):
    server.always(text("끝"))
    out = tmp_path / "r"
    benchmark.main(_argv(server, single_benchmark, out, ["--case-ids", "st_001", "--partial"]),
                   executor=fake_tools)
    with pytest.raises(records.ResumeRefused, match="partial run files"):
        benchmark.main(_argv(server, single_benchmark, out, ["--resume"]), executor=fake_tools)


def test_a_case_id_the_benchmark_does_not_have_is_refused(server, single_benchmark, tmp_path,
                                                          fake_tools):
    server.always(text("끝"))
    with pytest.raises(SystemExit, match="does not contain"):
        benchmark.main(_argv(server, single_benchmark, tmp_path / "r",
                             ["--case-ids", "st_404", "--partial"]), executor=fake_tools)


def test_a_run_that_lost_a_record_is_incomplete_and_exits_non_zero(
        server, single_benchmark, tmp_path, fake_tools, monkeypatch, capsys):
    from _experiments.scripts.runner import parallel

    real = parallel.run_jobs

    def drop_the_last_case(items, work, *, concurrency, on_result):
        real(list(items)[:-1], work, concurrency=concurrency, on_result=on_result)

    monkeypatch.setattr(benchmark.parallel, "run_jobs", drop_the_last_case)
    server.always(text("끝"))
    rc = benchmark.main(_argv(server, single_benchmark, tmp_path / "r"), executor=fake_tools)
    assert rc == 1
    assert "INCOMPLETE" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# `--limit N` is a mode, not a broken full run
# ---------------------------------------------------------------------------

def test_a_limited_run_is_complete_against_its_own_cases(server, single_benchmark, tmp_path,
                                                         fake_tools, capsys):
    server.always(text("끝"))
    rc = benchmark.main(_argv(server, single_benchmark, tmp_path / "r", ["--limit", "2"]),
                        executor=fake_tools)
    out = capsys.readouterr().out
    assert rc == 0, "a smoke run of the first N cases is not an incomplete run"
    assert "records: 2/2 (complete" in out
    assert "limited to 2 of 3" in out


def test_a_limited_run_records_the_limit_in_its_manifest(server, single_benchmark, tmp_path,
                                                         fake_tools):
    server.always(text("끝"))
    out = tmp_path / "r"
    benchmark.main(_argv(server, single_benchmark, out, ["--limit", "2"]), executor=fake_tools)
    manifest = json.loads(next(out.glob("*.manifest.json")).read_text(encoding="utf-8"))
    assert manifest["limit"] == 2
    assert manifest["n_cases_run"] == 2
    assert manifest["n_cases_benchmark"] == 3
    assert manifest["partial"] is False


def test_a_limited_run_covers_the_first_n_cases_of_the_benchmark(server, single_benchmark,
                                                                 tmp_path, fake_tools):
    server.always(text("끝"))
    out = tmp_path / "r"
    benchmark.main(_argv(server, single_benchmark, out, ["--limit", "2"]), executor=fake_tools)
    recs = [r for f in sorted(out.glob("*.jsonl")) for r in records.read_records(f)]
    assert [r["case_id"] for r in recs] == ["st_001", "st_002"]


def test_limit_and_case_ids_are_not_combined(server, single_benchmark, tmp_path, fake_tools):
    server.always(text("끝"))
    with pytest.raises(SystemExit, match="pass one of them"):
        benchmark.main(_argv(server, single_benchmark, tmp_path / "r",
                             ["--limit", "1", "--case-ids", "st_001", "--partial"]),
                       executor=fake_tools)


def test_a_resumed_run_is_complete_when_the_directory_covers_the_benchmark(
        server, single_benchmark, tmp_path, fake_tools, capsys):
    server.always(text("끝"))
    out = tmp_path / "r"
    benchmark.main(_argv(server, single_benchmark, out, ["--limit", "1"]), executor=fake_tools)
    capsys.readouterr()
    rc = benchmark.main(_argv(server, single_benchmark, out, ["--resume"]), executor=fake_tools)
    assert rc == 0
    assert "records: 3/3 (complete" in capsys.readouterr().out


def test_run_ids_carry_the_arm_the_setting_and_a_timestamp(server, single_benchmark, tmp_path,
                                                           fake_tools):
    server.always(text("끝"))
    out = tmp_path / "r"
    benchmark.main(_argv(server, single_benchmark, out), executor=fake_tools)
    run_id = next(out.glob("*.jsonl")).stem
    assert "kr" in run_id and "single" in run_id
    assert run_id.count("-") >= 3


# ---------------------------------------------------------------------------
# A resume continues one arm; it does not merge two (V-03)
#
# `benchmarks` and `benchmarks_en` carry the same 1,258 case ids by design, so a
# membership test cannot separate them: resuming a Korean run with
# `--cases-dir benchmarks_en` was accepted, the file then held both arms and the
# manifest claimed one. Every field that makes a run a different arm is checked.
# ---------------------------------------------------------------------------

@pytest.fixture
def english_benchmark(tmp_path, single_benchmark):
    """The same case ids, translated: a different directory and a different hash."""
    path = tmp_path / "benchmarks_en"
    path.mkdir()
    cases = json.loads((single_benchmark / "cases_multi_tool.json").read_text(encoding="utf-8"))
    english = ["How many suspicious transactions last month?",
               "Show the profile of account 9000000000000002",
               "What is money laundering?"]
    for case, question in zip(cases, english):
        case["question"] = question
    (path / "cases_multi_tool.json").write_text(json.dumps(cases, ensure_ascii=False),
                                                encoding="utf-8")
    return path


def _first_run(server, bench, out, fake_tools, extra=()):
    server.always(text("끝"))
    benchmark.main(_argv(server, bench, out, ["--limit", "1", *extra]), executor=fake_tools)
    return out


def test_resume_refuses_the_other_language_arm(server, single_benchmark, english_benchmark,
                                               tmp_path, fake_tools):
    """The reported hole: three Korean records, resumed with --cases-dir benchmarks_en."""
    out = _first_run(server, single_benchmark, tmp_path / "r", fake_tools)
    with pytest.raises(records.ResumeRefused) as excinfo:
        benchmark.main(_argv(server, english_benchmark, out, ["--resume"]), executor=fake_tools)
    message = str(excinfo.value)
    assert "benchmark_dir" in message and "--cases-dir" in message
    assert "benchmark_sha256" in message
    recs = [r for f in sorted(out.glob("*.jsonl")) for r in records.read_records(f)]
    assert {r["provenance"]["benchmark_dir"] for r in recs} == {"benchmarks"}, \
        "the refused run must not have written anything"


def test_resume_refuses_the_same_questions_from_another_copy_of_the_benchmark(
        server, single_benchmark, tmp_path, fake_tools):
    """Same directory name, edited content: the hash is what catches it."""
    out = _first_run(server, single_benchmark, tmp_path / "r", fake_tools)
    cases = json.loads((single_benchmark / "cases_multi_tool.json").read_text(encoding="utf-8"))
    cases[2]["question"] = cases[2]["question"] + " 자세히"
    (single_benchmark / "cases_multi_tool.json").write_text(json.dumps(cases, ensure_ascii=False),
                                                            encoding="utf-8")
    with pytest.raises(records.ResumeRefused, match="benchmark_sha256"):
        benchmark.main(_argv(server, single_benchmark, out, ["--resume"]), executor=fake_tools)


def test_resume_refuses_another_schema_arm(server, single_benchmark, tmp_path, fake_tools):
    out = _first_run(server, single_benchmark, tmp_path / "r", fake_tools)
    argv = base_argv(server, out, tools_lang="en") + ["--cases-dir", str(single_benchmark),
                                                     "--resume"]
    with pytest.raises(records.ResumeRefused, match="tools_lang"):
        benchmark.main(argv, executor=fake_tools)


def test_resume_refuses_another_prompt_variant(server, single_benchmark, tmp_path, fake_tools):
    out = _first_run(server, single_benchmark, tmp_path / "r", fake_tools)
    with pytest.raises(records.ResumeRefused, match="prompt_variant"):
        benchmark.main(_argv(server, single_benchmark, out,
                             ["--resume", "--prompt-variant", "list_reporting_tools"]),
                       executor=fake_tools)


def test_resume_refuses_another_model(server, single_benchmark, tmp_path, fake_tools):
    out = _first_run(server, single_benchmark, tmp_path / "r", fake_tools)
    argv = [a if a != "mock-model" else "other-model"
            for a in _argv(server, single_benchmark, out, ["--resume"])]
    with pytest.raises(records.ResumeRefused, match="model"):
        benchmark.main(argv, executor=fake_tools)


def test_a_query_language_that_contradicts_the_cases_is_refused(server, single_benchmark,
                                                                tmp_path, fake_tools):
    """--query-lang picks the data; naming one arm while reading the other is refused.

    It used to be a label only, so an "EN query" run scored Korean questions.
    """
    out = _first_run(server, single_benchmark, tmp_path / "r", fake_tools)
    with pytest.raises(SystemExit, match="contradicts"):
        benchmark.main(_argv(server, single_benchmark, out, ["--resume", "--query-lang", "en"]),
                       executor=fake_tools)


def test_resume_of_the_same_configuration_is_still_accepted(server, single_benchmark, tmp_path,
                                                            fake_tools):
    """The guard refuses another arm, not a resume."""
    out = _first_run(server, single_benchmark, tmp_path / "r", fake_tools)
    assert benchmark.main(_argv(server, single_benchmark, out, ["--resume"]),
                          executor=fake_tools) == 0
    recs = [r for f in sorted(out.glob("*.jsonl")) for r in records.read_records(f)]
    assert sorted(r["case_id"] for r in recs) == ["st_001", "st_002", "st_003"]


def test_the_identity_of_a_record_and_of_the_run_are_read_the_same_way(server, single_benchmark,
                                                                       tmp_path, fake_tools):
    out = _first_run(server, single_benchmark, tmp_path / "r", fake_tools)
    record = next(records.read_records(next(out.glob("*.jsonl"))))
    identity = records.run_identity(record)
    assert identity["benchmark_dir"] == "benchmarks"
    assert identity["tools_lang"] == "kr" and identity["query_lang"] == "kr"
    assert identity["setting"] == "single" and identity["prompt_variant"] == "baseline"
    assert len(identity["benchmark_sha256"]) == 64
    assert set(identity) == set(records.IDENTITY_FIELDS)


def test_a_multi_turn_resume_refuses_the_other_setting(server, multiturn_benchmark, tmp_path,
                                                       fake_tools):
    from _experiments.scripts import benchmark_multiturn

    server.always(text("끝"))
    out = tmp_path / "r"
    argv = base_argv(server, out) + ["--cases-dir", str(multiturn_benchmark), "--limit", "1"]
    benchmark_multiturn.main(argv + ["--setting", "oracle"], executor=fake_tools)
    with pytest.raises(records.ResumeRefused, match="setting"):
        benchmark_multiturn.main(argv[:-2] + ["--setting", "e2e", "--resume"],
                                 executor=fake_tools)
