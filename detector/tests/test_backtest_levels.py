"""Pure price-arithmetic derivations for the backtest layer (REQ-31, 47,
48): entry price, stop loss, take profit, risk:reward, net R-multiple.
"""

from datetime import datetime

from core.candle import Candle
from core.config import BacktestConfig
from primitives.swing import SwingPoint

from backtest.levels import entry_price, net_r_multiple, partial_price, stop_loss


def _candle(open, high, low, close):
    return Candle(timestamp=datetime(2026, 1, 1, 12, 0, 0), open=open, high=high, low=low, close=close)


def _uniform_atr_candles(reference: Candle, count: int) -> tuple[Candle, ...]:
    """`count` candles sharing `reference`'s high/low, each candle's own
    close pinned to its own open (always inside [low, high]) -- guarantees
    every one of them has true_range == reference.high - reference.low, so
    atr() over this tuple equals that same constant regardless of its
    lookback window or which index within `count` it is evaluated at."""
    return tuple(
        Candle(timestamp=reference.timestamp, open=reference.open, high=reference.high,
               low=reference.low, close=reference.open)
        for _ in range(count)
    )


def test_stop_loss_buffer_scales_with_series_atr_on_a_high_absolute_price_series():
    """Bug fix: sl_buffer_price (former bare default 0.0002) was a fixed
    price-unit constant sized for a ~1.05-1.20 FX pair. On a high-absolute-
    price series like DXYm (~90-110), that same constant sits ~180-220x
    smaller relative to the instrument's own volatility, collapsing the risk
    denominator (entry - stop) toward zero and producing absurd R-multiples.
    The buffer must scale with the series' own ATR(14) at anchor_index
    (sl_buffer_atr_multiple * atr(candles, anchor_index)), never stay pinned
    to an absolute constant regardless of price scale."""
    anchor = _candle(open=100.00, high=101.00, low=99.00, close=100.50)  # true_range = 2.00
    candles = _uniform_atr_candles(anchor, 2)  # ATR(14) at index 1 == 2.00
    config = BacktestConfig(sl_buffer_atr_multiple=0.3)

    stop = stop_loss(
        anchor, "bullish", swings=[], indices=[], anchor_index=1, retest_index=3,
        candles=candles, config=config,
    )

    buffer = anchor.low - stop
    assert abs(buffer - 0.6) < 1e-9  # 0.3 * ATR(14)=2.00 -- proportional to THIS series' own volatility
    assert buffer > 0.0002 * 100  # sanity: not left pinned to the old bare constant on a 100-scale series


def test_stop_loss_anchors_to_purge_extreme_when_no_qualifying_swing_exists():
    """REQ-31.1 (grounded, charter-2 [00:18:46]): no swing low beyond
    protected_extreme within the anchor->entry window -> stop_loss anchors
    to the purge candle's own extreme, offset by sl_buffer_atr_multiple *
    ATR(14)."""
    anchor = _candle(open=1.0998, high=1.1005, low=1.0990, close=1.1002)
    candles = _uniform_atr_candles(anchor, 2)  # ATR(14) at index 1 == 0.0015 (anchor's own high - low)

    stop = stop_loss(
        anchor, "bullish", swings=[], indices=[], anchor_index=1, retest_index=3,
        candles=candles, config=BacktestConfig(sl_buffer_atr_multiple=0.3),
    )

    assert abs(stop - 1.09855) < 1e-9  # 1.0990 - 0.3 * 0.0015


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
    candles = _uniform_atr_candles(anchor, 2)  # ATR(14) at index 1 == 0.0015
    swings = [SwingPoint(index=2, price=1.0975, kind="low")]

    stop = stop_loss(
        anchor, "bullish", swings, indices=[s.index for s in swings], anchor_index=1, retest_index=4,
        candles=candles, config=BacktestConfig(sl_buffer_atr_multiple=0.3),
    )

    assert abs(stop - 1.09705) < 1e-9  # 1.0975 - 0.3 * 0.0015


def test_stop_loss_anchors_to_deepest_of_multiple_qualifying_swings():
    """REQ-31.4 (edge): the deepest qualifying swing wins over a shallower
    one, never the shallowest or first-detected."""
    anchor = _candle(open=1.0998, high=1.1005, low=1.0990, close=1.1002)
    candles = _uniform_atr_candles(anchor, 2)  # ATR(14) at index 1 == 0.0015
    swings = [
        SwingPoint(index=2, price=1.0975, kind="low"),
        SwingPoint(index=3, price=1.0960, kind="low"),
    ]

    stop = stop_loss(
        anchor, "bullish", swings, indices=[s.index for s in swings], anchor_index=1, retest_index=5,
        candles=candles, config=BacktestConfig(sl_buffer_atr_multiple=0.3),
    )

    assert abs(stop - 1.09555) < 1e-9  # 1.0960 - 0.3 * 0.0015


def test_stop_loss_bearish_anchors_to_deepest_of_multiple_qualifying_swings():
    """REQ-31.4 (edge, bearish branch): mirrors the bullish deepest-swing
    test — for a short, "deepest" means the HIGHEST qualifying swing high,
    never the lower/shallower one or the first-detected."""
    anchor = _candle(open=1.1002, high=1.1010, low=1.0995, close=1.0998)
    candles = _uniform_atr_candles(anchor, 2)  # ATR(14) at index 1 == 0.0015 (same width as the bullish anchor)
    swings = [
        SwingPoint(index=2, price=1.1025, kind="high"),
        SwingPoint(index=3, price=1.1040, kind="high"),
    ]

    stop = stop_loss(
        anchor, "bearish", swings, indices=[s.index for s in swings], anchor_index=1, retest_index=5,
        candles=candles, config=BacktestConfig(sl_buffer_atr_multiple=0.3),
    )

    assert abs(stop - 1.10445) < 1e-9  # 1.1040 + 0.3 * 0.0015


def test_wick_entry_and_purge_extreme_stop_yield_the_real_risk_distance():
    """REQ-31.3 (edge, regression): a wick-type entry price diverges from
    protected_extreme, so risk is the genuine distance between the two
    computed levels, not the sl_buffer_atr_multiple * ATR term alone."""
    anchor = _candle(open=1.0998, high=1.1005, low=1.0990, close=1.1002)
    candles = _uniform_atr_candles(anchor, 2)  # ATR(14) at index 1 == 0.0015

    entry = entry_price(anchor, "bullish", "wick")
    stop = stop_loss(
        anchor, "bullish", swings=[], indices=[], anchor_index=1, retest_index=3,
        candles=candles, config=BacktestConfig(sl_buffer_atr_multiple=0.3),
    )

    assert entry == 1.1002
    assert abs(stop - 1.09855) < 1e-9  # 1.0990 - 0.3 * 0.0015
    assert abs((entry - stop) - 0.00165) < 1e-9


def test_doji_anchor_entry_equals_protected_extreme_but_risk_still_holds():
    """REQ-47.4 (edge, doji carve-out): a doji anchor (open==close==low)
    permits entry_price == protected_extreme -- the one documented
    exception to REQ-47.3's non-degeneracy -- but risk >= the ATR-relative
    buffer still holds because the buffer is applied unconditionally."""
    anchor = _candle(open=1.0990, high=1.1005, low=1.0990, close=1.0990)
    candles = _uniform_atr_candles(anchor, 2)  # ATR(14) at index 1 == 0.0015
    config = BacktestConfig(sl_buffer_atr_multiple=0.3)
    expected_buffer = config.sl_buffer_atr_multiple * 0.0015

    entry = entry_price(anchor, "bullish", "wick")
    stop = stop_loss(
        anchor, "bullish", swings=[], indices=[], anchor_index=1, retest_index=3, candles=candles, config=config
    )

    assert entry == anchor.low  # the documented doji exception
    assert entry - stop >= expected_buffer - 1e-9  # float64 tolerance on an exact-equality boundary


def test_net_r_multiple_nets_out_trading_cost_once_at_closure():
    """REQ-48.1 (happy): trading_cost_price=0.00007, risk=0.0014, gross R=3.0
    -> net R=2.95."""
    entry, stop = 1.1002, 1.0988  # risk = 0.0014
    exit_price = entry + 3.0 * (entry - stop)  # gross R = 3.0 for a bullish trade

    net = net_r_multiple(entry, exit_price, stop, "bullish", trading_cost_price=0.00007)

    assert abs(net - 2.95) < 1e-9


def test_partial_price_is_entry_to_target_midpoint():
    """REQ-68 (V2): partial_price is the midpoint between the trade's OWN
    entry_price and take_profit -- not the HTF CRT range's midpoint (V1's
    formula, falsified by REQ-70's property test on real data). Verified
    for both a bullish (target above entry) and bearish (target below
    entry) trade -- the formula itself is direction-agnostic, since
    entry/take_profit already encode direction."""
    assert abs(partial_price(entry_price=1.1010, take_profit=1.1100) - 1.10550) < 1e-9
    assert abs(partial_price(entry_price=1.1010, take_profit=1.0900) - 1.09550) < 1e-9


def test_net_r_multiple_at_default_zero_cost_is_bit_identical_to_gross():
    """REQ-48.2 (edge, default neutrality): trading_cost_price=0.0 (the
    BacktestConfig default) collapses the net formula to the gross one."""
    entry, exit_price, stop = 1.1002, 1.1030, 1.0988

    net = net_r_multiple(entry, exit_price, stop, "bullish", trading_cost_price=0.0)
    gross = (exit_price - entry) / abs(entry - stop)

    assert net == gross
