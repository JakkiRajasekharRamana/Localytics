"""Extract transport using the shared OSM pipeline. Run: python connectivity/extract_transport.py file.pbf."""

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from osm_data import classify_transport, extract_sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pbf", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, default=ROOT / "connectivity")
    args = parser.parse_args()
    rows, meta = extract_sources(args.pbf, classify_transport, consolidate=False)
    args.output.mkdir(parents=True, exist_ok=True)
    fields = [
        "osm_type",
        "osm_id",
        "category",
        "name",
        "latitude",
        "longitude",
        "coordinate_method",
        "operator",
        "network",
        "tags_json",
        "osm_version",
        "osm_timestamp",
        "source_files",
    ]
    csv_rows = []
    features = []
    for row in rows:
        tags = row["tags"]
        properties = dict(
            osm_type=row["osm_type"],
            osm_id=row["osm_id"],
            category=row["category"],
            name=row["name"],
            coordinate_method=row["method"],
            operator=tags.get("operator", ""),
            network=tags.get("network", ""),
            osm_version=row["version"],
            osm_timestamp=row["timestamp"],
            source_files=";".join(row["sources"]),
        )
        csv_rows.append(
            dict(
                properties,
                latitude=row["lat"],
                longitude=row["lon"],
                tags_json=json.dumps(tags, ensure_ascii=False),
            )
        )
        features.append(
            dict(
                type="Feature",
                geometry=dict(type="Point", coordinates=[row["lon"], row["lat"]]),
                properties=dict(properties, osm_tags=tags),
            )
        )
    with (args.output / "transport_locations.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(csv_rows)
    (args.output / "transport_locations.geojson").write_text(
        json.dumps(dict(type="FeatureCollection", features=features), ensure_ascii=False),
        encoding="utf-8",
    )
    metadata = dict(
        source_files=[s["file"] for s in meta["sources"]],
        source_header_bounds=[
            dict(file=s["file"], bounds=b) for s in meta["sources"] for b in s["bounds"]
        ],
        source_feature_counts=meta["source_feature_counts"],
        overlap_duplicates_removed=meta["overlap_removed"],
        deduplication="OSM type + ID; highest object version/timestamp wins; later input wins ties",
        extracted_at_utc=datetime.now(timezone.utc).isoformat(),
        counts=meta["counts"],
        invalid_features=meta["invalid"],
        limitations=[
            "Nodes/ways only; relation-only facilities may be absent.",
            "Mapped objects can represent parts of the same physical facility.",
            "Way positions are approximate bounding-box centres.",
            "Airport passenger service and OSM completeness are unverified.",
        ],
        attribution="© OpenStreetMap contributors, ODbL: https://www.openstreetmap.org/copyright",
    )
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
