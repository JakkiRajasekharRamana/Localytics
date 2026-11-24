"""Build per-pincode school profiles from the UDISE+ Delhi 2024-25 open-data CSVs.
Run: python scripts/build_school_profiles.py /path/to/folder
The folder needs 07_prof1.csv, 07_fac.csv, 07_tch.csv and 07_enr1.csv (see README).
Profiles describe schools by postal pincode: ranges and mixes, not a quality score.
"""

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "schools"
MIN_SCHOOLS_FOR_RANGE = 5
MAX_RATIO = 100  # pupil-teacher and students-per-classroom above this are treated as data errors

MANAGEMENT = {
    "1": "dept_education",
    "3": "local_body",
    "4": "aided",
    "7": "aided",
    "5": "private_unaided",
    "92": "central",
    "93": "central",
    "94": "central",
    "95": "central",
    "96": "central",
    "101": "central",
}
STAGE = {
    "1": "primary",
    "2": "upper_primary",
    "4": "upper_primary",
    "6": "secondary",
    "7": "secondary",
    "8": "secondary",
    "3": "higher_secondary",
    "5": "higher_secondary",
    "10": "higher_secondary",
    "11": "higher_secondary",
    "12": "pre_primary",
}
BOARD = {"1": "cbse", "2": "state_board", "3": "icse"}
MEDIUM = {"19": "english", "4": "hindi", "18": "urdu"}
INDICATORS = (
    "pupil_teacher_ratio",
    "students_per_classroom",
    "pct_postgraduate_teachers",
    "pct_computer_trained_teachers",
    "pct_regular_teachers",
)
SHARES = ("has_smart_board", "has_special_educator")


def read(folder, name):
    with (Path(folder) / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def number(value):
    return int(float(value or 0))


def percentile(sorted_values, p):
    position = p * (len(sorted_values) - 1)
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (position - low)


def distribution(values, digits):
    values = sorted(values)
    if len(values) < MIN_SCHOOLS_FOR_RANGE:
        return dict(n=len(values), p10=None, median=None, p90=None)
    return dict(
        n=len(values),
        **{
            k: round(percentile(values, p), digits)
            for k, p in (("p10", 0.1), ("median", 0.5), ("p90", 0.9))
        },
    )


def school_records(folder):
    """One flat record per school, joined on pseudocode. Raises if a file does not cover every school."""
    profile = {r["pseudocode"]: r for r in read(folder, "07_prof1.csv")}
    facilities = {r["pseudocode"]: r for r in read(folder, "07_fac.csv")}
    teachers = {r["pseudocode"]: r for r in read(folder, "07_tch.csv")}
    students = defaultdict(int)
    for r in read(folder, "07_enr1.csv"):
        if r["item_group"] == "1":  # social-category rows partition all enrolled students
            students[r["pseudocode"]] += sum(
                number(v) for k, v in r.items() if k not in ("pseudocode", "item_group", "item_id")
            )
    for name, table in (
        ("07_fac.csv", facilities),
        ("07_tch.csv", teachers),
        ("07_enr1.csv", students),
    ):
        missing = set(profile) - set(table)
        if missing:
            raise ValueError(f"{name} has no rows for {len(missing)} schools in 07_prof1.csv")
    records = []
    for pid, p in profile.items():
        f, t, s = facilities[pid], teachers[pid], students[pid]
        board = p["aff_board_sec"] if p["aff_board_sec"] != "0" else p["aff_board_hsec"]
        classrooms = sum(
            number(f[k])
            for k in (
                "classrooms_in_good_condition",
                "classrooms_needs_minor_repair",
                "classrooms_needs_major_repair",
            )
        )
        teacher_count = number(t["total_tch"])
        record = dict(
            pincode=p["pincode"].strip(),
            students=s,
            teachers=teacher_count,
            management=MANAGEMENT.get(p["managment"], "other"),
            stage=STAGE.get(p["school_category"], "other"),
            board="no_secondary" if board == "0" else BOARD.get(board, "other"),
            medium=MEDIUM.get(p["medium_instr1"], "other"),
            has_smart_board=number(f["digiboard"]) + number(f["smart_class_tv_tot"]) > 0,
            has_special_educator=f["spl_educator_yn"] == "1",
            indicators={},
        )
        ind = record["indicators"]
        if teacher_count:
            if s / teacher_count <= MAX_RATIO:
                ind["pupil_teacher_ratio"] = s / teacher_count
            ind["pct_postgraduate_teachers"] = (
                100 * number(t["post_graduate_and_above"]) / teacher_count
            )
            ind["pct_computer_trained_teachers"] = 100 * number(t["trained_comp"]) / teacher_count
            ind["pct_regular_teachers"] = 100 * number(t["regular"]) / teacher_count
        if classrooms and s / classrooms <= MAX_RATIO:
            ind["students_per_classroom"] = s / classrooms
        records.append(record)
    return records


def profile_of(schools):
    counts = lambda key: dict(Counter(r[key] for r in schools).most_common())
    return dict(
        schools=len(schools),
        students=sum(r["students"] for r in schools),
        teachers=sum(r["teachers"] for r in schools),
        management=counts("management"),
        stage=counts("stage"),
        board=counts("board"),
        medium=counts("medium"),
        indicators={
            k: distribution(
                [r["indicators"][k] for r in schools if k in r["indicators"]],
                1 if k in ("pupil_teacher_ratio", "students_per_classroom") else 0,
            )
            for k in INDICATORS
        },
        shares={k: dict(n=len(schools), yes=sum(1 for r in schools if r[k])) for k in SHARES},
    )


def build(folder):
    records = school_records(folder)
    by_pincode = defaultdict(list)
    unassigned = 0
    for r in records:
        if r["pincode"]:
            by_pincode[r["pincode"]].append(r)
        else:
            unassigned += 1
    pincodes = [dict(pincode=k, **profile_of(v)) for k, v in sorted(by_pincode.items())]
    return dict(
        metadata=dict(
            source="UDISE+ Delhi 2024-25 school data (Ministry of Education), as republished on OpenCity "
            "(public domain): https://data.opencity.in/dataset/delhi-udise-2024-25",
            generated_at_utc=datetime.now(timezone.utc).isoformat(),
            schools_total=len(records),
            schools_without_pincode=unassigned,
            pincode_count=len(pincodes),
            min_schools_for_range=MIN_SCHOOLS_FOR_RANGE,
            rules=[
                f"Ranges are 10th, 50th and 90th percentiles across schools in the pincode; shown only with at least {MIN_SCHOOLS_FOR_RANGE} schools.",
                f"Pupil-teacher ratio and students per classroom above {MAX_RATIO} are treated as data errors and excluded; schools with zero teachers are excluded from teacher-based indicators.",
                "Students are the sum of social-category enrolment rows; classrooms are the sum of the good, minor-repair and major-repair counts because total_class_rooms is empty in the source.",
                "Smart board means any digital board or smart classroom reported; special educator means a dedicated one on staff.",
                "Board is the secondary-section board, or the higher-secondary board if there is no secondary board; no_secondary means neither was reported. Medium is the school's first-listed medium of instruction.",
            ],
            not_shown=[
                "Water, library, electricity, internet, handwashing, ramps and furniture: almost every school reports yes, so they do not distinguish schools.",
                "Instructional days: 12% of schools report 0, treated as missing.",
                "Any single quality score: pincode explains little of the variation between schools, so a pincode score would hide most differences.",
            ],
            limitations=[
                "Pincodes are postal areas, not the 1 km grid cells; the two are not yet linked.",
                "These are resource and staffing indicators reported by schools, not learning outcomes or quality verdicts.",
                "The source has no school names or coordinates, so schools cannot be matched to map locations.",
            ],
        ),
        delhi=profile_of(records),
        pincodes=pincodes,
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    result = build(args.folder)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "pincode_profiles.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    meta = result["metadata"]
    print(
        f"{meta['schools_total']} schools, {meta['pincode_count']} pincodes, {meta['schools_without_pincode']} without a pincode"
    )


if __name__ == "__main__":
    main()
