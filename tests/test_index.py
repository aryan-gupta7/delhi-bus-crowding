"""S6: percentiles, level assignment and the stretch aggregation."""

from types import SimpleNamespace

import numpy as np

from crowd.index import hour_profile_z, levels_from_cuts, stretch_pi, weighted_percentile


def test_weighted_percentile_follows_the_exposure():
    values = np.array([1.0, 2.0, 3.0, 4.0])
    heavy_top = weighted_percentile(values, np.array([1.0, 1.0, 1.0, 10.0]), 50)
    equal = weighted_percentile(values, np.ones(4), 50)
    assert heavy_top > equal and np.isclose(equal, 2.5)
    assert weighted_percentile(values, np.array([0.0, 1.0, 1.0, 0.0]), 50) == 2.5     # zero weights ignored


def test_levels_are_monotone_in_pressure():
    pi = np.array([0.1, 0.5, 0.9, 5.0])
    lv = levels_from_cuts(pi, np.ones(4, bool), np.array([0.4, 1.0]))
    assert list(lv) == [1, 2, 2, 3]
    assert list(levels_from_cuts(pi, np.array([True, True, False, True]), np.array([0.4, 1.0]))) == [1, 2, 0, 3]


def test_stretch_pressure_is_invariant_to_splitting_a_segment():
    # one 2-minute segment vs the same segment split into two 1-minute halves
    whole = SimpleNamespace(tau_min=np.array([2.0, 3.0]), stretch_starts=np.array([0]))
    split = SimpleNamespace(tau_min=np.array([1.0, 1.0, 3.0]), stretch_starts=np.array([0]))
    q1, z1 = np.array([[10.0], [4.0]]), np.array([[2.0], [2.0]])
    q2, z2 = np.array([[10.0], [10.0], [4.0]]), np.array([[2.0], [2.0], [2.0]])
    assert np.allclose(stretch_pi(q1, z1, whole)[0], stretch_pi(q2, z2, split)[0])


def test_hour_profile_z_divides_each_hour_by_its_own_eligible_days():
    import pandas as pd
    days = pd.date_range("2026-10-05", periods=4)
    rows = [(d, h, 10 if h == 9 else 2) for d in days for h in range(24) if not (h == 9 and d == days[0])]   # 09h masked on day 0
    counts = pd.DataFrame(rows, columns=["date", "hour", "n_tickets"]).assign(day_type="weekday")
    z = hour_profile_z(counts, "weekday")
    # every day that is eligible at 09h carries 10 tickets, so 09h share is 10 per day, not 30/4
    share = np.where(np.arange(24) == 9, 10.0, 2.0)
    expected = (share / share.sum() - 1 / 24) / (share / share.sum()).std()
    assert np.allclose(z, expected)


def test_hour_profile_z_is_standardised():
    import pandas as pd
    counts = pd.DataFrame({"day_type": "weekday", "date": pd.Timestamp("2026-10-05"),
                           "hour": np.arange(24), "n_tickets": np.arange(24) + 1})
    z = hour_profile_z(counts, "weekday")
    assert abs(z.mean()) < 1e-12 and abs(z.std() - 1) < 1e-12
