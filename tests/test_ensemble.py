"""S7: the scenario ensemble and its invariances."""

import numpy as np

from crowd import stages, supply as supply_mod
from crowd.ensemble import Scenario, run_ensemble
from crowd.index import hour_profile_z


def _inputs(ctx):
    st = ctx.store
    geo = stages.geometry(ctx)
    dense = supply_mod.dense_supply(st.read_table("supply.parquet"), geo)
    z = {dt: hour_profile_z(st.read_table("counts.parquet"), dt) for dt in ("weekday", "weekend")}
    return (stages.estimator(ctx), dense, st.read_table("route_seats.parquet"), stages.route_coverage_array(ctx),
            st.read_table("route_info.parquet"), z)


def test_levels_are_aligned_with_cells(mini_ctx):
    cells = mini_ctx.store.read_table("crowding_cells.parquet")
    levels = mini_ctx.store.read_array("levels.npy")
    assert levels.shape == (len(cells), mini_ctx.cfg.ensemble.k)
    assert set(np.unique(levels)) <= {0, 1, 2, 3}
    no_estimate = cells["tier"] == "No estimate"
    assert (cells.loc[no_estimate, "level"] == 0).all() and (levels[no_estimate.to_numpy()] == 0).all()
    assert cells.loc[~no_estimate, "level"].between(1, 3).all()
    assert not cells.loc[no_estimate, "robust_in_range"].any()


def test_levels_row_matches_the_cell_it_belongs_to(mini_ctx):
    """A known cell's per-draw levels equal the levels recomputed from the stored cuts and its own Pi."""
    cells = mini_ctx.store.read_table("crowding_cells.parquet")
    levels = mini_ctx.store.read_array("levels.npy")
    cuts = mini_ctx.store.read_json("cuts.json")["cuts"]["weekday"]["central"]
    i = int(cells[(cells["route"] == "R1UP") & (cells["day_type"] == "weekday") & (cells["hour"] == 8)
                  & (cells["stretch_id"] == 2)].index[0])
    expected = 1 + int(cells.at[i, "pi_central"] > cuts[0]) + int(cells.at[i, "pi_central"] > cuts[1])
    assert cells.at[i, "level"] == expected
    assert (levels[i] == expected).mean() > 0.5               # the draws scatter around the central level


def test_without_route_effect_or_tilt_every_estimable_cell_is_as_robust_as_the_posterior_allows(mini_ctx):
    """sigma = 0 and a single theta leave only posterior noise, so robustness cannot fall below the wide-sigma case."""
    est, dense, seats, cov, info, z = _inputs(mini_ctx)
    scn = Scenario(theta_grid=(mini_ctx.cfg.ensemble.theta_central,), theta_central=mini_ctx.cfg.ensemble.theta_central, sigma_r=0.0)
    quiet = run_ensemble(est, dense, seats, cov, info, z, mini_ctx.cfg, scn)
    loud = run_ensemble(est, dense, seats, cov, info, z, mini_ctx.cfg, Scenario.from_config(mini_ctx.cfg, sigma_r=0.9))
    assert quiet.cells["robust_in_range"].mean() >= loud.cells["robust_in_range"].mean()
    # with the posterior collapsed to its mean (huge shape), draws equal the central level exactly
    collapsed = type(est)(**{**est.__dict__, "shape": {k: v * 1e9 for k, v in est.shape.items()},
                             "rate": {k: v * 1e9 for k, v in est.rate.items()}})
    exact = run_ensemble(collapsed, dense, seats, cov, info, z, mini_ctx.cfg, scn)
    estimable = exact.cells["tier"] != "No estimate"
    assert exact.cells.loc[estimable, "robust_in_range"].all()


def test_a_common_seat_scale_cancels_in_levels(mini_ctx):
    est, dense, seats, cov, info, z = _inputs(mini_ctx)
    base = run_ensemble(est, dense, seats, cov, info, z, mini_ctx.cfg)
    scaled = {dt: {"N": v["N"], "Z": v["Z"] * 2.7} for dt, v in dense.items()}
    other = run_ensemble(est, scaled, seats, cov, info, z, mini_ctx.cfg)
    assert (base.cells["level"].to_numpy() == other.cells["level"].to_numpy()).all()
    assert (base.levels == other.levels).all()


def test_more_route_effect_spread_never_makes_more_cells_robust(mini_ctx):
    est, dense, seats, cov, info, z = _inputs(mini_ctx)
    narrow = run_ensemble(est, dense, seats, cov, info, z, mini_ctx.cfg, Scenario.from_config(mini_ctx.cfg, sigma_r=0.0))
    wide = run_ensemble(est, dense, seats, cov, info, z, mini_ctx.cfg, Scenario.from_config(mini_ctx.cfg, sigma_r=0.9))
    assert narrow.cells["robust_in_range"].mean() >= wide.cells["robust_in_range"].mean()


def test_posterior_draws_do_not_depend_on_other_routes(mini_ctx):
    est = stages.estimator(mini_ctx)
    first = est.draw_lambda("weekday", 1, 5, seed=7)
    est.draw_lambda("weekday", 0, 5, seed=7)
    est.draw_lambda("weekday", 2, 5, seed=7)
    assert np.array_equal(first, est.draw_lambda("weekday", 1, 5, seed=7))
    assert not np.array_equal(first, est.draw_lambda("weekend", 1, 5, seed=7))


def test_pinch_point_of_the_known_route_is_found(mini_ctx):
    cells = mini_ctx.store.read_table("crowding_cells.parquet")
    peak = cells[(cells["route"] == "R1UP") & (cells["day_type"] == "weekday") & (cells["hour"] == 8)]
    # tickets A->D and C->H overlap on segment C->D (index 2): the pinch point
    assert peak.loc[peak["pi_mean"].idxmax(), "stretch_id"] == 2
