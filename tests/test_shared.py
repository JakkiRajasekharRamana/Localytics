"""Regression checks for the shared parsers and refactored route/assets boundary."""

import html
import json
import re

from app import app
from geography import consolidate_named, covered_radius
from observations import group_monitors
from osm_data import classify_transport, extract_sources


def test_latest_missing_pm_does_not_reuse_an_older_value():
    common = dict(station="Monitor", latitude="28.6", longitude="77.2", pollutant_id="PM2.5")
    stations, skipped = group_monitors(
        [
            dict(common, avg_value="20", last_update="24-10-2026 09:00:00"),
            dict(common, avg_value="NA", last_update="24-10-2026 10:00:00"),
            dict(common, latitude="nan", avg_value="50"),
        ]
    )
    assert skipped == 1
    assert stations[0]["pm"] is None
    assert stations[0]["stamp"].hour == 10


def test_named_deduplication_and_partial_coverage():
    rows = [
        dict(category="school", name="School", lat=28.6, lon=77.2),
        dict(category="school", name="school", lat=28.60001, lon=77.2),
        dict(category="school", name="Unnamed", lat=28.6, lon=77.2),
        dict(category="school", name="Unnamed", lat=28.6, lon=77.2),
    ]
    assert len(consolidate_named(rows)) == 3
    assert covered_radius(28.6, 77.2, 2, [[77, 28, 78, 29]])
    assert not covered_radius(28.6, 77.001, 2, [[77, 28, 78, 29]])


def test_home_and_external_assets():
    client = app.test_client()
    page = client.get("/").get_data(as_text=True)
    assert "Your priorities" in page
    config = json.loads(
        re.search(r'<script[^>]*id="area-config"[^>]*>(.*?)</script>', page, re.S).group(1)
    )
    assert len(config["geojson"]["features"]) == 1487
    assert config["preferences"]["radius"] == 2
    assert "/air-quality" in page
    for name in ["areas.js", "shared.js", "index.js", "areas.css", "index.css", "connectivity.css"]:
        response = client.get("/static/" + name)
        assert response.status_code == 200
        assert "{%" not in response.get_data(as_text=True)
    station_page = html.unescape(client.get("/air-quality").get_data(as_text=True))
    assert "/static/shared.js" in station_page
    assert "repaint();" in station_page


def test_shared_osm_extraction_preserves_versions_and_overlap(tmp_path):
    def fixture(filename, version, lat):
        path = tmp_path / filename
        path.write_text(f'''<?xml version="1.0"?><osm version="0.6" generator="test">
        <bounds minlat="28" minlon="77" maxlat="29" maxlon="78"/>
        <node id="1" version="{version}" lat="{lat}" lon="77.2" timestamp="2026-10-24T00:00:00Z">
        <tag k="name" v="A stop"/><tag k="highway" v="bus_stop"/></node></osm>''')
        return path

    first = fixture("first.osm", 1, 28.6)
    second = fixture("second.osm", 2, 28.7)
    rows, meta = extract_sources([first, second], classify_transport, consolidate=False)
    assert len(rows) == 1
    assert rows[0]["version"] == 2
    assert rows[0]["lat"] == 28.7
    assert rows[0]["sources"] == ["first.osm", "second.osm"]
    assert meta["overlap_removed"] == 1
    assert meta["source_feature_counts"] == {"first.osm": 1, "second.osm": 1}
