# Localytics: High-Level Architecture Reference

This reference document defines the complete architectural design of the **Localytics** platform, including component boundaries, data interchange specifications, hardware/runtime assumptions, and a Mermaid high-level architectural diagram.

---

## 1. High-Level Architectural Narrative

Localytics is structured as a **modular, data-driven geospatial web application** built with Python and Flask. Its primary architectural pattern is a **layered monolith with decoupled offline batch preprocessing pipelines**.

### Core Subsystems:

1. **Offline Geospatial ETL & Preprocessing Pipeline:**
   - Ingests multi-gigabyte OpenStreetMap PBF files (`delhi.pbf`, `other1.pbf`) via Pyosmium.
   - Converts coordinates into a projected UTM coordinate system (`EPSG:32643`) to construct a regular 1 km grid of 1,487 cells over Delhi.
   - Indexes 66,636 physical facilities using spherical $k$-d trees (`scipy.spatial.cKDTree`) and compiles precalculated counts and distances into an embedded SQLite database (`data/areas.sqlite`) backed by an R-Tree spatial index.
   - Transforms national school data (UDISE+ 2024-25) and India Post KML boundaries into optimized JSON files (`data/schools/`).

2. **Web Application & Request Routing Layer (`app.py`, `area_views.py`, `school_views.py`):**
   - Built on Flask 3.1. Runs as a single WSGI process.
   - Utilizes Flask Blueprints to decouple functional areas (`areas`, `schools`).
   - Serves server-side rendered HTML via Jinja2 templates and exposes a lightweight JSON API (`/api/areas/<id>`).

3. **In-Memory Analytical Recommendation Engine (`areas.py`):**
   - Operates on preloaded SQLite cell payloads cached in memory via Python's `@lru_cache`.
   - Evaluates multi-criteria user preferences on-the-fly without database round-trips.
   - Enforces a strict **Zero-Imputation Principle**: cells lacking verified evidence for a selected factor or failing a must-have distance filter are excluded from ranking.

4. **External API & Environmental Ingestion Layer (`air_client.py`, `observations.py`):**
   - Connects to the Indian Open Government Data portal (`api.data.gov.in`) to fetch real-time air quality readings.
   - Protects API credentials by executing `curl` via secure subprocess pipes with configuration passed over `stdin`.
   - Persists query payloads into an internal SQLite table (`air_cache`), decoupling live searches from third-party API availability.

5. **Institutional Education Intelligence Subsystem (`school_profiles.py`):**
   - Provides institutional profiles for 93 Delhi postal pincodes based on UDISE+ 2024-25 data.
   - Implements a pure-Python 2D ray-casting point-in-polygon algorithm to resolve coordinates from map clicks into postal pincodes on-the-fly.
   - Explicitly decoupled from neighborhood ranking to prevent biased or misleading quality scores.

6. **Descriptive Spatial Clustering Module (`clustering.py`):**
   - Employs unsupervised machine learning (`scikit-learn` K-Means and Agglomerative Clustering) over 16 normalized spatial feature dimensions.
   - Automatically determines optimal cluster counts ($k=2$) via silhouette analysis ($S = 0.357$) and validates stability across 5-fold bootstrap subsamples (Adjusted Rand Index $= 0.978$).
   - Kept strictly decoupled from the ranking engine: cluster labels only serve as descriptive categorical map layers.

7. **Client-Side Presentation & Interactive Cartography (`static/`, `templates/`):**
   - Renders interactive maps using Leaflet.js (for the area grid) and Folium (for nationwide stations).
   - Establishes a secure `window.postMessage` communication bridge between embedded Folium iframes and the host page sidebar.

---

## 2. High-Level Mermaid Architecture Diagram

```mermaid
graph TD
    %% External Actors and Data Providers
    User([End User / Web Browser])
    DataGov[("data.gov.in (Real-time AQI API)")]
    OSMData[("OpenStreetMap (.pbf dumps)")]
    UDISEData[("UDISE+ / India Post (OpenCity)")]
    OSMTiles[("OpenStreetMap Tile Servers")]

    %% System Boundary
    subgraph LocalyticsApp ["Localytics Application Boundary"]
        
        subgraph OfflinePipelines ["Offline Data Pipelines (scripts/)"]
            BuildAreas["scripts/build_areas.py<br/>(UTM Projection & cKDTree)"]
            BuildSchools["scripts/build_school_profiles.py<br/>(UDISE+ Aggregation)"]
            BuildBoundaries["scripts/build_pincode_boundaries.py<br/>(KML Parser)"]
            EvaluateAreas["scripts/evaluate_areas.py<br/>(Baseline & Sensitivity)"]
        end

        subgraph StorageLayer ["Data Storage (data/ & SQLite)"]
            SQLiteDB[("data/areas.sqlite<br/>- cells (1,487)<br/>- facilities (66,636)<br/>- facility_index (R-Tree)<br/>- air_cache")]
            SchoolJSON[("data/schools/<br/>- pincode_profiles.json<br/>- pincode_boundaries.json")]
            ReportsJSON[("Reports JSON<br/>- cluster_report.json<br/>- evaluation_report.json")]
            TransitCSV[("connectivity/<br/>- transport_locations.csv")]
        end

        subgraph CoreBackend ["Flask Core Web Application"]
            AppEntry["app.py<br/>(Flask App Entry Point)"]
            AreaViews["area_views.py<br/>(Blueprint: areas)"]
            SchoolViews["school_views.py<br/>(Blueprint: schools)"]
            DataStore["data_store.py<br/>(SQLite Access & LRU Cache)"]
            RankingEngine["areas.py<br/>(Transparent Scoring & Constraints)"]
            ClusteringEngine["clustering.py<br/>(scikit-learn K-Means / Stability)"]
            SchoolEngine["school_profiles.py<br/>(Ray-Casting Point-in-Polygon)"]
            AirClient["air_client.py<br/>(curl subprocess via stdin)"]
            Observations["observations.py<br/>(PM2.5 Parser & Severity Bands)"]
            UnifiedMap["unified_map.py<br/>(Folium Map Generator)"]
            TransportEngine["transport.py / connectivity.nearest<br/>(Haversine Distance)"]
        end

        subgraph FrontendLayer ["Client-Side UI (Browser runtime)"]
            AreaUI["static/areas.js<br/>(Leaflet Grid & Preferences)"]
            IndexUI["static/index.js<br/>(Air Explorer & iframe Bridge)"]
            SchoolUI["static/school_profile.js<br/>(Async Profile Fetcher)"]
            SharedUI["static/shared.js<br/>(XSS Escaping & Formatters)"]
        end
    end

    %% External Connections (Verified: Solid; Inferred: Dashed)
    OSMData ==>|"OSM Nodes & Ways"| BuildAreas
    UDISEData ==>|"School CSVs & KML"| BuildSchools
    UDISEData ==>|"Pincode KML"| BuildBoundaries
    BuildAreas -->|"Populates"| SQLiteDB
    BuildSchools -->|"Writes"| SchoolJSON
    BuildBoundaries -->|"Writes"| SchoolJSON
    EvaluateAreas -.->|"Generates"| ReportsJSON

    DataGov -->|"JSON AQI Records
(via curl stdin pipe)"| AirClient
    AirClient -->|"Normalizes Readings"| Observations
    AirClient -->|"Caches Observations"| DataStore
    DataStore <==|"Read-only Connection & LRU Cache"| SQLiteDB

    User <==|"HTTP GET/POST (Port 5000)"| AppEntry
    AppEntry --- AreaViews
    AppEntry --- SchoolViews
    
    AreaViews -->|"Queries Cells & Manifest"| DataStore
    AreaViews -->|"Computes Scores & Shortlist"| RankingEngine
    AreaViews -->|"Loads Group Archetypes"| ClusteringEngine
    SchoolViews -->|"Resolves Pincode via Ray-Casting"| SchoolEngine
    SchoolEngine -->|"Reads Profiles & Boundaries"| SchoolJSON

    AreaViews -->|"Renders HTML + browser_config"| AreaUI
    SchoolViews -->|"Renders HTML Snippet"| SchoolUI
    AppEntry -->|"Renders HTML + Folium Map"| IndexUI
    IndexUI -.->|"postMessage Event Bridge"| HostSidebar["Host Page Sidebar<br/>(Selection Details)"]

    AreaUI ==>|"Fetch Map Tiles"| OSMTiles
    IndexUI ==>|"Fetch Map Tiles"| OSMTiles
```

---

## 3. Architecture Component Inventory

| Component ID | Component Name | Responsibility | Runs Where | Inputs | Outputs | Communicates With | Evidence |
|---|---|---|---|---|---|---|---|
| `COMP-01` | **Flask App Bootstrap (`app.py`)** | Application initialization, blueprint registration, routing for `/air-quality` and `/connectivity`. | Server (Python WSGI process) | HTTP Requests, Environment variables (`.env`) | Rendered HTML pages | `area_views`, `school_views`, `air_client`, `transport`, `unified_map` | `app.py:1-99` |
| `COMP-02` | **Area Views Controller (`area_views.py`)** | Manages routes `/`, `/areas`, `/api/areas/<id>`, `/areas/export.csv`, `/areas/refresh-air`. | Server (Python WSGI process) | URL query parameters, form submissions | HTML responses, JSON detail payloads, CSV streams | `data_store`, `areas`, `clustering`, `air_client`, `observations` | `area_views.py:1-236` |
| `COMP-03` | **Recommendation Engine (`areas.py`)** | Mathematical scoring of service factors, must-have constraint validation, and ranking. | Server (Python memory) | Cell features, user weights, radii, caps, air stations, workplace coords | Scored cell dictionaries, eligibility status, contributions | `area_views.py`, `scripts/evaluate_areas.py` | `areas.py:1-127` |
| `COMP-04` | **Data Access Layer (`data_store.py`)** | SQLite read-only connection, memory LRU cache for 1,487 cells, air observation persistence. | Server (Python memory / SQLite) | SQL queries, raw API payloads | Cached cell lists, manifests, air records | `areas.sqlite`, `area_views.py`, `clustering.py` | `data_store.py:1-70` |
| `COMP-05` | **Secure Air API Client (`air_client.py`)** | Paginated consumption of data.gov.in AQI records using `curl` with stdin configuration. | Server (Python / curl child process) | State, City, `DATA_GOV_API_KEY` | Array of raw pollutant dictionaries | `api.data.gov.in`, `app.py`, `area_views.py` | `air_client.py:1-104` |
| `COMP-06` | **Observations Parser (`observations.py`)** | Station grouping, coordinate extraction, PM2.5 timestamp ordering, severity banding. | Server (Python memory) | Raw API records | Monitor dictionaries with latest PM2.5, timestamp, and severity color | `air_client.py`, `area_views.py`, `unified_map.py` | `observations.py:1-65` |
| `COMP-07` | **School Intelligence Layer (`school_profiles.py`)** | UDISE+ metric formatting, 2D ray-casting point-in-polygon spatial containment lookup. | Server (Python memory) | Latitude, Longitude, `pincode_profiles.json`, `pincode_boundaries.json` | Pincode string, structured statistical view dictionary | `school_views.py`, `data/schools/` | `school_profiles.py:1-164` |
| `COMP-08` | **Unsupervised Clustering (`clustering.py`)** | K-Means / Hierarchical area grouping over 16 normalized spatial features; stability checks. | Server (Python / scikit-learn) | Cell feature matrices | Cluster labels, profiles, silhouette scores, ARI stability metrics | `data_store.py`, `data/cluster_report.json` | `clustering.py:1-122` |
| `COMP-09` | **Transit Search Engine (`transport.py`)** | Nearest bus, metro, and airport lookup using spherical Haversine distance; Folium maps. | Server (Python / Folium) | Latitude, Longitude, search radius, limit | Ranked transit places dictionary, standalone Folium map HTML | `transport_data.py`, `connectivity/nearest.py` | `transport.py:1-61` |
| `COMP-10` | **Client Area Controller (`static/areas.js`)** | Client-side Leaflet map controller, interactive grid styling, factor slider updates, comparisons. | Client Web Browser | `browser_config` JSON, DOM events, mouse clicks | DOM mutations, fetch requests to `/api/areas/<id>` | Leaflet.js, `/api/areas/<id>`, `LocalyticsSchools` | `static/areas.js:1-407` |
| `COMP-11` | **Client School Loader (`static/school_profile.js`)** | Asynchronous fetch component to load school profile snippets upon grid/map clicks. | Client Web Browser | Latitude, Longitude, target DOM container | Injected HTML school profile card | `/schools/lookup`, `static/areas.js`, `static/index.js` | `static/school_profile.js:1-26` |
| `COMP-12` | **Offline Grid Builder (`scripts/build_areas.py`)** | Projects Delhi boundary to EPSG:32643, builds 1km spatial grid, queries 3D cKDTrees, writes SQLite. | Offline CLI Command | OSM PBF files, `delhi_boundary.geojson` | `data/areas.sqlite`, `data/area_manifest.json` | Pyosmium, PyProj, Shapely, SciPy | `scripts/build_areas.py:1-192` |

---

## 4. Architecture Connection Inventory

| Source Component | Destination Component | Data / Request Transferred | Mechanism / Protocol | Direction | Evidence |
|---|---|---|---|---|---|
| User Browser | `app.py` | HTTP GET/POST requests (`/`, `/air-quality`, `/connectivity`, `/schools`) | HTTP / TCP (Port 5000) | Bidirectional | `app.py:21,58`, `area_views.py:66` |
| `area_views.py` | `data_store.py` | Requests for cached cells, manifests, and cached air readings | Python function call (in-process) | Bidirectional | `area_views.py:71,83` |
| `data_store.py` | `data/areas.sqlite` | Read-only SQL queries (`SELECT payload FROM cells`) | SQLite3 C-API / URI mode (`mode=ro`) | Bidirectional | `data_store.py:15-20` |
| `area_views.py` | `areas.py` | Cell dictionaries, user weights, radii, caps, monitor arrays | Python function call (in-process) | Bidirectional | `area_views.py:85` |
| `air_client.py` | `api.data.gov.in` | HTTPS GET requests with pagination parameters | HTTPS via `curl` subprocess (stdin config) | Bidirectional | `air_client.py:30-55` |
| `air_client.py` | `data_store.py` | Persists successful air readings (`INSERT OR REPLACE INTO air_cache`) | SQLite3 C-API (timeout 15s) | Outward | `data_store.py:29-33` |
| `area_views.py` | `clustering.py` | Request for precomputed or live cluster labels (`request.args.get('clusters') == '1'`) | Python function call (in-process) | Bidirectional | `area_views.py:88-91` |
| Browser (`areas.js`) | `area_views.py` | HTTP GET `/api/areas/<id>?w_...` | AJAX / Fetch API (HTTP) | Bidirectional | `static/areas.js:132-139` |
| Browser (`school_profile.js`) | `school_views.py` | HTTP GET `/schools/lookup?lat=...&lon=...` | AJAX / Fetch API (HTTP) | Bidirectional | `static/school_profile.js:15` |
| `school_views.py` | `school_profiles.py` | Coordinate lookup request (`lat, lon`) | Python function call (in-process) | Bidirectional | `school_views.py:37` |
| `school_profiles.py` | `data/schools/` | Reads boundary rings and UDISE+ metric profiles | Local filesystem read (UTF-8 JSON) | Inward | `school_profiles.py:55,101` |
| Folium Map iframe | Parent Window (`index.js`) | Map point coordinates and rendered station HTML | HTML5 `window.postMessage` bridge | Inward (iframe to host) | `static/index.js:3-19`, `templates/combined_map.js.j2` |
| Web Browser | OpenStreetMap Tiles | Map tile image requests (`png`) | HTTPS (`https://{s}.tile.openstreetmap.org/`) | Bidirectional | `static/areas.js:9`, `transport.py:21` |