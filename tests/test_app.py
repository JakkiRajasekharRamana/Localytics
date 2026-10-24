import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

import air_client as client
import app as module
from unified_map import build_map


def row(value="87"):
    return {
        "station": "Test station",
        "city": "Delhi",
        "state": "Delhi",
        "latitude": "28.6",
        "longitude": "77.2",
        "pollutant_id": "PM2.5",
        "avg_value": value,
        "last_update": "16-10-2026 14:00:00",
    }


def test_initial_and_missing_key(monkeypatch):
    monkeypatch.delenv("DATA_GOV_API_KEY", raising=False)
    client = module.app.test_client()
    assert client.get("/air-quality").status_code == 200
    page = client.post("/air-quality", data={"state": "Delhi", "city": "Delhi"})
    assert b"Set DATA_GOV_API_KEY" in page.data


def test_pagination_uses_actual_batch_size(monkeypatch):
    monkeypatch.setenv("DATA_GOV_API_KEY", "test-secret")
    monkeypatch.setattr(client.shutil, "which", lambda _: "/usr/bin/curl")
    offsets = []

    def run(args, **kwargs):
        url = json.loads(kwargs["input"].split(" = ", 1)[1])
        offset = int(parse_qs(urlparse(url).query)["offset"][0])
        offsets.append(offset)
        batch = [dict(row(), station=str(offset))] if offset < 3 else []
        return SimpleNamespace(returncode=0, stdout=json.dumps({"total": 3, "records": batch}))

    monkeypatch.setattr(client.subprocess, "run", run)
    assert len(client.fetch_records("Delhi", "Delhi")) == 3
    assert offsets == [0, 1, 2]


def test_repeated_page_rejected(monkeypatch):
    monkeypatch.setenv("DATA_GOV_API_KEY", "test-secret")
    monkeypatch.setattr(client.shutil, "which", lambda _: "/usr/bin/curl")
    monkeypatch.setattr(
        client.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(
            returncode=0, stdout=json.dumps({"total": 3, "records": [row()]})
        ),
    )
    with pytest.raises(client.FetchError, match="repeated"):
        client.fetch_records("Delhi", "Delhi")


def test_map_and_post(monkeypatch):
    rows = [row(), dict(row("NA"), pollutant_id="CO"), dict(row(), latitude="nan")]
    html, count, skipped = build_map(rows)
    assert (count, skipped) == (1, 1)
    assert "tile.openstreetmap.org" in html
    assert "Moderate" in html
    assert "CO" in html
    monkeypatch.setattr(client, "fetch_records", lambda *a: rows)
    response = module.app.test_client().post(
        "/air-quality", data={"state": "Delhi", "city": "Delhi"}
    )
    assert response.status_code == 200
    assert b"iframe" in response.data


def test_missing_value_grey():
    html, _, _ = build_map([row("NA")])
    assert "#808080" in html
    assert "No PM2.5 data" in html


def test_no_results(monkeypatch):
    monkeypatch.setattr(client, "fetch_records", lambda *a: [])
    response = module.app.test_client().post("/air-quality", data={"state": "Delhi"})
    assert b"No matching records" in response.data
