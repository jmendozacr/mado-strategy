"""Stop-event eligibility classification.

Grounded directly in `detector/backtest/simulate.py`'s exit-resolution code
(`_resolve_level_exit`, `_resolve_trade`, `_resolve_single_leg`,
`_fill_candle_immediate_loss`) and the exact `BacktestConfig` used to generate
this lab's primary source: `detector/experimental/htf_trigger_1am_9am_backtest.py`'s
`SYMBOL_CONFIG` sets `breakeven_after_partial=True` for EURUSD/USDCAD/AUDUSD,
and `audit/2026-11-17-causal-lookahead-audit/run_d1_d2_d3.py:239` builds
`DetectorConfig(backtest=SYMBOL_CONFIG[symbol])` -- i.e. this exact,
unmodified config generated `trades_d3_c2_2015plus_run2.csv`.

Key facts this classifier relies on (verified against source, never assumed):

- `outcome` ("win"/"loss") is the SIGN of the net-of-cost R-multiple, not
  "which level resolved first" -- a cost-driven sign flip on a take-profit
  touch is possible in principle (checked empirically here, never assumed
  away: see `stats/eligibility_report.py`'s raw counts).
- For a non-partial trade, a "loss" `exit_price` equals `stop_loss` unless
  `gap_filled` (then it's the gap-open price) --
  `_resolve_single_leg`/`_fill_candle_immediate_loss`.
- For a partial-exit trade in THIS source, `breakeven_after_partial=True`
  always (it is set per-symbol in `SYMBOL_CONFIG`, not per-row): leg 2's
  adverse level is `entry_price`, not `stop_loss`. A "loss" on a
  partial-exit trade means leg 2 hit that MOVED breakeven level (or its
  gap-open), netting negative after cost -- `_resolve_trade`.
- `ambiguous_bar=True` means the adverse level (SL or breakeven) and the
  take-profit level touched within the SAME M15 bar, and the production
  engine's own pessimistic tie-break chose the adverse side. This lab does
  NOT inherit that choice as proof of what happened -- a tied bar is
  classified as Ambiguous here regardless of which way the engine broke the
  tie, because the true intrabar order remains genuinely unknown from M15
  data alone.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from schema.events import EventRecord, Outcome

PRICE_TOLERANCE = 1e-6  # float round-trip tolerance on 5-decimal FX prices


class StopEligibility(str, Enum):
    CONFIRMED_STOP = "confirmed_stop_event"
    STOP_AFTER_PARTIAL = "stop_after_partial_exit"
    OTHER_NEGATIVE_EXIT = "other_negative_exit"
    AMBIGUOUS_STOP = "ambiguous_stop_event"
    OPEN_CENSORED = "open_censored"


@dataclass(frozen=True)
class EligibilityResult:
    event_id: str
    category: StopEligibility
    # This lab's own qualitative judgment of classification confidence
    # (0..1) -- NOT a statistical probability and not inherited from any
    # source field.
    confidence: float
    stop_reference_price: float | None  # the level actually treated as "the stop" for this event
    reasons: tuple[str, ...]


def _isclose(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=0.0, abs_tol=PRICE_TOLERANCE)


def classify(record: EventRecord) -> EligibilityResult:
    """Classify a LOSS or OPEN event. Raises on WIN -- this taxonomy answers
    "was this loss really a stop execution," which is not a question a win
    needs answered."""
    op = record.operation
    event_id = record.identification.event_id

    if op.outcome is Outcome.OPEN:
        return EligibilityResult(
            event_id, StopEligibility.OPEN_CENSORED, 1.0, None,
            ("outcome=open: trade was still running when the source ledger ended",),
        )

    if op.outcome is not Outcome.LOSS:
        raise ValueError(f"{event_id}: classify() only applies to outcome in {{loss, open}}, got {op.outcome}")

    if op.exit_price is None:
        # Should never happen for outcome=loss (only `open` lacks exit_price)
        # -- never assume a default; surface the defect instead of hiding it.
        return EligibilityResult(
            event_id, StopEligibility.OTHER_NEGATIVE_EXIT, 0.0, None,
            ("outcome=loss but exit_price is missing -- source data defect, not classifiable",),
        )

    stop_reference = op.entry_price if op.has_partial_exit else op.stop_loss
    at_stop_reference = _isclose(op.exit_price, stop_reference)
    at_take_profit = _isclose(op.exit_price, op.take_profit)
    reasons: list[str] = []

    if op.ambiguous_bar:
        reasons.append(
            "ambiguous_bar=True: the adverse level and take-profit touched within the same "
            "M15 bar; the production engine's pessimistic tie-break chose the adverse side, "
            "but this lab treats the true intrabar order as unresolved regardless of that choice"
        )
        return EligibilityResult(event_id, StopEligibility.AMBIGUOUS_STOP, 0.5, stop_reference, tuple(reasons))

    if at_take_profit and not at_stop_reference:
        reasons.append(
            f"exit_price={op.exit_price} matches take_profit={op.take_profit}, not the stop "
            f"reference {stop_reference} -- this loss is a cost-driven sign flip on a "
            "take-profit touch, not a stop execution at all"
        )
        return EligibilityResult(event_id, StopEligibility.OTHER_NEGATIVE_EXIT, 0.9, None, tuple(reasons))

    if not at_stop_reference and not op.gap_filled:
        reasons.append(
            f"exit_price={op.exit_price} matches neither the expected stop reference "
            f"{stop_reference} nor take_profit={op.take_profit}, and gap_filled=False -- "
            "cannot confirm this was a stop execution from the available fields"
        )
        return EligibilityResult(event_id, StopEligibility.OTHER_NEGATIVE_EXIT, 0.3, None, tuple(reasons))

    if op.gap_filled and not at_stop_reference:
        reasons.append(
            f"gap_filled=True: price gapped through the stop reference {stop_reference}; "
            f"executed at the gap-open price {op.exit_price} instead -- still a genuine stop "
            "execution, just at a worse price than the nominal level"
        )
    else:
        reasons.append(f"exit_price={op.exit_price} matches the stop reference {stop_reference}")

    if op.has_partial_exit:
        reasons.append(
            "has_partial_exit=True with breakeven_after_partial=True (this source's fixed, "
            f"per-symbol config, not a per-row flag): the stop reference is "
            f"entry_price={op.entry_price}, not the original stop_loss column "
            f"({op.stop_loss})"
        )
        return EligibilityResult(event_id, StopEligibility.STOP_AFTER_PARTIAL, 0.95, stop_reference, tuple(reasons))

    return EligibilityResult(event_id, StopEligibility.CONFIRMED_STOP, 0.98, stop_reference, tuple(reasons))


def classify_all(records: list[EventRecord]) -> dict[str, EligibilityResult]:
    """Classify every LOSS/OPEN record; WIN records are out of this
    taxonomy's scope entirely and are not included in the result."""
    results: dict[str, EligibilityResult] = {}
    for record in records:
        if record.operation.outcome is Outcome.WIN:
            continue
        results[record.identification.event_id] = classify(record)
    return results
