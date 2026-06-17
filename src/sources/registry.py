"""Declarative registry of data sources, consumed by the orchestrator.

Adding a source = add one ``SourceSpec`` here (and its ``src/sources/<name>/``
package). Each spec wires existing functions together:

- ``run_understanding`` : produces the understanding artifacts (existing runner).
- ``load_dataframe``    : returns the DataFrame to process and store (DB-ready base;
                          for PII sources it is already anonymised).
- ``processing``        : declarative :class:`ProcessingConfig` for this source.
- ``table``             : target PostgreSQL table name.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from src.processing.pipeline import ProcessingConfig
from src.sources.incidents import runner as incidents_runner
from src.sources.machines import runner as machines_runner
from src.sources.telemetry import runner as telemetry_runner


@dataclass
class SourceSpec:
    """Everything the orchestrator needs to run one source through all stages."""

    name: str
    run_understanding: Callable[[], object]
    load_dataframe: Callable[[], object]
    processing: ProcessingConfig
    table: str


SOURCE_SPECS: list[SourceSpec] = [
    SourceSpec(
        name="incidents",
        run_understanding=incidents_runner.run_default,
        load_dataframe=incidents_runner.load_dataframe,
        processing=ProcessingConfig(
            encode={"shift": {"matin": 0, "apres-midi": 1, "nuit": 2}},
            impute={"severity": "median"},
            outliers=[],  # severity bounded, signals are 0/1
        ),
        table="incidents",
    ),
    SourceSpec(
        name="telemetry",
        run_understanding=telemetry_runner.run_default,
        load_dataframe=telemetry_runner.load_dataframe,
        processing=ProcessingConfig(
            encode={},
            impute={
                "temperature_c": "median",
                "pressure_bar": "median",
                "voltage_mean_v": "median",
                "rotation_mean_rpm": "median",
                "pieces_produced": "median",
            },
            outliers=[
                "temperature_c",
                "pressure_bar",
                "voltage_mean_v",
                "rotation_mean_rpm",
                "pieces_produced",
            ],
        ),
        table="telemetry",
    ),
    SourceSpec(
        name="machines",
        run_understanding=machines_runner.run_default,
        load_dataframe=machines_runner.load_dataframe,
        processing=ProcessingConfig(
            encode={
                "maintenance_type": {"proactive": 0, "reactive": 1},
                "component": None,  # automatic category codes
            },
            impute={},
            outliers=["duration_hours"],
        ),
        table="maintenance",
    ),
]
