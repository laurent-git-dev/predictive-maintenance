"""Generic shareable synthesis report (``dataset_report.md``), shared by all runs.

Each source/analysis builds its indicators, sections and notes, then calls
:func:`write_dataset_report`. This keeps the business-facing report consistent
across sources and trivial to add to a new source.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def write_dataset_report(
    run_dir: Path,
    *,
    title: str,
    subtitle: str,
    indicators: dict,
    sections: dict[str, list[tuple[str, str]]],
    notes: list[str],
    intro: str = "",
    filename: str = "dataset_report.md",
) -> Path:
    """Write a shareable, business-friendly synthesis report compiling all graphs.

    Parameters
    ----------
    run_dir : pathlib.Path
        Folder of the run (where the PNGs live and the report is written).
    title : str
        Report title (``# title``).
    subtitle : str
        One-line context shown as a block-quote under the title.
    indicators : dict
        ``label -> value`` rows of the "Dataset at a glance" table.
    sections : dict[str, list[tuple[str, str]]]
        ``section_title -> [(png_filename, caption), ...]``; each graph is embedded.
    notes : list[str]
        Bullet points for the "Notes for business teams" section.
    intro : str, optional
        Free markdown shown between the table and the graphs (how to read).
    filename : str, optional
        Output file name (default ``dataset_report.md``).
    """
    out = Path(run_dir) / filename

    ind_lines = "\n".join(f"| {label} | {value} |" for label, value in indicators.items())

    blocks = []
    for section_title, items in sections.items():
        lines = [f"## {section_title}", ""]
        for name, caption in items:
            lines.append(f"### {caption}")
            lines.append(f"![{caption}]({name})")
            lines.append("")
        blocks.append("\n".join(lines))
    graphs_md = "\n".join(blocks)

    notes_md = "\n".join(f"- {n}" for n in notes)
    intro_md = f"{intro}\n\n" if intro else ""

    content = f"""# {title}

> {subtitle}

## Dataset at a glance

| Indicator | Value |
|---|---|
{ind_lines}

{intro_md}{graphs_md}
## Notes for business teams

{notes_md}
"""
    out.write_text(content, encoding="utf-8")
    logger.info("Dataset report written: %s", out.name)
    return out
