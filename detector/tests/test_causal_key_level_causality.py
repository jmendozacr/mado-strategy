"""Finding #1 (human review, iteration 2): HTF key-level causality leak.

Refines the reviewer's B3/B4 analogy rather than reproducing it verbatim.
`causal.generate`'s HTF range set comes from `causal.ranges.causal_crt_ranges`
(resolution-ordered), NOT legacy `detect_crt_ranges` (start-index-ordered) --
`test_purge_index_map_is_growth_stable_under_resolution_order` below proves
this makes `alignment.htf_ltf._purge_index_map`'s per-purge-index winner
STABLE as more HTF candles arrive (the literal D3/B3-B4 "N grows, the map
flips" mechanism does NOT reproduce here). The real leak is CROSS-SIGNAL, not
cross-N: two different LTF signals with different event times `t` can
legitimately require DIFFERENT HTF ranges for the SAME shared purge_index
(H-A, REQ-CAUSAL-08, ties break on lowest start_index only once a competing
range becomes causally observable at that signal's own `t`) -- but a single
`key_level_credit_map` built ONCE, before the per-signal loop, from a
GLOBAL, all-ranges-derived `purge_index_to_range` can only ever hold ONE
winner for that purge_index, so a later/earlier signal whose own correctly
H-A-selected `htf_context` is the OTHER competing range gets key-level
credit computed from extremes of a range it was never actually attributed
to.

Fixture (adapted from `test_causal_htf.py`/`test_causal_regression_d3.py`'s
own 7-candle HTF shape: two ranges -- start=4 resolving early at index 5,
start=3 resolving late at index 6 -- sharing purge candle index 5) with ONE
change: candle 5's high is raised just enough to ALSO breach range@4's
(narrower) high bound while staying inside range@3's (wider) high bound, so
the two competing ranges' breach-extreme sets genuinely differ:
range@4 -> (high=1.1030, low=1.0940); range@3 -> (low=1.0940,) only. A
KeyLevel positioned to qualify ONLY via the 1.1030 high extreme then credits
correctly for an EARLY signal (H-A selects range@4) but must NOT credit for
a LATE signal (H-A ties-break to range@3, once range@3 becomes causally
observable) -- exactly the per-signal mismatch the global map cannot
represent.
"""

from datetime import datetime, timedelta

from alignment.htf_ltf import _key_level_credit_map, _purge_index_map, _purge_wick_extremes
from backtest.population import _population_cuts
from causal.generate import generate_causal_aligned_signals
from causal.htf import select_htf_context
from causal.ranges import causal_crt_ranges
from core.candle import Candle, OHLCSeries
from core.key_level import KeyLevel
from core.pairing_table import TIMEFRAME_DURATIONS
from primitives.crt_range import first_breach_index

_HTF_DURATION = TIMEFRAME_DURATIONS["4H"]
_HTF_START = datetime(2026, 1, 1, 0, 0)

_HTF_SPECS = [
    (1.1006, 1.1035, 1.0997, 1.1000),  # 0
    (1.1008, 1.1032, 1.0991, 1.0998),  # 1
    (1.0992, 1.1005, 1.0944, 1.0973),  # 2
    (1.0972, 1.1032, 1.0963, 1.1009),  # 3 -- range start=3 H=1.1032 L=1.0963, only resolves once candle 6 exists
    (1.1013, 1.1021, 1.0992, 1.1016),  # 4 -- range start=4 H=1.1021 L=1.0992, resolves true_break @5
    (1.0996, 1.1030, 1.0940, 1.0986),  # 5 -- purge candle: breaches range@4 on BOTH sides, range@3 on LOW only
    (1.1004, 1.1015, 1.0985, 1.1014),  # 6 -- future candle: resolves range start=3 as false_break @6
]

_LTF_START = datetime(2026, 1, 2, 0, 0)  # == HTF candle 6's own start (HTF_START + 24h)
_LTF_SPECS = [
    (1.1000, 1.1020, 1.0980, 1.1010),  # 0 -- LTF range: H=1.1020 L=1.0980
    (1.1010, 1.1035, 1.1000, 1.1015),  # 1 -- anchor, purges High (bearish)
    (1.1000, 1.1005, 1.0950, 1.0960),  # 2 -- confirms (wick entry)
    (1.0965, 1.0970, 1.0958, 1.0966),  # 3 -- filler: no wick-overlap, no breach
    (1.0960, 1.1012, 1.0955, 1.0965),  # 4 -- retest_index=4, LTF t = LTF_START + 4h = HTF_START + 28h
]

# Qualifies ONLY against range@4's high-side breach extreme (1.1030) -- range@3
# is never breached on its (wider) high side, so its own extremes never
# include 1.1030.
_KEY_LEVEL = KeyLevel(kind="fvg", top=1.1035, bottom=1.1025, origin_index=0, expiry_index=None)


def _htf_series(n: int) -> OHLCSeries:
    candles = tuple(
        Candle(timestamp=_HTF_START + _HTF_DURATION * i, open=o, high=h, low=l, close=c)
        for i, (o, h, l, c) in enumerate(_HTF_SPECS[:n])
    )
    return OHLCSeries(candles=candles, instrument="EURUSD", timeframe="4H")


def _ltf_series(n: int = 5) -> OHLCSeries:
    candles = tuple(
        Candle(timestamp=_LTF_START + timedelta(hours=i), open=o, high=h, low=l, close=c)
        for i, (o, h, l, c) in enumerate(_LTF_SPECS[:n])
    )
    return OHLCSeries(candles=candles, instrument="EURUSD", timeframe="15M")


def test_fixture_sanity_ranges_share_purge_index_with_different_breach_sets():
    htf7 = _htf_series(7)
    ranges = causal_crt_ranges(htf7)
    range4 = next(r for r in ranges if r.start_index == 4)
    range3 = next(r for r in ranges if r.start_index == 3)
    assert range4.resolved_at_index == 5
    assert range3.resolved_at_index == 6

    purge_index_4 = first_breach_index(htf7.candles, range4.start_index, range4.resolved_at_index, high=range4.high, low=range4.low)
    purge_index_3 = first_breach_index(htf7.candles, range3.start_index, range3.resolved_at_index, high=range3.high, low=range3.low)
    assert purge_index_4 == purge_index_3 == 5  # shared purge candle

    assert _purge_wick_extremes(htf7.candles[5], range4) == (1.1030, 1.0940)
    assert _purge_wick_extremes(htf7.candles[5], range3) == (1.0940,)  # high side NOT breached


def test_purge_index_map_is_growth_stable_under_resolution_order():
    """Refinement of the reviewer's diagnosis: `causal_crt_ranges` emits
    ranges in RESOLUTION order (ascending `resolved_at_index`), so
    `_purge_index_map`'s `setdefault` always keeps the earliest-resolving
    range for a shared purge_index -- and since a range's own
    `resolved_at_index` never changes once resolved (REQ-CAUSAL-01), no
    later-appearing competitor (which must resolve even later) can ever
    displace it. Unlike legacy `detect_crt_ranges` (start-index order, the
    actual D3/B3-B4 mechanism), growing N alone does NOT flip this map."""
    htf6, htf7 = _htf_series(6), _htf_series(7)
    map6 = _purge_index_map(htf6.candles, causal_crt_ranges(htf6))
    map7 = _purge_index_map(htf7.candles, causal_crt_ranges(htf7))
    assert map6[5].start_index == 4
    assert map7[5].start_index == 4  # UNCHANGED -- range@4 resolved first, keeps the slot


def test_key_level_credited_from_a_stale_global_winner_ignores_the_signals_own_htf_context():
    """RED (pre-fix): a LATE signal's own H-A-selected `htf_context` is
    range@3 (tie-break lowest start_index, once range@3 becomes causally
    observable) -- but a `key_level_credit_map` built once from the full
    HTF range set is keyed only by purge_index, so it returns whatever
    range WON that purge_index globally (range@4, per the test above) and
    credits a KeyLevel that only range@4's own breach ever qualified for.
    A per-signal-correct crediting, seeded from `htf_context` itself, must
    return `None` here."""
    htf7 = _htf_series(7)
    ltf5 = _ltf_series()
    tags = generate_causal_aligned_signals(ltf5, htf7, htf_key_levels=[_KEY_LEVEL])
    tagged = next(t for t in tags if t.ltf_signal.retest_index == 4)

    assert tagged.aligned == "aligned"
    assert tagged.htf_context is not None
    assert tagged.htf_context.start_index == 3  # H-A correctly ties-break to range@3 for this late t

    assert tagged.key_level is None  # FAILS pre-fix: credited via range@4's stale global-map extremes


def test_early_signal_still_correctly_credited_after_the_fix():
    """Regression guard: an EARLY signal (t = candle5 close + 4H, before
    range@3 is causally observable) correctly gets range@4 as `htf_context`
    and MUST still be credited -- the fix must not simply stop crediting
    everything."""
    htf7 = _htf_series(7)
    ranges = causal_crt_ranges(htf7)
    t_early = htf7.candles[5].timestamp + _HTF_DURATION
    ctx = select_htf_context(htf7, ranges, t_early)
    assert ctx.start_index == 4

    purge_index = first_breach_index(htf7.candles, ctx.start_index, ctx.resolved_at_index, high=ctx.high, low=ctx.low)
    credited = _key_level_credit_map(htf7.candles, {purge_index: ctx}, [_KEY_LEVEL]).get(purge_index)
    assert credited == _KEY_LEVEL


def test_stage6_membership_flips_with_the_leak_excluded_no_key_level():
    """Criterion (d): the causal leak's downstream effect on Stage6
    membership. Pre-fix, the LATE signal above is wrongly ADMITTED into the
    key-level bucket (survivor); the correct, per-signal-computed result
    excludes it (`excluded_no_key_level` == 1, zero survivors)."""
    htf7 = _htf_series(7)
    ltf5 = _ltf_series()
    tags = generate_causal_aligned_signals(ltf5, htf7, htf_key_levels=[_KEY_LEVEL])
    tagged = next(t for t in tags if t.ltf_signal.retest_index == 4)

    cuts = _population_cuts([tagged])
    assert cuts.no_key_level == 1
    assert cuts.survivors == []
