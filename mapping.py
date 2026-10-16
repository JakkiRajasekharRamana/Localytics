import math
from collections import defaultdict
from html import escape
import folium

def build_map(records):
    BANDS = [
        (30, "Good", "#008000"),
        (60, "Satisfactory", "#8fbc3f"),
        (90, "Moderate", "#ffff00"),
        (120, "Poor", "#ff9900"),
        (250, "Very poor", "#ff0000"),
        (math.inf, "Severe", "#800000"),
    ]


    def safe(value):
        return escape(str(value))


    def number(value):
        """Return a finite number, or None for missing/invalid values."""
        try:
            value = float(value)
            return value if math.isfinite(value) else None
        except (TypeError, ValueError):
            return None


    def station_severity(readings):
        """Use the latest timestamp's PM2.5 reading for station colour."""
        from datetime import datetime

        candidates = []

        for reading in readings:
            if reading.get("pollutant_id") != "PM2.5":
                continue

            try:
                updated = datetime.strptime(
                    reading.get("last_update", ""),
                    "%d-%m-%Y %H:%M:%S",
                )
            except (TypeError, ValueError):
                updated = datetime.min

            candidates.append((updated, reading))

        if not candidates:
            return None, "No PM2.5 data", "#808080", "NA"

        # Use the latest reading, even if its value is missing.
        _, latest = max(candidates, key=lambda item: item[0])
        value = number(latest.get("avg_value"))
        updated = latest.get("last_update", "NA")

        if value is None or value < 0:
            return None, "No PM2.5 data", "#808080", updated

        for upper, category, color in BANDS:
            if value <= upper:
                return value, category, color, updated


    # Group all records by station and coordinates.
    stations = defaultdict(list)
    skipped = 0

    for record in records:
        lat = number(record.get("latitude"))
        lon = number(record.get("longitude"))

        if (
            lat is None
            or lon is None
            or not (-90 <= lat <= 90 and -180 <= lon <= 180)
        ):
            skipped += 1
            continue

        key = (record.get("station", "Unknown station"), lat, lon)
        stations[key].append(record)

    if not stations:
        raise ValueError("No records with valid coordinates found.")


    # Centre the map on the stations in your records.
    coordinates = [[lat, lon] for _, lat, lon in stations]

    m = folium.Map(
        location=[
            sum(lat for lat, lon in coordinates) / len(coordinates),
            sum(lon for lat, lon in coordinates) / len(coordinates),
        ],
        zoom_start=11,
        tiles="OpenStreetMap",
    )


    for (station, lat, lon), readings in stations.items():
        value, category, color, updated = station_severity(readings)
        value_text = f"{value:g}" if value is not None else "NA"

        rows = ""

        for reading in sorted(
            readings,
            key=lambda item: str(item.get("pollutant_id", "")),
        ):
            rows += f"""
            <tr>
                <td>{safe(reading.get("pollutant_id", "NA"))}</td>
                <td>{safe(reading.get("min_value", "NA"))}</td>
                <td>{safe(reading.get("max_value", "NA"))}</td>
                <td>{safe(reading.get("avg_value", "NA"))}</td>
                <td>{safe(reading.get("last_update", "NA"))}</td>
            </tr>
            """

        first = readings[0]

        popup_html = f"""
        <div style="font-family:Arial; min-width:440px;">
            <h4>{safe(station)}</h4>

            <p>
                {safe(first.get("city", ""))},
                {safe(first.get("state", ""))},
                {safe(first.get("country", ""))}
            </p>

            <div style="
                border-left:6px solid {color};
                background:#f5f5f5;
                padding:10px;
                margin-bottom:12px;">
                <b>Indicative PM2.5 severity: {safe(category)}</b><br>
                PM2.5 average: {value_text}<br>
                Updated: {safe(updated)}
            </div>

            <table border="1" cellpadding="6"
                   style="border-collapse:collapse; width:100%;">
                <tr style="background:#eeeeee;">
                    <th>Pollutant</th>
                    <th>Min</th>
                    <th>Max</th>
                    <th>Average</th>
                    <th>Updated</th>
                </tr>
                {rows}
            </table>

            <p style="font-size:12px;">
                NA = missing reading.<br>
                Colour uses PM2.5 only, assuming a 24-hour concentration
                in µg/m³. It does not represent official overall AQI.
            </p>
        </div>
        """

        folium.CircleMarker(
            location=[lat, lon],
            radius=10,
            color="#333333",
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            tooltip=(
                f"{safe(station)} — {safe(category)} "
                f"(PM2.5: {value_text})"
            ),
            popup=folium.Popup(popup_html, max_width=650),
        ).add_to(m)


    # Fit all stations into view.
    if len(stations) > 1:
        m.fit_bounds(
            coordinates,
            padding=(30, 30),
            max_zoom=13,
        )


    # Add a fixed legend.
    legend_items = [
        ("Good: 0–30", "#008000"),
        ("Satisfactory: >30–60", "#8fbc3f"),
        ("Moderate: >60–90", "#ffff00"),
        ("Poor: >90–120", "#ff9900"),
        ("Very poor: >120–250", "#ff0000"),
        ("Severe: >250", "#800000"),
        ("No PM2.5 data", "#808080"),
    ]

    legend = """
    <div style="
        position:fixed;
        bottom:30px;
        left:30px;
        z-index:9999;
        background:white;
        padding:14px;
        border:1px solid #999;
        border-radius:6px;
        font-family:Arial;
        font-size:13px;">
        <b>Indicative PM2.5 severity</b><br>
        <small>Assumed 24-hour concentration, µg/m³</small>
        <hr style="margin:8px 0;">
    """

    for label, color in legend_items:
        legend += f"""
        <div style="margin:4px 0;">
            <span style="
                display:inline-block;
                width:12px;
                height:12px;
                background:{color};
                border:1px solid #777;
                margin-right:7px;">
            </span>
            {label}
        </div>
        """

    legend += """
        <hr style="margin:8px 0;">
        <small>Not official overall AQI</small>
    </div>
    """

    m.get_root().html.add_child(folium.Element(legend))

    return m._repr_html_(), len(stations), skipped
