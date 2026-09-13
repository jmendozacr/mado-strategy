"""Group 5 (REQ-CAUSAL-08): HTF H-A implementation. Event time
`t = ltf_series.candles[K].timestamp`; the selected HTF context is the
resolved range with the LARGEST `purge_index` among ranges whose own
`resolved_at_index` candle has fully closed by `t`, tie-break lowest
`start_index`.

The fixture is a REAL, verified-on-current-code reproduction of the design
counterexample (spec.md Section D1/B3-B4): a 7-candle HTF series where, at
6 candles, only the range starting at index 4 (resolved_at_index=5) shares
purge candle index 5. Once a 7th HTF candle is appended, a NEW range
starting at index 3 (resolved_at_index=6) ALSO claims purge candle index 5
— legacy `_purge_index_map`'s `setdefault`, iterating ranges by ascending
start_index, now assigns purge index 5 to the start=3 range instead
(start=3 is processed first once it exists), silently mutating
`take_profit`/`partial_price`/RR-eligibility for any LTF signal whose
`relevant_index` is 5 — even though the LTF event already happened at
`t = candle[5].timestamp + htf_duration` (candle 6's open), strictly BEFORE
the new range's own `resolved_at_index=6` candle has even closed.
"""

from datetime import datetime, timedelta

from core.candle import Candle, OHLCSeries
from core.pairing_table import TIMEFRAME_DURATIONS
from causal.htf import select_htf_context
from primitives.crt_range import detect_crt_ranges

_HTF_SPECS = [
    (1.1006, 1.1035, 1.0997, 1.1000),  # 0
    (1.1008, 1.1032, 1.0991, 1.0998),  # 1
    (1.0992, 1.1005, 1.0944, 1.0973),  # 2
    (1.0972, 1.1032, 1.0963, 1.1009),  # 3 -- range start=3 (H=1.1032 L=1.0963), only resolves once candle 6 exists
    (1.1013, 1.1021, 1.0992, 1.1016),  # 4 -- range start=4 (H=1.1021 L=1.0992), resolves true_break @5
    (1.0996, 1.1018, 1.0959, 1.0986),  # 5 -- purges BOTH ranges' extremes (shared purge_index=5)
    (1.1004, 1.1015, 1.0985, 1.1014),  # 6 -- future candle: resolves range start=3 as false_break @6
]

_HTF_DURATION = TIMEFRAME_DURATIONS["4H"]


def _htf_series(n: int) -> OHLCSeries:
    start = datetime(2026, 1, 1, 0, 0)
    candles = tuple(
        Candle(timestamp=start + _HTF_DURATION * i, open=o, high=h, low=l, close=c)
        for i, (o, h, l, c) in enumerate(_HTF_SPECS[:n])
    )
    return OHLCSeries(candles=candles, instrument="EURUSD", timeframe="4H")


def test_ha_selects_range_eligible_by_event_time():
    series6 = _htf_series(6)
    t = series6.candles[5].timestamp + _HTF_DURATION  # right when candle 5 closes
    ranges = detect_crt_ranges(series6)
    context = select_htf_context(series6, ranges, t)
    assert context is not None
    assert context.start_index == 4


def test_ha_ignores_not_yet_closed_htf_candle_even_when_present_in_input():
    """The exact design counterexample: adding the 7th HTF candle (whose
    OWN resolved_at candle has not fully closed by `t`) must NOT change
    H-A's selection, even though it silently flips legacy's
    `_purge_index_map` selection."""
    series7 = _htf_series(7)
    t = series7.candles[5].timestamp + _HTF_DURATION  # unchanged event time

    ranges7 = detect_crt_ranges(series7)
    assert any(r.start_index == 3 and r.resolved_at_index == 6 for r in ranges7), (
        "fixture sanity: the new range must exist once candle 6 is present"
    )

    context = select_htf_context(series7, ranges7, t)
    assert context is not None
    assert context.start_index == 4  # UNCHANGED from the 6-candle result


def test_legacy_purge_index_map_would_have_flipped_here():
    """Sanity/contrast check (not itself a causal-path assertion): proves
    this fixture really does reproduce the legacy mutation, so the
    "unchanged" assertion above is meaningful and not vacuous."""
    from alignment.htf_ltf import _purge_index_map

    series6, series7 = _htf_series(6), _htf_series(7)
    map6 = _purge_index_map(series6.candles, detect_crt_ranges(series6))
    map7 = _purge_index_map(series7.candles, detect_crt_ranges(series7))
    assert map6[5].start_index == 4
    assert map7[5].start_index == 3  # flipped purely by the future candle's presence
