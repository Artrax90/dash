import os
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Union

# Common UTC offsets fallback map when zoneinfo system database is not present
TZ_OFFSET_MAP = {
    "europe/moscow": 3,
    "moscow": 3,
    "msk": 3,
    "europe/kaliningrad": 2,
    "kaliningrad": 2,
    "europe/samara": 4,
    "samara": 4,
    "asia/yekaterinburg": 5,
    "asia/ekaterinburg": 5,
    "yekaterinburg": 5,
    "ekaterinburg": 5,
    "asia/omsk": 6,
    "omsk": 6,
    "asia/krasnoyarsk": 7,
    "krasnoyarsk": 7,
    "asia/novosibirsk": 7,
    "novosibirsk": 7,
    "asia/irkutsk": 8,
    "irkutsk": 8,
    "asia/yakutsk": 9,
    "yakutsk": 9,
    "asia/vladivostok": 10,
    "vladivostok": 10,
    "asia/magadan": 11,
    "magadan": 11,
    "asia/kamchatka": 12,
    "kamchatka": 12,
    "utc": 0,
    "gmt": 0,
    "europe/berlin": 1,
    "berlin": 1,
    "europe/paris": 1,
    "europe/london": 0,
    "america/new_york": -5,
}

def resolve_tz_name(tz_name: Optional[str] = None) -> str:
    """Resolve the active timezone name from argument, env, or default (Europe/Moscow)."""
    if tz_name and tz_name.strip():
        return tz_name.strip()
    return os.getenv("TZ") or os.getenv("TIMEZONE") or "Europe/Moscow"

def get_tzinfo(tz_name: Optional[str] = None):
    """
    Get a valid tzinfo instance for the given timezone name.
    Attempts zoneinfo first, then falls back to fixed offset timezone.
    """
    name = resolve_tz_name(tz_name)
    
    # 1. Try standard zoneinfo
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        pass
        
    # 2. Match known offset
    key = name.lower().replace(" ", "")
    if key in TZ_OFFSET_MAP:
        hours = TZ_OFFSET_MAP[key]
        return timezone(timedelta(hours=hours))
        
    # 3. Try to parse offset from string like 'UTC+3' or '+03:00'
    if "+" in key or "-" in key:
        import re
        m = re.search(r'([+-])(\d{1,2})(?::?(\d{2}))?', key)
        if m:
            sign = 1 if m.group(1) == "+" else -1
            hrs = int(m.group(2))
            mins = int(m.group(3) or 0)
            return timezone(sign * timedelta(hours=hrs, minutes=mins))
            
    # Default to Europe/Moscow (UTC+3)
    return timezone(timedelta(hours=3))

def get_local_now(tz_name: Optional[str] = None) -> datetime:
    """Return the current datetime localized to target timezone."""
    tz = get_tzinfo(tz_name)
    return datetime.now(timezone.utc).astimezone(tz)

def to_local_datetime(dt: datetime, tz_name: Optional[str] = None) -> datetime:
    """Convert any datetime (aware or naive assumed UTC) to target timezone."""
    if dt is None:
        return get_local_now(tz_name)
    tz = get_tzinfo(tz_name)
    if dt.tzinfo is None:
        # Assume naive datetime from database is UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)
