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
    assert set(np.unique(levels)) <= {1, 2, 3}
    assert cells["level"].between(1, 3).all()


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
