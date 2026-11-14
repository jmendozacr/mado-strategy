"""Breaker Block: the failed Model-1, flipped.

`core.key_level.KeyLevel` has named "Breaker Block later" as a planned
source since v1 with no production code behind it. This is it.

Mado's definition is narrower than the generic ICT "violated order block" —
charter-4 [00:07:35]: "La vela que termina siendo el Breaker Block es, en
el momento en que se forma, la misma vela que los traders leyeron como un
Modelo 1 válido... pero en realidad era un Modelo 1 falso (fake Model 1)
que los dejó atrapados operando en la dirección equivocada." Charter-5
[00:01:59]: the activation is the decisive close through the trapped
level. Charter-4 [00:07:45]: "El retest a esta vela ofrece una zona de
rechazo de alta probabilidad."

That maps 1:1 onto machinery this codebase already has: a `Model1Signal`
with `status == INVALIDATED` is precisely "a Model-1 that looked valid and
then had price close back through the anchor's protected extreme"
(`entries.model1._track_anchor`, line 150's `confirmation_index=j` at the
breach candle — that IS the activation index). No new geometry is
introduced here — only the flip, the zone and the retest.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.candle import Candle, first_overlap_index
from core.config import Model1Config
from core.key_level import KeyLevel
from core.results import DetectionStatus
from entries.model1 import Direction, Model1Signal


@dataclass(frozen=True)
class BreakerBlock:
    anchor_index: int
    """The fake-Model-1 candle — the trap itself (charter-4 [00:07:35])."""

    activation_index: int
    """The close that sprang the trap and flipped the zone's polarity
    (charter-5 [00:01:59]) — `Model1Signal.confirmation_index` at
    INVALIDATED, never knowable earlier."""

    direction: Direction
    """The RIP direction: the opposite of the trapped Model-1's own
    direction (charter-4 [00:07:35] "en la dirección equivocada")."""

    top: float
    bottom: float
    swept_level: float
    """The short-term extreme the trap had purged, carried over from the
    source Model-1's `purge_target`."""

    retest_index: int | None
    """The first return into the zone (charter-4 [00:07:45]) — a bare
    overlap, a touch. `None` when price never came back inside the
    configured window. This is the zone's creditable life as a Key Level
    (`to_key_levels`), NOT the entry: see `recovery_index`."""

    source_signal_id: str

    recovery_index: int | None = None
    """The first candle in the same window whose CLOSE is back inside
    `[bottom, top]` — the only index at which a Turtle-Soup-style entry
    exists. `None` when the zone was touched but never recovered (a bare
    liquidity run). Defaulted so a caller exercising the Key-Level path
    alone states nothing it has not measured."""


def detect_breaker_blocks(
    candles: tuple[Candle, ...],
    model1_signals: list[Model1Signal],
    config: Model1Config = Model1Config(),
) -> list[BreakerBlock]:
    """One block per invalidated Model-1 signal, in input order.

    The retest scan starts strictly AFTER `activation_index`: the
    activation candle closed through the zone and therefore spans it by
    construction. The window is bounded by `Model1Config.max_retest_lookback`,
    reusing the existing bound for "how long a retest stays the same setup"
    rather than adding a second one for the same concept.
    """
    blocks = []
    for signal in model1_signals:
        if signal.status != DetectionStatus.INVALIDATED:
            continue
        anchor = candles[signal.anchor_index]
        top, bottom = max(anchor.open, anchor.close), min(anchor.open, anchor.close)
        activation = signal.confirmation_index
        blocks.append(
            BreakerBlock(
                anchor_index=signal.anchor_index,
                activation_index=activation,
                direction="bullish" if signal.direction == "bearish" else "bearish",
                top=top,
                bottom=bottom,
                swept_level=signal.purge_target,
                retest_index=_retest_index(candles, activation, top, bottom, config),
                source_signal_id=signal.signal_id,
                recovery_index=_recovery_index(candles, activation, top, bottom, config),
            )
        )
    return blocks


def to_key_levels(blocks: list[BreakerBlock]) -> list[KeyLevel]:
    """Mirrors `composite.ict_order_block.to_key_levels`.

    `origin_index` is the activation, not the anchor: the zone is not a
    breaker until the trap springs, and crediting it earlier would let a
    purge be confluenced against a level that did not yet exist.

    `expiry_index` is the retest rather than a later invalidation: for a
    breaker the first return into the zone IS the trade (charter-4
    [00:07:45]), and `alignment.htf_ltf._key_level_credit_map` treats
    expiry right-closed, so the level stays creditable up to and
    including its retest and not after.
    """
    return [
        KeyLevel(
            kind="breaker_block", top=b.top, bottom=b.bottom,
            origin_index=b.activation_index, expiry_index=b.retest_index,
        )
        for b in blocks
    ]


def _window_end(candles: tuple[Candle, ...], activation_index: int, config: Model1Config) -> int:
    """One definition of "how long a retest stays the same setup", shared
    by the touch scan and the recovery scan below — the confirmation
    tightens what counts as an entry inside the window and must not
    quietly extend the window itself."""
    return min(activation_index + config.max_retest_lookback, len(candles) - 1)


def _retest_index(
    candles: tuple[Candle, ...],
    activation_index: int,
    top: float,
    bottom: float,
    config: Model1Config,
) -> int | None:
    end = _window_end(candles, activation_index, config)
    return first_overlap_index(candles[: end + 1], activation_index + 1, top, bottom)


def _recovery_index(
    candles: tuple[Candle, ...],
    activation_index: int,
    top: float,
    bottom: float,
    config: Model1Config,
) -> int | None:
    """Charter-6 [00:03:07]/[00:03:25]: a mere touch doesn't confirm a
    Turtle Soup — "podría ser solo un liquidity run"; only a CLOSE back
    inside the range confirms it. The test (`bottom <= close <= top`) is
    character-for-character `alignment.htf_ltf._purge_reaction`'s
    `reject_close_inside` branch, REPLICATED rather than imported because
    `.importlinter` puts `alignment` strictly above `entries`.

    Scanned over the same window and from the same start as the touch, so
    a recovery landing after `max_retest_lookback` belongs to no setup. No
    separate "was it touched first" precondition is needed: a close inside
    `[bottom, top]` always overlaps the zone, so `recovery_index >=
    retest_index` holds by construction.
    """
    for i in range(activation_index + 1, _window_end(candles, activation_index, config) + 1):
        if bottom <= candles[i].close <= top:
            return i
    return None
