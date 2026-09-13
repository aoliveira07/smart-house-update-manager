from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def local_now(zone):
    return datetime.now(ZoneInfo(zone))


def due(now, time, last_date):
    return now.strftime("%H:%M") >= time and last_date != now.date().isoformat()


def next_time(now, time, last_date):
    hour, minute = map(int, time.split(":"))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now or last_date == now.date().isoformat():
        target += timedelta(days=1)
    return target.isoformat()
