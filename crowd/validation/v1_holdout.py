"""V1: temporal hold-out on whole weekdays (design §4, development-plan §9).

Train = first eligible weekdays, test = the remaining ones. Everything (alpha, phi, prior,
profiles, the profile-shrinkage multiplier, z_h, band cuts) is fitted on the training days only.
Headline metrics are proper scores on *counts* (NB log score of daily boarding tickets, OD-pair
log score) because segment flows are not Poisson. Flow agreement is reported on Q (not Pi, which
shares the denominator Z with its target) against a like-for-like empirical target. No cell is
chosen by a test outcome: cells come from the model's training-based support; target cells of a
route-band with no matched test ticket are set to 0 (and counted).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from crowd import flows, stages, supply as supply_mod, tuning
from crowd.estimator import Estimator, dense_counts, fit_estimator, hour_bands
from crowd.index import hour_profile_z, levels_from_cuts, stretch_pi, weighted_percentile
from crowd.pipeline import Context
from crowd.validation import baselines, metrics, targets
from crowd.validation.splits import odd_even, weekday_split

TIER_LABELS = ["<10", "10-74", ">=75"]
DT = "weekday"
MODEL = "model Q-hat (shrinkage chosen on inner split)"
MODEL_FITTED = "model Q-hat (strengths as fitted)"


# -- counts: log score and predictive intervals ----------------------------------------------------

def count_scores(est: Estimator, counts: pd.DataFrame, test_dates: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame]:
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
    strata = {label: tier == t for t, label in enumerate(TIER_LABELS)}
    strata["all"] = np.ones_like(tier, bool)
    strata["all, training mean > 0"] = est.total[DT] > 0
    rows = []
    for label, sel in strata.items():
        row = {"stratum (training tickets/week per cell)": label, "cells x days": int(valid[sel].sum())}
        row.update({name: float(np.nanmean(arr[sel])) for name, arr in scores.items()})
        rows.append(row)

    # 80% intervals on cells with a meaningful count (training mean >= 5 tickets/day)
    lo, hi = metrics.nb_interval(m[..., None], size[..., None])
    lo_b, hi_b = metrics.nb_interval(raw[..., None], phi[..., None])
    sel = valid & (raw >= 5)[..., None]
    interval_rows = []
    for name, (l, h) in {"model": (lo, hi), "B5": (lo_b, hi_b)}.items():
        interval_rows.append({"predictor": name, "cells x days": int(sel.sum()),
                              "80% interval coverage": float(((yy >= l) & (yy <= h))[sel].mean()),
                              "interval score": float(metrics.interval_score(yy, l, h)[sel].mean())})
    return pd.DataFrame(rows), pd.DataFrame(interval_rows)


# -- OD profiles: multinomial log score -----------------------------------------------------------

def od_scores(est: Estimator, est_fitted: Estimator, od_train: pd.DataFrame, od_test: pd.DataFrame, cfg) -> pd.DataFrame:
    """Multinomial log score of held-out matched (a, b) pairs per route-band.

    Every model gets the same uniform floor ``p = (1 - eps) * P + eps / n_cells``, so none of them
    is penalised for a zero cell and none is flattened more than another (an add-k rule would
    flatten models with few effective counts more).
    """
    eps = cfg.validation.od_floor
    geo = est.geo
    pos_of = {int(r): p for p, r in enumerate(est.routes)}
    band_counts = {key: g.groupby(["a", "b"])["n_tickets"].sum().to_dict() for key, g in od_train.groupby(["route", "band"])}
    route_counts = {key: g.groupby(["a", "b"])["n_tickets"].sum().to_dict() for key, g in od_train.groupby("route")}
    edges = cfg.validation.tier_edges

    def empirical(counts: dict | None, a_idx, b_idx, n_cells: float) -> np.ndarray:
        total = sum(counts.values()) if counts else 0.0
        c = np.array([counts.get((int(x), int(y)), 0.0) for x, y in zip(a_idx, b_idx)]) if counts else np.zeros(len(a_idx))
        return (1 - eps) * (c / total if total > 0 else 0.0) + eps / n_cells

    rows = []
    for (route, band), g in od_test.groupby(["route", "band"]):
        r = geo.route_index.get(route)
        if r is None or r not in pos_of:
            continue
        n = int(geo.n_stops[r])
        n_cells = n * (n - 1) / 2
        w, a_idx, b_idx, hours = g["n_tickets"].to_numpy(float), g["a"].to_numpy(), g["b"].to_numpy(), g["hour"].to_numpy()
        p_model = (1 - eps) * est.profiles[pos_of[r]][hours, a_idx, b_idx] + eps / n_cells
        p_fitted = (1 - eps) * est_fitted.profiles[pos_of[r]][hours, a_idx, b_idx] + eps / n_cells
        train_band = band_counts.get((route, band))
        tier = int(np.searchsorted(edges, sum(train_band.values()) if train_band else 0.0, side="right"))
        scored = (p_model, p_fitted, empirical(train_band, a_idx, b_idx, n_cells), empirical(route_counts.get(route), a_idx, b_idx, n_cells),
                  np.full(len(g), 1 / n_cells))
        rows.append((tier, w.sum(), *(float((w * np.log(p)).sum()) for p in scored)))
    df = pd.DataFrame(rows, columns=["tier", "tickets", "model", "fitted", "band", "route", "uniform"])
    out = []
    for label, sel in {**{l: df["tier"] == t for t, l in enumerate(TIER_LABELS)}, "all": df["tier"] >= 0}.items():
        sub, tickets = df[sel], df.loc[sel, "tickets"].sum()
        out.append({"tier (training matched tickets in route-band)": label, "held-out tickets": int(tickets),
                    "model (shrinkage chosen on inner split)": float(sub["model"].sum() / tickets),
                    "model (strengths as fitted)": float(sub["fitted"].sum() / tickets),
                    "route all-day profile": float(sub["route"].sum() / tickets),
                    "raw band profile": float(sub["band"].sum() / tickets),
                    "uniform over i<j": float(sub["uniform"].sum() / tickets)})
    return pd.DataFrame(out)


# -- flows: rank agreement, shape, level kappa -------------------------------------------------------

class FlowInputs:
    """Everything the flow metrics compare: targets, predictors, supply and the level machinery."""

    def __init__(self, ctx: Context, est: Estimator, est_fitted: Estimator, train: np.ndarray, test: np.ndarray):
        cfg, store, self.geo = ctx.cfg, ctx.store, est.geo
        counts, od = store.read_table("counts.parquet"), store.read_table("od_pairs.parquet")
        dh = store.read_table("day_hour_ok.parquet")
        pairs = flows.matched_pairs(stages.tickets(ctx), store.read_table("ticket_stops.parquet"))
        names, self.boh = hour_bands(cfg)
        self.band_names = names
        self.dense = supply_mod.dense_supply(store.read_table("supply.parquet"), self.geo)[DT]
        seats = store.read_table("route_seats.parquet").set_index("route")["seats_per_bus"].reindex(self.geo.names).to_numpy(float)

        def target_for(dates):
            f = targets.rescale_factors(counts, od, dates, self.geo, self.boh, names)
            return targets.empirical_flow(pairs, self.geo, dh, dates, cfg.flows.gamma, f, self.boh)

        raw_target = target_for(test)
        self.unmatched_share = float(np.isnan(raw_target).mean())
        self.target = np.nan_to_num(raw_target)                       # no matched test ticket -> observed flow 0
        half_a, half_b = odd_even(test)
        self.t_a, self.t_b = np.nan_to_num(target_for(half_a)), np.nan_to_num(target_for(half_b))
        b2 = np.nan_to_num(target_for(train))
        self.predictors = {MODEL: est.qhat(DT).astype(float), MODEL_FITTED: est_fitted.qhat(DT).astype(float),
                           **baselines.flow_predictors(est, self.geo, b2, self.dense["N"].astype(float), seats)}
        z = hour_profile_z(counts[counts["date"].isin(train)], DT)
        self.tilt = np.exp(cfg.ensemble.theta_central * z)[None, :]
        self.est, self.cfg = est, cfg

    def selection(self) -> dict[str, np.ndarray]:
        """Cell strata chosen from the model's training-based support only."""
        est, geo = self.est, self.geo
        seg_route = np.repeat(np.arange(geo.n_routes), geo.n_stops - 1)
        pos = np.full(geo.n_routes, -1)
        pos[est.routes] = np.arange(len(est.routes))
        tier = np.where(pos[seg_route][:, None] >= 0, est.tier[DT][pos[seg_route].clip(0)], -1)
        base = self.predictors[MODEL] > 0
        out = {"all cells": base}
        out.update({f"route-hour tier {label}": base & (tier == t) for t, label in enumerate(TIER_LABELS)})
        out.update({f"band {name}": base & (self.boh[None, :] == b) for b, name in enumerate(self.band_names)})
        return out

    def levels(self, flow: np.ndarray, cuts: np.ndarray | None = None):
        """Stretch levels of a flow field (central tilt); cuts are exposure-weighted percentiles unless given."""
        pi, mins, has = stretch_pi(flow, self.dense["Z"].astype(float), self.geo)
        pi, mins = pi * self.tilt, mins * self.tilt
        if cuts is None:
            cuts = weighted_percentile(pi[has], mins[has], [self.cfg.index.p_r1, self.cfg.index.p_r2])
        return levels_from_cuts(pi, has, cuts), cuts, mins, has


def rank_rows(inp: FlowInputs) -> list[dict]:
    """Spearman and top-decile overlap per predictor and stratum, with replicate and noise-free ceilings."""
    rows = []
    for stratum, sel in inp.selection().items():
        for name, pred in inp.predictors.items():
            rows.append({"stratum": stratum, "predictor": name, "cells": int(sel.sum()),
                         "Spearman vs target": metrics.spearman(pred[sel], inp.target[sel]),
                         "top-decile overlap": metrics.top_overlap(pred[sel], inp.target[sel]) if sel.sum() >= 20 else np.nan})
        half = metrics.spearman(inp.t_a[sel], inp.t_b[sel])
        replicate = 2 * half / (1 + half)               # Spearman-Brown: two independent full-length replicates
        rows.append({"stratum": stratum, "predictor": "replicate ceiling (a predictor as noisy as the target)",
                     "cells": int(sel.sum()), "Spearman vs target": replicate})
        rows.append({"stratum": stratum, "predictor": "noise-free ceiling (sqrt of replicate ceiling)",
                     "cells": int(sel.sum()), "Spearman vs target": float(np.sqrt(max(replicate, 0.0)))})
    return rows


def shape_rows(inp: FlowInputs) -> list[dict]:
    """Where along a route the load peaks: within-route-hour Spearman, flow-weighted (the planner's question)."""
    ecfg = inp.cfg.estimator
    return [{"stratum": "route-hours with target >= %g pax/day" % ecfg.shape_min_flow, "predictor": name,
             "within-route-hour shape Spearman": metrics.shape_agreement(pred, inp.target, inp.geo, ecfg.shape_min_flow,
                                                                          ecfg.shape_min_segments)}
            for name, pred in inp.predictors.items()]


def kappa_rows(inp: FlowInputs) -> list[dict]:
    """Level agreement with the held-out target for the model and for B2 (each with its own training cuts)."""
    rows = []
    for name in (MODEL, MODEL_FITTED, "B2"):
        lvl_pred, cuts, mins, has = inp.levels(inp.predictors[name])
        lvl_tgt, _, _, _ = inp.levels(inp.target, cuts)
        ok = has & (mins > 0)
        for stratum, sel in {"all stretch-hours": ok, **{f"band {n}": ok & (inp.boh[None, :] == b)
                                                          for b, n in enumerate(inp.band_names)}}.items():
            rows.append({"stratum": stratum, "predictor": name, "cells": int(sel.sum()),
                         "weighted kappa": metrics.weighted_kappa(lvl_pred[sel], lvl_tgt[sel], mins[sel])})
    return rows


def run_v1(ctx: Context) -> tuple[dict[str, pd.DataFrame], Estimator, FlowInputs, np.ndarray]:
    """All V1 tables (also written under ``out/validation/``), the training-day estimator, the flow
    inputs and the training dates (V10 reuses them)."""
    store, geo, cfg = ctx.store, stages.geometry(ctx), ctx.cfg
    counts, od = store.read_table("counts.parquet"), store.read_table("od_pairs.parquet")
    dh, info = store.read_table("day_hour_ok.parquet"), store.read_table("route_info.parquet")
    train, test = weekday_split(dh, cfg)
    service = stages.service(ctx)
    pairs = flows.matched_pairs(stages.tickets(ctx), store.read_table("ticket_stops.parquet"))
    scale, scale_scores = tuning.choose_strength_scale(counts, od, pairs, dh, geo, info, service, cfg, train)
    est = fit_estimator(counts, od, geo, info, cfg, service=service, train_dates=train, strength_scale=scale)
    est_fitted = fit_estimator(counts, od, geo, info, cfg, service=service, train_dates=train)
    count_tbl, interval_tbl = count_scores(est, counts, test)
    od_tbl = od_scores(est, est_fitted, od[od["date"].isin(train)], od[od["date"].isin(test)], cfg)
    inp = FlowInputs(ctx, est, est_fitted, train, test)
    flow_tbl = pd.concat([pd.DataFrame(rank_rows(inp)), pd.DataFrame(shape_rows(inp)), pd.DataFrame(kappa_rows(inp))],
                         ignore_index=True)
    tuning_tbl = pd.DataFrame({"strength multiplier": list(scale_scores), "inner-split shape Spearman": list(scale_scores.values()),
                               "chosen": [s == scale for s in scale_scores]})
    split = pd.DataFrame({"set": ["train", "test"], "days": [len(train), len(test)],
                          "first": [str(train.min())[:10], str(test.min())[:10]], "last": [str(train.max())[:10], str(test.max())[:10]]})
    notes = pd.DataFrame({"note": [f"target cells of route-bands with no matched test ticket (set to 0): {inp.unmatched_share:.1%} of segment-hours"]})
    tables = {"split": split, "tuning": tuning_tbl, "count_log_score": count_tbl, "interval_calibration": interval_tbl,
              "od_log_score": od_tbl, "flow_agreement": flow_tbl, "notes": notes}
    out_dir = store.path("validation")
    out_dir.mkdir(exist_ok=True)
    for name, df in tables.items():
        df.to_csv(out_dir / f"v1_{name}.csv", index=False)
    return tables, est, inp, train
