import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from observations import freshest_only  # noqa: E402

NOW = datetime(2026, 11, 24, 18, 0, tzinfo=timezone.utc)


def mon(name, hours_ago):
    return dict(name=name, pm=100.0, stamp=NOW - timedelta(hours=hours_ago) if hours_ago is not None else None)


def test_old_cached_snapshot_is_dropped_next_to_a_fresh_one():
    kept = freshest_only([mon("fresh Gurugram", 1), mon("fresh Delhi", 2), mon("Delhi from 14 days ago", 14 * 24)])
    assert [m["name"] for m in kept] == ["fresh Gurugram", "fresh Delhi"]


def test_one_snapshot_only_means_nothing_is_dropped():
    old = [mon("a", 14 * 24), mon("b", 14 * 24 + 3)]
    assert freshest_only(old) == old


def test_window_edge_and_unstamped_readings():
    assert len(freshest_only([mon("new", 0), mon("edge", 48)])) == 2
    assert [m["name"] for m in freshest_only([mon("new", 0), mon("none", None)])] == ["new"]
    assert freshest_only([mon("none", None)]) == [mon("none", None)]
