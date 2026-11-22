"""Assemble validation tables into ``out/validation/report.md`` (what is and is not validated)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from crowd.pipeline import Context
from crowd.validation import v1_holdout

CANNOT_SHOW = (
    "**What no metric here can show:** crowding truth (the passengers per seat a rider meets). "
    "The tickets are a ~2.6% digital-ticket sample without trip identifiers or alighting counts; "
    "the held-out tests validate the estimator of the *sampled* process (volumes, spatial profiles, "
    "levels), not absolute loads, cross-route or cross-hour scale, true alighting or seat "
    "availability. V3 slices are subsets of the reference data, so V3 tests rerun determinism, "
    "not generalisation."
)


def markdown_table(df: pd.DataFrame, digits: int = 4) -> str:
    """Plain GitHub-flavoured markdown table (no optional dependencies)."""
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            cells.append("" if pd.isna(v) else (f"{v:.{digits}f}" if isinstance(v, float) else str(v)))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def run_all(ctx: Context) -> Path:
    """Run every implemented validation item and write the report."""
    tables = v1_holdout.run_v1(ctx)
    flow = tables["flow_agreement"]
    rank = flow[flow["weighted kappa"].isna()].drop(columns="weighted kappa")
    kappa = flow[flow["weighted kappa"].notna()][["stratum", "predictor", "cells", "weighted kappa"]]
    parts = ["# Validation report", "",
             "## V1: temporal hold-out on whole weekdays", "", "Split:", "", markdown_table(tables["split"]), "",
             "### Daily boarding-ticket counts: mean NB log score per cell-day (higher is better)", "",
             markdown_table(tables["count_log_score"]), "",
             "### 80% predictive intervals (cells with training mean >= 5 tickets/day)", "",
             markdown_table(tables["interval_calibration"]), "",
             "### OD pairs: mean multinomial log score per held-out ticket (higher is better)", "",
             markdown_table(tables["od_log_score"]), "",
             "### Flow rank agreement against the like-for-like held-out target", "", markdown_table(rank), "",
             "### Level agreement (weighted kappa, train cuts)", "", markdown_table(kappa), "", CANNOT_SHOW, ""]
    path = ctx.store.path("validation") / "report.md"
    path.write_text("\n".join(parts), encoding="utf-8")
    return path
