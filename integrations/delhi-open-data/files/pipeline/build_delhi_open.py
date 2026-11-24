"""Build a Delhi city for Flat Finder from open data only (no listing-site crawling).

usage (use the Localytics Python environment; needs osmium, shapely, numpy, scipy):
  python build_delhi_open.py --pbf NewDelhi.osm.pbf --rents New-Delhi-Rental-Listings.arff \
      --localytics /path/to/Localytics [--out ../web/public/data]

Sources, all open:
  * OpenStreetMap (BBBike "NewDelhi" extract, ODbL): named apartment buildings, society land parcels, colonies.
  * "New Delhi Rental Listings", OpenML 43837, declared CC0 by its uploader. Collected 11 Aug 2020, so rents are
    about six years old. The listings were originally taken from a real-estate site; disclose that, do not hide it.
  * Localytics data/areas.sqlite: nearby schools, hospitals, parks, metro, malls and cached PM2.5 readings.
  * Localytics data/delhi_boundary.geojson: the Delhi boundary used to clip everything.

Rents are LOCALITY medians (the dataset has locality-level coordinates, not building-level), split by property
type: apartment buildings only ever use apartment listings, colonies only use builder-floor listings.
"""

import argparse
import csv
import io
import json
import math
import re
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import osmium
import shapely.wkb
from scipy.spatial import cKDTree
from shapely.geometry import MultiPolygon, Point, mapping, shape
from shapely.ops import unary_union
from shapely.prepared import prep
from shapely.strtree import STRtree

RENT_DATASET = "https://www.openml.org/search?type=data&id=43837"
RENT_COLLECTED = "August 2020"
OSM_SOURCE = "https://www.openstreetmap.org/copyright"
CENTER, ZOOM = [77.209, 28.614], 10.4
MAX_RENT_KM = 1.5  # a building takes rents from the nearest locality only within this distance
MIN_N = 3  # listings needed for a median
KINDS = {"Apartment": "apartment", "Independent Floor": "builder floor"}

# ---------------------------------------------------------------- rents


def read_arff(path):
    attrs, rows, in_data = [], [], False
    for line in open(path, encoding="utf-8", errors="ignore"):
        s = line.strip()
        if not in_data:
            if s.upper().startswith("@ATTRIBUTE"):
                attrs.append(s.split()[1])
            elif s.upper().startswith("@DATA"):
                in_data = True
            continue
        if s and not s.startswith("%"):
            values = next(csv.reader(io.StringIO(s), quotechar="'", skipinitialspace=True))
            if len(values) == len(attrs):
                rows.append(dict(zip(attrs, values)))
    return rows


def loc_key(name):
    """Punctuation- and spacing-insensitive key, so 'Sector-8 Rohini' and 'sector 8 rohini' are one locality."""
    key = re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()
    return re.sub(r"\bsec\b", "sector", key)


def loc_title(name):
    return " ".join(w if w.isdigit() else w.capitalize() for w in loc_key(name).split())


def clean_rents(rows, boundary_geom):
    """Typo and outlier filtering. Returns clean rows and a Counter of why rows were dropped."""
    drops, out = Counter(), []
    near = boundary_geom.buffer(0.004)  # about 400 m of tolerance for locality-level coordinates
    for r in rows:
        try:
            kind = KINDS.get(r["propertyType"])
            bhk, size, rent = int(float(r["bedrooms"])), float(r["size_sq_ft"]), float(r["price"])
            lat, lon = float(r["latitude"]), float(r["longitude"])
        except (KeyError, ValueError):
            drops["unreadable"] += 1
            continue
        if kind is None:
            drops["other property type (house/villa)"] += 1
        elif not 1 <= bhk <= 5:
            drops["bedrooms outside 1-5"] += 1
        elif not 150 <= size <= 12000 or size / bhk < 80:
            drops["implausible size"] += 1
        elif not 2000 <= rent <= 1_000_000 or not 3 <= rent / size <= 400:
            drops["implausible rent (likely typo)"] += 1
        elif not near.contains(Point(lon, lat)):
            drops["outside the Delhi boundary"] += 1
        else:
            out.append(dict(kind=kind, bhk=bhk, size=size, rent=rent, lat=lat, lon=lon,
                            key=loc_key(r["localityName"]), name=loc_title(r["localityName"]), suburb=r["suburbName"]))
    return out, drops


def summarise_rents(rows):
    """localities[key] -> {name, lat, lon, buckets[(kind, bhk)] -> stats}, only buckets with enough listings."""
    by_loc = defaultdict(list)
    for r in rows:
        by_loc[r["key"]].append(r)
    localities = {}
    for key, rs in by_loc.items():
        buckets = {}
        by = defaultdict(list)
        for r in rs:
            by[(r["kind"], r["bhk"])].append(r)
        for k, items in by.items():
            if len(items) >= MIN_N:
                rents = sorted(i["rent"] for i in items)
                buckets[k] = dict(median=round(statistics.median(rents), -2), min=rents[0], max=rents[-1], n=len(rents),
                                  size=round(statistics.median(i["size"] for i in items)))
        name = Counter(r["name"] for r in rs).most_common(1)[0][0]
        if re.fullmatch(r"sector \d+[a-z]?|block [a-z]|pocket \d+", key):  # ambiguous on its own: add the area
            suburbs = Counter(r["suburb"] for r in rs if r["suburb"] and r["suburb"] != "Other")
            if suburbs:
                name = f"{name}, {suburbs.most_common(1)[0][0]}"
        localities[key] = dict(name=name,
                               lat=statistics.median(r["lat"] for r in rs), lon=statistics.median(r["lon"] for r in rs),
                               n=len(rs), buckets=buckets)
    return localities


# ---------------------------------------------------------------- geometry helpers


def xy(lat0):
    kx = 111320 * math.cos(math.radians(lat0))
    return lambda lon, lat: (lon * kx, lat * 110574)


PROJ = xy(28.6)


def height_of(tags, default):
    h = tags.get("height")
    try:
        if h:
            return min(150.0, float(re.sub(r"[^0-9.]", "", h)))
        if tags.get("building:levels"):
            return min(150.0, round(float(tags["building:levels"]) * 3.2, 1))
    except ValueError:
        pass
    return default


def ring_of(geom, digits=6):
    """Exterior ring of the largest polygon, rounded to ~10 cm (6 digits) or ~1 m (5 digits)."""
    poly = max(geom.geoms, key=lambda g: g.area) if isinstance(geom, MultiPolygon) else geom
    return [[round(x, digits), round(y, digits)] for x, y in poly.simplify(0.000008).exterior.coords]


SOCIETY = re.compile(r"\b(apartments?|apts?|flats?|society|societies|cghs|group housing|housing|residency|residences?|"
                     r"heights|towers?|dda|sfs|co-?operative|mansions?)\b", re.I)
GENERIC = re.compile(r"^(tower|block|building|wing|flat|house|pocket|phase|sector|plot)\s*-?\s*[a-z0-9]{1,3}$", re.I)
NOT_HOME = ("amenity", "shop", "office", "tourism", "healthcare", "leisure", "craft", "historic", "man_made", "religion")
# Institutional or staff housing is not on the open rental market.
INSTITUTIONAL = re.compile(r"hostel|quarters|barracks?|dormitor|guest ?house|hotel|lodge|\bstaff\b|\bpolice\b|\bmess\b|ashram|"
                           r"orphan|old age|\bpg\b|boarding|\bnavy\b|\barmy\b|\bcpwd\b|\brailway\b", re.I)


# --more: extra residential areas and clusters of unnamed apartment buildings, with stricter rent borrowing.
BORROW_KM = 1.0  # extra entries borrow a neighbouring locality's rents only within this distance
MORE_NOTE = (" Delhi also includes other mapped residential areas (their housing type is not mapped) and groups of apartment buildings that are unnamed in OpenStreetMap; "
             "their rents are borrowed from a nearby locality within 1 km, and each card names that locality and its distance.")
# Informal settlements, villages and camps are not the market the borrowed builder-floor rents describe.
AREA_EXCLUDE = re.compile(r"\b(j\.?\s?j\.?|jhuggi\w*|camp|resettlement|basti|village|gaon|slum|unauthori[sz]ed|labou?r|industrial|factory|warehouse)\b", re.I)
# "A block", "Sector 9", "Phase 2", "B1": meaningless on their own, so they get their locality appended.
GENERIC_AREA = re.compile(r"^(?:[a-z]|\d{1,3}[a-z]?)(?:[\s-]*(?:block|pocket|sector|phase|ext\.?|extension))?$|"
                          r"^(?:block|pocket|pkt\.?|sector|phase|ext\.?|extension)[\s-]*[a-z0-9]{0,3}$|^[a-z]{1,3}[\s-]?\d{1,3}$", re.I)


def cluster_buildings(units, radius_m=80):
    """Single-linkage clusters of buildings whose neighbours are within radius_m. Returns lists of units."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    if not units:
        return []
    pts = np.array([PROJ(u["lon"], u["lat"]) for u in units])
    pairs = np.array(list(cKDTree(pts).query_pairs(radius_m)))
    n = len(units)
    if len(pairs):
        graph = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
        _, labels = connected_components(graph, directed=False)
    else:
        labels = np.arange(n)
    groups = defaultdict(list)
    for u, label in zip(units, labels):
        groups[label].append(u)
    return list(groups.values())


def read_osm(pbf, boundary_prep, boundary_geom, collect_unnamed=False):
    """Pass 1: named apartment buildings, society land parcels and named residential colonies, clipped to Delhi.
    With collect_unnamed, also unnamed apartment/residential buildings of at least 120 m2 (for clustering)."""
    fp = (osmium.FileProcessor(pbf).with_locations().with_areas()
          .with_filter(osmium.filter.EntityFilter(osmium.osm.AREA))
          .with_filter(osmium.filter.KeyFilter("building", "landuse")))
    fab = osmium.geom.WKBFactory()
    found = dict(building=[], society_land=[], colony=[], unnamed_res=[])
    seen = Counter()
    for a in fp:
        t = a.tags
        name = (t.get("name") or "").strip()
        b, lu = t.get("building"), t.get("landuse")
        if not name:
            if collect_unnamed and b in ("apartments", "residential") and not any(k in t for k in NOT_HOME):
                try:
                    geom = shapely.wkb.loads(fab.create_multipolygon(a), hex=True)
                except Exception:
                    continue
                c = geom.centroid
                if geom.area * 1.2e10 >= 120 and boundary_prep.contains(c):
                    found["unnamed_res"].append(dict(id=f"{'w' if a.from_way() else 'r'}{a.orig_id()}", tags=dict(t), geom=geom,
                                                     lat=c.y, lon=c.x, area_m2=geom.area * 1.2e10))
            continue
        if INSTITUTIONAL.search(name):
            seen["institutional or staff housing"] += 1
            continue
        if lu == "residential":
            kind = "society_land" if SOCIETY.search(name) else "colony"
        elif b in ("apartments", "residential", "dormitory") or (b == "yes" and SOCIETY.search(name)):
            if any(k in t for k in NOT_HOME) or GENERIC.match(name) or GENERIC_AREA.match(name) or len(re.sub(r"[^a-z0-9]", "", name.lower())) <= 3:
                seen["rejected name or non-residential tags"] += 1  # "A", "D-8", "Tower 3": meaningless without their complex
                continue
            kind = "building"
        else:
            continue
        try:
            geom = shapely.wkb.loads(fab.create_multipolygon(a), hex=True)
        except Exception:
            seen["geometry error"] += 1
            continue
        c = geom.centroid
        if not boundary_prep.contains(c):
            seen["outside Delhi (e.g. Gurugram, Noida)"] += 1
            continue
        if geom.area * 1.2e10 < 150 or geom.area * 1.2e10 > 8e6:
            seen["too small or too large"] += 1
            continue
        found[kind].append(dict(id=f"{'w' if a.from_way() else 'r'}{a.orig_id()}", name=name, tags=dict(t), geom=geom,
                                lat=c.y, lon=c.x, area_m2=geom.area * 1.2e10))
    return found, seen


def read_footprints(pbf, polygons, exclude=()):
    """Pass 2: building footprints inside the given polygons (by centroid). polygons: list of dicts with 'geom'.
    Buildings whose centroid lies inside an exclude geometry belong to another entry and are skipped."""
    tree = STRtree([p["geom"] for p in polygons])
    ex_tree = STRtree(list(exclude)) if len(exclude) else None
    fp = (osmium.FileProcessor(pbf).with_locations().with_areas()
          .with_filter(osmium.filter.EntityFilter(osmium.osm.AREA)).with_filter(osmium.filter.KeyFilter("building")))
    fab = osmium.geom.WKBFactory()
    for a in fp:
        try:
            g = shapely.wkb.loads(fab.create_multipolygon(a), hex=True)
        except Exception:
            continue
        hits = tree.query(g.centroid, predicate="within")
        if len(hits) and ex_tree is not None and len(ex_tree.query(g.centroid, predicate="within")):
            continue
        if len(hits):
            i = min(hits, key=lambda j: polygons[j]["geom"].area)
            p = polygons[i]
            lst = p.setdefault("footprints", [])
            lst.append(dict(area=g.area * 1.2e10, ring=ring_of(g, p.get("digits", 6)), h=height_of(a.tags, 15.0 if p.get("tall") else 9.0)))
            cap = p.get("cap", 150)
            if len(lst) > cap * 2:  # keep memory bounded: only the largest footprints are ever drawn
                lst.sort(key=lambda z: -z["area"])
                del lst[cap:]


# ---------------------------------------------------------------- Localytics: nearby places and PM2.5

NEARBY = {"park": "park", "school": "school", "hospital": "hospital", "metro_station": "metro", "mall": "shopping"}


def load_nearby(db):
    pts = defaultdict(list)
    for cat, payload in db.execute("SELECT category, payload FROM facilities WHERE category IN (%s)" % ",".join("?" * len(NEARBY)), tuple(NEARBY)):
        p = json.loads(payload)
        if 28.35 <= p["lat"] <= 28.95 and 76.78 <= p["lon"] <= 77.4:
            pts[NEARBY[cat]].append((p["lat"], p["lon"], p.get("name") or ""))
    trees = {}
    for kind, items in pts.items():
        trees[kind] = (cKDTree(np.array([PROJ(lo, la) for la, lo, _ in items])), items)
    return trees


def nearby_for(lat, lon, trees):
    x, y = PROJ(lon, lat)
    out = {}
    for kind, (tree, items) in trees.items():
        d, i = tree.query([x, y])
        out[kind] = dict(m=round(float(d)), name=items[i][2] if items[i][2] and items[i][2] != "Unnamed" else None,
                         n=len(tree.query_ball_point([x, y], 1000)))
    return out


def load_monitors(db, localytics):
    sys.path.insert(0, str(localytics))
    from config import MONITOR_RADIUS_KM, PM25_BANDS
    from observations import group_monitors, severity

    # Every cached search for Delhi or Haryana (e.g. a "Haryana / Gurugram" refresh) feeds the monitors.
    records, fetched = [], []
    for query, fetched_at, payload in db.execute("SELECT query, fetched_at, payload FROM air_cache"):
        state = (json.loads(query) or [""])[0]
        if state in ("delhi", "haryana"):
            records += json.loads(payload)
            fetched.append(fetched_at)
    if not records:
        return [], None, MONITOR_RADIUS_KM, PM25_BANDS, severity
    monitors, _ = group_monitors(records)
    usable = [m for m in monitors if m["pm"] is not None and 28.15 <= m["lat"] <= 28.95 and 76.7 <= m["lon"] <= 77.5]
    return usable, max(fetched), MONITOR_RADIUS_KM, PM25_BANDS, severity


def air_for(lat, lon, monitors, radius_km, bands, severity):
    x, y = PROJ(lon, lat)
    best = None
    for m in monitors:
        mx, my = PROJ(m["lon"], m["lat"])
        d = math.hypot(mx - x, my - y) / 1000
        if d <= radius_km and (best is None or d < best[0]):
            best = (d, m)
    if not best:
        return None, -1
    d, m = best
    sev = severity(m["pm"])
    idx = next(i for i, (upper, _, _) in enumerate(bands) if upper is None or m["pm"] <= upper)
    return dict(pm=m["pm"], label=sev["label"], color=sev["color"], monitor=m["name"], km=round(d, 1),
                updated=m["stamp"].isoformat() if m["stamp"] else None), idx


# ---------------------------------------------------------------- assembling societies


def prices_for(loc, kind, dist_km=None):
    prices, units = {}, []
    far = f" ({dist_km:.1f} km away)" if dist_km else ""  # borrowed from a neighbouring locality: say how far
    for (k, bhk), st in sorted(loc["buckets"].items()):
        if k != kind:
            continue
        basis = f"{kind} listings in {loc['name']}{far}, {RENT_COLLECTED}"
        prices[str(bhk)] = dict(rent=dict(median=st["median"], min=st["min"], max=st["max"], n=st["n"], basis=basis))
        units.append(dict(label=f"{bhk} BHK · typical {st['size']:,} sq ft in this locality", bhk=bhk, size_sqft=float(st["size"]),
                          bedrooms=[], rooms_complete=False, confidence="locality", source=RENT_DATASET, page=None,
                          est_short=None, est_area=None))
    return prices, units


def make_society(sid, name, kind, lat, lon, loc, dist_km, shape_kind, note, air, aq, nearby, config_text, osm_url, shape_note):
    prices, units = prices_for(loc, kind, dist_km) if loc else ({}, [])
    rents = [v["rent"]["median"] for v in prices.values()]
    return dict(
        id=sid, name=name, developer="", locality=loc["name"] if loc else "", lat=round(lat, 6), lng=round(lon, 6),
        status="", possession="", rera_id="", units=None, towers=None, acres=None, price_min=None, price_max=None,
        kind=kind, kind_inferred=False, config_text=config_text, amenities=[], amen_facts={}, unit_types=units,
        url=osm_url, brochure_url=None, plan_links={}, verified=False, note=note, rating=None, rating_count=0,
        review_count=0, locality_rating=None, sale_count=0, rent_count=sum(v["rent"]["n"] for v in prices.values()),
        psf_now=None, gmaps="https://www.google.com/maps/search/?api=1&query=" + f"{lat:.6f}%2C{lon:.6f}",
        prices=prices, nearby=nearby, score=None, score_parts={}, shape=shape_kind, shape_note=shape_note, air=air, aq=aq,
        open_data=True, no_sale=True, city_label="Delhi",  # per-building flags: the app words cards and Buy mode from these
        rent_from=min(rents) if rents else None, rent_km=round(dist_km, 2) if dist_km is not None else None)


def circle(lon, lat, r_m=260, n=28):
    kx = 111320 * math.cos(math.radians(lat))
    return [[round(lon + r_m * math.cos(2 * math.pi * i / n) / kx, 6), round(lat + r_m * math.sin(2 * math.pi * i / n) / 110574, 6)]
            for i in range(n + 1)]


def norm_tokens(s):
    return set(re.sub(r"[^a-z0-9 ]+", " ", s.lower()).split()) - {"block", "colony", "extension", "ext", "enclave", "phase", "sector", "the"}


def build(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    loc_dir = Path(args.localytics)
    boundary = unary_union([shape(f["geometry"]) for f in json.loads((loc_dir / "data/delhi_boundary.geojson").read_text(encoding="utf-8"))["features"]])
    bprep = prep(boundary.buffer(0.0008))
    db = sqlite3.connect(f"file:{loc_dir / 'data/areas.sqlite'}?mode=ro", uri=True)

    rows = read_arff(args.rents)
    rents, drops = clean_rents(rows, boundary)
    locs = summarise_rents(rents)
    print(f"rent rows: {len(rows)} read, {len(rents)} kept; dropped: {dict(drops)}")
    print(f"localities: {len(locs)}; with an apartment bucket: {sum(1 for l in locs.values() if any(k[0] == 'apartment' for k in l['buckets']))}; "
          f"with a builder-floor bucket: {sum(1 for l in locs.values() if any(k[0] == 'builder floor' for k in l['buckets']))}")

    found, seen = read_osm(args.pbf, bprep, boundary, collect_unnamed=args.more)
    print("OSM candidates (inside Delhi):", {k: len(v) for k, v in found.items()}, "| rejected:", dict(seen))

    trees = load_nearby(db)
    monitors, fetched, radius_km, bands, severity = load_monitors(db, loc_dir)
    print(f"PM2.5 monitors usable: {len(monitors)} (cache fetched {fetched})")

    def nearest_locality(lat, lon, kind, limit_km=MAX_RENT_KM):
        """Nearest rent locality having data for this property kind (any kind if None), within limit_km, else (None, distance)."""
        pool = [(k, l) for k, l in locs.items() if kind is None or any(b[0] == kind for b in l["buckets"])]
        if not pool:
            return None, None
        x, y = PROJ(lon, lat)
        best = min(((math.hypot(PROJ(l["lon"], l["lat"])[0] - x, PROJ(l["lon"], l["lat"])[1] - y) / 1000, l) for _, l in pool), key=lambda t: t[0])
        return (best[1], best[0]) if best[0] <= limit_km else (None, best[0])

    # --- apartment buildings and society parcels
    societies, shapes_by_sid, events = [], {}, []
    parcels = [dict(f, tall=True) for f in found["society_land"]]
    standalone = []
    ptree = STRtree([p["geom"] for p in parcels]) if parcels else None
    for b in found["building"]:
        inside = ptree is not None and len(ptree.query(Point(b["lon"], b["lat"]), predicate="within")) > 0
        if not inside:
            standalone.append(dict(b, tall=True))
    # drop near-duplicate names within 200 m (keep the larger footprint)
    keep, seen_names = [], {}
    for f in sorted(parcels + standalone, key=lambda f: -f["area_m2"]):
        k = loc_key(f["name"])
        if any(math.hypot(PROJ(f["lon"], f["lat"])[0] - x, PROJ(f["lon"], f["lat"])[1] - y) < 200 for x, y in seen_names.get(k, [])):
            continue
        seen_names.setdefault(k, []).append(PROJ(f["lon"], f["lat"]))
        keep.append(f)
    apt_features = keep

    # --- colonies (builder floors), one per rent locality with builder-floor data
    colony_polys = found["colony"]
    floor_locs = [(k, l) for k, l in locs.items() if any(b[0] == "builder floor" for b in l["buckets"])]
    colony_pick = {}
    ctree = STRtree([c["geom"] for c in colony_polys]) if colony_polys else None
    for k, l in floor_locs:
        want = norm_tokens(l["name"])
        best = None
        for c in colony_polys:
            nt = norm_tokens(c["name"])
            if nt and want and (nt <= want or want <= nt) and math.hypot(*[a - b for a, b in zip(PROJ(c["lon"], c["lat"]), PROJ(l["lon"], l["lat"]))]) < 2500:
                if best is None or c["area_m2"] > best["area_m2"]:
                    best = c
        if best is None and ctree is not None:
            hits = ctree.query(Point(l["lon"], l["lat"]), predicate="within")
            if len(hits):
                best = colony_polys[min(hits, key=lambda j: colony_polys[j]["geom"].area)]
        colony_pick[k] = best

    # One entry per OSM polygon: localities that pick the same polygon are spellings of one place
    # ("Mayur Vihar", "Mayur Vihar I", "Mayur Vihar Phase 1"), so their listings are pooled instead of drawing it twice.
    rows_by_key = defaultdict(list)
    for r in rents:
        rows_by_key[r["key"]].append(r)
    by_polygon, merged_floor_locs, pooled = defaultdict(list), [], 0
    for k, l in floor_locs:
        c = colony_pick[k]
        (by_polygon[c["id"]] if c is not None else merged_floor_locs).append((k, l))
    for members in by_polygon.values():
        if len(members) == 1:
            merged_floor_locs.append(members[0])
            continue
        lead = max(members, key=lambda kl: kl[1]["n"])
        pool_rows = [dict(r, key=lead[0], name=lead[1]["name"], suburb="") for k, _ in members for r in rows_by_key[k]]
        merged_floor_locs.append((lead[0], summarise_rents(pool_rows)[lead[0]]))
        pooled += len(members) - 1
    floor_locs = merged_floor_locs
    print(f"colonies: {len(floor_locs)} entries after pooling {pooled} spellings that shared an OSM polygon")

    # --- more, tier 2: the other named residential areas, never overlapping an existing entry
    tier2, tier2_drops = [], Counter()
    if args.more:
        tier1_ids = {c["id"] for c in colony_pick.values() if c is not None}
        chosen = [f["geom"] for f in apt_features] + [c["geom"] for c in colony_pick.values() if c is not None]
        chosen_polys, chosen_pts = STRtree(chosen), STRtree([g.centroid for g in chosen])
        cands = []
        for c in colony_polys:
            if c["id"] in tier1_ids:
                continue
            if AREA_EXCLUDE.search(c["name"]):
                tier2_drops["informal or village-type name"] += 1
            elif not 3000 <= c["area_m2"] <= 2.5e6:
                tier2_drops["too small or too large"] += 1
            elif len(chosen_polys.query(c["geom"].centroid, predicate="within")) or len(chosen_pts.query(c["geom"], predicate="contains")):
                tier2_drops["overlaps an existing entry"] += 1
            else:
                cands.append(c)
        cpts = STRtree([c["geom"].centroid for c in cands]) if cands else None
        for i, c in enumerate(cands):
            if any(j != i for j in cpts.query(c["geom"], predicate="contains")):
                tier2_drops["parent of smaller areas"] += 1  # its children are kept instead, so nothing is drawn twice
                continue
            name = c["name"]
            if GENERIC_AREA.match(name) or len(name) <= 4:
                ctx, _ = nearest_locality(c["lat"], c["lon"], None, 2.0)
                if ctx is None:
                    tier2_drops["generic name, no locality context"] += 1
                    continue
                name = f"{name}, {ctx['name']}"
            if AREA_EXCLUDE.search(name):  # e.g. a generic block name whose locality turned out to be an industrial area
                tier2_drops["informal or industrial once its locality is added"] += 1
                continue
            tier2.append(dict(c, display=name, digits=5, cap=60, tall=False))
        print("tier 2 residential areas:", len(tier2), "| dropped:", dict(tier2_drops))

    wanted = [f for f in apt_features if f["id"] in {p["id"] for p in parcels}] + [c for c in colony_pick.values() if c is not None] + tier2
    wanted = list({id(w): w for w in wanted}.values())
    if wanted:
        # a named apartment building inside a colony keeps its own entry; the colony must not draw it again
        read_footprints(args.pbf, wanted, exclude=[f["geom"] for f in apt_features if f["id"] not in {p["id"] for p in parcels}])

    # --- societies: apartments
    shapes = []
    for f in apt_features:
        loc, dist = nearest_locality(f["lat"], f["lon"], "apartment")
        air, aq = air_for(f["lat"], f["lon"], monitors, radius_km, bands, severity)
        t = f["tags"]
        is_parcel = f in parcels
        sid = "a" + f["id"]
        note = "Name, outline and height from OpenStreetMap."
        if loc:
            note += f" Rents are locality medians ({loc['name']}, {dist:.1f} km away), not this building's own listings."
        else:
            note += " No rent data within 1.5 km."
        osm_url = f"https://www.openstreetmap.org/{'way' if f['id'][0] == 'w' else 'relation'}/{f['id'][1:]}"
        with_buildings = (not is_parcel) or bool(f.get("footprints"))
        shape_note = ("Society boundary and buildings from OpenStreetMap." if is_parcel and f.get("footprints")
                      else "Society boundary from OpenStreetMap; its buildings are not mapped there." if is_parcel
                      else "Building outline and height from OpenStreetMap (height is a default where not mapped).")
        s = make_society(sid, f["name"], "apartment", f["lat"], f["lon"], loc, dist if loc else None,
                         "osm" if with_buildings else "osm-site", note, air, aq,
                         nearby_for(f["lat"], f["lon"], trees), "Apartment building or housing society (OpenStreetMap)", osm_url, shape_note)
        societies.append(s)
        ring = ring_of(f["geom"])
        shapes.append(dict(type="Feature", properties=dict(sid=sid, role="site", aq=aq), geometry=dict(type="Polygon", coordinates=[ring])))
        if is_parcel and f.get("footprints"):
            for fpr in sorted(f["footprints"], key=lambda z: -z["area"])[:120]:
                shapes.append(dict(type="Feature", properties=dict(sid=sid, role="bld", h=fpr["h"], shape="osm", aq=aq),
                                   geometry=dict(type="Polygon", coordinates=[fpr["ring"]])))
        elif not is_parcel:
            shapes.append(dict(type="Feature", properties=dict(sid=sid, role="bld", h=height_of(t, 15.0), shape="osm", aq=aq),
                               geometry=dict(type="Polygon", coordinates=[ring])))
        events.append(dict(sid=sid, step="Located on map", finding=f"{s['locality'] or 'Delhi'} · {f['lat']:.4f}, {f['lon']:.4f}", url=osm_url))
        if loc and s["prices"]:
            first = next(iter(s["prices"].items()))
            events.append(dict(sid=sid, step="Locality rents matched", finding=f"{loc['name']} · {first[0]} BHK median ₹{first[1]['rent']['median']:,.0f}/mo (n={first[1]['rent']['n']})", url=RENT_DATASET))

    # --- societies: builder-floor colonies
    for k, l in floor_locs:
        c = colony_pick[k]
        sid = "c" + re.sub(r"[^a-z0-9]+", "-", k).strip("-")
        if c is not None:
            ring, shape_kind = ring_of(c["geom"]), "osm" if c.get("footprints") else "osm-site"
        else:
            ring, shape_kind = circle(l["lon"], l["lat"]), "generated"
        air, aq = air_for(l["lat"], l["lon"], monitors, radius_km, bands, severity)
        note = (f"Builder-floor rents are medians of {sum(v['n'] for (kk, _), v in l['buckets'].items() if kk == 'builder floor')} "
                f"listings in {l['name']} ({RENT_COLLECTED}). " +
                ("Outline from OpenStreetMap." if c is not None else "Approximate area, centred on the average position of the listings."))
        shape_note = {"osm": "Colony outline and buildings from OpenStreetMap.", "osm-site": "Colony outline from OpenStreetMap; its buildings are not mapped there.",
                      "generated": "Approximate circle at the average position of this locality's listings, not a real boundary."}[shape_kind]
        s = make_society(sid, l["name"] + " (builder floors)", "builder floor", l["lat"], l["lon"], l, 0.0, shape_kind, note, air, aq,
                         nearby_for(l["lat"], l["lon"], trees), "Independent builder floors in this colony",
                         f"https://www.openstreetmap.org/#map=16/{l['lat']:.5f}/{l['lon']:.5f}", shape_note)
        societies.append(s)
        shapes.append(dict(type="Feature", properties=dict(sid=sid, role="site", aq=aq), geometry=dict(type="Polygon", coordinates=[ring])))
        if c is not None and c.get("footprints"):
            for fpr in sorted(c["footprints"], key=lambda z: -z["area"])[:150]:
                shapes.append(dict(type="Feature", properties=dict(sid=sid, role="bld", h=fpr["h"], shape="osm", aq=aq),
                                   geometry=dict(type="Polygon", coordinates=[fpr["ring"]])))
        events.append(dict(sid=sid, step="Locality rents matched", finding=f"{l['name']} · builder floors, {sum(v['n'] for (kk, _), v in l['buckets'].items() if kk == 'builder floor')} listings", url=RENT_DATASET))

    # --- more: tier 2 residential areas and tier 3 clusters of unnamed apartment buildings
    more = Counter()
    if args.more:
        for c in tier2:
            lat, lon = c["lat"], c["lon"]
            loc, dist = nearest_locality(lat, lon, "builder floor", BORROW_KM)
            air, aq = air_for(lat, lon, monitors, radius_km, bands, severity)
            sid = "q" + c["id"]  # "q" + OSM id: cannot collide with locality slugs or other prefixes
            fps = sorted(c.get("footprints", []), key=lambda z: -z["area"])[:60]
            osm_url = f"https://www.openstreetmap.org/{'way' if c['id'][0] == 'w' else 'relation'}/{c['id'][1:]}"
            note = ("Residential area from OpenStreetMap; its housing type is not mapped there. "
                    + (f"Rents shown are builder-floor medians of listings in {loc['name']} ({dist:.1f} km away, {RENT_COLLECTED}), not this area's own listings."
                       if loc else f"No rent data within {BORROW_KM:g} km."))
            shape_note = ("Residential area outline and buildings from OpenStreetMap." if fps
                          else "Residential area outline from OpenStreetMap; its buildings are not mapped there.")
            s = make_society(sid, c["display"], "builder floor", lat, lon, loc, dist if loc else None, "osm" if fps else "osm-site", note, air, aq,
                             nearby_for(lat, lon, trees), "Residential area · housing type not mapped (OpenStreetMap)", osm_url, shape_note)
            societies.append(s)
            shapes.append(dict(type="Feature", properties=dict(sid=sid, role="site", aq=aq), geometry=dict(type="Polygon", coordinates=[ring_of(c["geom"], 5)])))
            for fpr in fps:
                shapes.append(dict(type="Feature", properties=dict(sid=sid, role="bld", h=fpr["h"], shape="osm", aq=aq),
                                   geometry=dict(type="Polygon", coordinates=[fpr["ring"]])))
            events.append(dict(sid=sid, step="Located on map", finding=f"{s['locality'] or 'Delhi'} · {lat:.4f}, {lon:.4f}", url=osm_url))
            more["residential areas"] += 1
            more["residential areas with borrowed rents"] += 1 if s["prices"] else 0

        chosen = [f["geom"] for f in apt_features] + [c["geom"] for c in colony_pick.values() if c is not None] + [c["geom"] for c in tier2]
        inside_tree = STRtree(chosen)
        free = [u for u in found["unnamed_res"] if not len(inside_tree.query(Point(u["lon"], u["lat"]), predicate="within"))]
        more["unnamed apartment/residential buildings outside existing entries"] = len(free)
        used_ids = {s["id"] for s in societies}
        for members in cluster_buildings(free, 80):
            if len(members) < 2 and members[0]["area_m2"] < 400:
                more["clusters dropped: a single small building"] += 1
                continue
            lat, lon = statistics.fmean(m["lat"] for m in members), statistics.fmean(m["lon"] for m in members)
            housenames = Counter(m["tags"].get("addr:housename") for m in members if m["tags"].get("addr:housename"))
            streets = Counter(m["tags"].get("addr:street") for m in members if m["tags"].get("addr:street"))
            loc, dist = nearest_locality(lat, lon, "apartment", BORROW_KM)
            ctx = loc or nearest_locality(lat, lon, None, 1.5)[0]
            if housenames:
                name = housenames.most_common(1)[0][0]
            elif streets:
                name = f"Apartments on {streets.most_common(1)[0][0]}"
            elif ctx:
                name = f"Apartments near {ctx['name']}"
            else:
                more["clusters dropped: no name or locality context"] += 1
                continue
            sid = f"ac{round(lon * 1e4)}{round(lat * 1e4)}"
            if sid in used_ids:
                continue
            used_ids.add(sid)
            members.sort(key=lambda m: -m["area_m2"])
            hull = unary_union([m["geom"] for m in members[:80]]).convex_hull.buffer(0.00012)
            if hull.geom_type != "Polygon":
                continue
            air, aq = air_for(lat, lon, monitors, radius_km, bands, severity)
            note = ("Apartment buildings from OpenStreetMap that carry no name there; grouped when within 80 m of each other. "
                    + (f"Rents shown are apartment medians of listings in {loc['name']} ({dist:.1f} km away, {RENT_COLLECTED}), not these buildings' own listings."
                       if loc else f"No rent data within {BORROW_KM:g} km."))
            s = make_society(sid, name, "apartment", lat, lon, loc, dist if loc else None, "osm", note, air, aq, nearby_for(lat, lon, trees),
                             f"Group of {len(members)} apartment building{'s' if len(members) > 1 else ''} (unnamed in OpenStreetMap)",
                             f"https://www.openstreetmap.org/#map=18/{lat:.5f}/{lon:.5f}",
                             "Building outlines and heights from OpenStreetMap (height is a default where not mapped); the site outline is their convex hull.")
            societies.append(s)
            shapes.append(dict(type="Feature", properties=dict(sid=sid, role="site", aq=aq), geometry=dict(type="Polygon", coordinates=[ring_of(hull, 5)])))
            for m in members[:60]:
                shapes.append(dict(type="Feature", properties=dict(sid=sid, role="bld", h=height_of(m["tags"], 15.0), shape="osm", aq=aq),
                                   geometry=dict(type="Polygon", coordinates=[ring_of(m["geom"], 5)])))
            events.append(dict(sid=sid, step="Located on map", finding=f"{s['locality'] or 'Delhi'} · {lat:.4f}, {lon:.4f}", url=s["url"]))
            more["apartment clusters"] += 1
            more["apartment clusters with borrowed rents"] += 1 if s["prices"] else 0
        print("more:", dict(more))

    # Repeated names (five "DDA Flats", fourteen "Apartments near ...") get their locality, then a group number,
    # so the results list and search stay usable.
    by_name = defaultdict(list)
    for s in societies:
        by_name[s["name"]].append(s)
    for name, group in by_name.items():
        if len(group) < 2:
            continue
        for s in group:
            if s["locality"] and s["locality"].lower() not in name.lower():
                s["name"] = f"{name}, {s['locality']}"
        again = defaultdict(list)
        for s in group:
            again[s["name"]].append(s)
        for nm, grp in again.items():
            if len(grp) > 1:
                for k, s in enumerate(sorted(grp, key=lambda z: (z["lat"], z["lng"])), 1):
                    s["name"] = f"{nm} · group {k}"

    # no footprint may be drawn under two entries, and ids must be unique
    ids = Counter(s["id"] for s in societies)
    assert all(v == 1 for v in ids.values()), f"duplicate ids: {[k for k, v in ids.items() if v > 1][:5]}"
    owner, cross, same = {}, 0, 0
    for f in shapes:
        if f["properties"]["role"] == "bld":
            ring = f["geometry"]["coordinates"][0]
            key = (round(sum(p[0] for p in ring) / len(ring), 5), round(sum(p[1] for p in ring) / len(ring), 5))
            if key in owner and owner[key] != f["properties"]["sid"]:
                cross += 1
            elif key in owner:
                same += 1  # the same building mapped twice in OpenStreetMap, inside one entry: harmless
            owner[key] = f["properties"]["sid"]
    print(f"footprints: {sum(1 for f in shapes if f['properties']['role'] == 'bld'):,} | drawn under two different entries: {cross} | doubled within one entry: {same}")
    assert cross == 0, "a building outline would be drawn under two entries"

    # --- write
    with_rent = [s for s in societies if s["prices"]]
    counts = dict(listed=len(societies), on_map=len(societies), not_located=0, ai_read=0, for_sale=0, for_rent=len(rents), verified=0,
                  apartments=sum(1 for s in societies if s["kind"] == "apartment"), colonies=sum(1 for s in societies if s["kind"] == "builder floor"),
                  residential_areas=more["residential areas"], apartment_clusters=more["apartment clusters"], dense=bool(args.more),
                  with_rent=len(with_rent), rent_rows_dropped=sum(drops.values()),
                  with_pm25=sum(1 for s in societies if s["air"]))
    ui = dict(
        modes=["rent"], hide_example=True, default_kinds=["apartment", "builder floor"], rent_as_of=RENT_COLLECTED,
        onboarding=[
            ["Every building and colony in Delhi", f"{counts['on_map']:,} apartment buildings, colonies and other mapped residential areas from OpenStreetMap, with rents by BHK from an open dataset ({RENT_COLLECTED}, borrowed from the nearest locality where needed) and indicative PM2.5 from the nearest air monitor. There are no sale prices for Delhi."],
            ["Start with what you cannot live without", "Set your monthly rent budget and the BHK you need. Add what you want nearby, like a park within 500 m."],
            ["How to read the map", "Brighter buildings fit your search and faint ones are not checked yet. The PM2.5 button colours every building by the nearest air monitor instead. Rents are locality medians, not the building's own listings."],
            ["Open a building, keep a list", "Click any building for rents by BHK, what is nearby and PM2.5. Star the ones you like. Export your results as a CSV any time."],
        ],
        note=f"{counts['on_map']:,} buildings and colonies · {len(rents):,} rent listings from {RENT_COLLECTED} (open dataset) · no sale prices",
        about_prices=(f"<b>Rents are locality medians from an open dataset collected in {RENT_COLLECTED}</b>, about six years old, so today's rents are higher. "
                      "The dataset places listings at locality level, so every building shows the median for its nearest locality and property type "
                      "(apartment listings for apartments, builder-floor listings for colonies), not its own listings. There are no sale prices for Delhi. "
                      "The dataset is declared CC0 by its uploader; its listings were originally taken from a real-estate website." + (MORE_NOTE if args.more else "")),
        more_note=MORE_NOTE if args.more else "",
        price_heading="Rent (locality median)",
        source_label="OpenStreetMap",
        source_url=OSM_SOURCE,
        page_description="Delhi apartment buildings and builder-floor colonies on one map, with locality rents by BHK (open data, August 2020) and PM2.5 readings.",
        neighbourhood_blurb="Compare neighbourhoods on the property map. Scores and these properties both cover Delhi.",
        air=dict(fetched=fetched, radius_km=radius_km, bands=[dict(upper=u, label=lb, color=c) for u, lb, c in bands],
                 note="Indicative PM2.5 from the nearest monitor within %d km, as last cached from data.gov.in. Not an official AQI; it may be days old." % radius_km))
    doc = dict(city=dict(id="delhi", name="Delhi", center=CENTER, zoom=ZOOM), price_model={}, room_model={"n": 0}, counts=counts,
               sources=["OpenStreetMap contributors (ODbL)", f"New Delhi rental listings, OpenML 43837 (CC0 declared; collected {RENT_COLLECTED})",
                        "Localytics: nearby places and cached PM2.5 (data.gov.in)", "Delhi boundary: DataMeet Municipal Spatial Data (CC BY-SA 2.5 India)"],
               ui=ui, societies=societies, events=events)
    (out / "delhi.json").write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    (out / "delhi-shapes.geojson").write_text(json.dumps(dict(type="FeatureCollection", features=shapes), separators=(",", ":")), encoding="utf-8")
    details = {s["id"]: dict(description=s["note"], ratings={}, reviews=[], images=[], trend=[]) for s in societies}
    (out / "delhi-details.json").write_text(json.dumps(details, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    with (out / "delhi-societies.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "kind", "locality", "lat", "lng", "rent_basis_km", "pm25", "pm25_label", "pm25_monitor", "pm25_km", "pm25_updated"]
                   + [f"rent_{b}bhk_{c}" for b in range(1, 6) for c in ("median", "min", "max", "n")])
        for s in societies:
            a = s["air"] or {}
            row = [s["id"], s["name"], s["kind"], s["locality"], s["lat"], s["lng"], s["rent_km"], a.get("pm"), a.get("label"), a.get("monitor"), a.get("km"), a.get("updated")]
            for b in range(1, 6):
                r = s["prices"].get(str(b), {}).get("rent", {})
                row += [r.get("median"), r.get("min"), r.get("max"), r.get("n")]
            w.writerow(row)
    with (out / "delhi-units.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["society_id", "name", "kind", "bhk", "typical_size_sqft_in_locality", "rent_median", "rent_n", "basis"])
        for s in societies:
            for u in s["unit_types"]:
                r = s["prices"][str(u["bhk"])]["rent"]
                w.writerow([s["id"], s["name"], s["kind"], u["bhk"], u["size_sqft"], r["median"], r["n"], r["basis"]])
    # merge into cities.json without dropping other cities
    cj = out / "cities.json"
    cities = json.loads(cj.read_text(encoding="utf-8")) if cj.exists() else {}
    cities["delhi"] = dict(name="Delhi (open data · rent)")
    cj.write_text(json.dumps(cities, ensure_ascii=False), encoding="utf-8")

    print("\n=== RESULT ===")
    print(json.dumps(counts, indent=1))
    miss = [s for s in societies if s["kind"] == "apartment" and not s["prices"]]
    print(f"apartments with no rent data within {MAX_RENT_KM} km: {len(miss)}")
    print("shape features:", len(shapes), "| files:", {p.name: round(p.stat().st_size / 1e6, 2) for p in out.glob("delhi*")})
    print("built", datetime.now(timezone.utc).isoformat())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pbf", required=True)
    ap.add_argument("--rents", required=True)
    ap.add_argument("--localytics", required=True, help="path to your Localytics checkout")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "web" / "public" / "data"))
    ap.add_argument("--more", action="store_true", help="also add other named residential areas and clusters of unnamed apartment buildings (denser map)")
    build(ap.parse_args())
