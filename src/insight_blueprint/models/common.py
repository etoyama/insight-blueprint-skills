"""Values shared by the models: the timezone and the theme id pattern."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")

# Used with fullmatch. A theme id prefixes design ids and names the tree file.
THEME_ID_PATTERN = re.compile(r"[A-Z][A-Z0-9]*")


def now_jst() -> datetime:
    """Return current datetime in JST timezone."""
    return datetime.now(tz=JST)
