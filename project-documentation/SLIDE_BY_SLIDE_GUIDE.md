# Localytics: slide-by-slide guide

Written for the presenters of Group 7 (BITS MPBA G507). For every slide of the 16-slide deck it says **what the slide claims**, **what is actually happening in the project behind it**, **where each number comes from**, **how to explain it simply**, and **what could go wrong**. Read section 0 first; it is the whole project on two pages.

Deck: https://claude.ai/artifact/SH6tj81G6tCRU9pfsbyWLs (private link; share it from the page's Share menu).

---

## 0. The project in two pages

### What it is
**Localytics** helps a household decide which parts of **Delhi and Gurugram** to look at before looking at individual flats. It combines open data about buildings, rents, air quality, schools and nearby services, and lets you ask in plain language.

### The three pieces (and where they live)

| Piece | What it is | Folder | How you open it |
|---|---|---|---|
| **Localytics website and app** | The original project. A Flask website and a Flet desktop/browser app. Cuts Delhi into 1,487 one-kilometre cells (and, in the property map, Gurugram into 1,257 more) and scores each cell for your priorities (metro, schools, hospitals, parks, air quality...). Also has the air-quality search page and the school profiles by pincode. | `Localytics/` | Website: http://127.0.0.1:5000/ . Flet app: http://127.0.0.1:8550/ |
| **Flat Finder map** | A 3D property map (an open-source project by "kairothq") that Sanjyot connected to Localytics. We extended it with Delhi buildings, a combined "Delhi NCR" view, a PM2.5 colour mode and the Ask panel. | `flat-finder-localytics/` | http://127.0.0.1:5173/ |
| **Ask Localytics** | The chat panel inside the Flat Finder map. Gemini asks the clarifying questions, a Python search engine does the real searching. | `flat-finder-localytics/integration/advisor*.py`, `web/src/advisor.js` | The **Ask** button on the map |

A small "data service" (`flat-finder-localytics/integration/localytics_api.py`, port 8766) sits behind the map: it serves the neighbourhood-score data and the chat endpoints.

### How data flows

```
Open sources                         Python builders                      What you see
-------------                        ---------------                      ------------
OpenStreetMap (Delhi extract) ─┐
OpenML Delhi rents (Aug 2020)  ├──▶ build_delhi_open.py ─▶ delhi.json ─┐
OpenAQ air quality (PM2.5)     ┘       (clean, match, dedupe)          ├─▶ build_ncr.py ─▶ ncr.json (4,650 buildings)
Magicbricks via Flat Finder ─────────▶ gurgaon.json ──────────────────┘          │
UDISE+ schools, India Post pincodes ─▶ build_school_profiles.py ─▶ data/schools/ │
OSM facilities ─▶ build_areas.py ─▶ areas.sqlite (1,487 + 1,257 cells, 66,636 facilities)│
                                                                                  ▼
                       Flat Finder map  ◀── ncr.json + shapes      Localytics website (area scores, schools, air)
                       Ask panel ─▶ data service ─▶ Gemini (language) + advisor.py (search over ncr.json)
```

### Who did what (from the git history and our work)
- **Sanjyot** wrote most of the original Localytics repository (11 commits) and the Flat Finder integration (the neighbourhood panel and the data bridge).
- **Jakki** (2 commits so far) added the school profiles by pincode, and, in this series of work, the Delhi building data, the combined NCR map, the PM2.5 mode and the Ask assistant.
- The other three presenters: write your own contribution here: ______.

### Key ideas to remember
1. **Every number traces to a source, and every gap is labelled.** Delhi rents say "August 2020"; a missing air reading says "no reading", never "clean".
2. **The AI only does language.** Gemini understands your message and writes the reply. A Python engine (`advisor.py`) produces every number.
3. **Two cities are ranked separately.** Delhi's 2020 rents would otherwise always win.

### Glossary
- **PM2.5**: fine particles in the air, in µg/m³. Our "indicative" air value. Not an official AQI.
- **AQI**: Air Quality Index, an official 0 to 500 scale. We do not compute it; we show PM2.5 bands (Good, Satisfactory, Moderate, Poor, Very poor, Severe).
- **BHK**: bedrooms, hall, kitchen. "3 BHK" = three bedrooms.
- **OSM**: OpenStreetMap, the open map of the world. **ODbL** is its licence.
- **UDISE+**: the Ministry of Education's school database.
- **Silhouette / adjusted Rand index**: two scores for clustering. Silhouette measures how well separated the groups are (1 is perfect); adjusted Rand index measures how stable the groups are when you re-run on a subsample (1 is identical).
- **Hedonic pricing**: an economics method that values a neighbourhood quality (like clean air) from house prices.

### Current status (read this before presenting)
- The deck, the app and the assistant all work.
- **Air quality is now comparable between the two cities.** The data.gov.in key in `.env` was rejected by the server (HTTP 403), so both cities' PM2.5 now come from OpenAQ, which republishes the same government monitors (CPCB, DPCC, HSPCB, IMD). One fetch on **24 Nov 2026** (`Localytics/scripts/refresh_air_openaq.py`), each monitor stored as its **24-hour average**, low-cost sensors left out. Result: **1,276 of 2,089 Delhi buildings** (17 monitors) and **1,507 of 2,561 Gurugram buildings** (5 Gurugram monitors, plus 2 Delhi border monitors, Aya Nagar and Sirifort, that serve 183 of them) have a reading. The old 10 Nov data.gov.in Delhi snapshot is still in the cache but the builder ignores any reading more than 48 hours older than the newest. Limits to say out loud: Gurugram rests on only five monitors, and one of them (Sector-51) serves 849 of the 1,507 covered buildings; monitors that publish only a latest value, no hourly history, are left out.

---

## Slide 1: Cover

**Says:** Title, the one-line pitch and five boxes: who presents which slides.

**What is happening in the project:** The picture is the real Flat Finder map in its light theme, zoomed out over Delhi NCR: every orange mark is one of the **4,650 buildings** in `ncr.json` (2,561 Gurugram societies plus 2,089 Delhi buildings and colonies).

**Numbers:** 4,650 = 2,561 + 2,089 (`counts` in `web/public/data/ncr.json`).

**Presenter note:** Fill in the `[name]` placeholders. The slide ranges (2-4, 5-7, 8-10, 11-13, 14-16) are the agenda.

---

## Slide 2: Problem statement (Presenter 1)

**Says:** Choosing where to live in Delhi NCR means stitching together sources never built to meet. The business question: *which parts of Delhi and Gurugram fit a household's budget, commute and air-quality needs, and can we show the evidence behind every number?* Four pain points.

**What is happening:** Nothing computed here; this is the framing. The four pain points come from our own review of how a household searches: portals list flats, not neighbourhoods; air quality sits on government dashboards; metro, schools and hospitals are on separate maps; Delhi and Gurugram data differ in date, format and coverage.

**Explain simply:** "The data exists but in five places. We put it together and show where each number came from."

**Careful:** The pain points are observations, not survey results. If asked for evidence: open any listing portal and look for PM2.5 next to the price.

---

## Slide 3: Clients and research questions (Presenter 1)

**Says:** Three kinds of client (a relocating household, relocation/HR teams, property advisors) and four research questions.

**What is happening:** The four questions are what the rest of the deck answers:
- **Q1** Which areas score best for a given mix of priorities? → slide 9 (area model) and slide 13 (worked examples).
- **Q2** How do Delhi and Gurugram compare on rent, air, transit? → slide 11 (rents), slide 12 (air).
- **Q3** How stable is a ranking when priorities change? → slide 9 (sensitivity test).
- **Q4** Can an assistant turn a vague need into an evidence-backed shortlist? → slides 10 and 13.

**Careful:** The clients are personas, not signed-up customers. No user study exists yet (slide 15 says so).

---

## Slide 4: Similar research and the gap (Presenter 1)

**Says:** A table of what exists (property portals, air dashboards, Walk Score, academic work) and what each leaves open; four boxes for the gap we fill.

**What is happening:** The four gap boxes map to real parts of the project:
1. **One map, two cities**: `ncr.json`, built by `build_ncr.py` from the Gurugram data (Flat Finder) and the Delhi data we built.
2. **Air on every building**: the PM2.5 lookup in `build_delhi_open.py` (`air_for`, nearest monitor within 5 km) and the PM2.5 colour mode (`airlayer.js`).
3. **Transparent scoring**: `areas.py` in the Localytics repo, ten factors with user weights.
4. **No invented numbers**: the assistant design (`advisor.py` produces the numbers, Gemini only talks).

**Careful (important):** The citations (Rosen 1974; Chay and Greenstone 2005; Moreno et al. 2021) and the claims about what portals show were written from memory. **Check them yourselves before presenting.** Say "as far as we found" for the portal claims.

---

## Slide 5: Data sources and data information (Presenter 2)

**Says:** Five sources and five headline numbers.

**What is happening, source by source:**
- **Magicbricks via Flat Finder** (Gurugram): Flat Finder crawls Magicbricks listings and builds the Gurugram dataset (`gurgaon.json`): 2,561 societies, 22,018 for sale and 7,371 for rent listings (29,389 in all). Sanjyot's connector links this to Localytics.
- **OpenStreetMap + DataMeet** (Delhi): `NewDelhi.osm.pbf` (BBBike's extract of OpenStreetMap) gives building outlines, colonies and place names; `delhi_boundary.geojson` (DataMeet) clips everything to Delhi. The 66,636 mapped facilities (bus stops, metro, schools, hospitals, parks, malls...) are in `areas.sqlite`, table `facilities`.
- **OpenML 43837** (Delhi rents): a public rental-listings file from **11 August 2020**, 17,890 rows, of which 16,842 are usable after cleaning. Declared CC0 by its uploader.
- **OpenAQ air quality**: readings of the government monitors (CPCB network, DPCC, HSPCB, IMD) republished by OpenAQ. Both cities were fetched together on **24 Nov 2026**, each monitor as its **24-hour average** (a single evening hour can read three times the day's level: Sector-51 was 75 to 140 all day and 300 to 400 after 7 pm), and cached in `areas.sqlite`, table `air_cache`. The earlier source was the data.gov.in feed (a 10 Nov snapshot, Delhi only).
- **UDISE+ and India Post pincodes**: Ministry of Education school data for Delhi (2024-25), republished by OpenCity, plus pincode boundaries. 5,556 schools in 93 pincodes.

**The five number boxes:** 4,650 buildings · 467 localities (236 Delhi + 231 Gurugram) · 2,744 one-km cells (1,487 Delhi + 1,257 Gurugram) · 66,636 facilities · 2,783 buildings with a PM2.5 reading (1,276 Delhi + 1,507 Gurugram).

**Careful:** The Magicbricks data is collected by Flat Finder's crawler, not by us; say "via the Flat Finder connector". The OpenML set's original source is a real-estate website (see slide 6).

---

## Slide 6: Data quality (Presenter 2)

**Says:** Five dimensions: what we found and what we did.

**What is happening, row by row:**
- **Freshness:** Delhi rents are from August 2020; air is one 24-hour average from 24 Nov 2026. *Action:* every Delhi card prints the date ("August 2020"); `build_ncr.py` keeps the two cities' prices in separate fields, and the assistant ranks them separately.
- **Coverage:** PM2.5 known for 1,276 of 2,089 Delhi buildings (17 monitors) and 1,507 of 2,561 Gurugram buildings (5 Gurugram monitors plus 2 Delhi border ones); the rest have no monitor within 5 km. Both come from the same fetch, so they can be compared. *Action:* a missing reading is stored as "no reading" and shown as unknown, never as clean.
- **Completeness:** 550 Delhi entries have no price (no rent data within 1.0 to 1.5 km), 1,048 of 17,890 rent rows dropped as unusable (implausible rents, typos). *Action:* in a budget search an unpriced entry is "not checked yet", never a match (the `strictPrice` rule in `filters.js` and `advisor.py`).
- **Accuracy:** Flat Finder flags likely-typo listing prices; our filters ignore flagged prices. In an early Delhi build about **2,100 building outlines were drawn twice** because different spellings of one place matched the same OpenStreetMap polygon. *Action:* spellings are now pooled per polygon, and `build_delhi_open.py` asserts that no outline is drawn under two entries (it stops the build if one is).
- **Provenance:** OpenML's description says the listings came from a real-estate website; "CC0" is the uploader's label. *Action:* disclosed; used as a baseline.

**Explain simply:** "We counted the holes in our data and made each hole visible instead of filling it with a guess."

---

## Slide 7: Matching rents and air to buildings (Presenter 2)

**Says:** Three steps (find buildings, match rents, attach air) and three guarantee numbers: 0 double-drawn outlines, 88% of priced Delhi entries borrow a nearby locality's rent, 2,089 Delhi entries.

**What is happening (this is `flat-finder-localytics/pipeline/build_delhi_open.py`):**
1. **Find the buildings.** Reads the OpenStreetMap file with `pyosmium`, turns outlines into shapes with `shapely`, and creates **one entry per polygon**. The 2,089 entries are 948 apartment buildings (about 250 of them are groups of apartment buildings that have no name in OpenStreetMap) and 1,141 builder-floor colonies and other named residential areas. The BBBike extract spills into Gurugram and Noida, so everything is clipped to the Delhi boundary and **977 Gurugram candidates are removed**. Names like JJ, camp, resettlement, village, industrial, warehouse are excluded.
2. **Match rents.** The OpenML file only has locality-level coordinates, so a building cannot be matched to its own listings. For each building we take the **median rent by BHK in its locality**, needing **at least 3 listings** per bucket; apartments use apartment listings, colonies use builder-floor listings. If the building's own locality has no data we **borrow the nearest locality's rents within 1.5 km** (1.0 km for the extra entries), found with a nearest-neighbour search (`scipy` `cKDTree`), and the card says which locality and how far. 1,539 Delhi entries have a rent; of those, **88%** (1,361) use a nearby locality.
3. **Attach air.** For every building, the nearest PM2.5 monitor within **5 km**, with its reading time. No monitor in range means no reading.

Then `build_ncr.py` merges Delhi (`delhi.json`) and Gurugram (`gurgaon.json`) into `ncr.json`, tags each building with its city, and writes the shapes, details and CSV files the map loads.

**Careful:** The 88% is why we call Delhi rents "indicative". Do not call them building prices.

---

## Slide 8: Approach and Python libraries by stage (Presenter 3)

**Says:** Five stages (collect, clean and match, score and rank, visualise, ask) with the real libraries under each.

**What is happening, library by library:**
- **Collect:** `urllib` (downloads and the data.gov.in client), `osmium` (pyosmium: reads the OpenStreetMap file), `sqlite3` (the `areas.sqlite` database), `csv`/`json`, `python-dotenv` (reads the keys from `.env`).
- **Clean and match:** `shapely` (polygons, boundary clipping), `pyproj` (project latitude/longitude to metres so distances are right; used in the area builder), `numpy`, `scipy` (`cKDTree` nearest-neighbour search, connected components), `difflib` (matches near-identical place names).
- **Score and rank:** `scikit-learn` (K-Means, hierarchical clustering, silhouette, adjusted Rand index), `numpy`, `statistics`, and our own scoring code (`areas.py`).
- **Visualise:** `Flask` (website), `Flet` (desktop and browser app), `folium` (transport map), and for the property map `Vite` + `MapLibre GL JS` (JavaScript, not Python).
- **Ask:** `google-genai` (Gemini), `anthropic` (optional Claude), a small tool-calling loop, and the standard `http.server` for the data service.
- **Quality:** `pytest`, `Vitest` (JavaScript tests), `ruff` (code style).

**Careful:** Be honest that part of the stack is JavaScript (the map). The professor asked for the Python libraries; the diagram shows Python ones plus the front-end.

---

## Slide 9: Area model and its stability test (Presenter 3)

**Says:** The score formula, ten factors, the stability test (bars) and the similar-area groups.

**What is happening (Localytics repo: `areas.py`, `config.py`, `clustering.py`, `scripts/build_areas.py`):**
- `build_areas.py` cuts Delhi (1,488 km²) into **1,487 one-kilometre cells** and, from the OpenStreetMap extracts, counts and measures the facilities around each cell. This is stored in `data/areas.sqlite`.
- `scripts/add_gurugram_cells.py` adds **1,257 Gurugram cells** (Gurugram district, 1,253 km², OpenStreetMap boundary relation 3577685) to the same database. They are built by the same code (`grid_cells.py`, shared with `build_areas.py`) from the facilities already stored, so a Gurugram cell and a Delhi cell are scored alike; a test rebuilds existing Delhi cells and checks they come out identical. Delhi's cells, the clustering report and the robustness report are untouched, so **clusters and sensitivity results are Delhi-only**; the Flask site and the Flet app still show Delhi only, while the property map's neighbourhood panel shows both. The map's air layer on the grid uses the same 24 Nov snapshot as the building dots, with each reading's real age shown. The district is mostly farmland outside the built-up core, so many Gurugram cells have few mapped facilities and score low, as Delhi's rural west does.
- For each cell and each factor a score between 0 and 1 is computed. Services: half "how close is the nearest" and half "how many within the radius" (radius 1, 2 or 5 km; count cap 5, 10 or 20). Workplace: `1 − min(km ÷ 50, 1)`. Air: `1 − min(PM2.5 ÷ 250, 1)`; the cap of 250 is a project choice, not a health threshold, and only a reading from a monitor within 5 km and 6 hours old counts.
- You set an importance from 0 to 5 per factor. Weights are normalised (priority ÷ sum of priorities) and **area score = 100 × Σ weight × factor score**. A cell with missing evidence for a factor you weighted is **excluded**, not guessed.
- **Stability test** (`data/evaluation_report.json`): eight scenarios over all 1,487 cells; how many of the default top-10 areas stay. Equal weights on the four core factors: 10 of 10. Radius 5 km, count cap 5 or 20: 6 of 10. Transit only: 4. Radius 1 km: 3. Schools only: 2. **So small tweaks move about 4 of the top 10; changing the priority mix moves 6 to 8.** That is the argument for letting the user set weights.
- **Clusters** (`data/cluster_report.json`): K-Means and hierarchical clustering for k = 2 to 6 on 16 facility features, scored by silhouette; the best is K-Means with **k = 2** (silhouette 0.357: moderately separated). Re-clustering five random 80% subsamples gives an **adjusted Rand index of 0.978**: the groups are stable. Groups of 761 and 726 cells. The clusters only describe similar areas; they never change a score.

**Careful:** This area model covers **Delhi only** (the cells). Gurugram is covered by the building map. The screenshot is the real Flask page.

---

## Slide 10: The assistant agent (Presenter 3)

**Says:** Five steps (you ask, the model asks back, the engine ranks, the model explains, the map shows) and three safeguards.

**What is happening (files: `web/src/advisor.js`, `integration/localytics_api.py`, `integration/advisor_chat.py`, `integration/advisor.py`):**
1. You type in the Ask panel. The browser sends it to the data service (`POST /api/localytics/advisor/chat`).
2. `advisor_chat.py` sends the conversation to **Gemini** with one tool, `search_homes`. The system prompt says: never invent numbers; ask for what is missing (rent or buy, BHK, city, budget); accept "don't mind"; ask at most three questions.
3. If the brief is complete, Gemini calls `search_homes` with structured fields (mode, city, bhk, budget, workplace, distance, air priority, must-haves, nice-to-haves). If something is missing, the tool returns an error that tells Gemini what to ask.
4. `advisor.py` runs the search over `ncr.json`: it applies the same filters as the map's filter panel, groups matching buildings into areas (locality; at least 3 buildings), scores each area and returns the top ones with real numbers and caveats.
5. Gemini writes a short reply from those numbers. The browser draws numbered pins and rings on the map and sets the left filters to match, using the engine's result, **not** the model's words.

**Ranking weights:** budget fit **0.30**, commute **0.30**, air **0 / 0.2 / 0.4** (none / some / high), each nice-to-have **0.10**. Air is ranked **relative to all other buildings**, because every reading is poor (the minimum PM2.5 is 84). Missing air counts as unknown (0.25), never good. With both cities selected each city is ranked on its own (two areas each), because Delhi's 2020 rents would always win.

**Reliability:** The Gemini free tier is often overloaded (HTTP 503). The code retries once, tries other Flash models for up to about 25 seconds, then shows "busy"; the **quick form** ("Prefer a short form?") runs the same engine with no model. Keys live in `Localytics/.env` (never in the repo). A parity test proves the engine's count equals the filter panel's count.

**Explain simply:** "The model is an interpreter. The calculator is our code."

**Careful:** Workplace is found by matching a locality or society name in the data (no coordinates from memory); "Cyber City" is not a locality in our data, "Golf Course Road" is. Commute is straight-line, not travel time.

---

## Slide 11: One map and the rent comparison (Presenter 4)

**Says:** The map, 4,650 buildings, 1,990 match a 3 BHK rent search, and a bar chart of median rents by BHK.

**What is happening:**
- The screenshot is the real app around Golf Course Road: extruded blocks are mapped buildings; orange ones match the filter.
- **1,990** = buildings with a 3 BHK rent among apartments and builder floors: **919 Gurugram + 1,071 Delhi**.
- **The bars** are the *median of the buildings' rent medians* for each BHK (computed from `ncr.json`): Delhi **13.5k, 22k, 30k, 42.5k** and Gurugram **20k, 32.5k, 51k, 85k** for 1 to 4 BHK (based on 978/1,190/1,071/446 Delhi buildings and 100/327/518/281 Gurugram buildings).
- Delhi's numbers are 2020 locality medians (many buildings share one locality's value); Gurugram's are current listing medians.

**Careful:** This chart is **not like-for-like** (six years of rent growth sit in the Delhi bars). The slide says so; say it out loud.

---

## Slide 12: Air quality and schools (Presenter 4)

**Says:** Left: air bands for both cities from one day's 24-hour averages (none Good, none Severe), medians 112 (Delhi) and 154 (Gurugram). Right: school profile numbers and how pincodes differ.

**What is happening, air:**
- Each building shows the PM2.5 of the nearest government monitor within 5 km (`build_delhi_open.py` loads the monitors, `build_ncr.py` attaches them to **both** cities from the same list, so the two are read on the same day).
- **Delhi**, 1,276 buildings, 17 monitors: **Moderate 366 (29%), Poor 476 (37%), Very poor 434 (34%)**; Good, Satisfactory and Severe: 0. **Median 112 µg/m³** (monitors from 68 to 140).
- **Gurugram**, 1,507 buildings, 5 Gurugram monitors plus 2 Delhi border monitors (183 buildings): **Poor 191 (13%), Very poor 1,316 (87%)**. **Median 154 µg/m³** (monitors from 102 to 154). Sector-51 (154) serves 849 buildings, Vikas Sadan (138) 382, and 66 more use Teri Gram, so the median is really "what Sector-51 says". On this day Gurugram reads worse than Delhi.
- Why 24-hour averages: the same Sector-51 monitor read 75 to 140 for most of 24 Nov and 300 to 400 after 7 pm. The latest hour alone would have shown 383 and made half of Gurugram look Severe.
- Bands follow the app's PM2.5 palette: Good ≤30, Satisfactory ≤60, Moderate ≤90, Poor ≤120, Very poor ≤250, Severe above.
- Because every area is poor, a pass/fail air filter would return nothing, so the assistant ranks air relatively.

**What is happening, schools (`school_profiles.py`, `scripts/build_school_profiles.py`, `data/schools/`):** 5,556 UDISE+ schools grouped into 93 pincodes using the pincode boundaries. Each pincode gets shares (who runs the schools, level, board, medium) and **10th to 90th percentile ranges** for staffing (only with at least 5 schools). Ratios above 100 are treated as data errors. **No quality score**: pincode explains only a small share of how schools differ, and the figures are school-reported. Delhi-wide: **2,637 of 5,556 (47%) are private unaided**; median pupil-teacher ratio **28.3** (range 16.5 to 41.6 across schools). Across pincodes the private share runs **0% to 81%** and the median ratio **15.8 to 38.5**.

**Careful:** One day's 24-hour average (24 Nov) is not a seasonal or annual figure; only five Gurugram monitors, so a few of them carry a lot of weight; it is the nearest monitor, not a reading at the building; it is not an official AQI. The school pages exist in the Flask website only, not in the Flet app or the property map.

---

## Slide 13: Worked examples (Presenter 4)

**Says:** Three real searches and their results.

**What is happening:** Each example is the output of `advisor.search(brief)` on `ncr.json`:
- **A** (rent, both cities, 3 BHK, up to ₹60k, near Golf Course Road within 8 km, air matters): 205 buildings, all Gurugram. #1 Sector 55 (₹44.6k median rent, PM2.5 121 known for 5 of 5 buildings, 3.5 km), #2 Sector 92 (₹30.6k, PM2.5 138 for 4 of 4, 3.7 km). No Delhi building lies within 8 km.
- **B** (rent, Delhi, 2 BHK, up to ₹30k, metro within 1.5 km and a school within 1 km): 936 buildings; #1 Shahdara (₹12k, Aug 2020, metro 488 m, PM2.5 87), #2 Chhattarpur Enclave Phase 1 (₹14.2k, metro 1.4 km, PM2.5 77).
- **C** (buy, Gurugram, 2 BHK, up to ₹1.5 crore, metro within 1.5 km): 38 buildings; only one area has 3 or more (Sector 105, ₹65 lakh).

You can reproduce them in the Ask panel (or the quick form). With Gemini the wording of the reply varies, the numbers do not.

**Careful:** The ₹10k Delhi rents are 2020 medians; expect questions about how low they look.

---

## Slide 14: Client playbook and prototype (Presenter 5)

**Says:** Five steps for a client and a screenshot of the Ask panel.

**What is happening:** The screenshot is the real Ask panel next to the light map. After the search the panel lists areas with fit score, median rent, PM2.5 with how many buildings had a reading, distance, and top buildings; the map shows rings and numbered pins; the left filters have been set (Rent, 3 BHK, up to ₹60k); the building count matches the filter panel.

**Live demo (3 minutes):**
1. Start the services (section "How to run" below). Open http://127.0.0.1:5173/ .
2. Click **Ask**. Send "Find me a nice place to live": it asks for rent or buy, bedrooms, city and budget instead of guessing.
3. Send "3 BHK to rent in Delhi or Gurugram, around 60k, I work near Golf Course Road within 8 km, air matters".
4. Click a building: rents by BHK with their date, PM2.5 with its age. Press the **PM2.5** button.
5. If it says Google is busy, use **Prefer a short form?** (same search, no model).

**Careful:** Do a dry run on the presenting laptop. The free Gemini tier is flaky.

---

## Slide 15: Reliability and limits (Presenter 5)

**Says:** Test counts (88, 30, 39, 7 of 7) and six limitations with next steps.

**What is happening:**
- **88** tests pass in the Localytics repository (`pytest`; two known failures that pre-date us: a Windows file-lock in a native-app test and an overlap-accounting test). That includes the tests for the two air-refresh scripts. The Flat Finder pipeline has 40 more, including the freshness rule.
- **30** tests for the assistant (`integration/test_advisor.py`): the search engine, the model loop for Gemini and Claude with fake clients, overload and quota handling.
- **39** front-end tests (`Vitest`) for the filter logic, including the Buy & rent mode.
- **7 of 7**: the parity test runs seven searches through the Python engine and the map's real JavaScript filters on the real data and checks they return the same buildings.
- Real Gemini was also tested by hand: a vague message gets questions, a complete one runs the search.
- **The six limitations**, each already labelled on screen: Delhi rents from Aug 2020; no Delhi sale prices; PM2.5 is one day's average; commute is straight-line; the free model can be busy; nobody has tested it with real users yet.

**Careful:** Do not hide the two failing tests; the slide says they pre-date us.

---

## Slide 16: Final decision and strategy (Presenter 5)

**Says:** Position Localytics as an *area-shortlisting aid for relocating households, not a price oracle*; three steps (now, next, later); business models to test; thank you and the GitHub link.

**What is happening:** This is the recommendation, not a computation. It follows from the data: the data supports "which areas deserve a visit and why", not "what a flat costs today". **Now:** replace the 2020 Delhi rents with current licensed data and extend the air data from one day to a season (the Haryana monitors are already in). **Next:** routed commute time and Noida; a pilot with 10 to 20 relocating households, measuring how many shortlists become visits. **Later:** a paid pilot with a relocation or HR team. The business models (subscriptions, lead generation, premium reports) are **hypotheses**.

**Likely questions and short answers**
- *Why no quality score for schools?* Pincode explains only a small share of how schools differ, and the figures are reported by schools.
- *Why are Delhi rents from 2020?* It is the best open dataset available; it is labelled everywhere; the roadmap replaces it.
- *What does the AI actually do?* It understands the question and writes the reply. A Python engine produces every number.
- *Is the ranking reliable?* Small tweaks move 4 of the top 10; a different priority mix moves 6 to 8, which is why users set their own weights.
- *Does it work for Gurugram air?* Yes, for 1,507 of 2,561 buildings, from five government monitors, read on the same day and the same basis as Delhi. It is one day and five monitors, so treat it as indicative.

---

## Appendix A: Number cheat-sheet

| Number | Meaning | Where it comes from |
|---|---|---|
| 4,650 | Buildings on the map | `ncr.json` counts: 2,561 Gurugram + 2,089 Delhi |
| 29,389 | Gurugram listings | 22,018 for sale + 7,371 for rent (Flat Finder / Magicbricks) |
| 16,842 / 17,890 / 1,048 | Delhi rent rows usable / read / dropped | `build_delhi_open.py` (OpenML 43837) |
| 467 | Localities | 236 Delhi + 231 Gurugram |
| 1,487 / 1,488 km² | Delhi grid cells / Delhi area | `areas.sqlite`, `area_manifest.json` |
| 1,257 / 1,253 km² | Gurugram grid cells / district area | `areas.sqlite`, `area_manifest.json` (key `gurugram`) |
| 66,636 | Mapped facilities | `areas.sqlite`, table `facilities` |
| 5,556 / 93 / 92 | Schools / pincodes profiled / pincode boundaries | `data/schools/` |
| 2,783 | Buildings with PM2.5 | 1,276 Delhi + 1,507 Gurugram |
| 977 | Gurugram candidates clipped from the Delhi build | `build_delhi_open.py` |
| 88% | Priced Delhi entries using a nearby locality's rent | 1,361 of 1,539 |
| ~2,100 | Outlines drawn twice in an early build (fixed) | Early build; now asserted to be 0 |
| 1,990 | 3 BHK rent matches | 919 Gurugram + 1,071 Delhi |
| 112 / 154 | Median PM2.5 Delhi / Gurugram (24-hour average, 24 Nov) | `ncr.json` |
| 0.357 / 0.978 | Silhouette / stability of the 2 clusters | `cluster_report.json` |
| 88 / 30 / 39 | Test counts | pytest, pytest, Vitest |

## Appendix B: How to run everything

Open PowerShell. Each command in its own window.

```powershell
# 1. Data service (the neighbourhood data and the chat endpoints), from the Localytics folder
cd C:\Users\Jakki\OneDrive\Desktop\Studies\BITS\S1\Python\Project\Localytics; .venv\Scripts\python ..\flat-finder-localytics\integration\localytics_api.py .
```
```powershell
# 2. Property map with the Ask panel -> http://127.0.0.1:5173/
cd C:\Users\Jakki\OneDrive\Desktop\Studies\BITS\S1\Python\Project\flat-finder-localytics\web; npm run dev -- --host 127.0.0.1 --strictPort
```
```powershell
# 3. Localytics website (areas, air quality, schools) -> http://127.0.0.1:5000/
cd C:\Users\Jakki\OneDrive\Desktop\Studies\BITS\S1\Python\Project\Localytics; .venv\Scripts\python -m flask --app app run
```

The chat needs `GEMINI_API_KEY` in `Localytics\.env`. The Gurugram air refresh needs a valid `DATA_GOV_API_KEY` in the same file.

## Appendix C: Before you present

1. Fill the `[name]` placeholders on the cover.
2. **Check the citations** and the portal claims on slide 4 (written from memory).
3. Do a full dry run, including the live demo, on the laptop you will present from.
4. If you re-run `python scripts/refresh_air_openaq.py` and rebuild before presenting, the air numbers change (they are one day's averages): update slides 5, 6, 12 and the PM2.5 values in the slide 13 examples from `scripts` output and `ncr.json`. The deck as it stands matches the 24 Nov 2026 data.
5. Remember: the school pages are in the Flask website only; the area model is Delhi only.
