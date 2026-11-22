"""Scoring rules and agreement metrics used by the held-out validation."""

from __future__ import annotations

import numpy as np
from scipy.special import gammaln
from scipy.stats import nbinom, spearmanr


def poisson_logpmf(y: np.ndarray, mean: np.ndarray) -> np.ndarray:
    m = np.maximum(mean, 1e-12)
    return y * np.log(m) - m - gammaln(y + 1)


def nb_logpmf(y: np.ndarray, mean: np.ndarray, size: np.ndarray | float) -> np.ndarray:
    """Negative-binomial log pmf with the given mean and size (variance = mean + mean^2 / size)."""
    m = np.maximum(mean, 1e-12)
    return (gammaln(y + size) - gammaln(size) - gammaln(y + 1)
            + size * np.log(size / (size + m)) + y * np.log(m / (size + m)))


def moment_matched_size(mean: np.ndarray, var: np.ndarray) -> np.ndarray:
    """NB size matching a given mean and variance (variance is floored just above the mean)."""
    return mean ** 2 / np.maximum(var - mean, 1e-9)


def nb_interval(mean: np.ndarray, size: np.ndarray, alpha: float = 0.2) -> tuple[np.ndarray, np.ndarray]:
    """Central ``1 - alpha`` predictive interval of an NB with the given mean and size."""
    p = size / (size + np.maximum(mean, 1e-12))
    return nbinom.ppf(alpha / 2, size, p), nbinom.ppf(1 - alpha / 2, size, p)


def interval_score(y: np.ndarray, lo: np.ndarray, hi: np.ndarray, alpha: float = 0.2) -> np.ndarray:
    """Gneiting & Raftery (2007) interval score: width plus penalties for misses (lower is better)."""
    return (hi - lo) + (2 / alpha) * np.maximum(lo - y, 0) + (2 / alpha) * np.maximum(y - hi, 0)


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 3 or np.ptp(a) == 0 or np.ptp(b) == 0:
        return float("nan")
    return float(spearmanr(a, b)[0])


def shape_agreement(pred: np.ndarray, target: np.ndarray, geo, min_flow: float, min_segments: int) -> float:
    """Flow-weighted mean Spearman, across segments, within each route-hour (where along the route
    the load peaks). ``pred`` and ``target`` are ``[n_seg, 24]``; route-hours with a small target
    flow or few segments are ignored."""
    total, weight = 0.0, 0.0
    for r in range(geo.n_routes):
        sl = geo.segs_of(r)
        if sl.stop - sl.start < min_segments:
            continue
        for h in np.flatnonzero(target[sl].sum(axis=0) >= min_flow):
            rho = spearman(pred[sl, h], target[sl, h])
            if rho == rho:
                total += rho * target[sl, h].sum()
                weight += target[sl, h].sum()
    return total / weight if weight else float("nan")


def top_overlap(score: np.ndarray, target: np.ndarray, frac: float = 0.1) -> float:
    """Share of the model's top ``frac`` cells that are also in the target's top ``frac`` cells."""
    k = max(int(len(score) * frac), 1)
    top_a = set(np.argpartition(-score, k - 1)[:k])
    top_b = set(np.argpartition(-target, k - 1)[:k])
    return len(top_a & top_b) / k


def weighted_kappa(a: np.ndarray, b: np.ndarray, weights: np.ndarray | None = None, n_levels: int = 3) -> float:
    """Quadratic-weighted Cohen's kappa between two level vectors (levels 1..n_levels)."""
    w = np.ones(len(a)) if weights is None else weights
    obs = np.zeros((n_levels, n_levels))
    np.add.at(obs, (a - 1, b - 1), w)
    obs /= obs.sum()
    exp = np.outer(obs.sum(axis=1), obs.sum(axis=0))
    i, j = np.indices(obs.shape)
    cost = (i - j) ** 2 / max(n_levels - 1, 1) ** 2
    denom = (cost * exp).sum()
    return float(1 - (cost * obs).sum() / denom) if denom > 0 else float("nan")
