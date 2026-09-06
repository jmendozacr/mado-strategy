"""Hypothesis harness for the no-lookahead structural contract (REQ-07,
ADR-03): detect(series.up_to(n)) must equal full-series detection,
truncated to indices in the settled zone (index <= n - k - 1).

Swing's k=1, so the settled zone is index <= n - 2 (swings need both
neighbours, so a truncated series of length n can never surface an index
beyond n - 2 anyway — the property test locks this in as a regression
guard against a future change accidentally introducing lookahead).
"""

from datetime import datetime, timedelta

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from alignment.htf_ltf import tag_alignment
from core.candle import Candle, OHLCSeries
from core.config import BacktestConfig, DetectorConfig
from composite.mss import detect_mss_events
from entries.model1 import detect_model1_signals
from primitives.crt_range import detect_crt_ranges
from primitives.fvg import detect_fvgs
from primitives.ict_order_block import detect_ict_order_blocks
from primitives.swing import detect_swings

from backtest.levels import entry_price, stop_loss
from backtest.simulate import simulate

_SWING_K = 1
_FVG_K = 3
_CRT_RANGE_K = 20
_MSS_K = 1
_ICT_ORDER_BLOCK_K = 1
_MODEL1_K = 20
_ALIGNMENT_LTF_PER_HTF = 4


def _ohlc_candle(draw, index: int) -> Candle:
    open_ = draw(st.floats(min_value=1.0, max_value=2.0, allow_nan=False))
    close = draw(st.floats(min_value=1.0, max_value=2.0, allow_nan=False))
    wick_up = draw(st.floats(min_value=0.0, max_value=0.05, allow_nan=False))
    wick_down = draw(st.floats(min_value=0.0, max_value=0.05, allow_nan=False))
    return Candle(
        timestamp=datetime(2026, 1, 1) + timedelta(hours=index),
        open=open_,
        high=max(open_, close) + wick_up,
        low=min(open_, close) - wick_down,
        close=close,
    )


@st.composite
def ohlc_series(draw, min_size=3, max_size=30):
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    candles = tuple(_ohlc_candle(draw, i) for i in range(size))
    return OHLCSeries(candles=candles, instrument="EURUSD", timeframe="1H")


@given(series=ohlc_series())
@settings(max_examples=100)
def test_swing_detection_has_no_lookahead(series: OHLCSeries):
    full_swings = detect_swings(series)

    for n in range(3, len(series.candles) + 1):
        truncated_swings = detect_swings(series.up_to(n))
        settled_boundary = n - _SWING_K - 1  # indices <= this are settled

        settled_full_swings = [s for s in full_swings if s.index <= settled_boundary]

        assert truncated_swings == settled_full_swings


@given(series=ohlc_series())
@settings(max_examples=100)
def test_fvg_detection_has_no_lookahead(series: OHLCSeries):
    """FVG's k=3 bounds formation identity (start_index/end_index/top/
    bottom/direction) — settled once candles i, i+1, i+2 are visible.
    fill_status is NOT k-bounded the same way: "cumulative price action
    after formation" can fill a gap arbitrarily far beyond formation, so it
    is monotonic (open -> filled, never filled -> open) rather than final
    within a fixed settling window. The property checks (a) full equality
    of formation-identity fields for settled gaps, and (b) fill_status
    monotonicity: a truncated view reporting "filled" must also report
    "filled" in the full series (that observation can't be undone by more
    data); "open" in a truncated view may still resolve "filled" later.
    """
    full_fvgs = detect_fvgs(series)
    full_by_start = {f.start_index: f for f in full_fvgs}

    for n in range(3, len(series.candles) + 1):
        truncated_fvgs = detect_fvgs(series.up_to(n))
        settled_boundary = n - _FVG_K - 1

        settled_truncated = [f for f in truncated_fvgs if f.start_index <= settled_boundary]

        settled_full_start_indices = {
            f.start_index for f in full_fvgs if f.start_index <= settled_boundary
        }
        assert {f.start_index for f in settled_truncated} == settled_full_start_indices

        for truncated_fvg in settled_truncated:
            full_fvg = full_by_start[truncated_fvg.start_index]
            assert truncated_fvg.end_index == full_fvg.end_index
            assert truncated_fvg.top == full_fvg.top
            assert truncated_fvg.bottom == full_fvg.bottom
            assert truncated_fvg.direction == full_fvg.direction
            if truncated_fvg.fill_status == "filled":
                assert full_fvg.fill_status == "filled"


@given(series=ohlc_series(max_size=45))
@settings(max_examples=100)
def test_crt_range_detection_has_no_lookahead(series: OHLCSeries):
    """CRT range's k=max_lookback=20 bounds the ENTIRE outcome (emitted or
    not, and every field) per start_index — unlike FVG's fill_status, a
    range's resolution always completes (or doesn't) within a bounded
    lookback, so settled entries need full equality, not monotonicity.
    """
    full_ranges = detect_crt_ranges(series)
    full_by_start = {r.start_index: r for r in full_ranges}

    for n in range(3, len(series.candles) + 1):
        truncated_ranges = detect_crt_ranges(series.up_to(n))
        settled_boundary = n - _CRT_RANGE_K - 1

        settled_truncated_starts = {
            r.start_index for r in truncated_ranges if r.start_index <= settled_boundary
        }
        settled_full_starts = {
            r.start_index for r in full_ranges if r.start_index <= settled_boundary
        }
        assert settled_truncated_starts == settled_full_starts

        truncated_by_start = {r.start_index: r for r in truncated_ranges}
        for start in settled_truncated_starts:
            assert truncated_by_start[start] == full_by_start[start]


@given(series=ohlc_series())
@settings(max_examples=100)
def test_mss_detection_has_no_lookahead(series: OHLCSeries):
    """MSS's k=1 bounds the broken swing's own identity (settled per
    Swing's k), but the break candle that eventually confirms it can occur
    arbitrarily far in the future — an unbounded settling window, just like
    FVG's fill_status. The property checks monotonicity on the
    (broken_swing.index, direction) identity: an MSS observed in a
    truncated view for a settled broken swing must also be observed with
    the same break index in the full series (that observation can't be
    undone by more data); absence in the truncated view is not asserted
    (more data may yet trigger it).
    """
    full_events = detect_mss_events(series)
    full_by_key = {(e.broken_swing.index, e.direction): e for e in full_events}

    for n in range(3, len(series.candles) + 1):
        truncated_events = detect_mss_events(series.up_to(n))
        settled_boundary = n - _MSS_K - 1

        for truncated_event in truncated_events:
            if truncated_event.broken_swing.index > settled_boundary:
                continue
            key = (truncated_event.broken_swing.index, truncated_event.direction)
            assert key in full_by_key
            full_event = full_by_key[key]
            assert truncated_event.index == full_event.index
            assert truncated_event.broken_swing == full_event.broken_swing


@given(series=ohlc_series())
@settings(max_examples=100)
def test_ict_order_block_detection_has_no_lookahead(series: OHLCSeries):
    """ICTOrderBlock's k=1 bounds the pair's own identity — an Order Block
    anchored at i is knowable only once candle i+1 exists in the prefix
    (structurally identical in shape to swing's own no-lookahead property).
    Invalidation status for an already-knowable block must be re-derivable
    from any prefix that includes the invalidating candle, and must remain
    open in any shorter prefix.
    """
    full_blocks = detect_ict_order_blocks(series)
    full_by_key = {(b.candle_index, b.direction): b for b in full_blocks}

    for n in range(3, len(series.candles) + 1):
        truncated_blocks = detect_ict_order_blocks(series.up_to(n))
        settled_boundary = n - _ICT_ORDER_BLOCK_K - 1

        settled_truncated = [b for b in truncated_blocks if b.candle_index <= settled_boundary]
        settled_full_keys = {
            key for key, block in full_by_key.items() if block.candle_index <= settled_boundary
        }
        assert {(b.candle_index, b.direction) for b in settled_truncated} == settled_full_keys

        for block in settled_truncated:
            full_block = full_by_key[(block.candle_index, block.direction)]
            assert block.confirmation_index == full_block.confirmation_index
            assert (block.top, block.bottom) == (full_block.top, full_block.bottom)

            invalidated_within_prefix = (
                full_block.invalidation_index is not None
                and full_block.invalidation_index < n
            )
            if invalidated_within_prefix:
                assert block.status == "invalidated"
                assert block.invalidation_index == full_block.invalidation_index
            else:
                assert block.status == "open"
                assert block.invalidation_index is None


@given(series=ohlc_series(max_size=40))
@settings(max_examples=100)
def test_model1_detection_has_no_lookahead(series: OHLCSeries):
    """Model-1's k=max_retest_lookback=20 bounds the ENTIRE tracked
    lifetime (confirmation + retest search) from the anchor's own index —
    unlike FVG's fill_status or MSS's break search, Model-1's tracking
    window is a hard budget from anchor_index (v1 does no open-ended
    live tracking; an anchor that neither confirms nor resolves within the
    window settles as PENDING, a terminal-for-v1 outcome, not an
    open-ended "still waiting" state). Settled signals therefore need FULL
    equality, matching CRT range's treatment, not monotonicity.
    """
    full_signals = detect_model1_signals(series)
    full_by_key = {
        (s.anchor_index, s.direction, s.confirmation_type): s for s in full_signals
    }

    for n in range(3, len(series.candles) + 1):
        truncated_signals = detect_model1_signals(series.up_to(n))
        settled_boundary = n - _MODEL1_K - 1

        settled_truncated_keys = {
            (s.anchor_index, s.direction, s.confirmation_type)
            for s in truncated_signals
            if s.anchor_index <= settled_boundary
        }
        settled_full_keys = {
            (s.anchor_index, s.direction, s.confirmation_type)
            for s in full_signals
            if s.anchor_index <= settled_boundary
        }
        assert settled_truncated_keys == settled_full_keys

        truncated_by_key = {
            (s.anchor_index, s.direction, s.confirmation_type): s for s in truncated_signals
        }
        for key in settled_truncated_keys:
            assert truncated_by_key[key] == full_by_key[key]


@st.composite
def paired_htf_ltf_series(draw, min_htf=3, max_htf=25):
    """A synthetic HTF series plus a matching LTF series where each HTF
    candle is nested by exactly `_ALIGNMENT_LTF_PER_HTF` LTF candles
    spanning its own 1H duration — the OHLC shape of the LTF candles is
    independently random (tag_alignment doesn't require price consistency
    across the pair), only their timestamps are derived from the HTF
    series so they land inside their enclosing HTF candle's span.
    """
    htf_size = draw(st.integers(min_value=min_htf, max_value=max_htf))
    htf_candles = tuple(_ohlc_candle(draw, i) for i in range(htf_size))
    htf_series = OHLCSeries(candles=htf_candles, instrument="EURUSD", timeframe="1H")

    ltf_step = timedelta(hours=1) / _ALIGNMENT_LTF_PER_HTF
    ltf_candles = []
    for htf_index, htf_candle in enumerate(htf_candles):
        for sub in range(_ALIGNMENT_LTF_PER_HTF):
            ltf_index = htf_index * _ALIGNMENT_LTF_PER_HTF + sub
            base = _ohlc_candle(draw, ltf_index)
            ltf_candles.append(
                Candle(
                    timestamp=htf_candle.timestamp + sub * ltf_step,
                    open=base.open,
                    high=base.high,
                    low=base.low,
                    close=base.close,
                )
            )
    ltf_series = OHLCSeries(candles=tuple(ltf_candles), instrument="EURUSD", timeframe="5M")
    return htf_series, ltf_series


def _relevant_htf_index(htf_candles, timestamp):
    index = None
    for i, candle in enumerate(htf_candles):
        if candle.timestamp > timestamp:
            break
        index = i
    return index


@given(pair=paired_htf_ltf_series())
@settings(max_examples=30)
def test_alignment_detection_has_no_lookahead(pair):
    """Alignment inherits its k from its inputs — it composes CRT range
    detection on the HTF side (k=20, by start_index) and Model-1 detection
    on the LTF side (k=20, by anchor_index). An LTF signal's alignment tag
    is settled once BOTH (a) its own anchor is Model-1-settled and (b)
    every CRT range candidate that could still claim its relevant HTF
    candle as a purge (start_index up to relevant_index - 1) is itself
    CRT-range-settled. The insufficient_htf_data tail state (ADR-05) is a
    deliberate POLICY choice for the still-forming last HTF candle, not a
    lookahead violation, so it is excluded from the settled set rather
    than asserted against.
    """
    htf_series, ltf_series = pair
    htf_size = len(htf_series.candles)

    def _key(signal):
        # Overlapping, non-deduplicated LTF CRT range candidates (design
        # 4.4) can independently produce a purge_engulf signal at the SAME
        # anchor_index/direction — purge_target disambiguates between
        # those distinct candidates.
        return (signal.anchor_index, signal.direction, signal.confirmation_type, signal.purge_target)

    full_tags = tag_alignment(htf_series, ltf_series)
    full_by_key = {_key(t.ltf_signal): t for t in full_tags}

    for n_htf in range(1, htf_size + 1):
        n_ltf = n_htf * _ALIGNMENT_LTF_PER_HTF
        truncated_htf = htf_series.up_to(n_htf)
        truncated_ltf = ltf_series.up_to(n_ltf)
        truncated_tags = tag_alignment(truncated_htf, truncated_ltf)
        ltf_settled_boundary = n_ltf - _MODEL1_K - 1

        for tag in truncated_tags:
            signal = tag.ltf_signal
            if signal.anchor_index > ltf_settled_boundary:
                continue
            anchor_ts = ltf_series.candles[signal.anchor_index].timestamp
            relevant_index = _relevant_htf_index(truncated_htf.candles, anchor_ts)
            if relevant_index is None or relevant_index > n_htf - _CRT_RANGE_K:
                continue  # HTF context not yet settled for this candle

            key = _key(signal)
            assert key in full_by_key
            assert full_by_key[key] == tag


@given(
    open_=st.floats(min_value=1.0, max_value=2.0, allow_nan=False),
    close=st.floats(min_value=1.0, max_value=2.0, allow_nan=False),
    high_wick=st.floats(min_value=0.0, max_value=0.05, allow_nan=False),
    low_wick=st.floats(min_value=0.0, max_value=0.05, allow_nan=False),
    direction=st.sampled_from(["bullish", "bearish"]),
)
@settings(max_examples=100)
def test_wick_entry_never_equals_protected_extreme(open_, close, high_wick, low_wick, direction):
    """REQ-47.3: for a non-degenerate wick anchor (open != close), the
    wick-type entry price never equals protected_extreme -- the property
    that makes REQ-31's stop-loss placement never collide with REQ-47's
    entry price for a genuine (non-doji) wick signal. The doji case
    (open == close) is REQ-47.4's documented carve-out, pinned separately
    by a deterministic test in test_backtest_levels.py.
    """
    assume(open_ != close)
    anchor = Candle(
        timestamp=datetime(2026, 1, 1),
        open=open_,
        close=close,
        high=max(open_, close) + high_wick,
        low=min(open_, close) - low_wick,
    )
    protected_extreme = anchor.low if direction == "bullish" else anchor.high

    entry = entry_price(anchor, direction, "wick")

    assert entry != protected_extreme


@st.composite
def series_with_anchor_and_retest(draw, min_size=5, max_size=30):
    series = draw(ohlc_series(min_size=min_size, max_size=max_size))
    n = len(series.candles)
    anchor_index = draw(st.integers(min_value=0, max_value=n - 3))
    retest_index = draw(st.integers(min_value=anchor_index + 1, max_value=n - 1))
    direction = draw(st.sampled_from(["bullish", "bearish"]))
    return series, anchor_index, retest_index, direction


@given(case=series_with_anchor_and_retest())
@settings(max_examples=100)
def test_stop_loss_swing_window_has_no_lookahead(case):
    """REQ-31/REQ-37 regression: `stop_loss`'s swing-window search must
    settle on data knowable strictly before candle `retest_index` opens
    (`series.up_to(retest_index)`) -- a swing that only becomes confirmable
    once candle `retest_index` (or later) is visible must never change the
    computed stop_loss. Checked by comparing the FULL series against the
    `up_to(retest_index)` truncation: since a trade can fill AT
    `retest_index` itself (REQ-50.1), any swing only confirmable from
    `retest_index` onward is exactly the lookahead this REQ forbids -- the
    two computations must be identical."""
    series, anchor_index, retest_index, direction = case
    anchor = series.candles[anchor_index]
    config = BacktestConfig()

    full_swings = detect_swings(series)
    known_swings = detect_swings(series.up_to(retest_index))

    stop_full = stop_loss(
        anchor, direction, full_swings, [s.index for s in full_swings],
        anchor_index, retest_index, series.candles, config,
    )
    stop_known = stop_loss(
        anchor, direction, known_swings, [s.index for s in known_swings],
        anchor_index, retest_index, series.up_to(retest_index).candles, config,
    )

    assert stop_full == stop_known


@given(pair=paired_htf_ltf_series())
@settings(max_examples=30)
def test_backtest_resolution_is_monotone_in_series_length(pair):
    """Backtest no-lookahead monotonicity (S-000, design/test-plan): the
    candidate population is fixed on the FULL pair (isolating simulation's
    own data use from detection's, already covered by the properties
    above); every trade a truncated run finds must exist, unchanged on its
    settled fields, in the full run — more data never revokes, re-fills,
    or re-prices an already-opened trade; an open trade may still resolve
    once more data arrives, so nothing is asserted for it.
    """
    htf_series, ltf_series = pair
    config = DetectorConfig()
    population = tag_alignment(htf_series, ltf_series)
    if not population:
        return
    n_min = max(s.ltf_signal.anchor_index for s in population) + 1
    if n_min > len(ltf_series.candles):
        return

    trades_full, report_full = simulate(population, ltf_series, config)
    by_id_full = {t.signal_id: t for t in trades_full}

    for n in range(n_min, len(ltf_series.candles) + 1):
        trades_n, report_n = simulate(population, ltf_series.up_to(n), config)

        for trade_n in trades_n:
            assert trade_n.signal_id in by_id_full
            trade_full = by_id_full[trade_n.signal_id]
            assert trade_n.entry_index == trade_full.entry_index
            assert (trade_n.entry_price, trade_n.stop_loss, trade_n.take_profit) == (
                trade_full.entry_price, trade_full.stop_loss, trade_full.take_profit
            )
            if trade_n.outcome != "open":
                assert (
                    trade_n.exit_index, trade_n.exit_price, trade_n.outcome,
                    trade_n.r_multiple, trade_n.ambiguous_bar, trade_n.gap_filled,
                ) == (
                    trade_full.exit_index, trade_full.exit_price, trade_full.outcome,
                    trade_full.r_multiple, trade_full.ambiguous_bar, trade_full.gap_filled,
                )

        assert report_n.signals_considered == report_full.signals_considered
        assert report_n.excluded_no_crt_range == report_full.excluded_no_crt_range
        assert report_n.excluded_unaligned == report_full.excluded_unaligned
        assert report_n.excluded_never_confirmed == report_full.excluded_never_confirmed
        assert report_n.excluded_duplicate == report_full.excluded_duplicate
        assert report_n.excluded_kill_zone == report_full.excluded_kill_zone


@given(pair=paired_htf_ltf_series())
@settings(max_examples=30)
def test_backtest_exit_is_local_to_its_own_window(pair):
    """Exit locality (S-000, design/test-plan): re-running simulate() on a
    series truncated to exactly a trade's own exit candle reproduces the
    same entry/exit/outcome — every stop-anchor swing that fed the trade's
    bracket is already confirmed within that truncation (design's ADR-05
    derivation), so no carve-out is needed."""
    htf_series, ltf_series = pair
    config = DetectorConfig()
    population = tag_alignment(htf_series, ltf_series)
    if not population:
        return
    n_min = max(s.ltf_signal.anchor_index for s in population) + 1
    if n_min > len(ltf_series.candles):
        return

    trades_full, _ = simulate(population, ltf_series, config)

    for trade in trades_full:
        if trade.exit_index is None:
            continue
        truncated_series = ltf_series.up_to(trade.exit_index + 1)
        # Other candidates in the fixed population may anchor later than
        # this trade's own exit — irrelevant to whether THIS trade's exit
        # is local, so they're excluded to keep the truncated call in
        # bounds (mirrors n_min's role in the monotonicity property above).
        sub_population = [
            s for s in population if s.ltf_signal.anchor_index <= trade.exit_index
        ]
        trades_truncated, _ = simulate(sub_population, truncated_series, config)
        by_id = {t.signal_id: t for t in trades_truncated}

        assert trade.signal_id in by_id
        matched = by_id[trade.signal_id]
        assert (matched.entry_index, matched.exit_index, matched.outcome) == (
            trade.entry_index, trade.exit_index, trade.outcome
        )
