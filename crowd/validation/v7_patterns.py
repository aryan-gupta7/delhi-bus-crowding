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


def _hubs(ctx: Context, hub_names: list[str]) -> dict:
    """Share of named hubs that sit on at least one top-decile weekday 09h stretch (hub list is an assumption)."""
    geo = stages.geometry(ctx)
    cells = ctx.store.read_table("crowding_cells.parquet", ["route", "stretch_id", "hour", "day_type", "pi_central"])
    nine = cells[(cells["hour"] == 9) & (cells["day_type"] == "weekday")]
    cut = nine["pi_central"].quantile(0.9)
    top = set(zip(nine.loc[nine["pi_central"] >= cut, "route"], nine.loc[nine["pi_central"] >= cut, "stretch_id"]))
    norm = make_normaliser(dict(ctx.cfg.matching.abbreviations.to_dict()))
    names = np.array([norm(n) for n in geo.stop_name])
    stop_route = np.repeat(np.arange(geo.n_routes), geo.n_stops)
    found, on_top = [], []
    for hub in hub_names:
        hits = np.flatnonzero(np.char.find(names.astype(str), norm(hub)) >= 0)
        if not len(hits):
            continue
        found.append(hub)
        stretches = set()
        for flat in hits:
            r = stop_route[flat]
            local = flat - geo.stop_ptr[r]
            for seg in (local - 1, local):
                if 0 <= seg < geo.n_stops[r] - 1:
                    stretches.add((geo.names[r], int(geo.stretch_id[geo.seg_ptr[r] + seg])))
        if stretches & top:
            on_top.append(hub)
    return {"found": found, "on_top": on_top}


def run_v7(ctx: Context) -> pd.DataFrame:
    """Evaluate all pattern assertions on the pipeline outputs."""
    st = ctx.store
    qhat = st.read_table("qhat.parquet")
    info = st.read_table("route_info.parquet")
    dh = st.read_table("day_hour_ok.parquet")
    rows = []

    wk, we = _hourly_totals(qhat, "weekday"), _hourly_totals(qhat, "weekend")
    mid = wk[list(MIDDAY)].mean()
    peaks = {k: wk[list(h)].max() / mid for k, h in PEAKS.items()}
    rows.append(_row("two weekday peaks: AM and PM peak hour each >= 1.5x the midday mean hour",
                     {k: round(float(v), 2) for k, v in peaks.items()}, ">= 1.5", all(v >= 1.5 for v in peaks.values())))
    ratio_wk = wk[6:22].max() / mid
    ratio_we = we[6:22].max() / we[list(MIDDAY)].mean()
    rows.append(_row("weekend peak-to-midday ratio is below the weekday ratio",
                     f"{ratio_we:.2f} vs {ratio_wk:.2f}", "weekend < weekday", ratio_we < ratio_wk))
    rows += _directionality(qhat, info)

    totals = dh.groupby(["date", "day_type"]).agg(pax=("v_null", "sum"), tagged=("v_tagged", "sum"), ok=("day_ok", "first")).reset_index()
    totals["pax"] += totals["tagged"]
    med = totals[totals["ok"]].groupby("day_type")["pax"].median()
    rows.append(_row("weekend/holiday days carry fewer tickets than weekdays (median daily passengers)",
                     f"{med['weekend']:.0f} vs {med['weekday']:.0f}", "weekend < 0.9 x weekday", med["weekend"] < 0.9 * med["weekday"]))

    am_pm = wk[list(PEAKS["am"])].mean() / wk[list(PEAKS["pm"])].mean()
    rows.append(_row("code check: AM/PM peak ratio of passenger-segments", round(float(am_pm), 2), "about 1.5 (profiled)",
                     0.8 <= am_pm <= 2.5, "the data assert this about themselves; kept only to catch a code bug"))

    hubs = _hubs(ctx, list(ctx.cfg.validation.hub_names))
    share = len(hubs["on_top"]) / max(len(hubs["found"]), 1)
    rows.append(_row("named hubs sit on top-decile weekday 09h stretches", f"{len(hubs['on_top'])}/{len(hubs['found'])}",
                     ">= 50% of hubs found in the GTFS", share >= 0.5,
                     f"hub list is an assumption (config validation.hub_names); on top: {hubs['on_top']}"))
    return pd.DataFrame(rows)
