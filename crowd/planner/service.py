"""Planner facade: stops in, JSON-ready cards out (shared by the CLI, the API and V8/V10)."""

from __future__ import annotations

from crowd import text
from crowd.config import Config
from crowd.gtfs import Geometry
from crowd.outputs import CrowdingTable
from crowd.planner.candidates import CandidateGenerator, Option
from crowd.planner.cards import margin_minutes, pick_cards
from crowd.planner.scoring import ScoredOption, Scorer
from crowd.planner.search import StopIndex
from crowd.planner.tables import TripTables


def clock(minutes: float) -> str:
    m = int(round(minutes)) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def level_json(level: int) -> dict:
    return {"code": level, "word": text.LEVEL_WORDS[level], "glyph": text.LEVEL_GLYPHS[level]}


class Planner:
    def __init__(self, geo: Geometry, table: CrowdingTable, trip_stops, stops, cuts: dict, cfg: Config):
        self.geo, self.cfg, self.table = geo, cfg, table
        self.tables = TripTables.build(trip_stops, geo)
        self.stops = StopIndex(stops, geo, cfg)
        self.generator = CandidateGenerator(geo, self.tables, self.stops, cfg)
        self.scorer = Scorer(table, geo, cuts, cfg)

    def rebind(self, table: CrowdingTable, cuts: dict, cfg: Config) -> "Planner":
        """The same schedule and search structures scored against another crowding table (V9, V10)."""
        other = object.__new__(Planner)
        other.geo, other.cfg, other.table = self.geo, cfg, table
        other.tables, other.stops = self.tables, self.stops
        other.generator = self.generator
        other.scorer = Scorer(table, self.geo, cuts, cfg)
        return other

    def options(self, from_stop: str, to_stop: str, time_hhmm: str) -> list[Option]:
        hh, mm = (int(x) for x in time_hhmm.split(":"))
        return self.generator.plan(self.stops.ids_named(from_stop), self.stops.ids_named(to_stop), hh * 60 + mm)

    def plan(self, from_stop: str, to_stop: str, time_hhmm: str, day_type: str = "weekday") -> dict:
        """Cards for a trip between two stop ids at a departure time (scheduled, static GTFS)."""
        base = {"query": {"from": from_stop, "to": to_stop, "time": time_hhmm, "day_type": day_type},
                "usually": text.USUALLY, "basis": text.basis(day_type), "sample": text.SAMPLE_NOTE}
        options = self.options(from_stop, to_stop, time_hhmm)
        if not options:
            return {**base, "cards": {}, "message": text.NO_SERVICE}
        scored = [self.scorer.score(o, day_type) for o in options]
        picked = pick_cards(scored, self.scorer, day_type, self.cfg)
        cards = {"fastest": self._card("Fastest", picked["fastest"], None)}
        if picked["calmer"] is not None:
            cards["comfortable"] = self._card("More comfortable", picked["calmer"], picked["gamma_star"])
        message = None if "comfortable" in cards else text.NO_CALMER
        if picked["candidate"] is None:
            message = text.NO_CALMER
        return {**base, "cards": cards, "message": message, "evidence": {
            "central_advantage_min": picked["advantage"], "draw_share": picked["draw_share"],
            "gamma_star": picked["gamma_star"],
            "margin_min": margin_minutes(picked["fastest"].t_adj, self.cfg)}}

    # -- serialisation --------------------------------------------------------------------------
    def _card(self, title: str, s: ScoredOption, gamma_star: float | None) -> dict:
        card = {
            "title": title, "depart": clock(s.option.legs[0].board_min), "arrive": clock(s.option.arrive_min),
            "minutes": round(s.option.total_min, 1), "adjusted_minutes": round(s.t_adj, 1),
            "transfers": s.option.transfers, "walk_minutes": round(s.option.walk_min, 1),
            "level": level_json(s.level), "partly_estimated": s.partly_estimated,
            "legs": [self._leg(leg, scored) for leg, scored in zip(s.option.legs, s.legs)],
        }
        if title != "Fastest":
            card["robustness"] = {"gamma_star": gamma_star,
                                  "note": text.breakdown_note(gamma_star, self.cfg.planner.gamma_max)}
        if s.partly_estimated:
            card["note"] = text.PARTLY_ESTIMATED
        return card

    def _leg(self, leg, scored) -> dict:
        r = leg.r
        stop_xy = list(zip(self.geo.lon[self.geo.stops_of(r)], self.geo.lat[self.geo.stops_of(r)]))
        seg_stretch = self.geo.stretch_id[self.geo.segs_of(r)]
        stretches, s = [], leg.board_idx
        for ref in scored.stretches:
            e = s
            while e < leg.alight_idx and seg_stretch[e] == ref.stretch_id:
                e += 1
            stretches.append({"stretch_id": ref.stretch_id, "level": level_json(ref.level),
                              "coords": [[float(x), float(y)] for x, y in stop_xy[s:e + 1]]})
            s = e
        return {"route": leg.route, "from": scored.board_stop, "to": scored.alight_stop,
                "board": clock(leg.board_min), "alight": clock(leg.alight_min), "minutes": round(scored.minutes, 1),
                "level": level_json(scored.level), "tier": scored.tier, "robust_in_range": scored.robust,
                "stretches": stretches}


def load_planner(ctx) -> Planner:
    """The planner built from the artefacts of a finished run (shared by the API, V8, V9 and V10)."""
    from crowd import stages                         # local import: stages -> gates -> planner would cycle
    st = ctx.store
    table = CrowdingTable.load(st.read_table("crowding_cells.parquet"), st.read_array("levels.npy"))
    return Planner(stages.geometry(ctx), table, st.read_table("trip_stops.parquet"), st.read_table("gtfs_stops.parquet"),
                   st.read_json("cuts.json")["cuts"], ctx.cfg)
