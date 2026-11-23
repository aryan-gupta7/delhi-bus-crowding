"""Leave later: would departing a little later be clearly calmer?

For each offset the same trip is re-planned. The fastest option at the later time is compared with
the fastest option now, counting the extra waiting time (``offset``) in its journey time, with the
same worst-case and 80%-of-draws rule as the "More comfortable" card. Hour bins are the scheduled
passage hours (never interpolated), so a difference can only come from a different hour's level.
"""

from __future__ import annotations

from crowd.config import Config
from crowd.planner.cards import margin_minutes
from crowd.planner.scoring import ScoredOption


def leave_later_rows(planner, from_stop: str, to_stop: str, time_hhmm: str, day_type: str, now: ScoredOption) -> list[dict]:
    """One row per offset with the fastest option's level and whether the advantage over leaving now holds."""
    cfg: Config = planner.cfg
    hh, mm = (int(x) for x in time_hhmm.split(":"))
    margin = margin_minutes(now.t_adj, cfg)
    rows = []
    for offset in cfg.planner.leave_later_offsets:
        minute = hh * 60 + mm + offset
        options = planner.generator.plan(planner.stops.ids_named(from_stop), planner.stops.ids_named(to_stop), minute)
        if not options:
            continue
        later = planner.scorer.score(options[0], day_type)                       # options are sorted fastest first
        advantage = now.t_adj_lo - (later.t_adj + offset)
        share = float(((now.t_adj_draws_lo - (later.t_adj_draws + offset)) >= margin).mean())
        rows.append({
            "offset": offset, "depart": f"{(minute // 60) % 24:02d}:{minute % 60:02d}", "routes": [leg.route for leg in later.option.legs],
            "level_code": later.level, "partly_estimated": later.partly_estimated,
            "arrives_later_by": round(later.option.arrive_min - now.option.arrive_min, 1),
            "advantage_min": round(float(advantage), 1),
            "holds": bool(advantage >= margin and share >= cfg.ensemble.robust_share)})
    return rows


def chip(rows: list[dict], cfg: Config) -> dict | None:
    """The smallest offset within the chip limit whose advantage holds, or None."""
    return next((r for r in rows if r["holds"] and r["offset"] <= cfg.planner.max_leave_later_chip), None)
