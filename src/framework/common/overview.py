"""Layer-wide (all-sources) overview — architecture extension point.

A *global overview* summarises a whole medallion layer (Bronze or Silver) across every
source at once — distinct from the cross-source analysis in ``src/analyses`` (which joins
sources on ``machine_id``). No global overview plot is implemented yet; this stub gives a
stable entry point so the notebook can render it as soon as content is added.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def global_overview(
    dfs_by_source: dict[str, pd.DataFrame], output_dir: Path, layer: str
) -> list[Path]:
    """Return the global-overview plot paths for ``layer`` (empty until implemented)."""
    return []
