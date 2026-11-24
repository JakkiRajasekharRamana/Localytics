"""Refresh the cached PM2.5 monitor readings for a state (and optionally one city) from data.gov.in.

usage (from the Localytics folder):
    python scripts/refresh_air_cache.py Haryana Gurugram
    python scripts/refresh_air_cache.py Haryana            # every Haryana monitor (slower, a few more pages)

Needs DATA_GOV_API_KEY in Localytics/.env: your own free key from data.gov.in (never paste it in chat or commit it).
The readings go into data/areas.sqlite, the same cache the Flask site's /air-quality page fills. After a Haryana refresh,
re-run the Flat Finder builder so Gurugram buildings pick up their nearest monitor:
    PYTHONPATH=../flat-finder-localytics/pipeline python ../flat-finder-localytics/pipeline/build_ncr.py --localytics .
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GURUGRAM_BOX = (28.30, 28.60, 76.85, 77.20)  # south, north, west, east: where Gurugram buildings are


def summarise(records):
    """Stations in these records, grouped the way the app groups them, with the latest PM2.5 of each."""
    from observations import group_monitors

    monitors, _ = group_monitors(records)
    return monitors


def refresh(state, city="", client=None, repository=None):
    """Fetch the records, store them in the cache and return (records, monitors). Raises FetchError or RuntimeError."""
    if client is None:
        from air_client import PythonAirClient

        client = PythonAirClient()
    if repository is None:
        import data_store

        repository = data_store._repository(data_store.DB)
    records = client.fetch_records(state, city)
    if not records:
        raise RuntimeError(f"data.gov.in returned no records for state '{state}'" + (f", city '{city}'" if city else "") + ".")
    if not repository.cache_air(state, city, records):
        raise RuntimeError("Could not write the cache: is data/areas.sqlite present and writable (and not open in another tool)?")
    return records, summarise(records)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("state", help="for example Haryana")
    parser.add_argument("city", nargs="?", default="", help="for example Gurugram (optional)")
    args = parser.parse_args(argv)
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    if not os.environ.get("DATA_GOV_API_KEY", "").strip():
        print("DATA_GOV_API_KEY is not set. Add a line DATA_GOV_API_KEY=<your key> to Localytics/.env (free key: https://data.gov.in, My Account), then run this again.", file=sys.stderr)
        return 2
    from air_client import FetchError

    try:
        records, monitors = refresh(args.state, args.city)
    except (FetchError, RuntimeError) as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1
    south, north, west, east = GURUGRAM_BOX
    near = [m for m in monitors if south <= m["lat"] <= north and west <= m["lon"] <= east]
    print(f"Cached {len(records)} records from {len(monitors)} stations ({sum(1 for m in monitors if m['pm'] is not None)} with a PM2.5 reading).")
    print(f"{len(near)} station(s) in the Gurugram area:")
    for m in sorted(near, key=lambda m: m["name"]):
        print(f"  {m['name']}: PM2.5 {m['pm'] if m['pm'] is not None else 'no reading'}  ({m['lat']:.4f}, {m['lon']:.4f})  {m['stamp'] or ''}")
    if not near:
        print("  none: check the state and city spelling; the dataset lists Gurugram stations under state 'Haryana'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
