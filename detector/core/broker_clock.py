from datetime import datetime, timedelta


def is_london_crt_h4(ts: datetime) -> bool:
    """H4 candle opening at 01:00 broker clock — the 1 AM CRT [charter-8, 00:01:41]."""
    return ts.hour == 1


def is_asia_range_h4(ts: datetime) -> bool:
    """H4 candle opening at 21:00 broker clock — Asia reference range [charter-8, 00:03:16]."""
    return ts.hour == 21


def in_execution_window(ts: datetime) -> bool:
    """02:00 <= broker hour < 04:00 [charter-8, 00:12:13, 00:12:52]."""
    return 2 <= ts.hour < 4


def in_priority_subwindow(ts: datetime) -> bool:
    """03:00 <= broker hour < 04:00 — highest-probability sub-window [charter-9, 00:05:18]."""
    return ts.hour == 3


def asia_range_timestamp(london_crt_ts: datetime) -> datetime:
    """The 21:00 Asia range candle is exactly 4 broker hours before the 01:00 London CRT candle."""
    return london_crt_ts - timedelta(hours=4)
