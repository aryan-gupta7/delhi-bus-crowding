"""S1: GTFS canonicalisation - patterns, scheduled offsets, segments, frozen stretches.

A route-direction *is* one ``route_short_name`` (e.g. ``102ADOWN``),
which equals the ticket ``route`` string. Each route's canonical pattern is the stop sequence of
its longest trip; every other trip is mapped onto it as a stop-id subsequence. Stretches are
GTFS-only (they never depend on tickets) and are frozen so that reruns reuse the same keys.
"""

from __future__ import annotations

import bisect
import re
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from crowd.config import Config

EARTH_RADIUS_M = 6_371_000.0
_DIRECTION = re.compile(r"(UP|DOWN)$")


@dataclass
class Gtfs:
    routes: pd.DataFrame       # route_id, route
    trips: pd.DataFrame        # trip_id, route
    stops: pd.DataFrame        # stop_id, stop_name, lat, lon
    stop_times: pd.DataFrame   # trip_id, stop_id, arr_min, dep_min (sorted by trip, sequence)


def route_key(name: str) -> int:
    """Stable integer key of a route name (random-stream keys must not depend on route order)."""
    return zlib.crc32(name.encode())


def haversine_m(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Great-circle distance in metres (vectorised)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlmb = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a))


def _to_minutes(col: pd.Series) -> np.ndarray:
    """'HH:MM:SS' (hours may exceed 24) -> integer minutes after midnight."""
    parts = col.str.split(":", expand=True)
    return (parts[0].astype(int) * 60 + parts[1].astype(int)).to_numpy(dtype=np.int16)


def load_gtfs(gtfs_dir: Path) -> Gtfs:
    routes = pd.read_csv(gtfs_dir / "routes.txt", dtype=str, usecols=["route_id", "route_short_name"])
    routes = routes.rename(columns={"route_short_name": "route"})
    trips = pd.read_csv(gtfs_dir / "trips.txt", dtype=str, usecols=["route_id", "trip_id"])
    trips = trips.merge(routes, on="route_id", how="inner")[["trip_id", "route"]]
    stops = pd.read_csv(gtfs_dir / "stops.txt", usecols=["stop_id", "stop_name", "stop_lat", "stop_lon"],
                        dtype={"stop_id": str})
    stops = stops.rename(columns={"stop_lat": "lat", "stop_lon": "lon"})
    st = pd.read_csv(gtfs_dir / "stop_times.txt", dtype=str,
                     usecols=["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"])
    st["stop_sequence"] = st["stop_sequence"].astype(int)
    out = pd.DataFrame({
        "trip_id": st["trip_id"], "stop_id": st["stop_id"],
        "arr_min": _to_minutes(st["arrival_time"]), "dep_min": _to_minutes(st["departure_time"]),
        "seq": st["stop_sequence"].to_numpy(),
    })
    out = out.sort_values(["trip_id", "seq"], kind="stable").drop(columns="seq").reset_index(drop=True)
    out = out[out["trip_id"].isin(trips["trip_id"])].reset_index(drop=True)
    return Gtfs(routes=routes, trips=trips, stops=stops, stop_times=out)


def _canonical_trips(trips: pd.DataFrame, stop_times: pd.DataFrame) -> pd.DataFrame:
    """Longest trip per route (ties -> smallest trip_id, for determinism)."""
    n = stop_times.groupby("trip_id", sort=False).size().rename("n_stops").reset_index()
    t = trips.merge(n, on="trip_id", how="inner")
    t = t.sort_values(["route", "n_stops", "trip_id"], ascending=[True, False, True], kind="stable")
    return t.drop_duplicates("route", keep="first").reset_index(drop=True)


def _map_to_canonical(canon_ids: dict[str, list[str]], trips_st: pd.DataFrame, trip_route: dict[str, str]):
    """Greedy leftmost subsequence mapping of every trip's stops onto its route's canonical stops.

    Returns arrays aligned to ``trips_st`` rows: canonical stop index (-1 if the trip is unmapped).
    """
    occ: dict[str, dict[str, list[int]]] = {}
    for route, ids in canon_ids.items():
        d: dict[str, list[int]] = {}
        for i, sid in enumerate(ids):
            d.setdefault(sid, []).append(i)
        occ[route] = d

    trip_ids = trips_st["trip_id"].to_numpy()
    stop_ids = trips_st["stop_id"].to_numpy()
    idx = np.full(len(trips_st), -1, dtype=np.int32)
    bounds = np.flatnonzero(np.r_[True, trip_ids[1:] != trip_ids[:-1], True])
    for lo, hi in zip(bounds[:-1], bounds[1:]):
        route = trip_route.get(trip_ids[lo])
        if route is None:
            continue
        table = occ[route]
        ptr, mapped = 0, []
        for sid in stop_ids[lo:hi]:
            lst = table.get(sid)
            if lst is None:
                mapped = None
                break
            k = bisect.bisect_left(lst, ptr)
            if k == len(lst):
                mapped = None
                break
            ptr = lst[k] + 1
            mapped.append(lst[k])
        if mapped is not None:
            idx[lo:hi] = mapped
    return idx


def build_patterns(g: Gtfs, cfg: Config) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Canonical patterns with scheduled offsets, mapped trip stop times, and per-route info."""
    canon = _canonical_trips(g.trips, g.stop_times)
    st_canon = g.stop_times.merge(canon[["trip_id", "route"]], on="trip_id", how="inner")
    st_canon["stop_idx"] = st_canon.groupby("trip_id", sort=False).cumcount().astype(np.int32)

    stop_lookup = g.stops.set_index("stop_id")
    patterns = st_canon[["route", "stop_idx", "stop_id", "arr_min"]].rename(columns={"arr_min": "canon_arr"})
    patterns = patterns.join(stop_lookup[["stop_name", "lat", "lon"]], on="stop_id")
    canon_ids = patterns.groupby("route", sort=False)["stop_id"].apply(list).to_dict()

    # map every trip onto its route's canonical pattern
    trip_route = dict(zip(g.trips["trip_id"], g.trips["route"]))
    mapped_idx = _map_to_canonical(canon_ids, g.stop_times, trip_route)
    ts = g.stop_times.assign(stop_idx=mapped_idx)
    ts["route"] = ts["trip_id"].map(trip_route)
    trip_ok = ts.groupby("trip_id", sort=False)["stop_idx"].min() >= 0
    n_trips = g.trips.groupby("route").size().rename("n_trips")
    n_unmapped = (~trip_ok).groupby(ts.drop_duplicates("trip_id").set_index("trip_id")["route"]).sum().rename("n_unmapped")
    ts = ts[ts["trip_id"].map(trip_ok).to_numpy()].reset_index(drop=True)
    trip_stops = ts[["route", "trip_id", "stop_idx", "arr_min", "dep_min"]]

    patterns["off_min"] = _scheduled_offsets(patterns, trip_stops, cfg)
    patterns = patterns.drop(columns="canon_arr")[
        ["route", "stop_idx", "stop_id", "stop_name", "lat", "lon", "off_min"]].reset_index(drop=True)
    info = _route_info(patterns, n_trips, n_unmapped, cfg)
    return patterns, trip_stops.reset_index(drop=True), info


def _scheduled_offsets(patterns: pd.DataFrame, trip_stops: pd.DataFrame, cfg: Config) -> np.ndarray:
    """Median minutes from the first canonical stop, over mapped trips that contain stop 0.

    SHORT trips that do not contain stop 0 contribute to N but not to offsets. Routes with fewer
    than ``min_offset_trips`` such trips fall back to the canonical (longest) trip's own offsets.
    The result is forced non-decreasing.
    """
    canon_off = patterns["canon_arr"] - patterns.groupby("route", sort=False)["canon_arr"].transform("first")
    first = trip_stops[trip_stops["stop_idx"] == 0][["trip_id", "arr_min"]].rename(columns={"arr_min": "arr0"})
    full = trip_stops.merge(first, on="trip_id", how="inner")
    full = full.assign(delta=(full["arr_min"] - full["arr0"]).astype(np.float32))
    n0 = first.merge(trip_stops[["trip_id", "route"]].drop_duplicates("trip_id"), on="trip_id").groupby("route").size()
    med = full.groupby(["route", "stop_idx"])["delta"].median().rename("med").reset_index()
    p = patterns[["route", "stop_idx"]].assign(canon=canon_off.to_numpy(dtype=np.float32))
    p = p.merge(med, on=["route", "stop_idx"], how="left")
    use_med = p["route"].map(n0).fillna(0).to_numpy() >= cfg.gtfs.min_offset_trips
    off = np.where(use_med & p["med"].notna().to_numpy(), p["med"].to_numpy(), p["canon"].to_numpy())
    off = pd.Series(off, index=patterns.index)
    return off.groupby(patterns["route"], sort=False).transform(np.maximum.accumulate).to_numpy(np.float32)


def _route_info(patterns: pd.DataFrame, n_trips: pd.Series, n_unmapped: pd.Series, cfg: Config) -> pd.DataFrame:
    """Per-route facts: stop count, loops, direction label, direction class vs the city centroid."""
    c_lat, c_lon = cfg.estimator.centroid
    grp = patterns.groupby("route", sort=True)
    info = pd.DataFrame({
        "n_stops": grp.size(),
        "has_loop": grp["stop_id"].apply(lambda s: bool(s.duplicated().any())),
        "first_lat": grp["lat"].first(), "first_lon": grp["lon"].first(),
        "last_lat": grp["lat"].last(), "last_lon": grp["lon"].last(),
    })
    d_first = haversine_m(info["first_lat"], info["first_lon"], c_lat, c_lon) / 1000
    d_last = haversine_m(info["last_lat"], info["last_lon"], c_lat, c_lon) / 1000
    diff = d_first - d_last
    thr = cfg.estimator.radial_min_diff_km
    info["dir_class"] = np.where(diff > thr, "inbound", np.where(diff < -thr, "outbound", "other"))
    info["direction"] = [(_DIRECTION.search(r).group(1) if _DIRECTION.search(r) else "") for r in info.index]
    info = info.join(n_trips).join(n_unmapped)
    info["n_unmapped"] = info["n_unmapped"].fillna(0).astype(int)
    info["n_trips"] = info["n_trips"].fillna(0).astype(int)
    return info.drop(columns=["first_lat", "first_lon", "last_lat", "last_lon"]).reset_index().rename(columns={"index": "route"})


def build_segments(patterns: pd.DataFrame, cfg: Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Segments (consecutive canonical stop pairs) and GTFS-only frozen stretches."""
    g = cfg.gtfs
    p = patterns
    nxt = p.groupby("route", sort=False)
    last = nxt.cumcount(ascending=False).to_numpy() == 0
    lat1, lon1 = p["lat"].to_numpy(), p["lon"].to_numpy()
    lat2, lon2 = np.roll(lat1, -1), np.roll(lon1, -1)
    off1, off2 = p["off_min"].to_numpy(), np.roll(p["off_min"].to_numpy(), -1)
    seg = pd.DataFrame({
        "route": p["route"].to_numpy(), "seg": p["stop_idx"].to_numpy(np.int16),
        "len_m": haversine_m(lat1, lon1, lat2, lon2).astype(np.float32),
        "tau_min": np.maximum(off2 - off1, g.min_tau_min).astype(np.float32),
    })[~last].reset_index(drop=True)

    stretch_id = np.zeros(len(seg), dtype=np.int32)
    rows = []
    for route, idx in seg.groupby("route", sort=True).indices.items():
        lens = seg["len_m"].to_numpy()[idx]
        start, acc_len, sid = 0, 0.0, 0
        bounds = []
        for k, ln in enumerate(lens):
            acc_len += ln
            if acc_len >= g.stretch_min_len_m or (k - start + 1) >= g.stretch_max_segments:
                bounds.append((start, k))
                start, acc_len = k + 1, 0.0
        if start < len(lens):                    # last short stretch merges backward
            if bounds:
                bounds[-1] = (bounds[-1][0], len(lens) - 1)
            else:
                bounds.append((start, len(lens) - 1))
        for sid, (a, b) in enumerate(bounds):
            stretch_id[idx[a:b + 1]] = sid
            rows.append((route, sid, a, b, float(lens[a:b + 1].sum())))
    seg["stretch_id"] = stretch_id
    stretches = pd.DataFrame(rows, columns=["route", "stretch_id", "seg_from", "seg_to", "len_m"])
    stretches["seg_from"] = stretches["seg_from"].astype(np.int16)
    stretches["seg_to"] = stretches["seg_to"].astype(np.int16)
    return seg.sort_values(["route", "seg"]).reset_index(drop=True), stretches


@dataclass
class Geometry:
    """Flat, route-indexed view of patterns and segments for fast NumPy joins."""

    names: np.ndarray            # sorted route names
    n_stops: np.ndarray          # per route
    stop_ptr: np.ndarray         # start of each route in the flat stop arrays (len = R + 1)
    seg_ptr: np.ndarray          # start of each route in the flat segment arrays (len = R + 1)
    off_min: np.ndarray          # per stop
    stop_id: np.ndarray          # per stop
    stop_name: np.ndarray        # per stop
    lat: np.ndarray
    lon: np.ndarray
    tau_min: np.ndarray          # per segment
    len_m: np.ndarray            # per segment
    stretch_id: np.ndarray       # per segment
    stretch_starts: np.ndarray   # first segment of every stretch (all routes, in segment order)
    stretch_route: np.ndarray    # route index of every stretch
    route_index: dict[str, int]

    @classmethod
    def build(cls, patterns: pd.DataFrame, segments: pd.DataFrame) -> "Geometry":
        p = patterns.sort_values(["route", "stop_idx"], kind="stable")
        names = p["route"].drop_duplicates().to_numpy()
        n_stops = p.groupby("route", sort=False).size().to_numpy()
        s = segments.sort_values(["route", "seg"], kind="stable")
        seg_route = np.repeat(np.arange(len(names)), n_stops - 1)
        sid = s["stretch_id"].to_numpy(np.int32)
        starts = np.flatnonzero(np.r_[True, (sid[1:] != sid[:-1]) | (seg_route[1:] != seg_route[:-1])])
        return cls(
            names=names, n_stops=n_stops,
            stop_ptr=np.r_[0, np.cumsum(n_stops)], seg_ptr=np.r_[0, np.cumsum(n_stops - 1)],
            off_min=p["off_min"].to_numpy(np.float32), stop_id=p["stop_id"].to_numpy(),
            stop_name=p["stop_name"].to_numpy(), lat=p["lat"].to_numpy(), lon=p["lon"].to_numpy(),
            tau_min=s["tau_min"].to_numpy(np.float32), len_m=s["len_m"].to_numpy(np.float32),
            stretch_id=sid, stretch_starts=starts, stretch_route=seg_route[starts],
            route_index={r: i for i, r in enumerate(names)},
        )

    @property
    def n_routes(self) -> int:
        return len(self.names)

    def route_ix(self, routes: pd.Series) -> np.ndarray:
        """Route-name column -> route index (-1 for routes absent from the GTFS)."""
        return routes.map(self.route_index).fillna(-1).to_numpy(np.int64)

    def stops_of(self, r: int) -> slice:
        return slice(self.stop_ptr[r], self.stop_ptr[r + 1])

    def segs_of(self, r: int) -> slice:
        return slice(self.seg_ptr[r], self.seg_ptr[r + 1])
