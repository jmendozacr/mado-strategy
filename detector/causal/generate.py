"""Top-level causal candidate generation (REQ-CAUSAL-01..08): produces a
`list[AlignedSignal]` in the exact shape `alignment.htf_ltf.tag_alignment`
produces, so it is a drop-in input to the UNCHANGED
`backtest.population.build_stage6_population` / `backtest.simulate.simulate`
(REQ-CAUSAL-12/13).

Only `purge_engulf` signals with an actual retest event (`retest_index is
not None`) are emitted — a signal that never retests has no event index
`K`, so I1-I4 (each stated "at event index K") do not apply to it by
construction, and `fvg_fill` signals are unconditionally excluded before a
Candidate is ever built from them (`backtest.population._population_cuts`)
— scope decisions documented in the change's own report, not omissions.

Key Level crediting reuses `alignment.htf_ltf`'s own private
`_key_level_credit_map`/`_reindex_daily_key_levels` UNMODIFIED —
REQ-CAUSAL-15 already proves that logic is causal-safe as-is, provided it is
only ever fed the ONE HTF range each signal's own H-A selection (REQ-CAUSAL-
08) actually attributes to it — never a global, all-ranges-derived
`purge_index_to_range` map computed once before the per-signal loop. Two
different signals with different event times `t` can causally require
DIFFERENT HTF ranges for the SAME shared `purge_index` (H-A ties broken by
lowest `start_index` only once a competing range becomes observable at that
signal's own `t`); a single map built once from the full HTF range set
cannot represent that per-signal difference, so crediting is computed here
per signal, seeded with exactly the range `select_htf_context` returned for
it.
"""

from alignment.htf_ltf import AlignedSignal, _key_level_credit_map, _purge_reaction, _reindex_daily_key_levels
from causal.htf import select_htf_context
from causal.ranges import causal_crt_ranges
from causal.signals import causal_purge_engulf_signals
from core.candle import OHLCSeries
from core.config import CRTRangeConfig, Model1Config
from core.key_level import KeyLevel
from primitives.crt_range import first_breach_index


def generate_causal_aligned_signals(
    ltf_series: OHLCSeries,
    htf_series: OHLCSeries,
    crt_config: CRTRangeConfig = CRTRangeConfig(),
    model1_config: Model1Config = Model1Config(),
    htf_key_levels: list[KeyLevel] | None = None,
    daily_series: OHLCSeries | None = None,
    daily_key_levels: list[KeyLevel] | None = None,
) -> list[AlignedSignal]:
    ltf_ranges = causal_crt_ranges(ltf_series, crt_config)
    htf_ranges = causal_crt_ranges(htf_series, crt_config)
    causal_signals = causal_purge_engulf_signals(ltf_series, ltf_ranges, model1_config)

    htf_candles = htf_series.candles
    htf_timestamps = [c.timestamp for c in htf_candles]
    all_key_levels = list(htf_key_levels or [])
    if daily_series is not None and daily_key_levels:
        all_key_levels += _reindex_daily_key_levels(
            daily_key_levels, daily_series.candles, htf_candles, htf_timestamps
        )

    tags: list[AlignedSignal] = []
    for signal in causal_signals:
        if signal.retest_index is None:
            continue
        t = ltf_series.candles[signal.retest_index].timestamp
        htf_context = select_htf_context(htf_series, htf_ranges, t)
        if htf_context is None:
            tags.append(AlignedSignal(ltf_signal=signal, htf_context=None, aligned="unaligned"))
            continue
        purge_index = first_breach_index(
            htf_candles, htf_context.start_index, htf_context.resolved_at_index,
            high=htf_context.high, low=htf_context.low,
        )
        key_level = None
        key_level_reaction = None
        if purge_index is not None:
            # Seed the credit map with exactly the range H-A selected for
            # THIS signal's own `t` -- never a global, all-ranges-derived
            # map that could hold a different competing range for the same
            # purge_index (REQ-CAUSAL-08/15).
            key_level = _key_level_credit_map(
                htf_candles, {purge_index: htf_context}, all_key_levels
            ).get(purge_index)
            if key_level is not None:
                key_level_reaction = _purge_reaction(htf_candles[purge_index], htf_context)
        tags.append(
            AlignedSignal(
                ltf_signal=signal, htf_context=htf_context, aligned="aligned",
                key_level=key_level, key_level_reaction=key_level_reaction,
            )
        )
    return tags
