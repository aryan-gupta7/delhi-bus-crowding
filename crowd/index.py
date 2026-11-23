"""S6: pressure index and relative bands.

``Pi_str = sum_s Q_s tau_s / sum_s Z_s tau_s`` (passenger-minutes over seat-minutes) per stretch,
band cuts are exposure-weighted percentiles of Pi with weights = passenger-minutes. Levels are
relative bands; no absolute (seats) claim is made.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from crowd.gtfs import Geometry


def weighted_percentile(values: np.ndarray, weights: np.ndarray, q: float | np.ndarray) -> np.ndarray:
    """Exposure-weighted percentile(s) ``q`` (0-100) of ``values``; zero-weight entries ignored."""
    keep = weights > 0
    if not keep.any():
        raise ValueError("no cell has positive exposure: nothing to take a percentile of")
    v, w = values[keep], weights[keep]
    order = np.argsort(v, kind="stable")
    v, w = v[order], w[order]
    cum = np.cumsum(w) - 0.5 * w
    cum /= w.sum()
    return np.interp(np.asarray(q) / 100.0, cum, v)


def levels_from_cuts(pi: np.ndarray, valid: np.ndarray, cuts: np.ndarray) -> np.ndarray:
    """Level 1-3 from ``cuts = (c1, c2)``; 0 where the cell has no scheduled service."""
    level = 1 + (pi > cuts[0]).astype(np.uint8) + (pi > cuts[1]).astype(np.uint8)
    return np.where(valid, level, 0).astype(np.uint8)


def hour_profile_z(counts: pd.DataFrame, day_type: str) -> np.ndarray:
    """Standardised citywide hourly ticket **share** (linear; mean 0, sd 1 over the 24 hours).

    This is the hour-tilt basis ``z_h`` of the scenario ensemble. It is linear share, not log
    volume: under log volume the 09h-13h gap shrinks from ~2.9 to ~0.8 and the theta grid would
    no longer span the flat-capture scenario.
    """
    sub = counts[counts["day_type"] == day_type]
    n_days = sub.groupby("hour")["date"].nunique().reindex(range(24), fill_value=0).to_numpy(float)   # eligible days per hour
    totals = sub.groupby("hour")["n_tickets"].sum().reindex(range(24), fill_value=0).to_numpy(float)
    share = totals / np.maximum(n_days, 1)
    share = share / share.sum()
    return (share - share.mean()) / share.std()


class StretchGrid:
    """Segment -> stretch aggregation for one route (contiguous segment blocks)."""

    def __init__(self, geo: Geometry, r: int):
        sl = geo.segs_of(r)
        sid = geo.stretch_id[sl]
        self.starts = np.flatnonzero(np.r_[True, sid[1:] != sid[:-1]])
        self.stretch_ids = sid[self.starts]
        self.tau = geo.tau_min[sl].astype(np.float64)
        self.n_stretches = len(self.starts)

    def sum(self, x: np.ndarray, weights: np.ndarray | None = None) -> np.ndarray:
        """Sum over each stretch of ``x [..., n_seg, 24]`` weighted by ``weights [n_seg]``."""
        w = self.tau if weights is None else weights
        return np.add.reduceat(x * w[:, None], self.starts, axis=-2)

    def mean_over_segments(self, x: np.ndarray) -> np.ndarray:
        """Unweighted mean over each stretch of ``x [n_seg, ...]`` (used for coverage counts)."""
        sums = np.add.reduceat(x, self.starts, axis=0)
        lens = np.diff(np.r_[self.starts, len(x)])
        return sums / lens.reshape(-1, *([1] * (x.ndim - 1)))


def stretch_pi(q: np.ndarray, z: np.ndarray, geo: Geometry) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Aggregate segment flows ``q [n_seg, 24]`` and seats ``z [n_seg, 24]`` to stretches (all routes).

    Returns ``(pi, passenger_minutes, has_service)`` each ``[n_stretch, 24]``; ``pi`` is passenger-
    minutes over seat-minutes.
    """
    tau = geo.tau_min.astype(np.float64)[:, None]
    num = np.add.reduceat(q * tau, geo.stretch_starts, axis=0)
    den = np.add.reduceat(z * tau, geo.stretch_starts, axis=0)
    has = den > 0
    return np.divide(num, den, out=np.zeros_like(num, dtype=np.float64), where=has), num, has
