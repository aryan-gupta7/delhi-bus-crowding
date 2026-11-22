"""Choosing how hard the OD profiles are shrunk (the multiplier on the fitted Dirichlet strengths).

The strengths are fitted by marginal likelihood of OD *pairs*, which rewards heavy shrinkage of
sparse pair counts. Segment flows are cumulative sums of pairs and far less sparse, so the same
shrinkage blurs the pinch points that the planner relies on. The multiplier is therefore chosen
for the flow objective on a day-blocked inner split of the *training* days only: fit on the
first part, score the within-route-hour shape of the flow on the rest.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from crowd.config import Config
from crowd.estimator import fit_estimator, hour_bands
from crowd.gtfs import Geometry
from crowd.validation import metrics, targets


def choose_strength_scale(counts: pd.DataFrame, od: pd.DataFrame, pairs: pd.DataFrame, day_hour_ok: pd.DataFrame,
                          geo: Geometry, route_info: pd.DataFrame, service: np.ndarray, cfg: Config,
                          train_dates: np.ndarray) -> tuple[float, dict[float, float]]:
    """Best multiplier from ``estimator.strength_scale_grid`` and the score of every candidate."""
    ecfg = cfg.estimator
    dates = np.sort(train_dates)
    cut = max(int(round(len(dates) * ecfg.tuning_train_share)), 1)
    inner_train, inner_val = dates[:cut], dates[cut:]
    names, boh = hour_bands(cfg)
    factors = targets.rescale_factors(counts, od, inner_val, geo, boh, names)
    target = np.nan_to_num(targets.empirical_flow(pairs, geo, day_hour_ok, inner_val, cfg.flows.gamma, factors, boh))
    scores = {}
    for scale in ecfg.strength_scale_grid:            # descending: ties keep the stronger shrinkage
        est = fit_estimator(counts, od, geo, route_info, cfg, service, train_dates=inner_train, strength_scale=scale)
        scores[float(scale)] = metrics.shape_agreement(est.qhat("weekday").astype(float), target, geo,
                                                       ecfg.shape_min_flow, ecfg.shape_min_segments)
    return max(scores, key=scores.get), scores
