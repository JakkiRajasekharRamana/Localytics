import csv
import json

from config import TRANSPORT_DIR


def test_merged_overlap_accounting():
    folder = TRANSPORT_DIR
    metadata = json.loads((folder / "metadata.json").read_text())
    with (folder / "transport_locations.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    identities = [(r["osm_type"], r["osm_id"]) for r in rows]
    assert len(identities) == len(set(identities))
    assert set(metadata["source_files"]) == {"delhi.pbf", "other1.pbf"}
    assert sum(metadata["source_feature_counts"].values()) - metadata[
        "overlap_duplicates_removed"
    ] == len(rows)
    assert metadata["overlap_duplicates_removed"] > 0
    assert any(";" in r["source_files"] for r in rows)
    assert any(r["source_files"] == "other1.pbf" for r in rows)
