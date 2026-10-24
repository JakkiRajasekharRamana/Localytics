"""One parser for station groups and the latest PM2.5 observation."""

import math
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from config import MISSING_PM25, PM25_BANDS
from geography import coordinates

INDIA_TZ = ZoneInfo("Asia/Kolkata")


def observation_time(value):
    try:
        return datetime.strptime(value, "%d-%m-%Y %H:%M:%S").replace(tzinfo=INDIA_TZ)
    except (ValueError, TypeError):
        return None


def latest_pm25(readings):
    candidates = [r for r in readings if r.get("pollutant_id") == "PM2.5"]
    if not candidates:
        return None, None
    latest = max(
        candidates,
        key=lambda r: (
            observation_time(r.get("last_update")) or datetime.min.replace(tzinfo=INDIA_TZ)
        ),
    )
    stamp = observation_time(latest.get("last_update"))
    try:
        value = float(latest["avg_value"])
        return (value if math.isfinite(value) and value >= 0 else None), stamp
    except (ValueError, TypeError, KeyError):
        return None, stamp


def severity(value):
    if value is None:
        return dict(MISSING_PM25)
    for upper, label, color in PM25_BANDS:
        if upper is None or value <= upper:
            return dict(value=value, label=label, color=color)


def group_monitors(records):
    groups = defaultdict(list)
    skipped = 0
    for row in records:
        try:
            lat, lon = coordinates(row["latitude"], row["longitude"])
        except (KeyError, ValueError, TypeError):
            skipped += 1
            continue
        groups[(str(row.get("station", "Unknown")), lat, lon)].append(row)
    monitors = []
    for (name, lat, lon), readings in groups.items():
        pm, stamp = latest_pm25(readings)
        monitors.append(dict(name=name, lat=lat, lon=lon, readings=readings, pm=pm, stamp=stamp))
    return monitors, skipped


def monitors(records):
    return group_monitors(records)[0]
