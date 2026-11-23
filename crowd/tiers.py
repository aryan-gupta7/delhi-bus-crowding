"""Evidence tiers: evidence only, not scale uncertainty.

Tier = the lower of the volume tier (route-hour tickets and posterior CV) and the profile tier
(matched training tickets covering the stretch). Small-N cells are capped at Medium, weekend
cells at Low, and routes with too little matched coverage have no estimate.
"""

from __future__ import annotations

import numpy as np

from crowd.config import Config

TIER_NAMES = ["No estimate", "Low", "Medium", "High"]


def volume_tier_code(tickets: np.ndarray, cv: np.ndarray, cfg: Config) -> np.ndarray:
    """0 None, 1 Low, 2 Medium, 3 High from ticket counts and posterior CV."""
    t = cfg.tiers
    code = np.zeros(np.broadcast(tickets, cv).shape, dtype=np.int8)
    code[tickets >= t.low.min_tickets] = 1
    code[(tickets >= t.medium.min_tickets) & (cv <= t.medium.max_cv)] = 2
    code[(tickets >= t.high.min_tickets) & (cv <= t.high.max_cv)] = 3
    return code


def profile_tier_code(n_od_cov: np.ndarray, cfg: Config) -> np.ndarray:
    """Same thresholds applied to matched tickets covering the stretch."""
    t = cfg.tiers
    code = np.zeros(n_od_cov.shape, dtype=np.int8)
    code[n_od_cov >= t.low.min_tickets] = 1
    code[n_od_cov >= t.medium.min_tickets] = 2
    code[n_od_cov >= t.high.min_tickets] = 3
    return code


def combine(volume: np.ndarray, profile: np.ndarray, n_buses: np.ndarray, weekend: bool,
            route_cov: np.ndarray, cfg: Config) -> np.ndarray:
    """Final tier code after the evidence caps."""
    tier = np.minimum(volume, profile)
    tier = np.where(n_buses <= cfg.tiers.small_n, np.minimum(tier, 2), tier)
    if weekend:
        tier = np.minimum(tier, 1)
    return np.where(route_cov < cfg.tiers.min_route_coverage, 0, tier).astype(np.int8)
