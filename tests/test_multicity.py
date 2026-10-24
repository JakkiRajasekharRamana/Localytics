import json
import re
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import air_client as client
import app as module
from unified_map import build_map


def test_other_city_filters_and_map(monkeypatch):
    monkeypatch.setenv("DATA_GOV_API_KEY", "test-secret")
    monkeypatch.setattr(client.shutil, "which", lambda _: "/usr/bin/curl")
    row = dict(
        station="Pune monitor",
        latitude="18.52",
        longitude="73.85",
        city="Pune",
        state="Maharashtra",
        pollutant_id="PM2.5",
        avg_value="40",
    )

    def run(args, **kwargs):
        params = parse_qs(urlparse(json.loads(kwargs["input"].split(" = ", 1)[1])).query)
        assert params["filters[state]"] == ["Maharashtra"]
        assert params["filters[city]"] == ["Pune"]
        return SimpleNamespace(returncode=0, stdout=json.dumps({"total": 1, "records": [row]}))

    monkeypatch.setattr(client.subprocess, "run", run)
    html, count, skipped = build_map(client.fetch_records("Maharashtra", "Pune"))
    assert (count, skipped) == (1, 0)
    assert "18.52" in html and "73.85" in html and "Pune monitor" in html
    assert "Transport coverage unavailable or partial" in html


def test_no_city_selected_initially():
    page = module.app.test_client().get("/air-quality").get_data(as_text=True)
    assert re.search(r'<input[^>]*name="state"[^>]*value=""', page)
    assert re.search(r'<input[^>]*name="city"[^>]*value=""', page)
    html, _, _ = build_map([])
    assert "22.5937" in html and "78.9629" in html
    assert "28.6139" not in html
