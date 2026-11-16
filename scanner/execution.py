"""Pure, MT5-independent order-sizing/type logic (odd/tasks/scanner-auto-
execution.md S3/S4) -- never calls MetaTrader5 itself. Account balance and
symbol trade specs are plain numbers passed in by the caller (mt5_feed.py
owns fetching them), exactly mirroring rules.py's own "pure filter, never
reimplements detection" boundary.
"""
import math


def calculate_lot_size(
    *, balance: float, risk_pct: float, entry_price: float, stop_loss: float,
    tick_value: float, tick_size: float, volume_min: float, volume_max: float, volume_step: float,
) -> float | None:
    """`None` means "do not place this trade" -- either the stop distance
    is zero/invalid (can't size risk against no risk) or the real target
    lot size rounds down below `volume_min`. Forcing `volume_min` in that
    second case would silently risk MORE than `risk_pct`, which is worse
    than skipping the trade (S3) -- a human reviewing a skipped alert can
    still decide to take it manually at a size they choose.

    Rounds DOWN to `volume_step`, never up or to the nearest step, so the
    real risk taken is never more than `risk_pct` of `balance` -- only
    ever equal or (due to the floor) slightly less."""
    stop_distance = abs(entry_price - stop_loss)
    if stop_distance <= 0:
        return None

    risk_amount = balance * risk_pct / 100.0
    ticks = stop_distance / tick_size
    risk_per_lot = ticks * tick_value
    raw_lots = risk_amount / risk_per_lot

    # round() before floor() absorbs binary-float noise (e.g. 0.0020/0.00001
    # landing on 199.99999999999997 instead of 200) without masking a
    # genuine fractional step -- real-world specs never carry more than a
    # handful of significant digits, so 9 decimal places of slack can
    # never hide an intentional fraction.
    stepped = math.floor(round(raw_lots / volume_step, 9)) * volume_step
    stepped = round(stepped, 8)  # clear the float/floor binary-rounding noise before the volume_min compare
    if stepped < volume_min:
        return None
    return min(stepped, volume_max)


def pending_order_type(direction: str, *, entry_price: float, current_price: float) -> str:
    """S4: a PENDING order, chosen by comparing `entry_price` to the
    CURRENT market price -- covers both `entry_type="wick"` and `"body"`
    signals (entries/model1.py) with one rule, never special-cased per
    entry_type. Caller maps the returned string to the real
    `mt5.ORDER_TYPE_*` constant (keeps this module import-free of
    MetaTrader5, like the rest of its pure functions)."""
    if direction == "bullish":
        return "BUY_LIMIT" if entry_price < current_price else "BUY_STOP"
    return "SELL_LIMIT" if entry_price > current_price else "SELL_STOP"


def partial_close_volume(
    *, volume: float, partial_fraction: float, volume_step: float, volume_min: float,
) -> float | None:
    """odd/tasks/scanner-breakeven-after-partial.md T1: the volume to
    CLOSE for the partial leg -- `None` means "skip the partial, leave
    the position whole" (too small to split cleanly). Same floor-never-
    round-up convention as `calculate_lot_size`: the partial volume is
    always floored to `volume_step`, never risking a larger partial than
    configured. Both the partial AND the remainder must clear
    `volume_min`, or MT5 itself would reject either leg's close/hold."""
    raw_partial = volume * partial_fraction
    partial = math.floor(round(raw_partial / volume_step, 9)) * volume_step
    partial = round(partial, 8)
    if partial < volume_min:
        return None
    remainder = round(volume - partial, 8)
    if remainder < volume_min:
        return None
    return partial


def partial_price_reached(direction: str, *, partial_price: float, current_price: float) -> bool:
    """Same directional-comparison shape as `pending_order_type`: a
    bullish trade's partial is reached going UP (current >= partial), a
    bearish trade's going DOWN (current <= partial)."""
    if direction == "bullish":
        return current_price >= partial_price
    return current_price <= partial_price
