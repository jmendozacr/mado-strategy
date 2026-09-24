"""Groups E/F/G/H/I/J (spec.md Section A/D/B/C2, REQ-STAT-24/25/04/35): the
operational `TradeJoinKey` reduction, its functional-dependency proof, the
aggregate-completeness guard REQ-STAT-25 requires before any Candidate
absence is interpreted as NEVER_FILLED, the CLOSED/OPEN/NEVER_FILLED outcome
mapping (never derived from `r_multiple`'s sign, Section C2), and the
explicit zero-risk geometry check (REQ-STAT-35, V4) applied to every Trade
regardless of outcome."""

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite

from adapter.errors import TradeJoinIntegrityError, TradeOutcomeContractError
from backtest.population import Stage6Population
from backtest.simulate import ReconciliationReport, Trade
from selection.model import CandidateIdentity, ClosedTradeOutcome, OutcomeState


@dataclass(frozen=True)
class TradeJoinKey:
    """Operational reduction of `CandidateIdentity` (spec.md Section A) —
    used exclusively to locate a `Trade`. Never stored as `candidate_id`,
    never substituted for `CandidateIdentity`."""

    instrument: str
    signal_id: str


def trade_join_key(candidate_id: CandidateIdentity) -> TradeJoinKey:
    return TradeJoinKey(instrument=candidate_id.instrument, signal_id=candidate_id.signal_id)


def prove_functional_join(
    identities: Sequence[CandidateIdentity], trades: Sequence[Trade], instrument: str
) -> tuple[dict[TradeJoinKey, CandidateIdentity], dict[TradeJoinKey, Trade]]:
    """REQ-STAT-24: before any lookup, prove — within this one instrument's
    run — that `TradeJoinKey -> CandidateIdentity` and `TradeJoinKey ->
    Trade` are both functions (at most one each). Either violated raises
    `TradeJoinIntegrityError`, never an arbitrary selection. A `Trade` whose
    `signal_id` matches no supplied `CandidateIdentity` (an orphan Trade) is
    equally a join-integrity break — it cannot be classified NEVER_FILLED,
    OPEN, or CLOSED against anything."""
    key_to_identity: dict[TradeJoinKey, CandidateIdentity] = {}
    for identity in identities:
        key = trade_join_key(identity)
        existing = key_to_identity.get(key)
        if existing is not None and existing != identity:
            raise TradeJoinIntegrityError(
                f"TradeJoinKey {key} maps to more than one CandidateIdentity: "
                f"{existing} and {identity} — TradeJoinKey -> CandidateIdentity is not a function"
            )
        key_to_identity[key] = identity

    key_to_trade: dict[TradeJoinKey, Trade] = {}
    for trade in trades:
        key = TradeJoinKey(instrument=instrument, signal_id=trade.signal_id)
        if key in key_to_trade:
            raise TradeJoinIntegrityError(
                f"TradeJoinKey {key} maps to more than one Trade — "
                f"TradeJoinKey -> Trade is not a function (duplicate join)"
            )
        if key not in key_to_identity:
            raise TradeJoinIntegrityError(
                f"Trade with TradeJoinKey {key} matches no CandidateIdentity in this run"
            )
        key_to_trade[key] = trade

    return key_to_identity, key_to_trade


def verify_aggregate_completeness(
    population: Stage6Population, trades: Sequence[Trade], reconciliation: ReconciliationReport
) -> None:
    """REQ-STAT-25: `len(Stage6Population.candidates) == len(trades) +
    ReconciliationReport.excluded_never_filled` MUST hold BEFORE any
    Candidate absence is interpreted as NEVER_FILLED — proven identity from
    `backtest/simulate.py::_fill_pass`/`_resolve_exits`. Broken accounting
    fails closed; it must NOT silently become NEVER_FILLED."""
    expected = len(trades) + reconciliation.excluded_never_filled
    actual = len(population.candidates)
    if actual != expected:
        raise TradeJoinIntegrityError(
            f"aggregate Trade accounting is broken: len(candidates)={actual} != "
            f"len(trades)={len(trades)} + excluded_never_filled="
            f"{reconciliation.excluded_never_filled} ({expected}) — the supplied Trade "
            f"collection is incomplete/untrustworthy, absence cannot be interpreted as NEVER_FILLED"
        )


def map_trade_outcome(trade: Trade | None) -> tuple[OutcomeState, ClosedTradeOutcome | None, float | None]:
    """Section B/C/C2, REQ-STAT-01/04: `trade is None` -> NEVER_FILLED
    (valid, expected, never an error — REQ-STAT-25 must already have passed
    before this is called). Otherwise validates the Trade's own contract
    (Section M #2/#3/#7, Group J) before mapping — never "repairs" a
    corrupted Trade."""
    if trade is None:
        return OutcomeState.NEVER_FILLED, None, None

    _require_nonzero_risk_geometry(trade)

    if trade.outcome == "win":
        _require_finite_r(trade)
        return OutcomeState.CLOSED, ClosedTradeOutcome.WIN, trade.r_multiple
    if trade.outcome == "loss":
        _require_finite_r(trade)
        return OutcomeState.CLOSED, ClosedTradeOutcome.LOSS, trade.r_multiple
    if trade.outcome == "open":
        if trade.r_multiple is not None:
            raise TradeOutcomeContractError(
                f"open Trade {trade.signal_id!r} must carry r_multiple=None, got {trade.r_multiple!r}"
            )
        return OutcomeState.OPEN, None, None

    raise TradeOutcomeContractError(
        f"Trade {trade.signal_id!r} has an unexpected outcome value {trade.outcome!r} "
        f"— expected one of 'win', 'loss', 'open'"
    )


def _require_nonzero_risk_geometry(trade: Trade) -> None:
    """REQ-STAT-35 (V4, Section M #7): `entry_price`/`stop_loss` MUST both be
    finite and `abs(entry_price - stop_loss) > 0`, checked for EVERY Trade
    regardless of `outcome` (WIN, LOSS, AND OPEN alike — `backtest/simulate.py
    ::Trade` populates both fields at fill time, independent of exit
    resolution). Integrity-only: never recomputes/repairs `r_multiple`,
    `entry_price`, or `stop_loss` — only raises if the geometry is
    impossible."""
    if not isfinite(trade.entry_price):
        raise TradeOutcomeContractError(
            f"Trade {trade.signal_id!r} has a non-finite entry_price {trade.entry_price!r}"
        )
    if not isfinite(trade.stop_loss):
        raise TradeOutcomeContractError(
            f"Trade {trade.signal_id!r} has a non-finite stop_loss {trade.stop_loss!r}"
        )
    if abs(trade.entry_price - trade.stop_loss) <= 0:
        raise TradeOutcomeContractError(
            f"Trade {trade.signal_id!r} has impossible zero-risk geometry: "
            f"entry_price {trade.entry_price!r} == stop_loss {trade.stop_loss!r}"
        )


def _require_finite_r(trade: Trade) -> None:
    if trade.r_multiple is None:
        raise TradeOutcomeContractError(
            f"{trade.outcome} Trade {trade.signal_id!r} must carry a finite r_multiple, got None"
        )
    if not isfinite(trade.r_multiple):
        raise TradeOutcomeContractError(
            f"{trade.outcome} Trade {trade.signal_id!r} must carry a finite r_multiple, "
            f"got {trade.r_multiple!r}"
        )
