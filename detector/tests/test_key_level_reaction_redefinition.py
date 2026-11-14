from datetime import datetime, timedelta

import pytest

from alignment.htf_ltf import AlignedSignal
from core.candle import Candle
from core.key_level import KeyLevel
from entries.model1 import Model1Signal
from experimental.key_level_reaction_redefinition import (
    KeyLevelReactionRedefinitionError,
    ReactionRedefinitionReport,
    build_redefinition_rows,
    redefine_reaction,
)
from primitives.crt_range import CRTRange


def _candle(i: int, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(
        timestamp=datetime(2026, 1, 1) + timedelta(hours=4 * i),
        open=o, high=h, low=l, close=c,
    )


def _range(*, high: float, low: float, start: int, end: int) -> CRTRange:
    return CRTRange(
        model="2-candle", high=high, low=low, start_index=start, end_index=end,
        resolution="true_break", resolved_at_index=end,
    )


def _signal(anchor_index: int = 0, direction: str = "bullish") -> Model1Signal:
    return Model1Signal(
        anchor_index=anchor_index, direction=direction, purge_target=0.0,
        confirmation_type="purge_engulf", entry_type="wick", entry_price=0.0,
        retest_index=None, status="CONFIRMED", confirmation_index=0, origin_index=0,
    )


def _aligned(crt_range: CRTRange, level: KeyLevel | None, reaction=None) -> AlignedSignal:
    return AlignedSignal(
        ltf_signal=_signal(), htf_context=crt_range, aligned="aligned",
        key_level=level, key_level_reaction=reaction,
    )


class TestRedefineReaction:
    def test_none_without_credited_key_level(self) -> None:
        crt_range = _range(high=1.10, low=1.00, start=0, end=1)
        candles = (_candle(0, 1.05, 1.06, 1.04, 1.05), _candle(1, 1.05, 1.11, 1.05, 1.08))
        signal = _aligned(crt_range, level=None)

        assert redefine_reaction(signal, candles) is None

    def test_high_side_genuine_rejection_matches_today(self) -> None:
        """Zone sits entirely ABOVE the CRT range (no overlap). The purge
        wick touches it, the close comes back inside the CRT range AND
        below the zone -- a genuine rejection under both definitions."""
        crt_range = _range(high=1.10, low=1.00, start=0, end=1)
        level = KeyLevel(kind="fvg", top=1.14, bottom=1.12, origin_index=0)
        purge = _candle(1, 1.09, 1.13, 1.08, 1.095)
        candles = (_candle(0, 1.05, 1.06, 1.04, 1.05), purge)
        signal = _aligned(crt_range, level)

        assert redefine_reaction(signal, candles) == "reject_close_inside"

    def test_divergence_zone_dips_into_the_crt_range(self) -> None:
        """The gap this module exists to measure: the zone's near edge sits
        INSIDE the CRT range. The purge wick touches the zone and the close
        comes back inside the CRT range (today's gate would say
        `reject_close_inside`) but the close is STILL inside the zone --
        never having rejected it."""
        crt_range = _range(high=1.10, low=1.00, start=0, end=1)
        level = KeyLevel(kind="ict_order_block", top=1.14, bottom=1.08, origin_index=0)
        purge = _candle(1, 1.09, 1.13, 1.08, 1.095)  # close 1.095: inside [1.00,1.10] AND inside [1.08,1.14]
        candles = (_candle(0, 1.05, 1.06, 1.04, 1.05), purge)
        signal = _aligned(crt_range, level, reaction="reject_close_inside")

        assert signal.key_level_reaction == "reject_close_inside"
        assert redefine_reaction(signal, candles) == "continuation"

    def test_low_side_symmetric_divergence(self) -> None:
        crt_range = _range(high=1.10, low=1.00, start=0, end=1)
        level = KeyLevel(kind="fvg", top=1.02, bottom=0.96, origin_index=0)
        purge = _candle(1, 1.01, 1.02, 0.97, 1.005)  # close 1.005: inside [1.00,1.10] AND inside [0.96,1.02]
        candles = (_candle(0, 1.05, 1.06, 1.04, 1.05), purge)
        signal = _aligned(crt_range, level, reaction="reject_close_inside")

        assert redefine_reaction(signal, candles) == "continuation"

    def test_close_exactly_on_zone_edge_is_still_inside_the_zone(self) -> None:
        """Mirrors the crediting convention's own inclusive-edge rule
        (REQ-55.4: exactly on `bottom` is CREDITED, i.e. still part of the
        zone) -- a close sitting exactly on `level.bottom` has not left the
        zone, so this must be `continuation`, not a rejection."""
        crt_range = _range(high=1.10, low=1.00, start=0, end=1)
        level = KeyLevel(kind="fvg", top=1.14, bottom=1.08, origin_index=0)
        purge = _candle(1, 1.09, 1.13, 1.08, 1.08)  # close exactly on level.bottom
        candles = (_candle(0, 1.05, 1.06, 1.04, 1.05), purge)
        signal = _aligned(crt_range, level)

        assert redefine_reaction(signal, candles) == "continuation"

    def test_low_side_genuine_rejection(self) -> None:
        crt_range = _range(high=1.10, low=1.00, start=0, end=1)
        level = KeyLevel(kind="fvg", top=0.98, bottom=0.96, origin_index=0)
        purge = _candle(1, 1.01, 1.02, 0.97, 1.005)
        candles = (_candle(0, 1.05, 1.06, 1.04, 1.05), purge)
        signal = _aligned(crt_range, level)

        assert redefine_reaction(signal, candles) == "reject_close_inside"

    def test_dual_sided_breach_both_in_zone_is_ambiguous(self) -> None:
        crt_range = _range(high=1.10, low=1.00, start=0, end=1)
        level = KeyLevel(kind="fvg", top=1.20, bottom=0.90, origin_index=0)
        purge = _candle(1, 1.05, 1.12, 0.95, 1.05)  # both sides breach and both sit in [0.90,1.20]
        candles = (_candle(0, 1.05, 1.06, 1.04, 1.05), purge)
        signal = _aligned(crt_range, level)

        assert redefine_reaction(signal, candles) == "ambiguous"

    def test_inconsistent_credit_raises(self) -> None:
        """A key_level that overlaps neither breached extreme is an
        AlignedSignal the production gate should never produce -- raise,
        never silently None."""
        crt_range = _range(high=1.10, low=1.00, start=0, end=1)
        level = KeyLevel(kind="fvg", top=2.00, bottom=1.90, origin_index=0)
        purge = _candle(1, 1.09, 1.13, 1.08, 1.095)
        candles = (_candle(0, 1.05, 1.06, 1.04, 1.05), purge)
        signal = _aligned(crt_range, level)

        with pytest.raises(KeyLevelReactionRedefinitionError):
            redefine_reaction(signal, candles)


class _Trade:
    def __init__(self, signal_id, outcome, r_multiple):
        self.signal_id = signal_id
        self.outcome = outcome
        self.r_multiple = r_multiple


class TestBuildRedefinitionRows:
    def test_skips_signals_without_credited_key_level(self) -> None:
        crt_range = _range(high=1.10, low=1.00, start=0, end=1)
        candles = (_candle(0, 1.05, 1.06, 1.04, 1.05), _candle(1, 1.05, 1.11, 1.05, 1.08))
        signals = [_aligned(crt_range, level=None)]

        rows = build_redefinition_rows(signals, candles, trades=[])

        assert rows == ()

    def test_joins_trade_outcome_on_anchor_and_direction(self) -> None:
        crt_range = _range(high=1.10, low=1.00, start=0, end=1)
        level = KeyLevel(kind="fvg", top=1.14, bottom=1.12, origin_index=0)
        purge = _candle(1, 1.09, 1.13, 1.08, 1.095)
        candles = (_candle(0, 1.05, 1.06, 1.04, 1.05), purge)
        signal = _aligned(crt_range, level, reaction="reject_close_inside")
        trade = _Trade(signal_id=signal.ltf_signal.signal_id, outcome="win", r_multiple=2.0)

        rows = build_redefinition_rows([signal], candles, trades=[trade])

        assert len(rows) == 1
        assert rows[0].outcome == "win"
        assert rows[0].r_multiple == 2.0
        assert rows[0].current_reaction == "reject_close_inside"
        assert rows[0].redefined_reaction == "reject_close_inside"

    def test_duplicate_join_key_raises(self) -> None:
        crt_range = _range(high=1.10, low=1.00, start=0, end=1)
        level = KeyLevel(kind="fvg", top=1.14, bottom=1.12, origin_index=0)
        purge = _candle(1, 1.09, 1.13, 1.08, 1.095)
        candles = (_candle(0, 1.05, 1.06, 1.04, 1.05), purge)
        signal = _aligned(crt_range, level)
        trades = [
            _Trade(signal_id=signal.ltf_signal.signal_id, outcome="win", r_multiple=2.0),
            _Trade(signal_id=signal.ltf_signal.signal_id, outcome="loss", r_multiple=-1.0),
        ]

        with pytest.raises(KeyLevelReactionRedefinitionError):
            build_redefinition_rows([signal], candles, trades=trades)


class TestReactionRedefinitionReport:
    def test_crosstab_and_flipped_and_stats(self) -> None:
        rows = (
            # agrees reject_close_inside under both, wins
            _row("reject_close_inside", "reject_close_inside", "win", 2.0),
            _row("reject_close_inside", "reject_close_inside", "win", 2.0),
            # flips: today says reject_close_inside, redefinition says continuation -- loses
            _row("reject_close_inside", "continuation", "loss", -1.0),
            _row("reject_close_inside", "continuation", "loss", -1.0),
            # agrees continuation under both
            _row("continuation", "continuation", "loss", -1.0),
        )
        report = ReactionRedefinitionReport(rows=rows)

        assert report.crosstab[("reject_close_inside", "reject_close_inside")] == 2
        assert report.crosstab[("reject_close_inside", "continuation")] == 2
        assert len(report.flipped_to_continuation) == 2

        current_stats = report.stats_for("reject_close_inside", using="current")
        assert current_stats["n"] == 4
        assert current_stats["win_rate"] == pytest.approx(0.5)
        assert current_stats["avg_r"] == pytest.approx(0.5)  # (2+2-1-1)/4

        redefined_stats = report.stats_for("reject_close_inside", using="redefined")
        assert redefined_stats["n"] == 2
        assert redefined_stats["win_rate"] == pytest.approx(1.0)
        assert redefined_stats["avg_r"] == pytest.approx(2.0)


def _row(current, redefined, outcome, r_multiple):
    from experimental.key_level_reaction_redefinition import ReactionRedefinitionRow
    return ReactionRedefinitionRow(
        signal_id="0-0-bullish-purge_engulf-wick", anchor_index=0, direction="bullish",
        current_reaction=current, redefined_reaction=redefined,
        outcome=outcome, r_multiple=r_multiple,
    )
