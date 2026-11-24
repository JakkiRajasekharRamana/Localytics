"""Combine the Gurugram and Delhi datasets into one "Delhi NCR" city so both show on the same map.

usage (Localytics Python environment): python build_ncr.py --localytics /path/to/Localytics [--data ../web/public/data]
Run build_delhi_open.py first; gurgaon.json comes with Flat Finder.

Nothing is invented: every building keeps its own source. Delhi buildings carry open_data/no_sale flags so the app words
their cards correctly and treats Buy mode as "not checked" for them. Gurugram buildings get PM2.5 only where a cached
Delhi monitor is within 5 km; the rest honestly show no reading.
"""

import argparse
import csv
import json
import sqlite3
from pathlib import Path

import build_delhi_open as bdo

CENTER, ZOOM = [77.14, 28.52], 9.6


def load(data, name):
    return json.loads((data / name).read_text(encoding="utf-8"))


def best(price):
    """(value, estimated) for one BHK price entry, preferring a real median."""
    if not price:
        return None, False
    real = price.get("median")
    if real:
        return real, False
    est = price.get("value")
    return (est, True) if est else (None, False)


def build(args):
    data = Path(args.data)
    g, d = load(data, "gurgaon.json"), load(data, "delhi.json")
    gs, ds = load(data, "gurgaon-shapes.geojson"), load(data, "delhi-shapes.geojson")
    gd, dd = load(data, "gurgaon-details.json"), load(data, "delhi-details.json")

    db = sqlite3.connect(f"file:{Path(args.localytics) / 'data/areas.sqlite'}?mode=ro", uri=True)
    monitors, fetched, radius_km, bands, severity = bdo.load_monitors(db, Path(args.localytics))

    aq_by_sid = {}
    with_air = 0
    for s in g["societies"]:
        s["city_label"] = "Gurugram"
        s["air"], s["aq"] = bdo.air_for(s["lat"], s["lng"], monitors, radius_km, bands, severity)
        with_air += 1 if s["air"] else 0
        aq_by_sid[s["id"]] = s["aq"]
    for s in d["societies"]:
        aq_by_sid[s["id"]] = s["aq"]

    shapes = gs["features"] + ds["features"]
    for f in shapes:
        f["properties"].setdefault("aq", aq_by_sid.get(f["properties"]["sid"], -1))

    gc, dc = g["counts"], d["counts"]
    n_g, n_d = len(g["societies"]), len(d["societies"])
    counts = dict(listed=gc.get("listed", n_g) + dc["listed"], on_map=n_g + n_d, not_located=gc.get("not_located", 0), ai_read=gc.get("ai_read", 0),
                  for_sale=gc.get("for_sale", 0), for_rent=gc.get("for_rent", 0) + dc["for_rent"], verified=gc.get("verified", 0),
                  gurugram=n_g, delhi=n_d, gurugram_with_pm25=with_air, delhi_with_pm25=dc["with_pm25"])
    du = d["ui"]
    ui = dict(
        default_mode="rent", default_kinds=["apartment", "builder floor"], hide_example=True,  # Divy's example is a Gurugram floor-plan search: see ?city=gurgaon
        rent_as_of=du["rent_as_of"], price_heading=du["price_heading"],
        note=(f"{n_g + n_d:,} buildings · Gurugram: {n_g:,} societies from Magicbricks listings ({gc.get('for_sale', 0):,} for sale, {gc.get('for_rent', 0):,} for rent) · "
              f"Delhi: {n_d:,} buildings and colonies from open data ({du['rent_as_of']} rents, no sale prices)"),
        about_prices=("<b>Two sources, shown together.</b> <b>Gurugram</b> prices and rents are medians of live Magicbricks listings; <b>⚠</b> marks a price our checks think is a typo "
                      "and <b>~</b> marks our estimate. <b>Delhi</b> rents are <b>locality medians from an open dataset collected in " + du["rent_as_of"] +
                      "</b>, about six years old, so today's rents are higher; they are not the building's own listings, and Delhi has no sale prices "
                      "(in Buy mode Delhi buildings show as not checked). The Delhi rent dataset is declared CC0 by its uploader; its listings were originally taken from a real-estate website." + du.get("more_note", "")),
        page_description="Delhi and Gurugram apartment buildings on one map: Gurugram prices and rents from listings, Delhi locality rents (open data), and indicative PM2.5.",
        neighbourhood_blurb="Compare neighbourhoods on the property map. Localytics scores cover Delhi only; Gurugram buildings have none.",
        air=dict(fetched=fetched, radius_km=radius_km, bands=du["air"]["bands"],
                 note=("Indicative PM2.5 from the nearest monitor within %d km in the cached Delhi readings. Gurugram buildings show a value only when a Delhi monitor is that close; "
                       "Haryana readings (cached from a data.gov.in refresh) would be used too, but none are cached. Not an official AQI; it may be days old." % radius_km)),
        onboarding=[
            ["Delhi and Gurugram, on one map", f"{n_g + n_d:,} buildings: {n_g:,} Gurugram societies with prices and rents from Magicbricks listings, and {n_d:,} Delhi apartment buildings, colonies and other mapped residential areas from OpenStreetMap with locality rents ({du['rent_as_of']}). Use the city picker to look at one city alone."],
            ["Start with what you cannot live without", "The map opens in Rent mode, where both cities have data. Set your budget and the BHK you need. Switching to Buy shows Gurugram prices; Delhi has no sale prices, so those buildings show as not checked."],
            None,
            None,
        ],
    )
    doc = dict(city=dict(id="ncr", name="Delhi NCR · Delhi + Gurugram", center=CENTER, zoom=ZOOM), price_model=g.get("price_model", {}), room_model=g.get("room_model", {}),
               counts=counts, sources=list(dict.fromkeys(g["sources"] + d["sources"])), ui=ui, societies=g["societies"] + d["societies"], events=g["events"] + d["events"])
    # steps 2 and 3 of the onboarding keep the app's own wording unless Delhi's differ; use the Delhi wording for the map legend step
    ui["onboarding"][2] = ["How to read the map", "Brighter buildings fit your search and faint ones are not checked yet. The PM2.5 button colours every building by the nearest air monitor instead (Delhi mostly; Gurugram only near a Delhi monitor). Delhi rents are locality medians, not the building's own listings."]
    ui["onboarding"][3] = ["Open a building, keep a list", "Click any building for its prices or rents by BHK, what is nearby and PM2.5. Star the ones you like. Export your results as a CSV any time."]

    (data / "ncr.json").write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    (data / "ncr-shapes.geojson").write_text(json.dumps(dict(type="FeatureCollection", features=shapes), separators=(",", ":")), encoding="utf-8")
    (data / "ncr-details.json").write_text(json.dumps({**gd, **dd}, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

    with (data / "ncr-societies.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["city", "id", "name", "kind", "developer", "locality", "lat", "lng", "price_source", "pm25", "pm25_label", "pm25_monitor", "pm25_km", "pm25_updated", "url"]
                   + [f"{m}_{b}bhk_{c}" for b in range(1, 6) for m in ("buy", "rent") for c in ("value", "estimated")])
        for s in doc["societies"]:
            a = s.get("air") or {}
            src = "Locality median, open dataset (Aug 2020)" if s.get("open_data") else "Magicbricks listings"
            row = [s["city_label"], s["id"], s["name"], s["kind"], s.get("developer") or "", s.get("locality") or "", s["lat"], s["lng"], src,
                   a.get("pm"), a.get("label"), a.get("monitor"), a.get("km"), a.get("updated"), s.get("url") or ""]
            for b in range(1, 6):
                p = (s.get("prices") or {}).get(str(b), {})
                for mode in ("buy", "rent"):
                    v, est = best(p.get(mode)) if p.get(mode) else best(p.get(f"{mode}_est"))
                    row += [v, "yes" if est else ""]
            w.writerow(row)
    with (data / "ncr-units.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["city", "society_id", "society", "unit", "bhk", "size_sqft", "bedrooms_ft", "all_bedrooms_read", "confidence", "source"])
        for s in doc["societies"]:
            for u in s.get("unit_types", []):
                size = u.get("super_sqft") or u.get("size_sqft") or u.get("carpet_sqft")
                beds = "; ".join(f"{a}x{b}" for a, b in (u.get("bedrooms") or []))
                w.writerow([s["city_label"], s["id"], s["name"], u.get("label"), u.get("bhk"), size, beds, u.get("rooms_complete"), u.get("confidence"), u.get("source")])

    cj = data / "cities.json"
    cities = json.loads(cj.read_text(encoding="utf-8")) if cj.exists() else {}
    ordered = {"ncr": dict(name="Delhi NCR · Delhi + Gurugram")}
    ordered.update({k: v for k, v in cities.items() if k != "ncr"})
    cj.write_text(json.dumps(ordered, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(counts, indent=1))
    print("shape features:", len(shapes), "| files:", {p.name: round(p.stat().st_size / 1e6, 1) for p in data.glob("ncr*")})
    print("Gurugram buildings with a Delhi monitor within", radius_km, "km:", with_air, "of", n_g)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--localytics", required=True)
    ap.add_argument("--data", default=str(Path(__file__).resolve().parents[1] / "web" / "public" / "data"))
    build(ap.parse_args())
