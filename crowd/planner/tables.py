"""Scheduled trip tables for the planner: per route a trip x stop matrix of departure minutes."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from crowd.gtfs import Geometry

MINUTES_PER_DAY = 1440


@dataclass
class TripTables:
    """``dep[r]`` is ``[n_trips, n_stops]`` minutes after midnight (NaN where the trip skips a stop),
    sorted by first departure. Dwell time is ignored: a bus is at a stop at its departure minute."""

    dep: list[np.ndarray]

    @classmethod
    def build(cls, trip_stops: pd.DataFrame, geo: Geometry) -> "TripTables":
        route_ix = geo.route_ix(trip_stops["route"])
        order = np.argsort(route_ix, kind="stable")
        route_sorted = route_ix[order]
        bounds = np.searchsorted(route_sorted, np.arange(geo.n_routes + 1))
        trip_id = trip_stops["trip_id"].to_numpy()[order]
        stop_idx = trip_stops["stop_idx"].to_numpy(np.int64)[order]
        minutes = trip_stops["dep_min"].to_numpy(np.float32)[order]
        tables = []
        for r in range(geo.n_routes):
            lo, hi = bounds[r], bounds[r + 1]
            if lo == hi:
                tables.append(np.full((0, int(geo.n_stops[r])), np.nan, np.float32))
                continue
            trips, local = np.unique(trip_id[lo:hi], return_inverse=True)
            mat = np.full((len(trips), int(geo.n_stops[r])), np.nan, np.float32)
            mat[local, stop_idx[lo:hi]] = minutes[lo:hi]
            first = np.nanmin(mat, axis=1)
            tables.append(mat[np.argsort(first, kind="stable")])
        return cls(dep=tables)

    def next_departure(self, r: int, stop: int, earliest: float) -> np.ndarray | None:
        """Stop times of the first trip of route ``r`` leaving ``stop`` at or after ``earliest``.

        Trips scheduled past 24:00 belong to the previous service day: they are also considered
        ``1440`` minutes earlier, so a 00:30 query finds a 25:10 trip (as 01:10). The returned times
        are on the query's own clock.
        """
        col = self.dep[r][:, stop]
        today = np.where(col >= earliest, col, np.inf)
        yesterday = np.where((col >= MINUTES_PER_DAY) & (col - MINUTES_PER_DAY >= earliest), col - MINUTES_PER_DAY, np.inf)
        row, shift = (int(np.argmin(today)), 0.0) if today.min() <= yesterday.min() else (int(np.argmin(yesterday)), MINUTES_PER_DAY)
        if not np.isfinite(min(today.min(), yesterday.min())):
            return None
        return self.dep[r][row] - shift

    def frequency(self, r: int) -> int:
        return int(self.dep[r].shape[0])
