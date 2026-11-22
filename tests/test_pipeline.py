"""Stage runner, manifest determinism and the ride query on the mini world."""

from crowd import stages
from crowd.outputs import CrowdingTable, StopResolver, query
from crowd.pipeline import run, write_manifest
from crowd.stages import STAGES

RUNNABLE = [s for s in STAGES if s.name != "gates"]


def test_up_to_date_stages_are_skipped(mini_ctx):
    assert run(RUNNABLE, mini_ctx) == {}


def test_forced_rerun_reproduces_every_output_hash(mini_ctx):
    first = write_manifest(RUNNABLE, mini_ctx, {}, {})["reproducibility_hash"]
    run(RUNNABLE, mini_ctx, force=True)
    mini_ctx.cache.clear()
    second = write_manifest(RUNNABLE, mini_ctx, {}, {})["reproducibility_hash"]
    assert first == second


def test_query_says_no_estimate_for_cells_without_evidence(mini_ctx):
    """R1UP runs at 06:00 but no ticket was sold then: every stretch must read "No estimate"."""
    cells = mini_ctx.store.read_table("crowding_cells.parquet")
    table = CrowdingTable.load(cells, mini_ctx.store.read_array("levels.npy"))
    geo = stages.geometry(mini_ctx)
    ride = query(table, geo, StopResolver(geo, mini_ctx.cfg), "R1UP", "Stop A", "Stop D", "06:10")
    assert ride["stretches"] and {s["level"] for s in ride["stretches"]} == {"No estimate"}


def test_query_returns_levels_for_each_stretch_of_a_ride(mini_ctx):
    table = CrowdingTable.load(mini_ctx.store.read_table("crowding_cells.parquet"), mini_ctx.store.read_array("levels.npy"))
    geo = stages.geometry(mini_ctx)
    out = query(table, geo, StopResolver(geo, mini_ctx.cfg), "R1UP", "Stop A", "Stop D", "08:30")
    assert [s["stretch_id"] for s in out["stretches"]] == [0, 1, 2]
    assert all(s["level"] in {"Lighter", "Busy", "Very busy", "No estimate"} for s in out["stretches"])
    assert "error" in query(table, geo, StopResolver(geo, mini_ctx.cfg), "R1UP", "Stop D", "Stop A", "08:30")
