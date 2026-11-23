"""Like-for-like held-out flow target and the baselines' predictors.

The model's Q-hat counts every route-resolved ticket (decision D-1), while observed flows can
only use both-ends-matched tickets. The held-out target is therefore the empirical test-day flow
rescaled per (route, hour band) by *resolved test passengers / both-ends-matched test passengers*
on the same days, so low-coverage routes are not penalised for a definitional reason.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from crowd import flows
from crowd.gtfs import Geometry


def rescale_factors(counts: pd.DataFrame, od: pd.DataFrame, dates: np.ndarray, geo: Geometry,
                    band_of_hour: np.ndarray, band_names: list[str]) -> np.ndarray:
    """[n_routes, n_bands]: resolved / matched passengers on ``dates`` (NaN if nothing matched)."""
    n_bands = len(band_names)
    band_index = {n: i for i, n in enumerate(band_names)}
    c = counts[counts["date"].isin(dates) & (counts["day_type"] == "weekday")]
    resolved = np.zeros((geo.n_routes, n_bands))
    ci = geo.route_ix(c["route"])
    np.add.at(resolved, (ci[ci >= 0], band_of_hour[c["hour"].to_numpy(np.int64)][ci >= 0]),
              c["pax"].to_numpy(float)[ci >= 0])
    o = od[od["date"].isin(dates)]
    matched = np.zeros((geo.n_routes, n_bands))
    oi = geo.route_ix(o["route"])
    np.add.at(matched, (oi[oi >= 0], o["band"].map(band_index).to_numpy()[oi >= 0]), o["pax"].to_numpy(float)[oi >= 0])
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(matched > 0, resolved / matched, np.nan)


def empirical_flow(pairs: pd.DataFrame, geo: Geometry, day_hour_ok: pd.DataFrame, dates: np.ndarray,
                   gamma: float, factors: np.ndarray, band_of_hour: np.ndarray) -> np.ndarray:
    """Weekday observed flow per eligible day, ``[n_seg, 24]``, rescaled to all resolved tickets."""
    flow = flows.observed_flows(pairs, geo, day_hour_ok, dates, gamma)["weekday"].per_day()
    seg_route = np.repeat(np.arange(geo.n_routes), geo.n_stops - 1)
    return flow * factors[seg_route][:, band_of_hour]


def route_hour_mean(flow: np.ndarray, geo: Geometry) -> np.ndarray:
    """Mean over each route's segments, broadcast back to segments (baseline B3)."""
    sums = np.add.reduceat(np.nan_to_num(flow), geo.seg_ptr[:-1], axis=0)
    mean = sums / (geo.n_stops - 1)[:, None]
    return np.repeat(mean, geo.n_stops - 1, axis=0)
