"""V7: known-pattern assertions. Each row says what was checked, what was observed, and whether it held.

Genuine tests lead (directionality, weekend lighter than weekday, two peaks, hubs); the AM/PM
ratio is only a code check because the data assert it about themselves.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from crowd import stages
from crowd.names import make_normaliser
from crowd.pipeline import Context

PEAKS = {"am": range(7, 11), "pm": range(17, 21)}
MIDDAY = range(11, 17)


def _hourly_totals(qhat: pd.DataFrame, day_type: str) -> np.ndarray:
    sub = qhat[qhat["day_type"] == day_type]
    return sub.groupby("hour")["qhat"].sum().reindex(range(24), fill_value=0.0).to_numpy()


def _row(name: str, observed, threshold, passed: bool, note: str = "") -> dict:
    return {"assertion": name, "observed": observed, "threshold": threshold, "held": bool(passed), "note": note}


def _directionality(qhat: pd.DataFrame, info: pd.DataFrame) -> list[dict]:
    """Inbound routes are busier in the AM share of their flow, outbound routes in the PM share."""
    q = qhat[qhat["day_type"] == "weekday"].merge(info[["route", "dir_class"]], on="route")
    q["band"] = np.where(q["hour"].between(6, 9), "am", np.where(q["hour"].between(16, 19), "pm", "other"))
    flow = q.groupby(["dir_class", "band"])["qhat"].sum().unstack(fill_value=0)
    share = flow.div(flow.sum(axis=1), axis=0)
    am = (share.loc["inbound", "am"], share.loc["outbound", "am"])
    pm = (share.loc["inbound", "pm"], share.loc["outbound", "pm"])
    return [
        _row("AM: inbound routes carry a larger AM share of their flow than outbound routes",
             f"{am[0]:.3f} vs {am[1]:.3f}", "inbound > outbound", am[0] > am[1],
             "radial routes only; inbound = last stop nearer the Connaught Place centroid"),
        _row("PM: outbound routes carry a larger PM share of their flow than inbound routes",
             f"{pm[1]:.3f} vs {pm[0]:.3f}", "outbound > inbound", pm[1] > pm[0], ""),
    ]


def _percentile_of_best_stretch(ctx: Context, names: list[str]) -> dict[str, float]:
    """For each name found in the GTFS: the percentile (among weekday 09h stretches) of the highest pressure
    on any stretch next to a stop of that name."""
    geo = stages.geometry(ctx)
    cells = ctx.store.read_table("crowding_cells.parquet", ["route", "stretch_id", "hour", "day_type", "pi_central", "tier"])
    nine = cells[(cells["hour"] == 9) & (cells["day_type"] == "weekday") & (cells["tier"] != "No estimate")]
    pct = nine["pi_central"].rank(pct=True)
    pct_of = dict(zip(zip(nine["route"], nine["stretch_id"]), pct))
    norm = make_normaliser(dict(ctx.cfg.matching.abbreviations.to_dict()))
    stop_names = np.array([norm(n) for n in geo.stop_name]).astype(str)
    stop_route = np.repeat(np.arange(geo.n_routes), geo.n_stops)
    out = {}
    for name in names:
        best = None
        for flat in np.flatnonzero(np.char.find(stop_names, norm(name)) >= 0):
            r = stop_route[flat]
            local = flat - geo.stop_ptr[r]
            for seg in (local - 1, local):
                if 0 <= seg < geo.n_stops[r] - 1:
                    p = pct_of.get((geo.names[r], int(geo.stretch_id[geo.seg_ptr[r] + seg])))
                    best = p if best is None or (p is not None and p > best) else best
        if best is not None:
            out[name] = float(best)
    return out


def run_v7(ctx: Context) -> pd.DataFrame:
    """Evaluate all pattern assertions on the pipeline outputs."""
    st, vcfg = ctx.store, ctx.cfg.validation
    qhat = st.read_table("qhat.parquet")
    info = st.read_table("route_info.parquet")
    dh = st.read_table("day_hour_ok.parquet")
    rows = []

    wk, we = _hourly_totals(qhat, "weekday"), _hourly_totals(qhat, "weekend")
    mid = wk[list(MIDDAY)].mean()
    peaks = {k: wk[list(h)].max() / mid for k, h in PEAKS.items()}
    rows.append(_row("two weekday peaks: AM and PM peak hour each >= 1.5x the midday mean hour",
                     {k: round(float(v), 2) for k, v in peaks.items()}, ">= 1.5", all(v >= 1.5 for v in peaks.values()),
                     "weak: the ticket hour profile is carried into the estimate by construction"))
    ratio_wk = wk[6:22].max() / mid
    ratio_we = we[6:22].max() / we[list(MIDDAY)].mean()
    rows.append(_row("weekend peak-to-midday ratio is below the weekday ratio",
                     f"{ratio_we:.2f} vs {ratio_wk:.2f}", "weekend < weekday", ratio_we < ratio_wk))
    rows += _directionality(qhat, info)

    daily = dh.assign(pax=dh["v_null"] + dh["v_tagged"]).groupby("date").agg(pax=("pax", "sum"), ok=("day_ok", "first")).reset_index()
    daily = daily[daily["ok"]]
    sundays = daily[pd.DatetimeIndex(daily["date"]).dayofweek == 6]["pax"].median()
    weekdays = daily[pd.DatetimeIndex(daily["date"]).dayofweek < 5]["pax"].median()
    rows.append(_row("Sundays carry fewer tickets than weekdays (median daily passengers; real Sundays only, so the "
                     "day-type rule cannot decide it)", f"{sundays:.0f} vs {weekdays:.0f}", "Sunday < 0.9 x weekday", sundays < 0.9 * weekdays))

    am_pm = wk[list(PEAKS["am"])].mean() / wk[list(PEAKS["pm"])].mean()
    rows.append(_row("code check: AM/PM peak ratio of passenger-segments", round(float(am_pm), 2), "about 1.5 (profiled)",
                     0.8 <= am_pm <= 2.5, "the data assert this about themselves; kept only to catch a code bug"))

    hubs, controls = (_percentile_of_best_stretch(ctx, list(vcfg[k])) for k in ("hub_names", "control_names"))
    hub_med, control_med = float(np.median(list(hubs.values()))), float(np.median(list(controls.values())))
    rows.append(_row("named hubs' busiest stretch ranks above suburban end-points (09h pressure percentile)",
                     f"hubs {hub_med:.2f} (n={len(hubs)}) vs controls {control_med:.2f} (n={len(controls)})",
                     f"hub median >= {vcfg.min_hub_percentile} and > controls", hub_med >= vcfg.min_hub_percentile and hub_med > control_med,
                     "hub and control lists are assumptions (config validation.hub_names / control_names)"))
    return pd.DataFrame(rows)
