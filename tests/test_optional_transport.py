from pathlib import Path

import unified_map

ROWS = [
    dict(
        station="Bengaluru test monitor",
        latitude="12.97",
        longitude="77.59",
        pollutant_id="PM2.5",
        avg_value="42",
    )
]


def test_air_map_without_transport_file(monkeypatch):
    original = Path.open

    def missing(path, *args, **kwargs):
        if path.name == "transport_locations.csv":
            raise FileNotFoundError("Missing transport")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", missing)
    html, stations, skipped = unified_map.build_map(ROWS)
    assert (stations, skipped) == (1, 0)
    assert "Bengaluru test monitor" in html
    assert "42" in html
    assert "facilities=[]" in html.replace(" ", "")
    assert "Transport coverage unavailable or partial" in html


def test_air_map_with_invalid_transport_metadata(monkeypatch):
    original = Path.read_text

    def broken(path, *args, **kwargs):
        if path.name == "metadata.json":
            return "{invalid"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", broken)
    html, stations, skipped = unified_map.build_map(ROWS)
    assert (stations, skipped) == (1, 0)
    assert "Bengaluru test monitor" in html
    assert "constbounds=[]" in html.replace(" ", "")
