"""Run the validation items and assemble ``out/validation/report.md`` (what is and is not validated)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from crowd.pipeline import Context
from crowd.planner.service import load_planner
from crowd.validation import v1_holdout, v3_rerun, v7_patterns, v8_planner, v9_sensitivity, v10_stability, v11_weekly
from crowd.validation.queries import PEAK_HOURS, sample_queries

ITEMS = ("v1", "v7", "v8", "v9", "v10", "v11", "v3")
MIDDAY_HOURS = tuple(range(11, 17))
CANNOT_SHOW = (
    "**What no metric here can show:** crowding truth (the passengers per seat a rider meets). "
    "The tickets are a ~2.6% digital-ticket sample without trip identifiers or alighting counts; "
    "the held-out tests validate the estimator of the *sampled* process (volumes, spatial profiles, "
    "levels), not absolute loads, cross-route or cross-hour scale, true alighting or seat "
    "availability. V3 slices are subsets of the reference data, so V3 tests rerun determinism, "
    "not generalisation. V9 is a sensitivity analysis, not unseen-case evidence."
)


def markdown_table(df: pd.DataFrame, digits: int = 4) -> str:
    """Plain GitHub-flavoured markdown table (no optional dependencies)."""
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            integral = isinstance(v, float) and not pd.isna(v) and float(v).is_integer() and abs(v) >= 100
            cells.append("" if pd.isna(v) else (f"{v:,.0f}" if integral else f"{v:.{digits}f}" if isinstance(v, float) else str(v)))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _section(title: str, *blocks: str) -> list[str]:
    return [f"## {title}", "", *[b for blk in blocks for b in (blk, "")]]


def _v1_section(tables: dict[str, pd.DataFrame]) -> list[str]:
    flow = tables["flow_agreement"]
    rank = flow[flow["Spearman vs target"].notna()][["stratum", "predictor", "cells", "Spearman vs target", "top-decile overlap"]]
    shape = flow[flow["within-route-hour shape Spearman"].notna()][["stratum", "predictor", "within-route-hour shape Spearman"]]
    kappa = flow[flow["weighted kappa"].notna()][["stratum", "predictor", "cells", "weighted kappa"]]
    return _section(
        "V1: temporal hold-out on whole weekdays", markdown_table(tables["split"]),
        "### Daily boarding-ticket counts: mean NB log score per cell-day (higher is better)", markdown_table(tables["count_log_score"]),
        "### 80% predictive intervals (cells with training mean >= 5 tickets/day)", markdown_table(tables["interval_calibration"]),
        "### OD pairs: mean log score per held-out ticket (higher is better)", markdown_table(tables["od_log_score"]),
        "### Flow rank agreement against the like-for-like held-out target", markdown_table(rank),
        "### Where along a route the load peaks (within-route-hour shape)", markdown_table(shape),
        "### Level agreement with the held-out target (weighted kappa; each predictor uses its own training cuts)", markdown_table(kappa),
        "### Profile-shrinkage multiplier (inner split of the training days)", markdown_table(tables["tuning"]),
        tables["notes"]["note"].iloc[0])


def run_all(ctx: Context, only: tuple[str, ...] = ITEMS) -> Path:
    """Run the selected validation items (default: all) and write the report."""
    parts = ["# Validation report", ""]
    need_planner = {"v8", "v9", "v10"} & set(only)
    tables = est = inp = train = None
    if "v1" in only or "v10" in only:
        tables, est, inp, train = v1_holdout.run_v1(ctx)
    if "v1" in only:
        parts += _v1_section(tables)
    if "v7" in only:
        parts += _section("V7: known-pattern assertions", markdown_table(v7_patterns.run_v7(ctx)))
    if need_planner:
        planner = load_planner(ctx)
        routes = ctx.store.read_table("counts.parquet", ["route"])["route"].unique()
        routes = planner.geo.route_ix(pd.Series(routes))
        n = ctx.cfg.validation.n_queries
        n_peak = int(n * ctx.cfg.validation.peak_query_share)
        queries = (sample_queries(planner, routes, n_peak, seed=1, hours=PEAK_HOURS)
                   + sample_queries(planner, routes, n - n_peak, seed=2, hours=MIDDAY_HOURS))
        if "v8" in only:
            v8 = v8_planner.run_v8(planner, queries)
            parts += _section("V8-lite: planner on random queries (each query is a ride on one scheduled route, so a direct "
                              "journey always exists: 'answered' is a light check)", markdown_table(v8_planner.summarise(v8)))
        if "v9" in only:
            v9 = v9_sensitivity.run_v9(ctx, planner, queries)
            parts += _section("V9: sensitivity of recommendations to the invented assumptions",
                              markdown_table(v9["sensitivity"]), "### Robustness value Gamma* (smallest coverage difference that erases the advantage)",
                              markdown_table(v9["gamma_star"]))
        if "v10" in only:
            peak_queries = sample_queries(planner, routes, ctx.cfg.validation.n_queries_v10, seed=3, hours=PEAK_HOURS)
            v10 = v10_stability.run_v10(ctx, planner, est, inp, train, peak_queries)
            parts += _section("V10: do recommendations made on training days hold on held-out days? (week-to-week stability "
                              "under the same unidentified scale; not a test of correctness)", markdown_table(v10),
                              "Queries not judged: " + ", ".join(f"{k}: {v}" for k, v in v10.attrs["dropped"].items()))
    if "v11" in only:
        weekly = v11_weekly.run_v11(ctx)
        parts += _section("V11: week-to-week stability (model fitted separately on each full weekday week)", markdown_table(weekly),
                          f"{len(weekly)} pair(s) of consecutive full weeks: October has full five-day weekday weeks on 5-9, 12-16 and 26-30 Oct "
                          "(19-23 Oct loses a day to a stream fault and a holiday), so the pairs are 5/12 Oct and 12/26 Oct (the latter skips a week).")
    if "v3" in only:
        parts += _section("V3: rerun on new files (time slices, frozen thresholds)", markdown_table(v3_rerun.run_v3(ctx)))
    parts += [CANNOT_SHOW, ""]
    path = ctx.store.path("validation") / "report.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")
    return path
