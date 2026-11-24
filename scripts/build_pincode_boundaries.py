"""Convert the India Post pincode KML for Delhi (via OpenCity) into a compact boundary file.
Run: python scripts/build_pincode_boundaries.py /path/to/Delhi-Pincodes.kml
Output: data/schools/pincode_boundaries.json (rounded coordinates; outer rings and holes per pincode).
"""

import argparse
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "schools"
KML = "{http://www.opengis.net/kml/2.2}"
DIGITS = 5  # about 1 metre


def ring(element):
    """Coordinates of a LinearRing as rounded [lon, lat] pairs, with repeated points dropped."""
    points = []
    for token in element.find(KML + "coordinates").text.split():
        lon, lat = (round(float(v), DIGITS) for v in token.split(",")[:2])
        if not points or points[-1] != [lon, lat]:
            points.append([lon, lat])
    if len(points) < 4 or points[0] != points[-1]:
        raise ValueError("ring is not closed or has too few points")
    return points


def parse(kml_path):
    raw = Path(kml_path).read_bytes()
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise ValueError("KML contains a DTD or entity declaration; refusing to parse")
    pincodes = {}
    for placemark in ET.fromstring(raw).iter(KML + "Placemark"):
        attrs = {d.get("name"): (d.text or "").strip() for d in placemark.iter(KML + "SimpleData")}
        pincode = attrs.get("PINCODE", "")
        if not re.fullmatch(r"\d{6}", pincode):
            raise ValueError(f"placemark has an invalid pincode: {pincode!r}")
        polygons = []
        for polygon in placemark.iter(KML + "Polygon"):
            rings = [ring(polygon.find(KML + "outerBoundaryIs/" + KML + "LinearRing"))]
            rings += [
                ring(r) for r in polygon.findall(KML + "innerBoundaryIs/" + KML + "LinearRing")
            ]
            polygons.append(rings)
        if not polygons:
            raise ValueError(f"pincode {pincode} has no polygon")
        entry = pincodes.setdefault(pincode, [])
        entry.extend(polygons)
    result = []
    for pincode, polygons in sorted(pincodes.items()):
        outer = [p for rings in polygons for p in rings[0]]
        lons, lats = [p[0] for p in outer], [p[1] for p in outer]
        result.append(
            dict(
                pincode=pincode,
                bbox=[min(lons), min(lats), max(lons), max(lats)],
                polygons=polygons,
            )
        )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("kml", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    pincodes = parse(args.kml)
    data = dict(
        metadata=dict(
            source="Pincode Map - Delhi, India Post boundaries republished by OpenCity (data updated 25 Nov 2025): "
            "https://data.opencity.in/dataset/pincode-maps-of-cities/resource/4fe127ea-5fbf-4d86-b456-605323a8caaf",
            credit="India Post; compiled by Deepak Malghan (as credited on OpenCity)",
            licence="Creative Commons Attribution Share-Alike per the OpenCity page, which also lists public domain; "
            "keep this attribution and share any redistributed boundary file on the same terms.",
            generated_at_utc=datetime.now(timezone.utc).isoformat(),
            pincode_count=len(pincodes),
            coordinate_digits=DIGITS,
            limitations=[
                "Pincodes are postal delivery areas, not neighbourhoods or school catchments.",
                "Some pincodes in the school data have no polygon here, so a map click cannot reach them.",
            ],
        ),
        pincodes=pincodes,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "pincode_boundaries.json").write_text(
        json.dumps(data, separators=(",", ":")), encoding="utf-8"
    )
    print(f"{len(pincodes)} pincodes, {sum(len(p['polygons']) for p in pincodes)} polygons")


if __name__ == "__main__":
    main()
