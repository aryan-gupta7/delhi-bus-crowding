"""S3: ticket pairs -> aggregated counts, OD pairs and observed passage-hour flows.

A ticket boarded at minute ``t0`` on
stop ``a`` crosses segment ``s`` at ``t0 + gamma * (off[s] - off[a])``; flow is binned by passage
hour. Eligibility masks the *boarding* hour. The estimator reads only the two aggregate tables
written here (``counts`` and ``od_pairs``), never raw tickets.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from crowd.gtfs import Geometry


def hour_band_map(bands: dict[str, list[int]]) -> dict[int, str]:
    return {h: name for name, hours in bands.items() for h in hours}


def eligible_tickets(tickets: pd.DataFrame, day_hour_ok: pd.DataFrame) -> pd.DataFrame:
    """Keep tickets whose (date, boarding hour) is usable; adds the ``day_type`` column."""
    cells = day_hour_ok[day_hour_ok["hour_ok"]][["date", "hour", "day_type"]]
    return tickets.merge(cells, on=["date", "hour"], how="inner")


def build_counts(tickets: pd.DataFrame, geo: Geometry, day_hour_ok: pd.DataFrame) -> pd.DataFrame:
    """Boarding tickets per (route, date, hour) for every route-resolved ticket.

    Includes an explicit zero row for each eligible (date, hour) of each ticketed route, so that
    the Poisson-gamma volume model counts zero days.
    """
    t = eligible_tickets(tickets, day_hour_ok)
    t = t[geo.route_ix(t["route"]) >= 0]
    agg = t.groupby(["route", "date", "hour"], sort=True).agg(
        n_tickets=("pax", "size"), pax=("pax", "sum")).reset_index()
    cells = day_hour_ok[day_hour_ok["hour_ok"]][["date", "hour", "day_type"]]
    routes = pd.DataFrame({"route": np.sort(agg["route"].unique())})
    grid = routes.merge(cells, how="cross")
    out = grid.merge(agg, on=["route", "date", "hour"], how="left")
    out[["n_tickets", "pax"]] = out[["n_tickets", "pax"]].fillna(0).astype("int32")
    out["hour"] = out["hour"].astype("int8")
    return out.sort_values(["route", "date", "hour"]).reset_index(drop=True)


def build_od_pairs(tickets: pd.DataFrame, resolved: pd.DataFrame, day_hour_ok: pd.DataFrame,
                   bands: dict[str, list[int]]) -> pd.DataFrame:
    """Matched board->alight pairs per (route, band, a, b, date, hour) on eligible cells."""
    t = tickets.assign(a=resolved["a"].to_numpy(), b=resolved["b"].to_numpy(),
                       ok=resolved["ok_pair"].to_numpy())
    t = eligible_tickets(t[t["ok"]], day_hour_ok)
    t["band"] = t["hour"].map(hour_band_map(bands))
    out = t.groupby(["route", "band", "a", "b", "date", "hour"], sort=True).agg(
        pax=("pax", "sum"), n_tickets=("pax", "size")).reset_index()
    out["a"] = out["a"].astype("int16")
    out["b"] = out["b"].astype("int16")
    out["hour"] = out["hour"].astype("int8")
    out[["pax", "n_tickets"]] = out[["pax", "n_tickets"]].astype("int32")
    return out


@dataclass
class FlowSums:
    """Summed passenger flow per (global segment, passage hour) and eligible-day counts."""

    total: np.ndarray       # [n_seg * 24]
    n_days: np.ndarray      # [24] eligible days contributing to each hour

    def per_day(self) -> np.ndarray:
        """Mean passengers per eligible day, shape [n_seg, 24]."""
        grid = self.total.reshape(-1, 24)
        return grid / np.maximum(self.n_days, 1)[None, :]


def _explode(route_ix: np.ndarray, a: np.ndarray, b: np.ndarray, pax: np.ndarray,
             t0: np.ndarray, geo: Geometry, gamma: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """One row per (ticket, crossed segment): global segment id, passage hour, passengers."""
    lens = (b - a).astype(np.int64)
    rep = np.repeat(np.arange(len(a)), lens)
    start = np.cumsum(lens) - lens
    seg = a[rep] + (np.arange(lens.sum()) - np.repeat(start, lens))
    stop_base = geo.stop_ptr[route_ix][rep]
    minute = t0[rep] + gamma * (geo.off_min[stop_base + seg] - geo.off_min[stop_base + a[rep]])
    hour = np.floor(minute / 60).astype(np.int64) % 24
    gseg = geo.seg_ptr[route_ix][rep] + seg
    return gseg, hour, pax[rep]


def observed_flows(pairs: pd.DataFrame, geo: Geometry, day_hour_ok: pd.DataFrame,
                   dates: np.ndarray, gamma: float) -> dict[str, FlowSums]:
    """Observed (unsmoothed) passage-hour flows by day-type for the given dates.

    ``pairs`` holds both-ends-matched tickets with columns route, a, b, pax, minute_of_day, date,
    hour. Tickets in masked (date, boarding-hour) cells are dropped.
    """
    n_seg = int(geo.seg_ptr[-1])
    cells = day_hour_ok[day_hour_ok["date"].isin(dates)]
    out = {}
    for day_type, sub in cells.groupby("day_type"):
        day_list = np.sort(sub["date"].unique())
        ok = sub[sub["hour_ok"]]
        n_days = np.zeros(24)
        np.add.at(n_days, ok["hour"].to_numpy(), 1)
        ok_hours = ok.groupby("date")["hour"].apply(set).to_dict()
        total = np.zeros(n_seg * 24)
        for day in day_list:
            day_t = pairs[pairs["date"] == day]
            day_t = day_t[day_t["hour"].isin(ok_hours.get(day, set()))]
            if day_t.empty:
                continue
            route_ix = geo.route_ix(day_t["route"])
            gseg, hour, w = _explode(route_ix, day_t["a"].to_numpy(np.int64), day_t["b"].to_numpy(np.int64),
                                     day_t["pax"].to_numpy(np.float64), day_t["minute_of_day"].to_numpy(np.float64),
                                     geo, gamma)
            total += np.bincount(gseg * 24 + hour, weights=w, minlength=n_seg * 24)
        out[day_type] = FlowSums(total=total, n_days=n_days)
    return out


def matched_pairs(tickets: pd.DataFrame, resolved: pd.DataFrame) -> pd.DataFrame:
    """Both-ends-matched tickets with the columns ``observed_flows`` needs."""
    ok = resolved["ok_pair"].to_numpy()
    return pd.DataFrame({
        "route": tickets["route"].to_numpy()[ok], "a": resolved["a"].to_numpy()[ok],
        "b": resolved["b"].to_numpy()[ok], "pax": tickets["pax"].to_numpy()[ok],
        "minute_of_day": tickets["minute_of_day"].to_numpy()[ok],
        "date": tickets["date"].to_numpy()[ok], "hour": tickets["hour"].to_numpy()[ok],
    })
