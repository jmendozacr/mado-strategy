"""D1 regression (spec.md Section A, leakage channel B1 — "anchor scan
unconditioned on range resolution"): `entries.model1._purge_signals` scans
for the LTF anchor within `(crt_range.start_index, crt_range.resolved_at_index]`,
but nothing conditions the anchor's own *retest* event (found later, inside
`_track_anchor`) on having occurred no later than `resolved_at_index` — so a
signal's own confirming event can precede the existence of the very CRT
range that produced it.

Fixture verified on current, real, committed code (synthetic-only, seed=2
of a fixed generator): a 6-candle series where the range starting at index
1 resolves at index 5, yet the anchor it produces (index 2, bearish)
confirms and retests at index 4 — one candle BEFORE its own source range
resolves.
"""

from datetime import datetime, timedelta

from core.candle import Candle, OHLCSeries
from core.config import Model1Config
from causal.ranges import causal_crt_ranges
from causal.signals import causal_purge_engulf_signals, r_strict_admissible
from entries.model1 import _purge_signals
from primitives.crt_range import detect_crt_ranges

_SPECS = [
    (1.1018, 1.1056, 1.1015, 1.1054),  # 0
    (1.1067, 1.1113, 1.1055, 1.1086),  # 1 -- range start=1: H=1.1113 L=1.1055, resolves true_break @5
    (1.1091, 1.1122, 1.1084, 1.1099),  # 2 -- anchor: purges range@1's high (1.1113? no -- purges range@1's low via bearish High-purge path)
    (1.1096, 1.1125, 1.1048, 1.1088),  # 3
    (1.1106, 1.1127, 1.1095, 1.1109),  # 4 -- retest_index=4: confirms+retests HERE
    (1.1091, 1.1109, 1.1040, 1.1053),  # 5 -- the SOURCE range only resolves on THIS candle
]


def _series(n: int = 6) -> OHLCSeries:
    start = datetime(2026, 1, 1, 12, 0)
    candles = tuple(
        Candle(timestamp=start + timedelta(hours=i), open=o, high=h, low=l, close=c)
        for i, (o, h, l, c) in enumerate(_SPECS[:n])
    )
    return OHLCSeries(candles=candles, instrument="EURUSD", timeframe="1H")


def test_legacy_reproduces_b1_retest_precedes_own_range_resolution():
    """Historical evidence only (LEGACY CAUSALITY FAILURE — KNOWN — NOT
    ACCEPTABLE FOR NEW LINE-B CAUSAL PATH, REQ-CAUSAL-21) — reproduces B1
    on the real, current, unmodified legacy pipeline."""
    series = _series()
    ranges = detect_crt_ranges(series)
    source_range = next(r for r in ranges if r.start_index == 1)
    assert source_range.resolved_at_index == 5

    signals = _purge_signals(series.candles, source_range, Model1Config())
    bearish = next(s for s in signals if s.direction == "bearish" and s.anchor_index == 2)

    assert bearish.retest_index == 4
    assert bearish.retest_index < source_range.resolved_at_index  # B1: the leak, reproduced


def test_causal_path_never_emits_a_signal_whose_source_fails_r_strict():
    """Fix: the causal generator only ever selects a source range that is
    R-strict-admissible relative to the signal's own event index — so no
    causally-emitted signal can ever exhibit B1's ordering violation."""
    series = _series()
    causal_ranges = causal_crt_ranges(series)
    causal_signals = causal_purge_engulf_signals(series, causal_ranges, Model1Config())

    # Sanity: the causally-inadmissible range from the legacy reproduction
    # above must not be usable as this anchor's source in the causal path.
    for signal in causal_signals:
        if signal.retest_index is None:
            continue
        source = next(r for r in causal_ranges if r.start_index == signal.origin_index)
        assert r_strict_admissible(source, signal.retest_index)
        assert source.resolved_at_index <= signal.retest_index - 1

    # The specific B1 anchor/direction (2, bearish) must either be absent
    # (no admissible source ever existed for it) or, if present, its
    # selected source is NOT the range that resolves too late (start=1).
    bearish_causal = [s for s in causal_signals if s.anchor_index == 2 and s.direction == "bearish"]
    for s in bearish_causal:
        assert s.origin_index != 1
