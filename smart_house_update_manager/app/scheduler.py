from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def local_now(zone):
    return datetime.now(ZoneInfo(zone))


def due(now, time, last_date):
    return now.strftime("%H:%M") >= time and last_date != now.date().isoformat()


def bootstrap_date(now, time, last_date):
    """Establish a late-start baseline without replaying a missed slot."""
    if last_date is not None:
        return last_date
    return now.date().isoformat() if now.strftime("%H:%M") >= time else None


def next_time(now, time, last_date):
    hour, minute = map(int, time.split(":"))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now or last_date == now.date().isoformat():
        target += timedelta(days=1)
    return target.isoformat()
