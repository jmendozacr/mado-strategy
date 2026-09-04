"""NY Kill Zone timestamp classification (REQ-29, REQ-36). Relocated
verbatim from `cli._in_ny_kill_zone` so `backtest` can reuse it without
importing `cli` — layers run the other way (REQ-52.1)."""

from datetime import datetime
from zoneinfo import ZoneInfo

from core.config import KillZoneConfig

_UTC = ZoneInfo("UTC")
_NY = ZoneInfo("America/New_York")


def in_ny_kill_zone(timestamp: datetime, config: KillZoneConfig) -> bool:
    """New REQ-29: candle timestamps are UTC wall-clock (verified against
    real broker data — no further broker offset). Converts via real
    America/New_York tz rules, not a fixed UTC offset, so the boundary
    correctly shifts between EST and EDT.
    """
    local = timestamp.replace(tzinfo=_UTC).astimezone(_NY)
    return config.ny_start_hour <= local.hour < config.ny_end_hour
