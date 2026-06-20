"""Declarative registry of data sources, consumed by the medallion orchestrator.

Adding a source = add one ``SourceSpec`` here (and its ``src/sources/<name>/``
package exposing ``load_bronze`` / ``to_silver`` + the numeric-feature lists).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from src import config
from src.processing.pipeline import ProcessingConfig
from src.sources.incidents import runner as incidents_runner
from src.sources.machines import referential_runner as machine_runner
from src.sources.machines import runner as machines_runner
from src.sources.telemetry import runner as telemetry_runner


@dataclass
class SourceSpec:
    """Everything the orchestrator needs to run one source through the layers."""

    name: str
    load_bronze: Callable[[], object]
    to_silver: Callable[[object], tuple]
    bronze_numeric: list[str]
    silver_numeric: list[str]
    table: str
    bronze_only: bool = False
    machine_col: str = field(default=config.MACHINE_COLUMN)
    count_features: list[str] = field(default_factory=list)
    count_label: str = "records"
    keyword_bars: list[tuple[str, list[str], str]] = field(default_factory=list)
    heatmaps: list[tuple[str, str]] = field(default_factory=list)
    timeseries: list[tuple[str, str, str, str]] = field(default_factory=list)
    bars_by_machine: list[str] = field(default_factory=list)
    cumulative: list[tuple[str, str, str]] = field(default_factory=list)
    feature_plots: dict[str, Callable] = field(default_factory=dict)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    overview: Callable | None = None


def _spec(runner) -> SourceSpec:
    return SourceSpec(
        name=runner.SOURCE_NAME,
        load_bronze=runner.load_bronze,
        to_silver=runner.to_silver,
        bronze_numeric=runner.BRONZE_NUMERIC,
        silver_numeric=runner.SILVER_NUMERIC,
        table=runner.TABLE,
        bronze_only=getattr(runner, "BRONZE_ONLY", False),
        machine_col=getattr(runner, "MACHINE_COL", config.MACHINE_COLUMN),
        count_features=getattr(runner, "COUNT_FEATURES", []),
        count_label=getattr(runner, "COUNT_LABEL", "records"),
        keyword_bars=getattr(runner, "KEYWORD_BARS", []),
        heatmaps=getattr(runner, "HEATMAPS", []),
        timeseries=getattr(runner, "TIMESERIES", []),
        bars_by_machine=getattr(runner, "BARS_BY_MACHINE", []),
        cumulative=getattr(runner, "CUMULATIVE", []),
        feature_plots=getattr(runner, "FEATURE_PLOTS", {}),
        processing=getattr(runner, "PROCESSING", ProcessingConfig()),
        overview=getattr(runner, "OVERVIEW", None),
    )


SOURCE_SPECS: list[SourceSpec] = [
    _spec(incidents_runner),
    _spec(telemetry_runner),
    _spec(machine_runner),  # dimension (referential) — before the maintenance fact
    _spec(machines_runner),
]
