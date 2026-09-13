from datetime import datetime
from zoneinfo import ZoneInfo
from app.scheduler import due, next_time


def test_once_per_local_day():
    now = datetime(2026, 9, 12, 5, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))
    assert due(now, "05:30", None)
    assert not due(now, "05:30", "2026-09-12")
    assert not due(now, "06:00", None)
    assert next_time(now, "05:30", "2026-09-12").startswith("2026-09-13T05:30")


def test_dst_duplicate_wall_clock_does_not_duplicate_day():
    now = datetime(2026, 11, 1, 1, 30, fold=1, tzinfo=ZoneInfo("America/New_York"))
    assert not due(now, "01:30", "2026-11-01")
