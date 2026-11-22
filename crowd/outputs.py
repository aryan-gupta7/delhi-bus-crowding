"""S8: queryable crowding table and the ride-level ``query`` (design/mechanism.md S8)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

from crowd.config import Config
from crowd.gtfs import Geometry
from crowd.names import make_normaliser

LEVEL_NAMES = {0: "No estimate", 1: "Lighter", 2: "Busy", 3: "Very busy"}


@dataclass
class CrowdingTable:
    """crowding_cells.parquet indexed for (route, stretch, hour, day_type) lookups, with the
    per-draw levels (aligned row by row) that the planner uses for joint evaluation."""

    cells: pd.DataFrame
    levels: np.ndarray                      # uint8 [n_cells, K]
    row_of: dict[tuple, int]

    @classmethod
    def load(cls, cells: pd.DataFrame, levels: np.ndarray) -> "CrowdingTable":
        keys = zip(cells["route"], cells["stretch_id"], cells["hour"], cells["day_type"])
        return cls(cells=cells, levels=levels, row_of={k: i for i, k in enumerate(keys)})

    def row(self, route: str, stretch_id: int, hour: int, day_type: str) -> int | None:
        return self.row_of.get((route, int(stretch_id), int(hour), day_type))


class StopResolver:
    """Stop-name -> canonical stop index on a route (exact normalised match, else fuzzy)."""

    def __init__(self, geo: Geometry, cfg: Config):
        self.geo = geo
        self.normalise = make_normaliser(dict(cfg.matching.abbreviations.to_dict()))
        self.min_score = cfg.matching.fuzzy_score

    def resolve(self, route: str, name: str) -> int | None:
        r = self.geo.route_index.get(route)
        if r is None:
            return None
        names = [self.normalise(n) for n in self.geo.stop_name[self.geo.stops_of(r)]]
        target = self.normalise(name)
        if target in names:
            return names.index(target)
        best = process.extractOne(target, names, scorer=fuzz.token_set_ratio)
        return names.index(best[0]) if best and best[1] >= self.min_score else None


def stretch_legs(geo: Geometry, route: str, a: int, b: int, depart_min: float) -> list[dict]:
    """Stretches crossed by a ride from stop ``a`` to ``b`` with minutes and clock hour of passage.

    ``depart_min`` is the minute of day at which the bus leaves stop ``a``; passage times follow
    the scheduled offsets of the canonical pattern.
    """
    r = geo.route_index[route]
    off = geo.off_min[geo.stops_of(r)]
    seg_sl = geo.segs_of(r)
    stretch_of = geo.stretch_id[seg_sl]
    tau = geo.tau_min[seg_sl]
    legs: list[dict] = []
    for s in range(a, b):
        sid = int(stretch_of[s])
        if not legs or legs[-1]["stretch_id"] != sid:
            passage = depart_min + float(off[s] - off[a])
            legs.append({"stretch_id": sid, "minutes": 0.0, "hour": int(passage // 60) % 24})
        legs[-1]["minutes"] += float(tau[s])
    return legs


def query(table: CrowdingTable, geo: Geometry, resolver: StopResolver, route: str, from_stop: str,
          to_stop: str, time_hhmm: str, day_type: str = "weekday") -> dict:
    """Crowding along one bus ride (the same lookup the planner uses)."""
    a, b = resolver.resolve(route, from_stop), resolver.resolve(route, to_stop)
    if a is None or b is None or a >= b:
        return {"route": route, "error": "stops not found on this route in this direction"}
    hh, mm = (int(x) for x in time_hhmm.split(":"))
    out = []
    for leg in stretch_legs(geo, route, a, b, hh * 60 + mm):
        i = table.row(route, leg["stretch_id"], leg["hour"], day_type)
        if i is None:
            out.append({**leg, "level": "No estimate", "tier": "No estimate"})
            continue
        c = table.cells.iloc[i]
        out.append({**leg, "level": LEVEL_NAMES[int(c["level"])], "robust_in_range": bool(c["robust_in_range"]),
                    "tier": c["tier"], "pi": round(float(c["pi_central"]), 4),
                    "buses_per_hour": float(c["N"]), "flags": c["flags"]})
    return {"route": route, "from": from_stop, "to": to_stop, "time": time_hhmm, "day_type": day_type, "stretches": out}
