"""Rebuild offline area data: python scripts/build_areas.py file1.pbf file2.pbf."""

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform, unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from grid_cells import grid_cells, index_rows
from osm_data import extract_sources


def build(sources, output, boundary_path):
    output.parent.mkdir(exist_ok=True, parents=True)
    rows, meta = extract_sources(sources)
    forward = Transformer.from_crs(4326, 32643, always_xy=True).transform
    reverse = Transformer.from_crs(32643, 4326, always_xy=True).transform
    features = json.loads(boundary_path.read_text())["features"]
    boundary = unary_union([shape(f["geometry"]) for f in features])
    if not boundary.is_valid:
        raise ValueError("Boundary geometry is invalid")
    projected = transform(forward, boundary)
    area = projected.area / 1e6
    if not 1300 < area < 1700:
        raise ValueError(f"Unexpected Delhi boundary area: {area}")
    meta.update(
        boundary_area_km2=area,
        boundary_source="https://github.com/datameet/Municipal_Spatial_Data/tree/master/Delhi",
        boundary_license="CC BY-SA 2.5 India",
        boundary_sha256=hashlib.sha256(boundary_path.read_bytes()).hexdigest(),
        built_at=datetime.now(timezone.utc).isoformat(),
        crs="EPSG:32643",
        cell_metres=1000,
        limitations=[
            "Boundary is a community-published reference, not a legal boundary.",
            "Nodes and ways only; relation-only features may be absent.",
            "Counts are mapped facilities, not proof of actual service availability.",
            "Unknown access is retained and disclosed; private/no access excluded.",
            "EV connector and airport passenger service are unverified.",
            "Grid cells do not imply residential suitability or land-use permission.",
        ],
    )
    bounds = [b for s in meta["sources"] for b in s["bounds"]]
    trees, catrows = index_rows(rows)
    cells = grid_cells("DL43", projected, reverse, trees, catrows, bounds)
    meta["cell_count"] = len(cells)
    temp = output.with_suffix(".tmp")
    if temp.exists():
        temp.unlink()
    with sqlite3.connect(temp) as db:
        db.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        db.execute("INSERT INTO metadata VALUES (?,?)", ("manifest", json.dumps(meta)))
        db.execute(
            "CREATE TABLE cells (id TEXT PRIMARY KEY,lat REAL,lon REAL,label TEXT,payload TEXT)"
        )
        db.executemany(
            "INSERT INTO cells VALUES (?,?,?,?,?)",
            [(c["id"], c["lat"], c["lon"], c["label"], json.dumps(c)) for c in cells],
        )
        db.execute(
            "CREATE VIRTUAL TABLE facility_index USING rtree(id,min_lon,max_lon,min_lat,max_lat)"
        )
        db.execute(
            "CREATE TABLE facilities (id INTEGER PRIMARY KEY,category TEXT,name TEXT,payload TEXT)"
        )
        for i, r in enumerate(rows):
            db.execute(
                "INSERT INTO facilities VALUES (?,?,?,?)",
                (i, r["category"], r["name"], json.dumps(r)),
            )
            db.execute(
                "INSERT INTO facility_index VALUES (?,?,?,?,?)",
                (i, r["lon"], r["lon"], r["lat"], r["lat"]),
            )
        db.execute("CREATE TABLE air_cache (query TEXT PRIMARY KEY,fetched_at TEXT,payload TEXT)")
    temp.replace(output)
    (output.parent / "area_manifest.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pbf", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "areas.sqlite")
    parser.add_argument("--boundary", type=Path, default=ROOT / "data" / "delhi_boundary.geojson")
    args = parser.parse_args()
    build(args.pbf, args.output, args.boundary)
