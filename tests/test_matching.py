"""S2: cascade steps and the loop-aware pair constraint."""

import numpy as np
import pandas as pd

from crowd import gtfs, matching
from tests import mini


def _world(tmp_path, real_config):
    cfg = mini.build(tmp_path, real_config)
    g = gtfs.load_gtfs(cfg.path("gtfs"))
    patterns, _, _ = gtfs.build_patterns(g, cfg)
    segments, _ = gtfs.build_segments(patterns, cfg)
    return cfg, g, gtfs.Geometry.build(patterns, segments)


def test_cascade_methods(tmp_path, real_config):
    cfg, g, geo = _world(tmp_path, real_config)
    pairs = pd.DataFrame({
        "route": ["R1UP"] * 5,
        "name": ["Stop C", "STOP  c", "Nowhere / Stop D", "Stop Ee", "Totally Unknown"],
        "pax": [1] * 5})
    m = matching.match_names(pairs, geo, g.stops, cfg).set_index("name")
    assert (m.loc["Stop C", "idx"], m.loc["Stop C", "method"]) == (2, "exact")
    assert (m.loc["STOP  c", "idx"], m.loc["STOP  c", "method"]) == (2, "exact")
    assert (m.loc["Nowhere / Stop D", "idx"], m.loc["Nowhere / Stop D", "method"]) == (3, "split")
    assert (m.loc["Stop Ee", "idx"], m.loc["Stop Ee", "method"]) == (4, "fuzzy")
    assert m.loc["Totally Unknown", "method"] == "none"


def test_loop_route_end_resolves_after_start(tmp_path, real_config):
    cfg, g, geo = _world(tmp_path, real_config)           # R3UP stops: A B C B D -> indices 0 1 2 3 4
    tickets = pd.DataFrame({"tid": [0], "route": ["R3UP"], "start_name": ["Stop B"], "end_name": ["Stop D"],
                            "pax": [1]})
    pairs = pd.DataFrame({"route": ["R3UP", "R3UP"], "name": ["Stop B", "Stop D"], "pax": [1, 1]})
    res = matching.resolve_tickets(tickets, matching.match_names(pairs, geo, g.stops, cfg), geo)
    assert (res["a"][0], res["b"][0], bool(res["ok_pair"][0])) == (1, 4, True)


def test_end_name_on_a_repeated_stop_moves_past_the_start(tmp_path, real_config):
    cfg, g, geo = _world(tmp_path, real_config)
    tickets = pd.DataFrame({"tid": [0], "route": ["R3UP"], "start_name": ["Stop C"], "end_name": ["Stop B"],
                            "pax": [1]})
    pairs = pd.DataFrame({"route": ["R3UP", "R3UP"], "name": ["Stop C", "Stop B"], "pax": [1, 1]})
    res = matching.resolve_tickets(tickets, matching.match_names(pairs, geo, g.stops, cfg), geo)
    assert (res["a"][0], res["b"][0]) == (2, 3)          # B's first occurrence (1) is before C; use the later one
