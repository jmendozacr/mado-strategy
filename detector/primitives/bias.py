from dataclasses import dataclass
from typing import Literal

from core.candle import Candle, OHLCSeries


@dataclass(frozen=True)
class BiasEvidence:
    observation_index: int
    close_relation: Literal["above", "below", "inside"]
    close_signal: Literal["bullish", "bearish"] | None
    wick_signal: Literal["bullish", "bearish", "conflict"] | None


def detect_bias_evidence(series: OHLCSeries) -> list[BiasEvidence]:
    """One evidence read per (previous, current) candle pair (REQ-BIAS-07)
    -- index 0 never produces evidence, there is no previous candle.
    close_signal and wick_signal are derived independently and never
    arbitrated against each other (REQ-BIAS-04): a candle may legitimately
    carry disagreeing evidence."""
    candles = series.candles
    evidence = []
    for i in range(1, len(candles)):
        previous, current = candles[i - 1], candles[i]
        relation = _close_relation(previous, current)
        evidence.append(
            BiasEvidence(
                observation_index=i,
                close_relation=relation,
                close_signal=_close_signal(relation, current),
                wick_signal=_wick_signal(current),
            )
        )
    return evidence


def _close_relation(previous: Candle, current: Candle) -> Literal["above", "below", "inside"]:
    """REQ-BIAS-01: partition against previous.high/low, both boundaries
    inclusive to "inside" (equality is not a break, mirrors REQ-OF-03.1)."""
    if current.close > previous.high:
        return "above"
    if current.close < previous.low:
        return "below"
    return "inside"


def _close_signal(
    relation: Literal["above", "below", "inside"], current: Candle
) -> Literal["bullish", "bearish"] | None:
    """REQ-BIAS-02: above/below are direct; inside follows the current
    candle's own body color; a doji body (open == close) is None, not a
    fabricated default (entries/model1.py REQ-47.4's doji carve-out is the
    same category of decision)."""
    if relation == "above":
        return "bullish"
    if relation == "below":
        return "bearish"
    if current.close > current.open:
        return "bullish"
    if current.close < current.open:
        return "bearish"
    return None


def _wick_signal(current: Candle) -> Literal["bullish", "bearish", "conflict"] | None:
    """REQ-BIAS-03: categorical existence, no magnitude threshold. Both
    wicks present is "conflict", never resolved to a direction; neither
    present is None."""
    upper = current.high > max(current.open, current.close)
    lower = current.low < min(current.open, current.close)
    if upper and lower:
        return "conflict"
    if upper:
        return "bearish"
    if lower:
        return "bullish"
    return None
