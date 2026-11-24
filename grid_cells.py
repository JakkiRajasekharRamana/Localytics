"""One-kilometre grid cells and their facility indicators.

Shared by scripts/build_areas.py (the Delhi build from OpenStreetMap extracts) and scripts/add_gurugram_cells.py (Gurugram cells built from the
facilities already stored in the same database), so both cities are scored from cells made by exactly the same code.
"""

import math

import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import Point, box, mapping
from shapely.ops import transform

from geography import covered_radius

CATS = ["bus_stop", "metro_station", "airport_terminal", "school", "hospital", "park", "gym", "mall", "ev"]
EARTH_KM = 6371.0088


# 3D spherical indexing keeps straight-line distances accurate across the extracts.
def xyz(lat, lon):
    a, b = math.radians(lat), math.radians(lon)
    return [math.cos(a) * math.cos(b), math.cos(a) * math.sin(b), math.sin(a)]


def index_rows(rows, named_localities=False):
    """Per-category lists of facility rows and a nearest-neighbour tree for each (the 'locality' rows name the cells).

    named_localities=True lets only localities that have a name label a cell: OpenStreetMap has many unnamed place points around Gurugram,
    which would otherwise label one cell in six 'Unnamed vicinity'. The Delhi build keeps the default, so its labels do not change."""
    trees, catrows = {}, {}
    for c in CATS + ["locality"]:
        catrows[c] = [r for r in rows if r["category"] == c and not (named_localities and c == "locality" and (r["name"] or "Unnamed") == "Unnamed")]
        if catrows[c]:
            trees[c] = cKDTree([xyz(r["lat"], r["lon"]) for r in catrows[c]])
    return trees, catrows


def build_cell(prefix, x, y, projected, reverse, trees, catrows, bounds):
    """The cell whose south-west corner is (x, y) metres, or None when its centre lies outside the boundary."""
    center = Point(x + 500, y + 500)
    if not projected.covers(center):
        return None
    lon, lat = reverse(center.x, center.y)
    cell = dict(
        id=f"{prefix}_{x // 1000}_{y // 1000}",
        lat=lat,
        lon=lon,
        geometry=mapping(transform(reverse, box(x, y, x + 1000, y + 1000).intersection(projected))),
        features={},
    )
    if "locality" in trees:
        chord, idx = trees["locality"].query(xyz(lat, lon))
        km = 2 * EARTH_KM * math.asin(min(1, chord / 2))
        cell["label"] = catrows["locality"][idx]["name"] + f" vicinity ({km:.1f} km)"
    else:
        cell["label"] = cell["id"]
    for radius in (1, 2, 5):
        indicators = {}
        for c in CATS:
            r = 25 if c == "airport_terminal" else radius
            covered = covered_radius(lat, lon, r, bounds)
            nearby = []
            nearest = None
            if c in trees:
                chord, idx = trees[c].query(xyz(lat, lon))
                nearest = 2 * EARTH_KM * math.asin(min(1, chord / 2))
                indices = trees[c].query_ball_point(xyz(lat, lon), 2 * math.sin(r / (2 * EARTH_KM)))
                for idx in indices:
                    p = catrows[c][idx]
                    d = 2 * EARTH_KM * math.asin(min(1, float(np.linalg.norm(np.array(xyz(lat, lon)) - xyz(p["lat"], p["lon"]))) / 2))
                    nearby.append(
                        dict(
                            name=p["name"],
                            km=round(d, 3),
                            lat=p["lat"],
                            lon=p["lon"],
                            method=p["method"],
                            osm=f"{p['osm_type']}/{p['osm_id']}",
                            access=p["tags"].get("access", "unknown"),
                        )
                    )
                nearby.sort(key=lambda p: p["km"])
            indicators[c] = dict(
                count=len(nearby),
                nearest_km=round(nearest, 3) if nearest is not None else None,
                coverage=covered,
                nearby=nearby[:5],
            )
        cell["features"][str(radius)] = indicators
    return cell


def grid_cells(prefix, projected, reverse, trees, catrows, bounds, skip=()):
    """Every 1 km cell (metres, EPSG:32643 grid) whose centre is inside the projected boundary, skipping any (x, y) in `skip`."""
    minx, miny, maxx, maxy = projected.bounds
    cells = []
    for x in range(math.floor(minx / 1000) * 1000, math.ceil(maxx / 1000) * 1000, 1000):
        for y in range(math.floor(miny / 1000) * 1000, math.ceil(maxy / 1000) * 1000, 1000):
            if (x, y) in skip:
                continue
            cell = build_cell(prefix, x, y, projected, reverse, trees, catrows, bounds)
            if cell is not None:
                cells.append(cell)
    return cells
