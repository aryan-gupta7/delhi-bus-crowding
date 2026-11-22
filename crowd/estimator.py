"""S5: the model of record - Poisson-gamma volume x OD profile x passage-hour convolution.

Design: design/mechanism.md S5,
``Q^(r,s,h) = sum_{h'} Lambda^(r,h') * G(r,h') * sum_{(i,j)} P_band(h')(i,j) 1[i <= s < j] *
P(pass s in h | h', i, s)`` where

* ``Lambda^`` is the expected number of boarding *tickets* of route-direction ``r`` in boarding
  hour ``h'`` (all route-resolved tickets, decision D-1), with a Poisson-gamma posterior, zero days
  counted, a direction-class prior share and a day-level dispersion ``phi`` for held-out days;
* ``G`` converts tickets to passengers (group size, shrunk to the citywide value);
* ``P_band`` is the board->alight distribution of matched tickets in the hour band (hard fall-back
  to the route's all-day profile, then to a length-class profile);
* the convolution is closed-form: boarding uniform within the hour, so a segment ``delta``
  minutes downstream is passed ``floor(delta/60)`` hours later with probability ``1 - f`` and one
  hour later still with probability ``f = (delta mod 60) / 60``.

The profile is pooled across day-types (assumption A-13). Everything linear in ``Lambda`` is
precomputed per route as an operator ``B[h', s, h]``, so ensemble draws are one matrix product.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import gammaln

from crowd.config import Config
from crowd.eligibility import WEEKDAY, WEEKEND
from crowd.gtfs import Geometry

DAY_TYPES = (WEEKDAY, WEEKEND)
DAYS_PER_WEEK = {WEEKDAY: 5, WEEKEND: 2}
SOURCE_CODES = {"band": 0, "route": 1, "length": 2}


# ----------------------------------------------------------------------------------------------
# Poisson-gamma volume model
# ----------------------------------------------------------------------------------------------

def fit_alpha(prior_mean: np.ndarray, total: np.ndarray, n_days: np.ndarray) -> float:
    """Gamma prior precision by negative-binomial marginal likelihood over all cells.

    Prior Gamma(alpha*mu, alpha) on the per-day rate; data = totals over ``n_days`` days.
    """
    mask = prior_mean > 0
    mu, s, n = prior_mean[mask], total[mask], np.broadcast_to(n_days, prior_mean.shape)[mask]

    def neg_ll(log_alpha: float) -> float:
        alpha = np.exp(log_alpha)
        return -np.sum(gammaln(alpha * mu + s) - gammaln(alpha * mu)
                       + alpha * mu * np.log(alpha) - (alpha * mu + s) * np.log(alpha + n))

    res = minimize_scalar(neg_ll, bounds=(-6.0, 8.0), method="bounded")
    return float(np.exp(res.x))


def nb_loglik(y: np.ndarray, mean: np.ndarray, phi: float) -> np.ndarray:
    """Negative-binomial log-likelihood (size ``phi``, given ``mean``), dropping ``log y!``."""
    m = np.maximum(mean, 1e-12)
    return (gammaln(y + phi) - gammaln(phi) + phi * np.log(phi / (phi + m)) + y * np.log(m / (phi + m)))


def fit_phi(y: np.ndarray, mean: np.ndarray) -> float:
    """Day dispersion: ``y_day ~ Poisson(Lambda * delta)``, ``delta ~ Gamma(phi, phi)``.

    ``y`` has shape [cells, days] (NaN where the day is not eligible), ``mean`` is [cells].
    """
    ok = ~np.isnan(y) & (mean[:, None] > 0)
    yy = y[ok]
    mm = np.broadcast_to(mean[:, None], y.shape)[ok]

    def neg_ll(log_phi: float) -> float:
        return -float(nb_loglik(yy, mm, np.exp(log_phi)).sum())

    return float(np.exp(minimize_scalar(neg_ll, bounds=(-3.0, 8.0), method="bounded").x))


def volume_tier(daily_mean: np.ndarray, day_type: str, edges: list[int]) -> np.ndarray:
    """Tier 0/1/2 from tickets per cell-week (<edges[0], <edges[1], above), training counts only."""
    weekly = daily_mean * DAYS_PER_WEEK[day_type]
    return np.searchsorted(np.asarray(edges), weekly, side="right")


# ----------------------------------------------------------------------------------------------
# OD profile and the passage-hour operator
# ----------------------------------------------------------------------------------------------

def _length_grid_profile(n: int, grid: np.ndarray) -> np.ndarray:
    """Dense [n, n] upper-triangular OD probability from a normalised-position grid profile."""
    g = grid.shape[0]
    pos = np.minimum((np.arange(n) / max(n - 1, 1) * g).astype(int), g - 1)
    p = np.triu(grid[np.ix_(pos, pos)], k=1)
    total = p.sum()
    return p / total if total > 0 else p


def _operator_from_profile(profile: np.ndarray, off: np.ndarray, hours: list[int], n_seg: int,
                           out: np.ndarray) -> None:
    """Add the profile's contribution for boarding hours ``hours`` to ``out[h', s, h]``."""
    n = len(off)
    tail = profile.sum(axis=1, keepdims=True) - np.cumsum(profile, axis=1)   # sum_{j>s} P[i, j]
    delta = off[None, :] - off[:, None]                                       # off[s] - off[i]
    i_idx, s_idx = np.triu_indices(n, k=0)
    keep = s_idx < n - 1
    i_idx, s_idx = i_idx[keep], s_idx[keep]
    w = tail[i_idx, s_idx]
    d = delta[i_idx, s_idx]
    k = np.floor(d / 60).astype(int)
    f = (d % 60) / 60
    k_max = int(k.max()) + 2 if len(k) else 2
    key = np.concatenate([s_idx * k_max + k, s_idx * k_max + k + 1])
    weights = np.concatenate([w * (1 - f), w * f])
    shifted = np.bincount(key, weights=weights, minlength=n_seg * k_max).reshape(n_seg, k_max)
    for h_board in hours:
        for shift in range(k_max):
            out[h_board, :, (h_board + shift) % 24] += shifted[:, shift]


@dataclass
class Estimator:
    """Fitted estimator; see module docstring."""

    geo: Geometry
    cfg: Config
    routes: np.ndarray                                   # geo route indices with training data
    alpha: dict[str, float]
    phi: dict[str, np.ndarray]                           # per day-type, per volume tier
    shape: dict[str, np.ndarray]                         # posterior gamma shape  [R, 24]
    rate: dict[str, np.ndarray]                          # posterior gamma rate   [R, 24]
    total: dict[str, np.ndarray]                         # training ticket sums   [R, 24]
    n_days: dict[str, np.ndarray]                        # eligible training days [24]
    tier: dict[str, np.ndarray]                          # volume tier per cell   [R, 24]
    group: np.ndarray                                    # passengers per ticket  [R, 24]
    operators: list[np.ndarray] = field(default_factory=list)   # B[h', s*24+h] per route
    od_cov: list[np.ndarray] = field(default_factory=list)       # tickets covering each segment [bands, s]
    profile_source: np.ndarray = field(default_factory=lambda: np.zeros((0, 0), int))
    band_names: list[str] = field(default_factory=list)
    band_of_hour: np.ndarray = field(default_factory=lambda: np.zeros(24, int))

    # -- accessors ---------------------------------------------------------------------------
    def lam_mean(self, day_type: str) -> np.ndarray:
        """Posterior-mean boarding tickets per day, [R, 24]."""
        return self.shape[day_type] / self.rate[day_type]

    def qhat_route(self, pos: int, lam_eff: np.ndarray) -> np.ndarray:
        """Q-hat [..., n_seg, 24] for ``lam_eff`` [..., 24] (tickets x group size) of route ``pos``."""
        b = self.operators[pos]
        n_seg = b.shape[1] // 24
        return (lam_eff @ b).reshape(*lam_eff.shape[:-1], n_seg, 24)

    def lam_eff_mean(self, day_type: str) -> np.ndarray:
        return self.lam_mean(day_type) * self.group

    def qhat(self, day_type: str) -> np.ndarray:
        """Posterior-mean passengers per day, dense [n_seg_total, 24] (zero for unticketed routes)."""
        out = np.zeros((int(self.geo.seg_ptr[-1]), 24), np.float32)
        lam = self.lam_eff_mean(day_type)
        for pos, r in enumerate(self.routes):
            out[self.geo.segs_of(int(r))] = self.qhat_route(pos, lam[pos])
        return out

    def draw_lambda(self, day_type: str, pos: int, n_draws: int, seed: int) -> np.ndarray:
        """Posterior draws of Lambda for route ``pos``: [n_draws, 24].

        Keyed by (seed, route, day-type), so draws do not depend on how many or which other
        routes are in the run.
        """
        rng = np.random.default_rng([seed, int(self.routes[pos]), 0 if day_type == WEEKDAY else 1])
        shape = np.maximum(self.shape[day_type][pos], 1e-6)
        return rng.gamma(shape, 1.0 / self.rate[day_type][pos], size=(n_draws, 24))

    def segment_od_cov(self, pos: int) -> np.ndarray:
        """Matched training tickets covering each segment, summed over hour bands."""
        return self.od_cov[pos].sum(axis=0)


# ----------------------------------------------------------------------------------------------
# fitting
# ----------------------------------------------------------------------------------------------

def _dense_counts(counts: pd.DataFrame, geo: Geometry, day_type: str, routes: np.ndarray):
    """Counts -> Y[R, 24, D] (NaN where the day-hour is not eligible), plus the date list."""
    sub = counts[counts["day_type"] == day_type]
    dates = np.sort(sub["date"].unique())
    pos = np.full(geo.n_routes, -1)
    pos[routes] = np.arange(len(routes))
    y = np.full((len(routes), 24, len(dates)), np.nan, dtype=np.float64)
    y[pos[geo.route_ix(sub["route"])], sub["hour"].to_numpy(np.int64),
      np.searchsorted(dates, sub["date"].to_numpy())] = sub["n_tickets"].to_numpy()
    return y


def _direction_shares(total_per_day: np.ndarray, dir_class: np.ndarray) -> np.ndarray:
    """Hourly ticket share per direction class for each route: [R, 24]."""
    shares = np.zeros_like(total_per_day)
    city = total_per_day.sum(axis=0)
    for cls in np.unique(dir_class):
        sel = dir_class == cls
        prof = total_per_day[sel].sum(axis=0)
        prof = prof if prof.sum() > 0 else city
        shares[sel] = prof / prof.sum()
    return shares


def _group_size(counts: pd.DataFrame, geo: Geometry, routes: np.ndarray, band_of_hour: np.ndarray,
                n_bands: int, shrink: float) -> np.ndarray:
    """Passengers per ticket by route and hour, shrunk toward the citywide band value."""
    pos = np.full(geo.n_routes, -1)
    pos[routes] = np.arange(len(routes))
    r = pos[geo.route_ix(counts["route"])]
    b = band_of_hour[counts["hour"].to_numpy(np.int64)]
    flat = r * n_bands + b
    size = len(routes) * n_bands
    pax = np.bincount(flat, weights=counts["pax"].to_numpy(float), minlength=size).reshape(-1, n_bands)
    tix = np.bincount(flat, weights=counts["n_tickets"].to_numpy(float), minlength=size).reshape(-1, n_bands)
    city = pax.sum(axis=0) / np.maximum(tix.sum(axis=0), 1)
    g = (pax + shrink * city) / (tix + shrink)
    return g[:, band_of_hour]


def fit_estimator(counts: pd.DataFrame, od_pairs: pd.DataFrame, geo: Geometry, route_info: pd.DataFrame,
                  cfg: Config, train_dates: np.ndarray | None = None) -> Estimator:
    """Fit the estimator on ``counts`` / ``od_pairs`` (optionally restricted to ``train_dates``)."""
    ecfg = cfg.estimator
    if train_dates is not None:
        counts = counts[counts["date"].isin(train_dates)]
        od_pairs = od_pairs[od_pairs["date"].isin(train_dates)]
    band_names = list(ecfg.hour_bands.to_dict())
    band_of_hour = np.zeros(24, int)
    for bi, name in enumerate(band_names):
        for h in ecfg.hour_bands.to_dict()[name]:
            band_of_hour[h] = bi

    routes = np.sort(geo.route_ix(pd.Series(counts["route"].unique())))
    routes = routes[routes >= 0]
    dir_class = route_info.set_index("route")["dir_class"].reindex(geo.names[routes]).to_numpy()

    shape, rate, total, tier, n_days, alpha, phi = {}, {}, {}, {}, {}, {}, {}
    for dt in DAY_TYPES:
        y = _dense_counts(counts, geo, dt, routes)
        n = (~np.isnan(y[0])).sum(axis=1).astype(float)                      # eligible days per hour
        s = np.nansum(y, axis=2)
        per_day = np.divide(s, n[None, :], out=np.zeros_like(s), where=n[None, :] > 0)
        mu = per_day.sum(axis=1, keepdims=True) * _direction_shares(per_day, dir_class)
        alpha[dt] = fit_alpha(mu.ravel(), s.ravel(), np.broadcast_to(n, s.shape).ravel())
        shape[dt], rate[dt] = alpha[dt] * mu + s, alpha[dt] + n[None, :].repeat(len(routes), 0)
        total[dt], n_days[dt] = s, n
        tier[dt] = volume_tier(per_day, dt, cfg.validation.tier_edges)
        lam = shape[dt] / rate[dt]
        phi[dt] = np.array([
            fit_phi(y[tier[dt] == t], lam[tier[dt] == t]) if (tier[dt] == t).sum() >= ecfg.min_hour_cells else np.inf
            for t in range(len(cfg.validation.tier_edges) + 1)])

    est = Estimator(geo=geo, cfg=cfg, routes=routes, alpha=alpha, phi=phi, shape=shape, rate=rate,
                    total=total, n_days=n_days, tier=tier,
                    group=_group_size(counts, geo, routes, band_of_hour, len(band_names), ecfg.group_shrink),
                    band_names=band_names, band_of_hour=band_of_hour)
    _build_operators(est, od_pairs, route_info, band_names)
    return est


def _build_operators(est: Estimator, od: pd.DataFrame, route_info: pd.DataFrame, band_names: list[str]) -> None:
    """Per route: band OD profiles (with fall-backs), segment coverage and the passage operator."""
    geo, ecfg = est.geo, est.cfg.estimator
    n_bands = len(band_names)
    hours_of_band = [list(np.flatnonzero(est.band_of_hour == b)) for b in range(n_bands)]
    od = od.assign(r=geo.route_ix(od["route"]), band_i=od["band"].map({n: i for i, n in enumerate(band_names)}))
    od = od.sort_values("r", kind="stable")
    bounds = np.searchsorted(od["r"].to_numpy(), np.r_[est.routes, geo.n_routes])
    by_route = {int(r): od.iloc[bounds[k]:bounds[k + 1]] for k, r in enumerate(est.routes)}

    n_stops = geo.n_stops
    edges = np.quantile(n_stops[est.routes], np.linspace(0, 1, ecfg.length_classes + 1)[1:-1])
    len_class = np.searchsorted(edges, n_stops, side="right")
    grids = _length_grids(by_route, n_stops, len_class, ecfg.length_classes, ecfg.length_grid)

    est.profile_source = np.zeros((len(est.routes), n_bands), int)
    for pos, r in enumerate(est.routes):
        r = int(r)
        n, n_seg = int(n_stops[r]), int(n_stops[r]) - 1
        off = geo.off_min[geo.stops_of(r)].astype(float)
        rows = by_route.get(r)
        counts = np.zeros((n_bands, n, n))
        cov = np.zeros((n_bands, n_seg))
        if rows is not None and len(rows):
            np.add.at(counts, (rows["band_i"].to_numpy(), rows["a"].to_numpy(), rows["b"].to_numpy()),
                      rows["n_tickets"].to_numpy(float))
            diff = np.zeros((n_bands, n + 1))
            np.add.at(diff, (rows["band_i"].to_numpy(), rows["a"].to_numpy()), rows["n_tickets"].to_numpy(float))
            np.add.at(diff, (rows["band_i"].to_numpy(), rows["b"].to_numpy()), -rows["n_tickets"].to_numpy(float))
            cov = np.cumsum(diff, axis=1)[:, :n_seg]
        all_day = counts.sum(axis=0)
        op = np.zeros((24, n_seg, 24))
        for b in range(n_bands):
            if counts[b].sum() >= ecfg.min_pairs:
                prof, src = counts[b], "band"
            elif all_day.sum() >= ecfg.min_pairs:
                prof, src = all_day, "route"
            else:
                prof, src = _length_grid_profile(n, grids[len_class[r]]), "length"
            est.profile_source[pos, b] = SOURCE_CODES[src]
            prof = prof / prof.sum() if prof.sum() > 0 else prof
            _operator_from_profile(prof, off, hours_of_band[b], n_seg, op)
        est.operators.append(op.reshape(24, n_seg * 24).astype(np.float32))
        est.od_cov.append(cov.astype(np.float32))


def _length_grids(by_route: dict[int, pd.DataFrame], n_stops: np.ndarray, len_class: np.ndarray,
                  n_classes: int, g: int) -> np.ndarray:
    """Citywide OD profile on a normalised-position grid, one per route-length class."""
    grids = np.zeros((n_classes, g, g))
    for r, rows in by_route.items():
        if not len(rows):
            continue
        scale = max(int(n_stops[r]) - 1, 1)
        ci = np.minimum((rows["a"].to_numpy() / scale * g).astype(int), g - 1)
        cj = np.minimum((rows["b"].to_numpy() / scale * g).astype(int), g - 1)
        np.add.at(grids[len_class[r]], (ci, cj), rows["n_tickets"].to_numpy(float))
    sums = grids.sum(axis=(1, 2), keepdims=True)
    return np.where(sums > 0, grids / np.maximum(sums, 1e-12), 1.0 / (g * g))
