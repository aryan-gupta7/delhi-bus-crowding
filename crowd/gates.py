"""Gates G1-G7 (design/mechanism.md §5): measurable checks run *before* trusting a stage.

Each gate returns ``{id, name, value, threshold, passed, blocking, note}``. G1 is a regression
test of the eligibility rule (its thresholds were chosen on October), not validation. G3 stays
open: the tickets carry no bus-length field.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import yaml
from scipy.stats import spearmanr

from crowd import flows, matching, stages
from crowd.gtfs import haversine_m
from crowd.pipeline import Context


def _gate(gid: str, name: str, value, threshold, passed, blocking: bool = False, note: str = "") -> dict:
    return {"id": gid, "name": name, "value": value, "threshold": threshold, "passed": passed,
            "blocking": blocking, "note": note}


def g1_eligibility(ctx: Context) -> dict:
    """The eligibility rule still reproduces the profiled October anomaly list."""
    path = ctx.cfg.root / ctx.cfg.gates.oracle
    if not path.exists():
        return _gate("G1", "eligibility regression", None, None, None, note="oracle file absent: skipped")
    oracle = yaml.safe_load(path.read_text())
    dh = ctx.store.read_table("day_hour_ok.parquet")
    dh["d"] = dh["date"].dt.strftime("%Y-%m-%d")
    masked = dh[dh["reason"] == "outage"].groupby("d")["hour"].apply(set).to_dict()
    failures = []
    for day, hours in oracle["outage_hours"].items():
        if not set(hours) <= masked.get(day, set()):
            failures.append(f"{day}: expected {hours} masked, got {sorted(masked.get(day, []))}")
    tolerated = {d: set(h) for d, h in oracle.get("tolerated_extra_masks", {}).items()}
    expected = {d: set(h) for d, h in oracle["outage_hours"].items()}
    for day, hours in masked.items():
        extra = hours - expected.get(day, set()) - tolerated.get(day, set())
        if extra and day not in oracle["stream_fault_days"]:
            failures.append(f"{day}: unexpected masked hours {sorted(extra)}")
    faults = set(dh[dh["reason"] == "stream_fault"]["d"])
    if faults != set(oracle["stream_fault_days"]):
        failures.append(f"stream-fault days {sorted(faults)} != {oracle['stream_fault_days']}")
    weekend_days = set(dh[dh["day_type"] == "weekend"]["d"])
    if not set(oracle["holiday_like_days"]) <= weekend_days:
        failures.append("holiday-like days not classified as weekend/holiday")
    sundays = dh[(dh["date"].dt.dayofweek == 6) & dh["hour"].isin(oracle["sunday_peak_hours"]) & (dh["reason"] == "outage")]
    if len(sundays):
        failures.append(f"{len(sundays)} Sunday peak-hour cells masked")
    return _gate("G1", "eligibility rule reproduces October anomalies (regression test)", len(failures), 0,
                 not failures, blocking=True, note="; ".join(failures) or "all anomalies reproduced")


def g2_coverage(ctx: Context) -> dict:
    """Both-ends stop-match coverage by route-volume tier, cascade contribution and hub bias."""
    cov = ctx.store.read_table("coverage.parquet")
    rc = matching.route_coverage(cov)
    by_tier = rc.groupby("vol_tier").apply(lambda g: g["pax_both"].sum() / g["pax"].sum(), include_groups=False)
    top = by_tier.get("top250", np.nan)
    m = ctx.store.read_table("stop_matches.parquet")
    steps = (m.groupby("method")["pax"].sum() / m["pax"].sum()).round(4).to_dict()
    unmatched = m[m["method"] == "none"].groupby("name")["pax"].sum().sort_values(ascending=False)
    hubs = {k: round(float(v / unmatched.sum()), 4) for k, v in unmatched.head(20).items()}
    ok = bool(rc.query("vol_tier != 'rest'")["pax_both"].sum() / rc.query("vol_tier != 'rest'")["pax"].sum()
              >= ctx.cfg.gates.min_top250_coverage)
    g = _gate("G2", "both-ends coverage, top-250 routes (passenger-weighted)",
              round(float(rc.query("vol_tier != 'rest'")["pax_both"].sum() / rc.query("vol_tier != 'rest'")["pax"].sum()), 4),
              ctx.cfg.gates.min_top250_coverage, ok, blocking=True,
              note="reported with cascade contribution and the 20 most frequent unmatched names")
    g["detail"] = {"coverage_by_tier": {k: round(float(v), 4) for k, v in by_tier.items()},
                   "pax_share_by_method": steps, "unmatched_hub_share_top20": hubs,
                   "overall_both_ends": round(float(cov["pax_both"].sum() / cov["pax"].sum()), 4)}
    return g


def g2b_fare_precision(ctx: Context) -> dict:
    """Precision proxy for fuzzy/coordinate matches: fare-vs-distance rank correlation by class."""
    df, geo = stages.tickets(ctx), stages.geometry(ctx)
    res = ctx.store.read_table("ticket_stops.parquet")
    ok = res["ok_pair"].to_numpy() & df["is_ac"].to_numpy()
    ma, mb = res["match_a"].to_numpy(), res["match_b"].to_numpy()
    classes = {"both_exact": (ma == "exact") & (mb == "exact"),
               "any_fuzzy": (ma == "fuzzy") | (mb == "fuzzy"), "any_coord": (ma == "coord") | (mb == "coord")}
    route_ix = geo.route_ix(df["route"])
    fare = (df["amount"] / df["pax"]).to_numpy()
    out = {}
    for name, sel in classes.items():
        idx = np.flatnonzero(sel & ok)[: ctx.cfg.gates.fare_check_sample]
        base = geo.stop_ptr[route_ix[idx]]
        d = haversine_m(geo.lat[base + res["a"].to_numpy()[idx]], geo.lon[base + res["a"].to_numpy()[idx]],
                        geo.lat[base + res["b"].to_numpy()[idx]], geo.lon[base + res["b"].to_numpy()[idx]])
        out[name] = round(float(spearmanr(fare[idx], d)[0]), 3)
    passed = bool(out["any_fuzzy"] >= out["both_exact"] - 0.05 and out["any_coord"] >= out["both_exact"] - 0.05)
    return _gate("G2b", "fuzzy/coordinate match precision proxy: Spearman(fare, ride distance), AC tickets",
                 out, "fuzzy and coord within 0.05 of exact", passed,
                 note="same correlation as exact matches supports match precision (fares are not used in matching)")


def g3_seats(ctx: Context) -> dict:
    seats = ctx.store.read_table("route_seats.parquet")
    default = float((seats["seats_source"] == "fleet_default").mean())
    return _gate("G3", "bus class mapping (OPEN: no bus-length field in tickets)", round(default, 3), None, None,
                 note="share of routes using the fleet-default AC mix; seat counts are the configured A-9 "
                      "assumption until an external vehicle->length table is obtained")


def g4_small_n(ctx: Context) -> dict:
    cells = ctx.store.read_table("crowding_cells.parquet", ["day_type", "pi_central", "Z", "N"])
    wk = cells[cells["day_type"] == "weekday"]
    w = (wk["pi_central"] * wk["Z"]).to_numpy()
    share = float(w[(wk["N"] <= ctx.cfg.tiers.small_n).to_numpy()].sum() / w.sum())
    return _gate("G4", "exposure share of cells with N <= small_n (weekday)", round(share, 3), None, None,
                 note="these cells are capped at tier Medium and flagged small_N; no Pi shrink by default")


def g5_gtfs(ctx: Context) -> dict:
    info = ctx.store.read_table("route_info.parquet")
    geo = stages.geometry(ctx)
    df = stages.tickets(ctx)
    route_share = float(df.loc[geo.route_ix(df["route"]) >= 0, "pax"].sum() / df["pax"].sum())
    unmapped = int(info["n_unmapped"].sum())
    g = _gate("G5", "trips not mappable onto their canonical pattern", unmapped, 0, unmapped == 0, blocking=True,
              note=f"loop routes: {int(info['has_loop'].sum())}; ticket volume on GTFS routes: {route_share:.4f}")
    return g


def g6_shift(ctx: Context) -> dict:
    """Destination-shift robustness: rank correlation of flows when declared ends move +-1/+-2 stops."""
    df, geo = stages.tickets(ctx), stages.geometry(ctx)
    res = ctx.store.read_table("ticket_stops.parquet")
    dh = ctx.store.read_table("day_hour_ok.parquet")
    dates = dh["date"].unique()
    n_stops = geo.n_stops[geo.route_ix(res["route"]).clip(0)]
    base = flows.observed_flows(flows.matched_pairs(df, res), geo, dh, dates, ctx.cfg.flows.gamma)["weekday"].per_day().ravel()
    corr = {}
    for shift in (-2, -1, 1, 2):
        moved = res.copy()
        b = np.clip(res["b"].to_numpy() + shift, 0, n_stops - 1)
        moved["b"] = b
        moved["ok_pair"] = res["ok_pair"].to_numpy() & (b > res["a"].to_numpy())
        alt = flows.observed_flows(flows.matched_pairs(df, moved), geo, dh, dates, ctx.cfg.flows.gamma)["weekday"].per_day().ravel()
        sel = (base > 0) | (alt > 0)
        corr[f"{shift:+d}"] = round(float(spearmanr(base[sel], alt[sel])[0]), 4)
    worst = min(corr.values())
    return _gate("G6", "rank correlation of segment flows under +-1/+-2-stop destination shift", corr,
                 ctx.cfg.gates.min_shift_rank_corr, worst >= ctx.cfg.gates.min_shift_rank_corr,
                 note="tests the least-validated assumption A-4 (declared destination = true alighting)")


def g7_hour_profile(ctx: Context) -> dict:
    """Documents cross-hour non-identifiability: ticket share peaks far harder than the timetable."""
    counts = ctx.store.read_table("counts.parquet")
    wk = counts[counts["day_type"] == "weekday"]
    tickets_h = wk.groupby("hour")["n_tickets"].sum().reindex(range(24), fill_value=0)
    trips = ctx.store.read_table("trip_stops.parquet", ["stop_idx", "dep_min"])
    starts = trips[trips["stop_idx"] == 0]
    trips_h = ((starts["dep_min"] % 1440) // 60).value_counts().reindex(range(24), fill_value=0)
    ratio = float((tickets_h[9] / tickets_h[13]) / (trips_h[9] / trips_h[13]))
    return _gate("G7", "ticket peak/midday ratio relative to timetable peak/midday ratio (09h vs 13h)",
                 round(ratio, 2), None, None,
                 note="a ratio far from 1 means cross-hour scale is not identified by the data (see mechanism §1)")


GATES = (g1_eligibility, g2_coverage, g2b_fare_precision, g3_seats, g4_small_n, g5_gtfs, g6_shift, g7_hour_profile)


def run_gates(ctx: Context) -> list[dict]:
    return [g(ctx) for g in GATES]
