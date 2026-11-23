"""Stop search, walking neighbours and the stop -> (route, index) inverted index."""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process
from scipy.spatial import cKDTree

from crowd.config import Config
from crowd.gtfs import Geometry
from crowd.names import make_normaliser

KM_PER_DEGREE = 111.2


class StopIndex:
    """All GTFS stops: name search, walking neighbours within a radius, and serving routes."""

    def __init__(self, stops: pd.DataFrame, geo: Geometry, cfg: Config):
        self.stops = stops.reset_index(drop=True)
        self.geo = geo
        self.normalise = make_normaliser(dict(cfg.matching.abbreviations.to_dict()))
        self.norm_names = [self.normalise(n) for n in self.stops["stop_name"]]
        self.pos_of = {sid: i for i, sid in enumerate(self.stops["stop_id"])}
        lat0 = float(self.stops["lat"].mean())
        self._xy = np.column_stack([self.stops["lat"] * KM_PER_DEGREE,
                                    self.stops["lon"] * KM_PER_DEGREE * np.cos(np.radians(lat0))])
        self._tree = cKDTree(self._xy)
        self._served: list[int] | None = None
        self.walk_radius_km = cfg.planner.walk_radius_m / 1000
        self.speed_mpm = cfg.planner.walk_speed_mps * 60
        self.detour = cfg.planner.walk_detour
        self.routes_at: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for r in range(geo.n_routes):
            for idx, sid in enumerate(geo.stop_id[geo.stops_of(r)]):
                self.routes_at[sid].append((r, idx))

    def search(self, text: str, limit: int = 8) -> list[dict]:
        """Stops matching the text: name prefix, then word prefix, then substring, then fuzzy.

        One row per distinct stop name; stops no route serves are skipped.
        """
        q = self.normalise(text)
        if not q:
            return []
        ranked = []
        for i, name in enumerate(self.norm_names):
            rank = 0 if name.startswith(q) else 1 if f" {q}" in name else 2 if q in name else None
            if rank is not None:
                ranked.append((rank, len(name), i))
        found: dict[str, dict] = {}
        for _, _, i in sorted(ranked):
            self._add(found, i)
            if len(found) >= limit:
                return list(found.values())
        for _, _, i in process.extract(q, self.norm_names, scorer=fuzz.WRatio, limit=limit * 3):
            self._add(found, i)
            if len(found) >= limit:
                break
        return list(found.values())

    def _served_once(self) -> list[int]:
        """One stop per distinct name among the stops some route serves, in alphabetical order of the name."""
        if self._served is None:
            first: dict[str, int] = {}
            for i, name in enumerate(self.norm_names):
                if self.stops.at[i, "stop_id"] in self.routes_at:
                    first.setdefault(name, i)
            self._served = sorted(first.values(), key=lambda i: (self.norm_names[i], i))
        return self._served

    def alphabetical(self, limit: int, offset: int = 0) -> list[dict]:
        """A page of the stop list in alphabetical order, for choosing a stop before typing anything."""
        return [self._row(i) for i in self._served_once()[offset:offset + limit]]

    def every_stop(self) -> list[dict]:
        """All distinct served stops (for a map of every stand)."""
        return [self._row(i) for i in self._served_once()]

    def nearest(self, lat: float, lon: float, limit: int = 5) -> list[dict]:
        """The closest served stops to a point, one per name, each with its straight-line distance in metres."""
        lat0 = float(self.stops["lat"].mean())
        point = np.array([lat * KM_PER_DEGREE, lon * KM_PER_DEGREE * np.cos(np.radians(lat0))])
        found: dict[str, dict] = {}
        k = min(len(self.stops), limit * 6)
        dist, idx = self._tree.query(point, k=k)
        for d, i in zip(np.atleast_1d(dist), np.atleast_1d(idx)):
            name = self.norm_names[int(i)]
            if name not in found and self.stops.at[int(i), "stop_id"] in self.routes_at:
                found[name] = {**self._row(int(i)), "distance_m": int(round(float(d) * 1000))}
                if len(found) >= limit:
                    break
        return list(found.values())

    def _add(self, found: dict[str, dict], i: int) -> None:
        name = self.norm_names[i]
        if name not in found and self.stops.at[i, "stop_id"] in self.routes_at:
            found[name] = self._row(i)

    def _row(self, i: int) -> dict:
        s = self.stops.iloc[i]
        return {"stop_id": s["stop_id"], "name": s["stop_name"], "lat": float(s["lat"]), "lon": float(s["lon"])}

    def ids_named(self, stop_id: str) -> list[str]:
        """Every stop sharing the (normalised) name of ``stop_id``: the same place, different poles."""
        name = self.norm_names[self.pos_of[stop_id]]
        return [self.stops.at[i, "stop_id"] for i, n in enumerate(self.norm_names)
                if n == name and self.stops.at[i, "stop_id"] in self.routes_at]

    def walk_minutes(self, a: str, b: str) -> float:
        d_km = float(np.hypot(*(self._xy[self.pos_of[a]] - self._xy[self.pos_of[b]])))
        return d_km * 1000 * self.detour / self.speed_mpm

    def neighbours(self, stop_id: str) -> list[tuple[str, float]]:
        """Stops within the walking radius with their walking minutes (the stop itself at 0)."""
        i = self.pos_of[stop_id]
        out = []
        for j in self._tree.query_ball_point(self._xy[i], self.walk_radius_km):
            sid = self.stops.at[j, "stop_id"]
            if sid in self.routes_at:
                out.append((sid, 0.0 if j == i else self.walk_minutes(stop_id, sid)))
        return out
