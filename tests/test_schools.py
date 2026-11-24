import csv
import json

import pytest

import school_profiles as sp
from app import app
from scripts.build_school_profiles import build, main, percentile, school_records

PROFILE = [
    "pseudocode",
    "pincode",
    "managment",
    "school_category",
    "aff_board_sec",
    "aff_board_hsec",
    "medium_instr1",
]
FAC = [
    "pseudocode",
    "classrooms_in_good_condition",
    "classrooms_needs_minor_repair",
    "classrooms_needs_major_repair",
    "digiboard",
    "smart_class_tv_tot",
    "spl_educator_yn",
]
TCH = ["pseudocode", "total_tch", "post_graduate_and_above", "trained_comp", "regular"]
ENR = ["pseudocode", "item_group", "item_id", "c1_b", "c1_g", "c2_b", "c2_g"]


def write(folder, name, fields, rows):
    with (folder / name).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def make_folder(tmp_path, n=6, pincode="110001"):
    """n schools in one pincode, one in another, one with no pincode, one with zero teachers."""
    profile, fac, tch, enr = [], [], [], []
    for i in range(1, n + 1):
        profile.append(
            dict(
                pseudocode=i,
                pincode=pincode,
                managment=5 if i % 2 else 1,
                school_category=3,
                aff_board_sec=1,
                aff_board_hsec=1,
                medium_instr1=19,
            )
        )
        fac.append(
            dict(
                pseudocode=i,
                classrooms_in_good_condition=9,
                classrooms_needs_minor_repair=1,
                classrooms_needs_major_repair=0,
                digiboard=0,
                smart_class_tv_tot=1 if i <= 2 else 0,
                spl_educator_yn=1,
            )
        )
        tch.append(
            dict(pseudocode=i, total_tch=10, post_graduate_and_above=i, trained_comp=5, regular=10)
        )
        enr.append(
            dict(pseudocode=i, item_group=1, item_id=1, c1_b=100, c1_g=100, c2_b=50, c2_g=50)
        )
    extras = [
        (100, "110002", 3, 0, 4),
        (101, "", 5, 20, 6),
        (102, "110002", 1, 20, 0),
    ]  # id, pincode, mgmt, teachers, unused
    for pid, pin, mgmt, teachers, _ in extras:
        profile.append(
            dict(
                pseudocode=pid,
                pincode=pin,
                managment=mgmt,
                school_category=2,
                aff_board_sec=0,
                aff_board_hsec=0,
                medium_instr1=4,
            )
        )
        fac.append(
            dict(
                pseudocode=pid,
                classrooms_in_good_condition=4,
                classrooms_needs_minor_repair=0,
                classrooms_needs_major_repair=0,
                digiboard=0,
                smart_class_tv_tot=0,
                spl_educator_yn=2,
            )
        )
        tch.append(
            dict(
                pseudocode=pid,
                total_tch=teachers,
                post_graduate_and_above=0,
                trained_comp=0,
                regular=teachers,
            )
        )
        enr.append(
            dict(pseudocode=pid, item_group=1, item_id=1, c1_b=500, c1_g=500, c2_b=0, c2_g=0)
        )
        enr.append(
            dict(pseudocode=pid, item_group=2, item_id=5, c1_b=999, c1_g=999, c2_b=0, c2_g=0)
        )  # ignored rows
    for name, fields, rows in (
        ("07_prof1.csv", PROFILE, profile),
        ("07_fac.csv", FAC, fac),
        ("07_tch.csv", TCH, tch),
        ("07_enr1.csv", ENR, enr),
    ):
        write(tmp_path, name, fields, rows)
    return tmp_path


def test_percentile():
    assert percentile([1, 2, 3, 4, 5], 0.5) == 3
    assert percentile([0, 10], 0.1) == 1


def test_records_join_and_rules(tmp_path):
    records = {
        r["pincode"] + str(i): r for i, r in enumerate(school_records(make_folder(tmp_path)))
    }
    first = records["1100010"]
    assert first["students"] == 300 and first["teachers"] == 10
    assert first["indicators"]["pupil_teacher_ratio"] == 30
    assert (
        first["indicators"]["students_per_classroom"] == 30
    )  # 300 students / (9 + 1 + 0) classrooms
    assert (
        first["management"] == "private_unaided"
        and first["board"] == "cbse"
        and first["medium"] == "english"
    )
    zero_teachers = [r for r in records.values() if r["teachers"] == 0][0]
    assert "pupil_teacher_ratio" not in zero_teachers["indicators"]
    assert (
        "students_per_classroom" not in zero_teachers["indicators"]
    )  # 1000 students / 4 classrooms exceeds the cap
    assert zero_teachers["board"] == "no_secondary" and zero_teachers["stage"] == "upper_primary"
    assert zero_teachers["management"] == "local_body"
    assert any(r["pincode"] == "" for r in records.values())


def test_implausible_ratio_excluded(tmp_path):
    folder = make_folder(tmp_path)
    rows = list(csv.DictReader((folder / "07_enr1.csv").open(encoding="utf-8")))
    rows[0]["c1_b"] = 5000  # school 1: 5100 + 100 + 100 students / 10 teachers > 100
    write(folder, "07_enr1.csv", ENR, rows)
    records = school_records(folder)
    assert "pupil_teacher_ratio" not in records[0]["indicators"]


def test_missing_school_in_other_file_raises(tmp_path):
    folder = make_folder(tmp_path)
    rows = list(csv.DictReader((folder / "07_tch.csv").open(encoding="utf-8")))[1:]
    write(folder, "07_tch.csv", TCH, rows)
    with pytest.raises(ValueError, match="07_tch.csv"):
        school_records(folder)


def test_build_profiles(tmp_path):
    result = build(make_folder(tmp_path))
    meta = result["metadata"]
    assert (meta["schools_total"], meta["schools_without_pincode"], meta["pincode_count"]) == (
        9,
        1,
        2,
    )
    big = next(p for p in result["pincodes"] if p["pincode"] == "110001")
    assert big["schools"] == 6 and big["management"] == {"private_unaided": 3, "dept_education": 3}
    assert big["indicators"]["pupil_teacher_ratio"]["median"] == 30
    assert big["indicators"]["pct_postgraduate_teachers"]["n"] == 6
    assert big["shares"]["has_smart_board"] == dict(n=6, yes=2)
    small = next(p for p in result["pincodes"] if p["pincode"] == "110002")
    assert small["schools"] == 2
    assert (
        small["indicators"]["pupil_teacher_ratio"]["median"] is None
    )  # fewer than 5 schools: no range
    assert (
        small["indicators"]["pupil_teacher_ratio"]["n"] == 1
    )  # the zero-teacher school is excluded
    assert result["delhi"]["schools"] == 9


def test_main_writes_json(tmp_path):
    out = tmp_path / "out"
    main([str(make_folder(tmp_path)), "--output", str(out)])
    data = json.loads((out / "pincode_profiles.json").read_text(encoding="utf-8"))
    assert data["metadata"]["schools_total"] == 9


def test_view_formatting():
    stats = dict(n=10, p10=14.84, median=31.26, p90=49.0)
    assert sp.indicator_text(stats, 1) == dict(median="31.3", range="14.8–49.0", sort=31.26)
    assert sp.indicator_text(dict(n=2, p10=None, median=None, p90=None), 1) is None
    assert [
        m["label"] for m in sp.mix({"local_body": 1, "private_unaided": 3}, sp.MANAGEMENT, 4)
    ] == ["Local body", "Private unaided"]
    assert (
        sp.valid_pincode("110094")
        and not sp.valid_pincode("11009")
        and not sp.valid_pincode("../etc")
    )


@pytest.fixture
def bundled():
    data = sp.load_profiles()
    if data is None:
        pytest.skip("schools/pincode_profiles.json has not been built")
    return data


def test_bundled_profiles_consistent(bundled):
    meta = bundled["metadata"]
    assert (
        sum(p["schools"] for p in bundled["pincodes"]) + meta["schools_without_pincode"]
        == meta["schools_total"]
    )
    assert bundled["delhi"]["schools"] == meta["schools_total"]
    for p in bundled["pincodes"]:
        assert sum(p["management"].values()) == p["schools"]
        assert sum(p["stage"].values()) == p["schools"]
        for stats in p["indicators"].values():
            assert (stats["median"] is None) == (
                p["schools"] < meta["min_schools_for_range"]
                or stats["n"] < meta["min_schools_for_range"]
            )


def test_routes(bundled):
    client = app.test_client()
    page = client.get("/schools")
    assert page.status_code == 200
    assert b"No single quality score" in page.data
    assert b"/schools/110094" in page.data
    detail = client.get("/schools/110094")
    assert detail.status_code == 200
    for text in [
        b"Pincode 110094",
        b"Who runs the schools",
        b"Pupil-teacher ratio",
        b"Delhi overall",
        b"profile, not a score",
    ]:
        assert text in detail.data
    for bad in ["999999", "abc", "11009"]:
        response = client.get("/schools/" + bad)
        assert response.status_code == 404
        assert b"No school profile" in response.data


def test_routes_without_data(monkeypatch):
    monkeypatch.setattr(sp, "load_profiles", lambda: None)
    client = app.test_client()
    for path in ["/schools", "/schools/110094"]:
        assert b"School profile data is missing" in client.get(path).data


def test_nav_links():
    client = app.test_client()
    for path in ["/", "/air-quality", "/connectivity"]:
        assert b'href="/schools"' in client.get(path).data
