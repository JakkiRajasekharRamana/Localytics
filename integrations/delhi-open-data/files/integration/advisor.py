"""Search and ranking engine behind the chat advisor.

The language model never searches or invents numbers. It only turns what the user says into a brief (budget, BHK,
workplace...). This module runs that brief over the real Delhi + Gurugram data (web/public/data/ncr.json) and returns
areas with measured numbers. The hard filters here mirror web/src/filters.js (matchSociety), so the count shown in the
chat equals the count the map's filter panel shows. integration/test_advisor.py checks that against the real JS.
"""

import json
import math
import re
import statistics
from collections import defaultdict
from difflib import get_close_matches
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "web" / "public" / "data" / "ncr.json"

# Mirrors NEAR in web/src/filters.js: OSM place kinds and the distance (metres) a building must be within.
NEAR = {
    "park": (("park",), 500),
    "metro": (("metro", "rail"), 1500),
    "school": (("school",), 1000),
    "hospital": (("hospital",), 2000),
    "shopping": (("shopping",), 1500),
}
KINDS = ("apartment", "builder floor", "villa", "plot")
CITIES = {"delhi": "Delhi", "gurugram": "Gurugram"}
MIN_AREA_BUILDINGS = 3  # an "area" needs at least this many matching buildings
AIR_WEIGHT = {"none": 0.0, "some": 0.2, "high": 0.4}
COST_WEIGHT, COMMUTE_WEIGHT, WISH_WEIGHT = 0.30, 0.30, 0.10


class BriefError(ValueError):
    """The brief is incomplete or inconsistent; the message says what to ask the user."""


# ---------- data ----------
_cache = {}


def load(path=DATA):
    key = str(path)
    if key not in _cache:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        societies = doc["societies"]
        _cache[key] = dict(doc=doc, societies=societies, air=_air_reference(societies))
    return _cache[key]


def _air_reference(societies):
    """Sorted PM2.5 values of every building with a reading, to rank one area's air against all of the others."""
    return sorted(s["air"]["pm"] for s in societies if s.get("air") and s["air"].get("pm") is not None)


def air_percentile(pm, reference):
    """Share of buildings with cleaner air (a lower PM2.5 reading) than this one: 0 is the cleanest, 1 the worst."""
    if pm is None or not reference:
        return None
    lo = sum(1 for v in reference if v < pm)
    hi = sum(1 for v in reference if v <= pm)
    return ((lo + hi) / 2) / len(reference)


# ---------- the filter logic of web/src/filters.js (the subset the advisor uses) ----------
def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(a))


def near_m(s, kinds):
    """Distance in metres to the nearest of these place kinds, or infinity when unknown (filters.js: `?? Infinity`)."""
    ms = [((s.get("nearby") or {}).get(k) or {}).get("m") for k in kinds]
    return min((m for m in ms if m is not None), default=math.inf)


def price_for(s, mode, bhk):
    """Cheapest price for the chosen BHKs: listing median first, our estimate otherwise (same rules as priceFor in filters.js)."""
    best = None
    for b, p in (s.get("prices") or {}).items():
        if bhk and int(b) not in bhk:
            continue
        flagged = (p.get("flags") or {}).get(mode)
        real = None if flagged else (p.get(mode) or {}).get("median")
        est = (p.get(f"{mode}_est") or {}).get("value")
        value = real if real is not None else est
        if value and (best is None or value < best["value"]):
            best = dict(value=value, estimated=real is None, bhk=int(b), n=None if real is None else (p.get(mode) or {}).get("n"))
    if best is None and mode == "buy" and s.get("price_min") and not bhk:
        best = dict(value=s["price_min"], estimated=False, bhk=None)
    return best


def state(s, c):
    """'match' when the building passes every hard filter in c, else 'no' or 'unknown' (not checked)."""
    if c["mode"] == "buy" and s.get("no_sale"):
        return "unknown"  # this building's source has no sale prices
    if c.get("city") and s.get("city_label") and s["city_label"] != c["city"]:
        return "no"
    if c["kinds"] and s["kind"] not in c["kinds"]:
        return "no"
    for key in c.get("near") or []:
        kinds, metres = NEAR[key]
        if near_m(s, kinds) > metres:
            return "no"
    commute = c.get("commute")
    if commute and haversine_km(s["lat"], s["lng"], commute["lat"], commute["lng"]) > commute["km"]:
        return "no"
    budget = c.get("maxRent") if c["mode"] == "rent" else c.get("maxPrice")
    floor = c.get("minRent") if c["mode"] == "rent" else c.get("minPrice")
    if budget or floor:
        p = price_for(s, c["mode"], c["bhk"])
        if not p and (s.get("open_data") or c.get("strictPrice")):
            return "unknown"  # no price for this mode: it cannot be shown to fit a budget
        if p and budget and p["value"] > budget:
            return "no"
        if p and floor and p["value"] < floor:
            return "no"
    if c["bhk"]:
        units = [u for u in s.get("unit_types") or [] if u["bhk"] in c["bhk"]]
        if not units:
            return "no" if s.get("unit_types") else "unknown"
    return "match"


# ---------- the brief ----------
def normalise(brief):
    """Validate a brief and turn it into the criteria the map's filter panel understands. Raises BriefError."""
    missing = []
    mode = brief.get("mode")
    if mode not in ("rent", "buy"):
        missing.append("mode (rent or buy)")
    try:
        bhk = sorted({int(b) for b in brief.get("bhk") or [] if 1 <= int(b) <= 6})
    except (TypeError, ValueError):
        raise BriefError("bhk must be a list of whole numbers from 1 to 6") from None
    if 5 in bhk and 6 not in bhk:
        bhk.append(6)  # "5+" in the filter panel means 5 and 6
    if not bhk:
        missing.append("bhk (how many bedrooms)")
    city = brief.get("city")
    if city not in ("delhi", "gurugram", "both"):
        missing.append("city (delhi, gurugram or both)")
    budget = brief.get("budget_max")
    if budget is not None and (not isinstance(budget, (int, float)) or budget <= 0):
        raise BriefError("budget_max must be a positive number of rupees")
    if missing:
        raise BriefError("Ask the user for: " + ", ".join(missing))
    if mode == "buy" and city == "delhi":
        raise BriefError("Delhi has no sale prices in this data (rents only). Tell the user, and ask whether to look at Gurugram purchases or Delhi rents instead.")
    kinds = [k for k in brief.get("kinds") or ["apartment", "builder floor"] if k in KINDS] or ["apartment", "builder floor"]
    near = [k for k in brief.get("must_be_near") or [] if k in NEAR]
    wishes = [k for k in brief.get("nice_to_have") or [] if k in NEAR and k not in near]
    air = brief.get("air_priority") or "some"
    if air not in AIR_WEIGHT:
        air = "some"
    criteria = dict(mode=mode, kinds=kinds, bhk=bhk, near=near, city=None if city == "both" else CITIES[city])
    if budget:
        criteria["maxRent" if mode == "rent" else "maxPrice"] = float(budget)
        criteria["strictPrice"] = True  # a society with no price for this BHK cannot be said to fit the budget
    return criteria, dict(city=city, wishes=wishes, air=air, budget=budget, workplace=brief.get("workplace"), max_commute_km=brief.get("max_commute_km"))


# ---------- finding the workplace in the data ----------
def _norm(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _centre(members):
    return statistics.median(s["lat"] for s in members), statistics.median(s["lng"] for s in members)


def resolve_place(data, text, city=None):
    """Find a place by locality or society name. Returns dict(status='found'|'ambiguous'|'not_found', ...).

    No coordinates are recalled from memory: the place's position is the middle of the mapped buildings that carry the name.
    """
    query = _norm(text)
    if not query:
        return dict(status="not_found", options=[])
    wanted = CITIES.get(city) if city in CITIES else None
    groups = defaultdict(list)
    for s in data["societies"]:
        if wanted and s.get("city_label") != wanted:
            continue
        if s.get("locality"):
            groups[("locality", s.get("city_label"), s["locality"])].append(s)
    tokens = query.split()

    def hits(names):
        exact = [k for k in names if _norm(k[2]) == query]
        if exact:
            return exact
        return [k for k in names if all(t in _norm(k[2]).split() for t in tokens)]

    found = hits(list(groups))
    if not found:  # a society name, e.g. "DLF Phase 3 Towers"
        by_name = [s for s in data["societies"] if (not wanted or s.get("city_label") == wanted) and all(t in _norm(s["name"]).split() for t in tokens)]
        if by_name:
            if len(by_name) > 1 and len({(s["city_label"], s.get("locality")) for s in by_name}) > 1:
                return dict(status="ambiguous", options=sorted({f"{s['name']} ({s.get('locality') or s['city_label']})" for s in by_name})[:6])
            lat, lng = _centre(by_name)
            return dict(status="found", name=by_name[0]["name"], city=by_name[0]["city_label"], lat=lat, lng=lng, n=len(by_name), via="society name")
    if len(found) == 1:
        key = found[0]
        lat, lng = _centre(groups[key])
        return dict(status="found", name=key[2], city=key[1], lat=lat, lng=lng, n=len(groups[key]), via="locality")
    if len(found) > 1:
        return dict(status="ambiguous", options=sorted(f"{k[2]} ({k[1]})" for k in found)[:8])
    close = get_close_matches(query, sorted({_norm(k[2]) for k in groups}), n=5, cutoff=0.6)
    names = {}
    for k in groups:
        names.setdefault(_norm(k[2]), f"{k[2]} ({k[1]})")
    return dict(status="not_found", options=[names[c] for c in close])


# ---------- search and ranking ----------
def _median(values):
    return statistics.median(values) if values else None


def _score(parts, weights):
    """Weighted mean (0 to 100) of the parts that have a value; parts without data take no weight."""
    live = {k: v for k, v in parts.items() if v is not None and weights.get(k)}
    total = sum(weights[k] for k in live)
    return round(100 * sum(weights[k] * v for k, v in live.items()) / total) if total else None


def search(brief, path=DATA, top=5):
    """Run a brief. Returns a dict with criteria for the map, counts, ranked areas, caveats. Raises BriefError."""
    data = load(path)
    societies = data["societies"]
    criteria, extra = normalise(brief)

    place = None
    if extra["workplace"]:
        place = resolve_place(data, extra["workplace"])
        if place["status"] != "found":
            hint = "; ".join(place["options"]) or "none close"
            raise BriefError(f"Could not pin down the workplace '{extra['workplace']}' ({place['status'].replace('_', ' ')}; options: {hint}). Ask the user for the nearest sector, colony or society name as shown on the map.")
        cap = extra["max_commute_km"]
        if cap:
            criteria["commute"] = dict(lat=place["lat"], lng=place["lng"], km=float(cap), name=place["name"])

    matched = [s for s in societies if state(s, criteria) == "match"]
    mode, bhk, budget = criteria["mode"], criteria["bhk"], extra["budget"]
    weights = dict(cost=COST_WEIGHT, air=AIR_WEIGHT[extra["air"]], commute=COMMUTE_WEIGHT if place else 0)
    for key in extra["wishes"]:
        weights[f"wish_{key}"] = WISH_WEIGHT

    def parts_for(prices, pms, coords, near_shares, pool_prices=None):
        parts = {}
        mid = _median(prices)
        if mid is not None:
            parts["cost"] = max(0.0, min(1.0, 1 - mid / budget)) if budget else None
        parts["air"] = None
        if pms:
            parts["air"] = 1 - air_percentile(_median(pms), data["air"])
        elif weights["air"]:
            parts["air"] = 0.25  # no reading is "unknown", never "good"
        parts["commute"] = None
        if place and coords:
            ref = extra["max_commute_km"] or 25
            parts["commute"] = max(0.0, 1 - haversine_km(coords[0], coords[1], place["lat"], place["lng"]) / ref)
        for key in extra["wishes"]:
            parts[f"wish_{key}"] = near_shares.get(key)
        return parts

    def near_share(members, key):
        kinds, metres = NEAR[key]
        return sum(1 for s in members if near_m(s, kinds) <= metres) / len(members)

    # cost without a budget: rank by relative price instead
    groups = defaultdict(list)
    unlabeled = 0
    for s in matched:
        if s.get("locality"):
            groups[(s["city_label"], s["locality"])].append(s)
        else:
            unlabeled += 1
    areas = []
    for (city, locality), members in groups.items():
        if len(members) < MIN_AREA_BUILDINGS:
            continue
        found = [p for p in (price_for(s, mode, bhk) for s in members) if p]
        prices = [p["value"] for p in found]
        counts = [p["n"] for p in found if p.get("n")]
        pms = [s["air"]["pm"] for s in members if s.get("air") and s["air"].get("pm") is not None]
        lat, lng = _centre(members)
        radius = sorted(haversine_km(lat, lng, s["lat"], s["lng"]) for s in members)[int(0.9 * (len(members) - 1))] * 1000
        shares = {k: near_share(members, k) for k in extra["wishes"]}
        areas.append(dict(
            city=city, name=locality, n=len(members), lat=lat, lng=lng, radius_m=int(max(350, min(2500, radius))),
            price=dict(median=_median(prices), low=min(prices), high=max(prices), priced=len(prices), listings=_median(counts), open_data=any(s.get("open_data") for s in members)) if prices else None,
            pm25=dict(median=_median(pms), low=min(pms), high=max(pms), known=len(pms), of=len(members)) if pms else dict(known=0, of=len(members)),
            nearest=_nearest(members), commute_km=round(haversine_km(lat, lng, place["lat"], place["lng"]), 1) if place else None,
            ids=[s["id"] for s in members], _prices=prices, _pms=pms, _shares=shares))

    if not budget:  # no budget given: cost is relative among the candidate areas of the same city
        for city in {a["city"] for a in areas}:
            medians = sorted(a["price"]["median"] for a in areas if a["city"] == city and a["price"])
            for a in areas:
                if a["city"] == city and a["price"] and len(medians) > 1:
                    a["_cost_rel"] = 1 - medians.index(a["price"]["median"]) / (len(medians) - 1)
    for a in areas:
        parts = parts_for(a["_prices"], a["_pms"], (a["lat"], a["lng"]), a["_shares"])
        if "_cost_rel" in a:
            parts["cost"] = a["_cost_rel"]
        a["parts"] = {k: round(v, 2) for k, v in parts.items() if v is not None}
        a["score"] = _score(parts, weights)
        a["school"] = _school_summary(a) if a["city"] == "Delhi" else None
        a["buildings"] = _best_buildings(a, matched, criteria, extra, place, weights, data, parts_for, near_share)
    ranked = sorted((a for a in areas if a["score"] is not None), key=lambda a: (-a["score"], -a["n"]))

    # a mixed ranking sorted by rent would always favour Delhi (its rents are from 2020), so each city is ranked alone
    picked = []
    if extra["city"] == "both":
        per = max(2, top // 2)
        for c in ("Gurugram", "Delhi"):
            picked += [a for a in ranked if a["city"] == c][:per]
    else:
        picked = ranked[:top]
    for rank, a in enumerate(picked, 1):
        a["rank"] = rank
    for a in picked:
        a["reasons"] = _reasons(a, mode, budget, place)
    for a in areas:
        for k in ("_prices", "_pms", "_shares", "_cost_rel"):
            a.pop(k, None)

    counts = dict(matched=len(matched), delhi=sum(1 for s in matched if s.get("city_label") == "Delhi"),
                  gurugram=sum(1 for s in matched if s.get("city_label") == "Gurugram"),
                  without_locality=unlabeled, areas_ranked=len(ranked))
    result = dict(criteria=criteria, counts=counts, areas=picked, workplace=place, warnings=_warnings(data, criteria, extra, matched, picked, unlabeled, place))
    if not picked:
        result["why_empty"] = diagnose_empty(brief, path)
        if matched:
            result["warnings"].append(f"{len(matched)} buildings match but fewer than {MIN_AREA_BUILDINGS} share any one area, so no area is ranked; they are still highlighted on the map.")
    return result


def _nearest(members):
    out = {}
    for key, (kinds, _) in NEAR.items():
        ms = [m for m in (near_m(s, kinds) for s in members) if m != math.inf]
        out[key] = int(_median(ms)) if ms else None
    return out


def _best_buildings(area, matched, criteria, extra, place, weights, data, parts_for, near_share):
    members = [s for s in matched if s["id"] in set(area["ids"])]
    rows = []
    for s in members:
        p = price_for(s, criteria["mode"], criteria["bhk"])
        pm = s["air"]["pm"] if s.get("air") and s["air"].get("pm") is not None else None
        parts = parts_for([p["value"]] if p else [], [pm] if pm is not None else [], (s["lat"], s["lng"]), {k: near_share([s], k) for k in extra["wishes"]})
        score = _score(parts, weights)
        rows.append(dict(id=s["id"], name=s["name"], kind=s["kind"], price=p["value"] if p else None, estimated=bool(p and p["estimated"]),
                         pm25=pm, score=score if score is not None else -1, lat=s["lat"], lng=s["lng"]))
    rows.sort(key=lambda r: (-r["score"], r["price"] if r["price"] is not None else math.inf, r["name"]))
    return rows[:3]


def _school_summary(area):
    """The UDISE+ school profile of the pincode at the area's centre (Delhi only; a profile, never a quality score)."""
    try:
        import school_profiles as sp
        boundaries, profiles = sp.load_boundaries(), sp.load_profiles()
        pincode = sp.pincode_at(boundaries, area["lat"], area["lng"]) if boundaries else None
        row = sp.find_pincode(profiles, pincode) if pincode and profiles else None
        if not row:
            return None
        v = sp.view(row)
        ptr = v["indicators"]["pupil_teacher_ratio"]["text"]
        return dict(pincode=pincode, schools=v["schools"], private_pct=round(v["private_pct"]), pupil_teacher_ratio=ptr["median"] if ptr else None)
    except Exception:  # the Localytics school data is optional here
        return None


def _reasons(a, mode, budget, place):
    out = []
    unit = "/month" if mode == "rent" else ""
    if a["price"]:
        basis = ", locality medians from Aug 2020" if a["price"]["open_data"] else (f", about {round(a['price']['listings'])} listings per building" if a["price"].get("listings") else "")
        out.append(f"median {mode} {_inr(a['price']['median'])}{unit} (range {_inr(a['price']['low'])} to {_inr(a['price']['high'])}{basis})")
        if budget and a["price"]["median"] <= budget:
            out.append(f"{round(100 * (1 - a['price']['median'] / budget))}% under your budget")
    if a["pm25"].get("known"):
        out.append(f"PM2.5 about {round(a['pm25']['median'])} (known for {a['pm25']['known']} of {a['n']} buildings)")
    else:
        out.append("no PM2.5 reading nearby")
    if a["commute_km"] is not None:
        out.append(f"{a['commute_km']} km straight-line to {place['name']}")
    if a["nearest"].get("metro") is not None:
        out.append(f"metro or rail about {a['nearest']['metro']} m")
    return out


def _inr(v):
    if v >= 1e7:
        return f"₹{v / 1e7:.2f} Cr"
    if v >= 1e5:
        return f"₹{v / 1e5:.1f} L"
    return f"₹{round(v / 1000)}k"


def _warnings(data, criteria, extra, matched, picked, unlabeled, place):
    out = []
    if any(a["city"] == "Delhi" for a in picked) and criteria["mode"] == "rent":
        out.append("Delhi rents are locality medians from August 2020, so today's rents are likely higher; Gurugram rents are current Magicbricks listing medians.")
    if criteria["mode"] == "buy" and extra["city"] == "both":
        out.append("Delhi has no sale prices in this data, so only Gurugram appears in Buy results.")
    ui_air = data["doc"].get("ui", {}).get("air", {})
    out.append("PM2.5 is the nearest monitor's reading from one cached snapshot" + (f" ({ui_air['fetched'][:10]})" if ui_air.get("fetched") else "") +
               ", indicative only, not an official AQI. Buildings with no monitor within 5 km have no reading and are not treated as clean.")
    if unlabeled:
        out.append(f"{unlabeled} matching buildings have no locality name, so they are on the map but not grouped into an area.")
    if place:
        out.append("Commute is straight-line distance, not travel time.")
        if criteria.get("commute") and extra["city"] == "both":
            for city in ("Delhi", "Gurugram"):
                if not any(s.get("city_label") == city for s in matched):
                    out.append(f"No {city} building matches within {criteria['commute']['km']:g} km of {place['name']}, so only the other city is listed.")
    return out


def diagnose_empty(brief, path=DATA):
    """Which single constraint, when dropped, brings results back: tells the advisor what to ask the user about."""
    out = {}
    for drop in ("budget_max", "max_commute_km", "must_be_near", "bhk"):
        if not brief.get(drop):
            continue
        looser = {k: v for k, v in brief.items() if k != drop}
        if drop == "bhk":
            looser["bhk"] = [1, 2, 3, 4, 5]
        try:
            criteria, extra = normalise(looser)
            place = resolve_place(load(path), extra["workplace"]) if extra["workplace"] else None
            if place and place["status"] == "found" and extra["max_commute_km"]:
                criteria["commute"] = dict(lat=place["lat"], lng=place["lng"], km=float(extra["max_commute_km"]))
            n = sum(1 for s in load(path)["societies"] if state(s, criteria) == "match")
        except BriefError:
            continue
        out[drop] = n
    lowest = None
    if brief.get("budget_max"):
        try:
            loose, _ = normalise({k: v for k, v in brief.items() if k != "budget_max"})
            prices = [p["value"] for s in load(path)["societies"] if state(s, loose) == "match" for p in [price_for(s, loose["mode"], loose["bhk"])] if p]
            lowest = min(prices) if prices else None
        except BriefError:
            pass
    return dict(matches_if_dropped=out, cheapest_available=lowest)


def for_model(result, rows=5):
    """A compact copy of a search result for the language model: numbers it may quote, without the id lists."""
    areas = []
    for a in result["areas"]:
        areas.append({k: v for k, v in a.items() if k not in ("ids", "lat", "lng", "radius_m", "parts")}
                     | dict(buildings=[{k: v for k, v in b.items() if k not in ("id", "lat", "lng")} for b in a["buildings"][:rows]]))
    return dict(counts=result["counts"], areas=areas, workplace=result.get("workplace"), warnings=result["warnings"], why_empty=result.get("why_empty"))
