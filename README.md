## Expanded OSM coverage

Transport data merges delhi.pbf and other1.pbf. Overlapping objects are deduplicated by (OSM type, OSM ID). Where versions differ, the highest object version/timestamp is retained; the later file wins ties. The source_files column records which extracts contained each selected object. Existing map-level consolidation of same-name, same-category features within 100m remains separate from exact overlap removal. Different IDs can legitimately represent different platforms or entrances; these are not blindly removed.

To rebuild both extracts together:

```sh
pip install osmium
python connectivity/extract_transport.py /path/to/delhi.pbf /path/to/other1.pbf
```

Rebuild from all source files together to preserve the union. Counts and removed overlaps are recorded in connectivity/metadata.json. This is a union of extracted nodes/ways, not a full history reconciliation: relation-only facilities and deleted or reclassified objects from older snapshots may require additional review.

## Sidebar update

Map clicks now update the Selected area sidebar instead of opening a large map popup. It shows connectivity scores/counts, nearby facilities and the nearest loaded air monitor with all pollutant readings. Changing radius updates the selected area's details automatically. The sidebar stacks below the map on smaller screens. The map legend is collapsible. Run the app as before.

# Unified map update

The home page combines air-quality dots, connectivity rings and optional transport layers. Click any location or monitor for both sets of data. Load air readings using the existing state/city form. Transport works before fetching air data.

Connectivity score = 50 × types/3 + 50 × min(count/20, 1). Types: bus stops, metro stations, airport terminals. Scores ≥70 high/green, 40–69 medium/amber, below 40 low/red; no mapped matches is grey. This is a project heuristic based on mapped proximity and diversity, not official accessibility or service frequency. Counts include every matching facility, not just the five displayed per category. All types use the selected radius; change radius in the map legend. Airports may only contribute at larger radii. Same-category same-name objects within 100m are consolidated: opposite-direction stops may merge, while unnamed duplicates remain. Ring colours refresh when radius changes; click again for updated details.

Air data at a clicked location is from the nearest loaded monitor, with distance and timestamps shown; no neighbourhood AQI is inferred. PM2.5 colours assume 24-hour concentrations and remain indicative. The original standalone transport page is retained as a legacy view.

# Localytics

Air-quality mapping plus local Delhi transport search, integrated from your original Localytics archive.

## Run

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000/connectivity for nearby transport. No API key or Overpass call is needed. Enter latitude, longitude, radius and result count. Bus stops are blue, metro stations purple and airport terminals orange. Every category uses the same radius; increase it to find more distant terminals.

Air quality remains at http://127.0.0.1:5000. Copy your existing `.env` into this folder to retain the data.gov.in key, or copy `.env.example` to `.env` and fill it in. Transport search works without this key. The archive intentionally contains no credentials.

## Data

The connectivity folder contains locations extracted from your delhi.pbf, source OSM tags, metadata and the reusable nearest-feature search. No need to reinstall osmium or parse the PBF to run the app. To refresh from another PBF, install `osmium`, then run `python connectivity/extract_transport.py /path/to/delhi.pbf`.

Distances are straight-line, not walking/driving times. Nodes and ways are extracted; relation-only features are omitted. Different OSM objects can represent the same physical station. Airport-terminal passenger service is unverified, and polygon bounding-box centres are approximate, not entrances. Coverage depends on the supplied extract. Missing matches do not prove absent transport. OpenStreetMap background tiles and map scripts require internet even though search is local.

Original air-quality colours remain indicative PM2.5 bands, not validated overall AQI.

Data attribution: © OpenStreetMap contributors, ODbL https://www.openstreetmap.org/copyright

## Tests

Install pytest, then run `python -m pytest -q`. API tests use simulated responses; transport tests use the bundled extracted data.
