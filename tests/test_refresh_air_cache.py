"""The air-cache refresh script: fetch, cache, and report stations, using a fake client and a throwaway database."""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import refresh_air_cache  # noqa: E402

from data_store import AreaRepository  # noqa: E402


def record(station, lat, lon, pm):
    return dict(country="India", state="Haryana", city="Gurugram", station=station, last_update="10-11-2026 16:00:00",
                latitude=str(lat), longitude=str(lon), pollutant_id="PM2.5", min_value="1", max_value="400", avg_value=str(pm))


class FakeClient:
    def __init__(self, records):
        self.records, self.calls = records, []

    def fetch_records(self, state, city=""):
        self.calls.append((state, city))
        return self.records


@pytest.fixture
def repo(tmp_path):
    db = tmp_path / "areas.sqlite"
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE air_cache (query TEXT PRIMARY KEY,fetched_at TEXT,payload TEXT)")
    return AreaRepository(db)


def test_refresh_caches_the_records_under_state_and_city(repo):
    client = FakeClient([record("Vikas Sadan, Gurugram - HSPCB", 28.4501, 77.0263, 180), record("Sector-51, Gurugram - HSPCB", 28.4243, 77.0722, 210)])
    records, monitors = refresh_air_cache.refresh("Haryana", "Gurugram", client=client, repository=repo)
    assert client.calls == [("Haryana", "Gurugram")] and len(records) == 2 and {m["pm"] for m in monitors} == {180.0, 210.0}
    cached, stamp = repo.query_air("Haryana", "Gurugram")
    assert len(cached) == 2 and stamp
    with sqlite3.connect(repo.database) as c:  # the key the Flat Finder builder reads: state first, lower case
        assert json.loads(c.execute("SELECT query FROM air_cache").fetchone()[0]) == ["haryana", "gurugram"]


def test_an_empty_answer_is_an_error_not_a_silent_success(repo):
    with pytest.raises(RuntimeError, match="no records"):
        refresh_air_cache.refresh("Haryana", "Nowhere", client=FakeClient([]), repository=repo)


def test_a_missing_key_is_reported_before_any_network_call(monkeypatch, capsys):
    monkeypatch.delenv("DATA_GOV_API_KEY", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    assert refresh_air_cache.main(["Haryana", "Gurugram"]) == 2
    assert "DATA_GOV_API_KEY" in capsys.readouterr().err
