"""Planner: candidate search against brute force, the robust-advantage rule and Gamma*."""

from types import SimpleNamespace

import numpy as np
import pytest

from crowd import stages
from crowd.outputs import CrowdingTable
from crowd.planner.candidates import Leg, Option
from crowd.planner.cards import pick_cards
from crowd.planner.scoring import LegScore, ScoredOption, Scorer, StretchRef
from crowd.planner.service import Planner


@pytest.fixture(scope="module")
def planner(mini_ctx) -> Planner:
    st = mini_ctx.store
    table = CrowdingTable.load(st.read_table("crowding_cells.parquet"), st.read_array("levels.npy"))
    cuts = st.read_json("cuts.json")["cuts"]
    return Planner(stages.geometry(mini_ctx), table, st.read_table("trip_stops.parquet"),
                   st.read_table("gtfs_stops.parquet"), cuts, mini_ctx.cfg)


def test_direct_ride_arrives_at_the_scheduled_time(planner):
    out = planner.plan("0", "3", "08:00")                 # Stop A -> Stop D, buses leave A at 08:00, 08:20, ...
    fastest = out["cards"]["fastest"]
    assert (fastest["depart"], fastest["arrive"], fastest["transfers"]) == ("08:00", "08:09", 0)
    assert fastest["legs"][0]["route"] == "R1UP"


def test_one_transfer_matches_exhaustive_search(planner):
    """Earliest one-transfer arrival A -> F equals brute force over every pair of trips."""
    t0, min_transfer = 8 * 60, planner.generator.min_transfer
    geo, tables = planner.geo, planner.tables
    best = np.inf
    for r1 in range(geo.n_routes):
        ids1 = list(geo.stop_id[geo.stops_of(r1)])
        if "0" not in ids1:
            continue
        i1 = ids1.index("0")
        for row1 in tables.dep[r1]:
            if row1[i1] < t0:
                continue
            for k in range(i1 + 1, len(ids1)):
                for r2 in range(geo.n_routes):
                    if r2 == r1:
                        continue
                    ids2 = list(geo.stop_id[geo.stops_of(r2)])
                    if ids1[k] not in ids2 or "5" not in ids2:
                        continue
                    i2, j2 = ids2.index(ids1[k]), ids2.index("5")
                    if j2 <= i2:
                        continue
                    for row2 in tables.dep[r2]:
                        if row2[i2] >= row1[k] + min_transfer:
                            best = min(best, row2[j2])
    transfers = [o for o in planner.options("0", "5", "08:00") if o.transfers == 1]
    assert transfers and min(o.arrive_min for o in transfers) == best


def test_no_service_late_at_night(planner):
    assert planner.plan("0", "3", "23:30")["cards"] == {}


def _option(minutes: float, route: str) -> Option:
    return Option([Leg(route, 0, 0, 1, 0.0, minutes)], 0.0, minutes, 0.0)


def _scored(minutes, t_adj, route, draws):
    return ScoredOption(option=_option(minutes, route), legs=[], t_adj=t_adj, t_adj_draws=np.asarray(draws, float),
                        routes=frozenset([route]))


def test_comfortable_card_needs_a_robust_advantage(mini_ctx):
    cfg = mini_ctx.cfg                                    # margin = max(5, 10% of 69) = 6.9, robust share 0.8
    scorer = SimpleNamespace(breakdown_ratio=lambda *a: 2.0)
    fast = _scored(30, 69.0, "F", np.full(10, 69.0))
    robust = _scored(40, 40.0, "C", np.full(10, 40.0))
    fragile = _scored(40, 40.0, "C", [40.0] * 7 + [75.0] * 3)          # advantage fails in 3 of 10 draws
    small = _scored(40, 66.0, "C", np.full(10, 66.0))                  # advantage 3 min < margin
    assert pick_cards([fast, robust], scorer, "weekday", cfg)["calmer"] is robust
    assert pick_cards([fast, fragile], scorer, "weekday", cfg)["calmer"] is None
    assert pick_cards([fast, small], scorer, "weekday", cfg)["calmer"] is None
    far = _scored(80, 40.0, "C", np.full(10, 40.0))                    # arrives too much later
    assert pick_cards([fast, far], scorer, "weekday", cfg)["calmer"] is None


def test_breakdown_ratio_is_known_analytically(mini_ctx):
    """Fastest: 30 min at level 3 (T_adj 69). Calmer: 40 min at pressure 0.5, cuts (1.0, 1.5).
    Scaling the calmer route's pressure crosses level 2 at gamma = 2 (advantage 9) and level 3 at
    gamma = 3 (advantage -23); the margin is 6.9, so Gamma* = 3."""
    cfg = mini_ctx.cfg
    scorer = Scorer(None, None, {"weekday": {"central": [1.0, 1.5]}}, cfg)

    def scored(route, minutes, level, pi, t_adj):
        stretch = StretchRef(route, 0, 8, float(minutes), 0, level, pi)
        leg = LegScore(route, "a", "b", float(minutes), [stretch], level=level)
        return ScoredOption(option=_option(minutes, route), legs=[leg], t_adj=t_adj,
                            t_adj_draws=np.full(3, t_adj), routes=frozenset([route]))

    fast, calm = scored("F", 30, 3, 2.0, 69.0), scored("C", 40, 1, 0.5, 40.0)
    assert scorer.breakdown_ratio(fast, calm, "weekday", margin=6.9) == pytest.approx(3.0, abs=0.01)
    shared = scored("F", 40, 1, 0.5, 40.0)               # same route in both options: nothing to scale
    assert scorer.breakdown_ratio(fast, shared, "weekday", margin=6.9) is None
