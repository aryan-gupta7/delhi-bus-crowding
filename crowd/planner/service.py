"""Planner facade: stops in, JSON-ready cards out (shared by the CLI, the API and V8/V10)."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pandas as pd

from crowd import text
from crowd.config import Config
from crowd.gtfs import Geometry
from crowd.outputs import CrowdingTable
from crowd.planner.candidates import CandidateGenerator, Option
from crowd.planner.cards import margin_minutes, pick_cards
from crowd.planner.scoring import GammaStar, ScoredOption, Scorer
from crowd.planner.search import StopIndex
from crowd.planner.tables import TripTables


def clock(minutes: float) -> str:
    m = int(round(minutes)) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def level_json(level: int) -> dict:
    return {"code": level, "word": text.LEVEL_WORDS[level], "glyph": text.LEVEL_GLYPHS[level]}


@dataclass(frozen=True)
class Planner:
    """Schedule, stop search, crowding table and scorer, ready to answer trips."""

    geo: Geometry
    cfg: Config
    table: CrowdingTable
    tables: TripTables
    stops: StopIndex
    generator: CandidateGenerator
    scorer: Scorer
    period: str                                     # e.g. "October 2026": the data period named in the caveat

    @classmethod
    def build(cls, geo: Geometry, table: CrowdingTable, trip_stops, stops, cuts: dict, cfg: Config, period: str) -> "Planner":
        tables = TripTables.build(trip_stops, geo)
        index = StopIndex(stops, geo, cfg)
        return cls(geo, cfg, table, tables, index, CandidateGenerator(geo, tables, index, cfg),
                   Scorer(table, geo, cuts, cfg), period)

    def rebind(self, table: CrowdingTable, cuts: dict, cfg: Config) -> "Planner":
        """The same schedule and search structures scored against another crowding table (V9, V10)."""
        return replace(self, cfg=cfg, table=table, scorer=Scorer(table, self.geo, cuts, cfg))

    def options(self, from_stop: str, to_stop: str, time_hhmm: str) -> list[Option]:
        hh, mm = (int(x) for x in time_hhmm.split(":"))
        return self.generator.plan(self.stops.ids_named(from_stop), self.stops.ids_named(to_stop), hh * 60 + mm)

    def plan(self, from_stop: str, to_stop: str, time_hhmm: str, day_type: str = "weekday") -> dict:
        """Cards for a trip between two stop ids at a departure time (scheduled, static GTFS)."""
        base = {"query": {"from": from_stop, "to": to_stop, "time": time_hhmm, "day_type": day_type},
                "usually": text.usually(self.period), "basis": text.basis(day_type), "sample": text.SAMPLE_NOTE}
        options = self.options(from_stop, to_stop, time_hhmm)
        if not options:
            return {**base, "cards": {}, "message": text.NO_SERVICE}
        scored = [self.scorer.score(o, day_type) for o in options]
        picked = pick_cards(scored, self.scorer, day_type, self.cfg)
        cards = {"fastest": self._card("Fastest", picked["fastest"], None)}
        if picked["calmer"] is not None:
            cards["comfortable"] = self._card("More comfortable", picked["calmer"], picked["gamma_star"],
                                              partly=picked["fastest"].partly_estimated)
        gamma = picked["gamma_star"]
        return {**base, "cards": cards, "message": None if "comfortable" in cards else text.NO_CALMER, "evidence": {
            "central_advantage_min": picked["advantage"], "worst_case_advantage_min": picked["advantage_worst"],
            "draw_share": picked["draw_share"],          # share of ensemble draws, not a probability
            "gamma_star": gamma.value if gamma else None, "gamma_star_status": gamma.status if gamma else None,
            "margin_min": margin_minutes(picked["fastest"].t_adj, self.cfg)}}

    # -- serialisation --------------------------------------------------------------------------
    def _card(self, title: str, s: ScoredOption, gamma_star: GammaStar | None, partly: bool = False) -> dict:
        card = {
            "title": title, "depart": clock(s.option.legs[0].board_min), "arrive": clock(s.option.arrive_min),
            "minutes": round(s.option.total_min, 1), "adjusted_minutes": round(s.t_adj, 1),
            "transfers": s.option.transfers, "walk_minutes": round(s.option.walk_min, 1),
            "level": level_json(s.level), "partly_estimated": s.partly_estimated or partly,
            "legs": [self._leg(leg, scored) for leg, scored in zip(s.option.legs, s.legs)],
        }
        if title != "Fastest":
            card["robustness"] = {"gamma_star": gamma_star.value, "status": gamma_star.status,
                                  "note": text.breakdown_note(gamma_star.status, gamma_star.value, self.cfg.planner.gamma_max)}
        if s.partly_estimated or partly:
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


def data_period(day_hour_ok: pd.DataFrame) -> str:
    """Month(s) covered by the tickets, e.g. "October 2026" or "October-November 2026"."""
    first, last = pd.Timestamp(day_hour_ok["date"].min()), pd.Timestamp(day_hour_ok["date"].max())
    if (first.year, first.month) == (last.year, last.month):
        return first.strftime("%B %Y")
    return f"{first.strftime('%B')}-{last.strftime('%B %Y')}" if first.year == last.year else f"{first.strftime('%B %Y')}-{last.strftime('%B %Y')}"


def load_planner(ctx) -> Planner:
    """The planner built from the artefacts of a finished run (shared by the API, V8, V9 and V10)."""
    from crowd import stages                         # local import: stages -> gates -> planner would cycle
    st = ctx.store
    table = CrowdingTable.load(st.read_table("crowding_cells.parquet"), st.read_array("levels.npy"))
    return Planner.build(stages.geometry(ctx), table, st.read_table("trip_stops.parquet"), st.read_table("gtfs_stops.parquet"),
                         st.read_json("cuts.json")["cuts"], ctx.cfg, data_period(st.read_table("day_hour_ok.parquet", ["date"])))
