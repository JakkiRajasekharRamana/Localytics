"""Shared OSM classification, version-aware merging and coordinate extraction."""

import hashlib
import math
from collections import Counter

import osmium

from geography import consolidate_named


def classify_transport(t):
    if t.get("aeroway") == "terminal":
        return "airport_terminal"
    if t.get("aeroway") == "aerodrome":
        return "airport"
    if t.get("railway") == "subway_entrance":
        return "metro_entrance"
    if (t.get("railway") in ("station", "halt") or t.get("public_transport") == "station") and (
        t.get("station") == "subway" or t.get("subway") == "yes"
    ):
        return "metro_station"
    if (
        t.get("highway") == "bus_stop"
        or t.get("amenity") == "bus_station"
        or (
            t.get("public_transport") in ("platform", "stop_position", "station")
            and t.get("bus") == "yes"
        )
    ):
        return "bus_stop"
    if t.get("railway") in ("station", "halt"):
        return "railway_station"
    return None


def classify(t):
    if t.get("access") in ("private", "no") or t.get("disused") == "yes":
        return None
    cat = classify_transport(t)
    if cat in ("bus_stop", "metro_station", "airport_terminal"):
        return cat
    if t.get("amenity") == "school":
        return "school"
    if t.get("amenity") == "hospital" or t.get("healthcare") == "hospital":
        return "hospital"
    if t.get("leisure") in ("park", "garden") and t.get("access") not in ("customers", "members"):
        return "park"
    if t.get("leisure") == "fitness_centre":
        return "gym"
    if t.get("shop") == "mall":
        return "mall"
    if t.get("amenity") == "charging_station" and t.get("access") not in ("customers", "members"):
        return "ev"
    if t.get("place") in ("suburb", "neighbourhood", "quarter", "village", "town"):
        return "locality"
    return None


def extract_sources(sources, classifier=classify, *, consolidate=True):
    merged, duplicates, invalid = {}, 0, 0
    manifest = []
    source_counts = {}
    for source in sources:
        reader = osmium.io.Reader(str(source))
        header = reader.header()
        bounds = []
        for b in [header.box()]:
            bounds.append([b.bottom_left.lon, b.bottom_left.lat, b.top_right.lon, b.top_right.lat])
        reader.close()
        digest = hashlib.sha256()
        with source.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        manifest.append(dict(file=source.name, sha256=digest.hexdigest(), bounds=bounds))
        processor = osmium.FileProcessor(
            str(source), entities=osmium.osm.NODE | osmium.osm.WAY
        ).with_locations("flex_mem")
        processor.with_filter(
            osmium.filter.KeyFilter(
                "amenity",
                "healthcare",
                "leisure",
                "shop",
                "place",
                "highway",
                "railway",
                "public_transport",
                "aeroway",
            )
        )
        count = 0
        for obj in processor:
            tags = dict(obj.tags)
            category = classifier(tags)
            if not category:
                continue
            try:
                if obj.is_node():
                    lat, lon = obj.location.lat, obj.location.lon
                    kind, method = "node", "mapped_point"
                else:
                    coords = [(n.lat, n.lon) for n in obj.nodes]
                    if not coords:
                        continue
                    lat = (min(p[0] for p in coords) + max(p[0] for p in coords)) / 2
                    lon = (min(p[1] for p in coords) + max(p[1] for p in coords)) / 2
                    kind, method = "way", "approximate_bbox_center"
                if not (math.isfinite(lat) and math.isfinite(lon)):
                    continue
            except osmium.InvalidLocationError:
                invalid += 1
                continue
            count += 1
            key = (kind, obj.id)
            row = dict(
                osm_type=kind,
                osm_id=obj.id,
                version=obj.version,
                timestamp=str(obj.timestamp),
                category=category,
                name=tags.get("name:en")
                or tags.get("name")
                or (tags.get("ref") if classifier is classify_transport else None)
                or "Unnamed",
                lat=lat,
                lon=lon,
                method=method,
                tags=tags,
                sources=[source.name],
            )
            old = merged.get(key)
            if old:
                duplicates += 1
                row["sources"] = sorted(set(old["sources"] + [source.name]))
                if (old["version"], old["timestamp"]) > (row["version"], row["timestamp"]):
                    old["sources"] = row["sources"]
                    continue
            merged[key] = row
        source_counts[source.name] = count
        print(f"{source.name}: {count} matching objects", flush=True)
    rows = sorted(merged.values(), key=lambda r: (r["osm_type"], r["osm_id"]))
    unique = consolidate_named(rows) if consolidate else rows
    consolidated = len(rows) - len(unique)
    rows = unique
    return rows, dict(
        sources=manifest,
        source_feature_counts=source_counts,
        overlap_removed=duplicates,
        physical_candidates_merged=consolidated,
        invalid=invalid,
        counts=dict(Counter(r["category"] for r in rows)),
    )
