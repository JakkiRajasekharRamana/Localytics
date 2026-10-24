"""SQLite area data and credential-free cached air observations."""

import json
import sqlite3
from datetime import datetime, timezone
from functools import lru_cache

from config import DATA_DIR

DB = DATA_DIR / "areas.sqlite"


@lru_cache(maxsize=1)
def dataset():
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as db:
        manifest = json.loads(
            db.execute("SELECT value FROM metadata WHERE key=?", ("manifest",)).fetchone()[0]
        )
        cells = [json.loads(r[0]) for r in db.execute("SELECT payload FROM cells ORDER BY id")]
    return cells, manifest


def cache_air(state, city, records):
    """Persist only successful data; keys never contain credentials."""
    if not DB.exists():
        return
    key = json.dumps([state.casefold(), city.casefold()])
    try:
        with sqlite3.connect(DB, timeout=15) as db:
            db.execute(
                "INSERT OR REPLACE INTO air_cache VALUES (?,?,?)",
                (key, datetime.now(timezone.utc).isoformat(), json.dumps(records)),
            )
    except (sqlite3.Error, OSError):
        # A cache failure must not prevent the original station map from loading.
        return


def air_records():
    if not DB.exists():
        return [], None
    with sqlite3.connect(DB) as db:
        rows = db.execute(
            "SELECT query,fetched_at,payload FROM air_cache ORDER BY fetched_at DESC"
        ).fetchall()
    # A recent complete state refresh takes priority over city subsets.
    for query, stamp, payload in rows:
        state, city = json.loads(query)
        if state == "delhi" and not city:
            return json.loads(payload), stamp
    records = []
    seen = set()
    latest = None
    for query, stamp, payload in rows:
        if json.loads(query)[0] != "delhi":
            continue
        latest = latest or stamp
        for r in json.loads(payload):
            key = (r.get("station"), r.get("pollutant_id"), r.get("last_update"))
            if key not in seen:
                records.append(r)
                seen.add(key)
    return records, latest


def read_report(name):
    try:
        return json.loads(DB.with_name(name).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
