"""Injectable application clock."""

from datetime import date, datetime
from zoneinfo import ZoneInfo


def get_today() -> date:
    """Return today's date in the application's Europe/Kyiv timezone."""
    return datetime.now(ZoneInfo("Europe/Kyiv")).date()
