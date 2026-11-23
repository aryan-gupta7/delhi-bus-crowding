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


def test_stop_list_before_typing_nearby_and_all(client):
    page = client.get("/stops", params={"limit": 3}).json()
    names = [s["name"] for s in page]
    assert len(page) == 3 and names == sorted(names, key=str.lower)
    assert client.get("/stops", params={"limit": 3, "offset": 3}).json()[0]["stop_id"] not in {s["stop_id"] for s in page}
    here = page[0]
    near = client.get("/stops/nearby", params={"lat": here["lat"], "lon": here["lon"], "limit": 2}).json()
    assert near[0]["stop_id"] == here["stop_id"] and near[0]["distance_m"] == 0
    every = client.get("/stops/all").json()
    assert every and len(every[0]) == 4 and len({row[1] for row in every}) == len(every)


def test_a_trip_with_no_service_still_has_the_full_plan_shape(client):
    """The app crashed on 'leave_later of undefined' when a trip had no service (here: against the only direction served)."""
    plan = client.get("/plan", params={"from_stop": "3", "to_stop": "0", "time": "08:00"}).json()
    assert plan["cards"] == {} and plan["message"]
    assert plan["leave_later"] == {"chip": None, "offsets": []} and plan["compared"] is None


@pytest.mark.parametrize("bad", ["25:99", "9:00", "24:00", "08:60", "noon"])
def test_a_departure_time_must_be_a_clock_time(client, bad):
    assert client.get("/plan", params={"from_stop": "0", "to_stop": "3", "time": bad}).status_code == 422
    assert client.get("/plan", params={"from_stop": "0", "to_stop": "3", "time": "23:59"}).status_code == 200


def _top_level_keys(body: str) -> set[str]:
    """Property names of a TypeScript object type body, ignoring nested object types and array element types."""
    keys, depth, token = set(), 0, ""
    for ch in body:
        if ch in "{[(<":
            depth += 1
        elif ch in "}])>":
            depth -= 1
        elif depth == 0 and ch == ":" and token.strip():
            keys.add(token.strip().rstrip("?"))
            token = ""
        elif depth == 0 and ch in ";,\n":
            token = ""
        elif depth == 0:
            token += ch
    return keys


def test_plan_json_has_every_key_the_phone_app_reads(client):
    """mobile/src/api/types.ts mirrors these shapes; the app crashed once on a key that was missing."""
    import re
    from pathlib import Path
    types = (Path(__file__).resolve().parents[1] / "mobile/src/api/types.ts").read_text()
    chunks = [c for c in types.split("export type ")[1:] if " = {" in c]
    declared = {c.split(" =")[0]: _top_level_keys(c[c.index("{") + 1:c.rindex("}")]) for c in chunks}
    optional = {"Plan": {"leave_later"}, "Card": {"robustness"}}
    for params in ({"from_stop": "0", "to_stop": "3"}, {"from_stop": "3", "to_stop": "0"}):    # served, and no service
        plan = client.get("/plan", params={**params, "time": "08:00"}).json()
        assert declared["Plan"] - optional["Plan"] <= plan.keys() and "leave_later" in plan
        for card in plan["cards"].values():
            assert declared["Card"] - optional["Card"] <= card.keys()
            for leg in card["legs"]:
                assert declared["Leg"] <= leg.keys()
                for stretch in leg["stretches"]:
                    assert declared["Stretch"] <= stretch.keys()
