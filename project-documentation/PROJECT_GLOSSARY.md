# Localytics: Project Glossary & Technical Terminology

This glossary introduces and explains the essential technical terms used throughout the **Localytics** repository in plain English, supplemented by repository-specific examples and references.

---

### 1. GIS and Geospatial Concepts

#### Coordinate Reference System (CRS)
* **Simple Explanation:** A standardized mathematical system used to map 3D points on the curved surface of the Earth onto a 2D flat map.
* **In Localytics:** The repository uses two coordinate systems:
  - `EPSG:4326` (WGS 84): Standard global latitude and longitude measured in degrees (e.g., latitude `28.6139`, longitude `77.2090`).
  - `EPSG:32643` (UTM Zone 43N): A projected coordinate system measured in meters, used in `scripts/build_areas.py` to create a geometrically accurate 1,000-meter (1 km) square grid across Delhi.

#### EPSG Code
* **Simple Explanation:** A numeric identifier established by the European Petroleum Survey Group to catalog specific map projections and coordinate reference systems.
* **In Localytics:** `pyproj.Transformer.from_crs(4326, 32643)` is used to project latitude/longitude coordinates into metric Cartesian coordinates for uniform grid tiling.

#### Haversine Formula
* **Simple Explanation:** A mathematical equation used to calculate the great-circle distance between two points on the surface of a sphere given their longitudes and latitudes.
* **In Localytics:** Implemented in `geography.distance_km()` using Earth radius $R = 6371.0088\text{ km}$ to compute accurate straight-line distances between grid cell centers and urban facilities.

#### Point-in-Polygon (Ray-Casting Algorithm)
* **Simple Explanation:** A geometric test to determine whether a given point lies inside or outside a closed polygon boundary. A theoretical ray is cast from the point to infinity; if it intersects polygon edges an odd number of times, the point is inside.
* **In Localytics:** Implemented in `school_profiles.in_ring()` and `in_polygon()`. Used by the `/schools/lookup` route to resolve the postal pincode of any map click without external spatial database extensions.

#### R-Tree Index
* **Simple Explanation:** A tree data structure optimized for indexing multi-dimensional spatial information. It groups geometric objects into hierarchical bounding rectangles, enabling fast spatial range queries.
* **In Localytics:** Stored as an SQLite virtual table `facility_index USING rtree(id, min_lon, max_lon, min_lat, max_lat)` inside `data/areas.sqlite`.

#### cKDTree (k-d Tree)
* **Simple Explanation:** A binary space-partitioning tree used for fast nearest-neighbor searches in multi-dimensional space.
* **In Localytics:** `scipy.spatial.cKDTree` is converted to 3D Cartesian coordinates on the unit sphere in `scripts/build_areas.py` to compute nearest facilities and radius counts across 66,000+ points in seconds.

#### PBF (Protocolbuffer Binary Format)
* **Simple Explanation:** A highly compressed binary file format used to distribute raw OpenStreetMap geographic datasets efficiently.
* **In Localytics:** Raw data files (`delhi.pbf`, `other1.pbf`) are read using `osmium.FileProcessor` to extract amenities, transit hubs, and municipal boundaries.

---

### 2. Environmental & Air Quality Terms

#### PM2.5 (Particulate Matter 2.5)
* **Simple Explanation:** Microscopic airborne particles with an aerodynamic diameter smaller than 2.5 micrometers (about 3% the diameter of a human hair). It penetrates deep into the lungs and bloodstream and is the primary indicator of urban air pollution in northern India.
* **In Localytics:** Extracted from the `data.gov.in` real-time API in `observations.latest_pm25()`.

#### PM2.5 Indicator Score
* **Simple Explanation:** A normalized mathematical metric between 0.0 and 1.0 (rendered as 0 to 100) indicating relative air cleanliness. Unlike official AQI tables, this project uses an explicit transparent cap.
* **In Localytics:** Calculated in `areas.py` as:
  $$\text{Score} = 1 - \min\left(\frac{\text{PM}_{2.5}}{250}, 1\right)$$
  Values at or above $250\,\mu\text{g}/\text{m}^3$ receive a score of 0.

#### Monitor Eligibility Window
* **Simple Explanation:** The geographic and temporal cutoff criteria applied before an air quality reading is permitted to influence an area's ranking.
* **In Localytics:** In `areas.nearest_air()`, an air monitor must be within 5 km of the cell center and no older than 6 hours (`MONITOR_MAX_AGE_HOURS = 6`). If no valid monitor meets this criterion, the air score is `None`, and the cell is marked unranked if the air factor weight is positive.

---

### 3. Education & Institutional Data Terms

#### UDISE+ (Unified District Information System for Education Plus)
* **Simple Explanation:** An official nationwide school census conducted annually by the Ministry of Education, Government of India, capturing detailed data on school infrastructure, staffing, and enrollments across India.
* **In Localytics:** The dataset `UDISE+ Delhi 2024-25` (republished on OpenCity) provides institutional profiles across 93 Delhi postal pincodes.

#### Pupil-Teacher Ratio (PTR)
* **Simple Explanation:** The number of enrolled students divided by the number of working teachers in a school. Lower ratios generally indicate smaller class sizes and more individualized attention.
* **In Localytics:** Calculated in `scripts/build_school_profiles.py`. Ratios exceeding 100 are filtered out as source data entry errors.

#### 10th-90th Percentile Range ($P_{10}$–$P_{90}$)
* **Simple Explanation:** A statistical measure representing the spread of values while ignoring extreme outliers. The 10th percentile is the value below which 10% of schools fall; the 90th percentile is the value below which 90% fall.
* **In Localytics:** Rendered on school profile cards to show real variation among neighborhood schools without condensing them into a single misleading average.

---

### 4. Machine Learning & Statistical Terms

#### K-Means Clustering
* **Simple Explanation:** An unsupervised machine learning algorithm that groups similar data points into $k$ distinct clusters by minimizing the distance between points and their cluster centers (centroids).
* **In Localytics:** Implemented in `clustering.py` to categorize Delhi's 1,487 grid cells into urban facility archetypes (e.g., dense transit-rich hubs vs. developing peripheral cells).

#### Agglomerative Hierarchical Clustering
* **Simple Explanation:** A "bottom-up" clustering method where each data point starts in its own cluster, and pairs of clusters are iteratively merged based on geometric proximity.
* **In Localytics:** Evaluated alongside K-Means for $k \in [2, 6]$ in `clustering.py` to compare clustering quality.

#### Silhouette Score
* **Simple Explanation:** A validation metric between -1 and +1 measuring how similar a data point is to its own cluster compared to neighboring clusters. Higher values indicate well-separated, coherent groupings.
* **In Localytics:** Evaluated in `clustering.py`. The model configuration achieving the highest silhouette coefficient (K-Means with $k=2$, score $= 0.357$) is persisted into `data/cluster_report.json`.

#### Adjusted Rand Index (ARI)
* **Simple Explanation:** A statistical metric between -1 and +1 measuring the agreement or stability between two different cluster label assignments, adjusted for chance.
* **In Localytics:** Used in `clustering.py` to conduct 5-fold bootstrap resampling stability checks on 80% subsamples. A stability score of $0.978$ proves that the identified area clusters are robust and not artifacts of random sampling.

---

### 5. Architecture & Software Engineering Terms

#### Zero-Imputation Principle (Strict Evidence Rule)
* **Simple Explanation:** The rule that if a data point is missing, the system refuses to guess, estimate, or average it. Instead, it leaves the value absent and openly reports the omission.
* **In Localytics:** Governs area suitability scoring. If a user assigns importance to a factor (e.g., air quality or EV charging) and a cell lacks verified evidence, the cell is omitted from the ranked shortlist. Weights are never silently reallocated.

#### Blueprints (Flask)
* **Simple Explanation:** A way to organize related routes and views into modular components in a Flask web application.
* **In Localytics:** Used in `area_views.py` (`areas` blueprint) and `school_views.py` (`schools` blueprint) to isolate route handling from the main `app.py`.

#### Leaflet & Folium
* **Simple Explanation:** Leaflet is an open-source JavaScript library for interactive web maps. Folium is a Python library that wraps Leaflet, enabling Python backends to generate Leaflet maps as HTML.
* **In Localytics:** Folium is used in `unified_map.py` and `transport.py`, while raw client-side Leaflet.js is used in `static/areas.js` for dynamic vector grid manipulation.

#### Formula Injection (CSV Injection)
* **Simple Explanation:** A security vulnerability where spreadsheets (Excel, Google Sheets) execute malicious formulas (e.g., `=cmd|' /C calc'!A0`) embedded in CSV cells that start with `=`, `+`, `-`, or `@`.
* **In Localytics:** Mitigated in `area_views.py` (`export()`) by prepending a single quote (`'`) to any locality label that starts with dangerous formula characters before writing the CSV.