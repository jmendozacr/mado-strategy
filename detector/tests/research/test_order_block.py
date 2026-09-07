import itertools
import json
import os

from fixtures.synthetic import CandleSeriesBuilder

from research.order_block import (
    OrderBlock,
    _distance_to_zone,
    detect_order_blocks,
    is_active,
    select_nearest_active_order_block,
)


def _ob(direction="bullish", origin_index=0, top=1.0, bottom=0.0, expiry_index=None):
    return OrderBlock(direction=direction, origin_index=origin_index, top=top, bottom=bottom, expiry_index=expiry_index)


# ---------------------------------------------------------------------------
# detect_order_blocks
# ---------------------------------------------------------------------------


def test_detect_order_blocks_known_bullish_bos_shape():
    """Hand-verified: candle 1 forms a swing high (1.0980), known from i=2
    onward. Candle 3 CLOSES above it (1.1000) -> bullish BOS. Displacement
    over candles 1-3 (body sum 0.0055) clears ATR14 at i=3 (~0.00275).
    Walking back from i=2, candle 2 is the first bearish (opposing) candle
    -> Order Block zone = candle 2's [low, high] = [1.0955, 1.0975],
    origin_index=3 (the BOS candle itself), never invalidated (series ends
    right after)."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0950, high=1.0955, low=1.0945, close=1.0950)  # 0 — filler
        .candle(open=1.0955, high=1.0980, low=1.0950, close=1.0965)  # 1 — swing high (1.0980)
        .candle(open=1.0970, high=1.0975, low=1.0955, close=1.0960)  # 2 — bearish, becomes the OB candle
        .candle(open=1.0965, high=1.1010, low=1.0960, close=1.1000)  # 3 — closes beyond 1.0980 -> bullish BOS
        .build()
    )

    blocks = detect_order_blocks(series)

    assert len(blocks) == 1
    ob = blocks[0]
    assert ob.direction == "bullish"
    assert ob.origin_index == 3
    assert ob.top == 1.0975
    assert ob.bottom == 1.0955
    assert ob.expiry_index is None


def test_detect_order_blocks_no_swing_no_bos():
    """A flat/monotonic series with no swing ever formed -> never a BOS
    candidate (`last_high`/`last_low` stay None) -> no Order Blocks."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1005, low=1.0995, close=1.1002)
        .candle(open=1.1002, high=1.1007, low=1.0997, close=1.1004)
        .candle(open=1.1004, high=1.1009, low=1.0999, close=1.1006)
        .build()
    )

    assert detect_order_blocks(series) == []


# ---------------------------------------------------------------------------
# is_active
# ---------------------------------------------------------------------------


def test_is_active_true_when_origin_before_cutoff_and_never_expired():
    ob = _ob(origin_index=3, expiry_index=None)
    assert is_active(ob, cutoff_index=10) is True


def test_is_active_false_when_origin_after_cutoff():
    ob = _ob(origin_index=11, expiry_index=None)
    assert is_active(ob, cutoff_index=10) is False


def test_is_active_true_when_expiry_equals_cutoff_right_closed_boundary():
    """REQ-55.9-.11 precedent (`alignment.htf_ltf._key_level_credit_map`):
    "exclude only purges strictly after expiry" -- an Order Block expiring
    exactly AT cutoff_index is still active AT that index."""
    ob = _ob(origin_index=1, expiry_index=6)
    assert is_active(ob, cutoff_index=6) is True


def test_is_active_false_when_cutoff_strictly_after_expiry():
    ob = _ob(origin_index=1, expiry_index=6)
    assert is_active(ob, cutoff_index=7) is False


# ---------------------------------------------------------------------------
# select_nearest_active_order_block: A-L
# ---------------------------------------------------------------------------


def test_A_single_active_ob_selected():
    ob = _ob(origin_index=5, top=1.1050, bottom=1.1000)
    assert select_nearest_active_order_block([ob], entry_price=1.1025, cutoff_index=10) == ob


def test_B_price_below_zone_distance_is_bottom_minus_entry():
    ob = _ob(origin_index=5, top=1.1050, bottom=1.1000)
    entry_price = 1.0990
    assert _distance_to_zone(entry_price, ob) == 1.1000 - 1.0990
    assert select_nearest_active_order_block([ob], entry_price, cutoff_index=10) == ob


def test_C_price_above_zone_distance_is_entry_minus_top():
    ob = _ob(origin_index=5, top=1.1050, bottom=1.1000)
    entry_price = 1.1060
    assert _distance_to_zone(entry_price, ob) == 1.1060 - 1.1050
    assert select_nearest_active_order_block([ob], entry_price, cutoff_index=10) == ob


def test_D_price_inside_zone_distance_is_zero():
    ob = _ob(origin_index=5, top=1.1050, bottom=1.1000)
    assert _distance_to_zone(1.1025, ob) == 0.0
    assert select_nearest_active_order_block([ob], entry_price=1.1025, cutoff_index=10) == ob


def test_E_overlapping_obs_entry_inside_both_tie_break_higher_origin_wins():
    older = _ob(origin_index=5, top=1.1050, bottom=1.1000)
    newer = _ob(origin_index=8, top=1.1040, bottom=1.1010)
    entry_price = 1.1020  # inside both -> distance 0 for both
    result = select_nearest_active_order_block([older, newer], entry_price, cutoff_index=10)
    assert result == newer


def test_F_non_overlapping_obs_equal_distance_tie_break_higher_origin_wins():
    # entry_price=0.0 makes the tie float-exact: distance_below = 0-(-d) = d
    # (negation only, no rounding) and distance_above = d-0 = d, the same
    # literal -- any nonzero anchor risks the two subtraction orders landing
    # a ULP apart and silently NOT exercising the tie-break at all.
    below = _ob(direction="bullish", origin_index=3, top=-0.0010, bottom=-0.0020)
    above = _ob(direction="bearish", origin_index=9, top=0.0020, bottom=0.0010)
    entry_price = 0.0
    assert _distance_to_zone(entry_price, below) == _distance_to_zone(entry_price, above)
    result = select_nearest_active_order_block([below, above], entry_price, cutoff_index=10)
    assert result == above


def test_G_old_vs_recent_at_tie_asserts_temporal_criterion_explicitly():
    old_ob = _ob(origin_index=2, top=1.1010, bottom=1.1000)
    recent_ob = _ob(origin_index=50, top=1.1010, bottom=1.1000)
    entry_price = 1.1005  # inside both -> tied at distance 0
    result = select_nearest_active_order_block([old_ob, recent_ob], entry_price, cutoff_index=100)
    assert result.origin_index == 50
    assert result == recent_ob


def test_H_invalidated_ob_never_a_candidate_even_if_otherwise_nearest():
    expired_but_nearest = _ob(origin_index=2, top=1.1010, bottom=1.1000, expiry_index=5)
    far_but_active = _ob(origin_index=1, top=2.0100, bottom=2.0000, expiry_index=None)
    entry_price = 1.1005  # inside the expired zone, far from the active one
    result = select_nearest_active_order_block(
        [expired_but_nearest, far_but_active], entry_price, cutoff_index=6
    )
    assert result == far_but_active


def test_I_future_ob_never_a_candidate_even_if_otherwise_nearest():
    future_but_nearest = _ob(origin_index=20, top=1.1010, bottom=1.1000, expiry_index=None)
    far_but_active = _ob(origin_index=1, top=2.0100, bottom=2.0000, expiry_index=None)
    entry_price = 1.1005  # inside the future zone, far from the active one
    result = select_nearest_active_order_block(
        [future_but_nearest, far_but_active], entry_price, cutoff_index=10
    )
    assert result == far_but_active


def test_J_permutation_invariance():
    candidates = [
        _ob(origin_index=2, top=1.1010, bottom=1.1000, expiry_index=None),
        _ob(origin_index=5, top=1.1030, bottom=1.1020, expiry_index=3),  # expired, excluded
        _ob(origin_index=8, top=1.1010, bottom=1.1000, expiry_index=None),  # tied with the first
        _ob(origin_index=15, top=1.1010, bottom=1.1000, expiry_index=None),  # future, excluded
    ]
    entry_price = 1.1005
    cutoff_index = 10
    expected = select_nearest_active_order_block(candidates, entry_price, cutoff_index)
    assert expected is not None

    for permutation in itertools.permutations(candidates):
        assert select_nearest_active_order_block(list(permutation), entry_price, cutoff_index) == expected


def test_K_direction_plays_no_role_in_tie_break():
    """Same zone, tied at distance 0: bullish has the LOWER origin_index,
    bearish has the HIGHER one. A hypothetical direction-preferring rule
    (e.g. "prefer bullish") would pick the bullish candidate; the actual
    rule ignores direction entirely and picks by origin_index alone."""
    bullish_lower_origin = _ob(direction="bullish", origin_index=3, top=1.1010, bottom=1.1000)
    bearish_higher_origin = _ob(direction="bearish", origin_index=7, top=1.1010, bottom=1.1000)
    entry_price = 1.1005

    result = select_nearest_active_order_block(
        [bullish_lower_origin, bearish_higher_origin], entry_price, cutoff_index=10
    )

    assert result == bearish_higher_origin
    assert result.direction == "bearish"


def test_L_no_lookahead_appending_a_future_ob_never_changes_the_past_selection():
    base = [
        _ob(origin_index=2, top=1.1010, bottom=1.1000, expiry_index=None),
        _ob(origin_index=5, top=1.1030, bottom=1.1020, expiry_index=None),
    ]
    entry_price = 1.1005
    cutoff_index = 5

    before = select_nearest_active_order_block(base, entry_price, cutoff_index)

    future_ob = _ob(origin_index=cutoff_index + 1, top=1.1006, bottom=1.1004, expiry_index=None)
    after = select_nearest_active_order_block(base + [future_ob], entry_price, cutoff_index)

    assert before == after


def test_no_active_candidates_returns_none():
    ob = _ob(origin_index=20, top=1.1010, bottom=1.1000, expiry_index=None)  # future relative to cutoff
    assert select_nearest_active_order_block([ob], entry_price=1.1005, cutoff_index=5) is None


def test_empty_order_block_list_returns_none():
    assert select_nearest_active_order_block([], entry_price=1.1005, cutoff_index=5) is None


# ---------------------------------------------------------------------------
# Golden reconciliation fixture: real Model1Signals x real Daily Order
# Blocks (EURUSDm/GBPUSDm/DXYm merged pairs data). Regression guard against
# future silent drift in the selection rule -- no win/loss/R/PF/outcome
# anywhere in this fixture, by construction (see the generating script's
# report, not committed).
# ---------------------------------------------------------------------------

_GOLDEN_FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "nearest_ob_golden.json")


def test_golden_fixture_reproduces_every_recorded_selection():
    with open(_GOLDEN_FIXTURE_PATH, encoding="utf-8") as f:
        golden_rows = json.load(f)

    assert len(golden_rows) >= 20

    for row in golden_rows:
        candidates = [
            OrderBlock(
                direction=c["direction"],
                origin_index=c["origin_index"],
                top=c["top"],
                bottom=c["bottom"],
                expiry_index=None,  # already filtered to active-at-cutoff when the fixture was built
            )
            for c in row["candidates"]
        ]
        result = select_nearest_active_order_block(candidates, row["entry_price"], row["cutoff_index"])
        assert result is not None
        assert result.origin_index == row["selected_origin_index"], row["signal_id"]
        assert result.direction == row["selected_direction"], row["signal_id"]
