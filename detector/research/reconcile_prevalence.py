"""Non-discardable A/B/C/D prevalence reconciliation runner — RESEARCH
TOOLING, not a production entry point.

Ends the "throwaway script reproduces the OB x Displacement bucket
prevalence by hand" problem for good: this module is the ONE place that
computes it, built on top of `research.order_block` and
`research.displacement` (both frozen 2026-09-06) plus
`research.bucket_classification`.

**Population, precisely** (the single most important thing to get right
here — a prior attempt got this wrong and reported ~120,000 "signals" per
instrument, 100% in bucket A, by classifying every raw `AlignedSignal`
directly): the classified population is the OPENED-TRADE population, i.e.
`AlignedSignal`s that (a) survive `backtest.simulate.simulate()`'s
population pipeline, with the binary Key-Level confluence gate neutralized,
and (b) appear in the resulting `Trade` list. `Trade.outcome`/`.r_multiple`
are NEVER read in THIS module — prevalence-only, by design (see
`research.classify_trades.ClassifiedTrade` for the outcome-carrying
counterpart).

The actual load -> align -> simulate -> OB/Displacement/bucket-classify
pipeline lives in `research.classify_trades.classify_instrument` — this
module is a thin wrapper over it that aggregates into prevalence-only
`BucketCounts`, dropping `outcome`/`r_multiple`.

Leaf module, same `.importlinter` rules as `research.order_block`/
`research.displacement`: may import downward from any production layer
(that direction is unconstrained), must never be imported BY one.
"""

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from core.candle import OHLCSeries
from core.config import DetectorConfig
from research.classify_trades import (
    INSTRUMENTS,
    ClassificationOutcome,
    Population,
    _load_instrument_series,
    _resolve_population_base,
    classify_instrument,
)

# "Rough order of magnitude" guardrails (task-mandated), generously padded
# (3x on both ends) so real run-to-run variance never trips this -- ONLY the
# ~40x-off shape of the known prior bug (raw-aligned-signals-as-population,
# ~120,000/instrument against an expected ~2,300-2,900) is meant to trip it.
_SANITY_RANGES: dict[Population, dict[str, tuple[int, int]]] = {
    "discovery": {"per_instrument": (2300, 2900), "pooled": (6965, 8300)},
    "checkpoint_1_oos": {"per_instrument": (18, 21), "pooled": (59, 60)},
}
_SANITY_SLACK = 3.0
_DOMINANT_BUCKET_FRACTION = 0.90

_PERCENT = 100


@dataclass(frozen=True)
class BucketCounts:
    a: int
    b: int
    c: int
    d: int
    excluded_no_active_ob: int
    excluded_no_displacement_event: int
    excluded_no_htf_purge_index: int

    @property
    def total_classified(self) -> int:
        return self.a + self.b + self.c + self.d

    def __add__(self, other: "BucketCounts") -> "BucketCounts":
        return BucketCounts(
            a=self.a + other.a,
            b=self.b + other.b,
            c=self.c + other.c,
            d=self.d + other.d,
            excluded_no_active_ob=self.excluded_no_active_ob + other.excluded_no_active_ob,
            excluded_no_displacement_event=self.excluded_no_displacement_event
            + other.excluded_no_displacement_event,
            excluded_no_htf_purge_index=self.excluded_no_htf_purge_index + other.excluded_no_htf_purge_index,
        )


_EMPTY_BUCKET_COUNTS = BucketCounts(0, 0, 0, 0, 0, 0, 0)


@dataclass(frozen=True)
class InstrumentReconciliation:
    instrument: str
    raw_signals: int
    aligned_signals: int
    trades_opened: int
    buckets: BucketCounts


@dataclass(frozen=True)
class PrevalenceReport:
    population: Population
    per_instrument: dict[str, InstrumentReconciliation]
    pooled: BucketCounts


class PrevalenceSanityError(RuntimeError):
    """Raised instead of ever returning a `PrevalenceReport` whose shape
    resembles the known prior bug — see module docstring."""

    def __init__(self, message: str, per_instrument: dict[str, InstrumentReconciliation]):
        super().__init__(message)
        self.per_instrument = per_instrument


def _aggregate(outcomes: list[ClassificationOutcome]) -> BucketCounts:
    """Sum over a set -- input-ordering independent by construction (no
    outcome's contribution depends on any other's position). Every outcome
    lands in exactly one counter -- `classify()` is a total function over
    exactly 4 buckets, and the 3 exclusion reasons are mutually exclusive by
    construction of `classify_instrument`'s early returns -- asserted below
    defensively rather than just relied upon."""
    counts = {
        "A": 0, "B": 0, "C": 0, "D": 0,
        "excluded_no_active_ob": 0, "excluded_no_displacement_event": 0, "excluded_no_htf_purge_index": 0,
    }
    for outcome in outcomes:
        counts[outcome] += 1

    assert sum(counts.values()) == len(outcomes), "every outcome must land in exactly one bucket"

    return BucketCounts(
        a=counts["A"], b=counts["B"], c=counts["C"], d=counts["D"],
        excluded_no_active_ob=counts["excluded_no_active_ob"],
        excluded_no_displacement_event=counts["excluded_no_displacement_event"],
        excluded_no_htf_purge_index=counts["excluded_no_htf_purge_index"],
    )


def _reconcile_instrument(
    instrument: str,
    m15: OHLCSeries,
    h4: OHLCSeries,
    daily: OHLCSeries,
    config: DetectorConfig,
    anchor_window: tuple[datetime, datetime] | None,
) -> InstrumentReconciliation:
    """Thin wrapper over `classify_instrument` (the shared pipeline pass):
    aggregates its per-trade classifications into prevalence-only
    `BucketCounts`, dropping `outcome`/`r_multiple`."""
    result = classify_instrument(instrument, m15, h4, daily, config, anchor_window)

    outcomes = [row.outcome for row in result.classifications]
    buckets = _aggregate(outcomes)
    accounted = (
        buckets.total_classified
        + buckets.excluded_no_active_ob
        + buckets.excluded_no_displacement_event
        + buckets.excluded_no_htf_purge_index
    )
    assert accounted == result.trades_opened, (
        f"{instrument}: accounted {accounted} != trade population {result.trades_opened}"
    )

    return InstrumentReconciliation(
        instrument=instrument,
        raw_signals=result.raw_signals,
        aligned_signals=result.aligned_signals,
        trades_opened=result.trades_opened,
        buckets=buckets,
    )


def _order_of_magnitude_ok(value: int, low: int, high: int, slack: float = _SANITY_SLACK) -> bool:
    return (low / slack) <= value <= (high * slack)


def _dominant_bucket_fraction(buckets: BucketCounts) -> float:
    total = buckets.total_classified
    if total == 0:
        return 0.0
    return max(buckets.a, buckets.b, buckets.c, buckets.d) / total


def _diagnostics_report(population: Population, per_instrument: dict[str, InstrumentReconciliation]) -> str:
    lines = [f"population={population!r} pipeline-stage diagnostics:"]
    for instrument, rec in per_instrument.items():
        b = rec.buckets
        lines.append(
            f"  {instrument}: raw_signals={rec.raw_signals} aligned_signals={rec.aligned_signals} "
            f"trades_opened={rec.trades_opened} classified_total={b.total_classified} "
            f"A={b.a} B={b.b} C={b.c} D={b.d} "
            f"excluded_no_active_ob={b.excluded_no_active_ob} "
            f"excluded_no_displacement_event={b.excluded_no_displacement_event} "
            f"excluded_no_htf_purge_index={b.excluded_no_htf_purge_index}"
        )
    return "\n".join(lines)


def _check_sanity(population: Population, per_instrument: dict[str, InstrumentReconciliation], pooled: BucketCounts) -> None:
    ranges = _SANITY_RANGES[population]
    low, high = ranges["per_instrument"]
    pooled_low, pooled_high = ranges["pooled"]
    issues: list[str] = []

    for instrument, rec in per_instrument.items():
        total = rec.buckets.total_classified
        if not _order_of_magnitude_ok(total, low, high):
            issues.append(
                f"{instrument}: classified total {total} is far outside the expected order of "
                f"magnitude [{low}, {high}] for population={population!r}"
            )
        dominant_fraction = _dominant_bucket_fraction(rec.buckets)
        if dominant_fraction > _DOMINANT_BUCKET_FRACTION:
            issues.append(
                f"{instrument}: one bucket captures {dominant_fraction:.1%} of its classified total "
                f"-- this is the shape of the known prior bug (100% bucket A)"
            )

    pooled_total = pooled.total_classified
    if not _order_of_magnitude_ok(pooled_total, pooled_low, pooled_high):
        issues.append(
            f"pooled: classified total {pooled_total} is far outside the expected order of "
            f"magnitude [{pooled_low}, {pooled_high}] for population={population!r}"
        )
    pooled_dominant_fraction = _dominant_bucket_fraction(pooled)
    if pooled_dominant_fraction > _DOMINANT_BUCKET_FRACTION:
        issues.append(
            f"pooled: one bucket captures {pooled_dominant_fraction:.1%} of the pooled classified total "
            f"-- this is the shape of the known prior bug (100% bucket A)"
        )

    if issues:
        message = "\n".join(
            [
                "PREVALENCE SANITY CHECK FAILED -- treating this as a bug in the script, per the "
                "documented guardrail. NOT reporting a result.",
                _diagnostics_report(population, per_instrument),
                *[f"  ISSUE: {issue}" for issue in issues],
            ]
        )
        print(message)
        raise PrevalenceSanityError(message, per_instrument)


def compute_prevalence(
    pairs_dir: str,
    population: Population,
    instruments: tuple[str, ...] = INSTRUMENTS,
    config: DetectorConfig = DetectorConfig(),
    enforce_sanity: bool = True,
) -> PrevalenceReport:
    """Runs the full OB x Displacement bucket-prevalence reconciliation for
    one population (`"discovery"` -> `{pairs_dir}/_discovery_snapshot/...`,
    `"checkpoint_1_oos"` -> `{pairs_dir}/...` filtered to the checkpoint
    anchor window) across `instruments`.

    `enforce_sanity=False` is for tests exercising a small, deliberately
    bounded real-data slice -- the sanity ranges are calibrated against the
    real, full-history population and would always fail a small slice. A
    real run of this module (its own `__main__` block) never passes it.
    """
    base, anchor_window = _resolve_population_base(pairs_dir, population)

    per_instrument: dict[str, InstrumentReconciliation] = {}
    for instrument in instruments:
        m15, h4, daily = _load_instrument_series(base, instrument)
        per_instrument[instrument] = _reconcile_instrument(instrument, m15, h4, daily, config, anchor_window)

    pooled = _EMPTY_BUCKET_COUNTS
    for rec in per_instrument.values():
        pooled = pooled + rec.buckets

    if enforce_sanity:
        _check_sanity(population, per_instrument, pooled)

    return PrevalenceReport(population=population, per_instrument=per_instrument, pooled=pooled)


def _percent_of(count: int, total: int) -> str:
    return f"{(count / total * _PERCENT):.1f}%" if total else "n/a"


def _format_bucket_line(label: str, buckets: BucketCounts) -> str:
    total = buckets.total_classified
    pct = lambda n: _percent_of(n, total)
    return (
        f"{label}: A={buckets.a} ({pct(buckets.a)}) B={buckets.b} ({pct(buckets.b)}) "
        f"C={buckets.c} ({pct(buckets.c)}) D={buckets.d} ({pct(buckets.d)}) "
        f"[total_classified={total}] "
        f"excluded_no_active_ob={buckets.excluded_no_active_ob} "
        f"excluded_no_displacement_event={buckets.excluded_no_displacement_event}"
    )


def _print_report(report: PrevalenceReport) -> None:
    print(f"=== population={report.population} ===")
    for instrument, rec in report.per_instrument.items():
        print(_format_bucket_line(instrument, rec.buckets))
    print(_format_bucket_line("POOLED", report.pooled))
    print()


if __name__ == "__main__":
    _pairs_dir = os.path.join(os.path.dirname(__file__), "..", "..", "pairs")
    for _population in ("discovery", "checkpoint_1_oos"):
        try:
            _report = compute_prevalence(_pairs_dir, _population)
        except PrevalenceSanityError:
            raise SystemExit(1)
        _print_report(_report)
