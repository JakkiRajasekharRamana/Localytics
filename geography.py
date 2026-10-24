"""Coordinate validation, straight-line distance and extract extent checks."""

import math
from collections import defaultdict

EARTH_RADIUS_KM = 6371.0088


def coordinates(latitude, longitude):
    lat, lon = float(latitude), float(longitude)
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Invalid latitude/longitude")
    return lat, lon


def distance_km(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    h = (
        math.sin((b - a) / 2) ** 2
        + math.cos(a) * math.cos(b) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1, max(0, h))))


def covered_radius(lat, lon, radius, bounds):
    dy = radius / 110
    dx = radius / (110 * max(0.001, math.cos(math.radians(lat))))
    return any(
        lon - dx >= b[0] and lat - dy >= b[1] and lon + dx <= b[2] and lat + dy <= b[3]
        for b in bounds
    )


def consolidate_named(rows):
    """Merge same-category/name representations within 100 m; keep unnamed objects."""
    unique, names = [], defaultdict(list)
    for row in rows:
        key = (row["category"], row["name"].strip().casefold())
        previous = next(
            (
                p
                for p in names[key]
                if key[1] != "unnamed"
                and distance_km(row["lat"], row["lon"], p["lat"], p["lon"]) < 0.1
            ),
            None,
        )
        if previous:
            if "osm_id" in row:
                previous.setdefault("related_osm", []).append(f"{row['osm_type']}/{row['osm_id']}")
            continue
        names[key].append(row)
        unique.append(row)
    return unique
