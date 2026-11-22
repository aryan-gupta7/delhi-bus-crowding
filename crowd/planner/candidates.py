"""Journey candidates: direct rides and one-transfer pairs (Tier 1 planner).

Search is over scheduled trips only (static GTFS). For an origin place (all poles sharing a
name), a destination place and a departure minute it returns every direct route and, for each
(route A, route B) pair that meets at a stop or within walking distance, the earliest feasible
connection. Candidates carry the exact trip rows so the scorer can read passage times.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from crowd.config import Config
from crowd.gtfs import Geometry
from crowd.planner.search import StopIndex
from crowd.planner.tables import TripTables


@dataclass(frozen=True)
class Leg:
    route: str
    r: int
    board_idx: int
    alight_idx: int
    board_min: float
    alight_min: float


@dataclass
class Option:
    """One journey: legs plus the minutes spent walking and waiting (all scheduled)."""

    legs: list[Leg]
    depart_min: float
    arrive_min: float
    walk_min: float
    transfers: int = field(init=False)

    def __post_init__(self) -> None:
        self.transfers = len(self.legs) - 1

    @property
    def total_min(self) -> float:
        return self.arrive_min - self.depart_min

    @property
    def in_vehicle_min(self) -> float:
        return sum(leg.alight_min - leg.board_min for leg in self.legs)

    @property
    def route_key(self) -> tuple[str, ...]:
        return tuple(leg.route for leg in self.legs)


class CandidateGenerator:
    def __init__(self, geo: Geometry, tables: TripTables, stops: StopIndex, cfg: Config):
        self.geo, self.tables, self.stops = geo, tables, stops
        self.min_transfer = cfg.planner.min_transfer_min
        self.max_routes = cfg.planner.max_routes_per_stop
        self.max_candidates = cfg.planner.max_candidates

    def plan(self, origin_ids: list[str], dest_ids: list[str], depart_min: float) -> list[Option]:
        """All candidate journeys leaving ``origin_ids`` at/after ``depart_min``, fastest first."""
        dest = set(dest_ids)
        boardings = self._boardings(origin_ids)
        options = self._direct(boardings, dest, depart_min)
        options += self._one_transfer(boardings, dest, depart_min)
        best: dict[tuple[str, ...], Option] = {}
        for opt in options:
            if opt.route_key not in best or opt.arrive_min < best[opt.route_key].arrive_min:
                best[opt.route_key] = opt
        ranked = sorted(best.values(), key=lambda o: (o.arrive_min, o.transfers))
        return ranked[: self.max_candidates]

    # -- helpers --------------------------------------------------------------------------------
    def _boardings(self, origin_ids: list[str]) -> list[tuple[int, int]]:
        """(route, stop index) pairs at the origin place, the most frequent routes first."""
        pairs = {(r, i) for sid in origin_ids for r, i in self.stops.routes_at[sid]}
        ranked = sorted(pairs, key=lambda p: -self.tables.frequency(p[0]))
        return ranked[: self.max_routes]

    def _direct(self, boardings, dest: set[str], depart_min: float) -> list[Option]:
        out = []
        for r, i in boardings:
            ids = self.geo.stop_id[self.geo.stops_of(r)]
            row = self.tables.next_trip(r, i, depart_min)
            if row is None:
                continue
            times = self.tables.dep[r][row]
            for j in range(i + 1, len(ids)):
                if ids[j] in dest and times[j] == times[j]:
                    leg = Leg(self.geo.names[r], r, i, j, float(times[i]), float(times[j]))
                    out.append(Option([leg], depart_min, float(times[j]), 0.0))
                    break
        return out

    def _one_transfer(self, boardings, dest: set[str], depart_min: float) -> list[Option]:
        into_dest = self._routes_into(dest)
        out = []
        for r1, i1 in boardings:
            row1 = self.tables.next_trip(r1, i1, depart_min)
            if row1 is None:
                continue
            ids1 = self.geo.stop_id[self.geo.stops_of(r1)]
            times1 = self.tables.dep[r1][row1]
            for k in range(i1 + 1, len(ids1)):
                if times1[k] != times1[k]:
                    continue
                for sid2, walk in self.stops.neighbours(ids1[k]):
                    for r2, i2 in self.stops.routes_at[sid2]:
                        if r2 == r1 or r2 not in into_dest:
                            continue
                        opt = self._connect(r1, i1, k, times1, r2, i2, walk, dest, depart_min)
                        if opt is not None:
                            out.append(opt)
        return out

    def _routes_into(self, dest: set[str]) -> dict[int, list[int]]:
        """Routes that stop at the destination place, with the stop indices where they do."""
        into: dict[int, list[int]] = {}
        for sid in dest:
            for r, j in self.stops.routes_at[sid]:
                into.setdefault(r, []).append(j)
        return into

    def _connect(self, r1, i1, k, times1, r2, i2, walk, dest, depart_min) -> Option | None:
        row2 = self.tables.next_trip(r2, i2, float(times1[k]) + walk + self.min_transfer)
        if row2 is None:
            return None
        ids2 = self.geo.stop_id[self.geo.stops_of(r2)]
        times2 = self.tables.dep[r2][row2]
        for j in range(i2 + 1, len(ids2)):
            if ids2[j] in dest and times2[j] == times2[j]:
                legs = [Leg(self.geo.names[r1], r1, i1, k, float(times1[i1]), float(times1[k])),
                        Leg(self.geo.names[r2], r2, i2, j, float(times2[i2]), float(times2[j]))]
                return Option(legs, depart_min, float(times2[j]), walk)
        return None
