from __future__ import annotations
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class NinePmMetrics:
    """Objective, threshold-free OHLC facts about the 9 PM H4 candle relative to its predecessor.

    All values are derived from the 9 PM candle and its immediate predecessor — both are
    finalised at the 01:00 H4 boundary after the 21:00 candle closes (REQ-80).

    Interpretation of each field is intentionally left to a downstream Phase 2 classification
    rule gated on Q1 + Q4. This struct is a measurement, not a verdict.
    """
    prior_h4_index: int

    # 9 PM candle body
    body_direction: Literal["bullish", "bearish", "doji"]
    body_ratio: float | None  # abs(close-open)/(high-low); None when high==low

    # 9 PM candle range relative to prior H4 candle range
    extends_prior_high: bool  # nine_pm.high > prior.high
    extends_prior_low: bool   # nine_pm.low < prior.low
    is_inside_bar: bool       # nine_pm.high <= prior.high AND nine_pm.low >= prior.low


def measure_nine_pm(
    nine_pm_open: float,
    nine_pm_high: float,
    nine_pm_low: float,
    nine_pm_close: float,
    prior_high: float,
    prior_low: float,
    prior_h4_index: int,
) -> NinePmMetrics:
    """Compute NinePmMetrics from raw OHLC values. Pure structural arithmetic, no thresholds."""
    if nine_pm_close > nine_pm_open:
        body_direction: Literal["bullish", "bearish", "doji"] = "bullish"
    elif nine_pm_close < nine_pm_open:
        body_direction = "bearish"
    else:
        body_direction = "doji"

    candle_range = nine_pm_high - nine_pm_low
    body_ratio = abs(nine_pm_close - nine_pm_open) / candle_range if candle_range > 0 else None

    return NinePmMetrics(
        prior_h4_index=prior_h4_index,
        body_direction=body_direction,
        body_ratio=body_ratio,
        extends_prior_high=nine_pm_high > prior_high,
        extends_prior_low=nine_pm_low < prior_low,
        is_inside_bar=nine_pm_high <= prior_high and nine_pm_low >= prior_low,
    )
