"""S3: segment crossing, passage-hour binning and conservation on the mini world."""

import numpy as np
import pandas as pd

from crowd import flows, gtfs
from tests import mini


def _geo(tmp_path, real_config):
    cfg = mini.build(tmp_path, real_config)
    patterns, _, _ = gtfs.build_patterns(gtfs.load_gtfs(cfg.path("gtfs")), cfg)
    segments, _ = gtfs.build_segments(patterns, cfg)
    return gtfs.Geometry.build(patterns, segments)


def test_ride_crossing_an_hour_boundary_is_split_by_passage_time(tmp_path, real_config):
    geo = _geo(tmp_path, real_config)
    r1 = geo.route_index["R1UP"]
    # boards stop A at 08:50 (minute 530); a segment s is crossed at 530 + 3 s
    gseg, hour, w = flows._explode(np.array([r1]), np.array([0]), np.array([7]), np.array([2.0]),
                                   np.array([530.0]), geo, gamma=1.0)
    assert len(gseg) == 7 and (w == 2.0).all()
    assert list(hour) == [8, 8, 8, 8, 9, 9, 9]            # segment 3 at 08:59, segment 4 at 09:02
    assert list(gseg - geo.seg_ptr[r1]) == list(range(7))


def test_observed_flow_conserves_passenger_segments(mini_ctx):
    from crowd import stages
    geo = stages.geometry(mini_ctx)
    tickets = stages.tickets(mini_ctx)
    resolved = mini_ctx.store.read_table("ticket_stops.parquet")
    dh = mini_ctx.store.read_table("day_hour_ok.parquet")
    pairs = flows.matched_pairs(tickets, resolved)
    sums = flows.observed_flows(pairs, geo, dh, dh["date"].unique(), 1.0)
    eligible = flows.eligible_tickets(pd.DataFrame({
        "route": tickets["route"], "date": tickets["date"], "hour": tickets["hour"], "pax": tickets["pax"],
        "a": resolved["a"], "b": resolved["b"], "ok": resolved["ok_pair"]}), dh)
    eligible = eligible[eligible["ok"]]
    expected = float((eligible["pax"] * (eligible["b"] - eligible["a"])).sum())
    assert sum(s.total.sum() for s in sums.values()) == expected


def test_counts_hold_explicit_zero_days(mini_ctx):
    counts = mini_ctx.store.read_table("counts.parquet")
    night = counts[(counts["route"] == "R1UP") & (counts["hour"] == 3) & (counts["day_type"] == "weekday")]
    assert len(night) == len(mini.WEEKDAYS) and (night["n_tickets"] == 0).all()
