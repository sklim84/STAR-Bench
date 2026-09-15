"""Shared runner layer for the STAR-Bench benchmarks.

Both runners (`benchmark.py`, `benchmark_multiturn.py`) build their requests,
read their responses and write their run records through this package, so a
serving decision or a record field is defined once.

    arms        schema arm (Korean / English tool definitions and prompt)
    registry    one entry per serving configuration
    provenance  startup guards and the provenance block of Contract 2
    records     Contract 2 run records: writer, run ids, resume checks
    client      request building and response reading against one model
    loop        the tool-calling loops that produce the records
"""

from __future__ import annotations

__all__ = ["arms", "client", "loop", "provenance", "records", "registry"]
