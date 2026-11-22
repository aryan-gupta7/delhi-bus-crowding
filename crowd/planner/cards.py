"""Cards: Fastest, More comfortable (only if the advantage is robust) and the honest fallback."""

from __future__ import annotations

import numpy as np

from crowd.config import Config
from crowd.planner.scoring import ScoredOption, Scorer


def margin_minutes(t_adj_fastest: float, cfg: Config) -> float:
    """P-R14: a calmer option must save at least max(5 min, 10%) of the fastest option's adjusted time."""
    return max(cfg.planner.min_advantage_min, cfg.planner.min_advantage_frac * t_adj_fastest)


def pick_cards(scored: list[ScoredOption], scorer: Scorer, day_type: str, cfg: Config) -> dict:
    """Select the Fastest card and, if it passes the robust-advantage rule, the More comfortable card.

    The comfortable candidate minimises central adjusted time among options arriving no later than
    ``fastest + max(P-R12 min, P-R13 x fastest ride)``. It is shown only if its advantage is at least the
    margin **in the worst case for stretches without an estimate** (fastest's "?" stretches as comfortable as
    possible, the candidate's as crowded as possible) both at the central scenario and in at least
    ``robust_share`` of the ensemble draws (shared across both options). Otherwise ``calmer`` is None and
    the UI says "No clearly calmer option". The robustness value Gamma* is computed for the best candidate
    whether it is shown or suppressed.
    """
    p = cfg.planner
    fastest = min(scored, key=lambda s: (s.option.arrive_min, s.option.transfers))
    window = max(p.extra_time_min, p.extra_time_frac * fastest.option.total_min)
    pool = [s for s in scored if s is not fastest and s.option.arrive_min <= fastest.option.arrive_min + window]
    result = {"fastest": fastest, "calmer": None, "candidate": None, "gamma_star": None, "advantage": None,
              "advantage_worst": None, "draw_share": None}
    if not pool:
        return result
    candidate = min(pool, key=lambda s: s.t_adj)
    margin = margin_minutes(fastest.t_adj, cfg)
    advantage_worst = fastest.t_adj_lo - candidate.t_adj
    share = float(np.mean(fastest.t_adj_draws_lo - candidate.t_adj_draws >= margin))
    result.update(candidate=candidate, advantage=fastest.t_adj - candidate.t_adj, advantage_worst=advantage_worst,
                  draw_share=share, gamma_star=scorer.breakdown_ratio(fastest, candidate, day_type, margin))
    if advantage_worst >= margin and share >= cfg.ensemble.robust_share:
        result["calmer"] = candidate
    return result
