"""S7: scenario ensemble, levels and the robust-in-range flag (design/mechanism.md S7).

Each of K draws combines a posterior draw of the boarding volumes (sampling uncertainty, a
probability) with an hour tilt ``theta_k`` (stratified over a one-sided grid) and a route effect
``eps_{r,k}`` (scenario uncertainty about who the tickets represent, not a probability):

    Pi_k = Q_k / Z * exp(theta_k * z_h + eps_{r,k})

Band cuts are recomputed per draw. The displayed level is the level at the *central* scenario
(posterior-mean volumes, central theta, eps = 0); ``robust_in_range`` says the same level holds
in at least ``robust_share`` of the draws across the stated range. It is a sensitivity analysis
over an assumed family, not a posterior probability. Common scale factors (rho, omega, kappa0,
a common seat scale) cancel in within-day-type percentiles and are therefore not in the ensemble.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from crowd import tiers
from crowd.config import Config
from crowd.estimator import Estimator
from crowd.index import StretchGrid, levels_from_cuts, weighted_percentile


@dataclass
class EnsembleResult:
    cells: pd.DataFrame            # crowding_cells (one row per cell with scheduled service)
    levels: np.ndarray             # uint8 [n_cells, K], aligned with ``cells``
    cuts: dict                     # frozen band cuts per day-type (central + per draw)
    pi_draws: dict                 # day_type -> float32 [K, n_cells]  (for planner / Gamma*)


@dataclass
class Scenario:
    """Hour-tilt grid, central tilt and route-effect spread (A-10)."""

    theta_grid: tuple[float, ...]
    theta_central: float
    sigma_r: float

    @classmethod
    def from_config(cls, cfg: Config, sigma_r: float | None = None,
                    theta_grid: tuple[float, ...] | None = None) -> "Scenario":
        e = cfg.ensemble
        grid = tuple(theta_grid) if theta_grid is not None else tuple(e.theta_grid)
        return cls(grid, float(e.theta_central), float(e.sigma_r if sigma_r is None else sigma_r))


def _route_blocks(est: Estimator, day_type: str, supply: dict, z: np.ndarray, scn: Scenario, k: int,
                  seed: int):
    """Yield per-route arrays for the ensemble: aggregated Pi draws, weights, central values."""
    geo = est.geo
    theta = np.array([scn.theta_grid[i % len(scn.theta_grid)] for i in range(k)])
    for pos, r in enumerate(est.routes):
        r = int(r)
        sl = geo.segs_of(r)
        sg = StretchGrid(geo, r)
        z_den = sg.sum(supply["Z"][sl])                                       # sum Z tau   [n_str, 24]
        tau_sum = np.add.reduceat(sg.tau, sg.starts)[:, None]
        n_str = sg.sum(supply["N"][sl]) / tau_sum                             # tau-weighted mean N
        valid = z_den > 0
        den = np.where(valid, z_den, 1.0)

        lam_draw = est.draw_lambda(day_type, pos, k, seed) * est.group[pos]   # [K, 24]
        num = sg.sum(est.qhat_route(pos, lam_draw))                           # [K, n_str, 24]
        pi_k = np.where(valid, num / den, 0.0)
        eps = scn.sigma_r * np.random.default_rng([seed, r, 7]).standard_normal(k)
        tilt = np.exp(theta[:, None, None] * z[None, None, :] + eps[:, None, None])

        num_c = sg.sum(est.qhat_route(pos, est.lam_eff_mean(day_type)[pos]))  # [n_str, 24]
        tilt_c = np.exp(scn.theta_central * z)[None, :]
        yield {
            "pos": pos, "r": r, "sg": sg, "valid": valid, "n": n_str, "z_den": z_den,
            "tau_sum": tau_sum, "pi_k": pi_k, "pi_t": pi_k * tilt, "w_t": num * tilt,
            "pi_c0": np.where(valid, num_c / den, 0.0), "pi_c": np.where(valid, num_c / den, 0.0) * tilt_c,
            "w_c": num_c * tilt_c,
        }


def run_ensemble(est: Estimator, supply: dict, route_seats: pd.DataFrame, route_cov: np.ndarray,
                 route_info: pd.DataFrame, z: dict[str, np.ndarray], cfg: Config,
                 scenario: Scenario | None = None, frozen_cuts: dict | None = None) -> EnsembleResult:
    """Run the ensemble for both day-types and assemble the crowding-cell table."""
    scn = scenario or Scenario.from_config(cfg)
    k = int(cfg.ensemble.k)
    if k % len(scn.theta_grid):
        raise ValueError("ensemble.k must be a multiple of the theta grid size (stratified theta)")
    geo, seed = est.geo, int(cfg.seed)
    p1, p2 = cfg.index.p_r1, cfg.index.p_r2
    seat_src = route_seats.set_index("route")["seats_source"].reindex(geo.names).to_numpy()
    seats_bus = route_seats.set_index("route")["seats_per_bus"].reindex(geo.names).to_numpy()
    direction = route_info.set_index("route")["direction"].reindex(geo.names).to_numpy()

    frames, level_blocks, pi_draws, cuts_out = [], [], {}, {}
    for day_type, sup in supply.items():
        blocks = list(_route_blocks(est, day_type, sup, z[day_type], scn, k, seed))
        valid = np.concatenate([b["valid"].ravel() for b in blocks])
        pi_t = np.concatenate([b["pi_t"].reshape(k, -1) for b in blocks], axis=1).astype(np.float32)
        w_t = np.concatenate([b["w_t"].reshape(k, -1) for b in blocks], axis=1)
        pi_c = np.concatenate([b["pi_c"].ravel() for b in blocks])
        w_c = np.concatenate([b["w_c"].ravel() for b in blocks])

        if frozen_cuts is None:
            central_cuts = weighted_percentile(pi_c[valid], w_c[valid], [p1, p2])
            draw_cuts = np.stack([weighted_percentile(pi_t[i][valid], w_t[i][valid], [p1, p2]) for i in range(k)])
        else:
            central_cuts = np.asarray(frozen_cuts[day_type]["central"])
            draw_cuts = np.asarray(frozen_cuts[day_type]["draws"])
        cuts_out[day_type] = {"central": central_cuts, "draws": draw_cuts}

        level_c = levels_from_cuts(pi_c, valid, central_cuts)
        level_k = np.stack([levels_from_cuts(pi_t[i], valid, draw_cuts[i]) for i in range(k)], axis=1)  # [cells, K]
        share = np.stack([(level_k == lv).mean(axis=1) for lv in (1, 2, 3)], axis=1)
        agree = (level_k == level_c[:, None]).mean(axis=1)

        frames.append(_cell_frame(est, day_type, blocks, geo, cfg, level_c, share, agree, pi_t, valid,
                                  seat_src, seats_bus, direction, route_cov))
        level_blocks.append(level_k[valid])
        pi_draws[day_type] = pi_t[:, valid]
    cells = pd.concat(frames, ignore_index=True)
    return EnsembleResult(cells=cells, levels=np.concatenate(level_blocks, axis=0), cuts=cuts_out, pi_draws=pi_draws)


def _cell_frame(est, day_type, blocks, geo, cfg, level_c, share, agree, pi_t, valid, seat_src, seats_bus,
                direction, route_cov) -> pd.DataFrame:
    """Assemble the per-cell table (cells with scheduled service only) for one day-type."""
    cols: dict[str, list] = {k: [] for k in (
        "route", "stretch_id", "hour", "pi_mean", "pi_central", "pi_lo", "pi_hi", "tier_volume",
        "tier_profile", "tier_code", "n_tickets_eff", "n_od_cov", "N", "Z", "seats", "flags")}
    weekend = day_type == "weekend"
    for b in blocks:
        pos, r, sg = b["pos"], b["r"], b["sg"]
        n_str = sg.n_stretches
        hours = np.tile(np.arange(24), n_str)
        tickets = np.broadcast_to(est.total[day_type][pos], (n_str, 24))
        cv = np.broadcast_to(1.0 / np.sqrt(np.maximum(est.shape[day_type][pos], 1e-6)), (n_str, 24))
        od_cov = sg.mean_over_segments(est.od_cov[pos].T)[:, est.band_of_hour]          # [n_str, 24]
        vol_t = tiers.volume_tier_code(tickets, cv, cfg)
        prof_t = tiers.profile_tier_code(od_cov, cfg)
        tier = tiers.combine(vol_t, prof_t, b["n"], weekend, route_cov[r], cfg)
        lo, hi = np.quantile(b["pi_k"], [0.1, 0.9], axis=0)
        flag = np.where(b["n"] <= cfg.tiers.small_n, "small_N", "")
        flag = np.char.add(flag, np.where(seat_src[r] == "fleet_default", ",default_seats", ""))
        for name, arr in (
            ("route", np.full(n_str * 24, geo.names[r], dtype=object)),
            ("stretch_id", np.repeat(sg.stretch_ids, 24)), ("hour", hours),
            ("pi_mean", b["pi_c0"].ravel()), ("pi_central", b["pi_c"].ravel()),
            ("pi_lo", lo.ravel()), ("pi_hi", hi.ravel()),
            ("tier_volume", vol_t.ravel()), ("tier_profile", prof_t.ravel()), ("tier_code", tier.ravel()),
            ("n_tickets_eff", tickets.ravel()), ("n_od_cov", od_cov.ravel()),
            ("N", b["n"].ravel()), ("Z", (b["z_den"] / b["tau_sum"]).ravel()),
            ("seats", np.full(n_str * 24, seats_bus[r])), ("flags", flag.ravel()),
        ):
            cols[name].append(arr)
    df = pd.DataFrame({k_: np.concatenate(v) for k_, v in cols.items()})
    df["direction"] = direction[geo.route_ix(df["route"])]
    df["day_type"] = day_type
    df["level"] = level_c
    df["p_l1"], df["p_l2"], df["p_l3"] = share[:, 0], share[:, 1], share[:, 2]
    df["robust_in_range"] = agree >= cfg.ensemble.robust_share
    df["pi_scn_lo"], df["pi_scn_hi"] = np.quantile(pi_t, [0.1, 0.9], axis=0)
    df["cov_route"] = route_cov[geo.route_ix(df["route"])]
    df["tier"] = [tiers.TIER_NAMES[c] for c in df["tier_code"]]
    out = df[valid].reset_index(drop=True)
    out["flags"] = out["flags"].str.strip(",")
    return out.drop(columns="tier_code").astype({
        "stretch_id": "int32", "hour": "int8", "level": "int8", "N": "float32", "Z": "float32",
        "seats": "float32", "n_tickets_eff": "float32", "n_od_cov": "float32", "cov_route": "float32"})
