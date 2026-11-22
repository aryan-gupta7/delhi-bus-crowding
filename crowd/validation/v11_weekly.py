"""V11: week-to-week stability. Fit the model separately on each full eligible weekday week and
compare the estimates of consecutive weeks (rank agreement of Q-hat and level kappa).

Each week has at most five days, so this is noisier than V1; it answers "would the planner give the
same picture next week?" and is read next to the sampling-noise ceiling of V1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from crowd import stages, supply as supply_mod
from crowd.estimator import fit_estimator
from crowd.index import hour_profile_z, levels_from_cuts, stretch_pi, weighted_percentile
from crowd.pipeline import Context
from crowd.validation import metrics

WEEKDAY = "weekday"


def full_weeks(day_hour_ok: pd.DataFrame) -> list[np.ndarray]:
    """Eligible weekdays grouped by ISO week, keeping only weeks with five eligible days."""
    ok = day_hour_ok[(day_hour_ok["day_type"] == WEEKDAY) & day_hour_ok["hour_ok"]]
    days = pd.DatetimeIndex(np.sort(ok["date"].unique()))
    weeks = [days[days.isocalendar().week.to_numpy() == w].to_numpy() for w in sorted(set(days.isocalendar().week))]
    return [w for w in weeks if len(w) == 5]


def run_v11(ctx: Context) -> pd.DataFrame:
    """One row per pair of consecutive full weeks."""
    st, cfg, geo = ctx.store, ctx.cfg, stages.geometry(ctx)
    counts, od = st.read_table("counts.parquet"), st.read_table("od_pairs.parquet")
    info, dh = st.read_table("route_info.parquet"), st.read_table("day_hour_ok.parquet")
    scale = st.read_json("estimator_fit.json")["strength_tuning"]["chosen"]
    dense = supply_mod.dense_supply(st.read_table("supply.parquet"), geo)[WEEKDAY]
    weeks = full_weeks(dh)
    fits, levels = [], []
    for dates in weeks:
        est = fit_estimator(counts, od, geo, info, cfg, stages.service(ctx), train_dates=dates, strength_scale=scale)
        q = est.qhat(WEEKDAY).astype(float)
        tilt = np.exp(cfg.ensemble.theta_central * hour_profile_z(counts[counts["date"].isin(dates)], WEEKDAY))[None, :]
        pi, minutes, has = stretch_pi(q, dense["Z"].astype(float), geo)
        pi, minutes = pi * tilt, minutes * tilt
        cuts = weighted_percentile(pi[has], minutes[has], [cfg.index.p_r1, cfg.index.p_r2])
        fits.append(q)
        levels.append((levels_from_cuts(pi, has, cuts), minutes, has))
    rows = []
    for i in range(len(weeks) - 1):
        a, b = (fits[i] > 0) & (fits[i + 1] > 0), levels[i][2] & levels[i + 1][2] & (levels[i][1] > 0) & (levels[i + 1][1] > 0)
        rows.append({
            "weeks": f"{str(weeks[i][0])[:10]} vs {str(weeks[i + 1][0])[:10]}", "cells": int(a.sum()),
            "Spearman of Q-hat": metrics.spearman(fits[i][a], fits[i + 1][a]),
            "level weighted kappa": metrics.weighted_kappa(levels[i][0][b], levels[i + 1][0][b], levels[i][1][b])})
    return pd.DataFrame(rows)
