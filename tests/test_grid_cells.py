import json
import sqlite3
import sys
from pathlib import Path

import pytest
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform, unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import grid_cells  # noqa: E402

DB = ROOT / "data" / "areas.sqlite"
FORWARD = Transformer.from_crs(4326, 32643, always_xy=True).transform
REVERSE = Transformer.from_crs(32643, 4326, always_xy=True).transform


@pytest.fixture(scope="module")
def world():
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as db:
        rows = [json.loads(r[0]) for r in db.execute("SELECT payload FROM facilities ORDER BY id")]
        manifest = json.loads(db.execute("SELECT value FROM metadata WHERE key='manifest'").fetchone()[0])
        stored = {r[0]: json.loads(r[1]) for r in db.execute("SELECT id, payload FROM cells")}
    trees, catrows = grid_cells.index_rows(rows)
    bounds = [b for s in manifest["sources"] for b in s["bounds"]]
    return stored, trees, catrows, bounds


def projected(path):
    features = json.loads(Path(path).read_text(encoding="utf-8"))["features"]
    return transform(FORWARD, unary_union([shape(f["geometry"]) for f in features]))


def normal(value):
    """Floats rounded to 9 places (the stored cells differ from a rebuild at the 15th) and equally distant facilities in a fixed order."""
    if isinstance(value, float):
        return round(value, 9)
    if isinstance(value, list):
        items = [normal(v) for v in value]
        return sorted(items, key=lambda v: (v["km"], v["osm"])) if items and isinstance(items[0], dict) and "osm" in items[0] else items
    if isinstance(value, dict):
        return {k: normal(v) for k, v in value.items()}
    return value


def test_delhi_cells_regenerate_identically_from_the_stored_facilities(world):
    """The shared cell code must reproduce the cells the Delhi build stored, or Gurugram would be scored differently from Delhi."""
    stored, trees, catrows, bounds = world
    delhi = projected(ROOT / "data" / "delhi_boundary.geojson")
    ids = sorted(i for i in stored if i.startswith("DL43_"))
    for cell_id in ids[::150]:  # about ten cells spread across the city
        _, x, y = cell_id.split("_")
        again = grid_cells.build_cell("DL43", int(x) * 1000, int(y) * 1000, delhi, REVERSE, trees, catrows, bounds)
        assert again is not None, cell_id
        assert normal(json.loads(json.dumps(again))) == normal(stored[cell_id]), cell_id


def test_gurugram_cells_exist_and_have_the_same_shape_as_delhi(world):
    stored, *_ = world
    gurugram = {i: c for i, c in stored.items() if i.startswith("GG43_")}
    delhi = {i: c for i, c in stored.items() if i.startswith("DL43_")}
    assert len(delhi) == 1487
    assert len(gurugram) > 1000, "run scripts/add_gurugram_cells.py first"
    sample_d, sample_g = next(iter(delhi.values())), next(iter(gurugram.values()))
    assert set(sample_g) == set(sample_d)
    assert set(sample_g["features"]) == {"1", "2", "5"}
    assert set(sample_g["features"]["2"]) == set(sample_d["features"]["2"])  # the same nine facility categories


def test_gurugram_cells_lie_in_gurugram_and_never_overlap_delhi_cells(world):
    stored, *_ = world
    gurugram = [c for i, c in stored.items() if i.startswith("GG43_")]
    assert all(28.15 < c["lat"] < 28.6 and 76.6 < c["lon"] < 77.3 for c in gurugram)
    delhi_xy = {tuple(i.split("_")[1:]) for i in stored if i.startswith("DL43_")}
    gurugram_xy = {tuple(i.split("_")[1:]) for i in stored if i.startswith("GG43_")}
    assert not delhi_xy & gurugram_xy  # one grid square belongs to one city
    assert len(gurugram_xy) == len([i for i in stored if i.startswith("GG43_")])
    # and the shared coordinate grid is the same one Delhi uses: whole kilometres in EPSG:32643
    assert all(int(x) == float(x) and int(y) == float(y) for x, y in gurugram_xy)
