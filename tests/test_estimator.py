"""S5: statistical building blocks and the passage-hour operator."""

import numpy as np

from crowd import estimator
from crowd.estimator import fit_alpha, fit_dirichlet_strength, fit_phi, nb_loglik


def test_fit_alpha_recovers_the_gamma_precision():
    rng = np.random.default_rng(0)
    true_alpha, n_days, n_cells = 2.0, 12, 4000
    mu = rng.uniform(0.5, 6.0, n_cells)
    rate = rng.gamma(true_alpha * mu, 1.0 / true_alpha)
    totals = rng.poisson(rate * n_days).astype(float)
    assert abs(fit_alpha(mu, totals, np.full(n_cells, n_days)) - true_alpha) < 0.3


def test_fit_phi_recovers_day_dispersion():
    rng = np.random.default_rng(1)
    true_phi, n_cells, n_days = 5.0, 3000, 8
    lam = rng.uniform(1.0, 20.0, n_cells)
    delta = rng.gamma(true_phi, 1.0 / true_phi, (n_cells, n_days))
    y = rng.poisson(lam[:, None] * delta).astype(float)
    assert abs(fit_phi(y, lam) - true_phi) < 0.6


def test_nb_loglik_tends_to_poisson_for_large_size():
    y, m = np.array([0.0, 3.0, 7.0]), np.array([2.0, 2.0, 2.0])
    poisson = y * np.log(m) - m                      # log y! dropped in both
    assert np.allclose(nb_loglik(y, m, 1e8), poisson, atol=1e-4)


def test_dirichlet_strength_is_large_when_groups_follow_the_prior():
    rng = np.random.default_rng(2)
    prior = np.triu(np.ones((6, 6)), 1)
    prior /= prior.sum()
    counts_close = [rng.multinomial(200, prior.ravel()).reshape(1, 6, 6).astype(float) for _ in range(30)]
    skewed = np.zeros((6, 6))
    skewed[0, 1] = 1.0
    counts_far = [rng.multinomial(200, skewed.ravel()).reshape(1, 6, 6).astype(float) for _ in range(30)]
    p = [prior[None]] * 30
    assert fit_dirichlet_strength(counts_close, p) > 10 * fit_dirichlet_strength(counts_far, p)


def test_passage_operator_conserves_probability_and_shifts_by_schedule():
    off = np.array([0, 3, 6, 9, 12, 15, 18, 21], float)
    n = len(off)
    profile = np.zeros((n, n))
    profile[0, 7] = 1.0                                  # everybody rides A -> H
    op = np.zeros((24, n - 1, 24))
    estimator._operator_from_profile(profile, off, [8, 23], n - 1, op)
    assert np.allclose(op[8].sum(axis=1), 1.0)           # every crossed segment is passed at some hour
    # boarding at hour 8, segment 6 is crossed 18 min later: all inside hour 8
    assert np.isclose(op[8, 6, 8], 1 - 0.3) and np.isclose(op[8, 6, 9], 0.3)
    # hour 23 wraps to hour 0
    assert np.isclose(op[23, 6, 0], 0.3) and np.isclose(op[23, 6, 23], 0.7)


def test_length_profile_is_a_distribution_over_forward_pairs():
    grid = np.full((10, 10), 0.01)
    p = estimator._length_grid_profile(12, grid)
    assert np.isclose(p.sum(), 1.0) and np.allclose(np.tril(p), 0.0)


def test_estimator_conserves_passenger_segments(mini_ctx):
    """Sum of Q-hat over segments and hours = sum over boarding hours of lam_eff * E[ride segments | profile]."""
    from crowd import stages
    est = stages.estimator(mini_ctx)
    lam = est.lam_eff_mean("weekday")
    for pos in range(len(est.routes)):
        n = est.profiles[pos].shape[1]
        ride_len = np.array([(p * (np.arange(n)[None, :] - np.arange(n)[:, None])).sum() for p in est.profiles[pos]])
        expected = float((lam[pos] * ride_len).sum())
        got = float(est.qhat_route(pos, lam[pos]).sum())
        assert np.isclose(got, expected, rtol=1e-4)


def test_leakage_guard_training_fit_ignores_everything_outside_train_dates(mini_ctx):
    """Perturb every count and OD row outside the training dates: the fit must not change at all."""
    from crowd import stages
    from crowd.estimator import fit_estimator
    from crowd.validation.splits import weekday_split
    st, geo = mini_ctx.store, stages.geometry(mini_ctx)
    counts, od = st.read_table("counts.parquet"), st.read_table("od_pairs.parquet")
    dh, info = st.read_table("day_hour_ok.parquet"), st.read_table("route_info.parquet")
    train, _ = weekday_split(dh, mini_ctx.cfg)
    service = stages.service(mini_ctx)
    base = fit_estimator(counts, od, geo, info, mini_ctx.cfg, service, train_dates=train)
    c2, o2 = counts.copy(), od.copy()
    outside_c, outside_o = ~c2["date"].isin(train), ~o2["date"].isin(train)
    c2.loc[outside_c, ["n_tickets", "pax"]] *= 7
    o2.loc[outside_o, ["n_tickets", "pax"]] *= 7
    other = fit_estimator(c2, o2, geo, info, mini_ctx.cfg, service, train_dates=train)
    assert base.alpha == other.alpha and base.profile_strength == other.profile_strength
    for dt in ("weekday", "weekend"):
        assert np.array_equal(base.shape[dt], other.shape[dt]) and np.array_equal(base.tier[dt], other.tier[dt])
        assert np.array_equal(base.phi[dt], other.phi[dt]) and np.array_equal(base.qhat(dt), other.qhat(dt))
