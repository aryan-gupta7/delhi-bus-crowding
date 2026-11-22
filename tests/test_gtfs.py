"""S1 on the mini world."""

import numpy as np

from crowd import gtfs
from tests import mini


def test_patterns_offsets_segments_and_stretches(tmp_path, real_config):
    cfg = mini.build(tmp_path, real_config)
    g = gtfs.load_gtfs(cfg.path("gtfs"))
    patterns, trip_stops, info = gtfs.build_patterns(g, cfg)
    segments, stretches = gtfs.build_segments(patterns, cfg)
    geo = gtfs.Geometry.build(patterns, segments)

    r1 = geo.route_index["R1UP"]
    assert geo.n_stops[r1] == 8
    assert list(geo.off_min[geo.stops_of(r1)]) == [0, 3, 6, 9, 12, 15, 18, 21]
    assert (np.diff(geo.off_min[geo.stops_of(r1)]) >= 0).all()
    assert (geo.tau_min[geo.segs_of(r1)] == 3).all()
    assert info.set_index("route").loc["R3UP", "has_loop"]
    assert info["n_unmapped"].sum() == 0
    # ~1.1 km segments exceed the 800 m minimum, so each segment is its own stretch
    assert (stretches[stretches["route"] == "R1UP"]["seg_to"] == stretches[stretches["route"] == "R1UP"]["seg_from"]).all()
    assert geo.stretch_starts.size == int(stretches.shape[0])


def test_short_trip_maps_as_subsequence_and_does_not_change_offsets(tmp_path, real_config):
    cfg = mini.build(tmp_path, real_config)
    # add a SHORT trip on R1UP that starts at stop index 4 (D->E->F...)
    gdir = cfg.path("gtfs")
    import pandas as pd
    trips = pd.read_csv(gdir / "trips.txt")
    times = pd.read_csv(gdir / "stop_times.txt")
    trips.loc[len(trips)] = [0, 1, "R1UP_SHORT"]
    short = [{"trip_id": "R1UP_SHORT", "arrival_time": f"07:{10 + 5 * i}:00", "departure_time": f"07:{10 + 5 * i}:00",
              "stop_id": sid, "stop_sequence": i, "fare_stage": 0, "stop_dist": ""} for i, sid in enumerate([4, 5, 6, 7])]
    pd.concat([times, pd.DataFrame(short)]).to_csv(gdir / "stop_times.txt", index=False)
    trips.to_csv(gdir / "trips.txt", index=False)

    patterns, trip_stops, info = gtfs.build_patterns(gtfs.load_gtfs(gdir), cfg)
    short_rows = trip_stops[trip_stops["trip_id"] == "R1UP_SHORT"]
    assert list(short_rows["stop_idx"]) == [4, 5, 6, 7]
    offs = patterns[patterns["route"] == "R1UP"]["off_min"].tolist()
    assert offs == [0, 3, 6, 9, 12, 15, 18, 21]


def test_after_midnight_times_are_minutes_beyond_1440():
    import pandas as pd
    assert list(gtfs._to_minutes(pd.Series(["25:10:00", "06:05:30"]))) == [1510, 365]
