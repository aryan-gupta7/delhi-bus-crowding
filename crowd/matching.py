"""S2: ticket stop names -> canonical stop indices (design/mechanism.md S2).

Matching is per route: candidates are only stops on that route's canonical pattern.
Cascade, stopping at the first success: (1) normalise, (2) exact on-route, (3) split composite
names on '/', (4) on-route fuzzy token-set match with an ambiguity guard, (5) coordinates of
the same-named stop elsewhere in ``stops.txt`` within a radius, (6) unmatched.
The work is done on unique (route, name) pairs, then joined back to tickets. The pair
constraint is loop-aware: the start maps to its first occurrence, the end to its first
occurrence after the start.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

from crowd.config import Config
from crowd.gtfs import Geometry, haversine_m
from crowd.names import make_normaliser, split_composite

METHODS = ["exact", "split", "fuzzy", "coord", "none"]


def _route_tables(geo: Geometry, normalise) -> list[dict[str, int]]:
    """Per route: normalised stop name -> first canonical index."""
    tables: list[dict[str, int]] = []
    for r in range(geo.n_routes):
        t: dict[str, int] = {}
        for i, name in enumerate(geo.stop_name[geo.stops_of(r)]):
            t.setdefault(normalise(name), i)
        tables.append(t)
    return tables


def _global_coords(stops: pd.DataFrame, normalise) -> dict[str, np.ndarray]:
    """Normalised stop name -> (k, 2) array of lat/lon over all GTFS stops of that name."""
    acc: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for name, lat, lon in zip(stops["stop_name"], stops["lat"], stops["lon"]):
        acc[normalise(name)].append((lat, lon))
    return {k: np.asarray(v) for k, v in acc.items()}


def match_names(pairs: pd.DataFrame, geo: Geometry, stops: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Resolve unique ``(route, name)`` pairs to a canonical stop index.

    ``pairs`` has columns route, name, pax (passengers using the name; used for diagnostics).
    Returns route, name, idx (first occurrence, -1 if unmatched), method.
    """
    mcfg = cfg.matching
    normalise = make_normaliser(dict(mcfg.abbreviations.to_dict()))
    tables = _route_tables(geo, normalise)
    coords = _global_coords(stops, normalise)
    pair_route = geo.route_ix(pairs["route"])

    idx = np.full(len(pairs), -1, dtype=np.int32)
    method = np.full(len(pairs), "none", dtype=object)
    for k, (r, name) in enumerate(zip(pair_route, pairs["name"].to_numpy())):
        if r < 0:
            continue
        table = tables[r]
        norm = normalise(name)
        hit = table.get(norm)
        if hit is not None:
            idx[k], method[k] = hit, "exact"
            continue
        parts = split_composite(norm) if "/" in norm else []
        hit = next((table[p] for p in parts if p in table), None)
        if hit is not None:
            idx[k], method[k] = hit, "split"
            continue
        hit = _fuzzy(norm, table, mcfg.fuzzy_score, mcfg.fuzzy_margin)
        if hit is not None:
            idx[k], method[k] = hit, "fuzzy"
            continue
        hit = _by_coordinates(parts or [norm], coords, geo, r, mcfg.coord_radius_m)
        if hit is not None:
            idx[k], method[k] = hit, "coord"
    return pd.DataFrame({"route": pairs["route"].to_numpy(), "name": pairs["name"].to_numpy(),
                         "idx": idx, "method": method})


def _fuzzy(norm: str, table: dict[str, int], min_score: float, margin: float) -> int | None:
    """Best on-route token-set match, accepted only if clear of the runner-up."""
    best = process.extract(norm, list(table), scorer=fuzz.token_set_ratio, limit=2)
    if not best or best[0][1] < min_score:
        return None
    if len(best) > 1 and best[0][1] - best[1][1] < margin:
        return None
    return table[best[0][0]]


def _by_coordinates(names: list[str], coords: dict[str, np.ndarray], geo: Geometry, r: int,
                    radius_m: float) -> int | None:
    """Nearest on-route stop to any same-named stop elsewhere in stops.txt, within a radius."""
    sl = geo.stops_of(r)
    lat, lon = geo.lat[sl], geo.lon[sl]
    best_d, best_i = radius_m, None
    for n in names:
        pts = coords.get(n)
        if pts is None:
            continue
        d = haversine_m(lat[:, None], lon[:, None], pts[None, :, 0], pts[None, :, 1]).min(axis=1)
        i = int(d.argmin())
        if d[i] <= best_d:
            best_d, best_i = d[i], i
    return best_i


def resolve_tickets(tickets: pd.DataFrame, matches: pd.DataFrame, geo: Geometry) -> pd.DataFrame:
    """Join matched stops back onto tickets and apply the loop-aware pair constraint."""
    key = matches.set_index(["route", "name"])
    start_pos = key.index.get_indexer(pd.MultiIndex.from_arrays([tickets["route"], tickets["start_name"]]))
    end_pos = key.index.get_indexer(pd.MultiIndex.from_arrays([tickets["route"], tickets["end_name"]]))
    idx_arr, method_arr = key["idx"].to_numpy(), key["method"].to_numpy()
    a = np.where(start_pos >= 0, idx_arr[start_pos], -1).astype(np.int32)
    b = np.where(end_pos >= 0, idx_arr[end_pos], -1).astype(np.int32)
    ma = np.where(start_pos >= 0, method_arr[start_pos], "none")
    mb = np.where(end_pos >= 0, method_arr[end_pos], "none")
    route_ix = geo.route_ix(tickets["route"])

    b = _end_after_start(a, b, route_ix, geo)
    ok_pair = (a >= 0) & (b >= 0) & (a < b)
    return pd.DataFrame({
        "tid": tickets["tid"].to_numpy(), "route": tickets["route"].to_numpy(),
        "a": a, "b": b, "match_a": ma, "match_b": mb, "ok_pair": ok_pair,
    })


def _end_after_start(a: np.ndarray, b: np.ndarray, route_ix: np.ndarray, geo: Geometry) -> np.ndarray:
    """Loop routes: move the end to its first occurrence with index > start."""
    b = b.copy()
    for k in np.flatnonzero((a >= 0) & (b >= 0) & (b <= a) & (route_ix >= 0)):
        sl = geo.stops_of(int(route_ix[k]))
        ids = geo.stop_id[sl]
        later = np.flatnonzero((ids == ids[b[k]]) & (np.arange(len(ids)) > a[k]))
        if later.size:
            b[k] = later[0]
    return b


def coverage_by_route_band(tickets: pd.DataFrame, resolved: pd.DataFrame, bands: dict[str, list[int]]) -> pd.DataFrame:
    """Passenger-weighted both-ends coverage per (route, hour band)."""
    hour_band = {h: name for name, hours in bands.items() for h in hours}
    df = pd.DataFrame({
        "route": tickets["route"].to_numpy(), "band": tickets["hour"].map(hour_band).to_numpy(),
        "pax": tickets["pax"].to_numpy(), "ok": resolved["ok_pair"].to_numpy(),
    })
    df["pax_both"] = np.where(df["ok"], df["pax"], 0)
    out = df.groupby(["route", "band"], sort=True).agg(
        n_tickets=("pax", "size"), pax=("pax", "sum"), pax_both=("pax_both", "sum")).reset_index()
    out["cov_both"] = (out["pax_both"] / out["pax"]).astype("float32")
    return out


def route_coverage(coverage: pd.DataFrame, top_edges: tuple[int, int] = (50, 250)) -> pd.DataFrame:
    """Route-level coverage with a volume tier (top-50 / top-250 / rest by passengers)."""
    r = coverage.groupby("route").agg(pax=("pax", "sum"), pax_both=("pax_both", "sum")).reset_index()
    r["cov_both"] = r["pax_both"] / r["pax"]
    rank = r["pax"].rank(ascending=False, method="first")
    r["vol_tier"] = np.where(rank <= top_edges[0], "top50", np.where(rank <= top_edges[1], "top250", "rest"))
    return r
