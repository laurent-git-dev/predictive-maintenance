"""Declarative registry of data sources, consumed by the medallion orchestrator.

Adding a source = add one ``SourceSpec`` here (and its ``src/sources/<name>/``
package exposing ``load_bronze`` / ``to_silver`` + the numeric-feature lists).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from src import config
from src.sources.incidents import runner as incidents_runner
from src.sources.machines import runner as machines_runner
from src.sources.telemetry import runner as telemetry_runner


@dataclass
class SourceSpec:
    """Everything the orchestrator needs to run one source through the layers."""

    name: str
    load_bronze: Callable[[], object]
    to_silver: Callable[[object], object]
    bronze_numeric: list[str]
    silver_numeric: list[str]
    table: str
    machine_col: str = field(default=config.MACHINE_COLUMN)


def _spec(runner) -> SourceSpec:
    return SourceSpec(
        name=runner.SOURCE_NAME,
        load_bronze=runner.load_bronze,
        to_silver=runner.to_silver,
        bronze_numeric=runner.BRONZE_NUMERIC,
        silver_numeric=runner.SILVER_NUMERIC,
        table=runner.TABLE,
    )


SOURCE_SPECS: list[SourceSpec] = [
    _spec(incidents_runner),
    _spec(telemetry_runner),
    _spec(machines_runner),
]
