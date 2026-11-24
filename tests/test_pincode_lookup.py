import json

import pytest

import school_profiles as sp
from app import app
from scripts.build_pincode_boundaries import main as build_boundaries
from scripts.build_pincode_boundaries import parse

SQUARE = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
HOLE = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]

KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
<Placemark><ExtendedData><SchemaData>
<SimpleData name="PT_ID">1</SimpleData><SimpleData name="PINCODE">110001</SimpleData></SchemaData></ExtendedData>
<Polygon><outerBoundaryIs><LinearRing><coordinates>77.0,28.0,0 77.1,28.0,0 77.1,28.1,0 77.0,28.1,0 77.0,28.0,0</coordinates></LinearRing></outerBoundaryIs>
<innerBoundaryIs><LinearRing><coordinates>77.04,28.04,0 77.06,28.04,0 77.06,28.06,0 77.04,28.06,0 77.04,28.04,0</coordinates></LinearRing></innerBoundaryIs></Polygon></Placemark>
</Document></kml>"""


def boundary(pincode, rings, bbox):
    return dict(pincode=pincode, bbox=bbox, polygons=[rings])


def test_in_polygon_with_hole():
    assert sp.in_polygon([SQUARE], 5, 5)
    assert not sp.in_polygon([SQUARE], 11, 5)
    assert not sp.in_polygon([SQUARE, HOLE], 5, 5)
    assert sp.in_polygon([SQUARE, HOLE], 2, 2)


def test_pincode_at_prefers_smaller_overlap_and_handles_misses():
    big = boundary("110001", [SQUARE], [0, 0, 10, 10])
    small = boundary("110002", [[[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]]], [1, 1, 3, 3])
    assert sp.pincode_at([big, small], lat=2, lon=2) == "110002"
    assert sp.pincode_at([big, small], lat=8, lon=8) == "110001"
    assert sp.pincode_at([big, small], lat=20, lon=20) is None


def test_build_boundaries(tmp_path):
    kml = tmp_path / "a.kml"
    kml.write_text(KML, encoding="utf-8")
    parsed = parse(kml)
    assert [p["pincode"] for p in parsed] == ["110001"]
    assert len(parsed[0]["polygons"][0]) == 2  # outer ring plus one hole
    assert parsed[0]["bbox"] == [77.0, 28.0, 77.1, 28.1]
    build_boundaries([str(kml), "--output", str(tmp_path / "out")])
    data = json.loads((tmp_path / "out" / "pincode_boundaries.json").read_text(encoding="utf-8"))
    assert data["metadata"]["pincode_count"] == 1 and "India Post" in data["metadata"]["credit"]
    assert sp.pincode_at(data["pincodes"], 28.02, 77.02) == "110001"
    assert sp.pincode_at(data["pincodes"], 28.05, 77.05) is None  # inside the hole


def test_build_boundaries_rejects_entities_and_bad_input(tmp_path):
    bad = tmp_path / "b.kml"
    bad.write_text('<!DOCTYPE x [<!ENTITY e "boom">]>' + KML, encoding="utf-8")
    with pytest.raises(ValueError, match="DTD"):
        parse(bad)
    bad.write_text(KML.replace("110001", "11000"), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid pincode"):
        parse(bad)
    bad.write_text(
        KML.replace(
            "77.0,28.0,0 77.1,28.0,0 77.1,28.1,0 77.0,28.1,0 77.0,28.0,0",
            "77.0,28.0,0 77.1,28.0,0 77.1,28.1,0",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not closed"):
        parse(bad)


@pytest.fixture
def bundled():
    boundaries, profiles = sp.load_boundaries(), sp.load_profiles()
    if boundaries is None or profiles is None:
        pytest.skip("schools/pincode_boundaries.json or pincode_profiles.json has not been built")
    return boundaries, profiles


def test_bundled_boundaries(bundled):
    boundaries, profiles = bundled
    assert len(boundaries) == 92
    assert len({b["pincode"] for b in boundaries}) == 92
    for b in boundaries:
        west, south, east, north = b["bbox"]
        assert 76.8 < west < east < 77.4 and 28.4 < south < north < 28.9
        assert all(rings[0][0] == rings[0][-1] for rings in b["polygons"])
    school_pins = {p["pincode"] for p in profiles["pincodes"]}
    assert len(school_pins & {b["pincode"] for b in boundaries}) >= 90
    # landmarks well inside their pincode areas
    assert sp.pincode_at(boundaries, 28.6315, 77.2167) == "110001"  # Connaught Place
    assert sp.pincode_at(boundaries, 28.6562, 77.2410) == "110006"  # Red Fort
    assert sp.pincode_at(boundaries, 19.07, 72.88) is None  # Mumbai


def test_lookup_route(bundled):
    client = app.test_client()
    page = client.get("/schools/lookup?lat=28.6315&lon=77.2167")
    assert page.status_code == 200
    for text in [
        b"Pincode <b>110001</b>",
        b"Who runs the schools",
        b"/schools/110001",
        b"A profile, not a score",
        b"CC BY-SA",
    ]:
        assert text in page.data
    assert (
        b"outside the Delhi pincode boundaries"
        in client.get("/schools/lookup?lat=19.07&lon=72.88").data
    )
    for query in ["", "?lat=28.6", "?lat=abc&lon=77.2", "?lat=nan&lon=77.2", "?lat=95&lon=77.2"]:
        response = client.get("/schools/lookup" + query)
        assert response.status_code == 400 and b"Could not read" in response.data


def test_lookup_route_is_not_a_pincode(bundled):
    # /schools/lookup must hit the lookup view, not the /schools/<pincode> 404 page
    assert (
        b"No school profile for pincode"
        not in app.test_client().get("/schools/lookup?lat=28.63&lon=77.21").data
    )


def test_lookup_no_schools_and_missing_data(monkeypatch, bundled):
    boundaries, profiles = bundled
    pincode = boundaries[0]["pincode"]
    trimmed = dict(profiles, pincodes=[p for p in profiles["pincodes"] if p["pincode"] != pincode])
    monkeypatch.setattr(sp, "load_profiles", lambda: trimmed)
    west, south, east, north = boundaries[0]["bbox"]
    inside = [
        (la, lo)
        for la in (south + (north - south) * f / 10 for f in range(1, 10))
        for lo in (west + (east - west) * g / 10 for g in range(1, 10))
        if sp.pincode_at(boundaries, la, lo) == pincode
    ]
    assert inside
    lat, lon = inside[0]
    assert (
        f"Pincode {pincode} has no schools".encode()
        in app.test_client().get(f"/schools/lookup?lat={lat}&lon={lon}").data
    )
    monkeypatch.setattr(sp, "load_boundaries", lambda: None)
    assert b"not built yet" in app.test_client().get("/schools/lookup?lat=28.63&lon=77.21").data


def test_map_page_wiring():
    from unified_map import build_map

    client = app.test_client()
    page = client.get("/air-quality").data
    assert b'id="school-profile"' in page and b"school_profile.js" in page
    assert b"LocalyticsSchools.load" in client.get("/static/index.js").data
    assert b"/schools/lookup?" in client.get("/static/school_profile.js").data
    html, _, _ = build_map([])
    assert "lat: point.lat" in html and "lon: point.lon" in html


def test_areas_page_wiring():
    client = app.test_client()
    assert b"school_profile.js" in client.get("/").data
    assert b"LocalyticsSchools.load" in client.get("/static/areas.js").data


def test_detail_page_flags_pincode_without_boundary(monkeypatch, bundled):
    boundaries, profiles = bundled
    boundary_pins = {b["pincode"] for b in boundaries}
    missing = [p["pincode"] for p in profiles["pincodes"] if p["pincode"] not in boundary_pins]
    assert missing, "expected at least one school pincode without a boundary"
    client = app.test_client()
    assert b"no boundary in the pincode map file" in client.get("/schools/" + missing[0]).data
    present = next(iter(boundary_pins & {p["pincode"] for p in profiles["pincodes"]}))
    assert b"no boundary in the pincode map file" not in client.get("/schools/" + present).data
