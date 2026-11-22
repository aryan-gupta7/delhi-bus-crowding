"""Checks against the real October files (slow): ``uv run pytest -m data``."""

import numpy as np
import pytest

from crowd import gates, stages
from crowd.config import Config
from crowd.index import hour_profile_z
from crowd.pipeline import Context
from crowd.store import Store
from tests.conftest import ROOT

pytestmark = pytest.mark.data


@pytest.fixture(scope="module")
def ctx() -> Context:
    cfg = Config.load(ROOT / "config.yaml")
    store = Store(cfg.path("out"))
    if not store.exists("crowding_cells.parquet"):
        pytest.skip("run `make all` first")
    return Context(cfg=cfg, store=store)


def test_ticket_totals(ctx):
    report = ctx.store.read_json("ingest_report.json")
    assert report["rows_out"] == 2_559_899 and report["total_pax"] == 2_753_606
    assert abs(report["null_vehicle_share"] - 0.485) < 0.001


def test_hour_tilt_basis_matches_the_calibrated_grid(ctx):
    z = hour_profile_z(ctx.store.read_table("counts.parquet"), "weekday")
    assert abs((z[9] - z[13]) - 2.9) < 0.1


def test_eligibility_reproduces_the_october_anomalies(ctx):
    assert gates.g1_eligibility(ctx)["passed"]


def test_all_trips_map_onto_their_canonical_pattern(ctx):
    assert ctx.store.read_table("route_info.parquet")["n_unmapped"].sum() == 0


def test_route_names_match_gtfs_for_nearly_all_volume(ctx):
    geo, df = stages.geometry(ctx), stages.tickets(ctx)
    share = df.loc[geo.route_ix(df["route"]) >= 0, "pax"].sum() / df["pax"].sum()
    assert share > 0.98
