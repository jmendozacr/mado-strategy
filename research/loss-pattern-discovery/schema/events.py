"""Event schema for the Loss Pattern Discovery lab.

Three field groups are kept structurally separate so a predictive feature can
never be built from information that was not yet knowable at the stage it
claims to describe:

  features_pre_entry   -- known strictly before the trade's own entry.
  features_at_stop      -- known strictly at/by the moment the SL/exit is confirmed.
  post_stop_outcomes     -- anything that depends on price action after the exit.

No dataclass below exposes all three groups through one flat namespace, and
`validate/integrity.py::check_temporal_ordering` re-checks the ordering at
runtime as defense in depth (the same pattern this repo's own fidelity-audit
app uses: enforce causality once, then re-check independently).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Outcome(str, Enum):
    WIN = "win"
    LOSS = "loss"
    OPEN = "open"  # censored: still open when the source data/horizon ran out


class ExitReasonBasis(str, Enum):
    """How `exit_reason` was determined -- never silently assumed."""

    OBSERVED = "observed"  # the source ledger states it directly
    INFERRED_BINARY = "inferred_binary"  # derived from `outcome` under a documented SL/TP-only assumption
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Identification:
    event_id: str  # the source's own stable id, assumed unique within source_version
    source_path: str  # repo-relative path of the source ledger file
    source_version: str  # e.g. "d3_c2_2015plus_run2"
    instrument: str
    session_label: str  # the source's "model" column, e.g. "9am", "1am"
    config_id: str  # the source's "arm" column, e.g. "d3_c2"; "" if the source has none
    original_direction: str  # "bullish"/"bearish" exactly as recorded, never re-derived


@dataclass(frozen=True)
class OriginalOperation:
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_price: float  # abs(entry_price - stop_loss), as priced
    activation_ts: Optional[datetime]  # when the setup's own signal activated
    order_placed_ts: Optional[datetime]  # when the entry order was placed
    entry_ts: Optional[datetime]
    exit_ts: Optional[datetime]  # None when the trade is still open (right-censored)
    exit_price: Optional[float]  # None when still open
    outcome: Outcome
    r_multiple: Optional[float]  # None when still open -- not yet knowable
    exit_reason: Optional[str]  # "stop_loss" / "take_profit" / None
    exit_reason_basis: ExitReasonBasis
    ambiguous_bar: bool  # source ledger's own intrabar SL/TP order ambiguity flag
    gap_filled: bool  # source ledger's own flag: execution price != planned price
    has_partial_exit: bool  # a partial scale-out leg exists; not yet modeled below


@dataclass(frozen=True)
class FeaturesPreEntry:
    """Known strictly before `OriginalOperation.entry_ts`."""

    feeder_ref_available_ts: Optional[datetime]
    activation_instant_ts: Optional[datetime]
    model1_available_ts: Optional[datetime]
    order_placed_ts: Optional[datetime]
    time_from_activation_to_order_s: Optional[float]
    planned_risk_price: float
    planned_reward_price: float
    planned_rr: Optional[float]


@dataclass(frozen=True)
class FeaturesAtStop:
    """Known strictly at/by the moment the exit is confirmed. May describe
    THIS trade's own stop event, but must never reference anything timestamped
    after `exit_ts`."""

    exit_ts: Optional[datetime]
    exit_price: Optional[float]
    outcome: Outcome
    r_multiple: Optional[float]
    speed_to_stop_s: Optional[float]  # exit_ts - entry_ts, seconds
    ambiguous_bar: bool
    gap_filled: bool


@dataclass
class PostStopOutcome:
    """Populated only by a later, explicit enrichment step that joins raw M15
    bars after `exit_ts` (see `extract/post_stop_trajectory.py`). Absent
    (the record simply not existing in `EventRecord.post_stop_outcomes`)
    means 'not yet computed' -- never 'zero movement'."""

    horizon_label: str  # e.g. "4h", "1d", "3d"
    horizon_ts: datetime
    mfe_price: Optional[float]
    mae_price: Optional[float]
    mfe_r: Optional[float]
    mae_r: Optional[float]
    price_at_horizon: Optional[float]
    bars_available: int
    censored: bool  # True if the data ran out before reaching horizon_ts


@dataclass
class EventRecord:
    identification: Identification
    operation: OriginalOperation
    features_pre_entry: FeaturesPreEntry
    features_at_stop: FeaturesAtStop
    post_stop_outcomes: list[PostStopOutcome] = field(default_factory=list)
