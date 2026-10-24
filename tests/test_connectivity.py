from app import app
from connectivity.nearest import distance_km
from transport import search_transport, transport_map


def test_distance():
    assert distance_km(28, 77, 28, 77) == 0
    assert 110 < distance_km(0, 0, 1, 0) < 112


def test_search_sorted_and_radius():
    results = search_transport(28.6139, 77.2090, 5, 5)
    for places in results.values():
        distances = [p["distance_km"] for p in places]
        assert distances == sorted(distances)
        assert len(places) <= 5
        assert all(d <= 5 for d in distances)
    assert results["bus_stop"]
    assert results["metro_station"]
    html = transport_map(28.6139, 77.2090, results, 5)
    assert "tile.openstreetmap.org" in html
    assert "Bus stops" in html


def test_routes():
    client = app.test_client()
    assert client.get("/connectivity").status_code == 200
    response = client.post(
        "/connectivity", data=dict(latitude="28.6139", longitude="77.2090", radius="5", limit="5")
    )
    assert response.status_code == 200
    assert b"iframe" in response.data
    assert b"Distance (km)" in response.data


def test_invalid_input():
    client = app.test_client()
    for lat in ["bad", "nan", "91"]:
        response = client.post(
            "/connectivity", data=dict(latitude=lat, longitude="77.2", radius="5", limit="5")
        )
        assert b"Enter valid coordinates" in response.data
