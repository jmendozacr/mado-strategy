"""Pure price-arithmetic derivations for the backtest layer (REQ-31, 47,
48): entry price, stop loss, take profit, risk:reward, net R-multiple.
"""

from datetime import datetime

from core.candle import Candle
from core.config import BacktestConfig
from primitives.swing import SwingPoint

from backtest.levels import entry_price, net_r_multiple, stop_loss


def _candle(open, high, low, close):
    return Candle(timestamp=datetime(2026, 1, 1, 12, 0, 0), open=open, high=high, low=low, close=close)


def test_stop_loss_anchors_to_purge_extreme_when_no_qualifying_swing_exists():
    """REQ-31.1 (grounded, charter-2 [00:18:46]): no swing low beyond
    protected_extreme within the anchor->entry window -> stop_loss anchors
    to the purge candle's own extreme, offset by sl_buffer_price."""
    anchor = _candle(open=1.0998, high=1.1005, low=1.0990, close=1.1002)

    stop = stop_loss(
        anchor, "bullish", swings=[], indices=[], anchor_index=1, retest_index=3,
        config=BacktestConfig(sl_buffer_price=0.0002),
    )

    assert stop == 1.0988


def test_entry_price_for_body_type_is_anchor_open():
    """REQ-47.1 (happy, body)."""
    anchor = _candle(open=1.0998, high=1.1005, low=1.0990, close=1.1002)

    assert entry_price(anchor, "bullish", "body") == 1.0998


def test_entry_price_for_wick_type_is_the_retest_side_body_boundary():
    """REQ-47.2 (happy, wick): bullish wick entry is the retest-side body
    boundary (max(open, close)), NEVER protected_extreme (the anchor's
    low)."""
    anchor = _candle(open=1.0998, high=1.1005, low=1.0990, close=1.1002)

    price = entry_price(anchor, "bullish", "wick")

    assert price == 1.1002
    assert price != anchor.low  # never protected_extreme


def test_stop_loss_anchors_to_single_qualifying_swing():
    """REQ-31.2 (grounded, charter-2 [00:18:46], single-swing branch): a
    swing low beyond protected_extreme within [anchor_index, retest_index-2]
    -> stop_loss anchors to it instead of the purge extreme."""
    anchor = _candle(open=1.0998, high=1.1005, low=1.0990, close=1.1002)
    swings = [SwingPoint(index=2, price=1.0975, kind="low")]

    stop = stop_loss(
        anchor, "bullish", swings, indices=[s.index for s in swings], anchor_index=1, retest_index=4,
        config=BacktestConfig(sl_buffer_price=0.0002),
    )

    assert stop == 1.0973


def test_stop_loss_anchors_to_deepest_of_multiple_qualifying_swings():
    """REQ-31.4 (edge): the deepest qualifying swing wins over a shallower
    one, never the shallowest or first-detected."""
    anchor = _candle(open=1.0998, high=1.1005, low=1.0990, close=1.1002)
    swings = [
        SwingPoint(index=2, price=1.0975, kind="low"),
        SwingPoint(index=3, price=1.0960, kind="low"),
    ]

    stop = stop_loss(
        anchor, "bullish", swings, indices=[s.index for s in swings], anchor_index=1, retest_index=5,
        config=BacktestConfig(sl_buffer_price=0.0002),
    )

    assert stop == 1.0958


def test_stop_loss_bearish_anchors_to_deepest_of_multiple_qualifying_swings():
    """REQ-31.4 (edge, bearish branch): mirrors the bullish deepest-swing
    test — for a short, "deepest" means the HIGHEST qualifying swing high,
    never the lower/shallower one or the first-detected."""
    anchor = _candle(open=1.1002, high=1.1010, low=1.0995, close=1.0998)
    swings = [
        SwingPoint(index=2, price=1.1025, kind="high"),
        SwingPoint(index=3, price=1.1040, kind="high"),
    ]

    stop = stop_loss(
        anchor, "bearish", swings, indices=[s.index for s in swings], anchor_index=1, retest_index=5,
        config=BacktestConfig(sl_buffer_price=0.0002),
    )

    assert stop == 1.1042


def test_wick_entry_and_purge_extreme_stop_yield_the_real_risk_distance():
    """REQ-31.3 (edge, regression): a wick-type entry price diverges from
    protected_extreme, so risk is the genuine distance between the two
    computed levels, not the sl_buffer_price constant alone."""
    anchor = _candle(open=1.0998, high=1.1005, low=1.0990, close=1.1002)

    entry = entry_price(anchor, "bullish", "wick")
    stop = stop_loss(
        anchor, "bullish", swings=[], indices=[], anchor_index=1, retest_index=3,
        config=BacktestConfig(sl_buffer_price=0.0002),
    )

    assert entry == 1.1002
    assert stop == 1.0988
    assert abs((entry - stop) - 0.0014) < 1e-9


def test_doji_anchor_entry_equals_protected_extreme_but_risk_still_holds():
    """REQ-47.4 (edge, doji carve-out): a doji anchor (open==close==low)
    permits entry_price == protected_extreme -- the one documented
    exception to REQ-47.3's non-degeneracy -- but risk >= sl_buffer_price
    still holds because the buffer is applied unconditionally."""
    anchor = _candle(open=1.0990, high=1.1005, low=1.0990, close=1.0990)
    config = BacktestConfig(sl_buffer_price=0.0002)

    entry = entry_price(anchor, "bullish", "wick")
    stop = stop_loss(anchor, "bullish", swings=[], indices=[], anchor_index=1, retest_index=3, config=config)

    assert entry == anchor.low  # the documented doji exception
    assert entry - stop >= config.sl_buffer_price - 1e-9  # float64 tolerance on an exact-equality boundary


def test_net_r_multiple_nets_out_trading_cost_once_at_closure():
    """REQ-48.1 (happy): trading_cost_price=0.00007, risk=0.0014, gross R=3.0
    -> net R=2.95."""
    entry, stop = 1.1002, 1.0988  # risk = 0.0014
    exit_price = entry + 3.0 * (entry - stop)  # gross R = 3.0 for a bullish trade

    net = net_r_multiple(entry, exit_price, stop, "bullish", trading_cost_price=0.00007)

    assert abs(net - 2.95) < 1e-9


def test_net_r_multiple_at_default_zero_cost_is_bit_identical_to_gross():
    """REQ-48.2 (edge, default neutrality): trading_cost_price=0.0 (the
    BacktestConfig default) collapses the net formula to the gross one."""
    entry, exit_price, stop = 1.1002, 1.1030, 1.0988

    net = net_r_multiple(entry, exit_price, stop, "bullish", trading_cost_price=0.0)
    gross = (exit_price - entry) / abs(entry - stop)

    assert net == gross
