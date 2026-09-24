"""Group 4 (REQ-CAUSAL-02/07/11): causal Model-1 purge_engulf signal
generation — `signal_id`/`origin_index` become stable once a candidate
exists and are never rewritten by a later, causally-inadmissible prefix.

The fixture below is a REAL, verified-on-current-code reproduction of B2
(spec.md Section A): a 9-candle synthetic series where, at prefix length
k=6, only the CRT range starting at index 2 (resolved_at_index=3) has been
detected, producing a `purge_engulf` signal at anchor_index=3 (bullish,
retest_index=5) with `origin_index=2`. At prefix length k=7, a SECOND range
starting at index 1 appears (resolved_at_index=6) that independently
produces the SAME (anchor_index=3, direction=bullish, retest_index=5)
signal. Legacy `_dedup`'s `min(origin_index)` rule flips the survivor's
identity from `'2-3-bullish-purge_engulf-wick'` to
`'1-3-bullish-purge_engulf-wick'` — one candle *after* the retest event
(index 5) already happened. Under R-strict (REQ-CAUSAL-07), the new range
(resolved_at_index=6) fails `resolved_at_index <= retest_index - 1 == 4`,
so it can never compete for this candidate's identity — `origin_index`
stays `2` forever, regardless of how many more candles arrive (verified
through k=9 here, and by construction for any k beyond, since a range's
own `resolved_at_index` never changes once detected, per REQ-CAUSAL-01/P1).
"""

from datetime import datetime, timedelta

from core.candle import Candle, OHLCSeries
from core.config import Model1Config
from causal.ranges import causal_crt_ranges
from causal.signals import causal_purge_engulf_signals

_D2_SPECS = [
    (1.1016, 1.1020, 1.0987, 1.0992),  # 0
    (1.1002, 1.1070, 1.0975, 1.1030),  # 1
    (1.1036, 1.1070, 1.1014, 1.1051),  # 2 -- range start=2: H=1.1070 L=1.1014, resolves true_break @3
    (1.1037, 1.1071, 1.0968, 1.1000),  # 3 -- anchor (purges range@2's low 1.1014); also range start=1 pokes here
    (1.1019, 1.1061, 1.1012, 1.1038),  # 4
    (1.1053, 1.1090, 1.1021, 1.1055),  # 5 -- confirms + retests -> retest_index=5
    (1.1066, 1.1109, 1.1049, 1.1077),  # 6 -- range start=1 (H=1.1070 L=1.0975) finally resolves true_break here
    (1.1086, 1.1112, 1.1047, 1.1088),  # 7
    (1.1103, 1.1144, 1.1094, 1.1120),  # 8
]


def _d2_series(n: int) -> OHLCSeries:
    start = datetime(2026, 1, 1, 12, 0)
    candles = tuple(
        Candle(timestamp=start + timedelta(hours=i), open=o, high=h, low=l, close=c)
        for i, (o, h, l, c) in enumerate(_D2_SPECS[:n])
    )
    return OHLCSeries(candles=candles, instrument="EURUSD", timeframe="1H")


def _signal_at(series: OHLCSeries):
    ranges = causal_crt_ranges(series)
    signals = causal_purge_engulf_signals(series, ranges, Model1Config())
    matches = [s for s in signals if s.anchor_index == 3 and s.direction == "bullish"]
    assert len(matches) == 1, matches
    return matches[0]


def test_causal_signal_identity_stable_across_growing_prefix():
    signal_at_6 = _signal_at(_d2_series(6))
    assert signal_at_6.origin_index == 2
    assert signal_at_6.signal_id == "2-3-bullish-purge_engulf-wick"
    assert signal_at_6.retest_index == 5

    for n in (7, 8, 9):
        signal_at_n = _signal_at(_d2_series(n))
        assert signal_at_n.origin_index == 2, f"origin_index flipped at n={n}"
        assert signal_at_n.signal_id == "2-3-bullish-purge_engulf-wick", f"signal_id flipped at n={n}"
        assert signal_at_n.retest_index == 5


def test_causal_signal_rejects_later_resolving_competitor():
    """The competing range (start_index=1, resolved_at_index=6) that would
    win the LEGACY min(origin_index) tie-break must never even be selected
    causally -- it fails R-strict (6 > retest_index-1 == 4)."""
    signals = causal_purge_engulf_signals(
        _d2_series(9), causal_crt_ranges(_d2_series(9)), Model1Config()
    )
    origins = {s.origin_index for s in signals if s.anchor_index == 3 and s.direction == "bullish"}
    assert origins == {2}
