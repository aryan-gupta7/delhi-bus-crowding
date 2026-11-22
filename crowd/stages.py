"""Stage glue: the I/O around the pure modules, and the stage registry (S0-S8)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from crowd import eligibility, flows, gtfs, ingest, matching, supply as supply_mod, tuning
from crowd.eligibility import DAY_TYPES
from crowd.estimator import fit_estimator
from crowd.ensemble import run_ensemble
from crowd.index import hour_profile_z
from crowd.pipeline import Context, Stage



# -- shared lazily built objects ------------------------------------------------------------------

def geometry(ctx: Context) -> gtfs.Geometry:
    return ctx.memo("geo", lambda: gtfs.Geometry.build(ctx.store.read_table("patterns.parquet"),
                                                        ctx.store.read_table("segments.parquet")))


def tickets(ctx: Context) -> pd.DataFrame:
    return ctx.memo("tickets", lambda: ctx.store.read_table("tickets.parquet"))


def estimator(ctx: Context):
    """Estimator fitted on all eligible days with the profile-shrinkage multiplier chosen by an inner
    day-blocked split (cached per run; the choice is recorded in ``ctx.cache['strength_tuning']``)."""
    def build():
        st, geo, cfg = ctx.store, geometry(ctx), ctx.cfg
        counts, od, info = st.read_table("counts.parquet"), st.read_table("od_pairs.parquet"), st.read_table("route_info.parquet")
        dhok = st.read_table("day_hour_ok.parquet")
        pairs = flows.matched_pairs(tickets(ctx), st.read_table("ticket_stops.parquet"))
        weekdays = np.sort(dhok[(dhok["day_type"] == "weekday") & dhok["hour_ok"]]["date"].unique())
        scale, scores = tuning.choose_strength_scale(counts, od, pairs, dhok, geo, info, service(ctx), cfg, weekdays)
        ctx.cache["strength_tuning"] = {"chosen": scale, "shape_score_by_scale": scores}
        return fit_estimator(counts, od, geo, info, cfg, service=service(ctx), strength_scale=scale)
    return ctx.memo("estimator", build)


def service(ctx: Context) -> np.ndarray:
    """Route-hours with scheduled service, from the mapped GTFS trips."""
    return ctx.memo("service", lambda: supply_mod.route_hour_service(
        ctx.store.read_table("trip_stops.parquet"), geometry(ctx)))


def route_coverage_array(ctx: Context) -> np.ndarray:
    """Route-level both-ends match coverage as an array over geometry route indices."""
    geo = geometry(ctx)
    rc = matching.route_coverage(ctx.store.read_table("coverage.parquet"))
    arr = np.zeros(geo.n_routes)
    arr[geo.route_ix(rc["route"])] = rc["cov_both"].to_numpy()
    return arr


# -- stages ---------------------------------------------------------------------------------------

def stage_ingest(ctx: Context) -> None:
    df, report = ingest.read_tickets(ctx.cfg.path("tickets"))
    ctx.store.write_table("tickets.parquet", df)
    ctx.store.write_json("ingest_report.json", ingest.report_dict(report))
    ctx.cache["tickets"] = df


def stage_eligibility(ctx: Context) -> None:
    ctx.store.write_table("day_hour_ok.parquet", eligibility.build_day_hour_ok(tickets(ctx), ctx.cfg))


def stage_gtfs(ctx: Context) -> None:
    g = gtfs.load_gtfs(ctx.cfg.path("gtfs"))
    patterns, trip_stops, info = gtfs.build_patterns(g, ctx.cfg)
    segments, stretches = gtfs.build_segments(patterns, ctx.cfg)
    for name, df in (("patterns", patterns), ("trip_stops", trip_stops), ("route_info", info),
                     ("segments", segments), ("stretches", stretches)):
        ctx.store.write_table(f"{name}.parquet", df)
    ctx.store.write_table("gtfs_stops.parquet", g.stops)


def stage_matching(ctx: Context) -> None:
    df, geo = tickets(ctx), geometry(ctx)
    long = pd.concat([df[["route", "start_name", "pax"]].rename(columns={"start_name": "name"}),
                      df[["route", "end_name", "pax"]].rename(columns={"end_name": "name"})])
    pairs = long.groupby(["route", "name"], sort=True)["pax"].sum().reset_index()
    stops = ctx.store.read_table("gtfs_stops.parquet")
    matches = matching.match_names(pairs, geo, stops, ctx.cfg).merge(pairs, on=["route", "name"])
    resolved = matching.resolve_tickets(df, matches, geo)
    ctx.store.write_table("stop_matches.parquet", matches)
    ctx.store.write_table("ticket_stops.parquet", resolved)
    ctx.store.write_table("coverage.parquet", matching.coverage_by_route_band(
        df, resolved, ctx.cfg.estimator.hour_bands.to_dict()))


def stage_flows(ctx: Context) -> None:
    df, geo = tickets(ctx), geometry(ctx)
    resolved = ctx.store.read_table("ticket_stops.parquet")
    dhok = ctx.store.read_table("day_hour_ok.parquet")
    bands = ctx.cfg.estimator.hour_bands.to_dict()
    ctx.store.write_table("counts.parquet", flows.build_counts(df, geo, dhok))
    ctx.store.write_table("od_pairs.parquet", flows.build_od_pairs(df, resolved, dhok, bands))


def stage_supply(ctx: Context) -> None:
    geo = geometry(ctx)
    seats = supply_mod.route_seats(tickets(ctx), geo, ctx.cfg)
    ctx.store.write_table("route_seats.parquet", seats)
    ctx.store.write_table("supply.parquet", supply_mod.build_supply(
        ctx.store.read_table("trip_stops.parquet"), seats, geo, ctx.cfg))


def stage_model(ctx: Context) -> None:
    est, geo = estimator(ctx), geometry(ctx)
    seg_route = np.repeat(np.arange(geo.n_routes), geo.n_stops - 1)
    seg_local = np.arange(int(geo.seg_ptr[-1])) - geo.seg_ptr[seg_route]
    frames = []
    for day_type in DAY_TYPES:
        q = est.qhat(day_type)
        g, h = np.nonzero(q)
        frames.append(pd.DataFrame({"route": geo.names[seg_route[g]], "seg": seg_local[g].astype(np.int16),
                                    "hour": h.astype(np.int8), "day_type": day_type, "qhat": q[g, h]}))
    ctx.store.write_table("qhat.parquet", pd.concat(frames, ignore_index=True))
    ctx.store.write_json("estimator_fit.json", {
        "strength_tuning": ctx.cache["strength_tuning"], "strengths_used": est.profile_strength,
        "alpha": est.alpha, "phi": {k: v.tolist() for k, v in est.phi.items()}, "routes_modelled": len(est.routes)})


def stage_ensemble(ctx: Context) -> None:
    est, geo = estimator(ctx), geometry(ctx)
    supply_tbl = ctx.store.read_table("supply.parquet")
    dense = supply_mod.dense_supply(supply_tbl, geo)
    counts = ctx.store.read_table("counts.parquet")
    z = {dt: hour_profile_z(counts, dt) for dt in DAY_TYPES}
    result = run_ensemble(est, dense, ctx.store.read_table("route_seats.parquet"), route_coverage_array(ctx),
                          ctx.store.read_table("route_info.parquet"), z, ctx.cfg,
                          frozen_cuts=ctx.frozen_cuts)
    ctx.store.write_table("crowding_cells.parquet", result.cells)
    ctx.store.write_array("levels.npy", result.levels)
    ctx.store.write_json("cuts.json", {"cuts": {k: {"central": v["central"], "draws": v["draws"]}
                                                for k, v in result.cuts.items()},
                                       "z": z, "scenario": {"theta_grid": list(ctx.cfg.ensemble.theta_grid),
                                                            "theta_central": ctx.cfg.ensemble.theta_central,
                                                            "sigma_r": ctx.cfg.ensemble.sigma_r,
                                                            "k": ctx.cfg.ensemble.k}})


def stage_outputs(ctx: Context) -> None:
    """Map and operator-view artefacts: stretch geometry and the route x hour matrix."""
    geo, cells = geometry(ctx), ctx.store.read_table("crowding_cells.parquet")
    stretches = ctx.store.read_table("stretches.parquet")
    features = []
    for row in stretches.itertuples(index=False):
        r = geo.route_index[row.route]
        sl = geo.stops_of(r)
        lat, lon = geo.lat[sl][row.seg_from:row.seg_to + 2], geo.lon[sl][row.seg_from:row.seg_to + 2]
        features.append({"type": "Feature",
                         "properties": {"route": row.route, "stretch_id": int(row.stretch_id),
                                        "len_m": round(float(row.len_m), 1)},
                         "geometry": {"type": "LineString",
                                      "coordinates": [[round(float(x), 6), round(float(y), 6)] for x, y in zip(lon, lat)]}})
    with open(ctx.store.path("stretches.geojson"), "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": features}, fh, separators=(",", ":"))
    worst = cells.sort_values(["route", "day_type", "hour", "pi_central"], ascending=[True, True, True, False])
    worst = worst.drop_duplicates(["route", "day_type", "hour"], keep="first")
    matrix = worst[["route", "day_type", "hour", "level", "robust_in_range", "tier", "stretch_id", "pi_central"]]
    matrix.rename(columns={"level": "level_worst_stretch", "stretch_id": "pinch_stretch_id"}).to_csv(
        ctx.store.path("route_hour_matrix.csv"), index=False)


def stage_gates(ctx: Context) -> None:
    from crowd import gates
    ctx.store.write_json("gates.json", gates.run_gates(ctx))


# everything the estimator (incl. its tuning split) reads
MODEL_INPUTS = ("counts.parquet", "od_pairs.parquet", "route_info.parquet", "patterns.parquet", "segments.parquet",
                "trip_stops.parquet", "tickets.parquet", "ticket_stops.parquet", "day_hour_ok.parquet")

STAGES: list[Stage] = [
    Stage("ingest", stage_ingest, ("raw:tickets",), ("tickets.parquet", "ingest_report.json"),
          (), ("ingest", "stages")),
    Stage("eligibility", stage_eligibility, ("tickets.parquet",), ("day_hour_ok.parquet",),
          ("eligibility",), ("eligibility", "stages")),
    Stage("gtfs", stage_gtfs, ("raw:gtfs",),
          ("patterns.parquet", "trip_stops.parquet", "route_info.parquet", "segments.parquet",
           "stretches.parquet", "gtfs_stops.parquet"), ("gtfs", "estimator"), ("gtfs", "stages")),
    Stage("matching", stage_matching, ("tickets.parquet", "patterns.parquet", "segments.parquet", "gtfs_stops.parquet"),
          ("stop_matches.parquet", "ticket_stops.parquet", "coverage.parquet"), ("matching", "estimator"),
          ("matching", "names", "stages")),
    Stage("flows", stage_flows, ("tickets.parquet", "ticket_stops.parquet", "day_hour_ok.parquet",
                                 "patterns.parquet", "segments.parquet"),
          ("counts.parquet", "od_pairs.parquet"), ("flows", "estimator"), ("flows", "stages")),
    Stage("supply", stage_supply, ("tickets.parquet", "trip_stops.parquet", "patterns.parquet", "segments.parquet"),
          ("supply.parquet", "route_seats.parquet"), ("supply",), ("supply", "stages")),
    Stage("model", stage_model, MODEL_INPUTS, ("qhat.parquet", "estimator_fit.json"),
          ("estimator", "flows", "supply", "validation"),
          ("estimator", "tuning", "supply", "flows", "validation/targets", "validation/metrics", "stages")),
    Stage("ensemble", stage_ensemble, MODEL_INPUTS + ("supply.parquet", "route_seats.parquet", "coverage.parquet", "frozen_cuts"),
          ("crowding_cells.parquet", "levels.npy", "cuts.json"),
          ("estimator", "flows", "supply", "validation", "ensemble", "index", "tiers"),
          ("estimator", "tuning", "supply", "flows", "ensemble", "index", "tiers", "validation/targets",
           "validation/metrics", "stages")),
    Stage("gates", stage_gates, ("tickets.parquet", "ticket_stops.parquet", "day_hour_ok.parquet", "coverage.parquet",
                                 "stop_matches.parquet", "route_info.parquet", "route_seats.parquet", "counts.parquet",
                                 "trip_stops.parquet", "crowding_cells.parquet", "patterns.parquet", "segments.parquet",
                                 "supply.parquet"),
          ("gates.json",), ("gates", "flows", "tiers"), ("gates", "flows", "index", "supply", "validation/metrics", "stages")),
    Stage("outputs", stage_outputs, ("crowding_cells.parquet", "stretches.parquet", "patterns.parquet", "segments.parquet"),
          ("stretches.geojson", "route_hour_matrix.csv"), (), ("stages",)),
]
