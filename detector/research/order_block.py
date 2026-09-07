"""Order Block detection and nearest-active-zone selection — RESEARCH
TOOLING, not a production Key Level source.

Frozen 2026-09-06. This module promotes, byte-for-byte in behavior, the
Swing -> BOS-by-close -> displacement (>=1x ATR14 over <=3 candles) ->
walk-back (<=10 candles to the last opposing candle) algorithm and the
"nearest active Order Block" selection rule that every prior ablation this
session reproduced by hand, in prose. A reconciliation audit found that
different reasonable readings of that prose produced different bucket
classifications for the same signals — this module exists to end that:
ONE canonical, versioned definition, unit-tested, never prose again.

This is a LEAF package: it may import downward from `core`/`primitives`
(reusing `primitives.swing.detect_swings`, `core.atr.atr`, `core.candle`)
but MUST NEVER be imported by any production layer (`entries`, `alignment`,
`backtest`, `viz`, `cli`) — see `.importlinter`'s `no-research-in-production`
contract. There is a separate, already-triaged SDD change
(`crt-detector-order-block-redefinition`) for eventually wiring a rigorous
Order Block into the live confluence gate; this module is not that, and its
`SELECTION_VERSION` is a research-only marker, never a production version.

Also note this shares nothing with `primitives.ict_order_block` beyond the
domain name "Order Block" — that module implements a completely different,
already-committed 2-candle engulfing rule.
"""

from dataclasses import dataclass
from typing import Literal

from core.atr import atr
from core.candle import OHLCSeries
from primitives.swing import detect_swings

SELECTION_VERSION = "nearest_ob_selection_v1"

_DISPLACEMENT_MULTIPLIER = 1.0
_MAX_OB_LOOKBACK = 10
_MAX_DISPLACEMENT_CANDLES = 3

Direction = Literal["bullish", "bearish"]


@dataclass(frozen=True)
class OrderBlock:
    """`origin_index` is the BOS candle's own index — it is ALSO effectively
    the confirmation index for this algorithm, since an Order Block only
    becomes knowable/confirmed at its own origin_index (there is no separate
    later confirmation step, unlike `primitives.ict_order_block`'s
    anchor/confirmation-candle split). This collapse matters for the
    tie-break in `select_nearest_active_order_block`: "most recently
    originated" and "most recently confirmed" are the same criterion here,
    not two that happen to agree.

    `expiry_index` is the first later index whose CLOSE breaches back
    through the zone (close-based, not wick — see `is_active`); `None` if
    never invalidated.
    """

    direction: Direction
    origin_index: int
    top: float
    bottom: float
    expiry_index: int | None


def detect_order_blocks(daily: OHLCSeries) -> list[OrderBlock]:
    """Swing -> BOS by close -> displacement -> walk-back, exactly as used
    across every prior ablation this session. No config parameter: the
    thresholds below (`_DISPLACEMENT_MULTIPLIER`, `_MAX_OB_LOOKBACK`,
    `_MAX_DISPLACEMENT_CANDLES`) are frozen constants, not tunables — this
    module has exactly one definition, on purpose."""
    candles = daily.candles
    swings = detect_swings(daily)
    last_high: tuple[float, int] | None = None
    last_low: tuple[float, int] | None = None
    used_high_break = used_low_break = False
    order_blocks: list[OrderBlock] = []
    swing_i = 0

    for i in range(2, len(candles)):
        while swing_i < len(swings) and swings[swing_i].index + 1 <= i:
            s = swings[swing_i]
            if s.kind == "high":
                last_high, used_high_break = (s.price, s.index), False
            else:
                last_low, used_low_break = (s.price, s.index), False
            swing_i += 1

        c = candles[i]
        bullish_bos = last_high is not None and not used_high_break and c.close > last_high[0]
        bearish_bos = last_low is not None and not used_low_break and c.close < last_low[0]
        if not (bullish_bos or bearish_bos):
            continue
        if bullish_bos:
            used_high_break = True
        else:
            used_low_break = True

        body = sum(
            abs(candles[j].close - candles[j].open)
            for j in range(i - _MAX_DISPLACEMENT_CANDLES + 1, i + 1)
            if j >= 0
        )
        if body < atr(candles, i) * _DISPLACEMENT_MULTIPLIER:
            continue

        ob_index = None
        for j in range(i - 1, max(-1, i - 1 - _MAX_OB_LOOKBACK), -1):
            is_opposing = candles[j].close < candles[j].open if bullish_bos else candles[j].close > candles[j].open
            if is_opposing:
                ob_index = j
                break
        if ob_index is None:
            continue

        ob_candle = candles[ob_index]
        top, bottom = ob_candle.high, ob_candle.low
        expiry_index = None
        for k in range(i + 1, len(candles)):
            breached = candles[k].close < bottom if bullish_bos else candles[k].close > top
            if breached:
                expiry_index = k
                break

        order_blocks.append(
            OrderBlock(
                direction="bullish" if bullish_bos else "bearish",
                origin_index=i,
                top=top,
                bottom=bottom,
                expiry_index=expiry_index,
            )
        )

    return order_blocks


def is_active(ob: OrderBlock, cutoff_index: int) -> bool:
    """Invalidation is CLOSE-based (not wick), per `detect_order_blocks`
    itself. The expiry boundary is right-closed at `cutoff_index` — an
    Order Block whose `expiry_index` equals `cutoff_index` is still active
    AT that index; it is excluded only once `cutoff_index` moves strictly
    PAST `expiry_index`. This deliberately mirrors this codebase's own
    production convention for `KeyLevel` expiry
    (`alignment.htf_ltf._key_level_credit_map`, REQ-55.9-.11: "exclude only
    purges strictly after expiry" — `purge_index <= level.expiry_index`
    still qualifies) — not invented independently here.

    **Documented reproducibility break (2026-09-06)**: every prior throwaway
    ablation script this session (Order Block Autopsy, the 4-feature
    ablation, the OB x Displacement 2x2, OOS checkpoint #1) used the
    OPPOSITE boundary — `expiry_index is None or expiry_index > cutoff_index`
    (strictly exclusive at cutoff). `is_active` here uses `>=` (inclusive),
    chosen deliberately for consistency with this codebase's own production
    precedent above, NOT to match those prior scripts. This is one of the
    two concrete, named causes of `nearest_ob_selection_v1`'s
    NOT-REPRODUCIBLE classification against historical results (the other
    being the lost/unrecoverable original "nearest OB" tie-break
    convention) — v1 does not, and is not intended to, reproduce those
    prior numbers. See `sdd/crt-detector-key-level-confluence/nearest-ob-v1`
    (engram) for the full classification.

    Mitigation is NOT tracked at all: there is no partial-mitigation state,
    only full invalidation (a close through the zone, per
    `detect_order_blocks`'s own `expiry_index` computation) deactivates.
    This part IS consistent with every prior ablation — not an oversight.
    """
    return ob.origin_index <= cutoff_index and (ob.expiry_index is None or ob.expiry_index >= cutoff_index)


def _distance_to_zone(entry_price: float, ob: OrderBlock) -> float:
    """Distance to the nearest edge of the `[bottom, top]` interval — 0.0
    when `entry_price` sits inside the zone (inclusive of both edges).
    Never midpoint, open, or single-candle-extreme distance."""
    if ob.bottom <= entry_price <= ob.top:
        return 0.0
    if entry_price < ob.bottom:
        return ob.bottom - entry_price
    return entry_price - ob.top


def select_nearest_active_order_block(
    order_blocks: list[OrderBlock], entry_price: float, cutoff_index: int
) -> OrderBlock | None:
    """Nearest active Order Block to `entry_price` as of `cutoff_index`.

    Tie-break (equal minimum distance): the HIGHEST `origin_index` wins —
    "most recently originated" and "most recently confirmed" collapse into
    one criterion for this algorithm (see `OrderBlock.origin_index`'s
    docstring). No further tie-break criterion is added: `origin_index`
    values are guaranteed unique across one `detect_order_blocks` call — the
    detection loop's `for i in range(2, len(candles))` visits each Daily
    index at most once and appends at most one `OrderBlock` per matching
    `i` — so a min-by-`(distance, -origin_index)` key can never actually
    tie. The key still incorporates `origin_index` (rather than a plain
    `min(candidates, key=distance)`) so the result stays fully deterministic
    and permutation-invariant regardless of input order, defensively, even
    though the tie it guards against is provably unreachable.
    """
    candidates = [ob for ob in order_blocks if is_active(ob, cutoff_index)]
    if not candidates:
        return None
    return min(candidates, key=lambda ob: (_distance_to_zone(entry_price, ob), -ob.origin_index))
