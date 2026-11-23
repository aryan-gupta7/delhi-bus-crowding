"""HTTP layer on the mini world: shapes the web page and the phone app rely on."""

import pytest
from fastapi.testclient import TestClient

from crowd.api.app import create_app


@pytest.fixture(scope="module")
def client(mini_ctx) -> TestClient:
    return TestClient(create_app(mini_ctx))


def test_stop_search_and_plan_shape(client):
    assert client.get("/healthz").json()["status"] == "ok"
    stops = client.get("/stops", params={"q": "Stop A"}).json()
    assert stops and stops[0]["name"] == "Stop A"
    plan = client.get("/plan", params={"from_stop": "0", "to_stop": "3", "time": "08:00"}).json()
    assert plan["period"] == "October 2026" and plan["usually"].startswith("Usually, based on October 2026")
    fastest = plan["cards"]["fastest"]
    stretch = fastest["legs"][0]["stretches"][0]
    assert {"tier", "robust_in_range", "shares", "flow", "minutes", "hour", "coords"} <= stretch.keys()
    assert "chip" in plan["leave_later"] and isinstance(plan["leave_later"]["offsets"], list)


def test_leave_later_offsets_are_replanned_and_never_claim_more_than_the_card_rule(client):
    plan = client.get("/plan", params={"from_stop": "0", "to_stop": "3", "time": "08:00"}).json()
    offsets = plan["leave_later"]["offsets"]
    assert [r["offset"] for r in offsets] == [10, 20, 30, 40, 50, 60]
    assert all({"depart", "level_code", "holds", "advantage_min"} <= r.keys() for r in offsets)
    chip = plan["leave_later"]["chip"]
    assert chip is None or (chip["holds"] and chip["offset"] <= 15)


def test_operator_endpoints(client):
    heat = client.get("/operator/heatmap", params={"limit": 3}).json()
    assert set(heat) >= {"routes", "grid", "coverage"} and len(heat["grid"][heat["routes"][0]]) == 24
    assert isinstance(client.get("/operator/overloaded").json(), list)
    assert isinstance(client.get("/operator/relief").json(), list)
    assert client.get("/operator/cell", params={"route": "R1UP", "stretch_id": 999, "hour": 8}).status_code == 404
    cell = client.get("/operator/cell", params={"route": "R1UP", "stretch_id": 2, "hour": 8}).json()
    assert cell["scenario_note"] == "Scenario, not measured." and len(cell["scenario_passengers_per_seat"]) == 2


def test_unknown_inputs_are_rejected_cleanly(client):
    assert client.get("/plan", params={"from_stop": "nope", "to_stop": "3"}).status_code == 404
    assert client.get("/plan", params={"from_stop": "0", "to_stop": "3", "day": "friday"}).status_code == 422
