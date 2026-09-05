"""REQ-70: partial-price ordering guarantee, checked against the real
3-instrument corpus (EURUSDm/GBPUSDm/DXYm) -- public functions only
(`alignment.tag_alignment`, `primitives.*`, `backtest.levels.*`,
`detect_swings`), never `backtest.simulate`'s private `_`-prefixed helpers.
Deterministic against real historical data, not a hypothesis-generated
property.
"""

import glob

from dataclasses import dataclass

import pytest

from alignment.htf_ltf import tag_alignment
from backtest.levels import Direction, entry_price, partial_price, risk_reward, stop_loss, take_profit
from core.config import DetectorConfig
from core.kill_zone import in_ny_kill_zone
from entries.model1 import detect_model1_signals
from ingestion.pairing import load_pair
from primitives.crt_range import detect_crt_ranges
from primitives.fvg import detect_fvgs, to_key_levels
from primitives.swing import detect_swings

_INSTRUMENTS = ("EURUSDm", "GBPUSDm", "DXYm")


@dataclass(frozen=True)
class _OrderingCandidate:
    """The minimal shape the ordering check needs -- decoupled from
    `backtest.simulate.Candidate` (a private-module type this file must not
    import) so the synthetic violation test (REQ-70.2) can construct one
    without touching `simulate.py` at all."""

    label: str
    direction: Direction
    entry_price: float
    stop_loss: float
    partial_price: float
    take_profit: float


def _assert_partial_price_ordering(candidates: list[_OrderingCandidate]) -> None:
    """REQ-70: stop_loss strictly worse than entry_price, strictly worse
    than partial_price, strictly worse than take_profit -- direction-
    adjusted. Fails loudly, naming the offending candidate, rather than
    silently skipping or excluding it."""
    for candidate in candidates:
        if candidate.direction == "bullish":
            ordered = (
                candidate.stop_loss < candidate.entry_price < candidate.partial_price < candidate.take_profit
            )
        else:
            ordered = (
                candidate.stop_loss > candidate.entry_price > candidate.partial_price > candidate.take_profit
            )
        if not ordered:
            raise AssertionError(
                f"partial-price ordering violated for candidate {candidate.label!r} "
                f"(direction={candidate.direction}): stop_loss={candidate.stop_loss}, "
                f"entry_price={candidate.entry_price}, partial_price={candidate.partial_price}, "
                f"take_profit={candidate.take_profit}"
            )


def _real_rr_floor_survivors(instrument: str) -> list[_OrderingCandidate]:
    """Reimplements `simulate.py`'s full pre-fill population chain --
    population cuts (stages 1-4), dedup (stage 4b), the kill-zone gate
    (stage 5), THEN the R:R floor (stage 6), in that exact order -- using
    ONLY public functions/fields, never `simulate.py`'s private
    `_population_cuts`/`_build_candidate`/`_dedup`/`_kill_zone_cut`/
    `_rr_floor_cut` helpers. Dedup and the kill-zone gate are NOT
    skippable shortcuts here: pipeline order means a candidate the
    kill-zone gate would exclude never reaches the R:R floor in
    production, so it is not "a candidate that survives the R:R floor
    filter" (REQ-70.1) even though its own price fields are unaffected by
    either cut -- an earlier version of this test skipped both and
    produced a false positive (a real kill-zone-excluded EURUSDm signal
    whose HTF range's `low` sat far below its own tight LTF entry/stop,
    flagged as an ordering violation) precisely because of this gap."""
    (htf_csv,) = glob.glob(f"../pairs/H4/{instrument}_H4_2*.csv")
    (ltf_csv,) = glob.glob(f"../pairs/M15/{instrument}_M15_*.csv")
    htf_series, ltf_series = load_pair(htf_csv, instrument, ltf_csv, instrument)

    model1_signals = detect_model1_signals(ltf_series)
    htf_ranges = detect_crt_ranges(htf_series)
    htf_key_levels = to_key_levels(detect_fvgs(htf_series))
    aligned_signals = tag_alignment(
        htf_series, ltf_series,
        ltf_signals=model1_signals, htf_ranges=htf_ranges, htf_key_levels=htf_key_levels,
    )

    swings = detect_swings(ltf_series)
    indices = [s.index for s in swings]
    config = DetectorConfig()

    population = [
        tagged for tagged in aligned_signals
        if tagged.ltf_signal.confirmation_type != "fvg_fill"
        and tagged.aligned == "aligned"
        and tagged.ltf_signal.retest_index is not None
        and tagged.key_level is not None
    ]

    candidates = []
    for tagged in population:
        signal = tagged.ltf_signal
        anchor = ltf_series.candles[signal.anchor_index]
        ep = entry_price(anchor, signal.direction, signal.entry_type)
        sl = stop_loss(
            anchor, signal.direction, swings, indices, signal.anchor_index, signal.retest_index, config.backtest
        )
        tp = take_profit(tagged.htf_context, signal.direction)
        pp = partial_price(ep, tp)
        candidates.append((signal, ep, sl, tp, pp))

    # Stage 4b: dedup on (anchor_index, direction, entry_price, entry_type),
    # lowest origin_index survives (REQ-46) -- mirrors `_dedup` exactly.
    by_key: dict[tuple, list] = {}
    for candidate in candidates:
        signal, ep, sl, tp, pp = candidate
        key = (signal.anchor_index, signal.direction, ep, signal.entry_type)
        by_key.setdefault(key, []).append(candidate)
    deduped = [min(group, key=lambda c: c[0].origin_index) for group in by_key.values()]

    # Stage 5: kill-zone gate, anchor-time basis only (REQ-36) -- mirrors
    # `_kill_zone_cut` exactly, default DetectorConfig() (kill_zone_gated=True).
    kill_zone_survivors = [
        candidate for candidate in deduped
        if not (
            config.backtest.kill_zone_gated
            and not in_ny_kill_zone(ltf_series.candles[candidate[0].anchor_index].timestamp, config.kill_zone)
        )
    ]

    survivors = []
    for signal, ep, sl, tp, pp in kill_zone_survivors:
        if risk_reward(ep, sl, tp, signal.direction) < config.backtest.min_risk_reward:
            continue
        survivors.append(
            _OrderingCandidate(
                label=signal.signal_id, direction=signal.direction,
                entry_price=ep, stop_loss=sl, partial_price=pp, take_profit=tp,
            )
        )
    return survivors


def test_partial_price_ordering_holds_across_real_corpus():
    """REQ-70.1: for every trade candidate surviving the R:R floor, across
    all 3 real instruments, stop_loss < entry_price < partial_price <
    take_profit (direction-adjusted) -- zero violations."""
    total = 0
    for instrument in _INSTRUMENTS:
        candidates = _real_rr_floor_survivors(instrument)
        assert candidates, f"{instrument}: no RR-floor survivors -- fixture regression, not a real zero"
        _assert_partial_price_ordering(candidates)
        total += len(candidates)
    assert total > 0


def test_ordering_violation_fails_loudly_naming_candidate():
    """REQ-70.2: a deliberately-violating candidate (partial_price on the
    wrong side of entry_price) makes the check fail explicitly, identifying
    that candidate by label -- never silently skipped or excluded."""
    violating = _OrderingCandidate(
        label="synthetic-violation-1", direction="bullish",
        entry_price=1.1000, stop_loss=1.0988, partial_price=1.0995, take_profit=1.1050,
    )

    with pytest.raises(AssertionError, match="synthetic-violation-1"):
        _assert_partial_price_ordering([violating])
