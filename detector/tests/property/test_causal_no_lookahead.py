"""REQ-CAUSAL-20: the causal-path-only property-test oracle. Matches by
`(retest_index, anchor_index, direction)` — the causal EVENT-anchored key
— never `signal_id` (embeds the very `origin_index` under test) and never
`origin_index`/`purge_target` directly (would trivially pass by
construction).

Two independent axes, NOT lockstep truncation (`n_ltf = n_htf * 4`):
lockstep cannot express a mid-HTF-candle cutoff (B5, spec.md Section A),
which this oracle constructs directly by varying `n_htf` over EVERY value
(not multiples of the LTF-per-HTF ratio) while holding the LTF series
whole, and separately varying `n_ltf` over every value while holding the
HTF series whole. Each axis independently proves:

(a) no disappearance — a causally-admissible candidate present in a
    shorter causal run remains present, with identical `CandidateIdentity`
    and economic fields, in every longer run once its own settlement bound
    is reached;
(b) no phantom creation — a candidate absent from a shorter causal run's
    admissible set never "was there all along" purely from more data
    becoming available.

Settlement bound: derived from H-A's OWN closure rule (`resolved_at_index`
+ 1 HTF candles needed) for the HTF axis, and from the event index itself
(`retest_index + 1` LTF candles needed) for the LTF axis — grounded in the
full-series computation, mirroring this repo's own no-lookahead property
family idiom (`tests/property/test_no_lookahead.py`).
"""

from datetime import datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from backtest.population import build_stage6_population
from causal.generate import generate_causal_aligned_signals
from core.candle import Candle, OHLCSeries
from core.config import DetectorConfig

_LTF_PER_HTF = 4


def _ohlc_candle(draw, index: int, base_hour: int = 0) -> Candle:
    open_ = draw(st.floats(min_value=1.0, max_value=2.0, allow_nan=False))
    close = draw(st.floats(min_value=1.0, max_value=2.0, allow_nan=False))
    wick_up = draw(st.floats(min_value=0.0, max_value=0.05, allow_nan=False))
    wick_down = draw(st.floats(min_value=0.0, max_value=0.05, allow_nan=False))
    return Candle(
        timestamp=datetime(2026, 1, 1) + timedelta(hours=base_hour + index),
        open=open_, high=max(open_, close) + wick_up, low=min(open_, close) - wick_down, close=close,
    )


@st.composite
def paired_htf_ltf_series(draw, min_htf=3, max_htf=10):
    """Same nesting scheme as `test_no_lookahead.py`'s own strategy (each
    HTF candle spans `_LTF_PER_HTF` LTF candles) — this file only differs
    in how the resulting pair is EXERCISED (independent-axis truncation),
    not in how it is generated."""
    htf_size = draw(st.integers(min_value=min_htf, max_value=max_htf))
    htf_candles = tuple(_ohlc_candle(draw, i) for i in range(htf_size))
    htf_series = OHLCSeries(candles=htf_candles, instrument="EURUSD", timeframe="4H")

    ltf_step = timedelta(hours=4) / _LTF_PER_HTF
    ltf_candles = []
    for htf_index, htf_candle in enumerate(htf_candles):
        for sub in range(_LTF_PER_HTF):
            ltf_index = htf_index * _LTF_PER_HTF + sub
            base = _ohlc_candle(draw, ltf_index)
            ltf_candles.append(
                Candle(
                    timestamp=htf_candle.timestamp + sub * ltf_step,
                    open=base.open, high=base.high, low=base.low, close=base.close,
                )
            )
    ltf_series = OHLCSeries(candles=tuple(ltf_candles), instrument="EURUSD", timeframe="15M")
    return htf_series, ltf_series


def _candidate_key(candidate):
    return (candidate.retest_index, candidate.anchor_index, candidate.direction)


def _full_population_and_htf_bounds(htf_series, ltf_series, config):
    full_tags = generate_causal_aligned_signals(ltf_series, htf_series)
    full_population = build_stage6_population(full_tags, ltf_series, config)
    full_by_key = {_candidate_key(c): c for c in full_population.candidates}

    tags_by_key = {}
    for tagged in full_tags:
        if tagged.ltf_signal.retest_index is None:
            continue
        key = (tagged.ltf_signal.retest_index, tagged.ltf_signal.anchor_index, tagged.ltf_signal.direction)
        tags_by_key[key] = tagged

    htf_bound = {}
    for key in full_by_key:
        tagged = tags_by_key.get(key)
        htf_bound[key] = (tagged.htf_context.resolved_at_index + 1) if tagged and tagged.htf_context else None
    return full_by_key, htf_bound


@given(pair=paired_htf_ltf_series())
@settings(max_examples=30)
def test_causal_generation_has_no_lookahead_on_the_htf_axis(pair):
    """Varies `n_htf` over EVERY value (not a multiple of `_LTF_PER_HTF`)
    while the LTF series stays whole -- a genuine mid-HTF-candle cutoff,
    which lockstep truncation cannot express."""
    htf_series, ltf_series = pair
    config = DetectorConfig()
    full_by_key, htf_bound = _full_population_and_htf_bounds(htf_series, ltf_series, config)

    for n_htf in range(2, len(htf_series.candles) + 1):
        truncated_tags = generate_causal_aligned_signals(ltf_series, htf_series.up_to(n_htf))
        truncated_population = build_stage6_population(truncated_tags, ltf_series, config)
        truncated_by_key = {_candidate_key(c): c for c in truncated_population.candidates}

        for key, candidate in truncated_by_key.items():
            assert key in full_by_key, f"phantom candidate at n_htf={n_htf}: {key}"
            bound = htf_bound[key]
            if bound is None or n_htf >= bound:
                assert candidate == full_by_key[key], f"identity/economics drifted at n_htf={n_htf}: {key}"

        for key, full_candidate in full_by_key.items():
            bound = htf_bound[key]
            if bound is not None and n_htf < bound:
                continue  # not yet settled on the HTF axis
            assert key in truncated_by_key, f"disappeared at n_htf={n_htf}: {key}"


@given(pair=paired_htf_ltf_series())
@settings(max_examples=30)
def test_causal_generation_has_no_lookahead_on_the_ltf_axis(pair):
    """Varies `n_ltf` over every value while the HTF series stays whole --
    the LTF-side mirror of REQ-CAUSAL-01/02/03/07."""
    htf_series, ltf_series = pair
    config = DetectorConfig()
    full_by_key, _ = _full_population_and_htf_bounds(htf_series, ltf_series, config)

    for n_ltf in range(4, len(ltf_series.candles) + 1):
        truncated_tags = generate_causal_aligned_signals(ltf_series.up_to(n_ltf), htf_series)
        truncated_population = build_stage6_population(truncated_tags, ltf_series.up_to(n_ltf), config)
        truncated_by_key = {_candidate_key(c): c for c in truncated_population.candidates}

        for key, candidate in truncated_by_key.items():
            assert key in full_by_key, f"phantom candidate at n_ltf={n_ltf}: {key}"
            assert candidate == full_by_key[key], f"identity/economics drifted at n_ltf={n_ltf}: {key}"

        for key, full_candidate in full_by_key.items():
            retest_index = key[0]
            if n_ltf < retest_index + 1:
                continue  # event hasn't happened within this LTF prefix yet
            assert key in truncated_by_key, f"disappeared at n_ltf={n_ltf}: {key}"
