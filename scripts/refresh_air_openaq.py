"""Refresh the cached PM2.5 readings for Delhi and Gurugram from OpenAQ (a free key; the CPCB / HSPCB / DPCC / IMD reference monitors).

Use this when you do not have a data.gov.in key. OpenAQ republishes the same government monitors, with the reading in
ug/m3 like the data.gov.in feed, and the readings go into the same cache the Flat Finder builder already reads.

Both cities are fetched in the same run on purpose: PM2.5 swings a lot from day to day, so Gurugram readings from today
only make sense next to Delhi readings from today. Low-cost sensors (AirGradient, Clarity, ...) are left out; only
reference-grade government monitors count.

The value stored for a monitor is its average over the last 24 hours (like an air-quality index), not its latest hour: one
evening spike (Sector-51 read 75-140 all day and 300-400 after 19:00) would otherwise decide the picture for hundreds of buildings.
A monitor needs at least 75% of the hours to count.

usage (from the Localytics folder):
    python scripts/refresh_air_openaq.py                # Delhi and Gurugram, 24-hour averages
    python scripts/refresh_air_openaq.py --hours 48     # a longer average

Needs OPENAQ_API_KEY in Localytics/.env (free: https://explore.openaq.org, sign in, Settings, API key). Never paste it in chat or commit it.
Where it writes (data/areas.sqlite, table air_cache): ["haryana","gurugram"] for the Gurugram-side monitors and ["delhi","openaq"] for Delhi's.
The Flask and Flet apps keep reading their own ["delhi",""] data.gov.in cache, so nothing there changes. Then rebuild the Flat Finder data:
    PYTHONPATH=../flat-finder-localytics/pipeline python ../flat-finder-localytics/pipeline/build_ncr.py --localytics .
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

API = "https://api.openaq.org/v3"
RADIUS_M = 25000  # OpenAQ allows at most 25 km around a point
GURUGRAM_CENTRE = (28.46, 77.03)
DELHI_CENTRE = (28.64, 77.21)
IST = ZoneInfo("Asia/Kolkata")
GURUGRAM_BOX = (28.30, 28.60, 76.85, 77.20)  # south, north, west, east: where Gurugram buildings are
BOUNDARY = ROOT / "data" / "delhi_boundary.geojson"


class OpenAQError(Exception):
    pass


PACE_S = 1.2  # the free tier allows about 60 requests a minute; one every 1.2 s stays under it
_last_call = [0.0]


def _http_get(path, params, key, timeout=40):
    req = Request(f"{API}{path}?{urlencode(params)}", headers={"X-API-Key": key, "Accept": "application/json", "User-Agent": "Localytics/1.0"})
    for attempt in range(4):
        time.sleep(max(0.0, _last_call[0] + PACE_S - time.monotonic()))
        _last_call[0] = time.monotonic()
        try:
            with urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code in (401, 403):
                raise OpenAQError("OpenAQ rejected the key (HTTP %d). Check OPENAQ_API_KEY in .env: copy it again from explore.openaq.org, Settings." % exc.code) from None
            if exc.code == 429 and attempt < 3:
                try:
                    wait = min(65.0, float(exc.headers.get("Retry-After") or 20))
                except ValueError:
                    wait = 20.0
                print(f"  OpenAQ asked us to slow down; waiting {wait:.0f} s ...", file=sys.stderr)
                time.sleep(wait)
                continue
            if exc.code == 429:
                raise OpenAQError("OpenAQ keeps saying too many requests (HTTP 429). Wait a few minutes and run it again.") from None
            raise OpenAQError(f"OpenAQ answered HTTP {exc.code} for {path}.") from None
        except (URLError, OSError, ValueError) as exc:
            raise OpenAQError(f"Could not reach OpenAQ: {type(exc).__name__}.") from None


def _to_ist_stamp(value):
    """OpenAQ ISO time -> the 'dd-mm-yyyy HH:MM:SS' (India time) text the data.gov.in records use."""
    when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(IST).strftime("%d-%m-%Y %H:%M:%S"), when


def delhi_test(path=BOUNDARY):
    """A function (lat, lon) -> True inside Delhi, from the project's own Delhi boundary file."""
    from shapely.geometry import Point, shape

    features = json.loads(Path(path).read_text(encoding="utf-8"))["features"]
    polygon = shape(features[0]["geometry"])
    return lambda lat, lon: polygon.contains(Point(lon, lat))


def locations_around(key, centre, get=_http_get):
    found, page = [], 1
    while True:
        body = get("/locations", {"coordinates": f"{centre[0]},{centre[1]}", "radius": RADIUS_M, "limit": 100, "page": page, "iso": "IN"}, key)
        results = body.get("results") or []
        found.extend(results)
        if len(results) < 100 or page >= 5:
            return found
        page += 1


def _points(rows):
    """(end time, value) for each usable row of an OpenAQ hours / measurements answer."""
    out = []
    for row in rows:
        end = ((row.get("period") or {}).get("datetimeTo") or {}).get("utc")
        if row.get("value") is not None and float(row["value"]) >= 0 and end:
            out.append((end, float(row["value"])))
    return out


def reading_record(location, key, get, since, hours, state, city):
    """One data.gov.in-shaped PM2.5 record (the average of the last `hours` hours) for a reference-grade location, or None when it has too few hours."""
    if location.get("isMonitor") is not True:  # low-cost sensors (AirGradient, Clarity, ...) are not comparable with the government monitors
        return None
    coords = location.get("coordinates") or {}
    lat, lon = coords.get("latitude"), coords.get("longitude")
    pm_sensors = {s["id"]: s for s in location.get("sensors") or [] if (s.get("parameter") or {}).get("name") == "pm25"}
    if lat is None or lon is None or not pm_sensors:
        return None
    sensor = next(iter(pm_sensors.values()))
    if not ((sensor.get("parameter") or {}).get("units") or "").lower().startswith(("µg", "ug")):
        return None
    start = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    need = max(1, int(0.75 * hours))  # a few missing hours are fine; a monitor that was mostly silent is not an average
    points = _points(get(f"/sensors/{sensor['id']}/hours", {"datetime_from": start, "limit": hours + 6}, key).get("results") or [])
    if len(points) < need:  # some stations publish raw readings but no hourly roll-up: average the raw ones hour by hour
        raw = _points(get(f"/sensors/{sensor['id']}/measurements", {"datetime_from": start, "limit": 1000}, key).get("results") or [])
        by_hour = {}
        for end, value in raw:
            by_hour.setdefault(end[:13], []).append((end, value))  # 'YYYY-MM-DDTHH'
        points = [(max(e for e, _ in group), sum(v for _, v in group) / len(group)) for group in by_hour.values()]
    if len(points) < need:
        return None
    values = [v for _, v in points]
    stamp, _ = _to_ist_stamp(max(end for end, _ in points))
    return dict(country="India", state=state, city=city, station=str(location.get("name") or f"OpenAQ {location['id']}"),
                last_update=stamp, latitude=str(lat), longitude=str(lon), pollutant_id="PM2.5",
                min_value=str(round(min(values), 1)), max_value=str(round(max(values), 1)), avg_value=str(round(sum(values) / len(values), 1)),
                source="OpenAQ", window_hours=hours, hours_used=len(values))


def fetch_records(key, get=_http_get, hours=24, now=None, in_delhi=None):
    """Return (delhi_records, gurugram_side_records), all from the same fetch. Raises OpenAQError."""
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(hours=hours)
    in_delhi = in_delhi or delhi_test()
    around_gurugram = locations_around(key, GURUGRAM_CENTRE, get)
    around_delhi = locations_around(key, DELHI_CENTRE, get)
    delhi, other, seen = [], [], set()
    for origin, locations in (("gurugram", around_gurugram), ("delhi", around_delhi)):
        for location in locations:
            if location["id"] in seen:
                continue
            seen.add(location["id"])
            coords = location.get("coordinates") or {}
            lat, lon = coords.get("latitude"), coords.get("longitude")
            if lat is None or lon is None:
                continue
            if in_delhi(lat, lon):
                record = reading_record(location, key, get, since, hours, "Delhi", "Delhi")
                if record:
                    delhi.append(record)
            elif origin == "gurugram":  # outside Delhi, near Gurugram: Haryana. (Noida, Ghaziabad, ... come from the Delhi search and are not wanted.)
                record = reading_record(location, key, get, since, hours, "Haryana", "Gurugram")
                if record:
                    other.append(record)
    return delhi, other


def refresh(key, repository=None, get=_http_get, hours=24, now=None, in_delhi=None):
    """Fetch, store, and return (delhi_records, haryana_records, monitors_of_both)."""
    delhi, haryana = fetch_records(key, get=get, hours=hours, now=now, in_delhi=in_delhi)
    if not haryana:
        raise OpenAQError(f"OpenAQ has no government PM2.5 monitor with enough hours in the last {hours} near Gurugram. Try --hours 48.")
    if not delhi:
        raise OpenAQError(f"OpenAQ has no government PM2.5 monitor with enough hours in the last {hours} in Delhi, so the two cities could not be compared. Try --hours 48.")
    if repository is None:
        import data_store

        repository = data_store._repository(data_store.DB)
    if not (repository.cache_air("Haryana", "Gurugram", haryana) and repository.cache_air("Delhi", "openaq", delhi)):
        raise OpenAQError("Could not write the cache: is data/areas.sqlite present and writable (and not open in another tool)?")
    from observations import group_monitors

    return delhi, haryana, group_monitors(delhi + haryana)[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hours", type=int, default=24, help="average each monitor over this many recent hours (default 24)")
    args = parser.parse_args(argv)
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    key = os.environ.get("OPENAQ_API_KEY", "").strip()
    if not key:
        print("OPENAQ_API_KEY is not set. Add a line OPENAQ_API_KEY=<your key> to Localytics/.env (free key: https://explore.openaq.org, Settings), then run this again.", file=sys.stderr)
        return 2
    try:
        delhi, haryana, monitors = refresh(key, hours=args.hours)
    except OpenAQError as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1
    print(f"Cached {len(delhi)} Delhi and {len(haryana)} Gurugram-side government monitors (OpenAQ, {args.hours}-hour averages).")
    south, north, west, east = GURUGRAM_BOX
    for title, group in (("Gurugram side", [m for m in monitors if m["name"] in {r["station"] for r in haryana}]),
                         ("Delhi", [m for m in monitors if m["name"] in {r["station"] for r in delhi}])):
        values = sorted(m["pm"] for m in group)
        print(f"\n{title}: {len(group)} stations, PM2.5 median {values[len(values) // 2]:.0f}, range {values[0]:.0f} to {values[-1]:.0f}")
        for m in sorted(group, key=lambda m: m["name"]):
            inside = "  [Gurugram area]" if south <= m["lat"] <= north and west <= m["lon"] <= east and title != "Delhi" else ""
            print(f"  {m['name']}: {m['pm']}  ({m['lat']:.4f}, {m['lon']:.4f})  {m['stamp'] or ''}{inside}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
