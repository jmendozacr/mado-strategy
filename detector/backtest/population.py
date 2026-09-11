"""Outcome-free construction of the canonical pre-fill candidate population."""

from dataclasses import dataclass

from alignment.htf_ltf import AlignedSignal
from backtest.candidate import Candidate
from backtest.levels import entry_price as _entry_price
from backtest.levels import partial_price as _partial_price
from backtest.levels import risk_reward as _risk_reward
from backtest.levels import stop_loss as _stop_loss
from backtest.levels import take_profit as _take_profit
from core.candle import OHLCSeries
from core.config import DetectorConfig
from core.kill_zone import in_ny_kill_zone
from primitives.swing import SwingPoint, detect_swings


@dataclass(frozen=True)
class Stage6Population:
    series: OHLCSeries
    candidates: list[Candidate]
    excluded_no_crt_range: int
    excluded_unaligned: int
    excluded_never_confirmed: int
    excluded_no_key_level: int
    excluded_duplicate: int
    excluded_kill_zone: int
    excluded_rr_floor: int


@dataclass(frozen=True)
class _PopulationCuts:
    survivors: list[AlignedSignal]
    no_crt_range: int
    unaligned: int
    never_confirmed: int
    no_key_level: int


def _build_candidate(
    tagged: AlignedSignal, swings, indices: list[int], ltf_series: OHLCSeries, backtest_config
) -> Candidate:
    signal = tagged.ltf_signal
    anchor = ltf_series.candles[signal.anchor_index]
    ep = _entry_price(anchor, signal.direction, signal.entry_type)
    sl = _stop_loss(
        anchor, signal.direction, swings, indices, signal.anchor_index, signal.retest_index,
        ltf_series.candles, backtest_config,
    )
    tp = _take_profit(tagged.htf_context, signal.direction)
    return Candidate(
        signal_id=signal.signal_id,
        anchor_index=signal.anchor_index,
        origin_index=signal.origin_index,
        direction=signal.direction,
        entry_type=signal.entry_type,
        retest_index=signal.retest_index,
        entry_price=ep,
        stop_loss=sl,
        take_profit=tp,
        partial_price=_partial_price(ep, tp),
    )


def _population_cuts(aligned_signals: list[AlignedSignal]) -> _PopulationCuts:
    survivors: list[AlignedSignal] = []
    excluded_no_crt_range = excluded_unaligned = excluded_never_confirmed = excluded_no_key_level = 0
    for tagged in aligned_signals:
        signal = tagged.ltf_signal
        if signal.confirmation_type == "fvg_fill":
            excluded_no_crt_range += 1
        elif tagged.aligned != "aligned":
            excluded_unaligned += 1
        elif signal.retest_index is None:
            excluded_never_confirmed += 1
        elif tagged.key_level is None:
            excluded_no_key_level += 1
        else:
            survivors.append(tagged)
    return _PopulationCuts(
        survivors=survivors, no_crt_range=excluded_no_crt_range, unaligned=excluded_unaligned,
        never_confirmed=excluded_never_confirmed, no_key_level=excluded_no_key_level,
    )


def _dedup(candidates: list[Candidate]) -> tuple[list[Candidate], int]:
    by_key: dict[tuple, list[Candidate]] = {}
    for candidate in candidates:
        key = (candidate.anchor_index, candidate.direction, candidate.entry_price, candidate.entry_type)
        by_key.setdefault(key, []).append(candidate)
    survivors = [min(group, key=lambda candidate: candidate.origin_index) for group in by_key.values()]
    return survivors, len(candidates) - len(survivors)


def _kill_zone_cut(
    candidates: list[Candidate], candles: tuple, config: DetectorConfig
) -> tuple[list[Candidate], int]:
    survivors, excluded = [], 0
    for candidate in candidates:
        if config.backtest.kill_zone_gated and not in_ny_kill_zone(
            candles[candidate.anchor_index].timestamp, config.kill_zone
        ):
            excluded += 1
        else:
            survivors.append(candidate)
    return survivors, excluded


def _rr_floor_cut(candidates: list[Candidate], min_risk_reward: float) -> tuple[list[Candidate], int]:
    survivors, excluded = [], 0
    for candidate in candidates:
        rr = _risk_reward(candidate.entry_price, candidate.stop_loss, candidate.take_profit, candidate.direction)
        if rr < min_risk_reward:
            excluded += 1
        else:
            survivors.append(candidate)
    return survivors, excluded


def build_stage6_population(
    aligned_signals: list[AlignedSignal],
    ltf_series: OHLCSeries,
    config: DetectorConfig,
    swings: list[SwingPoint] | None = None,
) -> Stage6Population:
    cuts = _population_cuts(aligned_signals)
    swings = swings if swings is not None else detect_swings(ltf_series, config.swing)
    indices = [s.index for s in swings]
    candidates = [
        _build_candidate(tagged, swings, indices, ltf_series, config.backtest) for tagged in cuts.survivors
    ]
    candidates, excluded_duplicate = _dedup(candidates)
    candidates, excluded_kill_zone = _kill_zone_cut(candidates, ltf_series.candles, config)
    candidates, excluded_rr_floor = _rr_floor_cut(candidates, config.backtest.min_risk_reward)
    return Stage6Population(
        series=ltf_series,
        candidates=candidates,
        excluded_no_crt_range=cuts.no_crt_range,
        excluded_unaligned=cuts.unaligned,
        excluded_never_confirmed=cuts.never_confirmed,
        excluded_no_key_level=cuts.no_key_level,
        excluded_duplicate=excluded_duplicate,
        excluded_kill_zone=excluded_kill_zone,
        excluded_rr_floor=excluded_rr_floor,
    )
