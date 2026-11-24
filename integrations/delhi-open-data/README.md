# Delhi + Gurugram on one Flat Finder map

Adds **Delhi** to the Flat Finder property map using open data only (no listing-site crawling), merges it with Flat Finder's Gurugram data into one **Delhi NCR** view, and adds a **PM2.5 colour mode**. It sits on top of the [Flat Finder integration](../flat-finder/README.md), so one page shows Delhi and Gurugram buildings, prices and rents by BHK, PM2.5 and the Localytics neighbourhood scores.

Three views, chosen with the city picker. **Delhi NCR · Delhi + Gurugram** is the default.

| View | Buildings | Prices |
|---|---|---|
| Delhi NCR | 4,650 (2,561 Gurugram + 2,089 Delhi) | Gurugram: buy and rent. Delhi: rent only |
| Gurugram | 2,561, unchanged from Flat Finder | Magicbricks listing medians (Flat Finder's own data) |
| Delhi | 2,089 | Locality rent medians, August 2020 (many borrowed from a locality within 1.5 km; about 550 entries have no price) |

The combined view opens in **Rent mode**, the only mode where both cities have data, with **Apartments and Builder floors** both selected so Delhi's colonies are visible. In Buy mode Delhi buildings show as "not checked yet" (no sale prices). Flat Finder's "Load Divy's search" example is hidden in the combined and Delhi views, because it is a Gurugram floor-plan search; use `?city=gurgaon` to demonstrate it.

## What Delhi has, and what it does not

| Has | Does not have |
|---|---|
| About 700 named apartment buildings and housing societies, 250 groups of apartment buildings that are unnamed in OpenStreetMap, 180 builder-floor colonies with their own listings, and 960 other mapped residential areas (housing type not mapped), all with outlines from OpenStreetMap | Sale prices |
| About 200 builder-floor colonies (the main Delhi housing type) | Per-building listings: rents are **locality medians** |
| Rent by BHK (1 to 5), with min, max and listing count | Developers, RERA ids, amenities, ratings, reviews, photos |
| What is nearby (park, school, hospital, metro, mall) from the Localytics database | Floor-plan bedroom sizes |
| Indicative PM2.5 from the nearest monitor within 5 km, with the reading's age | Current rents or current air readings |

## PM2.5

Each building shows PM2.5 from the nearest monitor within 5 km in the readings cached in `Localytics/data/areas.sqlite` (data.gov.in), with the reading's age. These are indicative PM2.5 bands, not an official AQI.

- **Delhi:** 2,053 of 2,089 entries have a value.
- **Gurugram:** only the 537 buildings within 5 km of a cached Delhi monitor have a value, because no Haryana readings are cached. To add them: put your own data.gov.in key in Localytics `.env` as `DATA_GOV_API_KEY=...`, run `python scripts/refresh_air_cache.py Haryana Gurugram` from the Localytics folder (it caches the readings in `data/areas.sqlite` and lists the Gurugram stations it found), then re-run the NCR builder (`build_ncr.py`, command under Rebuild). The builder reads every cached Delhi and Haryana search. A dry run with four made-up monitors raised Gurugram's coverage from 537 to 1,599 buildings; the real figure depends on the real stations. The Flask site's `/air-quality` page does the same refresh from a form. No data.gov.in key? `python scripts/refresh_air_openaq.py` does it from OpenAQ instead (free key in `.env` as `OPENAQ_API_KEY`). It fetches Delhi and Gurugram in the same run, keeps only government reference monitors (not low-cost sensors), stores each monitor's 24-hour average (a single evening hour can read three times the day's level), and writes Gurugram-side monitors to the `["haryana","gurugram"]` cache and Delhi's to `["delhi","openaq"]` (Delhi's own data.gov.in cache is left alone). The builders then ignore any cached reading more than 48 hours older than the newest one, and `build_ncr.py` recomputes Delhi's PM2.5 from the same monitors, so both cities come from one snapshot. Do not substitute a modelled source (for example Open-Meteo) for Gurugram alone: it reads about 3x lower than the measured Delhi monitors.

## Why Delhi looks as dense as it does (`--more`)

Delhi has far fewer *named* buildings in OpenStreetMap than Gurugram has named societies, so the strict version (without `--more`, 923 entries) looked sparse. `--more` adds only real mapped features, in two tiers, with safeguards:

- **Other named residential areas (963):** every named `landuse=residential` polygon not already shown, so colonies and blocks fill the map. Their housing type is not mapped, so the card says so. They are listed under *Builder floors* so the filter works, but the card never claims builder floors.
- **Groups of unnamed apartment buildings (252):** `building=apartments|residential` features with no name, grouped when within 80 m, and only buildings not already inside another entry.
- **Rents are borrowed, and labelled.** These entries take the nearest locality's rents only within 1.0 km, and each BHK line names that locality and the distance. Entries with no locality that close show no price (about 40% of the extra entries).
- **Excluded:** names marked JJ/jhuggi, camp, resettlement, basti, village, gaon, slum, unauthorised, labour, industrial, factory, warehouse.
- **Names:** generic names ("A block", "GH-14") get their locality appended; repeated names get their locality, then a group number.
- **No double drawing:** a polygon gets one entry (different spellings of one place are pooled); a polygon that contains a smaller chosen one is dropped in favour of its parts; the build asserts that no building outline is drawn under two entries.
- **Size:** at most 60 building outlines per extra entry. The combined map is about 80,000 shapes and 24 MB. On the test machine the data downloaded in about half a second locally and the page was usable within a few seconds; do a dry run on the laptop you will present from, since that is the real test.

To go back to the stricter version (874 Delhi entries), rebuild without `--more`, or copy the files from `flat-finder-localytics/pipeline/backup/strict-fixed/` into `web/public/data/`. An earlier strict build (923 entries) drew about 2,100 building outlines twice, because different spellings of one place matched the same OpenStreetMap polygon; the builders now pool those spellings and assert that no outline is drawn under two entries.

## Demo tips

- **Amenity filters (Squash, Pool, Gym...) apply to Gurugram only.** Delhi entries have no mapped amenities, so any amenity filter hides all of Delhi. Use the **Nearby** filters (Park, Metro, School, Hospital, Mall) instead; they work for both cities.
- **The rent slider** hides Delhi entries that have no price (shown as "not checked yet") rather than counting them as matches.
- **In Buy mode** Delhi buildings are "not checked yet" (no sale prices).

## Sources, licences and caveats

- **Buildings and colonies:** OpenStreetMap, BBBike "NewDelhi" extract (ODbL). The extract spills into Gurugram and Noida, so everything is clipped to the Delhi boundary (`Localytics/data/delhi_boundary.geojson`, DataMeet, CC BY-SA 2.5 India).
- **Delhi rents:** [New Delhi Rental Listings, OpenML 43837](https://www.openml.org/search?type=data&id=43837), declared CC0 by its uploader. **Collected 11 August 2020, so about six years old.** Its description says the listings come from a real-estate website; the CC0 label is the uploader's declaration, so treat reuse with care. Listings sit at locality-level coordinates, so a building cannot be matched to its own listings.
  - Apartment buildings use only apartment listings; colonies use only builder-floor listings. Houses and villas are not used.
  - A bucket needs at least 3 listings. Typos and implausible rows are dropped (1,048 of 17,890 rows).
  - A named building takes the nearest locality's rents only within 1.5 km; the extra entries below only within **1.0 km**; otherwise no price. Every card names the locality and the distance.
- **Gurugram:** Flat Finder's own data (Magicbricks listings, OpenStreetMap, HRERA), untouched.
- **PM2.5:** see above.

## Rebuild

Needs the Localytics Python environment (`osmium`, `shapely`, `scipy`, `numpy`).

```bash
# 1. data (public downloads)
curl -L -o NewDelhi.osm.pbf https://download.bbbike.org/osm/bbbike/NewDelhi/NewDelhi.osm.pbf
curl -L -o New-Delhi-Rental-Listings.arff https://openml.org/data/v1/download/22102662/New-Delhi-Rental-Listings.arff

# 2. put the kit into a Flat Finder clone that already has the Localytics integration applied
cp files/pipeline/*.py ../flat-finder-localytics/pipeline/
cp files/web/src/* ../flat-finder-localytics/web/src/
cp files/integration/* ../flat-finder-localytics/integration/
git -C ../flat-finder-localytics apply "$PWD/delhi-web.patch"

# 3. build, from your Localytics checkout: Delhi first, then the combined NCR file
.venv/Scripts/python ../flat-finder-localytics/pipeline/build_delhi_open.py --more \
  --pbf NewDelhi.osm.pbf --rents New-Delhi-Rental-Listings.arff --localytics .
PYTHONPATH=../flat-finder-localytics/pipeline .venv/Scripts/python \
  ../flat-finder-localytics/pipeline/build_ncr.py --localytics .
```

`delhi-web.patch` is relative to Flat Finder `f7a4612` with the Localytics integration patch already applied. It makes the app wording and Buy-mode logic per building, defaults to the NCR view, adds the PM2.5 button, replaces the Buy / Rent toggle with a **Show** menu (Buy & rent by default; a budget counts only for the way it was set), moves the match count above Amenities, and widens the neighbourhood panel to Delhi + Gurugram. Gurugram alone behaves as before. Tests: `cd ../flat-finder-localytics/web && npx vitest run --root .. web/src` (39 pass, including `mixed-city.test.js` and the Buy & rent cases). The advisor's Python tests: `cd ../flat-finder-localytics && <localytics python> -m pytest integration/test_advisor.py` (30 pass: engine, parity with the real JS filters, and the chat loop for both Gemini and Claude with fake clients, including overload and quota handling).

## Gurugram on the neighbourhood grid

The coloured one-kilometre grid used to cover Delhi only. `Localytics/scripts/add_gurugram_cells.py` adds 1,257 Gurugram cells (Gurugram district, OpenStreetMap boundary, `data/gurugram_boundary.geojson`) to `data/areas.sqlite`, built by the same code as Delhi's (`Localytics/grid_cells.py`, now shared with `build_areas.py`) from the facilities already stored. They are `GG43_*` rows beside Delhi's `DL43_*`. `AreaRepository.dataset(include_gurugram=True)` returns both; the default stays Delhi-only, so the Flask site, the Flet app, the clustering and the evaluation reports are unchanged. `integration/localytics_api.py` (in `delhi-web.patch`) asks for both cities and reads the air layer from the combined same-day snapshot (see PM2.5 above). Tests: `Localytics/tests/test_grid_cells.py`, including a check that Delhi cells rebuilt from the stored facilities match the stored ones.

## Ask Localytics (chat advisor)

An **Ask** button opens a side panel on the combined Delhi NCR map. Say what you need ("3 BHK to rent near Golf Course Road, around 70k, air matters") and it ranks areas, numbers them on the map and applies the same filters in the left panel. If something is missing or vague ("cheap", "nice place") it asks, instead of guessing.

- **The model never searches or invents numbers.** The language model (Gemini or Claude) only asks questions and fills in a brief; its one tool, `search_homes`, runs `integration/advisor.py` over the map's own data, and the page draws the areas from that result. The building count in the chat equals the filter panel's count (tested against the real JS filters).
- **Needs an API key for the chat; Gemini has a free tier.** Get a key at <https://aistudio.google.com/apikey>, put `GEMINI_API_KEY=...` in `Localytics/.env` yourself, `pip install google-genai` into the Localytics environment, and restart the data service. The default model is `gemini-3.5-flash-lite` (the `gemini-2.5-*` models are closed to new accounts). Google's free tier is often overloaded (HTTP 503 "high demand"), so a call retries once, then tries other Flash models your key lists, newest first, for up to about 25 seconds; after that the panel says Google is busy and offers the form. Set `GEMINI_MODEL` in `.env` to pin one. Claude works too: `ANTHROPIC_API_KEY=...` and `pip install anthropic` (default `claude-opus-5-5`, override with `ADVISOR_MODEL`, refusal fallback on). With both keys set, Gemini is used unless `ADVISOR_PROVIDER=anthropic`. Without a key, or offline, the panel shows a short **form** that runs the same search, so a presentation cannot fail. Free-tier quotas are small and can run out (the panel then says so and offers the form).
- **How areas are ranked:** budget fit, PM2.5 relative to every other area (a missing reading counts as unknown, never clean), straight-line distance to the workplace, and nice-to-haves (metro, school, park...). With both cities, each city is ranked on its own, because Delhi's 2020 rents would otherwise always win. An area needs at least 3 matching buildings.
- **Workplace:** matched to a locality or society name in the data (no coordinates from memory); if it is not found, the assistant asks for the nearest sector, colony or society. "Cyber City" is not a locality in the data, for example; "Golf Course Road" is.
- **Delhi schools:** each Delhi area shows the UDISE+ school profile of its pincode (schools, share private, pupils per teacher) from the Localytics school data, as a profile, not a quality score.
- **Limits:** one conversation is 30 messages; conversations live in the data service's memory and are lost on restart; commute is straight-line distance, not travel time.

## Run

```bash
# terminal 1, from the Localytics folder (the neighbourhood panel's data service)
.venv/Scripts/python ../flat-finder-localytics/integration/localytics_api.py .
# terminal 2
cd ../flat-finder-localytics/web && npm run dev -- --host 127.0.0.1 --strictPort
```

Open `http://127.0.0.1:5173/` for both cities, `?city=delhi` or `?city=gurgaon` for one, and add `&color=pm25` to start in PM2.5 mode.
