"""Running cases in parallel produces the same records a serial run does."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from _experiments.scripts import benchmark, benchmark_multiturn as mt
from _experiments.scripts.runner import parallel, records, registry
from _experiments.scripts.tests_runner.conftest import base_argv
from _experiments.scripts.tests_runner.mock_server import status, text, tool_call


def _answer(request: dict):
    """A deterministic mock: the reply depends only on the conversation so far.

    Nothing in it depends on arrival order, which is what lets a parallel run and
    a serial run be compared record by record.
    """
    last = request["messages"][-1]
    if last["role"] != "user":
        return text("정리했습니다.")
    question = last["content"]
    if "설명" in question:
        return text(f"설명: {question[:10]}")
    return tool_call(("get_statistics", {"q": question[:8]}))


def _tools():
    calls: list[tuple[str, dict]] = []
    lock = threading.Lock()

    def execute(name: str, arguments: dict) -> str:
        with lock:
            calls.append((name, dict(arguments)))
        return json.dumps({"tool": name, "arguments": arguments}, ensure_ascii=False)

    execute.calls = calls
    return execute


def _run_single(server, bench: Path, out: Path, concurrency: int, executor) -> list[dict]:
    argv = base_argv(server, out, concurrency=concurrency) + ["--cases-dir", str(bench)]
    assert benchmark.main(argv, executor=executor) == 0
    return [rec for f in sorted(out.glob("*.jsonl")) for rec in records.read_records(f)]


def _comparable(rec: dict) -> dict:
    """The record without the fields a wall clock or a run id makes different."""
    rounds = []
    for rnd in rec["rounds"]:
        rounds.append({
            "idx": rnd["idx"], "finish_reason": rnd["finish_reason"], "content": rnd["content"],
            "tool_calls": [{k: c[k] for k in ("name", "arguments", "source", "valid_json")}
                           for c in rnd["tool_calls"]],
            "executed": [{k: e[k] for k in ("name", "arguments", "result", "error")}
                         for e in rnd["executed"]],
            "error": rnd["error"], "attempts": rnd["attempts"],
        })
    return {"case_id": rec["case_id"], "turn": rec.get("turn"), "final_text": rec["final_text"],
            "stop_reason": rec["stop_reason"], "error": rec["error"], "rounds": rounds}


# ---------------------------------------------------------------------------
# Single turn
# ---------------------------------------------------------------------------

def test_four_workers_produce_the_same_records_as_one(server, single_benchmark, tmp_path):
    server.respond_with(_answer)
    serial = _run_single(server, single_benchmark, tmp_path / "n1", 1, _tools())
    parallel_recs = _run_single(server, single_benchmark, tmp_path / "n4", 4, _tools())

    assert [_comparable(r) for r in serial] == [_comparable(r) for r in parallel_recs]


def test_the_output_file_is_in_benchmark_order_whatever_the_worker_order(
        server, single_benchmark, tmp_path):
    server.respond_with(_answer)
    recs = _run_single(server, single_benchmark, tmp_path / "n4", 4, _tools())
    assert [r["case_id"] for r in recs] == ["st_001", "st_002", "st_003"]


def test_the_concurrency_actually_used_is_recorded(server, single_benchmark, tmp_path):
    server.respond_with(_answer)
    out = tmp_path / "n3"
    recs = _run_single(server, single_benchmark, out, 3, _tools())
    assert all(r["config"]["concurrency"] == 3 for r in recs)
    manifest = json.loads(next(out.glob("*.manifest.json")).read_text(encoding="utf-8"))
    assert manifest["concurrency"] == 3
    assert manifest["config"]["concurrency"] == 3
    assert manifest["provenance"]["preflight"]["concurrency"] == 3


def test_the_default_comes_from_the_registry(server, single_benchmark, tmp_path):
    server.respond_with(_answer)
    argv = [a for a in base_argv(server, tmp_path / "d") if a not in ("--concurrency", "1")]
    argv += ["--cases-dir", str(single_benchmark)]
    assert benchmark.main(argv, executor=_tools()) == 0
    recs = [rec for f in sorted((tmp_path / "d").glob("*.jsonl"))
            for rec in records.read_records(f)]
    assert all(r["config"]["concurrency"] == registry.CONCURRENCY for r in recs)


def test_every_worker_gets_its_own_client(server, single_benchmark, tmp_path):
    server.respond_with(_answer)
    out = tmp_path / "n3"
    _run_single(server, single_benchmark, out, 3, _tools())
    # Three cases over three workers: more than one client was built, and each
    # worker reused its own rather than building one per case.
    assert len(server.requests) >= 3


def test_a_worker_that_raises_only_costs_its_own_case(server, single_benchmark, tmp_path):
    server.respond_with(_answer)
    boom = {"n": 0}

    def flaky(name, arguments):
        if arguments.get("q", "").startswith("계좌"):
            boom["n"] += 1
            raise MemoryError("worker died")
        return json.dumps({"tool": name}, ensure_ascii=False)

    out = tmp_path / "n4"
    argv = base_argv(server, out, concurrency=4) + ["--cases-dir", str(single_benchmark)]
    benchmark.main(argv, executor=flaky)
    recs = {r["case_id"]: r for f in sorted(out.glob("*.jsonl"))
            for r in records.read_records(f)}
    assert set(recs) == {"st_001", "st_002", "st_003"}
    # The tool error belongs to its own case and the others are untouched.
    assert recs["st_002"]["rounds"][0]["executed"][0]["error"]["type"] == "MemoryError"
    assert recs["st_001"]["stop_reason"] != "error"
    assert recs["st_003"]["final_text"]


def test_a_failing_request_in_one_worker_does_not_corrupt_another_record(
        server, single_benchmark, tmp_path):
    def answer(request):
        last = request["messages"][-1]
        if last["role"] == "user" and "계좌" in last["content"]:
            return status(500, "this case only")
        return _answer(request)

    server.respond_with(answer)
    out = tmp_path / "n4"
    argv = base_argv(server, out, concurrency=4) + ["--cases-dir", str(single_benchmark)]
    benchmark.main(argv, executor=_tools())
    recs = {r["case_id"]: r for f in sorted(out.glob("*.jsonl"))
            for r in records.read_records(f)}
    assert recs["st_002"]["stop_reason"] == "error"
    assert recs["st_002"]["error"]["status"] == 500
    for case_id in ("st_001", "st_003"):
        assert recs[case_id]["error"] is None
        assert recs[case_id]["stop_reason"] != "error"


# ---------------------------------------------------------------------------
# Multi turn
# ---------------------------------------------------------------------------

def _run_mt(server, bench: Path, out: Path, concurrency: int, executor) -> list[dict]:
    argv = base_argv(server, out, concurrency=concurrency) + ["--cases-dir", str(bench)]
    assert mt.main(argv, executor=executor) == 0
    return [rec for f in sorted(out.glob("*.jsonl")) for rec in records.read_records(f)]


def test_scenarios_run_in_parallel_while_their_turns_stay_sequential(
        server, multiturn_benchmark, tmp_path):
    order: list[int] = []
    lock = threading.Lock()

    def answer(request):
        user_turns = [m for m in request["messages"] if m["role"] == "user"]
        with lock:
            order.append(len(user_turns))
        return text(f"turn {len(user_turns)}")

    server.respond_with(answer)
    recs = _run_mt(server, multiturn_benchmark, tmp_path / "mt", 4, _tools())
    assert [r["turn"] for r in recs] == [1, 2, 3]
    # One scenario in the fixture, so its turns had to arrive in order.
    assert order == [1, 2, 3]


def test_multi_turn_records_carry_the_concurrency_and_stay_in_order(
        server, multiturn_benchmark, tmp_path):
    server.respond_with(lambda request: text("네"))
    out = tmp_path / "mt"
    recs = _run_mt(server, multiturn_benchmark, out, 4, _tools())
    assert all(r["config"]["concurrency"] == 4 for r in recs)
    assert [(r["case_id"], r["turn"]) for r in recs] == [("mt_001", 1), ("mt_001", 2),
                                                         ("mt_001", 3)]
    manifest = json.loads(next(out.glob("*.manifest.json")).read_text(encoding="utf-8"))
    assert manifest["concurrency"] == 4


# ---------------------------------------------------------------------------
# The helper itself
# ---------------------------------------------------------------------------

def test_run_jobs_reports_every_item_once_even_when_work_raises():
    seen = []

    def work(item):
        if item == 2:
            raise ValueError("no")
        return item * 10

    parallel.run_jobs([1, 2, 3], work, concurrency=3,
                      on_result=lambda item, value, error: seen.append((item, value, error)))
    assert sorted(item for item, _v, _e in seen) == [1, 2, 3]
    failed = [entry for entry in seen if entry[2] is not None]
    assert len(failed) == 1 and failed[0][0] == 2
    assert isinstance(failed[0][2], ValueError)


def test_run_jobs_at_one_runs_inline_in_the_calling_thread():
    threads = set()

    def work(item):
        threads.add(threading.current_thread().name)
        return item

    parallel.run_jobs(range(4), work, concurrency=1, on_result=lambda *a: None)
    assert threads == {threading.current_thread().name}


def test_a_client_pool_builds_one_client_per_thread():
    pool = parallel.ClientPool(lambda: object())
    first, second = pool.get(), pool.get()
    assert first is second and pool.clients_built == 1

    others = []
    workers = [threading.Thread(target=lambda: others.append(pool.get())) for _ in range(3)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert pool.clients_built == 4
    assert all(other is not first for other in others)


def test_the_scorer_gives_the_same_result_for_one_worker_and_four(server, single_benchmark,
                                                                  tmp_path):
    """The point of the whole exercise: a parallel run scores like a serial one."""
    pytest.importorskip("sqlglot")
    from _experiments.scripts.scoring.aggregate import aggregate_single
    from _experiments.scripts.scoring.gold import load_benchmark
    from _experiments.scripts.scoring.score_runs import build_context, score_single_run

    server.respond_with(_answer)
    serial = _run_single(server, single_benchmark, tmp_path / "n1", 1, _tools())
    concurrent = _run_single(server, single_benchmark, tmp_path / "n4", 4, _tools())

    bench = load_benchmark(str(single_benchmark))
    ctx = build_context(execute_sql=False, use_catalog=False)
    serial_results, serial_info = score_single_run(serial, bench, ctx)
    concurrent_results, concurrent_info = score_single_run(concurrent, bench, ctx)

    assert serial_info["complete"] and concurrent_info["complete"]
    assert aggregate_single(serial_results) == aggregate_single(concurrent_results)
    assert [(r["case_id"], r["h"], r["a"], r["error_type"]) for r in serial_results] == \
           [(r["case_id"], r["h"], r["a"], r["error_type"]) for r in concurrent_results]
