# PROJECT UNDERSTANDING REPORT: LOCALYTICS
**Comprehensive Technical Architecture, Codebase Audit & Educational Guide**

---

## 1. Report Metadata and Investigation Scope

* **Project Name:** Localytics
* **Repository Location:** `c:\Users\Jakki\OneDrive\Desktop\Studies\BITS\S1\Python\Project\Localytics`
* **Investigation Date:** October 29, 2026
* **Investigator Roles:** Senior Software Architect, Senior Software Engineer, Technical Documentation Engineer, Patient Technical Teacher
* **Primary Technologies Identified:** Python 3.14, Flask 3.1, SQLite 3 (with R-Tree extension), Folium / Leaflet.js, Shapely 2.0, PyProj 3.7, SciPy 1.15, Scikit-learn 1.6, Pyosmium 4.0, Vanilla JavaScript (ES6+), HTML5/CSS3, Jinja2
* **Target Audience:** Complete beginners seeking a ground-up conceptual and architectural understanding, as well as AI assistants and system architects tasked with modeling or refining high-level system diagrams.
* **Audit Scope:** 100% of executable source files, configuration manifests, offline pipelines, database contents, client-side scripts, and test files were inspected.
* **Testing Status:** All 59 regression tests in `tests/` were executed and passed (`59 passed in 14.04s`). Static linting via Ruff was verified (`All checks passed!`). Database schemas and manifest payloads in `data/areas.sqlite` were directly queried and verified.
* **Investigation Constraints & Safety:** Strictly read-only investigation. No application source code, configuration files, dependencies, or database records were modified or deleted. No private credentials or live API keys were copied into this documentation.

---

## 2. Executive Summary

**Localytics** is an urban analytics and preference-based neighborhood recommendation web application designed for the National Capital Territory of Delhi, India, accompanied by an interactive nationwide air-quality and transit exploration engine.

### The Core Problem It Solves
Finding where to live or locate an office in a complex, rapidly expanding megacity like Delhi is notoriously difficult. Commercial real-estate search portals suffer from three fundamental flaws:
1. **Commercial Bias:** Listings and recommendations are heavily distorted by sponsored advertisements and developer commissions.
2. **Opaque Scoring:** Portals use proprietary, unverifiable "livability scores" that hide their underlying assumptions and weights.
3. **Data Silos:** Environmental health indicators (such as real-time PM2.5 air pollution), public transportation networks (Delhi Metro and bus lines), daily urban services (schools, hospitals, parks, gyms, malls, EV charging stations), and institutional school metrics (UDISE+ data) are kept completely separate.

### How Localytics Solves It
Localytics replaces commercial guesswork with a **transparent, evidence-based spatial recommendation engine**:
- **Uniform Spatial Grid:** It partitions Delhi into a regular 1,000-meter (1 km) spatial grid consisting of **1,487 grid cells** projected in UTM Zone 43N (`EPSG:32643`).
- **Comprehensive Amenities Extraction:** It indexes **66,636 physical facilities** pre-extracted from OpenStreetMap (OSM) protocol buffer files (`.pbf`), classifying them into 10 categories and storing them in an embedded SQLite database backed by an R-Tree spatial index.
- **Strict Evidence & Zero-Imputation Rule:** When ranking areas according to a user's personal preferences (importance sliders from 0 to 5, local search radius of 1, 2, or 5 km, and must-have proximity constraints), Localytics adheres to an uncompromising rule: **if empirical evidence is missing, the cell is disqualified from ranking**. It never invents, guesses, or redistributes weights.
- **Integrated Environmental Context:** It pulls live air pollution readings (PM2.5) from the Government of India's Open Government Data portal (`data.gov.in`) via a secure subprocess, matching each grid cell to the nearest valid monitoring station within 5 km and 6 hours.
- **Institutional School Intelligence:** Rather than inventing a misleading "school quality score", it provides a dedicated institutional profile for 93 Delhi postal pincodes using official UDISE+ 2024-25 data, displaying real statistical distributions (medians and 10th-90th percentiles) for pupil-teacher ratios, teacher qualifications, and facilities.
- **Descriptive Machine Learning:** It employs unsupervised clustering (K-Means and Hierarchical) over 16 normalized spatial feature dimensions to discover recurring urban archetypes (e.g., dense transit cores vs. developing suburbs), keeping model predictions strictly isolated from suitability scoring.

---

## 3. Project Explained in One Minute

Localytics is a website that helps you find the best neighborhood to live in Delhi based on what matters most to you. Instead of looking at individual real estate listings, the city is divided into 1,487 equal one-kilometer square blocks. You use simple sliders to tell the application what you care about—such as being close to metro stations, good schools, hospitals, parks, gyms, electric vehicle chargers, or your workplace—and you can set strict rules, like requiring a metro station within one kilometer. The system scores every neighborhood transparently based on actual mapped evidence from OpenStreetMap and real-time PM2.5 air pollution monitors, showing you the top ten matches on an interactive map. Clicking any neighborhood reveals exactly how its score was calculated, marks nearby facilities on the map, and looks up the educational profile of that postal code using official government school census data. If data for a service you requested is missing in an area, the app openly marks that area as unranked rather than making a guess.

---

## 4. Beginner-Friendly Project Explanation

### The Real-World Analogy: The "House Hunting Transparency Scorecard"
Imagine you are hiring a personal assistant to help you choose a neighborhood to move to in a massive city like Delhi.

Most commercial real-estate websites act like **pushy real estate agents**: they steer you toward luxury high-rises that paid them advertising fees, give neighborhoods vague 5-star ratings without explaining why, and gloss over severe air pollution or the fact that the nearest metro station is a 45-minute trek.

**Localytics acts like an objective, hyper-meticulous researcher with a clipboard and a measuring tape:**
1. **The Grid:** The researcher lays a giant grid map over Delhi, creating 1,487 equal 1 km squares. Every square gets an ID tag (like `DL43_714_3167`) and a nearby landmark name.
2. **The Survey:** The researcher visits every square and counts all the bus stops, metro stations, schools, hospitals, parks, fitness centers, shopping malls, and EV charging points within 1 km, 2 km, and 5 km.
3. **Your Priorities:** You hand the researcher your personal rulebook: *"I care a lot about metro access (weight 4) and public parks (weight 3), I work at Connaught Place, and I must have a hospital within 2 kilometers."*
4. **The Scorecard:** The researcher calculates a math score from 0 to 100 for each square. The score combines straight-line proximity (how close the nearest amenity is) and variety (how many facilities exist nearby). If a square is missing hospital data or fails your 2 km metro rule, the researcher writes **"Unranked"** and shows it in grey.
5. **The Reality Checks:**
   - **Air Quality:** The researcher checks the nearest official air pollution monitor. If the air data is older than 6 hours or farther than 5 km away, the researcher refuses to guess the air score.
   - **Schools:** Instead of giving schools a fake "10/10" rating, the researcher pulls the official Ministry of Education census and tells you: *"In this pincode, half the schools have a pupil-teacher ratio of 30, 40% are run by the government, and 60% have smart boards."*

### Three Levels of Explanation

```text
Level 1: 30-Second Summary
Localytics is an open-source web application for exploring Delhi neighborhoods. It ranks 1 km grid blocks based on customized user priorities (transit, healthcare, green spaces, schools, workplace commute, and air quality) using real geographic data and zero commercial bias.

Level 2: The Non-Technical Guide
Localytics combines maps, government air pollution sensors, and school census statistics into one simple web tool. You move sliders to reflect your lifestyle, and the map highlights the best neighborhoods for you in green. You can compare up to three neighborhoods side-by-side or download the data as a spreadsheet.

Level 3: The Technical Blueprint
Localytics is a Python 3.14/Flask monolithic spatial web application. It combines an offline ETL pipeline that parses OpenStreetMap PBF files using Pyosmium into an SQLite R-Tree database with an in-memory analytical ranking engine, an asynchronous school profile ray-casting polygon locator, an unsupervised scikit-learn clustering classifier, and a Leaflet/Folium frontend.
```

---

## 5. Problem Statement, Users, and Use Cases

### The Problem
* **Black-Box Livability Scores:** Commercial platforms present composite scores without showing input weights, data freshness, or formula structures.
* **Commercial Influence:** Portals prioritize paid property developments over genuine livability metrics.
* **Fragmented Datasets:** Commute transit (bus/metro), environmental pollution (PM2.5), daily conveniences (parks, grocery/malls), and school infrastructure exist across disparate government and open-data portals with incompatible formats (PBF, CSV, KML, JSON REST APIs).
* **Subjective School Rankings:** Commercial school review platforms rely on unverified parent reviews rather than hard government infrastructure data.

### Intended Users
1. **Home Seekers and Renters:** Individuals and families moving to or within Delhi looking for neighborhoods tailored to their daily commute, school needs, and environmental preferences.
2. **Urban Planners & Academic Researchers:** Students and researchers studying spatial amenity distribution, public transit coverage gaps, and socio-spatial equity in the National Capital Region.
3. **Data Journalists & Civic Technologists:** Analysts investigating correlations between urban facilities, educational resources, and environmental quality.

### Primary Use Cases
* **Use Case 1: Customized Neighborhood Shortlisting:** A user selects weights for transit, parks, and hospitals, clicks on the map to mark their office, and receives an instant ranked list of the top 10 matching 1 km cells.
* **Use Case 2: Hard Proximity Filtering:** A user requires that any recommended neighborhood must have a metro station within 1 km and a hospital within 2 km. Cells failing these constraints are excluded.
* **Use Case 3: Neighborhood Comparison:** A user selects three shortlisted neighborhoods and views a side-by-side factor breakdown table.
* **Use Case 4: Map-Based School Profile Exploration:** A user clicks on any neighborhood on the map to inspect the UDISE+ school profile for that postal pincode.
* **Use Case 5: Nationwide Air Quality & Transit Ingestion:** A user searches for any city across India (e.g., Pune, Bengaluru) to view live monitoring stations color-coded by PM2.5 severity alongside mapped transport stops.

---

## 6. Features: Implemented vs Planned vs Unverified

To maintain rigorous scientific accuracy, every feature in the repository has been audited and classified into one of three categories:

| Feature / Capability | Classification | Technical Evidence & Implementation Details |
|---|---|---|
| **1 km Regular Delhi Spatial Grid** | **Verified Implemented** | `scripts/build_areas.py:80-94`. 1,487 cells generated in EPSG:32643, bounded by DataMeet municipal boundary (1,488.1 km²). |
| **OSM Amenity Extraction & Deduplication** | **Verified Implemented** | `osm_data.py:60-153`. Extracts nodes and ways; resolves overlaps by highest version/timestamp; merges same-name facilities within 100 m. |
| **Transparent Multi-Criteria Ranking** | **Verified Implemented** | `areas.py:66-127`. Balanced proximity (50%) and count (50%) formula. Strict zero-imputation policy. |
| **Must-Have Distance Constraints** | **Verified Implemented** | `areas.py:79-87`. Validates distance limits for metro, schools, hospitals, parks, and EV chargers (`pass`, `fail`, `unverified`). |
| **Workplace Distance Factor** | **Verified Implemented** | `areas.py:76-77`. Computes straight-line Haversine distance up to 50 km cap; interactive map click selection (`static/areas.js:108-131`). |
| **data.gov.in Live AQI Client** | **Verified Implemented** | `air_client.py:16-82`. Paginated HTTPS query using `curl` with stdin configuration to protect API keys. |
| **Real-Time Air Quality Persistence** | **Verified Implemented** | `data_store.py:23-64`. Persists queries and records in `air_cache` table in `areas.sqlite`. |
| **PM2.5 Scoring & Eligibility Gate** | **Verified Implemented** | `areas.py:18-56`. Nearest monitor within 5 km and 6 hours. Cap at 250 µg/m³. Older/farther readings excluded from scoring. |
| **UDISE+ School Profiles by Pincode** | **Verified Implemented** | `school_profiles.py:1-164`, `school_views.py:1-77`. 93 pincodes; management, stage, board, medium, PTR, teacher degrees, smart boards. |
| **Map-Click Ray-Casting Pincode Lookup** | **Verified Implemented** | `school_profiles.py:61-90`. Pure-Python 2D ray-casting algorithm resolving lat/lon to postal pincode. |
| **Unsupervised Spatial Clustering** | **Verified Implemented** | `clustering.py:10-122`. Evaluates K-Means & Hierarchical models ($k=2..6$); outputs silhouette score (0.357) and ARI stability (0.978). |
| **Side-by-Side Area Comparison** | **Verified Implemented** | `static/areas.js:308-367`. Allows user to select up to 3 areas for comparative tabular inspection. |
| **CSV Shortlist Export** | **Verified Implemented** | `area_views.py:180-216`. Exports ranked areas; protects against CSV formula injection. |
| **Nationwide Air Quality Explorer** | **Verified Implemented** | `app.py:21-56`, `unified_map.py:12-59`. Supports any Indian state/city search with Folium iframe rendering. |
| **School Quality Ranking Score** | **Explicitly Excluded** | `README.md:38,53-56`, `scripts/build_school_profiles.py:194`. Deliberately omitted due to high within-pincode variance and lack of outcome metrics. |
| **Commute Time in Minutes** | **Not Applicable / Excluded** | `README.md:40`. Network routing and traffic times are not implemented; all distances are Euclidean/Haversine. |
| **Water, Crime, Affordability Factors** | **Explicitly Disabled** | `README.md:40`. Disabled pending verified empirical public data sources. |
| **12-Person User Usability Study** | **Planned / Incomplete** | `README.md:77`, `scripts/evaluate_areas.py:53`. Documented as planned research; no empirical subject trials recorded. |
| **OSM Relation-Only Facilities** | **Known Limitation** | `osm_data.py:77`. Pipeline processes OSM nodes and ways only; complex relation-only boundaries may be omitted. |
| **OSM Way Centroid Accuracy** | **Approximation** | `osm_data.py:103-108`. Way coordinates are bounding-box centroids, not guaranteed building entrances. |
| **EV Charger Compatibility & Access** | **Unverified External** | `README.md:38`. Mapped charging points do not verify connector compatibility (CCS2, Type 2, GB/T) or public uptime. |

---

## 7. Technology Stack and Dependency Analysis

### Master Technology Inventory

| Technology | Category | What it is | Why this project uses it | Where it appears | Importance |
|---|---|---|---|---|---|
| **Python 3.14** | Programming Language | High-level interpreted language with robust scientific and web ecosystems. | Core programming language for entire backend, data processing, and test suite. | Root repository, all `.py` files | **Essential** |
| **Flask 3.1** | Web Framework | Lightweight, modular WSGI web application microframework. | Handles HTTP routing, blueprint modularity, request lifecycle, and template rendering. | `app.py`, `area_views.py`, `school_views.py` | **Essential** |
| **SQLite 3** | Database Engine | Serverless, self-contained, transactional SQL database engine. | Embedded local data storage for 1,487 grid cells, 66k facilities, and cached air readings. | `data/areas.sqlite`, `data_store.py` | **Essential** |
| **SQLite R-Tree Extension** | Spatial Indexing | Virtual table module for spatial bounding box range indexing. | Provides rapid geometric lookups for facilities without requiring heavy GIS servers like PostGIS. | `data_store.py`, `scripts/build_areas.py:166` | **Essential** |
| **Folium 0.19** | Geospatial Visualization | Python library wrapping Leaflet.js to generate interactive HTML maps. | Generates embedded Leaflet maps for nationwide air quality and transit search. | `unified_map.py`, `transport.py`, `app.py` | **Essential** |
| **Branca** | HTML/JS Templating | Supporting library for Folium providing Jinja2 element wrapping. | Injects custom JavaScript macros and Leaflet event bridges into Folium maps. | `unified_map.py:4,46-56` | **Supporting** |
| **Leaflet.js 1.9** | Frontend Cartography | Client-side JavaScript library for interactive vector and tile mapping. | Powers the interactive 1 km grid map, slider updates, marker clustering, and tooltips. | `static/areas.js`, `templates/areas.html` | **Essential** |
| **Shapely 2.0** | Computational Geometry | Geometry library for manipulation and analysis of planar features. | Computes municipal boundary union, polygon validity, and grid cell intersection. | `scripts/build_areas.py:15-16`, `test_areas.py` | **Essential** (Build) |
| **PyProj 3.7** | Coordinate Transformation | Python interface to PROJ cartographic projection software. | Transforms coordinates between WGS 84 (`EPSG:4326`) and UTM Zone 43N (`EPSG:32643`). | `scripts/build_areas.py:13,27-28` | **Essential** (Build) |
| **SciPy 1.15** | Scientific Computing | Advanced mathematics and spatial data structures library. | Provides `cKDTree` for 3D spherical nearest-neighbor and ball-query spatial indexing. | `scripts/build_areas.py:14,77-129` | **Essential** (Build) |
| **Scikit-learn 1.6** | Machine Learning | Python library for predictive modeling, clustering, and preprocessing. | Executes K-Means, Agglomerative clustering, median imputation, and stability scoring. | `clustering.py:18-21`, `scripts/evaluate_areas.py` | **Essential** (Clustering) |
| **NumPy 2.2** | Numerical Computing | Fundamental library for multi-dimensional array operations. | Handles feature matrices, array filtering, vector math, and random subsampling. | `clustering.py`, `scripts/build_areas.py` | **Essential** |
| **Pyosmium 4.0** | OSM Data Parsing | Fast C++ Python bindings for parsing OpenStreetMap PBF files. | Reads raw OSM node/way entities and extracts amenities and transit infrastructure. | `osm_data.py:7-80` | **Essential** (ETL) |
| **python-dotenv 1.0** | Configuration | Library for loading environment variables from `.env` files into `os.environ`. | Loads local development secrets such as `DATA_GOV_API_KEY`. | `app.py:5,17` | **Essential** |
| **curl (System CLI)** | Networking Binary | Command-line tool for transferring data with URLs. | Executes HTTPS requests to data.gov.in using stdin pipes to shield API keys. | `air_client.py:20,30-50` | **Essential** |
| **Jinja2 3.1** | Templating Engine | Full-featured template engine for Python. | Renders server-side HTML pages, macros, and embedded JavaScript templates. | `templates/*.html`, `templates/combined_map.js.j2` | **Essential** |
| **Pytest 8.3** | Testing Framework | Comprehensive Python test runner and assertion framework. | Executes the 59 automated unit, integration, and regression tests. | `tests/`, `pytest.ini` | **Development** |
| **Ruff 0.17** | Code Quality / Linter | Extremely fast Python linter and code formatter written in Rust. | Enforces code style, import sorting (`isort`), and PEP-8 conventions. | `ruff.toml` | **Development** |
| **djLint 1.47** | HTML Template Linter | Linter and formatter for HTML and Django/Jinja template syntax. | Validates formatting and syntax of Jinja2 HTML templates. | `requirements-dev.txt` | **Development** |

### In-Depth Technology Breakdown

#### 1. Flask & Jinja2
- **What it is:** A lightweight web application framework and templating engine.
- **Why Localytics uses it:** Localytics is an analytical tool with minimal state. Flask allows defining lightweight routes and blueprints without the heavyweight overhead of database ORMs or user authentication systems found in Django.
- **Where it appears:** `app.py`, `area_views.py`, `school_views.py`, `templates/`.
- **What happens if removed:** The entire web presentation and API layer would cease to function; the application would become a command-line script.

#### 2. SQLite 3 with R-Tree Extension
- **What it is:** A self-contained, serverless database engine embedded directly into the application process.
- **Why Localytics uses it:** Eliminates the need for external database servers (like PostgreSQL/PostGIS) or network latency. The database file `areas.sqlite` is entirely precomputed, read-only at runtime for area queries, and writable only for caching air readings.
- **Where it appears:** `data/areas.sqlite`, `data_store.py`.
- **What happens if removed:** The application would need to load raw GeoJSON files and rebuild spatial indices on every startup, increasing boot time and memory consumption dramatically.

#### 3. SciPy (cKDTree) & PyProj
- **What it is:** High-performance spatial indexing and coordinate projection libraries.
- **Why Localytics uses it:** Calculating straight-line distances from 1,487 grid centers to 66,636 facilities across multiple radii (1, 2, and 5 km) requires nearly 300 million pair-wise checks if done naively. Converting coordinates to a 3D unit sphere ($x, y, z$) and querying a `cKDTree` completes the entire precomputation in under 10 seconds.
- **Where it appears:** `scripts/build_areas.py`.
- **What happens if removed:** Offline grid generation would become computationally intractable or inaccurate due to naive spherical approximations.

#### 4. Scikit-learn
- **What it is:** Industry-standard machine learning toolkit.
- **Why Localytics uses it:** Powers the unsupervised spatial clustering subsystem, automatically discovering whether neighborhoods cluster into distinct structural types (e.g., highly connected urban cores vs. sparse peripheral tracts) without manual labeling.
- **Where it appears:** `clustering.py`, `scripts/evaluate_areas.py`.
- **What happens if removed:** The "Similar area groups" map layer and clustering stability reports would be disabled; the core ranking engine would continue to function unaffected.

## 8. Repository Structure and File Responsibilities

The codebase follows a clean, decoupled modular architecture. Core business logic is contained in root-level Python modules, offline pipeline commands are stored in `scripts/`, institutional education datasets are grouped in `data/schools/`, and client assets reside in `static/` and `templates/`.

### Comprehensive File Responsibility Inventory

| File Path | Responsibility | Important Imports | Exported Symbols / Key Functions | Callers & Dependents | Data Received | Data Output / Changes | Architectural Role |
|---|---|---|---|---|---|---|---|
| `app.py` | Primary WSGI entry point; configures Flask and top-level explorer routes. | `Flask`, `air_client`, `data_store`, `area_views`, `school_views`, `transport`, `unified_map` | `app`, `index()`, `connectivity()` | Python runtime (`python app.py`) | HTTP GET/POST queries | Rendered HTML pages | **Core Entry Point** |
| `config.py` | Central configuration constants, file paths, scoring weights, and color maps. | `pathlib.Path` | `ROOT`, `DATA_DIR`, `FACTORS`, `DEFAULTS`, `CATEGORY`, `FACILITY_COLORS`, `LOCAL_RADII`, `PM25_BANDS` | All modules | None | Read-only configuration dictionaries | **Configuration** |
| `area_views.py` | Controller blueprint for area exploration, ranking, detail JSON API, and CSV export. | `Flask.Blueprint`, `areas`, `clustering`, `data_store`, `air_client`, `observations` | `bp`, `explore()`, `detail()`, `export()`, `refresh_area_air()`, `preferences()` | `app.py` | Query params (`w_*`, `radius`, `cap`, `must_*`) | HTML page, JSON cell detail, CSV stream | **Controller** |
| `areas.py` | Core mathematical ranking engine, factor scoring, and constraint validation. | `config`, `geography.distance_km` | `evaluate()`, `rank()`, `service_score()`, `nearest_air()` | `area_views.py`, `scripts/evaluate_areas.py` | Cells, weights, constraints, air readings | Ranked candidate lists, contribution breakdowns | **Business Logic** |
| `air_client.py` | Subprocess-isolated client for fetching paginated air readings from data.gov.in. | `subprocess`, `json`, `os`, `shutil` | `fetch_records()`, `_fetch_records()`, `FetchError` | `app.py`, `area_views.py` | State, City, `DATA_GOV_API_KEY` | List of raw pollutant record dicts | **External API Client** |
| `data_store.py` | Data access layer for `areas.sqlite`, LRU in-memory cell caching, and air observation storage. | `sqlite3`, `json`, `functools.lru_cache`, `config.DATA_DIR` | `dataset()`, `cache_air()`, `air_records()`, `read_report()` | `area_views.py`, `clustering.py`, `scripts/evaluate_areas.py` | Raw API payloads, report names | Parsed cell objects, air cache rows, report JSON | **Data Access Layer** |
| `observations.py` | Normalizes air quality records, extracts latest valid PM2.5, assigns severity bands. | `zoneinfo.ZoneInfo`, `config.PM25_BANDS`, `geography.coordinates` | `latest_pm25()`, `severity()`, `group_monitors()`, `monitors()` | `app.py`, `area_views.py`, `unified_map.py` | Raw API observation rows | Station dictionaries with latest PM2.5 & colors | **Data Parser** |
| `geography.py` | Validates geographic coordinates, calculates spherical Haversine distances, consolidates names. | `math`, `collections.defaultdict` | `coordinates()`, `distance_km()`, `covered_radius()`, `consolidate_named()` | `areas.py`, `osm_data.py`, `transport.py`, `school_views.py` | Lat/Lon pairs, radii, facility rows | Clean floats, distance in km, consolidated lists | **Shared Utility** |
| `osm_data.py` | OpenStreetMap PBF parser; classifies facilities and merges duplicate geometries. | `osmium`, `hashlib`, `geography.consolidate_named` | `classify()`, `classify_transport()`, `extract_sources()` | `scripts/build_areas.py`, `connectivity/extract_transport.py` | OSM PBF file paths | Extracted facility dictionaries & metadata manifest | **GIS Data Processing** |
| `transport.py` | Queries nearby transit features and renders Folium radius maps. | `folium`, `connectivity.nearest`, `transport_data` | `search_transport()`, `transport_map()` | `app.py` | Lat, Lon, radius, limit | Ranked transit matches, Folium HTML | **Service / Rendering** |
| `transport_data.py` | Loads transport records from CSV and extracts bounding box extents from JSON metadata. | `csv`, `json`, `pathlib.Path`, `geography.coordinates` | `load_transport()`, `source_bounds()` | `transport.py`, `unified_map.py` | File paths | List of transport dictionaries, bounding boxes | **Data Loader** |
| `unified_map.py` | Builds interactive Folium maps combining air quality monitors with transit layers. | `folium`, `branca.element`, `observations`, `transport_data` | `build_map()` | `app.py` | Air observation rows | Folium HTML map string, station counts | **Map Generator** |
| `school_profiles.py` | Loads UDISE+ school data and implements ray-casting point-in-polygon containment. | `json`, `re`, `config.SCHOOL_DIR` | `load_profiles()`, `load_boundaries()`, `in_polygon()`, `pincode_at()`, `view()` | `school_views.py` | Coordinates, pincode strings | Pincode string, formatted indicator dictionaries | **Domain Logic** |
| `school_views.py` | Controller blueprint for school catalog (`/schools`), detail view, and dynamic coordinate lookup. | `flask.Blueprint`, `school_profiles`, `geography.coordinates` | `bp`, `index()`, `lookup()`, `detail()`, `register()` | `app.py` | HTTP request coordinates, pincode paths | Rendered HTML templates & snippets | **Controller** |
| `clustering.py` | Unsupervised scikit-learn clustering (K-Means/Hierarchical) and bootstrap stability validation. | `sklearn.cluster`, `sklearn.impute`, `sklearn.preprocessing`, `sklearn.metrics`, `numpy` | `clustering()` | `area_views.py`, `scripts/evaluate_areas.py` | Cell feature matrices | Cluster labels, profiles, silhouette scores | **Machine Learning** |
| `connectivity/nearest.py` | Standalone nearest-transit lookup using Haversine distances. | `geography.coordinates`, `geography.distance_km`, `transport_data` | `nearest()` | `transport.py` | Lat, Lon, category, radius, limit | Sorted list of nearest transit dictionaries | **Domain Utility** |
| `connectivity/extract_transport.py` | CLI tool to extract bus stops, metro stations, and airport terminals from PBF files. | `osm_data`, `argparse`, `csv`, `json` | `main()` | CLI invocation | Raw OSM PBF files | `transport_locations.csv`, `metadata.json` | **Offline Pipeline** |
| `scripts/build_areas.py` | Builds `data/areas.sqlite` and `area_manifest.json` from raw PBF files and boundary GeoJSON. | `pyproj`, `scipy.spatial.cKDTree`, `shapely`, `sqlite3`, `osm_data` | `build()` | CLI invocation | PBF files, `delhi_boundary.geojson` | Precomputed `areas.sqlite` database | **Offline Pipeline** |
| `scripts/build_school_profiles.py` | Aggregates raw UDISE+ CSVs into pincode-level statistical distributions. | `csv`, `json`, `argparse` | `build()`, `school_records()`, `profile_of()` | CLI invocation | Folder of UDISE+ CSV files | `data/schools/pincode_profiles.json` | **Offline Pipeline** |
| `scripts/build_pincode_boundaries.py` | Parses India Post KML boundary files into compact, rounded GeoJSON boundary polygons. | `xml.etree.ElementTree`, `json`, `re` | `parse()`, `ring()`, `main()` | CLI invocation | `Delhi-Pincodes.kml` | `data/schools/pincode_boundaries.json` | **Offline Pipeline** |
| `scripts/evaluate_areas.py` | Generates ranking baseline comparisons and validates clustering stability across resamples. | `areas`, `clustering`, `data_store`, `config.DEFAULTS` | `evaluate()` | CLI invocation | `areas.sqlite` | `data/evaluation_report.json`, `cluster_report.json` | **Evaluation Script** |

---

## 9. Core Components and Their Relationships

### Component Boundaries & Communication Patterns

1. **Analytical Recommendation Core (`areas.py`):**
   - Pure functional design. It holds no global state, performs no I/O, and touches no database.
   - Given a list of cell dictionaries and a dictionary of weights, it performs synchronous in-memory numerical evaluations.
   - Decoupled from Flask; easily importable into offline evaluation scripts (`scripts/evaluate_areas.py`) or headless testing environments.

2. **Database & Cache Management (`data_store.py`):**
   - Wraps SQLite connections with `file:{DB}?mode=ro&uri=True` to prevent accidental database mutations during web requests.
   - Employs `@lru_cache(maxsize=1)` on `dataset()`: the 1,487 cell payloads and JSON manifest are deserialized once from SQLite into memory and subsequently served with zero disk I/O.
   - Maintains an isolated `air_cache` table for asynchronous observation persistence.

3. **External Ingestion Isolation (`air_client.py`):**
   - Shields the main Python process from network hangs and memory leaks.
   - Invokes `curl` as an external subprocess with `--connect-timeout 15` and `--max-time 120`.
   - Passes the URL and sensitive API key over `stdin` (`curl --config -`), ensuring that credentials are never exposed in process lists (`ps` or Windows Task Manager).

4. **School Spatial Boundary Subsystem (`school_profiles.py`):**
   - Independent spatial engine. It does not rely on Shapely or GDAL at runtime.
   - Uses an optimized 2D ray-casting point-in-polygon algorithm (`in_polygon()`) to perform containment checks against 92 Delhi postal polygons in sub-millisecond time.

5. **Clustering & Archetype Engine (`clustering.py`):**
   - Operates in strict read-only mode against precalculated reports (`data/cluster_report.json`).
   - If the precomputed report is missing or out of date relative to the database manifest timestamp, it dynamically fits K-Means and Hierarchical clustering models on the fly.
   - **Architectural Boundary:** Cluster labels are strictly informative (used for categorical map coloring) and are never fed back into area suitability scoring.

---

## 10. Startup and Initialization Sequence

When a developer runs `python app.py`, the following sequence executes:

```text
Step 1: Python Runtime Initialization
└── python app.py executes in the active virtual environment (.venv).

Step 2: Environment Variable Loading (app.py:17)
└── dotenv.load_dotenv(ROOT / ".env") reads local environment variables into os.environ.
    └── Extracts DATA_GOV_API_KEY if present.

Step 3: Flask Application Instantiation (app.py:18)
└── app = Flask(__name__) creates the central WSGI application object.

Step 4: Route & Blueprint Registration (app.py:95-96)
├── register_area_views(app) registers the 'areas' blueprint (area_views.py:28).
│   └── Exposes routes: '/', '/areas', '/api/areas/<cell_id>', '/areas/export.csv', '/areas/refresh-air', '/areas/evaluation.json'.
└── register_school_views(app) registers the 'schools' blueprint (school_views.py:8).
    └── Exposes routes: '/schools', '/schools/<pincode>', '/schools/lookup'.

Step 5: Top-Level Route Definition (app.py:21, 58)
├── Defines /air-quality route (index view for nationwide AQI exploration).
└── Defines /connectivity route (nearby transit search view).

Step 6: WSGI Server Binding (app.py:98-99)
└── If executed as main, app.run(host="127.0.0.1", port=5000, debug=False) starts the server.
    └── Listens on TCP port 5000; ready to process incoming HTTP requests.
    └── (Note: data_store.dataset() is lazily loaded upon the first HTTP request to '/').
```

---

## 11. End-to-End Execution Traces

### Execution Trace 1: User Visits Homepage, Ranks Areas, and Inspects a Cell

* **Goal:** A user searches for neighborhoods in Delhi with high priority on metro access, public green spaces, and air quality, then clicks cell `DL43_714_3167` to view details.

```text
1. Request Ingestion:
   - User Browser sends GET request to http://127.0.0.1:5000/?w_transit=4&w_park=3&w_air=5&radius=2&cap=10.
   - Handled by area_views.py:explore() (Line 68).

2. Data Loading & Lazy Caching:
   - explore() calls data_store.dataset() (Line 71).
   - data_store.dataset() executes sqlite3.connect("file:data/areas.sqlite?mode=ro").
   - Deserializes JSON payloads for 1,487 cells into memory. @lru_cache caches the list.

3. Preference Parsing & Validation:
   - preferences(request.args) parses weights into a float dictionary (Line 37-63).
   - Validates that weights are finite numbers between 0 and 5, radius is 1, 2, or 5 km, cap is 5, 10, or 20.

4. Environmental Context Retrieval:
   - data_store.air_records() retrieves cached Delhi AQI readings from SQLite (Line 83).
   - observations.monitors(records) parses readings and identifies latest PM2.5 values.

5. Scoring & Ranking Execution:
   - areas.rank(cells, weights, radius=2, cap=10, stations, workplace=None, must={}) is invoked (Line 85).
   - For each of the 1,487 cells:
     * areas.evaluate() calculates service_score() for 7 categories (school, hospital, park, gym, mall, ev, airport) and transit (bus + metro average).
     * areas.nearest_air() locates the nearest valid monitor within 5 km and 6 hours.
     * Computes weighted sum: Total = sum(100 * (w_i / total_w) * factor_score_i).
     * Missing check: If any factor with w > 0 has score is None, cell is marked unranked (score = None).
   - Candidates are sorted: valid scores descending, unranked cells placed at the bottom.

6. Map FeatureCollection Assembly:
   - explore() converts 1,487 cells into a GeoJSON FeatureCollection (Lines 92-107).
   - Each polygon feature includes properties: id, label, score, group (cluster ID), and missing count.

7. Server-Side HTML Rendering:
   - Flask renders templates/areas.html with top 10 eligible areas and embeds browser_config JSON.
   - Response sent to browser (HTTP 200).

8. Client-Side Leaflet Map Initialization:
   - Browser executes static/areas.js.
   - L.geoJSON() renders 1,487 vector polygons colored by score (Green: >=70, Orange: 40-69, Red: <40, Grey: Unranked).
   - Air quality monitor markers are rendered with severity dots.

9. Cell Inspection & Detail AJAX Fetch:
   - User clicks polygon DL43_714_3167 on the Leaflet map.
   - areas.js:inspect("DL43_714_3167") executes an asynchronous fetch to /api/areas/DL43_714_3167?w_transit=4...
   - Handled by area_views.py:detail() (Line 166).
   - Returns JSON payload with factor scores, nearest facility lists, and air monitor distance.

10. Sidebar Update & Async School Profile Lookup:
    - areas.js renders factor contribution table, nearest facilities, and air quality monitor age.
    - areas.js invokes LocalyticsSchools.load(container, lat, lon) (static/school_profile.js:6).
    - Client sends GET request to /schools/lookup?lat=28.6139&lon=77.2090.
    - Handled by school_views.py:lookup() (Line 28).
    - school_profiles.pincode_at() tests the coordinates against 92 boundary polygons using ray-casting.
    - Finds containing pincode 110001. Returns rendered HTML snippet (templates/school_snippet.html).
    - Browser injects school management mix and PTR percentiles into the sidebar.
```

---

### Execution Trace 2: User Searches Nationwide Air Quality & Local Connectivity

* **Goal:** A user searches for air pollution levels in Pune, Maharashtra, views monitoring stations on a Folium map, and clicks a station to view details.

```text
1. User Form Submission:
   - User navigates to http://127.0.0.1:5000/air-quality.
   - Fills state="Maharashtra", city="Pune" and clicks "Search".
   - Browser sends HTTP POST to /air-quality with form data (app.py:30).

2. API Client Invocation:
   - app.py calls air_client.fetch_records("Maharashtra", "Pune") (Line 38).
   - air_client._fetch_records() checks shutil.which("curl").
   - Builds curl stdin configuration string: url = "https://api.data.gov.in/resource/3b01bcb8...?api-key=...&filters[state]=Maharashtra&filters[city]=Pune".
   - Executes subprocess.run(["curl", "--config", "-", ...], capture_output=True, timeout=125).

3. Paginated Response Ingestion:
   - Parses stdout as JSON. Appends 100 records.
   - Checks offset and total count. If additional pages exist, loops up to 200 pages.
   - Returns complete array of pollutant dictionaries.

4. Persistent Caching:
   - data_store.cache_air("Maharashtra", "Pune", records) executes (Line 39).
   - Serializes records and stores them in SQLite air_cache table under key '["maharashtra", "pune"]'.

5. Folium Map Generation:
   - unified_map.build_map(records) is called (Line 42).
   - observations.group_monitors() groups raw readings by (station, lat, lon) and extracts latest PM2.5.
   - transport_data.load_transport(optional=True) loads local transit stops if available.
   - folium.Map() creates a Leaflet map centered at average monitor coordinates.
   - Injects custom JavaScript macro templates/combined_map.js.j2 and /static/shared.js.
   - Generates standalone map HTML via m._repr_html_().

6. Response Rendering & Client Display:
   - Flask renders templates/index.html with the embedded Folium iframe (Line 45).
   - Browser displays station markers color-coded by PM2.5 severity.

7. Map Click & postMessage Bridge:
   - User clicks a station marker inside the Folium iframe.
   - combined_map.js.j2 captures click and emits window.parent.postMessage({type: 'localytics:selection', html: '...', lat: 18.52, lon: 73.85}, '*').
   - static/index.js receives the message, validates event.source === frame.contentWindow, and renders details into the host page sidebar.
```

---

## 12. Data Flow and Business Logic

### Mathematical Scoring Formulation

For any grid cell $c$, search radius $R \in \{1, 2, 5\}\text{ km}$, and count cap $C \in \{5, 10, 20\}$, the suitability score is computed as follows:

#### 1. Service Factor Score (`service_score` in `areas.py:58-64`)
For any facility category $k$ (schools, hospitals, parks, gyms, malls, EV chargers, airport terminals):
- Let $d_k$ be the straight-line distance (in km) to the nearest mapped facility.
- Let $n_k$ be the count of mapped facilities within radius $R$ (or 25 km for airport terminals).
- If the extract extent does not cover radius $R$ around the cell (`coverage == False`), then $\text{Score}_k = \text{None}$.
- Otherwise, the score is the unweighted average of **Proximity** and **Density**:
  $$\text{Proximity}_k = 1 - \min\left(\frac{d_k}{R}, 1\right)$$
  $$\text{Density}_k = \min\left(\frac{n_k}{C}, 1\right)$$
  $$\text{Score}_k = 0.5 \times \text{Proximity}_k + 0.5 \times \text{Density}_k$$

#### 2. Transit Composite Score (`areas.py:72-73`)
Transit combines bus stops and metro stations equally:
$$\text{Score}_{\text{transit}} = \frac{\text{Score}_{\text{bus\_stop}} + \text{Score}_{\text{metro\_station}}}{2}$$
If either bus or metro coverage is missing, $\text{Score}_{\text{transit}} = \text{None}$.

#### 3. Air Quality Indicator Score (`areas.py:18-56`)
- Locates all monitors within $\le 5\text{ km}$ having an observation age $\le 6\text{ hours}$ and non-negative finite PM2.5 value.
- Selects the nearest eligible monitor $m$. If none qualify, $\text{Score}_{\text{air}} = \text{None}$.
- Normalizes using the project cap ($250\,\mu\text{g}/\text{m}^3$):
  $$\text{Score}_{\text{air}} = 1 - \min\left(\frac{\text{PM}_{2.5}}{250}, 1\right)$$

#### 4. Workplace Proximity Score (`areas.py:76-77`)
- Let $d_{\text{work}}$ be the straight-line distance to the user's selected workplace.
- Normalized against a 50 km cap:
  $$\text{Score}_{\text{workplace}} = 1 - \min\left(\frac{d_{\text{work}}}{50}, 1\right)$$

#### 5. Must-Have Constraint Evaluation (`areas.py:78-87`)
For each category constraint $k$ with required maximum distance $D_{\text{max}}$:
- If `coverage == False`, status is `"unverified"`.
- If $d_k \le D_{\text{max}}$, status is `"pass"`.
- If $d_k > D_{\text{max}}$ or no facility exists, status is `"fail"`.

#### 6. Total Weighted Composite Score (`areas.py:88-101`)
- Let $w_k \in [0, 5]$ be the user-assigned weight for factor $k$.
- Total weight $W = \sum_k w_k$.
- **Eligibility Check:** A cell is strictly **eligible** if and only if:
  1. $W > 0$.
  2. For every factor $k$ where $w_k > 0$, $\text{Score}_k \ne \text{None}$.
  3. Every must-have constraint status equals `"pass"`.
- If eligible:
  $$\text{Total Score} = \sum_{k, w_k > 0} 100 \times \left(\frac{w_k}{W}\right) \times \text{Score}_k$$
- If ineligible, $\text{Total Score} = \text{None}$ (displayed as "Unranked").

---

## 13. Database and Storage Analysis

### SQLite Schema (`data/areas.sqlite`)

The database contains 5 primary tables and 3 R-Tree virtual indexing tables:

```sql
-- 1. Metadata Manifest Table
CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- Contains 1 row with key='manifest', holding the complete JSON metadata for the grid build
-- (bounding area: 1,488.1 km², CRS: EPSG:32643, built_at timestamp, SHA256 hashes).

-- 2. Grid Cells Table
CREATE TABLE cells (
    id TEXT PRIMARY KEY,    -- e.g., 'DL43_714_3167'
    lat REAL,               -- Centroid latitude (WGS 84)
    lon REAL,               -- Centroid longitude (WGS 84)
    label TEXT,             -- Nearby locality name (e.g., 'Connaught Place vicinity (0.8 km)')
    payload TEXT            -- Full JSON object containing polygon geometry and precalculated features
);
-- Contains 1,487 rows. Indexed by primary key.

-- 3. Facilities Table
CREATE TABLE facilities (
    id INTEGER PRIMARY KEY, -- Sequential integer ID (0 to 66,635)
    category TEXT,          -- school, hospital, park, gym, mall, ev, bus_stop, metro_station, airport_terminal
    name TEXT,              -- Facility name or 'Unnamed'
    payload TEXT            -- Full JSON metadata (OSM tags, lat, lon, coordinate method)
);
-- Contains 66,636 physical mapped facilities.

-- 4. Spatial R-Tree Index Table
CREATE VIRTUAL TABLE facility_index USING rtree(
    id,                     -- Foreign key referencing facilities(id)
    min_lon, max_lon,       -- Bounding box longitude
    min_lat, max_lat        -- Bounding box latitude
);
-- Provides hardware-accelerated 2D bounding-box spatial queries.

-- 5. Persistent Air Observation Cache Table
CREATE TABLE air_cache (
    query TEXT PRIMARY KEY, -- JSON array of normalized query: '["state", "city"]'
    fetched_at TEXT,        -- ISO 8601 UTC timestamp of fetch
    payload TEXT            -- Full JSON string of returned data.gov.in records
);
```

### Static Flat Datasets

1. `data/schools/pincode_profiles.json` (174 KB):
   - Precomputed institutional metrics for 93 Delhi postal pincodes compiled from UDISE+ 2024-25.
   - Records total schools (5,781 total across Delhi), student enrollments, teacher counts, management splits, and 10th/50th/90th percentiles for PTR, students-per-classroom, and teacher qualifications.
2. `data/schools/pincode_boundaries.json` (386 KB):
   - Compact GeoJSON boundary definitions for 92 Delhi postal pincodes converted from India Post KML.
   - Coordinates rounded to 5 decimal places (~1 meter precision) with polygon holes preserved.
3. `connectivity/transport_locations.csv` (1.14 MB):
   - Flattened CSV containing 7,132 transit features (bus stops, metro stations, airport terminals) with OSM IDs, version timestamps, and coordinate derivation methods.
4. `data/cluster_report.json` & `data/evaluation_report.json`:
   - Offline evaluation artifacts capturing baseline ranking comparisons and scikit-learn clustering stability metrics.

---

## 14. APIs and External Integrations

### Internal HTTP Endpoints

| HTTP Method | Route / Path | Query / Body Parameters | Response Format | Purpose | Authentication |
|---|---|---|---|---|---|
| `GET` | `/` and `/areas` | `w_*` (weights 0-5), `radius` (1,2,5), `cap` (5,10,20), `must_*`, `clusters` (0/1) | HTML (`text/html`) | Homepage: interactive area ranking, Leaflet map, filters, and top 10 shortlist. | None |
| `GET` | `/api/areas/<cell_id>` | `w_*`, `radius`, `cap`, `must_*`, `work_lat`, `work_lon` | JSON (`application/json`) | Asynchronous detailed breakdown of a single cell's scores, nearest facilities, and air status. | None |
| `GET` | `/areas/export.csv` | `w_*`, `radius`, `cap`, `must_*`, `work_lat`, `work_lon` | CSV (`text/csv`) | Downloads ranked candidate list as a spreadsheet with injection protection. | None |
| `POST` | `/areas/refresh-air` | None | HTTP 302 Redirect | Triggers background fetch of live Delhi air readings from data.gov.in. | None |
| `GET` | `/areas/evaluation.json` | None | JSON File Download | Downloads the precomputed evaluation baseline report. | None |
| `GET` | `/air-quality` | None | HTML (`text/html`) | Initial nationwide station explorer page with empty Folium map. | None |
| `POST` | `/air-quality` | `state` (max 100 chars), `city` (max 100 chars) | HTML (`text/html`) | Queries data.gov.in, persists readings, renders Folium map with station pins. | None |
| `GET` | `/connectivity` | None | HTML (`text/html`) | Initial nearby transit search form. | None |
| `POST` | `/connectivity` | `latitude`, `longitude`, `radius` (0.1-100), `limit` (1-20) | HTML (`text/html`) | Searches local transit CSV, returns sorted table and Folium map. | None |
| `GET` | `/schools` | None | HTML (`text/html`) | Master catalog listing all 93 Delhi school pincodes with sorting and filtering. | None |
| `GET` | `/schools/<pincode>` | URL path: 6-digit pincode | HTML (`text/html`) | Detailed institutional profile for a specific pincode alongside Delhi averages. | None |
| `GET` | `/schools/lookup` | `lat` (float), `lon` (float) | HTML Fragment (`text/html`) | Ray-casting point-in-polygon lookup returning an HTML profile card for map popups. | None |

### External Third-Party Integrations

1. **Open Government Data Platform India (`api.data.gov.in`):**
   - **Resource ID:** `3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69` (Real-Time National Air Quality Index).
   - **Protocol:** HTTPS REST API returning JSON.
   - **Authentication:** `api-key` query parameter passed via `DATA_GOV_API_KEY`.
   - **Implementation:** `air_client.py:28-50`. Uses `curl` subprocess with configuration piped over `stdin` to prevent process-table credential leakage.
   - **Error Handling & Retries:** Handles timeouts (120s max), HTTP 502 bad gateway errors, repeated page detection (infinite loop guard), and case-insensitive fallback logic for state/city names.
2. **OpenStreetMap Tile Infrastructure:**
   - **Tile URL:** `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`.
   - **Protocol:** HTTPS GET for raster PNG tiles.
   - **Attribution:** `© OpenStreetMap contributors, ODbL`.

## 15. AI/ML Analysis

### Machine Learning Architecture & Objectives
Localytics integrates an **unsupervised spatial clustering subsystem** implemented in `clustering.py` and evaluated via `scripts/evaluate_areas.py`.

* **Objective:** Discover natural, recurring urban amenity archetypes across Delhi's 1,487 cells without human labeling bias (e.g., distinguishing dense, highly connected metropolitan cores from developing peripheral neighborhoods).
* **Architectural Decoupling (Critical Rule):** Model clustering is **purely descriptive**. Cluster assignments do not contribute bonus points or alter weights in the multi-criteria ranking engine. User suitability scores are derived exclusively from transparent mathematical formulas.

### Feature Engineering & Preprocessing Pipeline
For each of the 1,487 cells, a 16-dimensional feature vector is extracted representing urban amenities at a 2 km search radius across 8 categories:
$$\vec{x} = \begin{bmatrix} n_{\text{bus}}, d_{\text{bus}}, n_{\text{metro}}, d_{\text{metro}}, n_{\text{school}}, d_{\text{school}}, n_{\text{hosp}}, d_{\text{hosp}}, n_{\text{park}}, d_{\text{park}}, n_{\text{gym}}, d_{\text{gym}}, n_{\text{mall}}, d_{\text{mall}}, n_{\text{ev}}, d_{\text{ev}} \end{bmatrix}$$
where $n_k$ is the facility count and $d_k$ is the nearest straight-line distance (capped at 10 km).

```text
Raw Feature Extraction (clustering.py:23-38)
└── Extracts counts and distances for 8 categories from cell['features']['2'].
    └── Missing coverage features assigned np.nan.

Feature Selection & Variance Filtering (clustering.py:40-42)
└── Drops columns with >20% missing values or zero standard deviation.
    └── Verified: All 16 features pass and are retained.

Imputation & Normalization Pipeline (clustering.py:51-53)
├── SimpleImputer(strategy="median", add_indicator=True)
│   └── Replaces NaNs with the median value of the feature and appends missingness indicator flags.
└── StandardScaler()
    └── Centers features to mean 0 and scales to unit variance: z = (x - mu) / sigma.
```

### Model Selection, Evaluation, and Tuning
The module runs an exhaustive grid search across two clustering families for cluster counts $k \in \{2, 3, 4, 5, 6\}$:
1. **K-Means Clustering:** `KMeans(n_clusters=k, n_init=10, random_state=7)`.
2. **Agglomerative Hierarchical Clustering:** `AgglomerativeClustering(n_clusters=k)`.

Each trial configuration is evaluated using the **Silhouette Coefficient** over the normalized feature space ($Z$):
- Clusters with fewer than 10 cells are rejected as degenerate.
- The highest silhouette score determines the winning model.

**Actual Recorded Evaluation Results (`data/cluster_report.json`):**
- **Optimal Algorithm:** K-Means
- **Optimal Cluster Count ($k$):** 2
- **Silhouette Coefficient:** $0.357$ (indicating moderate structural separation between dense core areas and peripheral tracts).

### Cluster Stability & Reliability Validation
To ensure that discovered clusters are not artifacts of sampling noise or random seed selection, `clustering.py:82-92` performs a **5-fold bootstrap resampling stability test**:
- In each repeat, an 80% subsample of cells ($0.8 \times 1487 = 1189$ cells) is drawn without replacement.
- The full imputation and scaling pipeline is refit on the subsample, and a new K-Means model is trained.
- Subsample cluster assignments are compared against the full-dataset cluster assignments on overlapping cells using the **Adjusted Rand Index (ARI)**.
- **Recorded Stability Score:** $\text{ARI} = 0.978$ (extremely high stability, proving that the 2-cluster structure is statistically robust and reproducible).

---

## 16. Configuration, Setup, and Execution Guide

### Prerequisites
* **Operating System:** Windows, Linux, or macOS.
* **Python Runtime:** Python 3.10 to 3.14 (Verified running on Python 3.14.6 in `.venv`).
* **System Networking Tool:** `curl` must be installed and accessible in the system `PATH` (used by `air_client.py`).
* **Memory / Disk:** Minimum 2 GB RAM; ~100 MB free disk space for application files and SQLite database.

### Setup and Virtual Environment Configuration
All commands are designed to run in PowerShell (Windows) or Bash:

```bash
# 1. Clone or navigate to the repository directory
cd Localytics

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate the virtual environment
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# 4. Install runtime and development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 5. Configure API Key (Optional, for live air-quality refreshes)
# Copy example template and add your data.gov.in key:
cp .env.example .env
```

### Running the Web Application
```bash
# Start the Flask development server
python app.py
```
* **Local Access URLs:**
  - Area Recommendations (Homepage): `http://127.0.0.1:5000/`
  - Nationwide Air Quality & Transit Explorer: `http://127.0.0.1:5000/air-quality`
  - Nearby Transit Search: `http://127.0.0.1:5000/connectivity`
  - School Profiles Catalog: `http://127.0.0.1:5000/schools`

### Running the Test Suite & Quality Linters
```bash
# Execute the full Pytest regression test suite
python -m pytest -q
# Verified Output: 59 passed in ~14 seconds

# Run Ruff linter checks
ruff check .
# Verified Output: All checks passed!

# Check code formatting with Ruff
ruff format --check .
```

### Offline Data Rebuild Pipelines (Optional / Maintenance)
The bundled SQLite database and school profiles are prebuilt. Rebuilding is only necessary if updating underlying OpenStreetMap or UDISE+ source files:

```bash
# Rebuild the 1km area grid from raw OSM PBF extracts:
python scripts/build_areas.py /path/to/delhi.pbf /path/to/other1.pbf

# Recompute baseline evaluation and clustering reports:
python scripts/evaluate_areas.py

# Rebuild school profiles from UDISE+ CSVs:
python scripts/build_school_profiles.py /path/to/udise-folder

# Rebuild pincode boundary polygons from India Post KML:
python scripts/build_pincode_boundaries.py /path/to/Delhi-Pincodes.kml
```

---

## 17. Security, Quality, and Technical Risks

### Evidence-Based Security Audit

1. **API Key Protection & Subprocess Isolation:**
   - **Finding:** The application requires a `DATA_GOV_API_KEY` for fetching real-time air quality data.
   - **Implementation:** In `air_client.py:28-48`, the key is never passed as a command-line flag (which would be visible in `ps` or task manager). Instead, `curl` is invoked with `--config -`, piping the URL and query parameters securely via `stdin`.
   - **Verdict:** Secure implementation.

2. **Spreadsheet Formula Injection (CSV Injection):**
   - **Finding:** In `/areas/export.csv`, user-selected areas are exported to CSV. If an OpenStreetMap locality name began with an executable formula character (`=`, `+`, `-`, `@`), a malicious contributor to OSM could execute arbitrary commands in an end-user's Excel sheet.
   - **Implementation:** In `area_views.py:205-206`, locality labels starting with formula characters are automatically sanitized by prepending a single quote (`'`).
   - **Verdict:** Confirmed mitigated.

3. **Cross-Site Scripting (XSS) in Map Popups:**
   - **Finding:** Dynamic feature names and air station labels are rendered in Leaflet map tooltips.
   - **Implementation:** In `static/shared.js:2-15`, `Localytics.escape()` rigorously escapes HTML special entities (`&`, `<`, `>`, `"`, `'`).
   - **Verdict:** Confirmed mitigated.

4. **Authentication & Authorization Absence:**
   - **Finding:** There is no authentication or user session mechanism. All endpoints (`/`, `/api/areas/<id>`, `/areas/refresh-air`) are public.
   - **Risk:** If exposed publicly to the internet, malicious actors could flood `/areas/refresh-air` to trigger repeated outbound API calls to `data.gov.in`.
   - **Recommendation:** Rate-limit `/areas/refresh-air` or restrict administrative refresh routes behind basic authentication if deployed publicly.

5. **Cross-Origin Resource Sharing (CORS) & CSRF:**
   - **Finding:** Cross-Site Request Forgery (CSRF) tokens are not implemented on POST routes (`/air-quality`, `/connectivity`, `/areas/refresh-air`).
   - **Risk:** Low for local execution, but could allow external web pages to trigger air refreshes if exposed to public browser traffic.

---

## 18. High-Level Architecture Narrative

Localytics is designed as a **data-centric spatial decision support system** structured into three distinct runtime layers:

```text
[ Offline Pipeline Layer ] ──> [ Embedded Storage Layer ] ──> [ Flask Analytical Server ] ──> [ Interactive Browser UI ]
```

1. **Offline Pipeline Layer (`scripts/`):**
   Heavy geographic computing is isolated entirely from runtime web requests. High-volume OSM PBF extracts and government census records are processed ahead of time using C++ bindings (`pyosmium`), projected metric transformations (`pyproj`), and spatial indexing trees (`scipy.spatial.cKDTree`). The output is compiled into a lightweight, portable storage tier.

2. **Embedded Storage Layer (`data/`):**
   Eliminates external database daemon dependencies. An embedded SQLite database (`areas.sqlite`) stores precalculated counts, distances, and polygon geometries for 1,487 grid cells and 66,636 facilities, accelerated by an R-Tree index. Institutional education data and boundary polygons are stored as static JSON files.

3. **Analytical Server Tier (`app.py`, `areas.py`, `data_store.py`):**
   Runs as a stateless, lightweight Python WSGI process. It deserializes cell payloads into memory on the first request and caches them via `functools.lru_cache`. Analytical ranking, multi-criteria weighting, and must-have rule checks execute entirely in memory in sub-10-millisecond time.

4. **Interactive Browser Presentation Layer (`static/`, `templates/`):**
   Renders responsive, hardware-accelerated vector polygon maps using Leaflet.js. Client-side controllers handle slider interactions, asynchronous detail inspection, and tabular comparisons without full-page reloads.

---

## 19. Architecture Component Inventory

| Component ID | Component Name | Responsibility | Runs Where | Inputs | Outputs | Communicates With | Technical Evidence |
|---|---|---|---|---|---|---|---|
| `C-01` | **Flask Web Application** | HTTP request routing, blueprint management, view rendering. | Server Process (Python) | HTTP Requests | HTML / JSON / CSV | `C-02`, `C-03`, `C-06`, `C-07` | `app.py:18-99` |
| `C-02` | **Area Views Controller** | Handles `/`, `/areas`, `/api/areas/<id>`, CSV export. | Server Process (Python) | Query params (`w_*`, `radius`, `must_*`) | HTML, JSON, CSV stream | `C-03`, `C-04`, `C-05`, `C-08` | `area_views.py:28-236` |
| `C-03` | **Analytical Ranking Engine** | Mathematical factor scoring, must-have constraint checks, ranking. | In-Memory (Python) | Cell feature dicts, weights, air monitors | Scored & sorted area candidate list | `C-02`, `scripts/evaluate_areas.py` | `areas.py:58-127` |
| `C-04` | **Data Store & LRU Cache** | SQLite read-only connection, memory caching of 1,487 cells. | In-Memory / SQLite | SQL queries | Cell payloads, manifests, air cache | `data/areas.sqlite`, `C-02`, `C-05` | `data_store.py:13-70` |
| `C-05` | **Secure AQI Ingestion Client** | Fetches paginated air readings from data.gov.in via curl stdin. | Subprocess (curl) | State, City, `DATA_GOV_API_KEY` | Array of pollutant records | `api.data.gov.in`, `C-01`, `C-02` | `air_client.py:16-104` |
| `C-06` | **Observations Parser** | Groups station readings, parses latest PM2.5, assigns color bands. | In-Memory (Python) | Raw API record arrays | Normalized monitor dictionaries | `C-01`, `C-02`, `C-07` | `observations.py:14-65` |
| `C-07` | **Unified Folium Map Engine** | Constructs Leaflet maps combining air monitors and transit stops. | In-Memory (Python) | Monitor lists, transit locations | HTML map string with injected JS | `C-01`, `templates/combined_map.js.j2` | `unified_map.py:12-59` |
| `C-08` | **School Intelligence Subsystem** | Ray-casting point-in-polygon lookup, UDISE+ metrics formatting. | In-Memory (Python) | Lat, Lon, `pincode_profiles.json` | Pincode string, HTML profile card | `C-01`, `school_views.py`, `C-11` | `school_profiles.py:50-164` |
| `C-09` | **Unsupervised Clustering Engine**| Fits K-Means/Hierarchical models, measures silhouette & ARI stability. | In-Memory (scikit-learn) | 16-feature cell matrix | Cluster labels, profiles, metrics | `data_store.py`, `C-02` | `clustering.py:10-122` |
| `C-10` | **Client Leaflet Controller** | Client vector grid rendering, preference sliders, side-by-side compare. | Browser (JavaScript) | `browser_config` JSON, user clicks | DOM updates, detail fetch calls | `C-02`, `C-11`, OpenStreetMap Tiles | `static/areas.js:1-407` |
| `C-11` | **Client School Snippet Loader** | Asynchronously loads school profile cards for map coordinates. | Browser (JavaScript) | Lat, Lon coordinates | Injected HTML school card | `/schools/lookup`, `C-10` | `static/school_profile.js:1-26` |
| `C-12` | **Offline Spatial Grid Builder** | Precalculates 1km UTM grid and 3D cKDTrees, builds `areas.sqlite`. | Offline CLI (Python) | OSM PBF files, boundary GeoJSON | `areas.sqlite`, `area_manifest.json` | Pyosmium, PyProj, Shapely, SciPy | `scripts/build_areas.py:1-192` |

---

## 20. Architecture Connection Inventory

| Source Component | Destination Component | Data / Payload Transferred | Protocol / Mechanism | Direction | Verification Evidence |
|---|---|---|---|---|---|
| User Browser | `app.py` | HTTP GET/POST requests (`/`, `/air-quality`, `/connectivity`) | HTTP 1.1 / TCP (Port 5000) | Bidirectional | Verified (`app.py:21,58`) |
| `area_views.py` | `data_store.py` | Function call requesting cell payloads and air cache rows | Python In-Process Call (`@lru_cache`) | Bidirectional | Verified (`area_views.py:71,83`) |
| `data_store.py` | `data/areas.sqlite` | Read-only SQL queries (`SELECT payload FROM cells`) | SQLite3 C-API (`mode=ro&uri=True`) | Bidirectional | Verified (`data_store.py:15-20`) |
| `area_views.py` | `areas.py` | Cell dictionaries, user weights, radii, caps, monitor arrays | Python In-Process Call | Bidirectional | Verified (`area_views.py:85`) |
| `air_client.py` | `api.data.gov.in` | HTTPS GET requests with API key and pagination filters | HTTPS / TLS 1.3 (via curl subprocess) | Bidirectional | Verified (`air_client.py:30-50`) |
| `air_client.py` | `data_store.py` | `INSERT OR REPLACE INTO air_cache` with query & JSON payload | SQLite3 C-API (timeout 15s) | Outward | Verified (`data_store.py:29-33`) |
| `area_views.py` | `clustering.py` | Requests cluster report or on-the-fly fitting (`clustering()`) | Python In-Process Call (`@lru_cache`) | Bidirectional | Verified (`area_views.py:88-91`) |
| Browser (`areas.js`) | `area_views.py` | AJAX GET `/api/areas/<id>?w_...` | HTTP / Fetch API (JSON response) | Bidirectional | Verified (`static/areas.js:132-139`) |
| Browser (`school_profile.js`) | `school_views.py` | AJAX GET `/schools/lookup?lat=...&lon=...` | HTTP / Fetch API (HTML fragment) | Bidirectional | Verified (`static/school_profile.js:15`) |
| `school_views.py` | `school_profiles.py`| Function call to resolve coordinates (`pincode_at()`) | Python In-Process Call (Ray-Casting) | Bidirectional | Verified (`school_views.py:37`) |
| `school_profiles.py` | `data/schools/` | Deserializes `pincode_profiles.json` & `pincode_boundaries.json`| Local Filesystem Read (UTF-8 JSON) | Inward | Verified (`school_profiles.py:55,101`) |
| Folium Map iframe | Parent Window (`index.js`)| `{type: 'localytics:selection', html: '...', lat, lon}` | HTML5 `window.postMessage` bridge | Inward (iframe to host) | Verified (`static/index.js:3-19`) |
| Client Browser | OpenStreetMap Tiles | Map tile raster image requests (`png`) | HTTPS (`tile.openstreetmap.org`) | Bidirectional | Verified (`static/areas.js:9`) |

---

## 21. Mermaid Architecture Diagram

```mermaid
graph TD
    %% External Entities
    UserClient([End User Web Browser])
    GovAPI[("api.data.gov.in<br/>(National AQI Portal)")]
    OSMServer[("OpenStreetMap<br/>(Tile Server)")]
    OSMFiles[("Raw OSM PBF Files<br/>(delhi.pbf, other1.pbf)")]
    GovCSVs[("UDISE+ 2024-25 CSVs<br/>& India Post KML")]

    %% System Boundary
    subgraph LocalyticsSystem ["System Boundary: Localytics Application"]

        subgraph OfflineBatch ["Offline Preprocessing Pipelines (scripts/)"]
            BuildAreas["build_areas.py<br/>- Pyosmium PBF parser<br/>- EPSG:32643 UTM Grid<br/>- 3D cKDTree Queries"]
            BuildSchools["build_school_profiles.py<br/>- UDISE+ CSV Aggregator<br/>- Percentile Calculator"]
            BuildPincodes["build_pincode_boundaries.py<br/>- KML Polygon Parser<br/>- Hole Retainer"]
            EvaluateAreas["evaluate_areas.py<br/>- 8 Baseline Scenarios<br/>- Clustering Stability"]
        end

        subgraph StorageTier ["Data Storage Tier (data/ & SQLite)"]
            SQLiteFile[("areas.sqlite<br/>- metadata (1 row)<br/>- cells (1,487 rows)<br/>- facilities (66,636 rows)<br/>- facility_index (R-Tree)<br/>- air_cache (queries)")]
            SchoolJSONFiles[("data/schools/<br/>- pincode_profiles.json<br/>- pincode_boundaries.json")]
            ReportFiles[("Evaluation Reports<br/>- cluster_report.json<br/>- evaluation_report.json")]
        end

        subgraph WebCore ["Flask Web Application Core (app.py)"]
            WSGIApp["Flask WSGI Application<br/>(Port 5000)"]
            
            subgraph Controllers ["Controllers & Blueprints"]
                AreaBP["area_views.py<br/>- GET /<br/>- GET /areas<br/>- GET /api/areas/:id<br/>- GET /areas/export.csv<br/>- POST /areas/refresh-air"]
                SchoolBP["school_views.py<br/>- GET /schools<br/>- GET /schools/:pincode<br/>- GET /schools/lookup"]
                TopRoutes["app.py Routes<br/>- GET/POST /air-quality<br/>- GET/POST /connectivity"]
            end

            subgraph ServiceEngines ["Analytical & Service Engines"]
                DataStoreMod["data_store.py<br/>(Read-only SQLite & @lru_cache)"]
                RankingMod["areas.py<br/>(Mathematical Scoring & Must-Haves)"]
                AirClientMod["air_client.py<br/>(curl subprocess via stdin pipe)"]
                ObsMod["observations.py<br/>(PM2.5 Parser & Severity Bands)"]
                SchoolMod["school_profiles.py<br/>(2D Ray-Casting Point-in-Polygon)"]
                ClusterMod["clustering.py<br/>(K-Means & Hierarchical Models)"]
                MapMod["unified_map.py<br/>(Folium Map Generator)"]
            end
        end

        subgraph ClientUI ["Browser Presentation Layer (static/ & templates/)"]
            LeafletAreaUI["static/areas.js<br/>- Vector Grid Rendering<br/>- Dynamic Sliders<br/>- Side-by-Side Compare"]
            FoliumIframeUI["Folium Embedded iframe<br/>(Nationwide AQI & Transit)"]
            SchoolSnippetUI["static/school_profile.js<br/>(Async Profile Card Loader)"]
            SharedHelpers["static/shared.js<br/>(Localytics.escape XSS Guard)"]
        end
    end

    %% Verified Connections (Solid)
    OSMFiles ==>|"Raw PBF Nodes & Ways"| BuildAreas
    GovCSVs ==>|"CSVs & KML Polygons"| BuildSchools
    GovCSVs ==>|"KML Boundaries"| BuildPincodes
    BuildAreas -->|"Generates SQLite & Manifest"| SQLiteFile
    BuildSchools -->|"Writes JSON"| SchoolJSONFiles
    BuildPincodes -->|"Writes JSON"| SchoolJSONFiles
    EvaluateAreas -.->|"Generates JSON"| ReportFiles

    GovAPI -->|"HTTPS JSON Records"| AirClientMod
    AirClientMod -->|"Pipes via stdin to curl"| AirClientMod
    AirClientMod -->|"Normalizes Readings"| ObsMod
    AirClientMod -->|"Caches Records"| DataStoreMod
    DataStoreMod <==|"Read-Only SQL Queries"| SQLiteFile

    UserClient <==|"HTTP GET/POST Requests"| WSGIApp
    WSGIApp --- AreaBP
    WSGIApp --- SchoolBP
    WSGIApp --- TopRoutes

    AreaBP -->|"Fetches Cached Cells"| DataStoreMod
    AreaBP -->|"Executes Scoring & Ranking"| RankingMod
    AreaBP -->|"Retrieves Group Labels"| ClusterMod
    SchoolBP -->|"Resolves Pincode"| SchoolMod
    SchoolMod <==|"Reads JSON Data"| SchoolJSONFiles
    TopRoutes -->|"Generates Folium Map"| MapMod

    AreaBP -->|"Renders HTML + GeoJSON"| LeafletAreaUI
    SchoolBP -->|"Renders HTML Snippet"| SchoolSnippetUI
    TopRoutes -->|"Renders Folium Map"| FoliumIframeUI
    FoliumIframeUI -.->|"postMessage Event Bridge"| IndexUI["static/index.js<br/>(Host Page Sidebar)"]

    LeafletAreaUI ==>|"Fetch Map Tiles"| OSMServer
    FoliumIframeUI ==>|"Fetch Map Tiles"| OSMServer
```

## 22. Beginner-Friendly Glossary

* **Coordinate Reference System (CRS):** A standardized mathematical system used to map 3D points on the curved surface of the Earth onto a 2D flat map. *In Localytics:* The project uses `EPSG:4326` (WGS 84 latitude/longitude degrees) for map display and `EPSG:32643` (UTM Zone 43N meters) for creating its regular 1 km grid.
* **Haversine Formula:** A mathematical formula calculating the great-circle distance between two points on a sphere given their latitudes and longitudes. *In Localytics:* Implemented in `geography.distance_km()` to calculate straight-line distances between grid cells and urban facilities.
* **Point-in-Polygon (Ray-Casting):** An algorithm that determines whether a coordinate point lies inside a geometric polygon by casting an imaginary ray from the point and counting how many polygon boundaries it crosses. *In Localytics:* Implemented in `school_profiles.in_ring()` to look up which postal pincode contains a clicked map point.
* **R-Tree Index:** A tree data structure specifically designed for spatial indexing. It groups geometric objects into hierarchical bounding boxes. *In Localytics:* Implemented as an SQLite virtual table `facility_index` in `areas.sqlite` to quickly find amenities.
* **cKDTree:** A data structure for fast nearest-neighbor spatial queries in multi-dimensional space. *In Localytics:* `scipy.spatial.cKDTree` is converted to 3D spherical coordinates in `scripts/build_areas.py` to index 66k amenities in seconds.
* **PBF (Protocolbuffer Binary Format):** A highly compressed binary format for raw OpenStreetMap data. *In Localytics:* `delhi.pbf` and `other1.pbf` are parsed by Pyosmium during offline grid builds.
* **PM2.5:** Microscopic airborne particles smaller than 2.5 micrometers that penetrate deep into the lungs. *In Localytics:* Extracted from the `data.gov.in` real-time API and scored on a $1 - \min(\text{PM}_{2.5} / 250, 1)$ scale.
* **UDISE+:** Unified District Information System for Education Plus—India's national school census conducted by the Ministry of Education. *In Localytics:* Provides institutional statistics (management mix, pupil-teacher ratios, teacher degrees) across 93 Delhi postal pincodes.
* **Pupil-Teacher Ratio (PTR):** Total enrolled students divided by total appointed teachers in a school. *In Localytics:* Statistical distributions (10th, 50th, 90th percentiles) are presented on school cards; ratios over 100 are filtered out as errors.
* **Zero-Imputation Principle:** An architectural rule dictating that if empirical data is missing for a factor or constraint, the system refuses to guess, estimate, or average it. *In Localytics:* Missing data causes the cell to be marked "Unranked" rather than silently redistributing weights.
* **Silhouette Score:** A metric between -1 and +1 evaluating how well data points fit into their assigned clusters compared to neighboring clusters. *In Localytics:* Evaluated in `clustering.py` ($S = 0.357$ for K-Means $k=2$).
* **Adjusted Rand Index (ARI):** A measure of clustering agreement between two labelings, adjusted for chance. *In Localytics:* Used to measure stability across 5-fold bootstrap subsamples ($	ext{ARI} = 0.978$).
* **Folium & Leaflet:** Leaflet is a client-side JavaScript map library; Folium is a Python wrapper that generates Leaflet HTML. *In Localytics:* Folium generates the nationwide air map; Leaflet.js renders the 1 km Delhi grid on the homepage.
* **Formula Injection (CSV Injection):** An attack where malicious spreadsheet formulas (`=cmd|'...'`) execute when an exported CSV is opened. *In Localytics:* Mitigated in `area_views.py:205-206` by prepending a single quote (`'`) to any locality name beginning with dangerous characters.

---

## 23. Recommended Code Reading Order

For a beginner or architect seeking to understand this repository systematically, read the files in this precise sequence:

```text
Step 1: The Blueprint & Constants
└── Read config.py
    └── Why: Establishes all shared factor names, scoring defaults, radii, caps, file paths, and color palettes.

Step 2: The Core Scoring Logic
└── Read areas.py
    └── Why: Pure functional mathematical logic. Understand how service_score(), nearest_air(), and evaluate() calculate suitability without any web or database dependencies.

Step 3: Data Access & Caching
└── Read data_store.py
    └── Why: See how SQLite areas.sqlite is opened in read-only URI mode and how cells are cached in memory via @lru_cache.

Step 4: Web Application Bootstrap & Routing
├── Read app.py
│   └── Why: Understand WSGI initialization, environment loading, and route mounting.
└── Read area_views.py
    └── Why: Understand how HTTP query parameters (w_*, radius, cap) are parsed, validated, and passed to areas.rank().

Step 5: External API & Ingestion
├── Read air_client.py
│   └── Why: See how curl subprocesses with stdin configurations securely consume data.gov.in.
└── Read observations.py
    └── Why: Understand station grouping and PM2.5 severity color mapping.

Step 6: Specialized Subsystems
├── Read school_profiles.py & school_views.py
│   └── Why: Master the 2D ray-casting point-in-polygon algorithm and UDISE+ statistical views.
├── Read clustering.py
│   └── Why: Examine the scikit-learn K-Means and Hierarchical clustering pipeline and bootstrap stability checks.
└── Read scripts/build_areas.py
    └── Why: Understand the offline ETL pipeline that projects Delhi to EPSG:32643 and builds the SQLite database using 3D cKDTrees.
```

---

## 24. Important Facts to Remember

1. **Prebuilt Database:** The application works completely offline out-of-the-box. Recommendations do not require live API calls or PBF parsing at startup.
2. **Fixed Metric Grid:** Delhi is divided into 1,487 cells of exactly $1000\times 1000\text{ meters}$ in `EPSG:32643` (UTM Zone 43N).
3. **No Quality Score for Schools:** School profiles describe institutional resources and staffing; there is deliberately no single "quality score" because pincode explains little within-neighborhood variance.
4. **Strict Zero-Imputation:** If a user assigns positive weight to a factor and a cell lacks evidence, that cell is omitted from the ranked shortlist. Weights are never silently reallocated.
5. **Air Pollution Direction:** Lower PM2.5 is better. The factor score is $1 - \min(\text{PM}_{2.5} / 250, 1)$.
6. **Air Quality Eligibility Gate:** An air reading is only eligible for ranking if the monitor is within 5 km and the observation is $\le 6\text{ hours}$ old.
7. **Read-Only Runtime SQLite:** Web requests open `areas.sqlite` in read-only URI mode (`mode=ro`). The only runtime writes occur to the `air_cache` table.
8. **In-Memory Speed:** The 1,487 cells are cached in memory via `@lru_cache(maxsize=1)`. Ranking executes entirely in memory in under 10 milliseconds.
9. **OSM Deduplication:** Facilities extracted from overlapping PBF extracts are deduplicated by OSM Type and ID, retaining the highest version and timestamp. Same-name facilities within 100 meters are consolidated.
10. **Pure-Python Ray Casting:** Point-in-polygon containment for 92 pincodes is executed via pure-Python ray casting without heavyweight GIS libraries at runtime.
11. **Isolated Machine Learning:** K-Means clustering ($k=2$, silhouette $= 0.357$, ARI $= 0.978$) provides descriptive map coloring only. Model outputs never alter ranking scores.
12. **Subprocess Security:** API keys are never exposed in process lists; `air_client.py` pipes the query configuration to `curl` via `stdin`.
13. **CSV Injection Defense:** Spreadsheet formula injection attacks are prevented in `/areas/export.csv` by prepending `'` to risky locality labels.
14. **Straight-Line Distances:** All distances are Euclidean or Haversine straight-line measurements; road network travel times or traffic congestion are not modeled.
15. **Boundary Provenance:** The Delhi boundary is a community spatial reference from DataMeet (1,488.1 km²), not a legally certified boundary.

---

## 25. Likely Questions and Answers

### Q1: Why does Localytics use a 1 km square grid instead of official municipal ward or pincode boundaries?
**Answer:** Wards and pincodes vary drastically in size, population density, and geometry. A ward in central Delhi might be tiny and dense, while an outer rural ward might span dozens of square kilometers. Evaluating amenities by irregular administrative boundary would severely distort proximity metrics. A uniform 1 km grid in projected metric coordinates (`EPSG:32643`) provides consistent, objective spatial units of comparison across the entire metropolitan area (`scripts/build_areas.py:80-94`).

### Q2: Why does the application mark a neighborhood as "Unranked" instead of estimating missing data?
**Answer:** Localytics adheres to a strict **Zero-Imputation Principle**. Estimating missing data (e.g., assuming an average air quality value or guessing school proximity) produces false confidence and can mislead home seekers into moving to an underserved or heavily polluted area. If an area lacks verified empirical evidence for a factor the user explicitly requested, the system transparently marks the cell unranked (`areas.py:88-100`).

### Q3: Why doesn't the ranking engine provide a single composite "School Quality Score"?
**Answer:** UDISE+ open data captures institutional infrastructure (pupil-teacher ratios, teacher degrees, smart classrooms) but does not contain learning outcome metrics or standardized test scores. Furthermore, schools within the same pincode exhibit enormous variance. Condensing disparate schools into a single neighborhood score would be statistically unsound and misleading (`scripts/build_school_profiles.py:194`, `README.md:53-56`).

### Q4: How does the application prevent API key exposure when calling the government air quality API?
**Answer:** Rather than executing `curl` with the API key in the command-line arguments (where it would be visible in Windows Task Manager or `ps` to other system users), `air_client.py:28-48` builds a configuration string and passes it to `curl --config -` over the standard input (`stdin`) pipe.

### Q5: What is the purpose of the K-Means clustering module if it doesn't affect area ranking?
**Answer:** Unsupervised clustering serves a descriptive, exploratory purpose. By clustering the 16 normalized spatial features across all cells, the system discovers macro-level neighborhood archetypes (such as dense commercial/transit hubs vs. quiet residential sectors vs. peripheral rural tracts). Users can toggle the "Similar area groups" map layer to explore structural urban patterns without biasing their personalized preference ranking (`clustering.py:10-122`).

### Q6: Can Localytics be used for cities other than Delhi?
**Answer:** The nationwide air quality explorer (`/air-quality`) already works for any state and city across India. However, the personalized area recommendation engine (`/areas`) is currently bundled only for Delhi. To expand recommendations to another city, a developer must provide the target city's boundary polygon, choose an appropriate projected metric CRS (e.g., UTM Zone 43N for Mumbai/Delhi, UTM Zone 44N for Bengaluru/Hyderabad), and run `scripts/build_areas.py` with validated OSM PBF extracts (`README.md:68`).

---

## 26. Known Unknowns and Investigation Limitations

* **Offline Usability Trials:** The documentation references a planned 12-person usability study (`README.md:77`, `scripts/evaluate_areas.py:53`). No empirical subject trial data or user interview transcripts exist in the repository.
* **OSM Relation Geometries:** The OSM ingestion pipeline in `osm_data.py:77` processes nodes and ways only. Multipolygon relations (e.g., massive university campuses or complex administrative enclosures mapped solely as relations) may have incomplete spatial footprints.
* **Transit Passenger Service Verification:** Mapped airport terminals and EV charging points reflect OpenStreetMap tags. The repository cannot verify whether an airport terminal has active commercial passenger flights or whether an EV charging station is operational and publicly accessible.
* **Historical Air Trends:** `air_cache` stores real-time snapshots of air quality queries. The application does not maintain longitudinal time-series models or seasonal weather forecasting.

---

## 27. Evidence Index and Important Source References

Every major architectural, mathematical, and functional claim in this report is anchored directly in the repository source code:

1. **Delhi 1 km Projected Grid & Boundary Plausibility:**
   - Source: `scripts/build_areas.py:27-36, 80-94`.
   - Verified: EPSG:4326 to EPSG:32643 metric projection, $1300 < \text{area} < 1700\text{ km}^2$ sanity check, 1,487 grid cells.
2. **OSM Classification & Version-Aware Deduplication:**
   - Source: `osm_data.py:37-58, 116-140`.
   - Verified: 10 facility categories; duplicate objects resolved by `(kind, obj.id)` with highest `(version, timestamp)` winning; same-name consolidation within 100 m via `geography.py:34-54`.
3. **Service Factor Scoring Formulation:**
   - Source: `areas.py:58-64`.
   - Verified: Balanced $0.5 \times \text{Proximity} + 0.5 \times \text{Density}$ formula.
4. **PM2.5 Air Indicator Normalization & Eligibility:**
   - Source: `areas.py:18-56`, `config.py:49-51`.
   - Verified: Cap at 250 µg/m³, monitor radius $\le 5\text{ km}$, monitor age $\le 6\text{ hours}$, reject future/negative readings.
5. **Zero-Imputation Ranking Rule:**
   - Source: `areas.py:88-100`.
   - Verified: Unranked cell assignment if any factor with $w > 0$ has `score is None` or must-have check fails.
6. **Subprocess Credential Shielding:**
   - Source: `air_client.py:28-50`.
   - Verified: `curl --config -` reading JSON configuration over `stdin`.
7. **CSV Spreadsheet Formula Sanitization:**
   - Source: `area_views.py:205-207`.
   - Verified: Single quote prepended to labels starting with `=`, `+`, `-`, `@`.
8. **Pure-Python 2D Ray-Casting Algorithm:**
   - Source: `school_profiles.py:61-75`.
   - Verified: Ray-crossing parity check handling outer rings and inner polygon holes.
9. **Unsupervised K-Means Silhouette & ARI Stability:**
   - Source: `clustering.py:58-92`, `data/cluster_report.json`.
   - Verified: K-Means $k=2$, Silhouette $= 0.357$, 5-fold bootstrap resampling stability $\text{ARI} = 0.978$.
10. **Database Schema & R-Tree Spatial Index:**
    - Source: `scripts/build_areas.py:155-181`, `data_store.py:13-64`.
    - Verified: Tables `metadata`, `cells`, `facilities`, `facility_index` (R-Tree), `air_cache`.