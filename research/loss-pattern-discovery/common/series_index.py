"""Shared, cached bisect-ready timestamp index for an OHLCSeries.

Rebuilding `[c.timestamp for c in series.candles]` on every call is O(n) per
call; at Phase-2 scale (thousands of event/control lookups against a
~587k-bar M15 series) that adds up to billions of wasted operations across
a single run. This module builds the list once per series object (keyed by
the candle tuple's identity) and reuses it for the lifetime of the process.
"""
from __future__ import annotations

from datetime import datetime

from core.candle import OHLCSeries

# Keying purely on id(series.candles) is UNSAFE: CPython reuses an object's
# id as soon as it's garbage-collected, and short-lived series (as built in
# tests, or per-control synthetic records) can collide with a freed tuple's
# old id, silently returning a stale, wrong-length timestamp list. Each
# cache entry therefore also stores a cheap fingerprint (length + first/last
# timestamp) that is checked in O(1) before trusting the cached list; a
# mismatch recomputes rather than risking a false hit. This keeps the
# intended win (a real, persistent ~587k-bar series loaded once and reused
# thousands of times) while staying correct for small, short-lived series.
_cache: dict[int, tuple[int, object, object, list[datetime]]] = {}


def timestamps_for(series: OHLCSeries) -> list[datetime]:
    key = id(series.candles)
    candles = series.candles
    n = len(candles)
    fingerprint = (n, candles[0].timestamp if n else None, candles[-1].timestamp if n else None)

    cached = _cache.get(key)
    if cached is not None and (cached[0], cached[1], cached[2]) == fingerprint:
        return cached[3]

    timestamps = [c.timestamp for c in candles]
    _cache[key] = (fingerprint[0], fingerprint[1], fingerprint[2], timestamps)
    return timestamps
