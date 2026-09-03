import ast
from datetime import datetime, timedelta
from pathlib import Path

from fixtures.synthetic import (
    key_level_confluence_pair_setup,
    model1_pending_setup,
    model1_purge_engulf_charter2_setup,
)

from alignment.htf_ltf import tag_alignment
from core.candle import Candle, OHLCSeries
from core.config import CRTRangeConfig
from core.key_level import KeyLevel
from core.results import DetectionStatus
from primitives.fvg import detect_fvgs, to_key_levels


def _shift(series: OHLCSeries, offset: timedelta, timeframe: str | None = None) -> OHLCSeries:
    candles = tuple(
        Candle(timestamp=c.timestamp + offset, open=c.open, high=c.high, low=c.low, close=c.close)
        for c in series.candles
    )
    return OHLCSeries(candles=candles, instrument=series.instrument, timeframe=timeframe or series.timeframe)


def _htf_series(*, candle_specs: list[tuple], start: datetime, step: timedelta, timeframe: str) -> OHLCSeries:
    candles = tuple(
        Candle(timestamp=start + i * step, open=o, high=h, low=l, close=c)
        for i, (o, h, l, c) in enumerate(candle_specs)
    )
    return OHLCSeries(candles=candles, instrument="EURUSD", timeframe=timeframe)


# HTF range: candle0 establishes range (H=1.1020,L=1.0980); candle1 stays
# trapped (no breach); candle2 purges the High (wick to 1.1035, closes back
# inside 1.1005); candle3 closes below the Low (1.0960) -> true_break,
# resolved_at_index=3, model=multi-inside, purge candle = index2.
_HTF_MULTI_INSIDE_SPECS = [
    (1.1000, 1.1020, 1.0980, 1.1010),  # 0 — range
    (1.1005, 1.1015, 1.0990, 1.1000),  # 1 — trapped
    (1.1010, 1.1035, 1.1000, 1.1005),  # 2 — purges High
    (1.1000, 1.1005, 1.0950, 1.0960),  # 3 — closes below Low -> true_break
]


def test_ltf_signal_inside_htf_purge_window_is_aligned():
    """REQ-05.1, grounded charter-2 [00:12:34]-[00:13:55]: an LTF Model-1
    signal whose anchor timestamp falls within the HTF purge candle's own
    1H window -> aligned, htf_context set to the resolved HTF CRTRange.
    """
    htf_series = _htf_series(
        candle_specs=_HTF_MULTI_INSIDE_SPECS,
        start=datetime(2026, 1, 1, 12, 0, 0),
        step=timedelta(hours=1),
        timeframe="1H",
    )
    # anchor_index=1 in this LTF fixture defaults to timestamp 2026-01-01
    # 13:00 (1H builder spacing off _KILL_ZONE_BASE) — shift it to land
    # inside the HTF purge candle's window [14:00, 15:00): candle2
    # (t=13:00) shifts to t=14:00.
    ltf_series = _shift(
        model1_purge_engulf_charter2_setup(),
        offset=timedelta(hours=1),
        timeframe="5M",
    )

    tags = tag_alignment(htf_series, ltf_series)

    signal_tag = next(t for t in tags if t.ltf_signal.anchor_index == 1 and t.ltf_signal.direction == "bearish")
    assert signal_tag.aligned == "aligned"
    assert signal_tag.htf_context is not None
    assert signal_tag.htf_context.start_index == 0
    assert signal_tag.htf_context.model == "multi-inside"


def test_ltf_signal_outside_any_purge_window_is_unaligned():
    """REQ-05.2: an LTF Model-1 signal whose anchor timestamp maps to an
    HTF candle that never purges the range -> unaligned, no htf_context.
    """
    htf_series = _htf_series(
        candle_specs=_HTF_MULTI_INSIDE_SPECS,
        start=datetime(2026, 1, 1, 12, 0, 0),
        step=timedelta(hours=1),
        timeframe="1H",
    )
    # anchor_index=1 stays at its default t=13:00 -> maps to HTF candle1
    # (t=13:00), which is "trapped" (no purge) in this HTF series.
    ltf_series = _shift(
        model1_purge_engulf_charter2_setup(), offset=timedelta(0), timeframe="5M"
    )

    tags = tag_alignment(htf_series, ltf_series)

    signal_tag = next(t for t in tags if t.ltf_signal.anchor_index == 1 and t.ltf_signal.direction == "bearish")
    assert signal_tag.aligned == "unaligned"
    assert signal_tag.htf_context is None


def test_ltf_signal_near_htf_tail_with_partial_coverage_is_insufficient():
    """REQ-05.3, ADR-05: the LTF signal's relevant HTF candle is the LAST
    one in the HTF series, and the LTF series' own last candle ends before
    that HTF candle's full 1H span -> insufficient_htf_data, never dropped
    and never forced into aligned/unaligned.
    """
    htf_series = _htf_series(
        candle_specs=[
            (1.1000, 1.1010, 1.0990, 1.1005),  # 0
            (1.1005, 1.1020, 1.1000, 1.1015),  # 1 — last HTF candle, spans [13:00, 14:00)
        ],
        start=datetime(2026, 1, 1, 12, 0, 0),
        step=timedelta(hours=1),
        timeframe="1H",
    )
    o, h, l, c = 1.1000, 1.1020, 1.0980, 1.1010
    o1, h1, l1, c1 = 1.1010, 1.1035, 1.1005, 1.1015
    o2, h2, l2, c2 = 1.1000, 1.1005, 1.0990, 1.0995
    ltf_series = OHLCSeries(
        candles=(
            Candle(timestamp=datetime(2026, 1, 1, 13, 0, 0), open=o, high=h, low=l, close=c),
            Candle(timestamp=datetime(2026, 1, 1, 13, 30, 0), open=o1, high=h1, low=l1, close=c1),
            Candle(timestamp=datetime(2026, 1, 1, 13, 48, 0), open=o2, high=h2, low=l2, close=c2),
        ),
        instrument="EURUSD",
        timeframe="5M",
    )

    tags = tag_alignment(htf_series, ltf_series)

    signal_tag = next(t for t in tags if t.ltf_signal.anchor_index == 1)
    assert signal_tag.aligned == "insufficient_htf_data"
    assert signal_tag.htf_context is None
    assert signal_tag.ltf_signal.status == DetectionStatus.PENDING


def test_ltf_signal_before_first_htf_candle_has_no_enclosing_index():
    """Bug 1c regression (bisect swap): an LTF anchor timestamp strictly
    before the HTF series' very first candle has no enclosing HTF index at
    all — pins the "no candle at or before" branch, which `bisect_right`
    returning position 0 must still map to None, matching the old linear
    scan's behavior exactly.
    """
    htf_series = _htf_series(
        candle_specs=_HTF_MULTI_INSIDE_SPECS,
        start=datetime(2026, 1, 1, 12, 0, 0),
        step=timedelta(hours=1),
        timeframe="1H",
    )
    # anchor_index=1 defaults to t=13:00 (see other tests in this file);
    # shifting -2h puts it strictly before the HTF series' t=12:00 start.
    ltf_series = _shift(
        model1_purge_engulf_charter2_setup(), offset=-timedelta(hours=2), timeframe="5M"
    )

    tags = tag_alignment(htf_series, ltf_series)

    signal_tag = next(t for t in tags if t.ltf_signal.anchor_index == 1 and t.ltf_signal.direction == "bearish")
    assert signal_tag.aligned == "unaligned"
    assert signal_tag.htf_context is None


def test_crt_config_is_read_through_not_hardcoded():
    """REQ-25: `crt_config` is threaded through to BOTH the HTF and the
    LTF's own internal CRT range detection (crt_range.py already proves
    max_lookback itself is config-driven, not hardcoded — this test proves
    `tag_alignment` actually passes the parameter through rather than
    silently using a default). A max_lookback of 0 leaves no room for ANY
    CRT range (HTF or LTF) to resolve, since resolution always needs at
    least 1 forward candle — collapsing the default set of aligned tags to
    none.
    """
    htf_series = _htf_series(
        candle_specs=_HTF_MULTI_INSIDE_SPECS,
        start=datetime(2026, 1, 1, 12, 0, 0),
        step=timedelta(hours=1),
        timeframe="1H",
    )
    ltf_series = _shift(
        model1_purge_engulf_charter2_setup(),
        offset=timedelta(hours=1),
        timeframe="5M",
    )

    default_tags = tag_alignment(htf_series, ltf_series)
    strict_tags = tag_alignment(htf_series, ltf_series, crt_config=CRTRangeConfig(max_lookback=0))

    assert any(t.aligned == "aligned" for t in default_tags)
    assert strict_tags == []


def _bearish_signal_tag(tags):
    return next(t for t in tags if t.ltf_signal.anchor_index == 1 and t.ltf_signal.direction == "bearish")


def test_high_side_breach_credited_when_extreme_inside_unexpired_zone():
    """REQ-55.1: an aligned signal whose HTF purge candle breached its CRT
    range's high, with high=1.1035 inside an unexpired Key Level
    [1.1030, 1.1050] with an earlier origin_index, is credited that Key
    Level — notwithstanding the signal's own direction being bearish."""
    htf_specs = [
        (1.1000, 1.1020, 1.0980, 1.1010),  # 0 — range H=1.1020 L=1.0980
        (1.1010, 1.1035, 1.1000, 1.1005),  # 1 — purges High(1.1035), closes back inside
        (1.1000, 1.1005, 1.0950, 1.0960),  # 2 — closes below Low -> true_break
    ]
    htf_series = _htf_series(
        candle_specs=htf_specs, start=datetime(2026, 1, 1, 12, 0, 0), step=timedelta(hours=1), timeframe="1H",
    )
    ltf_series = _shift(model1_purge_engulf_charter2_setup(), offset=timedelta(0), timeframe="5M")
    key_level = KeyLevel(kind="fvg", top=1.1050, bottom=1.1030, origin_index=0)

    tags = tag_alignment(htf_series, ltf_series, htf_key_levels=[key_level])

    signal_tag = _bearish_signal_tag(tags)
    assert signal_tag.aligned == "aligned"
    assert signal_tag.key_level == key_level


def test_low_side_breach_credited_when_extreme_inside_unexpired_zone():
    """REQ-55.2: mirror of REQ-55.1 for a low-side purge breach."""
    htf_specs = [
        (1.1000, 1.1020, 1.0980, 1.1010),  # 0 — range H=1.1020 L=1.0980
        (1.1005, 1.1015, 1.0965, 1.0995),  # 1 — pokes Low(1.0965), closes back inside
        (1.1000, 1.1005, 1.0950, 1.1025),  # 2 — closes above High -> true_break
    ]
    htf_series = _htf_series(
        candle_specs=htf_specs, start=datetime(2026, 1, 1, 12, 0, 0), step=timedelta(hours=1), timeframe="1H",
    )
    ltf_series = _shift(model1_purge_engulf_charter2_setup(), offset=timedelta(0), timeframe="5M")
    key_level = KeyLevel(kind="fvg", top=1.0975, bottom=1.0960, origin_index=0)

    tags = tag_alignment(htf_series, ltf_series, htf_key_levels=[key_level])

    signal_tag = _bearish_signal_tag(tags)
    assert signal_tag.aligned == "aligned"
    assert signal_tag.key_level == key_level


def test_both_sides_breached_each_evaluated_independently_higher_origin_wins():
    """REQ-63.4 (V3, was REQ-55.6/lower-wins under V2): a purge candle
    breaching BOTH sides has each extreme evaluated independently against
    its own matching Key Level; the level with the HIGHER origin_index
    (most recent) is recorded across both extremes — flipped from V2's
    oldest-wins so the most recent Daily Key Level takes priority."""
    htf_specs = [
        (1.1000, 1.1010, 1.0995, 1.1005),  # 0 — filler
        (1.1005, 1.1010, 1.0995, 1.1002),  # 1 — filler
        (1.1000, 1.1020, 1.0980, 1.1010),  # 2 — range H=1.1020 L=1.0980
        (1.1005, 1.1045, 1.0955, 1.1000),  # 3 — breaches BOTH high(1.1045) and low(1.0955), closes inside
        (1.1000, 1.1005, 1.0950, 1.1025),  # 4 — closes above High -> true_break
    ]
    htf_series = _htf_series(
        candle_specs=htf_specs, start=datetime(2026, 1, 1, 12, 0, 0), step=timedelta(hours=1), timeframe="1H",
    )
    ltf_series = _shift(model1_purge_engulf_charter2_setup(), offset=timedelta(hours=2), timeframe="5M")
    high_side_level = KeyLevel(kind="fvg", top=1.1050, bottom=1.1040, origin_index=2)
    low_side_level = KeyLevel(kind="fvg", top=1.0960, bottom=1.0950, origin_index=0)

    tags = tag_alignment(htf_series, ltf_series, htf_key_levels=[high_side_level, low_side_level])

    signal_tag = _bearish_signal_tag(tags)
    assert signal_tag.aligned == "aligned"
    assert signal_tag.key_level == high_side_level  # higher origin_index (2 > 0) wins


_DAILY_HTF_SPECS = [
    (1.1000, 1.1020, 1.0980, 1.1010),  # 0 — range H=1.1020 L=1.0980
    (1.1010, 1.1035, 1.1000, 1.1005),  # 1 — purges High(1.1035), closes back inside
    (1.1000, 1.1005, 1.0950, 1.0960),  # 2 — closes below Low -> true_break
]
_DAILY_ZONE = {"top": 1.1050, "bottom": 1.1030}  # contains the purge wick extreme, 1.1035


def _daily_htf_series():
    """H4 series purging at index 1, 09:00-13:00-17:00 on 2026-01-01 —
    same shape as test_high_side_breach_credited_when_extreme_inside_unexpired_zone,
    timestamps chosen so a Daily boundary of 2026-01-01 00:00 lands AT/BEFORE
    candle 0 and a Daily boundary of 2026-01-02 00:00 lands AFTER candle 2."""
    return _htf_series(
        candle_specs=_DAILY_HTF_SPECS, start=datetime(2026, 1, 1, 9, 0, 0),
        step=timedelta(hours=4), timeframe="4H",
    )


def _daily_series():
    """2 Daily candles: confirmation on index 0 (2025-12-31) closes at
    2026-01-01 00:00 (<= the HTF series' own first candle); confirmation on
    index 1 (2026-01-01) closes at 2026-01-02 00:00 (after the HTF series'
    last candle, 17:00 on 2026-01-01) — i.e. index 1 is "not yet knowable"
    against the HTF purge below."""
    return _htf_series(
        candle_specs=[(1.1, 1.1, 1.1, 1.1), (1.1, 1.1, 1.1, 1.1)],
        start=datetime(2025, 12, 31, 0, 0, 0), step=timedelta(days=1), timeframe="D",
    )


def test_daily_key_level_confirmed_before_purge_boundary_is_credited():
    """REQ-63.5: a Daily-sourced KeyLevel confirmed on Daily candle 0 (whose
    close boundary lands at/before the HTF purge candle) IS reindexed into
    H4-index-space and credited, exactly like an H4-native KeyLevel would
    be at the same effective time."""
    htf_series = _daily_htf_series()
    ltf_series = _shift(model1_purge_engulf_charter2_setup(), offset=timedelta(0), timeframe="5M")
    daily_key_level = KeyLevel(kind="ict_order_block", origin_index=0, **_DAILY_ZONE)

    tags = tag_alignment(
        htf_series, ltf_series, daily_series=_daily_series(), daily_key_levels=[daily_key_level],
    )

    signal_tag = _bearish_signal_tag(tags)
    assert signal_tag.aligned == "aligned"
    assert signal_tag.key_level is not None
    assert signal_tag.key_level.kind == "ict_order_block"


def test_daily_key_level_not_yet_knowable_at_purge_time_is_not_credited():
    """REQ-63.5 (edge): a Daily-sourced KeyLevel confirmed on Daily candle 1
    (whose close boundary lands AFTER every HTF candle in this fixture) is
    reindexed to an out-of-range H4 index and is NEVER credited — proves
    the reindex is not a no-op / always-match."""
    htf_series = _daily_htf_series()
    ltf_series = _shift(model1_purge_engulf_charter2_setup(), offset=timedelta(0), timeframe="5M")
    daily_key_level = KeyLevel(kind="ict_order_block", origin_index=1, **_DAILY_ZONE)

    tags = tag_alignment(
        htf_series, ltf_series, daily_series=_daily_series(), daily_key_levels=[daily_key_level],
    )

    signal_tag = _bearish_signal_tag(tags)
    assert signal_tag.aligned == "aligned"
    assert signal_tag.key_level is None


_EARLY_TOUCH_HTF_SPECS = [
    (1.1010, 1.1035, 1.1000, 1.1005),  # 0 — EARLY TOUCH: high=1.1035 lands inside _DAILY_ZONE
    (1.1000, 1.1020, 1.0980, 1.1010),  # 1 — range establish H=1.1020 L=1.0980
    (1.1005, 1.1015, 1.0990, 1.1000),  # 2 — trapped
    (1.1010, 1.1035, 1.1000, 1.1005),  # 3 — purges High(1.1035) -- ALSO lands inside the zone
    (1.1000, 1.1005, 1.0950, 1.0960),  # 4 — closes below Low -> true_break
]


def _early_touch_htf_series():
    """5 H4 candles, 09:00/13:00/17:00/21:00/next-day-01:00 on 2026-01-01 —
    candle 0 (the reindexed origin) touches the zone immediately; the real
    CRT purge only happens later, at candle 3, which ALSO touches the zone
    but must be excluded once expiry is set at candle 0."""
    return _htf_series(
        candle_specs=_EARLY_TOUCH_HTF_SPECS, start=datetime(2026, 1, 1, 9, 0, 0),
        step=timedelta(hours=4), timeframe="4H",
    )


def test_daily_key_level_expiry_is_the_first_htf_candle_that_overlaps_the_zone():
    """REQ-63.7 (V4): expiry_index for a Daily-sourced KeyLevel is NOT a
    translated Daily-native boundary (V3's bug) — it's the first H4 candle,
    scanning from the reindexed origin, whose OWN range overlaps the zone.
    Here that's candle 0 itself (touches immediately) — so the level is
    already expired by the time the real CRT purge happens at candle 3,
    even though candle 3's wick would otherwise match the zone too."""
    htf_series = _early_touch_htf_series()
    ltf_series = _shift(model1_purge_engulf_charter2_setup(), offset=timedelta(hours=8), timeframe="5M")
    daily_key_level = KeyLevel(kind="ict_order_block", origin_index=0, **_DAILY_ZONE)

    tags = tag_alignment(
        htf_series, ltf_series, daily_series=_daily_series(), daily_key_levels=[daily_key_level],
    )

    signal_tag = _bearish_signal_tag(tags)
    assert signal_tag.aligned == "aligned"
    assert signal_tag.key_level is None


def test_wick_extreme_just_outside_zone_yields_no_confluence():
    """REQ-63.6 (V3 reconfirmation, not a behaviour change): a purge wick
    extreme that misses a Key Level's zone by any margin, however small,
    yields no confluence — exact overlap only, no tolerance. Locks the
    existing `level.bottom <= extreme <= level.top` check in as a
    regression guard against the tempting-but-rejected 10%-tolerance
    alternative (spec.md REQ-63, `htf_confluence.py` precedent)."""
    htf_specs = [
        (1.1000, 1.1020, 1.0980, 1.1010),  # 0 — range H=1.1020 L=1.0980
        (1.1010, 1.1035, 1.1000, 1.1005),  # 1 — purges High(1.1035), closes back inside
        (1.1000, 1.1005, 1.0950, 1.0960),  # 2 — closes below Low -> true_break
    ]
    htf_series = _htf_series(
        candle_specs=htf_specs, start=datetime(2026, 1, 1, 12, 0, 0), step=timedelta(hours=1), timeframe="1H",
    )
    ltf_series = _shift(model1_purge_engulf_charter2_setup(), offset=timedelta(0), timeframe="5M")
    # Zone top is 0.0001 below the purge wick extreme (1.1035) — a near-miss.
    key_level = KeyLevel(kind="fvg", top=1.1034, bottom=1.1020, origin_index=0)

    tags = tag_alignment(htf_series, ltf_series, htf_key_levels=[key_level])

    signal_tag = _bearish_signal_tag(tags)
    assert signal_tag.aligned == "aligned"
    assert signal_tag.key_level is None


def test_direction_based_wick_selection_must_fail_this_scenario():
    """REQ-55.7: the purge breached the CRT high ONLY, so the credited
    extreme is 1.1035 (high side); direction is therefore bearish. A Key
    Level containing the theoretical LOW extreme but NOT the high extreme
    must NOT be credited — an implementation selecting the wick by
    `direction` (wrongly reading bearish -> low) would wrongly credit it."""
    htf_specs = [
        (1.1000, 1.1020, 1.0980, 1.1010),  # 0 — range H=1.1020 L=1.0980
        (1.1010, 1.1035, 1.1000, 1.1005),  # 1 — purges High(1.1035) ONLY, closes back inside
        (1.1000, 1.1005, 1.0950, 1.0960),  # 2 — closes below Low -> true_break
    ]
    htf_series = _htf_series(
        candle_specs=htf_specs, start=datetime(2026, 1, 1, 12, 0, 0), step=timedelta(hours=1), timeframe="1H",
    )
    ltf_series = _shift(model1_purge_engulf_charter2_setup(), offset=timedelta(0), timeframe="5M")
    # Contains the range LOW (1.0980), never breached by this purge — a
    # direction-based (bearish -> low) implementation would wrongly match it.
    low_side_level = KeyLevel(kind="fvg", top=1.0985, bottom=1.0975, origin_index=0)

    tags = tag_alignment(htf_series, ltf_series, htf_key_levels=[low_side_level])

    signal_tag = _bearish_signal_tag(tags)
    assert signal_tag.aligned == "aligned"
    assert signal_tag.key_level is None


def test_minimal_pair_builder_confluent_and_non_confluent_twins_agree_with_expectation():
    """Design §8.9: the minimal-pair fixture's `expected_key_level` for
    each variant matches what a real HTF FVG source (`to_key_levels(
    detect_fvgs(...))`) actually produces through `tag_alignment` — proves
    the builder itself is wired correctly for S-001..S-004's consumption."""
    for confluent in (True, False):
        pair = key_level_confluence_pair_setup(confluent=confluent)
        htf_key_levels = to_key_levels(detect_fvgs(pair.htf_series))

        tags = tag_alignment(pair.htf_series, pair.ltf_series, htf_key_levels=htf_key_levels)

        signal_tag = _bearish_signal_tag(tags)
        assert signal_tag.aligned == "aligned"
        assert signal_tag.key_level == pair.expected_key_level


def test_htf_ltf_imports_unchanged():
    """REQ-63.3 regression guard: `alignment/htf_ltf.py` stays source-agnostic
    -- it must keep importing `core.key_level` (the normalised, source-agnostic
    type) and must NEVER import a source detector's own type (`primitives.
    ict_order_block`, `core.structure_break`, `composite.mss`), which would
    reintroduce the coupling SEAM-01 exists to avoid."""
    module_path = Path(__file__).resolve().parent.parent / "alignment" / "htf_ltf.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))

    imported_modules = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }

    assert "core.key_level" in imported_modules
    assert "primitives.ict_order_block" not in imported_modules
    assert "core.structure_break" not in imported_modules
    assert "composite.mss" not in imported_modules
