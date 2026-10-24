"""Transparent scoring of observed factors; no database or model transformations."""

import math
from datetime import datetime, timezone

from config import (
    AIRPORT_RADIUS_KM,
    CATEGORY,
    FACTORS,
    MONITOR_MAX_AGE_HOURS,
    MONITOR_RADIUS_KM,
    PM25_CAP,
    WORKPLACE_CAP_KM,
)
from geography import distance_km as distance


def nearest_air(cell, stations, now=None):
    """Separate the nearest displayed monitor from the nearest eligible ranking input."""
    if not stations:
        return None
    now = now or datetime.now(timezone.utc)
    observations = []
    for station in stations:
        km = distance(cell["lat"], cell["lon"], station["lat"], station["lon"])
        age = (now - station["stamp"]).total_seconds() / 3600 if station["stamp"] else None
        observations.append((station, km, age))
    nearest, km, age = min(observations, key=lambda item: item[1])
    eligible = [
        item
        for item in observations
        if item[0]["pm"] is not None
        and item[2] is not None
        and 0 <= item[2] <= MONITOR_MAX_AGE_HOURS
        and item[1] <= MONITOR_RADIUS_KM
    ]
    scored, scoring_km, _ = (
        min(eligible, key=lambda item: item[1]) if eligible else (None, None, None)
    )
    return dict(
        name=nearest["name"],
        lat=nearest["lat"],
        lon=nearest["lon"],
        distance_km=round(km, 2),
        pm=nearest["pm"],
        age_hours=round(age, 1) if age is not None else None,
        readings=nearest["readings"],
        score=1 - min(scored["pm"] / PM25_CAP, 1) if scored else None,
        scoring_monitor=scored["name"] if scored else None,
        scoring_value=scored["pm"] if scored else None,
        scoring_distance_km=round(scoring_km, 2) if scored else None,
        status="PM2.5 indicator: lower values score better; not official AQI"
        if scored
        else "No valid PM2.5 monitor within 5 km and 6 hours",
    )


def service_score(feature, radius, cap=10):
    if not feature["coverage"]:
        return None
    d = feature["nearest_km"]
    proximity = 1 - min(d / radius, 1) if d is not None else 0
    return 0.5 * proximity + 0.5 * min(feature["count"] / cap, 1)


def evaluate(cell, weights, radius=2, cap=10, stations=(), workplace=None, must=None):
    features = cell["features"][str(radius)]
    scores = {
        k: service_score(features[c], AIRPORT_RADIUS_KM if k == "airport" else radius, cap)
        for k, c in CATEGORY.items()
    }
    transit = [service_score(features[c], radius, cap) for c in ("bus_stop", "metro_station")]
    scores["transit"] = sum(transit) / 2 if all(v is not None for v in transit) else None
    air = nearest_air(cell, stations)
    scores["air"] = air["score"] if air else None
    work_km = distance(cell["lat"], cell["lon"], *workplace) if workplace else None
    scores["workplace"] = 1 - min(work_km / WORKPLACE_CAP_KM, 1) if work_km is not None else None
    checks = []
    for category, max_distance in (must or {}).items():
        f = features[category]
        if not f["coverage"]:
            status = "unverified"
        elif f["nearest_km"] is not None and f["nearest_km"] <= max_distance:
            status = "pass"
        else:
            status = "fail"
        checks.append(dict(factor=category, status=status, limit=max_distance))
    missing = [k for k, w in weights.items() if w > 0 and scores[k] is None]
    total = sum(weights.values())
    contributions = (
        {
            k: 100 * w / total * scores[k]
            for k, w in weights.items()
            if w > 0 and scores[k] is not None
        }
        if total
        else {}
    )
    eligible = not missing and all(c["status"] == "pass" for c in checks)
    score = sum(contributions.values()) if eligible and total > 0 else None
    return dict(
        id=cell["id"],
        label=cell["label"],
        lat=cell["lat"],
        lon=cell["lon"],
        scores=scores,
        score=round(score, 2) if score is not None else None,
        missing=missing,
        checks=checks,
        contributions=contributions,
        air=air,
        features=features,
        work_km=round(work_km, 2) if work_km is not None else None,
    )


def rank(cells, weights, radius=2, cap=10, stations=(), workplace=None, must=None):
    if not weights or not any(w > 0 for w in weights.values()):
        raise ValueError("Choose a positive importance for at least one factor.")
    if any(
        k not in FACTORS or not math.isfinite(w) or not 0 <= w <= MONITOR_RADIUS_KM
        for k, w in weights.items()
    ):
        raise ValueError("Importance values must be between 0 and 5.")
    results = [evaluate(c, weights, radius, cap, stations, workplace, must) for c in cells]
    results.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0), r["id"]))
    return results
