import copy
from datetime import datetime, timedelta, timezone

import areas
import clustering
import data_store
from app import app
from osm_data import classify


def test_extract_categories_and_access():
    assert classify({"amenity": "school"}) == "school"
    assert classify({"healthcare": "hospital"}) == "hospital"
    assert classify({"leisure": "park", "access": "private"}) is None
    assert classify({"amenity": "charging_station", "access": "customers"}) is None
    assert classify({"shop": "mall"}) == "mall"
    assert classify({"leisure": "fitness_centre"}) == "gym"


def test_grid_and_data_integrity():
    cells, meta = data_store.dataset()
    assert meta["cell_count"] == len(cells) > 100
    assert len({c["id"] for c in cells}) == len(cells)
    assert 1300 < meta["boundary_area_km2"] < 1700
    assert meta["overlap_removed"] > 0
    assert meta["counts"]["school"] > 0
    assert all("2" in c["features"] for c in cells)


def test_scoring_directions_and_missing():
    f = dict(coverage=True, nearest_km=0, count=10)
    assert areas.service_score(f, 2) == 1
    f["nearest_km"] = 1
    assert areas.service_score(f, 2) == 0.75
    f.update(nearest_km=3, count=0)
    assert areas.service_score(f, 2) == 0
    f["coverage"] = False
    assert areas.service_score(f, 2) is None


def test_weights_constraints_and_no_imputation():
    cell = copy.deepcopy(data_store.dataset()[0][0])
    cell["features"]["2"]["park"] = dict(coverage=True, count=10, nearest_km=0, nearby=[])
    cell["features"]["2"]["hospital"] = dict(coverage=True, count=0, nearest_km=5, nearby=[])
    r = areas.evaluate(cell, {"park": 3, "hospital": 1})
    assert r["score"] == 75
    assert sum(r["contributions"].values()) == 75
    # Disabled EV never penalises a user.
    cell["features"]["2"]["ev"]["coverage"] = False
    assert areas.evaluate(cell, {"park": 3, "hospital": 1})["score"] == 75
    assert areas.evaluate(cell, {"park": 3, "ev": 1})["score"] is None
    r = areas.evaluate(cell, {"park": 1}, must={"hospital": 1})
    assert r["score"] is None and r["checks"][0]["status"] == "fail"
    cell["features"]["2"]["hospital"]["coverage"] = False
    assert (
        areas.evaluate(cell, {"park": 1}, must={"hospital": 1})["checks"][0]["status"]
        == "unverified"
    )


def test_air_age_distance_and_indicator():
    now = datetime.now(timezone.utc)
    cell = {"lat": 28.6, "lon": 77.2}
    s = dict(name="monitor", lat=28.6, lon=77.2, readings=[], pm=50, stamp=now - timedelta(hours=1))
    assert areas.nearest_air(cell, [s], now)["score"] == 0.8
    s["stamp"] = now - timedelta(hours=7)
    assert areas.nearest_air(cell, [s], now)["score"] is None
    s.update(stamp=now, lat=29.6)
    assert areas.nearest_air(cell, [s], now)["score"] is None


def test_routes_and_validation():
    client = app.test_client()
    response = client.get("/areas")
    assert response.status_code == 200
    assert b"Your shortlist" in response.data
    assert b"School quality" in response.data
    assert b"1487" in response.data
    cell = data_store.dataset()[0][0]["id"]
    r = client.get("/api/areas/" + cell).get_json()
    assert r["id"] == cell and "school" in r["features"]
    assert client.get("/api/areas/unknown").status_code == 404
    assert client.get("/api/areas/" + cell + "?w_park=nan").status_code == 400
    assert client.get("/api/areas/" + cell + "?radius=3").status_code == 400
    assert client.get("/api/areas/" + cell + "?w_workplace=3").status_code == 400
    assert client.get("/api/areas/" + cell + "?must_school=10").status_code == 400
    assert client.get("/areas/export.csv").status_code == 200
    assert b"suitability_score" in client.get("/areas/export.csv").data


def test_cache_and_no_cross_city_mix(tmp_path, monkeypatch):
    import sqlite3

    db = tmp_path / "areas.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE air_cache(query TEXT PRIMARY KEY,fetched_at TEXT,payload TEXT)")
    monkeypatch.setattr(data_store, "DB", db)
    data_store.cache_air("Maharashtra", "Pune", [{"city": "Pune"}])
    assert data_store.air_records() == ([], None)
    data_store.cache_air("Delhi", "", [{"city": "Delhi"}])
    assert data_store.air_records()[0] == [{"city": "Delhi"}]


def test_cluster_is_separate_from_ranking():
    cells, _ = data_store.dataset()
    before = areas.evaluate(cells[0], {"park": 1})
    model = clustering.clustering()
    assert model["available"]
    assert len(model["labels"]) == len(cells)
    assert len(model["trials"]) >= 2
    assert model["stability_repeats"] == 5
    assert -1 <= model["stability"] <= 1
    assert areas.evaluate(cells[0], {"park": 1}) == before
    assert app.test_client().get("/areas?clusters=1").status_code == 200


def test_air_refresh_failure_keeps_cache(monkeypatch):
    import air_client as app_module

    # The registered view closes over the original fetch function, whose raw request is replaceable.
    before = data_store.air_records()

    def failing(*args):
        raise app_module.FetchError("Offline test")

    monkeypatch.setattr(app_module, "_fetch_records", failing)
    result = app.test_client().post("/areas/refresh-air")
    assert result.status_code == 302 and "air_error" in result.location
    assert data_store.air_records() == before


def test_boundary_reference_contains_delhi_not_other_cities():
    import json

    from shapely.geometry import Point, shape
    from shapely.ops import unary_union

    features = json.loads(data_store.DB.with_name("delhi_boundary.geojson").read_text())["features"]
    boundary = unary_union([shape(f["geometry"]) for f in features])
    assert boundary.covers(Point(77.209, 28.614))
    assert not boundary.covers(Point(73.85, 18.52))
    assert not boundary.covers(Point(77.59, 12.97))


def test_pm25_indicator_direction_and_cap():
    now = datetime.now(timezone.utc)
    cell = {"lat": 28.6, "lon": 77.2}
    station = dict(name="PM monitor", lat=28.6, lon=77.2, readings=[], pm=25, stamp=now)
    assert areas.nearest_air(cell, [station], now)["score"] == 0.9
    station["pm"] = 125
    assert areas.nearest_air(cell, [station], now)["score"] == 0.5
    station["pm"] = 300
    assert areas.nearest_air(cell, [station], now)["score"] == 0
    station["stamp"] = now + timedelta(hours=1)
    assert areas.nearest_air(cell, [station], now)["score"] is None


def test_pm25_slider_enabled_and_contributes(monkeypatch):
    import re
    from zoneinfo import ZoneInfo

    cell = data_store.dataset()[0][0]
    stamp = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d-%m-%Y %H:%M:%S")
    record = dict(
        station="PM test",
        latitude=str(cell["lat"]),
        longitude=str(cell["lon"]),
        pollutant_id="PM2.5",
        avg_value="50",
        last_update=stamp,
    )
    monkeypatch.setattr(data_store, "air_records", lambda: ([record], None))
    client = app.test_client()
    page = client.get("/areas?w_air=5").get_data(as_text=True)
    slider = re.search(r'<input[^>]+id="w_air"[^>]*>', page).group()
    assert "disabled" not in slider
    assert 'value="5"' in slider
    assert "not official AQI" in page
    r = client.get("/api/areas/" + cell["id"] + "?w_air=5").get_json()
    assert r["scores"]["air"] == 0.8
    assert r["contributions"]["air"] > 0
    assert r["score"] is not None
    assert r["air"]["scoring_value"] == 50
    assert client.get("/api/areas/" + cell["id"] + "?w_air=0").get_json()["score"] != r["score"]
