"""FastAPI app: planner, ride query and operator view endpoints plus the static web page."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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
        return planner.plan(from_stop, to_stop, time, check_day(day))

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
            grid[row.route][row.hour] = {"level": level_json(int(row.level_worst_stretch)),
                                         "robust_in_range": bool(row.robust_in_range), "tier": row.tier}
        return {"day": day, "routes": list(routes), "grid": grid}

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
            props = {**f["properties"], "level": level_json(level)}
            if i is not None:
                props.update(tier=cells.at[i, "tier"], robust_in_range=bool(cells.at[i, "robust_in_range"]),
                             pi=round(float(cells.at[i, "pi_central"]), 4), buses_per_hour=float(cells.at[i, "N"]))
            out.append({"type": "Feature", "properties": props, "geometry": f["geometry"]})
        return {"type": "FeatureCollection", "features": out}

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
