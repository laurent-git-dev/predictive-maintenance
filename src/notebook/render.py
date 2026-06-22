"""Rendering helpers for ``notebooks/pipeline.ipynb`` — moved out of the notebook so they are
importable, lint/test-able and cheap to read (the notebook Setup cell just does
``from src.notebook.render import *``).

Shared state lives here as module-level dicts (``bronze`` / ``silver`` / ``gold`` / …); the
notebook cells mutate them in place, so both sides see the same objects.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import Image, Markdown, display

from src import config
from src.common.overview import global_overview
from src.common.processing_summary import per_feature_processing_markdown
from src.common.profiling import (
    feature_status_badge,
    feature_synthesis_markdown,
    new_feature_badge,
    plot_category_counts,
    plot_crosstab_heatmap,
    plot_cumulative_by_machine,
    plot_feature_by_machine,
    plot_feature_distribution,
    plot_keyword_breakdown,
    plot_timeseries_by_machine,
    plot_value_by_machine,
)
from src.gold.features import FEATURES_COUNT, FEATURES_NUMERIC
from src.sources.registry import SOURCE_SPECS

__all__ = [
    "SPECS",
    "bronze",
    "silver",
    "gold",
    "bronze_flagged",
    "silver_stats",
    "show_per_feature",
    "show_per_feature_spec",
    "silver_new_features",
    "show_gold_features",
    "show_ingestion",
    "show_bronze_processing",
    "silver_engine",
    "silver_key",
    "planned_treatments_markdown",
    "show_silver_preview",
    "show_silver_processing",
    "show_silver_overview",
    "show_gold_usecase",
    "show_gold_build",
    "show_gold_overview",
    "show_overview",
    "show_processing",
    "show_global",
]

# Source registry drives every phase; data is shared across phases via these dicts.
SPECS = {s.name: s for s in SOURCE_SPECS}
bronze: dict = {}
silver: dict = {}
gold: dict = {}
bronze_flagged: dict = {}
silver_stats: dict = {}


def show_per_feature(
    df,
    numeric_features,
    count_features=(),
    count_label="records",
    keyword_bars=(),
    heatmaps=(),
    timeseries=(),
    bars_by_machine=(),
    cumulative=(),
    machine_col=config.MACHINE_COLUMN,
    feature_plots=None,
    source=None,
    new_features=(),
    only_features=None,
):
    """Per-feature understanding: type-aware synthesis (+OK/NOK +NEW) and the hook-driven plots."""
    feature_plots = feature_plots or {}
    new_features = set(new_features)
    out = Path(tempfile.mkdtemp(prefix="nb_"))
    kw_by_feature: dict = {}
    for m, (f, kw, title) in enumerate([t for t in keyword_bars if t[0] in df.columns], start=1):
        kw_by_feature.setdefault(f, []).append((kw, title, m))
    heat_by_row: dict = {}
    present = [(r, c) for r, c in heatmaps if r in df.columns and c in df.columns]
    for k, (r, c) in enumerate(present, start=1):
        heat_by_row.setdefault(r, []).append((c, k))
    ts_by_feature: dict = {}
    present_ts = [
        (v, t, ti, fr) for v, t, ti, fr in timeseries if v in df.columns and t in df.columns
    ]
    for n, (v, t, ti, fr) in enumerate(present_ts, start=1):
        ts_by_feature.setdefault(v, []).append((t, ti, fr, n))
    bar_by_feature: dict = {}
    for q, v in enumerate([b for b in bars_by_machine if b in df.columns], start=1):
        bar_by_feature.setdefault(v, []).append(q)
    cum_by_feature: dict = {}
    present_cum = [c for c in cumulative if c[0] in df.columns and c[1] in df.columns]
    for r, (v, t, ti) in enumerate(present_cum, start=1):
        cum_by_feature.setdefault(v, []).append((t, ti, r))
    cols = df.columns if not only_features else [c for c in df.columns if c in set(only_features)]
    for col in cols:
        badge = f"{feature_status_badge(df, col, source)}{new_feature_badge(col in new_features)}"
        display(Markdown(f"##### {col}{badge}"))
        display(Markdown(feature_synthesis_markdown(df, col, source)))
        if col in numeric_features:
            i = numeric_features.index(col) + 1
            if machine_col in df.columns:
                display(Image(filename=str(plot_feature_by_machine(df, col, i, out, machine_col))))
            display(Image(filename=str(plot_feature_distribution(df, col, i, out))))
        if col in count_features:
            j = list(count_features).index(col) + 1
            display(Image(filename=str(plot_category_counts(df, col, j, out, count_label))))
        for kw, title, m in kw_by_feature.get(col, []):
            display(
                Image(filename=str(plot_keyword_breakdown(df, col, kw, m, out, title, count_label)))
            )
        for c, k in heat_by_row.get(col, []):
            display(Image(filename=str(plot_crosstab_heatmap(df, col, c, k, out))))
        for t, title, fr, n in ts_by_feature.get(col, []):
            display(
                Image(
                    filename=str(
                        plot_timeseries_by_machine(
                            df, col, t, machine_col, n, out, freq=fr, title=title
                        )
                    )
                )
            )
        for q in bar_by_feature.get(col, []):
            display(Image(filename=str(plot_value_by_machine(df, col, q, out))))
        for t, title, r in cum_by_feature.get(col, []):
            display(
                Image(
                    filename=str(plot_cumulative_by_machine(df, col, t, machine_col, r, out, title))
                )
            )
        plot_fn = feature_plots.get(col)
        if plot_fn is not None:
            for png in plot_fn(df, out):
                display(Image(filename=str(png)))


def show_per_feature_spec(spec, df, numeric_features, new_features=(), only_features=None):
    """Per-feature understanding via a source spec's hooks (NEW badge on created cols)."""
    show_per_feature(
        df,
        numeric_features,
        spec.count_features,
        spec.count_label,
        spec.keyword_bars,
        spec.heatmaps,
        spec.timeseries,
        spec.bars_by_machine,
        spec.cumulative,
        spec.machine_col,
        feature_plots=spec.feature_plots,
        source=spec.name,
        new_features=new_features,
        only_features=only_features,
    )


def silver_new_features(silver_name, bronze_name=None):
    """Silver columns absent from the matching Bronze frame (``bronze_name`` defaults to it)."""
    bronze_cols = set(bronze[bronze_name or silver_name].columns)
    return [c for c in silver[silver_name].columns if c not in bronze_cols]


def show_gold_features(df):
    """Per-feature understanding of the unified Gold table (representative subset)."""
    feats = list(FEATURES_NUMERIC) + list(FEATURES_COUNT)
    show_per_feature(
        df,
        FEATURES_NUMERIC,
        FEATURES_COUNT,
        count_label="machine-hours",
        machine_col=config.MACHINE_COLUMN,
        source="gold",
        only_features=feats,
    )


def show_ingestion(df, source):
    """Per-feature ingestion note for the Bronze layer (raw load; operator PII pseudonymised)."""
    pii = (config.OPERATOR_NAME_COLUMN, config.OPERATOR_BADGE_COLUMN)
    lines = []
    for c in df.columns:
        if c in pii:
            note = "**Pseudonymised** at ingestion (HMAC-SHA256, truncated) - PII never in clear."
        elif c == config.COMMENT_COLUMN:
            note = "Kept **raw** at ingestion (free text); PII reviewed/flagged in Silver."
        else:
            note = "Raw typed load - no transformation."
        lines.append(f"##### {c}\n- {note}")
    display(Markdown("\n\n".join(lines)))


def show_bronze_processing(name):
    """Bronze PROCESSING: ingestion note + Pydantic validation/flagging + DB load + rejects."""
    from src.database.engine import get_engine, is_available
    from src.ingestion.load import ingest_bronze
    from src.ingestion.stats import plot_parse_reasons, reason_table_markdown

    show_ingestion(bronze[name], name)
    engine = get_engine() if is_available() else None
    bronze_flagged[name], st = ingest_bronze(name, bronze[name], engine)
    display(
        Markdown(
            f"**Validation & ingestion** -> {st['db']} - parse_ok **{st['parse_ok']}** - "
            f"rejected **{st['parse_ko']}** (parse_ok=False). Rejected rows by reason:"
        )
    )
    display(Markdown(reason_table_markdown(bronze_flagged[name])))
    out = Path(tempfile.mkdtemp(prefix="nb_parse_"))
    png = plot_parse_reasons(bronze_flagged[name], name, out)
    if png is not None:
        display(Image(filename=str(png)))


def silver_engine():
    """Return the DB engine if PostgreSQL is up, else None (Silver reads bronze.* from the DB)."""
    from src.database.engine import get_engine, is_available

    return get_engine() if is_available() else None


def silver_key(name):
    """Silver dict key for a source ('machines' facts -> 'maintenance')."""
    return "maintenance" if name == "machines" else name


def planned_treatments_markdown(spec):
    """List the treatments configured for a source (from its ProcessingConfig)."""
    p = spec.processing
    items = []
    if p.dedup.get("keys"):
        items.append(
            f"**deduplication** on {p.dedup['keys']} (strategy: {p.dedup.get('strategy')})"
        )
    if p.interpolate.get("columns"):
        items.append(f"**time interpolation** on {p.interpolate['columns']}")
    if p.impute:
        items.append(f"**imputation** {p.impute}")
    if p.outliers:
        items.append(f"**outliers (IQR clip)** on {list(p.outliers)}")
    if p.encode:
        items.append(f"**encoding** of {list(p.encode)} (+ `_code`)")
    if p.normalize:
        items.append(f"**normalization** {p.normalize} (+ `_norm`)")
    if spec.name == "machines":
        items.append("**dimension merge** (machine attributes, star schema)")
    return "Planned treatments: " + ("; ".join(items) if items else "_(none)_") + "."


def show_silver_preview(name):
    """Silver PREVIEW: analyse bronze.* (parse_ok flags + planned treatments) before refining."""
    from src.ingestion.stats import reason_table_markdown
    from src.silver.refine import read_bronze_table, split_rejected

    eng = silver_engine()
    if eng is None:
        display(Markdown("_PostgreSQL unavailable - run chapter 1 BRONZE first._"))
        return
    spec = SPECS[name]
    bdf = read_bronze_table(spec.table, eng)
    kept, rejected = split_rejected(bdf)
    display(
        Markdown(
            f"- Bronze rows **{len(bdf)}** | correctable kept **{len(kept)}** | "
            f"rejected **{len(rejected)}** (non-correctable)\n\n{planned_treatments_markdown(spec)}"
            f"\n\n**parse_ok=False breakdown** (duplicate/missing = correctable, else rejected):"
        )
    )
    display(Markdown(reason_table_markdown(bdf)))


def show_silver_processing(name):
    """Silver PROCESSING: refine bronze.* -> silver, load silver.*, document per feature."""
    from src.database.loader import write_table
    from src.silver.refine import read_bronze_table, refine_silver, split_rejected

    eng = silver_engine()
    if eng is None:
        display(Markdown("_PostgreSQL unavailable._"))
        return
    spec = SPECS[name]
    sdf, report, st = refine_silver(name, eng)
    silver[silver_key(name)] = sdf
    silver_stats[name] = st
    rows = write_table(sdf, spec.table, eng, config.SILVER_SCHEMA)
    display(
        Markdown(
            f"**Refined & ingested** -> silver.{spec.table}: {rows} rows"
            f" | rejected {st['rejected']} | modifications {st['modifications']}"
        )
    )
    kept, _ = split_rejected(read_bronze_table(spec.table, eng))
    display(Markdown(per_feature_processing_markdown(kept, sdf, spec.processing, name)))


def show_silver_overview(name):
    """Silver OVERVIEW: per-feature understanding of the treated data + permanent plots."""
    key = silver_key(name)
    if key not in silver:
        display(Markdown("_Run the PROCESSING cell above first._"))
        return
    show_per_feature_spec(SPECS[name], silver[key], SPECS[name].silver_numeric)
    show_overview(SPECS[name], silver[key])


def show_gold_usecase():
    """Gold PREVIEW: use-case framing + targeted cross-silver analyses motivating the features."""
    from src.gold.features import read_silver

    eng = silver_engine()
    if eng is None:
        display(Markdown("_PostgreSQL unavailable - run chapters 1-2 first._"))
        return
    sil = read_silver(eng)
    inc = sil["incidents"].copy()
    inc["fail"] = pd.to_numeric(inc["severity"], errors="coerce") >= 4
    fails = inc[inc["fail"]]
    display(
        Markdown(
            f"**Use case** - predict a **failure (severity >= 4)** within +6/12/24/48h "
            f"per (machine, hour). **Failures**: {len(fails)}/{len(inc)} incidents "
            f"({100 * len(fails) / len(inc):.1f}%) across {fails['machine_id'].nunique()} machines."
        )
    )
    crit = sil["maintenance"][["machine_id", "criticality"]].drop_duplicates("machine_id")
    fbym = (
        fails.groupby("machine_id")
        .size()
        .rename("failures")
        .reset_index()
        .merge(crit, on="machine_id", how="left")
    )
    by_crit = fbym.groupby("criticality")["failures"].sum().reindex(["LOW", "MEDIUM", "HIGH"])
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(by_crit.index.astype(str), by_crit.values, color="#C44E52", edgecolor="white")
    ax.set_title("Failures by machine criticality")
    ax.set_ylabel("failures")
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.show()
    plt.close(fig)
    display(
        Markdown(
            "**Hypotheses (feature groups):** recent telemetry level/dispersion (**memory**), "
            "short-term drift (**trend**), abnormal vs trailing-24h / machine (**anomaly**), "
            "and recent **context** (incidents / signals / maintenance) should carry signal."
        )
    )


def show_gold_build():
    """Gold PROCESSING: build the single gold.features from silver.* (DB) and ingest it."""
    from src.database.engine import get_engine, is_available
    from src.database.loader import write_table
    from src.gold.features import build_gold_from_db

    eng = get_engine() if is_available() else None
    if eng is None:
        display(Markdown("_PostgreSQL unavailable._"))
        return
    gold["features"] = build_gold_from_db(eng)
    rows = write_table(gold["features"], config.GOLD_TABLE, eng, config.GOLD_SCHEMA)
    display(
        Markdown(
            f"**Built & ingested** -> gold.{config.GOLD_TABLE}: {rows} rows x "
            f"{gold['features'].shape[1]} columns (one row per machine-hour)."
        )
    )


def show_gold_overview():
    """Gold OVERVIEW: ingestion stats (rows, features by group, label rates, censored) + story."""
    from src.gold.features import read_silver
    from src.gold.stats import label_markdown, plot_label_positive_rates, summary_markdown

    if "features" not in gold:
        display(Markdown("_Run the PROCESSING build cell first._"))
        return
    g = gold["features"]
    eng = silver_engine()
    spine = len(read_silver(eng)["telemetry"]) if eng is not None else len(g)
    display(Markdown(summary_markdown(g, spine)))
    display(Markdown("**Labels (failure within horizon):**"))
    display(Markdown(label_markdown(g)))
    out = Path(tempfile.mkdtemp(prefix="nb_gold_ov_"))
    display(Image(filename=str(plot_label_positive_rates(g, out))))
    show_global(gold, "gold")


def show_overview(spec, df):
    """Render a source's whole-source overview plots (heading is the markdown cell above)."""
    if spec.overview is None:
        display(Markdown(f"_Overview {spec.name}: a venir._"))
        return
    out = Path(tempfile.mkdtemp(prefix="nb_overview_"))
    for png in spec.overview(df, out):
        display(Image(filename=str(png)))


def show_processing(spec, bronze_df, prefix):
    """Run Bronze -> Silver in-memory; display the per-feature treatment; return silver."""
    silver_df, _report = spec.to_silver(bronze_df)
    display(
        Markdown(per_feature_processing_markdown(bronze_df, silver_df, spec.processing, prefix))
    )
    return silver_df


def show_global(dfs, layer):
    """Render the layer-wide global overview, or a placeholder until it exists."""
    out = Path(tempfile.mkdtemp(prefix="nb_global_"))
    imgs = global_overview(dfs, out, layer)
    if not imgs:
        display(Markdown(f"_Global overview {layer}: a venir._"))
        return
    for png in imgs:
        display(Image(filename=str(png)))
