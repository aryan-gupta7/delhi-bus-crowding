"""Scoring options: travel time, discomfort-adjusted time and the ensemble of draws.

For each leg the stretches it crosses are looked up (hour of passage from the scheduled
offsets) in the crowding table. Levels map to ordinal discomfort multipliers (P-R3). A stretch
without an estimate ("?") has no level, so every option is scored **twice**:

* ``t_adj`` (hi): "?" at the pessimistic multiplier m3, so a leg without data never *looks*
  better than one with data; used for display and for ranking;
* ``t_adj_lo``: "?" at m1, the most comfortable it could turn out to be.

A "More comfortable" card must keep its advantage in the worst case (fastest at lo, calmer at hi),
otherwise absence of data on the fastest option would be presented as comfort of the other.
``T_adj = T + sum_legs in_vehicle_minutes * (E[m_leg] - 1)`` is computed at the central scenario and
for every ensemble draw (shared across legs and options).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from crowd.config import Config
from crowd.gtfs import Geometry
from crowd.outputs import CrowdingTable, stretch_legs
from crowd.planner.candidates import Option

NO_ESTIMATE = 0
TIER_RANK = {"No estimate": 0, "Low": 1, "Medium": 2, "High": 3}
FINITE, ALREADY_BELOW, BEYOND_MAX, NOT_APPLICABLE = "finite", "already_below", "beyond_max", "not_applicable"


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


@dataclass
class ScoredOption:
    option: Option
    legs: list[LegScore]
    t_adj: float                                  # central scenario, "?" at m3
    t_adj_draws: np.ndarray                       # [K]
    t_adj_lo: float                               # central scenario, "?" at m1
    t_adj_draws_lo: np.ndarray                    # [K]
    level: int = NO_ESTIMATE                      # overall level of the option
    partly_estimated: bool = False
    routes: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class GammaStar:
    """Robustness value: ``value`` is the smallest coverage factor that erases the advantage."""

    value: float | None
    status: str                                   # finite | already_below | beyond_max | not_applicable


class Scorer:
    def __init__(self, table: CrowdingTable, geo: Geometry, cuts: dict, cfg: Config):
        self.table, self.geo, self.cfg = table, geo, cfg
        self.m = np.asarray(cfg.planner.multipliers, dtype=float)       # [m1, m2, m3]
        self.share = cfg.planner.overall_leg_share
        self.cuts = cuts                                                 # central cuts per day-type
        self._tier_name = {v: k for k, v in TIER_RANK.items()}

    def multiplier(self, level: int | np.ndarray, unknown: float) -> np.ndarray:
        """Ordinal multiplier of a level; level 0 (no estimate) gets ``unknown``."""
        lv = np.asarray(level)
        return np.where(lv == NO_ESTIMATE, unknown, self.m[np.clip(lv - 1, 0, 2)])

    # -- scoring ----------------------------------------------------------------------------------
    def score(self, option: Option, day_type: str) -> ScoredOption:
        k = self.table.levels.shape[1]
        legs, extra = [], {name: (0.0, np.zeros(k)) for name in ("hi", "lo")}
        unknown = {"hi": self.m[2], "lo": self.m[0]}
        for leg in option.legs:
            refs = self._stretches(leg.route, leg.board_idx, leg.alight_idx, leg.board_min, day_type)
            minutes = sum(s.minutes for s in refs)
            in_vehicle = leg.alight_min - leg.board_min
            for name in extra:
                m_central = sum(s.minutes * float(self.multiplier(s.level, unknown[name])) for s in refs) / minutes
                m_draw = sum(s.minutes * self.multiplier(self._levels_k(s), unknown[name]) for s in refs) / minutes
                central, draws = extra[name]
                extra[name] = (central + in_vehicle * (m_central - 1), draws + in_vehicle * (m_draw - 1))
            legs.append(self._leg_score(leg, refs, minutes))
        total = option.total_min
        scored = ScoredOption(option=option, legs=legs, t_adj=total + extra["hi"][0], t_adj_draws=total + extra["hi"][1],
                              t_adj_lo=total + extra["lo"][0], t_adj_draws_lo=total + extra["lo"][1],
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

    def _leg_score(self, leg, refs: list[StretchRef], minutes: float) -> LegScore:
        rows = [s.row for s in refs if s.row is not None]
        tiers = [TIER_RANK[self.table.cells.at[i, "tier"]] for i in rows] or [0]
        robust = bool(rows) and len(rows) == len(refs) and all(self.table.cells.at[i, "robust_in_range"] for i in rows)
        names = self.geo.stop_name[self.geo.stops_of(leg.r)]
        # the leg's displayed level uses the same 25%-of-minutes rule as the option's overall level
        return LegScore(route=leg.route, board_stop=str(names[leg.board_idx]), alight_stop=str(names[leg.alight_idx]),
                        minutes=minutes, stretches=refs, level=self._dominant_level([(s.level, s.minutes) for s in refs]),
                        tier=self._tier_name[min(tiers)], robust=robust)

    def _dominant_level(self, items: list[tuple[int, float]]) -> int:
        """Highest level reached by at least ``overall_leg_share`` of the minutes that have an estimate.

        Going down from the busiest level, minutes at that level or above accumulate; the first level whose
        cumulative share reaches the threshold is the answer. A brief crush stretch therefore does not set a
        whole leg's level, and a long crowded run always does, however many stretches it is cut into.
        0 (no estimate) if no minute has an estimate.
        """
        known = [(lv, m) for lv, m in items if lv != NO_ESTIMATE]
        total = sum(m for _, m in known)
        if total == 0:
            return NO_ESTIMATE
        for level in sorted({lv for lv, _ in known}, reverse=True):
            if sum(m for lv, m in known if lv >= level) >= self.share * total:
                return level
        return NO_ESTIMATE

    # -- robustness value -----------------------------------------------------------------------
    def _adjusted(self, scored: ScoredOption, scale: dict[str, float], unknown: float, day_type: str) -> float:
        """Central adjusted time with the central pressure of the given routes multiplied by ``scale[route]``
        and levels recomputed against the frozen central cuts (unknown stretches have no pressure to scale)."""
        c1, c2 = self.cuts[day_type]["central"]
        extra = 0.0
        for leg, ls in zip(scored.option.legs, scored.legs):
            m = 0.0
            for s in ls.stretches:
                level = s.level
                if s.row is not None and s.route in scale:
                    pi = s.pi * scale[s.route]
                    level = 1 + int(pi > c1) + int(pi > c2)
                m += s.minutes * float(self.multiplier(level, unknown))
            extra += (leg.alight_min - leg.board_min) * (m / ls.minutes - 1)
        return scored.option.total_min + extra

    def breakdown_ratio(self, fastest: ScoredOption, calmer: ScoredOption, day_type: str, margin: float) -> GammaStar:
        """Smallest factor by which ticket coverage would have to differ between the options' routes for the
        calmer option's advantage to fall below ``margin`` (Gamma*), in the worst case for unknown stretches
        (fastest at m1, calmer at m3).

        If the calmer option has routes the fastest lacks, their central pressure is multiplied by gamma;
        otherwise the fastest's exclusive routes are divided by gamma; if the options share all their routes
        there is nothing to scale (``not_applicable``). Bisection on log(gamma) is valid because the
        advantage is non-increasing in gamma.
        """
        calm_only, fast_only = calmer.routes - fastest.routes, fastest.routes - calmer.routes
        if not calm_only and not fast_only:
            return GammaStar(None, NOT_APPLICABLE)
        unknown_fast, unknown_calm = self.m[0], self.m[2]

        def advantage(gamma: float) -> float:
            fast_scale = {} if calm_only else {r: 1.0 / gamma for r in fast_only}
            calm_scale = {r: gamma for r in calm_only}
            return (self._adjusted(fastest, fast_scale, unknown_fast, day_type)
                    - self._adjusted(calmer, calm_scale, unknown_calm, day_type))

        if advantage(1.0) < margin:
            return GammaStar(1.0, ALREADY_BELOW)
        lo, hi = 0.0, float(np.log(self.cfg.planner.gamma_max))
        if advantage(float(np.exp(hi))) >= margin:
            return GammaStar(None, BEYOND_MAX)
        for _ in range(14):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if advantage(float(np.exp(mid))) >= margin else (lo, mid)
        return GammaStar(float(np.exp(hi)), FINITE)
