"""Add Gurugram district's one-kilometre cells to the area database, built from the facilities already stored in it.

usage (from the Localytics folder):
    python scripts/add_gurugram_cells.py

The cells are made by the same code as Delhi's (grid_cells.py), on the same kilometre grid, from the same facility table (the OpenStreetMap
extract that covers both cities), so a Gurugram cell and a Delhi cell are scored exactly alike. They are stored as `GG43_*` rows next to the
`DL43_*` Delhi rows. Delhi's cells, `built_at`, the clustering report and the evaluation report are left untouched; the Flask and Flet apps keep
reading Delhi only unless a client asks for Gurugram too (`AreaRepository.dataset(include_gurugram=True)`).

Safe to re-run: existing GG43 cells are replaced. Back up data/areas.sqlite first if you want a way back.
"""

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
from grid_cells import grid_cells, index_rows  # noqa: E402

PREFIX = "GG43"
NOTE = ("Gurugram cells were added after the Delhi build, from the same stored facilities and the OpenStreetMap Gurugram district boundary; "
        "no clustering or sensitivity analysis was run on them.")


def add(db_path, boundary_path):
    forward = Transformer.from_crs(4326, 32643, always_xy=True).transform
    reverse = Transformer.from_crs(32643, 4326, always_xy=True).transform
    boundary = unary_union([shape(f["geometry"]) for f in json.loads(boundary_path.read_text(encoding="utf-8"))["features"]])
    if not boundary.is_valid:
        raise ValueError("Gurugram boundary geometry is invalid")
    projected = transform(forward, boundary)
    area = projected.area / 1e6
    if not 1100 < area < 1400:
        raise ValueError(f"Unexpected Gurugram district area: {area:.0f} km2")
    with sqlite3.connect(db_path) as db:
        rows = [json.loads(r[0]) for r in db.execute("SELECT payload FROM facilities ORDER BY id")]
        meta = json.loads(db.execute("SELECT value FROM metadata WHERE key='manifest'").fetchone()[0])
        delhi_squares = {tuple(int(v) * 1000 for v in r[0].split("_")[1:]) for r in db.execute("SELECT id FROM cells WHERE id LIKE 'DL43\\_%' ESCAPE '\\'")}
        if not delhi_squares:
            raise ValueError("No Delhi cells found: is this the right database?")
        bounds = [b for s in meta["sources"] for b in s["bounds"]]
        trees, catrows = index_rows(rows, named_localities=True)
        cells = grid_cells(PREFIX, projected, reverse, trees, catrows, bounds, skip=delhi_squares)
        db.execute("DELETE FROM cells WHERE id LIKE 'GG43\\_%' ESCAPE '\\'")
        db.executemany(
            "INSERT INTO cells VALUES (?,?,?,?,?)",
            [(c["id"], c["lat"], c["lon"], c["label"], json.dumps(c)) for c in cells],
        )
        meta["gurugram"] = dict(
            cells=len(cells),
            boundary_area_km2=area,
            boundary_source="https://www.openstreetmap.org/relation/3577685",
            boundary_license="ODbL 1.0, (c) OpenStreetMap contributors",
            boundary_sha256=hashlib.sha256(boundary_path.read_bytes()).hexdigest(),
            added_at=datetime.now(timezone.utc).isoformat(),
            cell_prefix=PREFIX,
        )
        meta["limitations"] = [x for x in meta["limitations"] if not x.startswith("Gurugram cells were added")] + [NOTE]
        db.execute("UPDATE metadata SET value=? WHERE key='manifest'", (json.dumps(meta),))
    (db_path.parent / "area_manifest.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return cells, meta


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "areas.sqlite")
    parser.add_argument("--boundary", type=Path, default=ROOT / "data" / "gurugram_boundary.geojson")
    args = parser.parse_args()
    cells, meta = add(args.db, args.boundary)
    print(f"Added {len(cells)} Gurugram cells ({meta['gurugram']['boundary_area_km2']:.0f} km2 district) next to Delhi's {meta['cell_count']}.")
