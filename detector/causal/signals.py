"""Causal Model-1 purge_engulf signal generation (REQ-CAUSAL-02/07/11).

Only `purge_engulf` signals are in scope: `backtest.population._population_cuts`
unconditionally excludes every `fvg_fill` signal (`excluded_no_crt_range`)
before a Candidate is ever built from it, so `fvg_fill` signals can never
violate I1-I4 — they never reach the invariant-bearing population. Restricting
the causal path to the channel that actually produces Candidates is a scope
decision (YAGNI), not an omission.
"""

from core.candle import OHLCSeries
from core.config import Model1Config
from core.results import DetectionStatus
from entries.model1 import Model1Signal, _purge_signals, _track_anchor
from primitives.crt_range import CRTRange


def r_strict_admissible(source_range: CRTRange, retest_index: int | None) -> bool:
    """REQ-CAUSAL-07 (R-strict): `source_range` may produce/compete for a
    signal whose own event index is `retest_index = K` iff
    `source_range.resolved_at_index <= K - 1`. A signal with no retest
    event (`retest_index is None`, never confirmed/invalidated-pre-confirm)
    has no K to test against — vacuously admissible, since such a signal
    can never become a Candidate (REQ-CAUSAL-04 governs that exclusion, not
    this predicate)."""
    if retest_index is None:
        return True
    return source_range.resolved_at_index <= retest_index - 1


def causal_purge_engulf_signals(
    ltf_series: OHLCSeries, ltf_ranges: list[CRTRange], config: Model1Config = Model1Config(),
    htf_series: OHLCSeries | None = None, htf_ranges: list[CRTRange] | None = None,
) -> list[Model1Signal]:
    """REQ-CAUSAL-02/07/11: the causally-stable `purge_engulf` signal set
    produced from an already-causal LTF range set (`causal.ranges.
    causal_crt_ranges`). `_purge_signals` is reused UNCHANGED (Line-A
    isolation) — it already computes, per range, up to one bearish and one
    bullish anchor-tracked signal via `_track_anchor`, a pure function of
    `(candles, anchor_index, direction, config)` alone (REQ-CAUSAL-11's own
    proof), so every signal sharing `(anchor_index, direction)` is
    identical except for `origin_index`/`purge_target` (which encode only
    which range produced it).

    Competing source ranges for the same `(anchor_index, direction)` are
    filtered to the R-strict-admissible set (REQ-CAUSAL-07) before applying
    `_dedup`'s own `min(origin_index)` survivor rule (REQ-CAUSAL-11) — a
    group with NO admissible source does not causally exist at all (its
    only real-world producers all resolved too late relative to the
    event), which is how this closes B1/B2 without needing to touch
    `_dedup` itself.

    `htf_series`/`htf_ranges` (odd/tasks/model1-causal-retry-chain.md
    T4/T5, optional and paired — `None` preserves this function's exact
    original behavior for every existing caller/test): once a group's
    winner is picked by the R-strict dedup above (unchanged), if that
    winner's single-anchor result INVALIDATED before confirming, retry
    with `causal.retry_chain` instead of settling it as final — the chain
    is applied only AFTER dedup, to the already-selected winning `(range,
    signal)` pair, never by re-running dedup against the chain's eventual
    anchor/retest_index. R-strict's own competition semantics are
    therefore unchanged by this parameter. The chain's own HTF stop-check
    uses `htf_ranges` fresh at every invalidation (via H-A, same as
    `causal.generate`'s own HTF-context selection) — it is NOT the LTF
    `winning_range` passed alongside it, which only supplies the LTF
    anchor's own purge target.
    """
    candles = ltf_series.candles
    raw: list[tuple[CRTRange, Model1Signal]] = [
        (source_range, signal)
        for source_range in ltf_ranges
        for signal in _purge_signals(candles, source_range, config)
    ]

    groups: dict[tuple[int, str], list[tuple[CRTRange, Model1Signal]]] = {}
    for source_range, signal in raw:
        groups.setdefault((signal.anchor_index, signal.direction), []).append((source_range, signal))

    causal_signals: list[Model1Signal] = []
    for pairs in groups.values():
        retest_index = pairs[0][1].retest_index
        admissible = [pair for pair in pairs if r_strict_admissible(pair[0], retest_index)]
        if not admissible:
            continue
        winning_range, winning_signal = min(admissible, key=lambda pair: pair[0].start_index)
        if htf_series is not None and winning_signal.status == DetectionStatus.INVALIDATED:
            from causal.retry_chain import chained_purge_engulf_signal  # local: avoids a signals<->retry_chain import cycle

            chained = chained_purge_engulf_signal(
                candles, winning_signal.anchor_index, winning_signal.direction, winning_range,
                config, winning_range.start_index, htf_series, htf_ranges or [],
            )
            if chained is not None:
                causal_signals.append(chained)
            continue
        causal_signals.append(_causally_settle(candles, winning_signal, config))
    return causal_signals


def _causally_settle(
    candles: tuple, signal: Model1Signal, config: Model1Config
) -> Model1Signal:
    """`_track_anchor` (REQ-CAUSAL-11's own proof) freezes every field I1-I4
    care about -- `anchor_index`/`direction`/`entry_type`/`entry_price`/
    `retest_index` -- no later than the retest candle `K = retest_index`
    itself; only `status`/`confirmation_index` can still change from candles
    strictly after `K` (a later breach or close-beyond-open the original,
    possibly-longer-prefix scan happened to see). Neither field is read
    downstream (`backtest.population._population_cuts` gates only on
    `retest_index is None`; `_build_candidate` never reads `status`), but
    leaving them un-normalized would still mean the emitted `Model1Signal`
    is not itself byte-identical across growing prefixes (I1). Re-running
    `_track_anchor` on `candles[:K+1]` -- the exact causal boundary for this
    signal's own event -- reproduces every already-frozen field unchanged
    (the scan up to K is identical) and pins `status`/`confirmation_index`
    to the one value a caller who only ever had data up to K could have
    seen, closing the gap without touching `_track_anchor`'s own logic."""
    if signal.retest_index is None:
        return signal
    settled = _track_anchor(
        candles[: signal.retest_index + 1],
        signal.anchor_index,
        signal.direction,
        signal.purge_target,
        signal.confirmation_type,
        config,
        signal.origin_index,
    )
    assert settled is not None  # the original (wider) scan already confirmed + retested by K
    return settled
