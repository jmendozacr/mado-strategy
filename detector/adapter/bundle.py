"""Group D (spec.md REQ-STAT-23, Section L): the instrument-scoped input
bundle. `backtest.simulate.Trade` carries no `instrument` field, so Layer-2
MUST NOT accept an undifferentiated `Sequence[Trade]` — everything needed to
build one instrument's `DirectionPolicyObservation` universe travels together,
with `instrument` supplied by `Stage6Population.series.instrument`, never
inferred from a bare `Trade`."""

from dataclasses import dataclass
from datetime import datetime

from adapter.errors import AdapterIntegrityError
from backtest.population import Stage6Population
from backtest.simulate import ReconciliationReport, Trade
from core.candle import OHLCSeries
from core.config import DetectorConfig
from evaluation.direction import DirectionEvaluation


@dataclass(frozen=True)
class InstrumentRunBundle:
    instrument: str
    population: Stage6Population
    evaluations: tuple[DirectionEvaluation, ...]
    trades: tuple[Trade, ...]
    reconciliation: ReconciliationReport
    htf_series: OHLCSeries
    config: DetectorConfig
    candidate_cutoff_end_utc: datetime
    outcome_followup_end_utc: datetime

    def __post_init__(self) -> None:
        if self.instrument != self.population.series.instrument:
            raise AdapterIntegrityError(
                f"bundle.instrument {self.instrument!r} must equal "
                f"population.series.instrument {self.population.series.instrument!r} "
                f"— never diverge from the Stage6Population it was built for"
            )
        if self.htf_series.instrument != self.instrument:
            raise AdapterIntegrityError(
                f"htf_series.instrument {self.htf_series.instrument!r} must equal "
                f"bundle.instrument {self.instrument!r} — one instrument per bundle"
            )
