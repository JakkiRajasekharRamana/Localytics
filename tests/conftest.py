"""Keep real cached observations intact when API tests use example records."""

import sqlite3

import pytest

import data_store


@pytest.fixture(autouse=True)
def preserve_air_cache():
    target = data_store.DB
    if not target.exists():
        yield
        return
    with sqlite3.connect(target) as db:
        saved = db.execute("SELECT query,fetched_at,payload FROM air_cache").fetchall()
    yield
    with sqlite3.connect(target) as db:
        db.execute("DELETE FROM air_cache")
        db.executemany("INSERT INTO air_cache VALUES (?,?,?)", saved)
