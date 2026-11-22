"""Planner: candidate search against brute force, the robust-advantage rule and Gamma*."""

from types import SimpleNamespace

import numpy as np
import pytest

from crowd import stages
from crowd.outputs import CrowdingTable
from crowd.planner.candidates import Leg, Option
from crowd.planner.cards import pick_cards
from crowd.planner.scoring import GammaStar, LegScore, ScoredOption, Scorer, StretchRef
from crowd.planner.service import Planner, data_period


@pytest.fixture(scope="module")
def planner(mini_ctx) -> Planner:
    st = mini_ctx.store
    table = CrowdingTable.load(st.read_table("crowding_cells.parquet"), st.read_array("levels.npy"))
    cuts = st.read_json("cuts.json")["cuts"]
    return Planner.build(stages.geometry(mini_ctx), table, st.read_table("trip_stops.parquet"),
                         st.read_table("gtfs_stops.parquet"), cuts, mini_ctx.cfg, data_period(st.read_table("day_hour_ok.parquet", ["date"])))


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


def _scored(minutes, t_adj, route, draws, t_adj_lo=None, draws_lo=None):
    """A ScoredOption with no stretches; ``*_lo`` default to the hi values (no unknown stretches)."""
    draws = np.asarray(draws, float)
    return ScoredOption(option=_option(minutes, route), legs=[], t_adj=t_adj, t_adj_draws=draws,
                        t_adj_lo=t_adj if t_adj_lo is None else t_adj_lo,
                        t_adj_draws_lo=draws if draws_lo is None else np.asarray(draws_lo, float),
                        routes=frozenset([route]))


def test_comfortable_card_needs_a_robust_advantage(mini_ctx):
    cfg = mini_ctx.cfg                                    # margin = max(5, 10% of 69) = 6.9, robust share 0.8
    scorer = SimpleNamespace(breakdown_ratio=lambda *a: GammaStar(2.0, "finite"))
    fast = _scored(30, 69.0, "F", np.full(10, 69.0))
    robust = _scored(40, 40.0, "C", np.full(10, 40.0))
    fragile = _scored(40, 40.0, "C", [40.0] * 7 + [75.0] * 3)          # advantage fails in 3 of 10 draws
    small = _scored(40, 66.0, "C", np.full(10, 66.0))                  # advantage 3 min < margin
    assert pick_cards([fast, robust], scorer, "weekday", cfg)["calmer"] is robust
    assert pick_cards([fast, fragile], scorer, "weekday", cfg)["calmer"] is None
    assert pick_cards([fast, small], scorer, "weekday", cfg)["calmer"] is None
    far = _scored(80, 40.0, "C", np.full(10, 40.0))                    # arrives too much later
    assert pick_cards([fast, far], scorer, "weekday", cfg)["calmer"] is None


def test_an_advantage_that_exists_only_because_the_fastest_lacks_data_is_not_shown(mini_ctx):
    """The fastest option's unknown stretches score 69 at m3 but only 40 at m1: the calmer option (45)
    wins when unknowns are pessimistic and loses when they are comfortable, so no card is shown."""
    scorer = SimpleNamespace(breakdown_ratio=lambda *a: GammaStar(None, "not_applicable"))
    fast = _scored(30, 69.0, "F", np.full(10, 69.0), t_adj_lo=40.0, draws_lo=np.full(10, 40.0))
    calm = _scored(40, 45.0, "C", np.full(10, 45.0))
    picked = pick_cards([fast, calm], scorer, "weekday", mini_ctx.cfg)
    assert picked["calmer"] is None and picked["advantage"] == pytest.approx(24.0) and picked["advantage_worst"] == pytest.approx(-5.0)


def _stretch(route, level, pi, row, minutes=30.0):
    return StretchRef(route, 0, 8, minutes, row, level, pi)


def _with_stretches(route, minutes, stretches, t_adj, t_adj_lo):
    leg = LegScore(route, "a", "b", float(minutes), stretches, level=max((s.level for s in stretches), default=0))
    return ScoredOption(option=_option(minutes, route), legs=[leg], t_adj=t_adj, t_adj_draws=np.full(3, t_adj),
                        t_adj_lo=t_adj_lo, t_adj_draws_lo=np.full(3, t_adj_lo), routes=frozenset([route]))


def test_breakdown_ratio_is_known_analytically(mini_ctx):
    """Fastest: 30 min at level 3 (T_adj 69). Calmer: 40 min at pressure 0.5, cuts (1.0, 1.5).
    Scaling the calmer route's pressure crosses level 2 at gamma = 2 (advantage 9) and level 3 at
    gamma = 3 (advantage -23); the margin is 6.9, so Gamma* = 3."""
    scorer = Scorer(None, None, {"weekday": {"central": [1.0, 1.5]}}, mini_ctx.cfg)
    fast = _with_stretches("F", 30, [_stretch("F", 3, 2.0, 0)], 69.0, 69.0)
    calm = _with_stretches("C", 40, [_stretch("C", 1, 0.5, 1, 40.0)], 40.0, 40.0)
    g = scorer.breakdown_ratio(fast, calm, "weekday", margin=6.9)
    assert g.status == "finite" and g.value == pytest.approx(3.0, abs=0.01)


def test_breakdown_ratio_scales_the_fastest_when_the_calmer_option_adds_no_route(mini_ctx):
    """Calmer uses a subset of the fastest's routes: the advantage comes from the fastest's own crowded route."""
    scorer = Scorer(None, None, {"weekday": {"central": [1.0, 1.5]}}, mini_ctx.cfg)
    fast = _with_stretches("F", 30, [_stretch("F", 3, 2.0, 0)], 69.0, 69.0)
    calm = ScoredOption(option=_option(40, "C"), legs=[LegScore("C", "a", "b", 40.0, [_stretch("X", 1, 0.5, 1, 40.0)], level=1)],
                        t_adj=40.0, t_adj_draws=np.full(3, 40.0), t_adj_lo=40.0, t_adj_draws_lo=np.full(3, 40.0),
                        routes=frozenset(["X"]))
    fast.routes = frozenset(["F", "X"])                  # the calmer option's only route is also in the fastest
    g = scorer.breakdown_ratio(fast, calm, "weekday", margin=6.9)
    assert g.status == "finite" and g.value > 1.0        # F's pressure / gamma eventually drops it to level 1: advantage vanishes
    same = _with_stretches("F", 40, [_stretch("F", 1, 0.5, 1, 40.0)], 40.0, 40.0)
    same.routes = fast.routes                              # identical route sets: nothing to scale
    assert scorer.breakdown_ratio(fast, same, "weekday", margin=6.9).status == "not_applicable"


def test_unknown_stretches_are_scored_at_both_extremes(planner):
    """A cell without an estimate scores m3 in t_adj and m1 in t_adj_lo, in the central and every draw."""
    options = planner.options("0", "3", "06:10")          # R1UP runs at 06:10 but no ticket was sold: all stretches unknown
    scored = planner.scorer.score(options[0], "weekday")
    assert scored.partly_estimated and scored.level == 0
    in_vehicle = options[0].legs[0].alight_min - options[0].legs[0].board_min
    m = planner.scorer.m
    assert scored.t_adj == pytest.approx(options[0].total_min + in_vehicle * (m[2] - 1))
    assert scored.t_adj_lo == pytest.approx(options[0].total_min + in_vehicle * (m[0] - 1))
    assert np.allclose(scored.t_adj_draws, scored.t_adj) and np.allclose(scored.t_adj_draws_lo, scored.t_adj_lo)


def test_the_leg_level_is_the_highest_level_with_a_quarter_of_the_minutes(planner):
    scorer = planner.scorer
    assert scorer._dominant_level([(3, 20.0), (1, 80.0)]) == 1          # 20% of the minutes: ignored
    assert scorer._dominant_level([(3, 30.0), (1, 70.0)]) == 3          # 30%: counts
    assert scorer._dominant_level([(0, 100.0)]) == 0


def test_a_00_30_query_finds_a_trip_scheduled_after_midnight(planner):
    tables = planner.tables
    r = planner.geo.route_index["R1UP"]
    last = tables.dep[r][-1]
    tables.dep[r] = np.vstack([tables.dep[r], last - last[0] + (25 * 60 + 10)])                  # a 25:10 trip appended
    times = tables.next_departure(r, 0, 30.0)
    assert times is not None and times[0] == pytest.approx(70.0)                                # 01:10 on the query's clock
    tables.dep[r] = tables.dep[r][:-1]
