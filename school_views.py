"""Flask views for per-pincode school profiles and the map-click lookup."""

from flask import Blueprint, render_template, request

import school_profiles as sp
from geography import coordinates

bp = Blueprint("schools", __name__)


@bp.route("/schools")
def index():
    data = sp.load_profiles()
    if data is None:
        return render_template("schools.html", missing=True, detail=None)
    return render_template(
        "schools.html",
        missing=False,
        detail=None,
        meta=data["metadata"],
        delhi=sp.view(data["delhi"]),
        rows=sp.pincode_views(data),
        sp=sp,
    )


@bp.route("/schools/lookup")
def lookup():
    """HTML fragment for a map sidebar: the school profile of the pincode containing a point."""
    try:
        lat, lon = coordinates(request.args["lat"], request.args["lon"])
    except (KeyError, ValueError):
        return render_template("school_snippet.html", status="invalid"), 400
    data, boundaries = sp.load_profiles(), sp.load_boundaries()
    if data is None or boundaries is None:
        return render_template("school_snippet.html", status="missing")
    pincode = sp.pincode_at(boundaries, lat, lon)
    if pincode is None:
        return render_template("school_snippet.html", status="outside")
    profile = sp.find_pincode(data, pincode)
    if profile is None:
        return render_template("school_snippet.html", status="no_schools", pincode=pincode)
    return render_template(
        "school_snippet.html",
        status="ok",
        sp=sp,
        detail=dict(pincode=pincode, **sp.view(profile)),
        delhi=sp.view(data["delhi"]),
    )


@bp.route("/schools/<pincode>")
def detail(pincode):
    data = sp.load_profiles()
    if data is None:
        return render_template("schools.html", missing=True, detail=None)
    profile = sp.find_pincode(data, pincode) if sp.valid_pincode(pincode) else None
    if profile is None:
        return (
            render_template(
                "schools.html", missing=False, detail=None, not_found=pincode, meta=data["metadata"]
            ),
            404,
        )
    return render_template(
        "schools.html",
        missing=False,
        detail=dict(pincode=pincode, **sp.view(profile)),
        meta=data["metadata"],
        delhi=sp.view(data["delhi"]),
        sp=sp,
        on_map=sp.has_boundary(pincode),
    )


def register(app):
    app.register_blueprint(bp)
