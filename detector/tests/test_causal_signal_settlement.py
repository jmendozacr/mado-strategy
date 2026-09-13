"""Finding #2 (human review, iteration 2): exhaustive audit of
`entries.model1._purge_signals`/`_track_anchor` for future-candle reads, and
the chosen fix (Option A -- REQ-CAUSAL-02/07/11).

Audit conclusion (see the session report's Section D for the full trace):
for a signal whose own event index is `retest_index = K`, NONE of
`origin_index`, `anchor_index`, `direction`, `confirmation_type`,
`entry_type`, `entry_price`, `retest_index`, `signal_id` can be changed by
any candle strictly after K -- each is assigned exactly once, at or before
K, and never reassigned. `status`/`confirmation_index` are the ONLY fields
that CAN change from candles after K (a later breach or close-beyond-open
the scan happens to reach) -- and while neither field is read downstream
(`backtest.population._population_cuts` gates only on
`retest_index is None`; `_build_candidate` never reads `status`), leaving
them un-normalized still means the raw `Model1Signal` object itself is not
byte-identical across growing prefixes, which is what I1 (REQ-CAUSAL-01)
demands of the causal generator's own output.

`causal.signals._causally_settle` (Option A) closes this by re-running
`_track_anchor` on `candles[:K+1]` -- the causal boundary for the signal's
own event -- once `K` is known, pinning `status`/`confirmation_index` to the
one value obtainable from data available no later than K.
"""

from datetime import datetime, timedelta

from core.candle import Candle, OHLCSeries
from core.config import Model1Config
from core.results import DetectionStatus
from causal.signals import causal_purge_engulf_signals
from primitives.crt_range import CRTRange

_CRT_RANGE = CRTRange(
    model="2-candle", high=1.1000, low=1.0950, start_index=0, end_index=1,
    resolution="true_break", resolved_at_index=1,
)

# Bullish purge_engulf: candle1 purges the range's low (anchor); candle2
# confirms; candle3 sets retest_index=3 WITHOUT resolving immediately
# (close does not close beyond retest_open on the same candle); candle4 is
# an inert filler (neither breaches nor confirms) so a prefix ending here
# (n=5) can only return PENDING; candle5 (only visible at n=6) closes
# beyond retest_open, resolving CONFIRMED -- a genuine status change caused
# purely by a candle strictly after K=3.
_SPECS = [
    (1.0980, 1.1000, 1.0950, 1.0990),  # 0 -- range seed
    (1.0960, 1.0970, 1.0930, 1.0955),  # 1 -- anchor (purges low)
    (1.0958, 1.0985, 1.0955, 1.0980),  # 2 -- confirms
    (1.0965, 1.0968, 1.0958, 1.0962),  # 3 -- retest_index=3, does not resolve here
    (1.0960, 1.0966, 1.0955, 1.0961),  # 4 -- inert filler
    (1.0962, 1.0990, 1.0960, 1.0980),  # 5 -- only visible at n=6: closes > retest_open -> CONFIRMED
]


def _series(n: int) -> OHLCSeries:
    start = datetime(2026, 1, 1, 0, 0)
    candles = tuple(
        Candle(timestamp=start + timedelta(hours=i), open=o, high=h, low=l, close=c)
        for i, (o, h, l, c) in enumerate(_SPECS[:n])
    )
    return OHLCSeries(candles=candles, instrument="EURUSD", timeframe="1H")


def _signal_at(n: int):
    signals = causal_purge_engulf_signals(_series(n), [_CRT_RANGE], Model1Config())
    matches = [s for s in signals if s.anchor_index == 1 and s.direction == "bullish"]
    assert len(matches) == 1, matches
    return matches[0]


def test_fixture_sanity_raw_track_anchor_status_changes_after_k():
    """Sanity check on the RAW legacy helper (unmodified, used exactly as
    `_purge_signals` calls it) -- proves candles after K=3 really do change
    `status`/`confirmation_index` when nothing intervenes, so the invariance
    test below is not vacuous."""
    from entries.model1 import _track_anchor

    raw5 = _track_anchor(_series(5).candles, 1, "bullish", 1.0950, "purge_engulf", Model1Config(), 0)
    raw6 = _track_anchor(_series(6).candles, 1, "bullish", 1.0950, "purge_engulf", Model1Config(), 0)
    assert raw5.retest_index == raw6.retest_index == 3
    assert raw5.status == DetectionStatus.PENDING and raw5.confirmation_index == 4
    assert raw6.status == DetectionStatus.CONFIRMED and raw6.confirmation_index == 5
    assert raw5 != raw6  # the raw helper's own output is NOT prefix-invariant


def test_causal_signal_settlement_is_prefix_invariant_across_growing_n():
    """RED (pre-fix): the CAUSAL-EMITTED signal for this group must be
    byte-identical whether the causal generator currently has 5 or 6 LTF
    candles available -- I1 (REQ-CAUSAL-01) applies to the emitted
    `Model1Signal` itself, not only to the subset of fields Stage6 happens
    to read."""
    signal_at_5 = _signal_at(5)
    signal_at_6 = _signal_at(6)

    assert signal_at_5 == signal_at_6
    assert signal_at_5.retest_index == 3
    assert signal_at_5.status == DetectionStatus.PENDING
    assert signal_at_5.confirmation_index == 3  # settled at K, not at whatever window_end N happened to give
