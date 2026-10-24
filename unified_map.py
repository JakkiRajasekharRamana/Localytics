"""One map for air observations and local connectivity; click anywhere to inspect."""

import folium
from branca.element import JavascriptLink, MacroElement, Template

from config import ROOT, TRANSPORT_CATEGORIES
from geography import consolidate_named
from observations import group_monitors, severity
from transport_data import load_transport, source_bounds


def build_map(records):
    grouped, skipped = group_monitors(records)
    stations = [
        dict(
            name=p["name"],
            lat=p["lat"],
            lon=p["lon"],
            readings=p["readings"],
            air=severity(p["pm"]),
        )
        for p in grouped
    ]
    rows = load_transport(optional=True)
    transport = [
        dict(
            name=r.get("name") or "Unnamed",
            lat=r["latitude"],
            lon=r["longitude"],
            category=r["category"],
            method=r.get("coordinate_method", "unknown"),
        )
        for r in rows
        if r.get("category") in TRANSPORT_CATEGORIES
    ]
    unique = consolidate_named(transport)
    center = [22.5937, 78.9629]
    if stations:
        center = [
            sum(s["lat"] for s in stations) / len(stations),
            sum(s["lon"] for s in stations) / len(stations),
        ]
    m = folium.Map(location=center, zoom_start=11 if stations else 5, tiles="OpenStreetMap")
    if len(stations) > 1:
        m.fit_bounds([[s["lat"], s["lon"]] for s in stations], max_zoom=12)
    control = MacroElement()
    control._name = "CombinedExplorer"
    control.stations = stations
    control.transport = unique
    control.bounds = source_bounds() if unique else []
    control.category_names = {k: v[0] for k, v in TRANSPORT_CATEGORIES.items()}
    control.category_colors = {k: v[1] for k, v in TRANSPORT_CATEGORIES.items()}
    control._template = Template(
        (ROOT / "templates" / "combined_map.js.j2").read_text(encoding="utf-8")
    )

    m.get_root().header.add_child(JavascriptLink("/static/shared.js"))
    m.add_child(control)
    return m._repr_html_(), len(stations), skipped
