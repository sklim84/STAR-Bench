"""Running cases in parallel, with one worker's failure contained to that case.

A full sweep does not fit its deadline one request at a time, and the tool layer
is thread-safe (per-call DuckDB cursors, threading gate on the platform branch),
so there is no cross-talk to force concurrency 1.

Two rules keep a parallel run comparable with a serial one:

  * nothing mutable is shared between cases. Each worker thread builds its own
    OpenAI client, and a case's message history, rounds and record exist only
    inside `run_case`.
  * results are handed back to the calling thread, one at a time, so writing and
    progress reporting stay single-threaded and the record file needs no
    coordination beyond the writer's own lock.

At concurrency 1 the work runs inline, without a pool, so the serial reference
run is the same code path it always was.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Iterable

__all__ = ["run_jobs", "ClientPool"]


def run_jobs(items: Iterable[Any], work: Callable[[Any], Any], *, concurrency: int,
             on_result: Callable[[Any, Any, BaseException | None], None]) -> None:
    """Runs `work` over `items`, calling `on_result` in this thread for each one.

    `on_result(item, value, error)` is called exactly once per item. A worker that
    raises passes the exception through as `error` with `value` None; it never
    stops the other workers and never touches another case's record.
    """
    items = list(items)
    if concurrency <= 1:
        for item in items:
            try:
                on_result(item, work(item), None)
            except BaseException as exc:  # noqa: BLE001 - reported, not swallowed
                on_result(item, None, exc)
        return

    with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="case") as pool:
        futures = {pool.submit(work, item): item for item in items}
        for future in as_completed(futures):
            item = futures[future]
            try:
                on_result(item, future.result(), None)
            except BaseException as exc:  # noqa: BLE001
                on_result(item, None, exc)


class ClientPool:
    """One model client per worker thread, built on first use.

    A client is cheap to build and not documented as safe to share across
    threads, so each worker gets its own. The request options are read-only and
    shared, which is what keeps the retry policy and the budgets identical in
    every worker.
    """

    def __init__(self, build: Callable[[], Any]):
        self._build = build
        self._local = threading.local()
        self._built = 0
        self._lock = threading.Lock()

    def get(self) -> Any:
        client = getattr(self._local, "client", None)
        if client is None:
            client = self._build()
            self._local.client = client
            with self._lock:
                self._built += 1
        return client

    @property
    def clients_built(self) -> int:
        with self._lock:
            return self._built
