"""Produce repeatable ranking baselines, sensitivity and clustering results."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import areas
import clustering
import data_store
from config import DEFAULTS


def evaluate():
    cells, manifest = data_store.dataset()
    base = areas.rank(cells, DEFAULTS)
    top = lambda rows: [r["id"] for r in rows if r["score"] is not None][:10]
    original = set(top(base))
    scenarios = []
    definitions = [
        ("Default priorities", DEFAULTS, 2, 10),
        ("Equal core weights", dict(transit=1, school=1, hospital=1, park=1), 2, 10),
        ("Transit only", dict(transit=1), 2, 10),
        ("Schools only", dict(school=1), 2, 10),
        ("Local radius 1 km", DEFAULTS, 1, 10),
        ("Local radius 5 km", DEFAULTS, 5, 10),
        ("Count cap 5", DEFAULTS, 2, 5),
        ("Count cap 20", DEFAULTS, 2, 20),
    ]
    for name, weights, radius, cap in definitions:
        rows = areas.rank(cells, weights, radius, cap)
        ids = top(rows)
        scenarios.append(
            dict(
                scenario=name,
                weights=weights,
                radius_km=radius,
                count_cap=cap,
                eligible=sum(r["score"] is not None for r in rows),
                top10=ids,
                top10_overlap_with_default=len(original & set(ids)) / max(1, len(original)),
            )
        )
    cluster = clustering.clustering()
    report = dict(
        created_at=datetime.now(timezone.utc).isoformat(),
        data_version=manifest["built_at"],
        cell_count=len(cells),
        ranking_scenarios=scenarios,
        clustering={k: v for k, v in cluster.items() if k != "labels"},
        note="Offline descriptive evaluation, not user relevance or recommendation accuracy. No invented user feedback. These offline baselines compare service factors; the PM2.5 indicator is available in personalised ranking.",
    )
    target = ROOT / "data" / "evaluation_report.json"
    target.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "clustering"}, indent=2))


if __name__ == "__main__":
    evaluate()
