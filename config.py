"""Project paths and documented scoring/display choices."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
TRANSPORT_DIR = ROOT / "connectivity"
FACTORS = {
    "air": "Air quality (PM2.5)",
    "transit": "Bus and metro",
    "school": "School proximity",
    "hospital": "Hospitals",
    "park": "Public green spaces",
    "gym": "Gyms",
    "mall": "Malls",
    "ev": "EV charging",
    "airport": "Airport terminals",
    "workplace": "Workplace distance",
}
DEFAULTS = {"transit": 4, "school": 3, "hospital": 3, "park": 3}
CATEGORY = {
    "school": "school",
    "hospital": "hospital",
    "park": "park",
    "gym": "gym",
    "mall": "mall",
    "ev": "ev",
    "airport": "airport_terminal",
}
TRANSPORT_CATEGORIES = {
    "bus_stop": ("Bus stops", "#2878b5"),
    "metro_station": ("Metro stations", "#8b46a5"),
    "airport_terminal": ("Airport terminals", "#db7618"),
}
FACILITY_COLORS = {
    **{k: v[1] for k, v in TRANSPORT_CATEGORIES.items()},
    "school": "#326da8",
    "hospital": "#b94058",
    "park": "#34885b",
    "gym": "#9c66b3",
    "mall": "#d58b22",
    "ev": "#448c92",
}
LOCAL_RADII = (1, 2, 5)
COUNT_CAPS = (5, 10, 20)
AIRPORT_RADIUS_KM = 25
WORKPLACE_CAP_KM = 50
PM25_CAP = 250
MONITOR_RADIUS_KM = 5
MONITOR_MAX_AGE_HOURS = 6
# Indicative display bands retained from the prototype, not official AQI conversions.
PM25_BANDS = [
    [30, "Good", "#008000"],
    [60, "Satisfactory", "#8fbc3f"],
    [90, "Moderate", "#ffff00"],
    [120, "Poor", "#ff9900"],
    [250, "Very poor", "#ff0000"],
    [None, "Severe", "#800000"],
]
MISSING_PM25 = {"label": "No PM2.5 data", "color": "#808080", "value": "NA"}
