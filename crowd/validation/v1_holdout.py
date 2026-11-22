"""V1: temporal hold-out on whole weekdays (design §4, development-plan §9).

Train = first eligible weekdays, test = the remaining ones. Everything (alpha, phi, prior,
profiles, z_h, band cuts) is fitted on the training days only. Headline metrics are proper
scores on *counts* (NB log score of daily boarding tickets, multinomial OD log score) because
segment flows are not Poisson. Flow agreement is reported on Q (not Pi, which shares the
denominator Z with its target) against a like-for-like empirical target, with the noise ceiling
(odd/even test halves) next to every agreement statistic. Cells and tiers are chosen from
training counts only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from crowd import flows, stages, supply as supply_mod
from crowd.estimator import Estimator, fit_estimator, dense_counts
from crowd.index import hour_profile_z, levels_from_cuts, stretch_pi, weighted_percentile
from crowd.pipeline import Context
from crowd.validation import baselines, metrics, targets
from crowd.validation.splits import odd_even, weekday_split

TIER_LABELS = ["<10 tickets/week", "10-74", ">=75"]
DT = "weekday"


def _tier_label(t: int) -> str:
    return TIER_LABELS[t]


# -- counts: log score and predictive intervals ----------------------------------------------------

def count_scores(est: Estimator, counts: pd.DataFrame, test_dates: np.ndarray, cfg) -> tuple[pd.DataFrame, pd.DataFrame]:
    """NB log score and 80% interval calibration on held-out daily boarding counts."""
    y = dense_counts(counts[counts["date"].isin(test_dates)], est.geo, DT, est.routes)    # [R, 24, D]
    valid = ~np.isnan(y)
    m, a, b = np.maximum(est.lam_mean(DT), baselines.MEAN_FLOOR), est.shape[DT], est.rate[DT]   # same floor as baselines
    phi = est.phi[DT][est.tier[DT]]
    phi = np.where(np.isfinite(phi), phi, 1e6)
    var = m + (m ** 2 + a / b ** 2) / phi + a / b ** 2          # day dispersion + parameter uncertainty
    size = metrics.moment_matched_size(m, var)
    raw = baselines.raw_means(est, DT)
    yy = np.where(valid, y, 0.0)

    def per_cell(fn) -> np.ndarray:
        return np.where(valid, fn(yy), np.nan)

    scores = {
        "model (Poisson-gamma + phi)": per_cell(lambda v: metrics.nb_logpmf(v, m[..., None], size[..., None])),
        "B5 per-cell MLE, NB": per_cell(lambda v: metrics.nb_logpmf(v, raw[..., None], phi[..., None])),
        "B0 per-cell MLE, Poisson": per_cell(lambda v: metrics.poisson_logpmf(v, raw[..., None])),
        "Bc citywide-share prior, NB": per_cell(lambda v: metrics.nb_logpmf(
            v, np.maximum(est.prior_mean[DT], baselines.MEAN_FLOOR)[..., None], phi[..., None])),
    }
    tier = est.tier[DT]
    rows = []
    for t in list(range(len(TIER_LABELS))) + [None]:
        sel = np.ones_like(tier, bool) if t is None else tier == t
        row = {"tier (training counts)": "all" if t is None else _tier_label(t), "cells x days": int(valid[sel].sum())}
        for name, arr in scores.items():
            row[name] = float(np.nanmean(arr[sel]))
        rows.append(row)
    score_table = pd.DataFrame(rows)

    # 80% intervals on cells with a meaningful count (training mean >= 5 tickets/day)
    dense = raw >= 5
    lo, hi = metrics.nb_interval(m[..., None], size[..., None])
    lo_b, hi_b = metrics.nb_interval(raw[..., None], phi[..., None])
    rows = []
    for name, (l, h) in {"model": (lo, hi), "B5": (lo_b, hi_b)}.items():
        sel = valid & dense[..., None]
        covered = ((yy >= l) & (yy <= h))[sel]
        rows.append({"predictor": name, "cells x days": int(sel.sum()), "80% interval coverage": float(covered.mean()),
                     "interval score": float(metrics.interval_score(yy, l, h)[sel].mean())})
    return score_table, pd.DataFrame(rows)


# -- OD profiles: multinomial log score -----------------------------------------------------------

def od_scores(est: Estimator, od_train: pd.DataFrame, od_test: pd.DataFrame, cfg) -> pd.DataFrame:
    """Multinomial log score of held-out matched (a, b) pairs per route-band.

    Every model gets the same uniform floor ``p = (1 - eps) * P + eps / n_cells``, so none of them
    is penalised for a zero cell and none is flattened more than another (an add-k rule would
    flatten models with few effective counts more).
    """
    eps = cfg.validation.od_floor
    geo = est.geo
    pos_of = {int(r): p for p, r in enumerate(est.routes)}
    train_groups = {key: g for key, g in od_train.groupby(["route", "band"])}
    edges = cfg.validation.tier_edges
    rows = []
    for (route, band), g in od_test.groupby(["route", "band"]):
        r = geo.route_index.get(route)
        if r is None or r not in pos_of:
            continue
        pos = pos_of[r]
        n = int(geo.n_stops[r])
        n_cells = n * (n - 1) / 2
        w = g["n_tickets"].to_numpy(float)
        a_idx, b_idx = g["a"].to_numpy(), g["b"].to_numpy()
        hours = g["hour"].to_numpy()
        p_model = (1 - eps) * est.profiles[pos][hours, a_idx, b_idx] + eps / n_cells
        tr = train_groups.get((route, band))
        if tr is not None and len(tr):
            counts = tr.groupby(["a", "b"])["n_tickets"].sum()
            c_train = float(counts.sum())
            lookup = counts.to_dict()
            c_ab = np.array([lookup.get((int(x), int(y)), 0.0) for x, y in zip(a_idx, b_idx)])
        else:
            c_train, c_ab = 0.0, np.zeros(len(g))
        p_raw = (1 - eps) * (c_ab / c_train if c_train > 0 else 0.0) + eps / n_cells
        tier = int(np.searchsorted(edges, c_train, side="right"))
        rows.append((tier, w.sum(), (w * np.log(p_model)).sum(), (w * np.log(1 / n_cells)).sum(),
                     (w * np.log(p_raw)).sum()))
    df = pd.DataFrame(rows, columns=["tier", "tickets", "model", "uniform", "raw_band"])
    out = []
    for t in list(range(len(TIER_LABELS))) + [None]:
        sub = df if t is None else df[df["tier"] == t]
        tickets = sub["tickets"].sum()
        out.append({"tier (training pairs in route-band)": "all" if t is None else _tier_label(t),
                    "held-out tickets": int(tickets),
                    "model (hour profile shrunk to band, route, length class)": float(sub["model"].sum() / tickets),
                    "raw band profile": float(sub["raw_band"].sum() / tickets),
                    "uniform over i<j": float(sub["uniform"].sum() / tickets)})
    return pd.DataFrame(out)


# -- flows: rank agreement, top decile, level kappa with noise ceilings --------------------------------

def _levels(pi: np.ndarray, weights: np.ndarray, valid: np.ndarray, cuts: np.ndarray | None, cfg):
    if cuts is None:
        cuts = weighted_percentile(pi[valid], weights[valid], [cfg.index.p_r1, cfg.index.p_r2])
    return levels_from_cuts(pi, valid, cuts), cuts


def flow_agreement(ctx: Context, est: Estimator, train: np.ndarray, test: np.ndarray) -> pd.DataFrame:
    """Q-hat (and baselines) against the like-for-like held-out flow, with noise ceilings."""
    cfg, store, geo = ctx.cfg, ctx.store, est.geo
    counts, od = store.read_table("counts.parquet"), store.read_table("od_pairs.parquet")
    dh = store.read_table("day_hour_ok.parquet")
    seats = store.read_table("route_seats.parquet")
    dense = supply_mod.dense_supply(store.read_table("supply.parquet"), geo)[DT]
    pairs = flows.matched_pairs(stages.tickets(ctx), store.read_table("ticket_stops.parquet"))
    gamma = cfg.flows.gamma
    band_names, boh = est.band_names, est.band_of_hour

    def target_for(dates):
        f = targets.rescale_factors(counts, od, dates, geo, boh, band_names)
        return targets.empirical_flow(pairs, geo, dh, dates, gamma, f, boh)

    target = target_for(test)
    half_a, half_b = odd_even(test)
    t_a, t_b = target_for(half_a), target_for(half_b)
    b2 = target_for(train)
    seats_route = seats.set_index("route")["seats_per_bus"].reindex(geo.names).to_numpy(float)
    predictors = {"model Q-hat": est.qhat(DT).astype(float),
                  **baselines.flow_predictors(est, geo, np.nan_to_num(b2), dense["N"].astype(float), seats_route)}

    seg_route = np.repeat(np.arange(geo.n_routes), geo.n_stops - 1)
    in_train = np.zeros(geo.n_routes, bool)
    in_train[est.routes] = True
    pos = np.full(geo.n_routes, -1)
    pos[est.routes] = np.arange(len(est.routes))
    tier_seg = np.where(in_train[seg_route][:, None], est.tier[DT][pos[seg_route].clip(0)], -1)
    base = (predictors["model Q-hat"] > 0) & np.isfinite(target) & np.isfinite(t_a) & np.isfinite(t_b)   # training-only selection
    strata = {"all cells": base}
    for t, label in enumerate(TIER_LABELS):
        strata[f"route-hour tier {label}"] = base & (tier_seg == t)
    for b, name in enumerate(band_names):
        strata[f"band {name}"] = base & (boh[None, :] == b)

    z = hour_profile_z(counts[counts["date"].isin(train)], DT)
    tilt = np.exp(cfg.ensemble.theta_central * z)[None, :]
    pi_model, w_model, has = stretch_pi(predictors["model Q-hat"], dense["Z"].astype(float), geo)
    pi_model = pi_model * tilt
    lvl_model, cuts = _levels(pi_model, w_model * tilt, has, None, cfg)
    pi_tgt, _, _ = stretch_pi(np.nan_to_num(target), dense["Z"].astype(float), geo)
    lvl_tgt, _ = _levels(pi_tgt * tilt, w_model, has, cuts, cfg)
    pi_a, w_a, _ = stretch_pi(np.nan_to_num(t_a), dense["Z"].astype(float), geo)
    pi_b, _, _ = stretch_pi(np.nan_to_num(t_b), dense["Z"].astype(float), geo)
    lvl_a, cuts_a = _levels(pi_a * tilt, w_a * tilt, has, None, cfg)
    lvl_b, _ = _levels(pi_b * tilt, w_a, has, cuts_a, cfg)
    stretch_hour_ok = has & (w_model > 0)
    stretch_band = np.broadcast_to(boh[None, :], has.shape)

    rows = []
    for stratum, sel in strata.items():
        x_t = target[sel]
        for name, pred in predictors.items():
            rows.append({"stratum": stratum, "predictor": name, "cells": int(sel.sum()),
                         "Spearman vs target": metrics.spearman(pred[sel], x_t),
                         "top-decile overlap": metrics.top_overlap(pred[sel], x_t) if sel.sum() >= 20 else np.nan})
        r_half = metrics.spearman(t_a[sel], t_b[sel])
        rows.append({"stratum": stratum, "predictor": "noise ceiling (odd vs even test days; Spearman-Brown for the full test set)",
                     "cells": int(sel.sum()), "Spearman vs target": 2 * r_half / (1 + r_half),
                     "top-decile overlap": metrics.top_overlap(t_a[sel], t_b[sel]) if sel.sum() >= 20 else np.nan})
    for stratum, sel in {"all stretch-hours": stretch_hour_ok,
                         **{f"band {n}": stretch_hour_ok & (stretch_band == b) for b, n in enumerate(band_names)}}.items():
        rows.append({"stratum": stratum, "predictor": "level kappa: model vs target (train cuts)", "cells": int(sel.sum()),
                     "weighted kappa": metrics.weighted_kappa(lvl_model[sel], lvl_tgt[sel], w_model[sel])})
        rows.append({"stratum": stratum, "predictor": "level kappa ceiling (odd vs even test days)", "cells": int(sel.sum()),
                     "weighted kappa": metrics.weighted_kappa(lvl_a[sel], lvl_b[sel], w_a[sel])})
    return pd.DataFrame(rows)


def run_v1(ctx: Context) -> dict[str, pd.DataFrame]:
    """All V1 tables (also written under ``out/validation/``)."""
    store, geo = ctx.store, stages.geometry(ctx)
    counts, od = store.read_table("counts.parquet"), store.read_table("od_pairs.parquet")
    dh, info = store.read_table("day_hour_ok.parquet"), store.read_table("route_info.parquet")
    train, test = weekday_split(dh, ctx.cfg)
    est = fit_estimator(counts, od, geo, info, ctx.cfg, service=stages.service(ctx), train_dates=train)
    count_tbl, interval_tbl = count_scores(est, counts, test, ctx.cfg)
    od_tbl = od_scores(est, od[od["date"].isin(train)], od[od["date"].isin(test)], ctx.cfg)
    flow_tbl = flow_agreement(ctx, est, train, test)
    split = pd.DataFrame({"set": ["train", "test"], "days": [len(train), len(test)],
                          "first": [train.min(), test.min()], "last": [train.max(), test.max()]})
    tables = {"split": split, "count_log_score": count_tbl, "interval_calibration": interval_tbl,
              "od_log_score": od_tbl, "flow_agreement": flow_tbl}
    out_dir = store.path("validation")
    out_dir.mkdir(exist_ok=True)
    for name, df in tables.items():
        df.to_csv(out_dir / f"v1_{name}.csv", index=False)
    return tables
