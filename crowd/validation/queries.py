"""Random (origin, destination, time) queries over the ticketed network for V8, V9 and V10."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from crowd.planner.service import Planner

PEAK_HOURS = (7, 8, 9, 10, 17, 18, 19, 20)
MIN_RIDE_STOPS = 4


@dataclass(frozen=True)
class Query:
    from_stop: str
    to_stop: str
    time: str

    @property
    def hour(self) -> int:
        return int(self.time[:2])


def sample_queries(planner: Planner, routes: np.ndarray, n: int, seed: int, hours: tuple[int, ...] = PEAK_HOURS) -> list[Query]:
    """``n`` random rides: a ticketed route, two of its stops at least a few stops apart, a clock time.

    Origin and destination are taken from one route, so a direct journey always exists on a route
    that has scheduled service; the planner may still prefer another route or a transfer.
    """
    rng = np.random.default_rng(seed)
    geo = planner.geo
    out: list[Query] = []
    while len(out) < n:
        r = int(rng.choice(routes))
        if geo.n_stops[r] <= MIN_RIDE_STOPS:
            continue
        a = int(rng.integers(0, geo.n_stops[r] - MIN_RIDE_STOPS))
        b = int(rng.integers(a + MIN_RIDE_STOPS, geo.n_stops[r]))
        ids = geo.stop_id[geo.stops_of(r)]
        out.append(Query(str(ids[a]), str(ids[b]), f"{int(rng.choice(hours)):02d}:{int(rng.integers(0, 60)):02d}"))
    return out
