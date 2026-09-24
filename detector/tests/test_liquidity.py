import dataclasses

from fixtures.synthetic import CandleSeriesBuilder

from primitives.liquidity import LiquidityCandidate, detect_liquidity_candidates


def _series(*bodies):
    builder = CandleSeriesBuilder()
    for body in bodies:
        builder.candle(**body)
    return builder.build()


_C0 = dict(open=1.1000, high=1.1020, low=1.0980, close=1.1010)
_C1 = dict(open=1.1010, high=1.1035, low=1.1005, close=1.1015)
_C2 = dict(open=1.1015, high=1.1030, low=1.0990, close=1.1000)


# --- REQ-LIQ-01: candidate emission per closed candle ------------------------

def test_n_candles_yield_2n_candidates():
    """REQ-LIQ-01.1 (LC2)."""
    series = _series(_C0, _C1, _C2)

    candidates = detect_liquidity_candidates(series)

    assert len(candidates) == 6


def test_single_candle_yields_two_candidates():
    """REQ-LIQ-01.2 (LC1): no 'previous candle' relationship is required —
    unlike Bias, a lone candle's own high/low are already valid
    observations."""
    series = _series(_C0)

    candidates = detect_liquidity_candidates(series)

    assert len(candidates) == 2
    assert {c.kind for c in candidates} == {"high", "low"}


def test_empty_series_yields_no_candidates():
    series = _series()

    assert detect_liquidity_candidates(series) == []


def test_ancient_candle_still_contributes_a_candidate():
    """REQ-LIQ-01.3 (LC9, crucial): historical candidate existence != a
    currently-relevant short-term DOL. V1 makes no relevance claim, so a
    candle far back in the series is not excluded."""
    filler = dict(open=1.1000, high=1.1005, low=1.0995, close=1.1000)
    series = _series(_C0, *([filler] * 200))

    candidates = detect_liquidity_candidates(series)

    assert any(c.source_index == 0 and c.kind == "high" and c.price == 1.1020 for c in candidates)
    assert any(c.source_index == 0 and c.kind == "low" and c.price == 1.0980 for c in candidates)


def test_gap_between_candles_has_no_special_rule():
    """REQ-LIQ-01.4 (LC8): a gap candle's high/low is computed identically
    to any other candle."""
    gap = dict(open=1.1200, high=1.1210, low=1.1195, close=1.1205)
    series = _series(_C0, gap)

    candidates = detect_liquidity_candidates(series)

    gap_high = next(c for c in candidates if c.source_index == 1 and c.kind == "high")
    gap_low = next(c for c in candidates if c.source_index == 1 and c.kind == "low")
    assert gap_high.price == 1.1210
    assert gap_low.price == 1.1195


# --- REQ-LIQ-02: candidate price exactness -----------------------------------

def test_candidate_price_equals_source_high_low_exactly():
    series = _series(_C0)

    candidates = detect_liquidity_candidates(series)

    high = next(c for c in candidates if c.kind == "high")
    low = next(c for c in candidates if c.kind == "low")
    assert high.price == _C0["high"]
    assert low.price == _C0["low"]


# --- REQ-LIQ-03: identity, no price-based deduplication ----------------------

def test_equal_highs_across_candles_are_not_deduplicated():
    """REQ-LIQ-03.1 (LC3)."""
    same_high_a = dict(open=1.1000, high=1.1050, low=1.0990, close=1.1010)
    same_high_b = dict(open=1.1010, high=1.1050, low=1.1000, close=1.1020)
    series = _series(same_high_a, same_high_b)

    candidates = detect_liquidity_candidates(series)
    highs = [c for c in candidates if c.kind == "high"]

    assert len(highs) == 2
    assert {h.source_index for h in highs} == {0, 1}
    assert all(h.price == 1.1050 for h in highs)


def test_equal_lows_across_candles_are_not_deduplicated():
    """REQ-LIQ-03.2 (LC4), mirror."""
    same_low_a = dict(open=1.1010, high=1.1020, low=1.0950, close=1.1005)
    same_low_b = dict(open=1.1005, high=1.1015, low=1.0950, close=1.1000)
    series = _series(same_low_a, same_low_b)

    candidates = detect_liquidity_candidates(series)
    lows = [c for c in candidates if c.kind == "low"]

    assert len(lows) == 2
    assert {l.source_index for l in lows} == {0, 1}
    assert all(l.price == 1.0950 for l in lows)


# --- REQ-LIQ-04: flat candle --------------------------------------------------

def test_flat_candle_still_produces_distinct_high_and_low():
    """REQ-LIQ-04.1 (LC5): same price, distinct kind -- never collapsed."""
    flat = dict(open=1.1000, high=1.1000, low=1.1000, close=1.1000)
    series = _series(flat)

    candidates = detect_liquidity_candidates(series)

    assert len(candidates) == 2
    kinds = {c.kind for c in candidates}
    assert kinds == {"high", "low"}
    assert all(c.price == 1.1000 for c in candidates)


# --- REQ-LIQ-05: no lifecycle or selection semantics -------------------------

def test_liquidity_candidate_has_no_lifecycle_or_selection_fields():
    """REQ-LIQ-05.1: exactly kind, price, source_index -- no active,
    consumed, reached, expired, selected, direction, rank, score,
    distance, confidence, or timeframe_priority field."""
    field_names = {f.name for f in dataclasses.fields(LiquidityCandidate)}

    assert field_names == {"kind", "price", "source_index"}


# --- REQ-LIQ-08: deterministic output ordering -------------------------------

def test_candidates_ordered_by_source_index_then_high_before_low():
    series = _series(_C0, _C1)

    candidates = detect_liquidity_candidates(series)

    assert [(c.source_index, c.kind) for c in candidates] == [
        (0, "high"), (0, "low"), (1, "high"), (1, "low"),
    ]


# --- REQ-LIQ-09: no duplicate candidate for CRT overlap ----------------------

def test_no_crt_specific_candidate_type_exists():
    """REQ-LIQ-09.1: a candidate at a price that also happens to be a CRT
    High/Low is still just one generic LiquidityCandidate -- no separate
    CRT-tagged type or field exists (enforced structurally too: the
    `liquidity` module has no dependency on `primitives.crt_range`, per
    lint-imports)."""
    import primitives.liquidity as liquidity_module

    series = _series(_C0)
    candidates = detect_liquidity_candidates(series)

    assert all(c.kind in ("high", "low") for c in candidates)
    assert "crt_range" not in vars(liquidity_module)
