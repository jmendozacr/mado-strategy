from dataclasses import dataclass
from datetime import datetime, timedelta

from core.candle import Candle, OHLCSeries
from core.key_level import KeyLevel


# 12:00 UTC is 07:00 NY EST — the first hour inside the default NY Kill
# Zone. Backtest's kill-zone gate defaults to enabled (REQ-36), so a base of
# midnight UTC would put every fixture's early candles outside the zone and
# silently cut the whole population at stage 5 for every backtest unit test.
_KILL_ZONE_BASE = datetime(2026, 1, 1, 12, 0)


class CandleSeriesBuilder:
    """Fluent builder for synthetic OHLCSeries fixtures.

    Candles are auto-timestamped one hour apart in emission order — tests
    care about OHLC shape and relative position, not wall-clock time. The
    default `start` (`_KILL_ZONE_BASE`) keeps a fixture's early candles
    inside the NY Kill Zone; pass an explicit `start` to land elsewhere.
    """

    def __init__(self, instrument: str = "EURUSD", timeframe: str = "1H", start: datetime = _KILL_ZONE_BASE):
        self._instrument = instrument
        self._timeframe = timeframe
        self._start = start
        self._candles: list[Candle] = []

    def candle(
        self, open: float, high: float, low: float, close: float
    ) -> "CandleSeriesBuilder":
        index = len(self._candles)
        self._candles.append(
            Candle(
                timestamp=self._start + timedelta(hours=index),
                open=open,
                high=high,
                low=low,
                close=close,
            )
        )
        return self

    def build(self) -> OHLCSeries:
        return OHLCSeries(
            candles=tuple(self._candles),
            instrument=self._instrument,
            timeframe=self._timeframe,
        )


def bearish_fvg_fill_setup() -> OHLCSeries:
    """Charter-2 [00:13:19] DXY daily: "El mercado llenó un FVG, cerró por
    debajo de la vela de rebalanceo, retesteó dicha vela y se expandió a la
    baja" — a bearish Fair Value Gap forms (candle-1's low sits above
    candle-3's high), price later trades back up to fully fill it (retest),
    then expands down.

    Index 0-2 form the gap (bearish: candle[2].high < candle[0].low).
    Index 3 is filler. Index 4 trades back up to fill the gap (its high
    reaches candle[0].low, the gap's top/far edge).
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1050, high=1.1055, low=1.1040, close=1.1045)  # 0 — gap top = low 1.1040
        .candle(open=1.1030, high=1.1035, low=1.1005, close=1.1020)  # 1 — middle candle (low kept above candle 3's high to avoid an overlapping i=1 gap)
        .candle(open=1.1010, high=1.1015, low=1.0995, close=1.1000)  # 2 — gap bottom = high 1.1015
        .candle(open=1.1000, high=1.1010, low=1.0990, close=1.0995)  # 3 — filler, still below gap
        .candle(open=1.1005, high=1.1042, low=1.1000, close=1.1038)  # 4 — retest, high reaches gap top (1.1040) -> filled
        .build()
    )


def bullish_fvg_partial_fill_setup() -> OHLCSeries:
    """Charter-3 [00:14:47]-[00:15:23]: a 4H bullish FVG identified as a
    support zone; "el mercado sube sin rellenar completamente el FVG" — price
    rises without fully filling the gap below it.

    Index 0-2 form the gap (bullish: candle[2].low > candle[0].high).
    Index 3 dips into the gap's near edge (top) but never reaches the far
    edge (bottom) — REQ-10.1's partial re-entry, stays "open".
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.0980, high=1.0985, low=1.0970, close=1.0975)  # 0 — gap bottom = high 1.0985
        .candle(open=1.0995, high=1.1005, low=1.0990, close=1.1000)  # 1 — middle candle
        .candle(open=1.1010, high=1.1020, low=1.1005, close=1.1015)  # 2 — gap top = low 1.1005
        .candle(open=1.1000, high=1.1008, low=1.0990, close=1.0993)  # 3 — dips to gap top (1.0985<1.0990<=1.1005) but not gap bottom (1.0985)
        .build()
    )


def three_candle_crt_setup() -> OHLCSeries:
    """Charter-1 [00:16:11] Example 2: Vela1 establishes the range. Vela2
    purges the CRT High (wick beyond, close back inside) reacting to a
    Rejection Block. Vela3 expands directly to the CRT Low (close beyond
    the opposite extreme) -> 3-candle model, true_break resolution.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1010, high=1.1035, low=1.1000, close=1.1005)  # 1 — pokes High, closes back inside
        .candle(open=1.1000, high=1.1005, low=1.0950, close=1.0960)  # 2 — closes below Low -> true_break
        .build()
    )


def two_candle_crt_setup() -> OHLCSeries:
    """Charter-1 [00:16:53] Example 3: Vela1 establishes the range. Vela2
    sweeps the CRT High AND, within that same candle, falls hard to close
    beyond the CRT Low -> 2-candle model, true_break resolution.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1015, high=1.1035, low=1.0950, close=1.0960)  # 1 — pokes High AND closes below Low
        .build()
    )


def multi_inside_crt_setup() -> OHLCSeries:
    """Charter-1 [00:18:12] Example 5: Vela1 establishes the range. Candles
    2-3 stay fully trapped inside [Low, High] (no wick or close breach).
    Candle 4 finally purges the CRT High (wick beyond, close back inside).
    Candle 5 expands to close beyond the CRT Low -> multi-inside model.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1005, high=1.1015, low=1.0990, close=1.1000)  # 1 — trapped
        .candle(open=1.1000, high=1.1012, low=1.0985, close=1.1005)  # 2 — trapped
        .candle(open=1.1010, high=1.1035, low=1.1000, close=1.1005)  # 3 — finally pokes High, closes inside
        .candle(open=1.1000, high=1.1005, low=1.0950, close=1.0960)  # 4 — closes below Low -> true_break
        .build()
    )


def multi_outside_crt_setup() -> OHLCSeries:
    """Charter-1 [00:11:06] Outside Bar CRT: Vela1 establishes the range.
    Vela2 purges the CRT High (wick beyond, close back inside) — same
    shape as the 3-candle model's Vela2. Unlike 3-candle, expansion does
    NOT complete at Vela3 — candle 2 stays inside without even reaching
    the range midpoint; only candle 3 finally closes beyond the CRT Low
    -> multi-outside (expansion took multiple subsequent candles).
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980, mid=1.1000
        .candle(open=1.1010, high=1.1035, low=1.1000, close=1.1005)  # 1 — pokes High, closes back inside
        .candle(open=1.1005, high=1.1015, low=1.0995, close=1.1008)  # 2 — stays inside, above midpoint
        .candle(open=1.1000, high=1.1005, low=1.0950, close=1.0960)  # 3 — finally closes below Low
        .build()
    )


def crt_range_false_break_setup() -> OHLCSeries:
    """Charter-1 [00:06:48]/[00:07:03] "Ruptura Falsa / Turtle Soup": Vela2
    pokes the CRT Low (wick beyond, close back inside). Candle 2's close
    reverses back through the range reaching at least the midpoint
    ((High+Low)/2 = 1.1000) without fully breaking the opposite (High)
    extreme -> false_break resolution.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980, mid=1.1000
        .candle(open=1.0990, high=1.1010, low=1.0960, close=1.0995)  # 1 — pokes Low, closes back inside
        .candle(open=1.0995, high=1.1008, low=1.0990, close=1.1005)  # 2 — close reaches midpoint (>= 1.1000)
        .build()
    )


def crt_range_never_resolves_setup() -> OHLCSeries:
    """Price stays fully within [Low, High] for the whole lookback window
    (`max_lookback=2` in the test's config) -> REQ-14: never resolves,
    not emitted at all.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1005, high=1.1015, low=1.0990, close=1.1000)  # 1 — inside
        .candle(open=1.1000, high=1.1010, low=1.0985, close=1.1005)  # 2 — inside
        .build()
    )


def crt_range_resolves_on_last_candle_setup() -> OHLCSeries:
    """Price stays inside for one candle, then resolves exactly on the
    candle at `i + max_lookback` (`max_lookback=2` in the test's config) —
    the last candle the lookback window allows.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1005, high=1.1015, low=1.0990, close=1.1000)  # 1 — inside
        .candle(open=1.1000, high=1.1005, low=1.0950, close=1.0960)  # 2 — offset=2=max_lookback, true_break
        .build()
    )


def bullish_mss_setup() -> OHLCSeries:
    """Charter-3 [00:10:32]-grounded shape (REQ-15.1): a swing low forms
    (opposite-extreme rejection), then a swing high forms after it, then a
    later candle CLOSES beyond the swing high by at least
    `decisive_close_ratio` (default 0.25) of the swing-to-opposite-extreme
    distance -> bullish MSS flagged at the break candle.

    Swing low @1 (price 1.0950), swing high @3 (price 1.1000). Distance =
    0.0050; threshold = 1.1000 + 0.25*0.0050 = 1.10125. Candle 5 closes at
    1.1020, clearing the threshold.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.0980, high=1.0985, low=1.0975, close=1.0980)  # 0 — filler
        .candle(open=1.0960, high=1.0965, low=1.0950, close=1.0955)  # 1 — swing low
        .candle(open=1.0975, high=1.0990, low=1.0970, close=1.0985)  # 2 — filler
        .candle(open=1.0985, high=1.1000, low=1.0980, close=1.0995)  # 3 — swing high
        .candle(open=1.0985, high=1.0995, low=1.0982, close=1.0990)  # 4 — filler
        .candle(open=1.0995, high=1.1025, low=1.0990, close=1.1020)  # 5 — break, close >= 1.10125
        .build()
    )


def bearish_mss_setup() -> OHLCSeries:
    """Mirror of `bullish_mss_setup`: swing high forms first (opposite-
    extreme rejection), then a swing low forms after it, then a later
    candle CLOSES beyond the swing low by at least `decisive_close_ratio`
    of the swing-to-opposite-extreme distance -> bearish MSS.

    Swing high @1 (price 1.1050), swing low @3 (price 1.1000). Distance =
    0.0050; threshold = 1.1000 - 0.25*0.0050 = 1.09875. Candle 5 closes at
    1.0980, clearing the threshold.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1020, high=1.1025, low=1.1015, close=1.1020)  # 0 — filler
        .candle(open=1.1040, high=1.1050, low=1.1035, close=1.1045)  # 1 — swing high
        .candle(open=1.1025, high=1.1030, low=1.1010, close=1.1015)  # 2 — filler
        .candle(open=1.1015, high=1.1020, low=1.1000, close=1.1005)  # 3 — swing low
        .candle(open=1.1010, high=1.1018, low=1.1002, close=1.1008)  # 4 — filler
        .candle(open=1.1005, high=1.1010, low=1.0975, close=1.0980)  # 5 — break, close <= 1.09875
        .build()
    )


def mss_ratio_undershoot_setup() -> OHLCSeries:
    """Same swing structure as `bullish_mss_setup`, but the break candle's
    close beats the swing high price WITHOUT clearing the decisive-close
    ratio (1.1005 is only 0.0005 above the 1.1000 swing high, i.e. a 0.10
    ratio of the 0.0050 distance, short of the default 0.25) -> no MSS.
    Triangulates the ratio-weighted threshold against a plain "close beyond
    swing price" implementation.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.0980, high=1.0985, low=1.0975, close=1.0980)  # 0 — filler
        .candle(open=1.0960, high=1.0965, low=1.0950, close=1.0955)  # 1 — swing low
        .candle(open=1.0975, high=1.0990, low=1.0970, close=1.0985)  # 2 — filler
        .candle(open=1.0985, high=1.1000, low=1.0980, close=1.0995)  # 3 — swing high
        .candle(open=1.0985, high=1.0995, low=1.0982, close=1.0990)  # 4 — filler
        .candle(open=1.0995, high=1.1010, low=1.0990, close=1.1005)  # 5 — close beats swing, ratio undershoot
        .build()
    )


def mss_uses_most_recent_opposite_swing_setup() -> OHLCSeries:
    """Triangulates "most recent swing point of the OPPOSITE kind formed
    BEFORE it" (design.md 4.4) against a plain nearest-by-index-distance
    selection that ignores before/after: swing low A @1 (price 1.0980)
    forms BEFORE the swing high @3 (price 1.1000, the broken swing);
    swing low C @4 (price 1.0985) forms AFTER it and is numerically closer
    in index (distance 1 vs 2).

    Correct (most-recent-BEFORE) pairing uses low A: distance=0.0020,
    threshold=1.1000+0.25*0.0020=1.10050. The break candle @6 closes at
    1.1004 — clears an incorrect nearest-by-index-distance threshold
    computed from low C (distance=0.0015, threshold=1.100375) but falls
    short of the correct threshold from low A, so the correct
    implementation reports NO MSS here.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.0985, high=1.0990, low=1.0985, close=1.0987)  # 0 — filler
        .candle(open=1.0982, high=1.0987, low=1.0980, close=1.0983)  # 1 — swing low A
        .candle(open=1.0985, high=1.0993, low=1.0990, close=1.0991)  # 2 — filler
        .candle(open=1.0990, high=1.1000, low=1.0988, close=1.0995)  # 3 — swing high (broken swing)
        .candle(open=1.0993, high=1.0997, low=1.0985, close=1.0990)  # 4 — swing low C (after)
        .candle(open=1.0990, high=1.0996, low=1.0992, close=1.0994)  # 5 — filler
        .candle(open=1.0994, high=1.1006, low=1.0990, close=1.1004)  # 6 — no MSS (correct threshold not cleared)
        .build()
    )


def mss_no_prior_opposite_swing_setup() -> OHLCSeries:
    """REQ-16.1: a swing high forms with NO swing low ever recorded before
    it (a plain one-directional rise from series start) -> excluded, no
    MSS, regardless of how decisively the later close clears the swing
    high. Swing high @1 (price 1.0975); the break candle @3 closes at
    1.1000, well past any plausible ratio threshold, but must still be
    excluded for lack of a prior opposite-extreme rejection.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.0950, high=1.0955, low=1.0945, close=1.0950)  # 0 — filler (never a swing candidate, index 0)
        .candle(open=1.0955, high=1.0975, low=1.0950, close=1.0965)  # 1 — swing high
        .candle(open=1.0960, high=1.0965, low=1.0955, close=1.0958)  # 2 — filler
        .candle(open=1.0970, high=1.1010, low=1.0965, close=1.1000)  # 3 — decisively beyond swing high, but excluded
        .build()
    )


def model1_wick_priority_setup() -> OHLCSeries:
    """REQ-20.1: candle 1 purges the CRT High (bearish anchor). Candle 2's
    close (1.0995) goes beyond the anchor's WICK-low extreme (1.1005), not
    just its body extreme (1.1010) -> Wick used regardless of body size,
    entry_price = anchor's wick extreme (1.1035, the swept side).
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1010, high=1.1035, low=1.1005, close=1.1015)  # 1 — anchor, purges High
        .candle(open=1.1000, high=1.1005, low=1.0990, close=1.0995)  # 2 — confirms beyond wick extreme
        .build()
    )


def model1_body_tiebreak_big_body_setup() -> OHLCSeries:
    """REQ-20: anchor candle 1 is a "big beefy candle" (body_ratio=0.767,
    >= body_ratio_tiebreak=0.6). Candle 2's close (1.1002) clears the
    anchor's BODY extreme (1.1005) but not its WICK extreme (1.1000) ->
    middle zone -> tiebreak favors Body (big body): entry_price = anchor's
    body extreme (1.1005), per charter-2 [00:11:18].
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1005, high=1.1030, low=1.1000, close=1.1028)  # 1 — anchor, big body, purges High
        .candle(open=1.1005, high=1.1010, low=1.0995, close=1.1002)  # 2 — confirms in middle zone
        .build()
    )


def model1_body_tiebreak_small_body_setup() -> OHLCSeries:
    """REQ-20: anchor candle 1 has a small body and long wick (body_ratio=
    0.044, < body_ratio_tiebreak=0.6). Candle 2's close (1.1000) clears the
    anchor's BODY extreme (1.1015) but not its WICK extreme (1.0995) ->
    middle zone -> tiebreak favors Wick (small body): entry_price =
    anchor's wick extreme (1.1040), per charter-2 [00:12:02].
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1015, high=1.1040, low=1.0995, close=1.1017)  # 1 — anchor, small body, purges High
        .candle(open=1.1015, high=1.1018, low=1.0998, close=1.1000)  # 2 — confirms in middle zone
        .build()
    )


def model1_body_tiebreak_aligned_color_setup() -> OHLCSeries:
    """REQ-20 regression, bearish: anchor candle 1 is a big-body BEARISH-
    colored candle (close < open) whose direction is ALSO bearish — the
    color matches the direction, so anchor.open (1.1038) sits on the
    body's HIGH side, not its low side. Candle 1 itself closes beyond the
    range high (1.1020, true_break) so the CRT range resolves AND purges
    High on the same candle. Candle 2's close (1.1021) clears the anchor's
    BODY extreme (1.1022) but not its WICK extreme (1.1020) -> middle zone
    -> tiebreak favors Body (body_ratio=0.8 >= 0.6): per charter-2
    [00:11:04]-[00:11:18], "Body" and "Open" are synonyms — entry_price is
    always anchor.open (1.1038) regardless of which side of the body it
    falls on.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1038, high=1.1040, low=1.1020, close=1.1022)  # 1 — anchor, big red body, purges High + resolves range
        .candle(open=1.1022, high=1.1025, low=1.1015, close=1.1021)  # 2 — confirms in middle zone
        .build()
    )


def model1_body_tiebreak_aligned_color_bullish_setup() -> OHLCSeries:
    """REQ-20 regression, bullish mirror of
    `model1_body_tiebreak_aligned_color_setup`: anchor candle 1 is a
    big-body BULLISH-colored candle (close > open) whose direction is ALSO
    bullish — color matches direction, so anchor.open (1.0962) sits on the
    body's LOW side. Candle 1 itself closes beyond the range low (1.0980,
    true_break) so the CRT range resolves AND purges Low on the same
    candle. Candle 2's close (1.0979) clears the anchor's BODY extreme
    (1.0978) but not its WICK extreme (1.0980) -> middle zone -> tiebreak
    favors Body (body_ratio=0.8 >= 0.6): entry_price is anchor.open
    (1.0962).
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.0990, high=1.1020, low=1.0980, close=1.1000)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.0962, high=1.0980, low=1.0960, close=1.0978)  # 1 — anchor, big green body, purges Low + resolves range
        .candle(open=1.0978, high=1.0982, low=1.0975, close=1.0979)  # 2 — confirms in middle zone
        .build()
    )


def model1_confirmed_setup() -> OHLCSeries:
    """Dedicated, isolated CONFIRMED fixture (REQ-21): anchor purges the
    CRT High, confirms via wick-beyond close, then candle 3 both retests
    (its wick overlaps the anchor's body range) AND closes beyond its own
    open in the trade direction on the SAME candle -> CONFIRMED. Exercises
    "any magnitude beyond the retest candle's own open" without needing a
    separate expansion candle.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1010, high=1.1035, low=1.1005, close=1.1015)  # 1 — anchor, purges High
        .candle(open=1.1000, high=1.1005, low=1.0990, close=1.0995)  # 2 — confirms (wick entry @1.1035)
        .candle(open=1.0995, high=1.1012, low=1.0980, close=1.0990)  # 3 — retest + same-candle close -> CONFIRMED
        .build()
    )


def model1_invalidated_setup() -> OHLCSeries:
    """REQ-18/REQ-21: same anchor+confirmation as `model1_confirmed_setup`,
    but candle 3 CLOSES beyond the anchor's protected extreme (1.1035)
    before any retest is found -> INVALIDATED (respect_rule_tolerance=0,
    close-based; a wick breach alone would not invalidate).
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1010, high=1.1035, low=1.1005, close=1.1015)  # 1 — anchor, purges High
        .candle(open=1.1000, high=1.1005, low=1.0990, close=1.0995)  # 2 — confirms (wick entry @1.1035)
        .candle(open=1.0995, high=1.1040, low=1.0990, close=1.1038)  # 3 — closes beyond 1.1035 -> INVALIDATED
        .build()
    )


def model1_pending_setup() -> OHLCSeries:
    """REQ-21.1, grounded charter-2 [00:08:29]-[00:08:57]: same anchor +
    confirmation as `model1_confirmed_setup`, but the series ENDS right
    after confirmation — no retest found by series end -> PENDING, never
    dropped (Model-1's "one disadvantage": price can take off without
    ever returning to retest the purge candle).
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1010, high=1.1035, low=1.1005, close=1.1015)  # 1 — anchor, purges High
        .candle(open=1.1000, high=1.1005, low=1.0990, close=1.0995)  # 2 — confirms; series ends, no retest
        .build()
    )


def model1_pre_confirmation_breach_setup() -> OHLCSeries:
    """REQ-18 regression: anchor purges the CRT High (bearish), but the
    very next candle CLOSES beyond the anchor's protected extreme (High,
    1.1035) before any engulfing confirmation ever occurs -> must
    invalidate immediately (INVALIDATED), not silently drop the anchor.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1010, high=1.1035, low=1.1005, close=1.1015)  # 1 — anchor, purges High
        .candle(open=1.1015, high=1.1050, low=1.1010, close=1.1040)  # 2 — closes beyond 1.1035, never confirmed -> INVALIDATED
        .build()
    )


def model1_purge_engulf_charter2_setup() -> OHLCSeries:
    """Charter-2 [00:05:28]-[00:06:04], Example 1: candle 1 purges the CRT
    High ("barre el Alto tomando la liquidez"). Candle 2 closes below the
    anchor's body ("cierra por debajo del cuerpo") -> confirms, entry=wick
    (close also clears the anchor's wick extreme). Candle 3 retests and
    respects the anchor (no breach). Candle 4 expands beyond the retest
    candle's own open ("fuerte expansión bajista") -> CONFIRMED.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1010, high=1.1035, low=1.1000, close=1.1015)  # 1 — anchor, purges High
        .candle(open=1.1000, high=1.1005, low=1.0950, close=1.0960)  # 2 — confirms (close beyond wick+body); also resolves range true_break
        .candle(open=1.0960, high=1.1012, low=1.0955, close=1.0965)  # 3 — retest (overlaps anchor body [1.1010,1.1015])
        .candle(open=1.0965, high=1.0968, low=1.0900, close=1.0910)  # 4 — expansion, close beyond retest's own open -> CONFIRMED
        .build()
    )


def model1_delayed_engulf_charter2_setup() -> OHLCSeries:
    """Charter-2 [00:06:35]-[00:07:02], Example 2: candle 1 purges the CRT
    Low. The engulfing close does NOT happen on the very next candle —
    candle 2 stays inside (no breach either way) — it takes until candle 3
    to close beyond the anchor's body ("toma un par de velas cerrar por
    encima"). No candle ever closed below the anchor's protected extreme in
    between ("Regla de Respeto") -> anchor stays valid, confirms on close.
    Candle 4 retests; candle 5 expands -> CONFIRMED.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.0990, high=1.1000, low=1.0960, close=1.0985)  # 1 — anchor, purges Low
        .candle(open=1.0985, high=1.0995, low=1.0975, close=1.0980)  # 2 — delay: no confirm, no invalidate
        .candle(open=1.0980, high=1.1040, low=1.0975, close=1.1030)  # 3 — delayed confirm, entry=wick @1.0960
        .candle(open=1.1030, high=1.1032, low=1.0987, close=1.1020)  # 4 — retest (overlaps anchor body [1.0985,1.0990])
        .candle(open=1.1020, high=1.1055, low=1.1015, close=1.1050)  # 5 — expansion, close beyond retest's own open -> CONFIRMED
        .build()
    )


def model1_dual_purge_and_fvg_fill_charter2_setup() -> OHLCSeries:
    """Charter-2 [00:07:27]-[00:07:56], Example 3: candle 4 does BOTH jobs
    at once — purges a short-term CRT Low (from the range formed at candle
    3) AND fills/rebalances the bullish FVG formed by candles 0-2 — a
    "high probability" dual-condition setup. Both confirmation types
    (`purge_engulf` and `fvg_fill`) are independently detected at the same
    anchor candle. Candle 5 confirms both (and resolves the CRT range as
    false_break); candle 6 retests; candle 7 expands -> both CONFIRMED.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1010, low=1.0990, close=1.1005)  # 0 — FVG candle1 (high=1.1010)
        .candle(open=1.1010, high=1.1030, low=1.1005, close=1.1020)  # 1 — FVG candle2 (filler)
        .candle(open=1.1025, high=1.1045, low=1.1020, close=1.1040)  # 2 — FVG candle3 (low=1.1020) -> gap [1.1010,1.1020]
        .candle(open=1.1040, high=1.1055, low=1.1012, close=1.1045)  # 3 — CRT range: H=1.1055 L=1.1012
        .candle(open=1.1030, high=1.1035, low=1.1005, close=1.1020)  # 4 — anchor: purges range-low AND fills FVG
        .candle(open=1.1020, high=1.1042, low=1.1015, close=1.1040)  # 5 — confirms both; resolves range false_break
        .candle(open=1.1040, high=1.1042, low=1.1025, close=1.1038)  # 6 — retest (overlaps anchor body [1.1020,1.1030])
        .candle(open=1.1038, high=1.1060, low=1.1035, close=1.1055)  # 7 — expansion -> CONFIRMED
        .build()
    )


def model1_delayed_confirmation_after_retest_setup() -> OHLCSeries:
    """REQ-43.1: retest touches at index 3 (wick overlaps the anchor body,
    but the retest candle's own close does not beat its own open), then 5
    flat candles (4-8) neither breach the anchor's protected extreme nor
    close beyond the retest candle's open, until candle 9 finally does —
    confirmation lands 6 candles after the retest touch, so
    confirmation_index (9) is distinct from retest_index (3).
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1010, high=1.1035, low=1.1005, close=1.1015)  # 1 — anchor, purges High
        .candle(open=1.1000, high=1.1005, low=1.0990, close=1.0995)  # 2 — confirms (wick entry @1.1035)
        .candle(open=1.1005, high=1.1012, low=1.1008, close=1.1010)  # 3 — retest (overlaps anchor body [1.1010,1.1015]), no same-candle beat
        .candle(open=1.1008, high=1.1012, low=1.1004, close=1.1010)  # 4 — flat, no breach/beat
        .candle(open=1.1008, high=1.1012, low=1.1004, close=1.1010)  # 5 — flat
        .candle(open=1.1008, high=1.1012, low=1.1004, close=1.1010)  # 6 — flat
        .candle(open=1.1008, high=1.1012, low=1.1004, close=1.1010)  # 7 — flat
        .candle(open=1.1008, high=1.1012, low=1.1004, close=1.1010)  # 8 — flat
        .candle(open=1.1010, high=1.1015, low=1.0990, close=1.0995)  # 9 — closes beyond retest open (1.1005) -> CONFIRMED, 6 candles after retest
        .build()
    )


def bearish_purge_setup() -> OHLCSeries:
    """Charter-2 [00:05:28]-[00:06:04]: a swing high forms, then a later
    candle purges it (wicks above, taking the resting liquidity) before the
    market reverses down.

    Index 1 is the swing high (strictly higher than index 0 and index 2 on
    the high side) — flaggable as soon as index 2 exists, i.e. BEFORE the
    purge candle at index 3 appears (REQ-06.1). Index 3 is the purge
    candle: its wick sweeps above index 1's high. Full engulf/retest
    mechanics are Model-1's concern (S-004) — this fixture only needs to
    carry the Swing-relevant shape for S-000.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1005, low=1.0985, close=1.0995)
        .candle(open=1.0995, high=1.1020, low=1.0990, close=1.1005)
        .candle(open=1.1005, high=1.1010, low=1.0980, close=1.0990)
        .candle(open=1.0990, high=1.1030, low=1.0970, close=1.0975)
        .build()
    )


@dataclass(frozen=True)
class KeyLevelConfluencePair:
    htf_series: OHLCSeries
    ltf_series: OHLCSeries
    expected_key_level: KeyLevel | None  # the level REQ-55 must credit; None for the non-confluent twin


def key_level_confluence_pair_setup(confluent: bool) -> KeyLevelConfluencePair:
    """Design §8.9 minimal-pair builder: an HTF bearish FVG (candles 0-2),
    a CRT range (candle 3), and a purge candle (candle 4) whose high
    (1.1035) breaches the range and — in the confluent variant — lands
    inside the FVG zone. The two variants differ in EXACTLY ONE number —
    candle 2's high (the FVG zone's bottom edge) — shifted so the zone no
    longer contains the purge's credited extreme; everything else
    (timestamps, CRT range, purge candle, LTF series, Model-1 signal) is
    identical, which is what makes a differential comparison (REQ-56.3)
    meaningful. Same geometry as test_cli_backtest_e2e.py's `_HTF_DAILY`
    (design §8.2), reused here as an HTF/LTF `OHLCSeries` pair rather than
    MT5 CSV rows.
    """
    zone_bottom = 1.1030 if confluent else 1.1036
    htf_start = datetime(2026, 7, 2)
    htf_specs = [
        (1.1060, 1.1065, 1.1040, 1.1045),  # 0 — FVG top = low 1.1040
        (1.1042, 1.1044, 1.1034, 1.1036),  # 1 — middle candle
        (1.1028, zone_bottom, 1.1020, 1.1022),  # 2 — FVG bottom = high (varies)
        (1.1020, 1.1028, 1.0900, 1.0910),  # 3 — CRT range: H=1.1028 L=1.0900
        (1.0915, 1.1035, 1.0905, 1.0920),  # 4 — purge (high 1.1035)
        (1.0920, 1.0930, 1.0910, 1.0925),  # 5 — trailing
    ]
    htf_series = OHLCSeries(
        candles=tuple(
            Candle(timestamp=htf_start + timedelta(days=i), open=o, high=h, low=l, close=c)
            for i, (o, h, l, c) in enumerate(htf_specs)
        ),
        instrument="EURUSD", timeframe="D",
    )

    ltf_start = datetime(2026, 7, 6, 10, 0)
    ltf_specs = [
        (1.1000, 1.1020, 1.0980, 1.1010),  # 0 — range: H=1.1020 L=1.0980
        (1.1010, 1.1035, 1.1000, 1.1015),  # 1 — anchor, purges High
        (1.1000, 1.1005, 1.0950, 1.0960),  # 2 — confirms
        (1.0960, 1.1012, 1.0955, 1.0965),  # 3 — retest + fills
        (1.0965, 1.1010, 1.0790, 1.0910),  # 4 — expansion -> CONFIRMED
    ]
    ltf_series = OHLCSeries(
        candles=tuple(
            Candle(timestamp=ltf_start + timedelta(hours=i), open=o, high=h, low=l, close=c)
            for i, (o, h, l, c) in enumerate(ltf_specs)
        ),
        instrument="EURUSD", timeframe="1H",
    )

    expected_key_level = (
        KeyLevel(kind="fvg", top=1.1040, bottom=zone_bottom, origin_index=2, expiry_index=None)
        if confluent else None
    )
    return KeyLevelConfluencePair(htf_series=htf_series, ltf_series=ltf_series, expected_key_level=expected_key_level)
