"""Local transport search and Folium rendering."""
import json
from html import escape
from pathlib import Path
import folium
from connectivity.nearest import nearest

DATA_DIR = Path(__file__).parent / 'connectivity'
CATEGORIES = {'bus_stop': ('Bus stops', '#2878b5'),
              'metro_station': ('Metro stations', '#8b46a5'),
              'airport_terminal': ('Airport terminals', '#db7618')}


def search_transport(lat, lon, radius, limit):
    return {category: nearest(lat, lon, category, limit=limit, radius_km=radius,
             csv_path=DATA_DIR / 'transport_locations.csv') for category in CATEGORIES}


def transport_map(lat, lon, results, radius):
    m = folium.Map(location=[lat, lon], zoom_start=13, tiles='OpenStreetMap')
    folium.Marker([lat, lon], tooltip='Your selected location',
                  icon=folium.Icon(color='red', icon='home')).add_to(m)
    folium.Circle([lat, lon], radius=radius*1000, color='#526578',
                  weight=1, fill=False, tooltip='Search radius (straight-line)').add_to(m)
    bounds = [[lat, lon]]
    for category, places in results.items():
        title, color = CATEGORIES[category]
        layer = folium.FeatureGroup(name=title)
        for p in places:
            name = escape(p['name'])
            approximate = p['coordinate_method'] != 'mapped_point'
            popup = (f'<b>{name}</b><br>{title}<br>'
                     f"{p['distance_km']:.2f} km straight-line<br>"
                     f"OSM {p['osm_type']} {p['osm_id']}<br>"
                     + ('Approximate geometry centre; not an entrance.<br>' if approximate else '')
                     + ('Passenger service not verified.<br>' if category == 'airport_terminal' else ''))
            folium.CircleMarker([p['latitude'], p['longitude']], radius=8,
                 color=color, fill=True, fill_opacity=.85,
                 tooltip=f"{name}: {p['distance_km']:.2f} km", popup=popup).add_to(layer)
            bounds.append([p['latitude'], p['longitude']])
        layer.add_to(m)
    folium.LayerControl().add_to(m)
    if len(bounds) > 1:
        m.fit_bounds(bounds, padding=(35,35), max_zoom=15)
    return m._repr_html_()
