"""Load per-pincode school profiles and shape them for display."""

import json
import re

from config import SCHOOL_DIR

PROFILES_PATH = SCHOOL_DIR / "pincode_profiles.json"
MANAGEMENT = [
    ("dept_education", "Dept. of Education"),
    ("local_body", "Local body"),
    ("aided", "Govt. aided"),
    ("private_unaided", "Private unaided"),
    ("central", "Central govt. (KV, JNV etc.)"),
    ("other", "Other"),
]
STAGE = [
    ("pre_primary", "Pre-primary only"),
    ("primary", "Up to primary"),
    ("upper_primary", "Up to upper primary"),
    ("secondary", "Up to secondary"),
    ("higher_secondary", "Up to higher secondary"),
    ("other", "Other"),
]
BOARD = [
    ("cbse", "CBSE"),
    ("state_board", "State board"),
    ("icse", "ICSE"),
    ("other", "Other or unclear"),
    ("no_secondary", "No secondary section"),
]
MEDIUM = [("english", "English"), ("hindi", "Hindi"), ("urdu", "Urdu"), ("other", "Other")]
INDICATORS = [
    ("pupil_teacher_ratio", "Pupil-teacher ratio", "students per teacher", 1),
    ("students_per_classroom", "Students per classroom", "students", 1),
    ("pct_postgraduate_teachers", "Teachers with a postgraduate degree", "% of teachers", 0),
    ("pct_computer_trained_teachers", "Teachers trained in computers", "% of teachers", 0),
    ("pct_regular_teachers", "Regular teachers (not contract or part-time)", "% of teachers", 0),
]
SHARES = [
    ("has_smart_board", "Schools with a smart board or smart classroom"),
    ("has_special_educator", "Schools with a dedicated special educator"),
]


BOUNDARIES_PATH = SCHOOL_DIR / "pincode_boundaries.json"
_boundaries = None


def load_boundaries():
    """Return the list of pincode boundaries, or None if the file is missing or unreadable."""
    global _boundaries
    if _boundaries is None:
        try:
            _boundaries = json.loads(BOUNDARIES_PATH.read_text(encoding="utf-8"))["pincodes"]
        except (OSError, ValueError, KeyError):
            return None
    return _boundaries


def in_ring(ring, lon, lat):
    """Ray casting: is the point inside this closed ring of [lon, lat] pairs?"""
    inside, j = False, len(ring) - 1
    for i in range(len(ring)):
        (xi, yi), (xj, yj) = ring[i], ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def in_polygon(rings, lon, lat):
    """rings[0] is the outer boundary; any further rings are holes."""
    return in_ring(rings[0], lon, lat) and not any(in_ring(hole, lon, lat) for hole in rings[1:])


def pincode_at(boundaries, lat, lon):
    """The pincode whose boundary contains the point, or None. If boundaries overlap, the smaller one wins."""
    hits = [
        b
        for b in boundaries
        if b["bbox"][0] <= lon <= b["bbox"][2]
        and b["bbox"][1] <= lat <= b["bbox"][3]
        and any(in_polygon(rings, lon, lat) for rings in b["polygons"])
    ]
    if not hits:
        return None
    return min(hits, key=lambda b: (b["bbox"][2] - b["bbox"][0]) * (b["bbox"][3] - b["bbox"][1]))[
        "pincode"
    ]


def has_boundary(pincode):
    boundaries = load_boundaries()
    return boundaries is not None and any(b["pincode"] == pincode for b in boundaries)


def load_profiles():
    """Return the profile file's contents, or None if it is missing or unreadable."""
    try:
        return json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def valid_pincode(text):
    return bool(re.fullmatch(r"\d{6}", text or ""))


def mix(counts, labels, total):
    return [
        dict(key=k, label=label, count=counts[k], pct=100 * counts[k] / total)
        for k, label in labels
        if counts.get(k)
    ]


def indicator_text(stats, digits):
    """Median and 10th-90th percentile range, or None when too few schools to show a range."""
    if stats["median"] is None:
        return None
    return dict(
        median=f"{stats['median']:.{digits}f}",
        range=f"{stats['p10']:.{digits}f}–{stats['p90']:.{digits}f}",
        sort=stats["median"],
    )


def view(profile):
    """Display-ready values for one pincode profile (or the Delhi-wide profile)."""
    total = profile["schools"]
    return dict(
        schools=total,
        students=profile["students"],
        teachers=profile["teachers"],
        private_pct=100 * profile["management"].get("private_unaided", 0) / total,
        management=mix(profile["management"], MANAGEMENT, total),
        stage=mix(profile["stage"], STAGE, total),
        board=mix(profile["board"], BOARD, total),
        medium=mix(profile["medium"], MEDIUM, total),
        indicators={
            k: dict(
                n=profile["indicators"][k]["n"],
                text=indicator_text(profile["indicators"][k], digits),
            )
            for k, _, _, digits in INDICATORS
        },
        shares={
            k: dict(
                n=profile["shares"][k]["n"],
                yes=profile["shares"][k]["yes"],
                pct=100 * profile["shares"][k]["yes"] / profile["shares"][k]["n"],
            )
            for k, _ in SHARES
        },
    )


def pincode_views(data):
    return [dict(pincode=p["pincode"], **view(p)) for p in data["pincodes"]]


def find_pincode(data, pincode):
    return next((p for p in data["pincodes"] if p["pincode"] == pincode), None)
