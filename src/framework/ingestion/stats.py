"""Bronze ingestion statistics (the OVERVIEW step): what was ingested from the DataLake.

Works from the flagged DataFrames (``parse_ok`` / ``parse_reason``) produced by the ingestion.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.framework.common.reporting import markdown_table
from src.framework.ingestion.validate import PARSE_OK, PARSE_REASON


def global_summary_markdown(flagged: dict[str, pd.DataFrame]) -> str:
    """Per-source recap: original = ingested rows, valid (parse_ok), rejected (parse_ok=False)."""
    headers = ["source", "rows ingested", "parse_ok", "rejected (parse_ok=False)", "reject rate"]
    rows = []
    tot = [0, 0, 0]
    for name, df in flagged.items():
        n = len(df)
        ok = int(df[PARSE_OK].sum())
        ko = n - ok
        tot = [tot[0] + n, tot[1] + ok, tot[2] + ko]
        rate = f"{100 * ko / n:.2f}%" if n else "—"
        rows.append([name, n, ok, ko, rate])
    rate = f"{100 * tot[2] / tot[0]:.2f}%" if tot[0] else "—"
    rows.append(["**total**", tot[0], tot[1], tot[2], rate])
    return markdown_table(headers, rows)


def reason_counts(df: pd.DataFrame) -> Counter:
    """Count individual reason tokens (a row may carry several ``;``-joined reasons)."""
    counter: Counter = Counter()
    for reason in df.loc[~df[PARSE_OK], PARSE_REASON]:
        counter.update(t for t in str(reason).split(";") if t)
    return counter


def reason_table_markdown(df: pd.DataFrame) -> str:
    """Rejected-row breakdown by individual reason token (descending)."""
    counts = reason_counts(df)
    if not counts:
        return "_No rejected row (all parse_ok)._"
    rows = [[f"`{r}`", n] for r, n in counts.most_common()]
    return markdown_table(["reason", "rows"], rows)


def plot_parse_reasons(df: pd.DataFrame, source: str, output_dir: Path) -> Path | None:
    """Horizontal bar chart of the rejection reasons for one source (``None`` if all valid)."""
    counts = reason_counts(df)
    out = Path(output_dir) / f"parse_reasons_{source}.png"
    if not counts:
        return None
    items = counts.most_common()
    labels = [r for r, _ in items][::-1]
    values = [n for _, n in items][::-1]
    fig, ax = plt.subplots(figsize=(10, max(2.5, 0.4 * len(labels) + 1)))
    ax.barh(labels, values, color="#C44E52", edgecolor="white")
    ax.set_title(f"Rejected rows by reason - {source}")
    ax.set_xlabel("rows")
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out
