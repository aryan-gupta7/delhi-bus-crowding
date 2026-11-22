"""Scoring options: travel time, discomfort-adjusted time and the ensemble of draws.

For each leg the stretches it crosses are looked up (hour of passage from the scheduled
offsets) in the crowding table. Levels map to ordinal discomfort multipliers (P-R3);
a stretch without an estimate is scored with the pessimistic multiplier when comparing
options, so a leg without data never looks better than one with data.
``T_adj = T + sum_legs in_vehicle_minutes * (E[m_leg] - 1)`` is computed at the central
scenario and for every ensemble draw (shared across legs and options).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from crowd.config import Config
from crowd.gtfs import Geometry
from crowd.outputs import CrowdingTable, stretch_legs
from crowd.planner.candidates import Option

NO_ESTIMATE = 0


@dataclass
class StretchRef:
    route: str
    stretch_id: int
    hour: int
    minutes: float
    row: int | None                  # row in the crowding table (None: no estimate)
    level: int                       # central level, 0 = no estimate
    pi: float                        # central pressure (0 if unknown)


@dataclass
class LegScore:
    route: str
    board_stop: str
    alight_stop: str
    minutes: float
    stretches: list[StretchRef]
    level: int = NO_ESTIMATE
    tier: str = "No estimate"
    robust: bool = False
    m_central: float = 1.0


@dataclass
class ScoredOption:
    option: Option
    legs: list[LegScore]
    t_adj: float                                  # central scenario
    t_adj_draws: np.ndarray                       # [K]
    level: int = NO_ESTIMATE                      # overall level of the option
    partly_estimated: bool = False
    routes: frozenset[str] = field(default_factory=frozenset)


class Scorer:
    def __init__(self, table: CrowdingTable, geo: Geometry, cuts: dict, cfg: Config):
        self.table, self.geo, self.cfg = table, geo, cfg
        self.m = np.asarray(cfg.planner.multipliers, dtype=float)       # [m1, m2, m3]
        self.share = cfg.planner.overall_leg_share
        self.cuts = cuts                                                 # central cuts per day-type
        self._tier_rank = {"No estimate": 0, "Low": 1, "Medium": 2, "High": 3}
        self._tier_name = {v: k for k, v in self._tier_rank.items()}

    # -- multipliers ------------------------------------------------------------------------------
    def multiplier(self, level: int | np.ndarray) -> np.ndarray:
        """Ordinal multiplier of a level; level 0 (no estimate) gets the pessimistic m3."""
        lv = np.asarray(level)
        return np.where(lv == NO_ESTIMATE, self.m[2], self.m[np.clip(lv - 1, 0, 2)])

    # -- scoring ----------------------------------------------------------------------------------
    def score(self, option: Option, day_type: str) -> ScoredOption:
        k = self.table.levels.shape[1]
        legs, draws_extra, extra_central = [], np.zeros(k), 0.0
        for leg in option.legs:
            refs = self._stretches(leg.route, leg.board_idx, leg.alight_idx, leg.board_min, day_type)
            minutes = sum(s.minutes for s in refs)
            m_draw = sum(s.minutes * self.multiplier(self._levels_k(s)) for s in refs) / minutes
            m_central = sum(s.minutes * float(self.multiplier(s.level)) for s in refs) / minutes
            extra_central += (leg.alight_min - leg.board_min) * (m_central - 1)
            draws_extra += (leg.alight_min - leg.board_min) * (m_draw - 1)
            legs.append(self._leg_score(leg, refs, minutes, m_central))
        scored = ScoredOption(option=option, legs=legs, t_adj=option.total_min + extra_central,
                              t_adj_draws=option.total_min + draws_extra,
                              routes=frozenset(leg.route for leg in option.legs))
        scored.level = self._dominant_level([(lg.level, lg.minutes) for lg in legs])
        scored.partly_estimated = any(s.level == NO_ESTIMATE for lg in legs for s in lg.stretches)
        return scored

    def _stretches(self, route: str, a: int, b: int, board_min: float, day_type: str) -> list[StretchRef]:
        out = []
        for leg in stretch_legs(self.geo, route, a, b, board_min):
            row = self.table.row(route, leg["stretch_id"], leg["hour"], day_type)
            usable = row is not None and self.table.cells.at[row, "tier"] != "No estimate"
            level = int(self.table.cells.at[row, "level"]) if usable else NO_ESTIMATE
            pi = float(self.table.cells.at[row, "pi_central"]) if usable else 0.0
            out.append(StretchRef(route, leg["stretch_id"], leg["hour"], leg["minutes"],
                                  row if usable else None, level, pi))
        return out

    def _levels_k(self, s: StretchRef) -> np.ndarray:
        k = self.table.levels.shape[1]
        return np.zeros(k, dtype=int) if s.row is None else self.table.levels[s.row].astype(int)

    def _leg_score(self, leg, refs: list[StretchRef], minutes: float, m_central: float) -> LegScore:
        rows = [s.row for s in refs if s.row is not None]
        tiers = [self._tier_rank[self.table.cells.at[i, "tier"]] for i in rows] or [0]
        robust = bool(rows) and len(rows) == len(refs) and all(self.table.cells.at[i, "robust_in_range"] for i in rows)
        return LegScore(
            route=leg.route, board_stop=str(self.geo.stop_name[self.geo.stops_of(leg.r)][leg.board_idx]),
            alight_stop=str(self.geo.stop_name[self.geo.stops_of(leg.r)][leg.alight_idx]), minutes=minutes,
            stretches=refs, level=self._dominant_level([(s.level, s.minutes) for s in refs]),
            tier=self._tier_name[min(tiers)], robust=robust, m_central=m_central)

    def _dominant_level(self, items: list[tuple[int, float]]) -> int:
        """Highest level among items carrying at least ``overall_leg_share`` of the minutes;
        0 (no estimate) if none of the qualifying items has an estimate."""
        total = sum(m for _, m in items)
        qualifying = [lv for lv, m in items if m >= self.share * total]
        known = [lv for lv in qualifying if lv != NO_ESTIMATE]
        return max(known) if known else NO_ESTIMATE

    # -- robustness value -----------------------------------------------------------------------
    def breakdown_ratio(self, fastest: ScoredOption, calmer: ScoredOption, day_type: str, margin: float) -> float | None:
        """Smallest factor by which the calmer option's *exclusive* routes' ticket coverage would
        have to differ for its advantage over ``fastest`` to fall below ``margin`` (Gamma*).

        Scales the central pressure of stretches on routes only the calmer option uses, recomputes
        their levels against the frozen central cuts, and bisects on log(gamma). ``None`` means the
        advantage survives even ``gamma_max``; ``1.0`` that it is already below the margin.
        """
        exclusive = calmer.routes - fastest.routes
        if not exclusive:
            return None
        c1, c2 = self.cuts[day_type]["central"]

        def advantage(gamma: float) -> float:
            extra = 0.0
            for leg, scored in zip(calmer.option.legs, calmer.legs):
                m = 0.0
                for s in scored.stretches:
                    level = s.level
                    if s.route in exclusive and s.row is not None:
                        pi = s.pi * gamma
                        level = 1 + int(pi > c1) + int(pi > c2)
                    m += s.minutes * float(self.multiplier(level))
                extra += (leg.alight_min - leg.board_min) * (m / scored.minutes - 1)
            return fastest.t_adj - (calmer.option.total_min + extra)

        if advantage(1.0) < margin:
            return 1.0
        lo, hi = 0.0, float(np.log(self.cfg.planner.gamma_max))
        if advantage(float(np.exp(hi))) >= margin:
            return None
        for _ in range(14):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if advantage(float(np.exp(mid))) >= margin else (lo, mid)
        return float(np.exp(hi))
