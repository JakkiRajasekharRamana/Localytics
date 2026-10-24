from app import app
from unified_map import build_map


def test_combined_map():
    rows = [
        {
            "station": "Example",
            "latitude": "28.61",
            "longitude": "77.20",
            "pollutant_id": "PM2.5",
            "avg_value": "50",
            "last_update": "17-10-2026 12:00:00",
        }
    ]
    html, n, skipped = build_map(rows)
    assert (n, skipped) == (1, 0)
    for text in [
        "Connectivity (outer rings)",
        "Air quality (inner dots)",
        "Air-quality observations",
        "Metro stations",
        "Airport terminals",
        "Example",
    ]:
        assert text in html


def test_unified_home():
    response = app.test_client().get("/air-quality")
    assert response.status_code == 200
    assert b"iframe" in response.data


def test_bad_coordinates_and_no_air():
    html, n, skipped = build_map([{"latitude": "nan", "longitude": "77"}])
    assert (n, skipped) == (0, 1)
    assert "No loaded air-quality readings" in html


def test_sidebar_markup_and_selection_bridge():
    response = app.test_client().get("/air-quality")
    assert b'id="selection-details"' in response.data
    assert b"LOCATION INSIGHTS" in response.data
    assert b"event.source !== frame.contentWindow" in app.test_client().get("/static/index.js").data
    html, _, _ = build_map([])
    assert "localytics:selection" in html
    assert "L.popup({maxWidth:550" not in html
    assert "inspect(lastSelection.point, lastSelection.exact)" in html
