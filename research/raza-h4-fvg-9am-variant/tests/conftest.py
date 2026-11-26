import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
DETECTOR_ROOT = REPO_ROOT / "detector"
AUDIT_ROOT = REPO_ROOT / "audit" / "2026-11-17-causal-lookahead-audit"
LPD_ROOT = REPO_ROOT / "research" / "loss-pattern-discovery"

for _path in (LAB_ROOT, DETECTOR_ROOT, AUDIT_ROOT, LPD_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import causal_intrabar as ci  # noqa: E402
from core.candle import Candle  # noqa: E402

_NY = ZoneInfo("America/New_York")
M15 = timedelta(minutes=15)


def ny_ts(y, m, d, hour_ny):
    return ci.ny_anchored_open_utc(date(y, m, d), hour_ny)


def flat_bucket(open_ts, n, base=1.1000, flat_delta=0.0005):
    """n M15 candles, each with a small symmetric high/low around `base`
    and close == open (no net movement) -- a safe "nothing happens here"
    filler, overridden candle-by-candle by callers that need specific
    OHLC shapes at specific offsets."""
    candles = []
    for i in range(n):
        candles.append(Candle(
            open_ts + i * M15, open=base, high=base + flat_delta, low=base - flat_delta, close=base,
        ))
    return candles


def override(candles, index, **kwargs):
    c = candles[index]
    fields = {"open": c.open, "high": c.high, "low": c.low, "close": c.close}
    fields.update(kwargs)
    candles[index] = Candle(c.timestamp, **fields)
    return candles
