import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import refresh_air_openaq as oa  # noqa: E402

NOW = datetime(2026, 11, 24, 15, 0, tzinfo=timezone.utc)
IN_DELHI = lambda lat, lon: lat > 28.5  # noqa: E731  (a stand-in for the real boundary polygon)


def loc(id_, name, lat, lon, sensors, monitor=True):
    return dict(id=id_, name=name, isMonitor=monitor, coordinates=dict(latitude=lat, longitude=lon),
                sensors=[dict(id=sid, name=f"{p} {u}", parameter=dict(id=1, name=p, units=u)) for sid, p, u in sensors])


def hours(values, last_end="2026-11-24T14:00:00Z"):
    """Hourly rows, oldest first, the last one ending at last_end (like OpenAQ's /sensors/{id}/hours)."""
    end = datetime.fromisoformat(last_end.replace("Z", "+00:00"))
    rows = []
    for i, v in enumerate(reversed(values)):
        to = end - timedelta(hours=i)
        rows.append(dict(value=v, period=dict(datetimeFrom=dict(utc=(to - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")), datetimeTo=dict(utc=to.strftime("%Y-%m-%dT%H:%M:%SZ")))))
    return list(reversed(rows))


LOCATIONS = [
    loc(1, "Sector-51, Gurugram - HSPCB", 28.4243, 77.0722, [(11, "pm25", "µg/m³"), (12, "pm10", "µg/m³")]),
    loc(2, "Vikas Sadan, Gurugram - HSPCB", 28.4501, 77.0263, [(21, "pm25", "µg/m³")]),
    loc(3, "Only ozone", 28.40, 77.00, [(31, "o3", "ppb")]),
    loc(4, "Mostly silent monitor", 28.38, 77.05, [(41, "pm25", "µg/m³")]),
    loc(5, "Wrong unit", 28.37, 77.06, [(51, "pm25", "ppm")]),
    loc(6, "Cheap sensor, Sector 62", 28.40, 77.08, [(61, "pm25", "µg/m³")], monitor=False),  # AirGradient / Clarity type: not a government monitor
    loc(7, "JNU, Delhi - DPCC", 28.5407, 77.1685, [(71, "pm25", "µg/m³")]),
    loc(8, "Anand Vihar, Delhi - DPCC", 28.6469, 77.3160, [(81, "pm25", "µg/m³")]),
    loc(9, "Raw-only, Delhi - DPCC", 28.6100, 77.2000, [(91, "pm25", "µg/m³")]),
]
# Sector-51's real day: 75-140 for most hours, then an evening spike. Its latest hour (400) must not be what we store.
SECTOR51 = [76] * 6 + [135] * 8 + [90] * 4 + [300, 325, 403, 383]  # 22 hours
HOURS = {
    11: hours(SECTOR51 + [100, 100]),  # 24 hours
    21: hours([147] * 24),
    41: hours([90] * 5),  # only 5 of 24 hours: not an average
    51: hours([0.1] * 24),
    61: hours([50] * 24),
    71: hours([128.4] * 24),
    81: hours([260] * 23 + [None]),  # one missing hour is fine
}


# a station with raw 15-minute readings but no hourly roll-up (some DPCC stations): 4 readings an hour for 24 hours
RAW = {91: [r for h in hours([110] * 24) for r in (dict(h), dict(h), dict(h), dict(h))]}


def fake_get(path, params, key):
    assert key == "k"
    if path == "/locations":
        return {"results": LOCATIONS if params["page"] == 1 else []}
    sensor = int(path.split("/")[2])
    if path.endswith("/hours"):
        return {"results": HOURS.get(sensor, [])}
    assert path.endswith("/measurements"), path
    return {"results": RAW.get(sensor, [])}


def test_gurugram_side_records_look_like_data_gov_in_rows_and_skip_unusable_stations():
    delhi, haryana = oa.fetch_records("k", get=fake_get, now=NOW, in_delhi=IN_DELHI)
    # no pm25 sensor, too few hours, wrong unit and the low-cost (not a government monitor) sensor are all left out
    assert sorted(r["station"] for r in haryana) == ["Sector-51, Gurugram - HSPCB", "Vikas Sadan, Gurugram - HSPCB"]
    sector = next(r for r in haryana if r["station"].startswith("Sector"))
    mean = sum(SECTOR51 + [100, 100]) / 24
    assert sector["avg_value"] == str(round(mean, 1)) and 140 < mean < 160  # the 24-hour mean, not the 383-403 evening spike
    assert sector["max_value"] == "403" or sector["max_value"] == "403.0"
    assert sector["pollutant_id"] == "PM2.5" and sector["state"] == "Haryana" and sector["hours_used"] == 24
    assert sector["last_update"] == "24-11-2026 19:30:00"  # the last hour ends 14:00 UTC = 19:30 in India
    assert sector["latitude"] == "28.4243" and sector["longitude"] == "77.0722"


def test_delhi_stations_are_split_off_by_the_boundary_and_come_from_the_same_fetch():
    delhi, haryana = oa.fetch_records("k", get=fake_get, now=NOW, in_delhi=IN_DELHI)
    assert sorted(r["station"] for r in delhi) == ["Anand Vihar, Delhi - DPCC", "JNU, Delhi - DPCC", "Raw-only, Delhi - DPCC"]
    assert all(r["state"] == "Delhi" for r in delhi) and not any("Delhi" in r["station"] for r in haryana)


def test_records_are_read_by_the_existing_monitor_parser():
    from observations import group_monitors

    delhi, haryana = oa.fetch_records("k", get=fake_get, now=NOW, in_delhi=IN_DELHI)
    monitors, skipped = group_monitors(delhi + haryana)
    assert skipped == 0 and all(m["stamp"] is not None for m in monitors)
    assert sorted(round(m["pm"]) for m in monitors) == [110, 128, 146, 147, 260]


def test_refresh_caches_the_two_cities_under_separate_keys():
    stored = {}

    class Repo:
        def cache_air(self, state, city, records):
            stored[(state, city)] = len(records)
            return True

    delhi, haryana, monitors = oa.refresh("k", repository=Repo(), get=fake_get, now=NOW, in_delhi=IN_DELHI)
    assert stored == {("Haryana", "Gurugram"): 2, ("Delhi", "openaq"): 3}  # Delhi's own data.gov.in cache is left alone
    assert len(monitors) == 5


def test_nothing_recent_is_an_error_not_an_empty_cache():
    with pytest.raises(oa.OpenAQError, match="no government PM2.5 monitor"):
        oa.refresh("k", repository=object(), get=lambda p, q, k: {"results": []}, now=NOW, in_delhi=IN_DELHI)


def test_missing_key_exits_2(monkeypatch, capsys):
    monkeypatch.delenv("OPENAQ_API_KEY", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    assert oa.main([]) == 2
    assert "OPENAQ_API_KEY is not set" in capsys.readouterr().err


def test_the_real_delhi_boundary_separates_the_cities():
    inside = oa.delhi_test()
    assert inside(28.6469, 77.3160) is True or inside(28.6139, 77.2090) is True  # Anand Vihar / Connaught Place area
    assert inside(28.4501, 77.0263) is False  # Vikas Sadan, Gurugram
    assert inside(28.4243, 77.0722) is False  # Sector 51, Gurugram
