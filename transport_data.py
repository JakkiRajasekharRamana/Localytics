"""Load transport records and validated source extents for all map views."""

import csv
import json
import math
from pathlib import Path

from config import TRANSPORT_DIR
from geography import coordinates


def load_transport(path=None, *, optional=False):
    path = Path(path) if path else TRANSPORT_DIR / "transport_locations.csv"
    rows = []
    try:
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                try:
                    lat, lon = coordinates(row["latitude"], row["longitude"])
                except (KeyError, ValueError, TypeError):
                    continue
                row.update(latitude=lat, longitude=lon)
                rows.append(row)
    except (OSError, UnicodeError, csv.Error):
        if not optional:
            raise
        return []
    return rows


def source_bounds(path=None):
    path = Path(path) if path else TRANSPORT_DIR / "metadata.json"
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
        bounds = [item["bounds"] for item in metadata["source_header_bounds"]]
        return [
            b
            for b in bounds
            if isinstance(b, list)
            and len(b) == 4
            and all(isinstance(v, (int, float)) and math.isfinite(v) for v in b)
            and -180 <= b[0] < b[2] <= 180
            and -90 <= b[1] < b[3] <= 90
        ]
    except (OSError, UnicodeError, ValueError, TypeError, KeyError):
        return []
