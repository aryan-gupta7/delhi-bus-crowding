"""V9: how much the shown recommendations and the robust share depend on the invented assumptions.

Re-runs the ensemble under alternative scenario families, discomfort multipliers and the two
small-N treatments, and re-plans the same random queries each time. Reports the "More comfortable"
suppression rate by hour band, how many recommendations change, the exposure share of robust cells,
the robustness value Gamma*, and the exposure share whose level changes. These are sensitivity
analyses, not unseen-case evidence.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from crowd import stages, supply as supply_mod
from crowd.ensemble import Scenario, run_ensemble
from crowd.index import hour_profile_z
from crowd.outputs import CrowdingTable
from crowd.pipeline import Context
from crowd.planner.service import Planner
from crowd.validation.queries import Query

HOUR_BANDS = {"peak am (07-10)": range(7, 11), "midday (11-16)": range(11, 17), "peak pm (17-20)": range(17, 21)}
ROUTE_SWITCH_THRESHOLDS = {"sigma 0.4": 1.61, "sigma 0.9": 2.91}      # exp(0.84 * sigma * sqrt(2)), from the design


def smooth_hours(dense: dict) -> dict:
    """Quarter-half-quarter smoothing of scheduled buses across hours (wrapping at midnight)."""
    out = {}
    for day_type, v in dense.items():
        n = 0.25 * np.roll(v["N"], 1, axis=1) + 0.5 * v["N"] + 0.25 * np.roll(v["N"], -1, axis=1)
        seats = np.where(v["N"] > 0, v["Z"] / np.maximum(v["N"], 1e-9), 0).max(axis=1, keepdims=True)
        out[day_type] = {"N": n.astype(np.float32), "Z": (n * seats).astype(np.float32)}
    return out


def _level_change_share(base: pd.DataFrame, other: pd.DataFrame) -> float:
    """Exposure share (base passenger pressure x seats, weekday) of base cells whose central level differs
    in ``other``; a base cell missing from ``other`` counts as changed."""
    keys = ["route", "stretch_id", "hour", "day_type"]
    b = base[base["day_type"] == "weekday"][keys + ["level", "pi_central", "Z"]]
    merged = b.merge(other[keys + ["level"]], on=keys, how="left", suffixes=("", "_other"))
    weight = (merged["pi_central"] * merged["Z"]).to_numpy()
    moved = (merged["level"] != merged["level_other"]).to_numpy()
    return float(weight[moved].sum() / weight.sum())


def _plans(planner: Planner, queries: list[Query]) -> pd.DataFrame:
    rows = []
    for q in queries:
        out = planner.plan(q.from_stop, q.to_stop, q.time)
        ev = out.get("evidence") or {}
        calmer = out["cards"].get("comfortable")
        rows.append({"hour": q.hour, "shown": calmer is not None,
                     "calmer_routes": tuple(leg["route"] for leg in calmer["legs"]) if calmer else None,
                     "gamma_star": ev.get("gamma_star")})
    return pd.DataFrame(rows)


def _band_rates(df: pd.DataFrame) -> dict[str, float]:
    return {f"shown: {name}": float(df.loc[df["hour"].isin(hours), "shown"].mean()) for name, hours in HOUR_BANDS.items()}


def run_v9(ctx: Context, planner: Planner, queries: list[Query]) -> dict[str, pd.DataFrame]:
    """Sensitivity tables: per-setting recommendation behaviour, and the Gamma* distribution."""
    st, cfg = ctx.store, ctx.cfg
    est, geo = stages.estimator(ctx), stages.geometry(ctx)
    dense = supply_mod.dense_supply(st.read_table("supply.parquet"), geo)
    smoothed = smooth_hours(dense)
    counts = st.read_table("counts.parquet")
    z = {dt: hour_profile_z(counts, dt) for dt in ("weekday", "weekend")}
    seats, coverage, info = st.read_table("route_seats.parquet"), stages.route_coverage_array(ctx), st.read_table("route_info.parquet")
    cache: dict = {}

    def ensemble(scenario: Scenario, smooth_n: bool):
        """Ensemble results are shared between settings that differ only in the planner's multipliers."""
        if (scenario, smooth_n) not in cache:
            cache[(scenario, smooth_n)] = run_ensemble(est, smoothed if smooth_n else dense, seats, coverage, info, z, cfg, scenario)
        return cache[(scenario, smooth_n)]

    base = Scenario.from_config(cfg)
    multiplier_sets = {"multipliers 1.0/1.25/1.6": [1.0, 1.25, 1.6], "multipliers 1.0/1.3/3.0": [1.0, 1.3, 3.0]}
    settings = {                                             # name -> (scenario, smooth N, planner config)
        "base: sigma 0.4, theta in {-0.4,-0.2,0}": (base, False, cfg),
        "route effect sigma 0.0": (Scenario.from_config(cfg, sigma_r=0.0), False, cfg),
        "route effect sigma 0.9": (Scenario.from_config(cfg, sigma_r=0.9), False, cfg),
        "theta = 0 only (constant capture)": (Scenario.from_config(cfg, theta_grid=(0.0,)), False, cfg),
        "theta = -0.2 only": (Scenario.from_config(cfg, theta_grid=(-0.2,)), False, cfg),
        "small-N: Pi shrink n0=2": (Scenario.from_config(cfg, small_n_shrink=2.0), False, cfg),
        "small-N: 1/4-1/2-1/4 smoothing of N": (base, True, cfg),
        **{name: (base, False, cfg.with_overrides({"planner.multipliers": m})) for name, m in multiplier_sets.items()},
    }
    base_cells, base_plans, rows, gammas = None, None, [], []
    for name, (scenario, smooth_n, cfg_variant) in settings.items():
        result = ensemble(scenario, smooth_n)
        table = CrowdingTable.load(result.cells, result.levels)
        plans = _plans(planner.rebind(table, {k: {"central": v["central"]} for k, v in result.cuts.items()}, cfg_variant), queries)
        wk = result.cells[(result.cells["day_type"] == "weekday") & (result.cells["tier"] != "No estimate")]
        weight = (wk["pi_central"] * wk["Z"]).to_numpy()
        row = {"setting": name, "robust share (exposure-weighted)": float(weight[wk["robust_in_range"].to_numpy()].sum() / weight.sum()),
               **_band_rates(plans)}
        if base_cells is None:
            base_cells, base_plans = result.cells, plans
            row.update({"recommendations changed vs base": 0.0, "exposure share whose level changes vs base": 0.0})
        else:
            changed = (plans["shown"] != base_plans["shown"]) | (plans["shown"] & (plans["calmer_routes"] != base_plans["calmer_routes"]))
            row.update({"recommendations changed vs base": float(changed.mean()),
                        "exposure share whose level changes vs base": _level_change_share(base_cells, result.cells)})
        rows.append(row)
        if name.startswith("base") or "sigma 0.9" in name:
            gammas.append(plans.assign(setting=name))
    g = pd.concat(gammas)
    g = g[g["gamma_star"].notna()]
    gamma_tbl = pd.DataFrame([{
        "setting": name, "queries with Gamma*": len(sub), "median": float(sub["gamma_star"].median()),
        "p90": float(sub["gamma_star"].quantile(0.9)),
        **{f"share >= {thr}x ({label})": float((sub["gamma_star"] >= thr).mean()) for label, thr in ROUTE_SWITCH_THRESHOLDS.items()},
    } for name, sub in g.groupby("setting")])
    return {"sensitivity": pd.DataFrame(rows), "gamma_star": gamma_tbl}
