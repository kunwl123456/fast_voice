from datetime import datetime
from zoneinfo import ZoneInfo


def tz_now(timezone: str = "Asia/Shanghai") -> datetime:
    """返回 Asia/Shanghai 时区的当前时间"""
    return datetime.now(ZoneInfo(timezone))
