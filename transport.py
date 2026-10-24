"""Local transport search and Folium rendering."""

from html import escape

import folium

from config import TRANSPORT_CATEGORIES
from connectivity.nearest import nearest
from transport_data import load_transport


def search_transport(lat, lon, radius, limit):
    rows = load_transport()
    return {
        category: nearest(lat, lon, category, limit=limit, radius_km=radius, rows=rows)
        for category in TRANSPORT_CATEGORIES
    }


def transport_map(lat, lon, results, radius):
    m = folium.Map(location=[lat, lon], zoom_start=13, tiles="OpenStreetMap")
    folium.Marker(
        [lat, lon], tooltip="Your selected location", icon=folium.Icon(color="red", icon="home")
    ).add_to(m)
    folium.Circle(
        [lat, lon],
        radius=radius * 1000,
        color="#526578",
        weight=1,
        fill=False,
        tooltip="Search radius (straight-line)",
    ).add_to(m)
    bounds = [[lat, lon]]
    for category, places in results.items():
        title, color = TRANSPORT_CATEGORIES[category]
        layer = folium.FeatureGroup(name=title)
        for p in places:
            name = escape(p["name"])
            approximate = p["coordinate_method"] != "mapped_point"
            popup = (
                f"<b>{name}</b><br>{title}<br>"
                f"{p['distance_km']:.2f} km straight-line<br>"
                f"OSM {p['osm_type']} {p['osm_id']}<br>"
                + ("Approximate geometry centre; not an entrance.<br>" if approximate else "")
                + ("Passenger service not verified.<br>" if category == "airport_terminal" else "")
            )
            folium.CircleMarker(
                [p["latitude"], p["longitude"]],
                radius=8,
                color=color,
                fill=True,
                fill_opacity=0.85,
                tooltip=f"{name}: {p['distance_km']:.2f} km",
                popup=popup,
            ).add_to(layer)
            bounds.append([p["latitude"], p["longitude"]])
        layer.add_to(m)
    folium.LayerControl().add_to(m)
    if len(bounds) > 1:
        m.fit_bounds(bounds, padding=(35, 35), max_zoom=15)
    return m._repr_html_()
