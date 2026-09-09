import dataclasses

from fixtures.synthetic import CandleSeriesBuilder

from primitives.bias import BiasEvidence, detect_bias_evidence


def _series(*bodies):
    builder = CandleSeriesBuilder()
    for body in bodies:
        builder.candle(**body)
    return builder.build()


_PREVIOUS = dict(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # range [1.0980, 1.1020]


# --- REQ-BIAS-01: close-relation partition -----------------------------------

def test_close_above_previous_high():
    """REQ-BIAS-01.1: close strictly beyond previous.high -> above."""
    series = _series(_PREVIOUS, dict(open=1.1015, high=1.1035, low=1.1010, close=1.1025))

    evidence = detect_bias_evidence(series)[0]

    assert evidence.close_relation == "above"


def test_close_below_previous_low():
    series = _series(_PREVIOUS, dict(open=1.0985, high=1.0990, low=1.0955, close=1.0965))

    evidence = detect_bias_evidence(series)[0]

    assert evidence.close_relation == "below"


def test_close_equals_previous_high_is_inside_not_above():
    """REQ-BIAS-01.2: boundary equality resolves to inside, not above — a
    closed range includes its own edges (consistent with REQ-OF-03.1's
    exact-equality-is-not-a-break convention)."""
    series = _series(_PREVIOUS, dict(open=1.1005, high=1.1020, low=1.1000, close=1.1020))

    evidence = detect_bias_evidence(series)[0]

    assert evidence.close_relation == "inside"


def test_close_equals_previous_low_is_inside_not_below():
    series = _series(_PREVIOUS, dict(open=1.0990, high=1.0995, low=1.0980, close=1.0980))

    evidence = detect_bias_evidence(series)[0]

    assert evidence.close_relation == "inside"


def test_flat_previous_candle_boundary_is_inside():
    """REQ-BIAS-01.3: previous.high == previous.low (degenerate point
    range) — the partition still applies without modification; equality
    at that single point is inside, same as any other boundary."""
    flat_previous = dict(open=1.1000, high=1.1000, low=1.1000, close=1.1000)
    series = _series(flat_previous, dict(open=1.1000, high=1.1005, low=1.0995, close=1.1000))

    evidence = detect_bias_evidence(series)[0]

    assert evidence.close_relation == "inside"


def test_gap_up_candle_is_above():
    """C12: a gap candle (current.low already beyond previous.high) is
    just a strong case of 'above' — no gap-specific rule is needed."""
    series = _series(_PREVIOUS, dict(open=1.1030, high=1.1045, low=1.1025, close=1.1040))

    evidence = detect_bias_evidence(series)[0]

    assert evidence.close_relation == "above"


# --- REQ-BIAS-02: close-derived signal ---------------------------------------

def test_above_yields_bullish_close_signal():
    series = _series(_PREVIOUS, dict(open=1.1015, high=1.1035, low=1.1010, close=1.1025))

    evidence = detect_bias_evidence(series)[0]

    assert evidence.close_signal == "bullish"


def test_below_yields_bearish_close_signal():
    series = _series(_PREVIOUS, dict(open=1.0985, high=1.0990, low=1.0955, close=1.0965))

    evidence = detect_bias_evidence(series)[0]

    assert evidence.close_signal == "bearish"


def test_inside_bullish_body_yields_bullish_close_signal():
    """REQ-BIAS-02.2: inside the previous range, current candle's own
    body color (close > open) drives the signal."""
    series = _series(_PREVIOUS, dict(open=1.0995, high=1.1015, low=1.0990, close=1.1005))

    evidence = detect_bias_evidence(series)[0]

    assert evidence.close_relation == "inside"
    assert evidence.close_signal == "bullish"


def test_inside_bearish_body_yields_bearish_close_signal():
    series = _series(_PREVIOUS, dict(open=1.1005, high=1.1015, low=1.0990, close=1.0995))

    evidence = detect_bias_evidence(series)[0]

    assert evidence.close_relation == "inside"
    assert evidence.close_signal == "bearish"


def test_inside_doji_body_yields_none_close_signal():
    """REQ-BIAS-02.3: current.close == current.open (doji/flat body) inside
    the previous range -> close_signal is None, not a fabricated default.
    Mirrors this repo's existing doji carve-out precedent (entries/model1.py
    REQ-47.4)."""
    series = _series(_PREVIOUS, dict(open=1.1000, high=1.1015, low=1.0990, close=1.1000))

    evidence = detect_bias_evidence(series)[0]

    assert evidence.close_relation == "inside"
    assert evidence.close_signal is None


# --- REQ-BIAS-03: wick-derived signal -----------------------------------------

def test_upper_wick_only_yields_bearish_wick_signal():
    series = _series(_PREVIOUS, dict(open=1.1000, high=1.1020, low=1.1000, close=1.1005))

    evidence = detect_bias_evidence(series)[0]

    assert evidence.wick_signal == "bearish"


def test_lower_wick_only_yields_bullish_wick_signal():
    series = _series(_PREVIOUS, dict(open=1.1005, high=1.1005, low=1.0985, close=1.1000))

    evidence = detect_bias_evidence(series)[0]

    assert evidence.wick_signal == "bullish"


def test_both_wicks_yield_conflict_not_a_resolved_direction():
    """REQ-BIAS-03.3: both wicks present -> 'conflict', NEVER resolved to
    bullish or bearish — the source states the two claims independently
    and never addresses simultaneity."""
    series = _series(_PREVIOUS, dict(open=1.1000, high=1.1015, low=1.0990, close=1.1005))

    evidence = detect_bias_evidence(series)[0]

    assert evidence.wick_signal == "conflict"


def test_no_wicks_yields_none_wick_signal():
    """REQ-BIAS-03.4: high == max(open, close) and low == min(open, close)
    (no wick on either side) -> None, not a fabricated direction."""
    series = _series(_PREVIOUS, dict(open=1.1000, high=1.1005, low=1.1000, close=1.1005))

    evidence = detect_bias_evidence(series)[0]

    assert evidence.wick_signal is None


def test_minimal_nonzero_wick_counts_identically_to_a_large_wick():
    """REQ-BIAS-03.5: no magnitude threshold — a wick of any strictly-
    positive size counts the same as a large one."""
    minimal = _series(_PREVIOUS, dict(open=1.1000, high=1.1005001, low=1.1000, close=1.1005))
    large = _series(_PREVIOUS, dict(open=1.1000, high=1.1100, low=1.1000, close=1.1005))

    assert detect_bias_evidence(minimal)[0].wick_signal == "bearish"
    assert detect_bias_evidence(large)[0].wick_signal == "bearish"


# --- REQ-BIAS-04: no cross-signal arbitration ---------------------------------

def test_bullish_close_signal_and_bearish_wick_signal_are_both_preserved():
    """REQ-BIAS-04.1: disagreement is recorded as-is, never resolved to a
    single final direction."""
    series = _series(_PREVIOUS, dict(open=1.1015, high=1.1035, low=1.1015, close=1.1025))

    evidence = detect_bias_evidence(series)[0]

    assert evidence.close_signal == "bullish"
    assert evidence.wick_signal == "bearish"


def test_bearish_close_signal_and_bullish_wick_signal_are_both_preserved():
    series = _series(_PREVIOUS, dict(open=1.0985, high=1.0985, low=1.0955, close=1.0965))

    evidence = detect_bias_evidence(series)[0]

    assert evidence.close_signal == "bearish"
    assert evidence.wick_signal == "bullish"


def test_inside_bullish_body_with_both_wicks_conflict_is_not_arbitrated():
    """E4/E6-style case: close_signal speaks (bullish, from body color),
    wick_signal internally conflicts (both wicks) -- no field collapses
    this into one verdict."""
    series = _series(_PREVIOUS, dict(open=1.0995, high=1.1015, low=1.0985, close=1.1005))

    evidence = detect_bias_evidence(series)[0]

    assert evidence.close_relation == "inside"
    assert evidence.close_signal == "bullish"
    assert evidence.wick_signal == "conflict"


# --- REQ-BIAS-05: no semantic horizon ------------------------------------------

def test_bias_evidence_has_no_horizon_or_arbitration_fields():
    """REQ-BIAS-05/REQ-BIAS-04: the record carries exactly observation_index,
    close_relation, close_signal, wick_signal -- no target_index, direction,
    confidence, score, weight, expiry, or state field."""
    field_names = {f.name for f in dataclasses.fields(BiasEvidence)}

    assert field_names == {"observation_index", "close_relation", "close_signal", "wick_signal"}


# --- REQ-BIAS-07: input/output cardinality -------------------------------------

def test_empty_series_returns_no_evidence():
    series = _series()

    assert detect_bias_evidence(series) == []


def test_single_candle_series_returns_no_evidence():
    """REQ-BIAS-07.1: index 0 never produces evidence -- there is no
    previous candle to compare against."""
    series = _series(_PREVIOUS)

    assert detect_bias_evidence(series) == []


def test_two_candle_series_returns_one_evidence_at_index_1():
    """REQ-BIAS-07.2."""
    series = _series(_PREVIOUS, dict(open=1.1015, high=1.1035, low=1.1010, close=1.1025))

    evidence = detect_bias_evidence(series)

    assert len(evidence) == 1
    assert evidence[0].observation_index == 1


def test_n_candles_yield_one_evidence_per_index_from_1_to_n_minus_1():
    series = _series(
        _PREVIOUS,
        dict(open=1.1015, high=1.1035, low=1.1010, close=1.1025),
        dict(open=1.1025, high=1.1030, low=1.1000, close=1.1005),
        dict(open=1.1005, high=1.1010, low=1.0960, close=1.0970),
    )

    evidence = detect_bias_evidence(series)

    assert [e.observation_index for e in evidence] == [1, 2, 3]
