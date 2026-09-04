from dataclasses import dataclass, field
from typing import Literal

from core.candle import Candle, OHLCSeries
from core.config import CRTRangeConfig, FVGConfig, Model1Config
from core.results import DetectionStatus
from primitives.crt_range import CRTRange, detect_crt_ranges, first_breach_index
from primitives.fvg import FVG, detect_fvgs

Direction = Literal["bullish", "bearish"]


@dataclass(frozen=True)
class Model1Signal:
    anchor_index: int
    direction: Direction
    purge_target: float
    confirmation_type: Literal["purge_engulf", "fvg_fill"]
    entry_type: Literal["wick", "body"]
    entry_price: float
    retest_index: int | None
    status: DetectionStatus
    confirmation_index: int
    origin_index: int
    signal_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "signal_id",
            f"{self.origin_index}-{self.anchor_index}-{self.direction}-{self.confirmation_type}-{self.entry_type}",
        )


def detect_model1_signals(
    series: OHLCSeries,
    crt_config: CRTRangeConfig = CRTRangeConfig(),
    fvg_config: FVGConfig = FVGConfig(),
    config: Model1Config = Model1Config(),
    crt_ranges: list[CRTRange] | None = None,
    fvgs: list[FVG] | None = None,
) -> list[Model1Signal]:
    """`crt_ranges`/`fvgs` let a caller that already computed them for the
    same `series`+config reuse them instead of triggering a second
    O(n)+ detection pass — cli.py's orchestration was calling
    detect_crt_ranges/detect_fvgs a second time for results it had already
    computed via this function. `None` (the default) preserves the original
    self-contained behavior for every existing call site.
    """
    candles = series.candles
    signals = []

    for crt_range in crt_ranges if crt_ranges is not None else detect_crt_ranges(series, crt_config):
        signals.extend(_purge_signals(candles, crt_range, config))

    for fvg in fvgs if fvgs is not None else detect_fvgs(series, fvg_config):
        signal = _fvg_fill_signal(candles, fvg, config)
        if signal is not None:
            signals.append(signal)

    return signals


def _purge_signals(
    candles: tuple[Candle, ...], crt_range: CRTRange, config: Model1Config
) -> list[Model1Signal]:
    signals = []
    anchor_index = first_breach_index(candles, crt_range.start_index, crt_range.resolved_at_index, high=crt_range.high)
    if anchor_index is not None:
        signal = _track_anchor(
            candles, anchor_index, "bearish", crt_range.high, "purge_engulf", config, crt_range.start_index
        )
        if signal is not None:
            signals.append(signal)

    anchor_index = first_breach_index(candles, crt_range.start_index, crt_range.resolved_at_index, low=crt_range.low)
    if anchor_index is not None:
        signal = _track_anchor(
            candles, anchor_index, "bullish", crt_range.low, "purge_engulf", config, crt_range.start_index
        )
        if signal is not None:
            signals.append(signal)

    return signals


def _fvg_fill_signal(
    candles: tuple[Candle, ...], fvg: FVG, config: Model1Config
) -> Model1Signal | None:
    """Reuses FVG's already-computed fill_index (Bug 1a fix) instead of
    independently rescanning forward from fvg.end_index+1 for the same
    result — fvg.py's own fill-status pass already resolves this.
    """
    if fvg.fill_index is None:
        return None
    direction: Direction = "bullish" if fvg.direction == "bullish" else "bearish"
    purge_target = fvg.bottom if fvg.direction == "bullish" else fvg.top
    return _track_anchor(candles, fvg.fill_index, direction, purge_target, "fvg_fill", config, fvg.start_index)


def _track_anchor(
    candles: tuple[Candle, ...],
    anchor_index: int,
    direction: Direction,
    purge_target: float,
    confirmation_type: Literal["purge_engulf", "fvg_fill"],
    config: Model1Config,
    origin_index: int,
) -> Model1Signal | None:
    anchor = candles[anchor_index]
    protected_extreme = anchor.low if direction == "bullish" else anchor.high
    body_low = min(anchor.open, anchor.close)
    body_high = max(anchor.open, anchor.close)

    confirmed = False
    entry_type: Literal["wick", "body"] | None = None
    entry_price: float | None = None
    retest_index: int | None = None
    retest_open: float | None = None

    def signal(retest_index: int | None, status: DetectionStatus, confirmation_index: int) -> Model1Signal:
        return Model1Signal(
            anchor_index=anchor_index,
            direction=direction,
            purge_target=purge_target,
            confirmation_type=confirmation_type,
            entry_type=entry_type,
            entry_price=entry_price,
            retest_index=retest_index,
            status=status,
            confirmation_index=confirmation_index,
            origin_index=origin_index,
        )

    window_end = min(anchor_index + config.max_retest_lookback, len(candles) - 1)
    for j in range(anchor_index + 1, window_end + 1):
        candle = candles[j]

        if _breaches_protected_extreme(candle.close, protected_extreme, direction, config.respect_rule_tolerance):
            if not confirmed:
                # REQ-18: a close beyond the anchor's protected extreme
                # before any confirmation invalidates immediately — the
                # signal is still emitted, not dropped. `protected_extreme`
                # doubles as the wick-entry price _select_entry would have
                # returned (the anchor's swept side), since no confirming
                # close ever happened to select an entry from.
                # Pre-confirmation breach: entry_price is the breached
                # protected extreme, not a planned entry — no
                # confirmation/engulf ever occurred for this signal.
                entry_type, entry_price = "wick", protected_extreme
                return signal(None, DetectionStatus.INVALIDATED, j)
            return signal(retest_index, DetectionStatus.INVALIDATED, j)

        if not confirmed:
            if _closes_beyond(candle.close, body_high, body_low, direction):
                confirmed = True
                entry_type, entry_price = _select_entry(candle.close, anchor, direction, config.body_ratio_tiebreak)
            continue

        if retest_index is None and _wick_overlaps(candle, body_low, body_high):
            retest_index = j
            retest_open = candle.open
        if retest_index is not None and _closes_beyond_open(candle.close, retest_open, direction):
            return signal(retest_index, DetectionStatus.CONFIRMED, j)

    if not confirmed:
        return None
    return signal(retest_index, DetectionStatus.PENDING, window_end)


def _breaches_protected_extreme(
    close: float, protected_extreme: float, direction: Direction, tolerance: float
) -> bool:
    if direction == "bullish":
        return close < protected_extreme - tolerance
    return close > protected_extreme + tolerance


def _closes_beyond(close: float, body_high: float, body_low: float, direction: Direction) -> bool:
    if direction == "bullish":
        return close > body_high
    return close < body_low


def _closes_beyond_open(close: float, retest_open: float, direction: Direction) -> bool:
    if direction == "bullish":
        return close > retest_open
    return close < retest_open


def _wick_overlaps(candle: Candle, body_low: float, body_high: float) -> bool:
    return candle.low <= body_high and candle.high >= body_low


def _select_entry(
    close: float, anchor: Candle, direction: Direction, body_ratio_tiebreak: float
) -> tuple[Literal["wick", "body"], float]:
    if direction == "bullish":
        wick_extreme = anchor.high
        if close > wick_extreme:
            return "wick", anchor.low
        if _body_ratio(anchor) >= body_ratio_tiebreak:
            return "body", anchor.open
        return "wick", anchor.low

    wick_extreme = anchor.low
    if close < wick_extreme:
        return "wick", anchor.high
    if _body_ratio(anchor) >= body_ratio_tiebreak:
        return "body", anchor.open
    return "wick", anchor.high


def _body_ratio(anchor: Candle) -> float:
    candle_range = anchor.high - anchor.low
    if candle_range <= 0:
        return 0.0
    return abs(anchor.close - anchor.open) / candle_range
