"""FastAPI app: planner, ride query and operator view endpoints plus the static web page."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from crowd import stages
from crowd.eligibility import DAY_TYPES
from crowd.outputs import StopResolver, query
from crowd.pipeline import Context
from crowd.planner.service import level_json, load_planner

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def create_app(ctx: Context) -> FastAPI:
    """Build the app from the artefacts in ``ctx.store`` (run ``make all`` first)."""
    st = ctx.store
    cells = st.read_table("crowding_cells.parquet")
    planner = load_planner(ctx)
    table, geo = planner.table, planner.geo
    resolver = StopResolver(geo, ctx.cfg)
    matrix = pd.read_csv(st.path("route_hour_matrix.csv"))
    volume = st.read_table("counts.parquet", ["route", "day_type", "n_tickets"]).groupby(["day_type", "route"])["n_tickets"].sum()
    with open(st.path("stretches.geojson"), encoding="utf-8") as fh:
        stretch_features: dict[str, list[dict]] = {}
        for f in json.load(fh)["features"]:
            stretch_features.setdefault(f["properties"]["route"], []).append(f)

    daily = st.read_table("day_hour_ok.parquet").assign(pax=lambda d: d["v_null"] + d["v_tagged"])
    daily = daily[daily["day_ok"] & (daily["day_type"] == "weekday")].groupby("date")["pax"].sum()
    scenario_capture = ctx.cfg.operator.daily_riders / float(daily.median())     # press-figure riders per sampled passenger (A-1)
    coverage = dict(zip(geo.names, stages.route_coverage_array(ctx)[: geo.n_routes]))
    cells = cells.assign(sampled=cells["pi_mean"] * cells["Z"])
    stretch_ends = {(r.route, int(r.stretch_id)): (int(r.seg_from), int(r.seg_to)) for r in st.read_table("stretches.parquet").itertuples()}

    def stretch_label(route: str, stretch_id: int) -> str:
        """First and last stop of a stretch, for lists and the detail panel."""
        a, b = stretch_ends[(route, stretch_id)]
        names = geo.stop_name[geo.stops_of(geo.route_index[route])]
        return f"{names[a]} to {names[b + 1]}"

    def day_cells(day: str) -> pd.DataFrame:
        check_day(day)
        return cells[cells["day_type"] == day]

    def cell_rows(sub: pd.DataFrame) -> list[dict]:
        return [{"route": r.route, "stretch_id": int(r.stretch_id), "label": stretch_label(r.route, int(r.stretch_id)),
                 "hour": int(r.hour), "level": level_json(int(r.level)),
                 "tier": r.tier, "robust_in_range": bool(r.robust_in_range), "sampled": round(float(r.sampled), 1),
                 "pi": round(float(r.pi_central), 3), "buses_per_hour": float(r.N),
                 "relief": round(float(getattr(r, "relief", 0.0)), 3)} for r in sub.itertuples()]

    app = FastAPI(title="Delhi bus crowding planner", docs_url="/api/docs", redoc_url=None)

    def check_day(day: str) -> str:
        if day not in DAY_TYPES:
            raise HTTPException(422, f"day must be one of {DAY_TYPES}")
        return day

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "cells": len(cells)}

    @app.get("/stops")
    def stops(q: str = Query(min_length=2)) -> list[dict]:
        return planner.stops.search(q)

    @app.get("/plan")
    def plan(from_stop: str, to_stop: str, time: str = "09:00", day: str = "weekday") -> dict:
        if from_stop not in planner.stops.pos_of or to_stop not in planner.stops.pos_of:
            raise HTTPException(404, "unknown stop id")
        return planner.plan(from_stop, to_stop, time, check_day(day), with_later=True)

    @app.get("/crowding")
    def crowding(route: str, from_stop: str, to_stop: str, time: str = "09:00", day: str = "weekday") -> dict:
        result = query(table, geo, resolver, route, from_stop, to_stop, time, check_day(day))
        if "error" in result:
            raise HTTPException(404, result["error"])
        return result

    @app.get("/operator/heatmap")
    def heatmap(day: str = "weekday", limit: int = 40) -> dict:
        """Route x hour grid of the worst stretch's level, busiest routes (by tickets) first."""
        check_day(day)
        routes = volume.loc[day].sort_values(ascending=False).head(limit).index
        sub = matrix[(matrix["day_type"] == day) & matrix["route"].isin(routes)]
        grid = {r: [None] * 24 for r in routes}
        for row in sub.itertuples(index=False):
            grid[row.route][row.hour] = {"level": level_json(int(row.level_worst_stretch)), "stretch_id": int(row.pinch_stretch_id),
                                         "robust_in_range": bool(row.robust_in_range), "tier": row.tier}
        return {"day": day, "routes": list(routes), "grid": grid, "coverage": {r: round(float(coverage[r]), 3) for r in routes}}

    @app.get("/operator/stretches")
    def stretches(route: str, hour: int = Query(ge=0, le=23), day: str = "weekday") -> dict:
        """Stretch lines of one route with their level at an hour (for the map)."""
        check_day(day)
        feats = stretch_features.get(route)
        if feats is None:
            raise HTTPException(404, "unknown route")
        out = []
        for f in feats:
            i = table.row(route, f["properties"]["stretch_id"], hour, day)
            level = int(cells.at[i, "level"]) if i is not None else 0
            props = {**f["properties"], "level": level_json(level), "flow": 0.0}
            if i is not None:
                props.update(tier=cells.at[i, "tier"], robust_in_range=bool(cells.at[i, "robust_in_range"]),
                             pi=round(float(cells.at[i, "pi_central"]), 4), buses_per_hour=float(cells.at[i, "N"]),
                             flow=round(float(cells.at[i, "sampled"]), 2))
            out.append({"type": "Feature", "properties": props, "geometry": f["geometry"]})
        return {"type": "FeatureCollection", "features": out}

    @app.get("/operator/overloaded")
    def overloaded(day: str = "weekday") -> list[dict]:
        """Stretch-hours that are Very busy with medium or high evidence and firm, ranked by sampled riders."""
        sub = day_cells(day)
        sub = sub[(sub["level"] == 3) & sub["tier"].isin(["Medium", "High"]) & sub["robust_in_range"]]
        return cell_rows(sub.sort_values("sampled", ascending=False).head(ctx.cfg.operator.list_size))

    @app.get("/operator/relief")
    def relief(day: str = "weekday") -> list[dict]:
        """Relief per added bus = sampled riders x Pi / (N + 1) (ignores induced demand and bunching); no 'buses needed'."""
        sub = day_cells(day)
        sub = sub[sub["tier"].isin(["Medium", "High"])].assign(relief=lambda d: d["sampled"] * d["pi_central"] / (d["N"] + 1))
        return cell_rows(sub.sort_values("relief", ascending=False).head(ctx.cfg.operator.list_size))

    @app.get("/operator/cell")
    def cell(route: str, stretch_id: int, hour: int = Query(ge=0, le=23), day: str = "weekday") -> dict:
        """Everything behind one stretch-hour for the detail panel; passengers per seat only as a labelled scenario."""
        i = table.row(route, stretch_id, hour, check_day(day))
        if i is None:
            raise HTTPException(404, "no such stretch-hour")
        c = cells.iloc[i]
        g = scenario_capture
        lo, hi = ctx.cfg.operator.operated_share
        pi = float(c["pi_mean"])
        return {"route": route, "stretch_id": stretch_id, "label": stretch_label(route, stretch_id), "hour": hour, "day": day,
                "level": level_json(int(c["level"])),
                "tier": c["tier"], "robust_in_range": bool(c["robust_in_range"]), "pi": pi,
                "pi_range": [float(c["pi_lo_draws"]), float(c["pi_hi_draws"])], "buses_per_hour": float(c["N"]),
                "effective_tickets": float(c["n_tickets_eff"]), "route_coverage": float(c["cov_route"]),
                "seats_per_bus": float(c["seats"]), "flags": c["flags"],
                "scenario_passengers_per_seat": [round(pi * g / hi, 1), round(pi * g / lo, 1)],
                "scenario_note": "Scenario, not measured."}

    @app.get("/examples")
    def examples() -> list[dict]:
        """Example trips from config, resolved to stop ids."""
        out = []
        for ex in ctx.cfg.demo.examples:
            a, b = planner.stops.search(ex["from"], 1), planner.stops.search(ex["to"], 1)
            if a and b:
                out.append({"from": a[0], "to": b[0], "time": ex["time"]})
        return out

    @app.get("/gates")
    def gates() -> list[dict]:
        if not st.exists("gates.json"):
            raise HTTPException(404, "run `python -m crowd gates` first")
        return st.read_json("gates.json")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
    return app
