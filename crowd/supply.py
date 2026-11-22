"""S4: scheduled supply N, seats per bus and Z = N * seats (design/mechanism.md S4)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from crowd.config import Config
from crowd.eligibility import DAY_TYPES, WEEKDAY, WEEKEND
from crowd.gtfs import Geometry


def build_trip_counts(trip_stops: pd.DataFrame, geo: Geometry) -> np.ndarray:
    """N per (global segment, hour): mapped trips whose departure from the segment's upstream stop
    falls in that hour. Departures after midnight wrap to the next clock day's hours."""
    route_ix = geo.route_ix(trip_stops["route"])
    idx = trip_stops["stop_idx"].to_numpy(np.int64)
    has_segment = idx < (geo.n_stops[route_ix] - 1)
    gseg = geo.seg_ptr[route_ix] + idx
    hour = (trip_stops["dep_min"].to_numpy(np.int64) % 1440) // 60
    n_seg = int(geo.seg_ptr[-1])
    counts = np.bincount((gseg * 24 + hour)[has_segment], minlength=n_seg * 24)
    return counts.reshape(n_seg, 24).astype(np.float32)


def route_hour_service(trip_stops: pd.DataFrame, geo: Geometry) -> np.ndarray:
    """[n_routes, 24] bool: the route has a scheduled bus passing some segment in that hour."""
    per_route = np.add.reduceat(build_trip_counts(trip_stops, geo), geo.seg_ptr[:-1], axis=0)
    return per_route > 0


def route_seats(tickets: pd.DataFrame, geo: Geometry, cfg: Config) -> pd.DataFrame:
    """Seats per bus by route: vehicle-weighted AC share x configured seat counts (A-9).

    One vote per distinct tagged vehicle on the route (a vehicle is AC if most of its tickets
    are). Routes without a tagged vehicle use the fleet-wide AC share. Bus length is not in the
    tickets, so gate G3 stays open and every row says where its seat count came from.
    """
    tagged = tickets[tickets["vehicle"].notna()]
    veh = tagged.groupby(["route", "vehicle"], sort=True)["is_ac"].mean().ge(0.5).reset_index()
    per_route = veh.groupby("route").agg(n_vehicles=("is_ac", "size"), share_ac=("is_ac", "mean"))
    fleet_share = float(veh["is_ac"].mean())
    out = pd.DataFrame({"route": geo.names}).merge(per_route.reset_index(), on="route", how="left")
    out["n_vehicles"] = out["n_vehicles"].fillna(0).astype(int)
    out["seats_source"] = np.where(out["n_vehicles"] > 0, "vehicle_mix", "fleet_default")
    out["share_ac"] = out["share_ac"].fillna(fleet_share)
    seats = cfg.supply.seats
    out["seats_per_bus"] = (out["share_ac"] * seats.ac + (1 - out["share_ac"]) * seats.non_ac).astype("float32")
    return out


def build_supply(trip_stops: pd.DataFrame, seats: pd.DataFrame, geo: Geometry, cfg: Config) -> pd.DataFrame:
    """Long supply table over (route, seg, hour, day_type) with non-zero N."""
    n_weekday = build_trip_counts(trip_stops, geo)
    omega = cfg.supply.weekend_omega
    seat_by_route = seats.set_index("route")["seats_per_bus"].reindex(geo.names).to_numpy(np.float32)
    seg_route = np.repeat(np.arange(geo.n_routes), geo.n_stops - 1)
    seg_local = np.arange(int(geo.seg_ptr[-1])) - geo.seg_ptr[seg_route]
    frames = []
    for day_type, n_mat in ((WEEKDAY, n_weekday), (WEEKEND, n_weekday * omega)):
        g, h = np.nonzero(n_mat)
        frames.append(pd.DataFrame({
            "route": geo.names[seg_route[g]], "seg": seg_local[g].astype(np.int16),
            "hour": h.astype(np.int8), "day_type": day_type,
            "N": n_mat[g, h], "seats_per_bus": seat_by_route[seg_route[g]],
        }))
    out = pd.concat(frames, ignore_index=True)
    out["Z"] = (out["N"] * out["seats_per_bus"]).astype("float32")
    return out.sort_values(["day_type", "route", "seg", "hour"]).reset_index(drop=True)


def dense_supply(supply: pd.DataFrame, geo: Geometry) -> dict[str, dict[str, np.ndarray]]:
    """Supply table -> dense ``{day_type: {'N': [n_seg,24], 'Z': [n_seg,24]}}`` arrays."""
    route_ix = geo.route_ix(supply["route"])
    gseg = geo.seg_ptr[route_ix] + supply["seg"].to_numpy(np.int64)
    n_seg = int(geo.seg_ptr[-1])
    out: dict[str, dict[str, np.ndarray]] = {}
    for day_type, sub in supply.groupby("day_type"):
        sel = (supply["day_type"] == day_type).to_numpy()
        n_mat = np.zeros((n_seg, 24), np.float32)
        z_mat = np.zeros((n_seg, 24), np.float32)
        n_mat[gseg[sel], supply["hour"].to_numpy()[sel]] = supply["N"].to_numpy()[sel]
        z_mat[gseg[sel], supply["hour"].to_numpy()[sel]] = supply["Z"].to_numpy()[sel]
        out[day_type] = {"N": n_mat, "Z": z_mat}
    return out
