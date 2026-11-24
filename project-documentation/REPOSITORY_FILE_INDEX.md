# Localytics: Complete Repository File Index

This document provides an exhaustive, navigable directory tree and file responsibility inventory for the **Localytics** codebase. Every file in the repository (excluding auto-generated virtual environments and caches) has been audited and cataloged below.

---

## 1. Directory Structure

```text
Localytics/
├── .env.example                     # Template for environment variables (DATA_GOV_API_KEY)
├── .gitattributes                  # Git line-ending normalization configuration
├── .gitignore                      # Git exclusion rules for virtualenvs, caches, and local secrets
├── LICENSE                         # MIT License documentation (Copyright (c) 2026 Sanjyot)
├── README.md                       # High-level project summary, quickstart, and design guidelines
├── pytest.ini                      # Pytest test-runner configuration and path resolution
├── requirements.txt                # Runtime dependency manifest (Flask, Folium, SciPy, Shapely, etc.)
├── requirements-dev.txt            # Development & testing dependency manifest (pytest, ruff, djlint)
├── ruff.toml                       # Ruff linter configuration (line length, import sorting rules)
│
├── app.py                          # Flask application entry point and nationwide explorer routes
├── config.py                       # Global constants, paths, factor weights, and color mappings
├── area_views.py                   # Blueprint for area recommendation, ranking, and export endpoints
├── areas.py                        # Transparent factor scoring, must-have constraint checks, ranking
├── air_client.py                   # Paginated HTTP client for data.gov.in API with curl security isolation
├── data_store.py                   # SQLite database access layer, LRU-caching, and air-cache storage
├── observations.py                 # Air monitoring station parser, PM2.5 extraction, and severity banding
├── geography.py                    # Spatial math, Haversine distance, coordinate validation, extent checks
├── osm_data.py                     # OpenStreetMap PBF classification, object merging, and deduplication
├── transport.py                    # Local transport search coordinator and Folium map visualizer
├── transport_data.py               # CSV transport loader and bounding box extent parser
├── unified_map.py                  # Folium unified map generator with custom JavaScript/Leaflet templates
├── school_profiles.py              # UDISE+ school profile processor, data formatter, ray-casting lookup
├── school_views.py                 # Blueprint for school profile views and map-click spatial lookup
├── clustering.py                   # Unsupervised scikit-learn clustering (K-Means/Hierarchical) and validation
│
├── connectivity/                   # Standalone transport lookup subsystem
│   ├── extract_transport.py        # CLI script to extract transit features from raw OSM PBF files
│   ├── metadata.json               # Extraction provenance metadata, counts, and boundary extents
│   ├── nearest.py                  # Standalone nearest-transit lookup using Haversine formulas
│   ├── transport_locations.csv     # Extracted transit coordinates (bus stops, metro, airports)
│   └── transport_locations.geojson # GeoJSON representation of extracted transit points
│
├── data/                           # Application data storage directory
│   ├── areas.sqlite                # SQLite database (1,487 grid cells, 66,636 facilities, R-Tree index)
│   ├── area_manifest.json          # Metadata manifest for the precomputed Delhi 1km spatial grid
│   ├── boundary_source.md          # Provenance and CC BY-SA 2.5 license for DataMeet Delhi boundary
│   ├── delhi_boundary.geojson      # Raw municipal boundary polygon for Delhi from DataMeet
│   ├── cluster_report.json         # Precomputed K-Means/Hierarchical clustering evaluation report
│   ├── evaluation_report.json      # Repeatable ranking baselines and sensitivity analysis report
│   └── schools/                    # Educational institutional data directory
│       ├── pincode_boundaries.json # Compact GeoJSON boundaries for 92 Delhi postal pincodes
│       └── pincode_profiles.json   # Aggregated UDISE+ 2024-25 metrics for 93 Delhi postal pincodes
│
├── scripts/                        # Offline preprocessing, pipeline, and evaluation CLI tools
│   ├── build_areas.py              # Builds areas.sqlite from OSM PBF files and boundary GeoJSON
│   ├── build_pincode_boundaries.py # Converts India Post KML boundary files into optimized JSON
│   ├── build_school_profiles.py    # Aggregates raw UDISE+ CSVs into pincode_profiles.json
│   └── evaluate_areas.py           # Generates ranking sensitivity and clustering stability reports
│
├── static/                         # Frontend client assets (vanilla JavaScript and CSS)
│   ├── areas.css                   # Styles for the area recommendation interface
│   ├── areas.js                    # Leaflet client controller for area grid, sliders, and comparisons
│   ├── base.css                    # Global application typography, navigation bar, and color palette
│   ├── connectivity.css            # Styles for the nearby transit search form and results table
│   ├── index.css                   # Styles for the nationwide air quality & transit explorer
│   ├── index.js                    # Client controller for the air explorer and iframe message bridge
│   ├── schools.css                 # Styles for the school profiles catalog and pincode detail pages
│   ├── schools.js                  # Table sorting and live text-filter logic for school listings
│   ├── school_profile.js           # Shared asynchronous loader for sidebar school profile widgets
│   └── shared.js                   # XSS escaping utility (Localytics.escape) and number formatters
│
├── templates/                      # Jinja2 HTML presentation templates
│   ├── _school_macros.html         # Reusable Jinja macros for rendering school indicator rows
│   ├── areas.html                  # Homepage: area recommendations, Leaflet map, filters, and top 10
│   ├── base.html                   # HTML base layout with header, navigation bar, and script blocks
│   ├── combined_map.js.j2          # Jinja-templated JavaScript for Folium Leaflet map interactions
│   ├── connectivity.html           # Nearby transit search input form, results list, and embedded map
│   ├── explorer.html               # Supporting template for interactive geographic exploration
│   ├── index.html                  # Nationwide air quality station explorer and filter form
│   ├── school_snippet.html         # Asynchronous HTML fragment for map-click school profile popups
│   └── schools.html                # School profile directory catalog and individual pincode view
│
└── tests/                          # Automated Pytest regression test suite (59 unit/integration tests)
    ├── conftest.py                 # Pytest fixture to isolate and restore cached air observations
    ├── test_app.py                 # Tests for nationwide explorer, pagination, error states, and curl
    ├── test_areas.py               # Tests for factor scoring, ranking, must-have constraints, and caching
    ├── test_connectivity.py        # Tests for Haversine distance calculations and transit endpoints
    ├── test_multicity.py           # Tests for nationwide city filtering and map generation
    ├── test_optional_transport.py  # Tests for air quality map behavior when transport data is missing
    ├── test_overlap.py             # Tests for OSM object deduplication and version tie-breaking
    ├── test_pincode_lookup.py      # Tests for ray-casting point-in-polygon containment and edge cases
    ├── test_schools.py             # Tests for UDISE+ data aggregation, percentile calculations, routes
    ├── test_search_case.py         # Tests for case-insensitive city/state queries and fallback logic
    ├── test_shared.py              # Tests for shared parsers, XSS escaping, and asset integrity
    └── test_unified.py             # Tests for the combined Folium map and iframe postMessage bridge
```

---

## 2. File Responsibility Matrix

| File Path | Role & Classification | Primary Responsibility | Key Functions / Classes / Components | Imports & Dependencies | Consumed By |
|---|---|---|---|---|---|
| `app.py` | Web Entry Point (Core) | Application bootstrap; registers blueprints; exposes `/air-quality` and `/connectivity` routes. | `index()`, `connectivity()` | `Flask`, `folium`, `air_client`, `data_store`, `area_views`, `school_views`, `transport`, `unified_map` | Direct user CLI (`python app.py`) |
| `config.py` | Configuration (Core) | Centralized application constants, file paths, scoring defaults, and visual color palettes. | `ROOT`, `FACTORS`, `DEFAULTS`, `CATEGORY`, `TRANSPORT_CATEGORIES`, `FACILITY_COLORS`, `PM25_BANDS` | `pathlib.Path` | All Python backend modules |
| `area_views.py` | Controller / Route (Core) | Area exploration views (`/`, `/areas`), JSON detail API (`/api/areas/<id>`), CSV export, air refresh. | `explore()`, `detail()`, `export()`, `refresh_area_air()`, `preferences()` | `flask.Blueprint`, `areas`, `clustering`, `data_store`, `air_client`, `observations` | `app.py` (via `register_area_views`) |
| `areas.py` | Business Logic (Core) | Transparent mathematical scoring of urban factors, constraint evaluation, and candidate ranking. | `evaluate()`, `rank()`, `service_score()`, `nearest_air()` | `math`, `datetime`, `config`, `geography.distance_km` | `area_views.py`, `scripts/evaluate_areas.py` |
| `air_client.py` | External API Client (Core) | Robust, paginated consumer of the data.gov.in AQI API; uses secure `curl` pipes to shield API keys. | `fetch_records()`, `_fetch_records()`, `FetchError` | `json`, `os`, `shutil`, `subprocess`, `urllib.parse` | `app.py`, `area_views.py` |
| `data_store.py` | Data Access Layer (Core) | Manages read-only connection to `areas.sqlite`, LRU-caches cells in memory, and persists air readings. | `dataset()`, `cache_air()`, `air_records()`, `read_report()` | `sqlite3`, `json`, `functools.lru_cache`, `config.DATA_DIR` | `area_views.py`, `clustering.py`, `scripts/evaluate_areas.py` |
| `observations.py` | Data Parser (Core) | Normalizes raw AQI readings; extracts latest valid PM2.5 observation; maps to severity color bands. | `observation_time()`, `latest_pm25()`, `severity()`, `group_monitors()`, `monitors()` | `datetime`, `zoneinfo.ZoneInfo`, `config.PM25_BANDS` | `app.py`, `area_views.py`, `unified_map.py` |
| `geography.py` | Spatial Math (Core) | Strict coordinate validation, spherical Haversine distance calculations, and named facility consolidation. | `coordinates()`, `distance_km()`, `covered_radius()`, `consolidate_named()` | `math`, `collections.defaultdict` | `areas.py`, `transport.py`, `school_views.py`, `osm_data.py` |
| `osm_data.py` | GIS Extraction (Core) | Extracts nodes/ways from OSM PBF files; classifies facilities into 10 categories; deduplicates by version. | `classify()`, `classify_transport()`, `extract_sources()` | `osmium`, `hashlib`, `math`, `geography.consolidate_named` | `connectivity/extract_transport.py`, `scripts/build_areas.py` |
| `transport.py` | Spatial Service (Core) | Queries nearest transit features and constructs standalone Folium maps with radius rings. | `search_transport()`, `transport_map()` | `folium`, `config.TRANSPORT_CATEGORIES`, `connectivity.nearest`, `transport_data` | `app.py` |
| `transport_data.py` | Data Loader (Core) | Loads transit CSV records; parses and validates source bounding box extents from metadata.json. | `load_transport()`, `source_bounds()` | `csv`, `json`, `pathlib.Path`, `geography.coordinates` | `transport.py`, `unified_map.py` |
| `unified_map.py` | Map Generator (Core) | Generates combined Folium map rendering AQI monitor markers and transit stations; injects custom JS. | `build_map()` | `folium`, `branca.element`, `observations`, `transport_data`, `geography` | `app.py` |
| `school_profiles.py` | Institutional Data (Core) | Loads UDISE+ school statistics; performs ray-casting point-in-polygon spatial containment lookup. | `load_profiles()`, `load_boundaries()`, `pincode_at()`, `in_polygon()`, `view()` | `json`, `re`, `config.SCHOOL_DIR` | `school_views.py` |
| `school_views.py` | Controller / Route (Core) | School catalog (`/schools`), pincode view (`/schools/<pin>`), and dynamic coordinate lookup endpoint. | `index()`, `detail()`, `lookup()`, `register()` | `flask.Blueprint`, `school_profiles`, `geography.coordinates` | `app.py` (via `register_school_views`) |
| `clustering.py` | Machine Learning (Core) | Unsupervised spatial clustering (K-Means / Agglomerative) using 16 facility features; stability reporting. | `clustering()` | `scikit-learn`, `numpy`, `data_store`, `functools.lru_cache` | `area_views.py`, `scripts/evaluate_areas.py` |
| `connectivity/nearest.py` | Utility (Core) | Standalone Haversine search finding top N nearest transit locations within a given radius. | `nearest()` | `geography.coordinates`, `geography.distance_km`, `transport_data` | `transport.py` |
| `connectivity/extract_transport.py` | Preprocessing CLI (Script) | Offline CLI tool extracting bus stops, metro stations, and airport terminals into CSV/GeoJSON. | `main()` | `osm_data`, `argparse`, `csv`, `json` | Offline developer maintenance |
| `scripts/build_areas.py` | Preprocessing CLI (Script) | Generates 1km UTM grid (EPSG:32643), spatial KD-Tree queries, and builds `areas.sqlite`. | `build()` | `pyproj.Transformer`, `shapely`, `scipy.spatial.cKDTree`, `sqlite3`, `osm_data` | Offline pipeline execution |
| `scripts/build_school_profiles.py` | Preprocessing CLI (Script) | Processes UDISE+ 2024-25 open data CSVs; joins facilities/teachers/students; computes percentiles. | `build()`, `school_records()`, `profile_of()` | `csv`, `json`, `argparse` | Offline pipeline execution |
| `scripts/build_pincode_boundaries.py` | Preprocessing CLI (Script) | Converts India Post KML boundary polygons into clean, rounded GeoJSON boundary polygons. | `parse()`, `ring()`, `main()` | `xml.etree.ElementTree`, `json`, `re` | Offline pipeline execution |
| `scripts/evaluate_areas.py` | Evaluation CLI (Script) | Evaluates ranking sensitivity across 8 scenarios and validates clustering stability with 5 resamples. | `evaluate()` | `areas`, `clustering`, `data_store`, `config.DEFAULTS` | Model evaluation & documentation |
| `static/areas.js` | Frontend Controller (UI) | Manages Leaflet map grid rendering, preference sliders, area detail sidebar, and comparisons. | IIFE client controller | Vanilla JS, Leaflet.js, `shared.js` | `templates/areas.html` |
| `static/shared.js` | Frontend Utility (UI) | Provides safe HTML entity escaping (`Localytics.escape`) and standardized number formatting. | `Localytics.escape()`, `Localytics.formatNumber()` | Vanilla JS | All HTML templates |
| `static/school_profile.js` | Frontend Component (UI) | Asynchronously fetches `/schools/lookup` HTML snippet when a map point or grid cell is clicked. | `LocalyticsSchools.load()` | Vanilla JS (Fetch API) | `templates/areas.html`, `templates/index.html` |
| `static/schools.js` | Frontend Component (UI) | Handles client-side table search filtering and multi-column sorting for school pincode listings. | IIFE table controller | Vanilla JS | `templates/schools.html` |
| `static/index.js` | Frontend Component (UI) | Listens for postMessage events from the Folium iframe map and loads location insights & schools. | IIFE window listener | Vanilla JS (postMessage API) | `templates/index.html` |