"""Chained-anchor Model-1 retry (odd/tasks/model1-causal-retry-chain.md
S2-S4, confirmed with the user 2026-11-11):

- S2: on LTF, when the current anchor's close breaches its own protected
  extreme before any confirmation (`entries.model1`'s pre-confirmation
  INVALIDATED branch), the breaching candle becomes a NEW current anchor
  and tracking continues -- a single invalidation no longer ends the
  search.
- S3: the chain stops retrying only when the relevant HTF range -- the
  one H-A (`causal.htf.select_htf_context`) would currently attribute to
  this moment -- has itself been truly broken (`resolution == "true_break"`),
  known as of the invalidating candle's own timestamp. `select_htf_context`
  already only returns a range whose resolution is closed by that
  timestamp, so no separate closure check is needed here. The user
  confirmed this is ONE condition ("superar el low del key level de HTF"
  and "el HTF candle cierra más allá del low que queríamos purgar" are the
  same event) -- exactly `primitives.crt_range`'s `true_break`
  classification on whichever range H-A selects at that moment. A
  `"false_break"` resolution (or no closed range at all yet) never stops
  the chain.
- S4: mirror low/high for bearish/bullish; confirmation may land on the
  first anchor or several retries later.

Important: the LTF anchor's own purge target (what price level it is
purging on the LTF series) is an LTF-native `CRTRange` (`ltf_range`,
unrelated to the HTF stop-check) -- it is NOT the HTF range. Those are two
different things: which LTF range a signal's anchor purges (fixed, from
`causal.signals`' own R-strict dedup) versus which HTF context is
currently relevant for deciding whether to keep retrying (re-evaluated at
every invalidation via H-A, since the relevant HTF range can itself change
as more candles become knowable).

The check runs only at the moment an anchor invalidates (as the user's own
walkthrough frames it) -- an anchor that is still alive and tracking
normally is not re-checked candle by candle against the HTF break; it
either confirms, goes PENDING, or itself invalidates and triggers the next
check. This is the stop condition's exact (and only) scope per the
confirmed spec, not a simplification of a broader one.

Built here, never by editing `entries.model1._track_anchor` in place:
`causal.signals.causal_purge_engulf_signals`'s own causal-correctness
proof relies on `_track_anchor` staying "a pure function of (candles,
anchor_index, direction, config) alone" (REQ-CAUSAL-11) -- this module
composes repeated calls to it instead.
"""

from causal.htf import select_htf_context
from causal.signals import _causally_settle
from core.candle import Candle, OHLCSeries
from core.config import Model1Config
from core.results import DetectionStatus
from entries.model1 import Direction, Model1Signal, _track_anchor
from primitives.crt_range import CRTRange


def chained_purge_engulf_signal(
    candles: tuple[Candle, ...],
    anchor_index: int,
    direction: Direction,
    ltf_range: CRTRange,
    config: Model1Config,
    origin_index: int,
    htf_series: OHLCSeries,
    htf_ranges: list[CRTRange],
) -> Model1Signal | None:
    purge_target = ltf_range.high if direction == "bearish" else ltf_range.low
    current_anchor = anchor_index

    while True:
        result = _track_anchor(
            candles, current_anchor, direction, purge_target, "purge_engulf", config, origin_index
        )
        if result is None:
            return None
        if result.status != DetectionStatus.INVALIDATED:
            return _causally_settle(candles, result, config)

        breach_index = result.confirmation_index
        t = candles[breach_index].timestamp
        htf_context = select_htf_context(htf_series, htf_ranges, t)
        if htf_context is not None and htf_context.resolution == "true_break":
            return result  # the HTF level H-A currently attributes to this moment broke -- chain exhausted
        if breach_index >= len(candles) - 1:
            return result  # no further candle to re-anchor from

        current_anchor = breach_index
