"""A tiny, fully known world for tests: three routes, ten days of hand-made tickets.

R1UP  stops A..H (8 stops, one every ~1.1 km)   tickets A->D, C->H, E->H in the peak hours
R2UP  stops C..F (short route sharing stops)    a few C->F tickets
R3UP  loop A B C B D                            tickets B->D that must resolve to indices 1 -> 4
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from crowd.config import Config

STOPS = {i: (f"Stop {chr(65 + i)}", 28.60 + 0.01 * i, 77.20) for i in range(8)}      # ids 0..7
ROUTES = {"R1UP": [0, 1, 2, 3, 4, 5, 6, 7], "R2UP": [2, 3, 4, 5], "R3UP": [0, 1, 2, 1, 3]}
WEEKDAYS = ["2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08",
            "2026-10-09", "2026-10-12", "2026-10-13", "2026-10-14"]
WEEKEND = ["2026-10-03", "2026-10-04", "2026-10-10", "2026-10-11"]


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}:00"


def write_gtfs(root: Path) -> Path:
    """Routes run every 20 minutes from 06:00 to 21:40; stops are 3 minutes apart."""
    g = root / "gtfs"
    g.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"route_id": list(range(len(ROUTES))), "route_short_name": list(ROUTES)}).to_csv(g / "routes.txt", index=False)
    pd.DataFrame([{"stop_id": sid, "stop_name": n, "stop_lat": la, "stop_lon": lo} for sid, (n, la, lo) in STOPS.items()]
                 ).to_csv(g / "stops.txt", index=False)
    trips, times = [], []
    for ri, (name, stops) in enumerate(ROUTES.items()):
        for start in range(6 * 60, 22 * 60, 20):
            tid = f"{name}_{start}"
            trips.append({"route_id": ri, "service_id": 1, "trip_id": tid})
            for seq, sid in enumerate(stops):
                t = _hhmm(start + 3 * seq)
                times.append({"trip_id": tid, "arrival_time": t, "departure_time": t, "stop_id": sid,
                              "stop_sequence": seq, "fare_stage": 0, "stop_dist": ""})
    pd.DataFrame(trips).to_csv(g / "trips.txt", index=False)
    pd.DataFrame(times).to_csv(g / "stop_times.txt", index=False)
    return g


def write_tickets(root: Path) -> Path:
    """Weekday peak tickets (hours 8 and 9) with a known pinch point; fewer at weekends."""
    rows = []
    rng = np.random.default_rng(1)

    def add(day, route, a, b, hour, n, vehicle):
        for k in range(n):
            minute, second = int(rng.integers(0, 60)), int(rng.integers(0, 60))
            rows.append({"passenger_count": 1, "amount": "9", "vehicle_number": vehicle if k % 2 else "NULL",
                         "ticket_type_id": 1, "end_stop_name": STOPS[b][0], "route": route,
                         "start_stop_name": STOPS[a][0], "created_at": f"{day} {hour:02d}:{minute:02d}:{second:02d}.000000+05:30",
                         "is_ac": True})

    for day in WEEKDAYS:
        for hour in (8, 9):
            add(day, "R1UP", 0, 3, hour, 6, "DL1PD0001")
            add(day, "R1UP", 2, 7, hour, 6, "DL1PD0001")
            add(day, "R1UP", 4, 7, hour, 2, "DL1PD0001")
            add(day, "R2UP", 2, 5, hour, 3, "DL1PD0002")
            add(day, "R3UP", 1, 3, hour, 3, "DL1PD0003")
        for hour in (13, 18):
            add(day, "R1UP", 0, 7, hour, 2, "DL1PD0001")
            add(day, "R2UP", 2, 5, hour, 1, "DL1PD0002")
    for day in WEEKEND:
        for hour in (10, 11):
            add(day, "R1UP", 0, 7, hour, 3, "DL1PD0001")
            add(day, "R2UP", 2, 5, hour, 1, "DL1PD0002")
    cols = ["passenger_count", "amount", "vehicle_number", "ticket_type_id", "end_stop_name", "route",
            "start_stop_name", "created_at", "is_ac"]
    path = root / "tickets.csv"
    pd.DataFrame(rows)[cols].to_csv(path, index=False)
    return path


def mini_config(root: Path, base: Config) -> Config:
    """The real config with paths pointing at the mini world and loosened data-size thresholds."""
    data = yaml.safe_load(yaml.safe_dump(base.to_dict()))
    data["paths"] = {"tickets": "tickets.csv", "gtfs": "gtfs", "out": "out"}
    data["ensemble"]["k"] = 9
    data["eligibility"]["min_median"] = 1
    data["validation"]["train_days"] = 6
    data["estimator"]["strength_classes"] = 2
    return Config(data, root)


def build(root: Path, base: Config) -> Config:
    write_gtfs(root)
    write_tickets(root)
    return mini_config(root, base)
