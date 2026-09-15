"""STAR-Bench scoring library (Contract 3 over Contract 2 records and Contract 1 gold).

Single-turn and multi-turn share one comparison module (``compare``), so a
parameter is judged the same way wherever it appears. The metric definitions are
in ``README.md`` next to this file.
"""

from .aggregate import aggregate_multiturn, aggregate_single, mean_n
from .catalog import Catalog
from .compare import ScoringContext
from .gold import load_benchmark
from .multiturn import score_scenario, score_turn
from .records import iter_records, view_record
from .schema import load_tool_schemas
from .single import score_case
from .sql import SqlExecutor

__all__ = [
    "Catalog", "ScoringContext", "SqlExecutor", "aggregate_multiturn", "aggregate_single",
    "iter_records", "load_benchmark", "load_tool_schemas", "mean_n", "score_case",
    "score_scenario", "score_turn", "view_record",
]
