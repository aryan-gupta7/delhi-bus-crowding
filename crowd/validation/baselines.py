"""Baselines B0-B5 and the citywide-share prior (design §4); every metric is reported against them.

B0  raw boardings per route-hour                B3  route-hour mean flow, no segment shape
B1  boardings per scheduled bus                 B4  per-seat variant of B1 (isolates bus size)
B2  unsmoothed pooled segment flow              B5  NB with the per-cell training MLE mean, same
Bc  citywide-share prior V_r * share_h              day dispersion, no shrinkage (the strong baseline)
"""

from __future__ import annotations

import numpy as np

from crowd.estimator import Estimator
from crowd.gtfs import Geometry
from crowd.validation.targets import route_hour_mean

MEAN_FLOOR = 0.01       # a zero training mean would give -inf log score on any later ticket


def raw_means(est: Estimator, day_type: str) -> np.ndarray:
    """Per-cell raw training mean tickets per day (the MLE), floored. [R, 24]"""
    n = np.maximum(est.n_days[day_type], 1)[None, :]
    return np.maximum(est.total[day_type] / n, MEAN_FLOOR)


def flow_predictors(est: Estimator, geo: Geometry, b2_train_flow: np.ndarray, n_dense: np.ndarray,
                    seats_per_route: np.ndarray, day_type: str = "weekday") -> dict[str, np.ndarray]:
    """Per-(segment, hour) score predictors for the flow rank metrics."""
    raw = np.zeros((geo.n_routes, 24))
    raw[est.routes] = est.total[day_type] / np.maximum(est.n_days[day_type], 1)[None, :]
    seg_route = np.repeat(np.arange(geo.n_routes), geo.n_stops - 1)
    b0 = raw[seg_route]
    n_route_hour = np.add.reduceat(n_dense, geo.seg_ptr[:-1], axis=0) / (geo.n_stops - 1)[:, None]
    n_seg = n_route_hour[seg_route]
    b1 = np.divide(b0, n_seg, out=np.zeros_like(b0), where=n_seg > 0)
    b4 = b1 / seats_per_route[seg_route][:, None]
    return {"B0": b0, "B1": b1, "B2": b2_train_flow, "B3": route_hour_mean(b2_train_flow, geo), "B4": b4}
