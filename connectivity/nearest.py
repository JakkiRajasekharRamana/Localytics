"""Local nearest-feature lookup. No external dependencies or API key."""

import math

from geography import coordinates
from geography import distance_km as distance_km
from transport_data import load_transport


def nearest(
    latitude, longitude, category="bus_stop", limit=5, radius_km=None, csv_path=None, *, rows=None
):
    """Return nearest mapped features, with straight-line distances.
    Category: bus_stop, metro_station, metro_entrance, railway_station,
    airport_terminal, airport. Duplicates may represent one physical facility.
    """
    latitude, longitude = coordinates(latitude, longitude)
    if limit < 1:
        raise ValueError("limit must be positive")
    if radius_km is not None and (not math.isfinite(radius_km) or radius_km < 0):
        raise ValueError("radius_km must be nonnegative")
    matches = []
    for source in load_transport(csv_path) if rows is None else rows:
        if source.get("category") != category:
            continue
        row = dict(source)
        distance = distance_km(latitude, longitude, row["latitude"], row["longitude"])
        if radius_km is None or distance <= radius_km:
            row["distance_km"] = distance
            matches.append(row)
    return sorted(matches, key=lambda x: x["distance_km"])[:limit]
