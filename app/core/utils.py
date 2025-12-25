"""工具函数"""

from datetime import datetime


def format_datetime(dt: datetime | None) -> str | None:
    """
    将 datetime 对象格式化为字符串

    Args:
        dt: datetime 对象或 None

    Returns:
        格式化后的时间字符串（格式：2025-12-12 12:00:00）或 None
    """
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")
