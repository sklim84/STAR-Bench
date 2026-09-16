"""Startup guards: the platform commit, the data hashes and the column names."""

from __future__ import annotations

import json

import pytest

from _experiments.scripts import benchmark
from _experiments.scripts.runner import arms, provenance
from _experiments.scripts.tests_runner.conftest import base_argv
from _experiments.scripts.tests_runner.mock_server import text


def test_the_collected_provenance_carries_what_contract_2_asks_for():
    arm = arms.load_arm("kr")
    record = provenance.collect(arm=arm, config={})
    for key in ("star_bench_commit", "platform_commit", "data_sha256", "db_sha256",
                "model_file_sha256", "system_prompt_sha256", "tools_sha256",
                "streamlit_stubbed", "started_at", "tools_lang", "prompt_variant"):
        assert key in record, key
    assert record["tools_sha256"] == arm.tools_sha256


def test_a_pinned_value_that_moved_stops_the_run():
    arm = arms.load_arm("kr")
    record = provenance.collect(arm=arm, config={})
    pin = {"platform_commit": "0" * 40}
    with pytest.raises(provenance.EnvironmentMismatch, match="platform_commit"):
        provenance.check_pin(record, pin, strict=True)
    problems = provenance.check_pin(record, pin, strict=False)
    assert any("platform_commit" in p for p in problems)


def test_a_korean_column_database_is_refused():
    record = {"hofinet_columns": ["거래일자", "거래금액"], "streamlit_stubbed": True}
    with pytest.raises(provenance.EnvironmentMismatch, match="hofinet columns"):
        provenance.check_pin(record, None, strict=True)


def test_a_live_streamlit_cache_is_refused():
    record = {"hofinet_columns": list(provenance.HOFINET_COLUMNS), "streamlit_stubbed": False}
    with pytest.raises(provenance.EnvironmentMismatch, match="Streamlit cache"):
        provenance.check_pin(record, None, strict=True)


def test_the_schema_arm_hash_is_pinned_per_arm():
    kr, en = arms.load_arm("kr"), arms.load_arm("en")
    assert kr.tools_sha256 != en.tools_sha256
    record = provenance.collect(arm=kr, config={})
    with pytest.raises(provenance.EnvironmentMismatch, match="tools_sha256"):
        provenance.check_pin(record, {"tools_sha256": en.tools_sha256}, strict=True)


def test_a_run_with_a_matching_pin_starts(server, single_benchmark, tmp_path, fake_tools):
    arm = arms.load_arm("kr")
    pin = tmp_path / "pin.json"
    pin.write_text(json.dumps({"tools_sha256": arm.tools_sha256,
                               "system_prompt_sha256": arm.prompt_sha256}), encoding="utf-8")
    server.always(text("끝"))
    argv = [a for a in base_argv(server, tmp_path / "r") if a != "--no-env-check"]
    argv += ["--cases-dir", str(single_benchmark), "--pin", str(pin), "--no-env-check"]
    assert benchmark.main(argv, executor=fake_tools) == 0


def test_the_environment_check_is_recorded_even_when_it_is_not_fatal(
        server, single_benchmark, tmp_path, fake_tools):
    server.always(text("끝"))
    out = tmp_path / "r"
    benchmark.main(base_argv(server, out) + ["--cases-dir", str(single_benchmark)],
                   executor=fake_tools)
    manifest = json.loads(next(out.glob("*.manifest.json")).read_text(encoding="utf-8"))
    assert "hofinet_columns" in manifest["provenance"]
    assert "streamlit_stubbed" in manifest["provenance"]


# ---------------------------------------------------------------------------
# Which database answered, and which benchmark files the run read
# ---------------------------------------------------------------------------

def test_the_record_says_which_database_object_answered():
    """C2-016: `collect()` read connection_info() before anything opened it."""
    arm = arms.load_arm("kr")
    record = provenance.collect(arm=arm, config={})
    database = record["database"]
    assert database["origin"], "provenance.database.origin is empty, so the record does not " \
                               "say which database object answered"
    assert database["origin"] in ("file", "external")
    assert database["duckdb_path"] and database["parquet_path"]
    build = database["build_info"]
    assert build and build["parquet_sha256"] and build["row_count"] > 0


def test_a_run_whose_database_never_opened_is_refused():
    record = {"hofinet_columns": list(provenance.HOFINET_COLUMNS), "streamlit_stubbed": True,
              "database": {"origin": None, "build_info": None}}
    with pytest.raises(provenance.EnvironmentMismatch, match="which database object answered"):
        provenance.check_pin(record, None, strict=True)


def test_the_record_carries_the_hash_of_the_benchmark_files_it_read(tmp_path):
    """C1-012: the eval file carried a data hash and the run record did not."""
    arm = arms.load_arm("kr")
    record = provenance.collect(arm=arm, config={}, cases_dir="benchmarks")
    assert record["benchmark_dir"] == "benchmarks"
    assert len(record["benchmark_sha256"]) == 64
    assert record["benchmark_files"] > 0

    from _experiments.scripts.scoring.gold import load_benchmark
    assert record["benchmark_sha256"] == load_benchmark("benchmarks").sha256, \
        "the runner and the scorer must digest the case files the same way"


def test_the_benchmark_hash_moves_when_a_case_file_changes(tmp_path):
    (tmp_path / "cases_demo.json").write_text('[{"id": "st_a_001"}]', encoding="utf-8")
    first = provenance.benchmark_digest(tmp_path)
    (tmp_path / "cases_demo.json").write_text('[{"id": "st_a_002"}]', encoding="utf-8")
    second = provenance.benchmark_digest(tmp_path)
    assert first["benchmark_sha256"] != second["benchmark_sha256"]
    assert [f["name"] for f in provenance.benchmark_file_hashes(tmp_path)] == ["cases_demo.json"]
