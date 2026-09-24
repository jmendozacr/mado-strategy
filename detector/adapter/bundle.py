"""Group D (spec.md REQ-STAT-23, Section L): the instrument-scoped input
bundle. `backtest.simulate.Trade` carries no `instrument` field, so Layer-2
MUST NOT accept an undifferentiated `Sequence[Trade]` — everything needed to
build one instrument's `DirectionPolicyObservation` universe travels together,
with `instrument` supplied by `Stage6Population.series.instrument`, never
inferred from a bare `Trade`."""

from dataclasses import dataclass
from datetime import datetime

from adapter.errors import AdapterIntegrityError
from alignment.htf_ltf import AlignedSignal
from backtest.population import Stage6Population
from backtest.simulate import ReconciliationReport, Trade
from evaluation.direction import DirectionEvaluation


@dataclass(frozen=True)
class InstrumentRunBundle:
    instrument: str
    population: Stage6Population
    evaluations: tuple[DirectionEvaluation, ...]
    trades: tuple[Trade, ...]
    reconciliation: ReconciliationReport
    aligned_signals: tuple[AlignedSignal, ...]
    candidate_cutoff_end_utc: datetime
    outcome_followup_end_utc: datetime

    def __post_init__(self) -> None:
        if self.instrument != self.population.series.instrument:
            raise AdapterIntegrityError(
                f"bundle.instrument {self.instrument!r} must equal "
                f"population.series.instrument {self.population.series.instrument!r} "
                f"— never diverge from the Stage6Population it was built for"
            )
        signal_ids_in_aligned = {s.ltf_signal.signal_id for s in self.aligned_signals}
        for candidate in self.population.candidates:
            if candidate.signal_id not in signal_ids_in_aligned:
                raise AdapterIntegrityError(
                    f"candidate signal_id {candidate.signal_id!r} absent from aligned_signals"
                )
