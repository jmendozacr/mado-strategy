"""OB x Displacement bucket classification, WITH trade outcomes — RESEARCH
TOOLING, not a production entry point.

Extracted from `research.reconcile_prevalence` (frozen 2026-09-06): that
module's own population construction (opened-trade population via
`backtest.simulate.simulate()` with the Key-Level confluence gate
neutralized) and per-trade OB/Displacement/bucket classification is the
ONE canonical pipeline; this module reuses it, unchanged, and additionally
carries each trade's `outcome`/`r_multiple` through — the one thing
`reconcile_prevalence` deliberately never reads (prevalence-only, by
design). `reconcile_prevalence.compute_prevalence` is now a thin wrapper
over `classify_instrument` (this module), dropping `outcome`/`r_multiple`
to keep its own prevalence-only behavior unchanged.

Leaf module, same `.importlinter` rules as `research.order_block`/
`research.displacement`/`research.reconcile_prevalence`: may import
downward from any production layer (that direction is unconstrained), must
never be imported BY one.
"""

import bisect
import glob
import os
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal

from alignment.htf_ltf import AlignedSignal, tag_alignment
from backtest.simulate import simulate
from core.candle import OHLCSeries
from core.config import DetectorConfig
from core.key_level import KeyLevel
from entries.model1 import detect_model1_signals
from ingestion.loader import load_mt5_csv
from ingestion.pairing import load_pair
from primitives.crt_range import CRTRange, first_breach_index
from research.bucket_classification import Alignment, Bucket, classify
from research.displacement import DisplacementEvent, detect_displacements, most_recent_before
from research.order_block import OrderBlock, detect_order_blocks, select_nearest_active_order_block

INSTRUMENTS: tuple[str, ...] = ("EURUSDm", "GBPUSDm", "DXYm")

Population = Literal["discovery", "checkpoint_1_oos", "active_full"]
ExclusionReason = Literal[
    "excluded_no_htf_purge_index", "excluded_no_active_ob", "excluded_no_displacement_event"
]
ClassificationOutcome = Bucket | ExclusionReason
TradeOutcome = Literal["win", "loss", "open"]

# Same neutralization as every prior ablation this session -- see
# `reconcile_prevalence`'s own module docstring for the full rationale.
_NEUTRAL_KEY_LEVEL = KeyLevel(kind="fvg", top=0.0, bottom=0.0, origin_index=0)

_CHECKPOINT_ANCHOR_WINDOW = (datetime(2026, 8, 20, 0, 0), datetime(2026, 9, 4, 23, 59))


@dataclass(frozen=True)
class ClassifiedTrade:
    """One OPENED, OB/Displacement-CLASSIFIED trade -- i.e. `bucket` is
    always "A"/"B"/"C"/"D", never an exclusion reason. Trades excluded from
    OB/Displacement classification (`excluded_no_active_ob` etc.) carry no
    bucket and are dropped from `classify_trades`' result; per-instrument
    exclusion accounting stays `reconcile_prevalence.compute_prevalence`'s
    job (`InstrumentReconciliation`/`BucketCounts`)."""

    instrument: str
    signal_id: str
    bucket: Bucket
    outcome: TradeOutcome
    r_multiple: float | None


@dataclass(frozen=True)
class _RawClassification:
    """Internal, pre-drop shape: one row per OPENED trade (bucketed or
    excluded) -- `reconcile_prevalence._reconcile_instrument` aggregates
    `.outcome` (which may be an `ExclusionReason`) into `BucketCounts`;
    `classify_trades` keeps only the `Bucket`-valued rows and repackages
    them as `ClassifiedTrade`."""

    signal_id: str
    outcome: ClassificationOutcome
    trade_outcome: TradeOutcome
    r_multiple: float | None


@dataclass(frozen=True)
class InstrumentClassification:
    """Everything `reconcile_prevalence.InstrumentReconciliation` needs
    (`raw_signals`/`aligned_signals`/`trades_opened`) plus the full
    per-trade classification list, computed in exactly one pipeline pass
    per instrument -- the shared result both `reconcile_prevalence` and
    `classify_trades` build on."""

    instrument: str
    raw_signals: int
    aligned_signals: int
    trades_opened: int
    classifications: list[_RawClassification]


def _neutralize_key_level_gate(aligned_signals: list[AlignedSignal]) -> list[AlignedSignal]:
    return [
        replace(signal, key_level=_NEUTRAL_KEY_LEVEL) if signal.key_level is None else signal
        for signal in aligned_signals
    ]


def _floor_daily_index(daily_candles: tuple, timestamp: datetime) -> int | None:
    """Last Daily index whose own timestamp is <= `timestamp` -- the same
    floor-bisection convention as `alignment.htf_ltf._enclosing_htf_index`.
    `None` when `timestamp` precedes every Daily candle."""
    timestamps = [c.timestamp for c in daily_candles]
    position = bisect.bisect_right(timestamps, timestamp)
    return position - 1 if position > 0 else None


def _purge_daily_index(h4: OHLCSeries, daily: OHLCSeries, htf_context: CRTRange) -> int | None:
    """The structural-break point every prior ablation anchored OB/
    Displacement alignment on -- see `reconcile_prevalence`'s prior version
    of this function for the full rationale (unchanged here)."""
    htf_purge_index = first_breach_index(
        h4.candles, htf_context.end_index, len(h4.candles) - 1,
        high=htf_context.high, low=htf_context.low,
    )
    if htf_purge_index is None:
        return None
    return _floor_daily_index(daily.candles, h4.candles[htf_purge_index].timestamp)


def _classify_signal_bucket(
    tagged: AlignedSignal,
    h4: OHLCSeries,
    daily: OHLCSeries,
    order_blocks: list[OrderBlock],
    displacements: list[DisplacementEvent],
) -> ClassificationOutcome:
    """Single-trade classification -- pure, no aggregation state."""
    signal = tagged.ltf_signal
    assert tagged.htf_context is not None  # aligned="aligned" always carries a resolved htf_context

    purge_index = _purge_daily_index(h4, daily, tagged.htf_context)
    if purge_index is None:
        return "excluded_no_htf_purge_index"

    selected_ob = select_nearest_active_order_block(order_blocks, signal.entry_price, purge_index)
    if selected_ob is None:
        return "excluded_no_active_ob"

    displacement_event = most_recent_before(displacements, purge_index)
    if displacement_event is None:
        return "excluded_no_displacement_event"

    ob_alignment: Alignment = "aligned" if selected_ob.direction == signal.direction else "opposed"
    displacement_alignment: Alignment = (
        "aligned" if displacement_event.direction == signal.direction else "opposed"
    )
    return classify(ob_alignment, displacement_alignment)


def _find_csv(directory: str, instrument: str) -> str:
    """Exactly one match expected -- `pairs/H4/*` carries a second,
    differently-shaped `{instrument}_H4_UTC4aligned.csv` file per
    instrument, explicitly excluded (see `reconcile_prevalence`'s prior
    version of this function for the full rationale)."""
    candidates = [
        path
        for path in glob.glob(os.path.join(directory, f"{instrument}_*.csv"))
        if "UTC4aligned" not in os.path.basename(path)
    ]
    if len(candidates) != 1:
        raise FileNotFoundError(
            f"expected exactly one CSV for instrument={instrument!r} in {directory!r}, found: {candidates}"
        )
    return candidates[0]


def _resolve_population_base(
    pairs_dir: str, population: Population
) -> tuple[str, tuple[datetime, datetime] | None]:
    if population == "discovery":
        return os.path.join(pairs_dir, "_discovery_snapshot"), None
    if population == "checkpoint_1_oos":
        return pairs_dir, _CHECKPOINT_ANCHOR_WINDOW
    if population == "active_full":
        # The current, active (repaired) `pairs_dir` series, unfiltered --
        # full available history through whatever `pairs_dir` actually
        # contains. Distinct from `"discovery"` (which reads the frozen,
        # no-longer-current `_discovery_snapshot` subdirectory) and from
        # `"checkpoint_1_oos"` (same active dir, but anchor-windowed).
        return pairs_dir, None
    raise ValueError(f"unknown population: {population!r}")


def _load_instrument_series(base: str, instrument: str) -> tuple[OHLCSeries, OHLCSeries, OHLCSeries]:
    """Returns `(m15, h4, daily)`."""
    m15_dir, h4_dir, d1_dir = os.path.join(base, "M15"), os.path.join(base, "H4"), os.path.join(base, "D1")
    h4, m15 = load_pair(
        htf_csv=_find_csv(h4_dir, instrument), htf_symbol=instrument,
        ltf_csv=_find_csv(m15_dir, instrument), ltf_symbol=instrument,
    )
    daily = load_mt5_csv(_find_csv(d1_dir, instrument), symbol=instrument)
    return m15, h4, daily


def classify_instrument(
    instrument: str,
    m15: OHLCSeries,
    h4: OHLCSeries,
    daily: OHLCSeries,
    config: DetectorConfig,
    anchor_window: tuple[datetime, datetime] | None,
) -> InstrumentClassification:
    """One full pipeline pass for one instrument: raw signals -> HTF/LTF
    alignment -> opened-trade population (Key-Level gate neutralized) ->
    per-trade OB/Displacement/bucket classification, carrying each opened
    trade's own `outcome`/`r_multiple` along. The single computation both
    `reconcile_prevalence._reconcile_instrument` (prevalence-only) and
    `classify_trades` (with outcomes) build on."""
    raw_signals = detect_model1_signals(m15)
    aligned_signals = tag_alignment(htf_series=h4, ltf_series=m15, ltf_signals=raw_signals)
    aligned_only = [tagged for tagged in aligned_signals if tagged.aligned == "aligned"]

    neutralized = _neutralize_key_level_gate(aligned_only)
    trades, _report = simulate(neutralized, m15, config)

    by_signal_id = {tagged.ltf_signal.signal_id: tagged for tagged in neutralized}

    if anchor_window is not None:
        start, end = anchor_window
        trades = [
            trade
            for trade in trades
            if start <= m15.candles[by_signal_id[trade.signal_id].ltf_signal.anchor_index].timestamp <= end
        ]

    order_blocks = detect_order_blocks(daily)
    displacements = detect_displacements(daily)

    seen_signal_ids: set[str] = set()
    classifications: list[_RawClassification] = []
    for trade in trades:
        assert trade.signal_id not in seen_signal_ids, f"duplicate signal_id in trade population: {trade.signal_id}"
        seen_signal_ids.add(trade.signal_id)
        tagged = by_signal_id[trade.signal_id]
        outcome = _classify_signal_bucket(tagged, h4, daily, order_blocks, displacements)
        classifications.append(
            _RawClassification(
                signal_id=trade.signal_id, outcome=outcome,
                trade_outcome=trade.outcome, r_multiple=trade.r_multiple,
            )
        )

    return InstrumentClassification(
        instrument=instrument, raw_signals=len(raw_signals), aligned_signals=len(aligned_only),
        trades_opened=len(trades), classifications=classifications,
    )


def classify_trades(
    pairs_dir: str,
    population: Population,
    instruments: tuple[str, ...] = INSTRUMENTS,
    config: DetectorConfig = DetectorConfig(),
) -> list[ClassifiedTrade]:
    """Runs `classify_instrument` across `instruments` and returns one
    `ClassifiedTrade` per OPENED trade that landed in an A/B/C/D bucket --
    trades excluded from OB/Displacement classification are dropped (see
    `ClassifiedTrade`'s docstring)."""
    base, anchor_window = _resolve_population_base(pairs_dir, population)

    result: list[ClassifiedTrade] = []
    for instrument in instruments:
        m15, h4, daily = _load_instrument_series(base, instrument)
        classification = classify_instrument(instrument, m15, h4, daily, config, anchor_window)
        for row in classification.classifications:
            if row.outcome in ("A", "B", "C", "D"):
                result.append(
                    ClassifiedTrade(
                        instrument=instrument, signal_id=row.signal_id, bucket=row.outcome,
                        outcome=row.trade_outcome, r_multiple=row.r_multiple,
                    )
                )
    return result
