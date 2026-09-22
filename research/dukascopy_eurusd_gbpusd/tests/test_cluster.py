"""Synthetic tests for remap_to_instrument_day_clusters.

All tests use in-memory fixtures only — no filesystem I/O, no real CSVs,
no production modules are modified, no outcomes are produced.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.candle import Candle, OHLCSeries
from selection.model import (
    CandidateIdentity,
    ClosedTradeOutcome,
    DirectionPolicyObservation,
    OutcomeState,
    Relation,
)
from research.dukascopy_eurusd_gbpusd.cluster import (
    ClusterRemapError,
    remap_to_instrument_day_clusters,
    run_statistics_with_instrument_day_clusters,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EURUSD = "DUKASCOPY_EURUSD"
_GBPUSD = "DUKASCOPY_GBPUSD"

# Helsinki is UTC+2 in winter (EET) and UTC+3 in summer (EEST).
# UTC 22:00 = Helsinki 00:00 next day in winter (UTC+2).
# UTC 21:00 = Helsinki 00:00 next day in summer (UTC+3).

# Winter dates (UTC+2 / EET)
_WINTER_DAY1_LAST_CANDLE = datetime(2023, 1, 15, 21, 45)   # Helsinki: 23:45 Jan 15
_WINTER_DAY2_FIRST_CANDLE = datetime(2023, 1, 15, 22, 0)   # Helsinki: 00:00 Jan 16

# Summer dates (UTC+3 / EEST)
_SUMMER_DAY1_LAST_CANDLE = datetime(2023, 7, 15, 20, 45)   # Helsinki: 23:45 Jul 15
_SUMMER_DAY2_FIRST_CANDLE = datetime(2023, 7, 15, 21, 0)   # Helsinki: 00:00 Jul 16

# Ordinary weekday candles, same day in Helsinki
_MON_09_00_UTC = datetime(2023, 3, 6, 9, 0)   # Helsinki: 11:00 (winter, UTC+2)
_MON_09_15_UTC = datetime(2023, 3, 6, 9, 15)  # Helsinki: 11:15 (same day)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FLAT_PRICE = 1.1000


def _candle(naive_utc: datetime) -> Candle:
    return Candle(
        timestamp=naive_utc,
        open=_FLAT_PRICE,
        high=_FLAT_PRICE,
        low=_FLAT_PRICE,
        close=_FLAT_PRICE,
    )


def _series(instrument: str, *timestamps: datetime) -> OHLCSeries:
    """Build an M15 OHLCSeries from an ordered list of naive-UTC timestamps."""
    return OHLCSeries(
        candles=tuple(_candle(ts) for ts in timestamps),
        instrument=instrument,
        timeframe="15M",
    )


def _never_filled_obs(
    instrument: str,
    retest_index: int,
    policy_id: str = "policy_a",
    signal_id: str = "sig_001",
    relation: Relation = Relation.ALIGNED,
) -> DirectionPolicyObservation:
    return DirectionPolicyObservation(
        candidate_id=CandidateIdentity(
            instrument=instrument,
            timeframe="15M",
            signal_id=signal_id,
            retest_index=retest_index,
        ),
        context_cluster_id=(instrument, 0, 0, 0),  # placeholder — will be replaced
        policy_id=policy_id,
        relation=relation,
        outcome_state=OutcomeState.NEVER_FILLED,
        closed_outcome=None,
        realized_r=None,
    )


def _closed_obs(
    instrument: str,
    retest_index: int,
    realized_r: float = 1.0,
    closed_outcome: ClosedTradeOutcome = ClosedTradeOutcome.WIN,
    policy_id: str = "policy_a",
    signal_id: str = "sig_win",
) -> DirectionPolicyObservation:
    return DirectionPolicyObservation(
        candidate_id=CandidateIdentity(
            instrument=instrument,
            timeframe="15M",
            signal_id=signal_id,
            retest_index=retest_index,
        ),
        context_cluster_id=(instrument, 0, 0, 0),
        policy_id=policy_id,
        relation=Relation.ALIGNED,
        outcome_state=OutcomeState.CLOSED,
        closed_outcome=closed_outcome,
        realized_r=realized_r,
    )


# ---------------------------------------------------------------------------
# Happy-path: cluster identity
# ---------------------------------------------------------------------------

class TestSameInstrumentDaySharesCluster:
    """Two observations from the same instrument on the same Helsinki date
    must receive the same context_cluster_id."""

    def test_two_candles_same_day_same_cluster(self) -> None:
        series = _series(_EURUSD, _MON_09_00_UTC, _MON_09_15_UTC)
        obs_a = _never_filled_obs(_EURUSD, retest_index=0, signal_id="sig_a")
        obs_b = _never_filled_obs(_EURUSD, retest_index=1, signal_id="sig_b")

        result = remap_to_instrument_day_clusters(
            [obs_a, obs_b], {_EURUSD: series}
        )

        assert result[0].context_cluster_id == result[1].context_cluster_id

    def test_cluster_id_is_instrument_day_tuple(self) -> None:
        """Cluster tuple must be (instrument, ordinal, ordinal, ordinal)."""
        from datetime import date

        series = _series(_EURUSD, _MON_09_00_UTC)
        obs = _never_filled_obs(_EURUSD, retest_index=0)

        (remapped,) = remap_to_instrument_day_clusters([obs], {_EURUSD: series})

        # Helsinki: 2023-03-06T11:00+02 → date = 2023-03-06
        expected_date = date(2023, 3, 6)
        ordinal = expected_date.toordinal()
        assert remapped.context_cluster_id == (_EURUSD, ordinal, ordinal, ordinal)

    def test_non_cluster_fields_preserved(self) -> None:
        """Every field other than context_cluster_id must be unchanged."""
        series = _series(_EURUSD, _MON_09_00_UTC)
        obs = _closed_obs(_EURUSD, retest_index=0, realized_r=2.5,
                          closed_outcome=ClosedTradeOutcome.WIN, policy_id="p1")

        (remapped,) = remap_to_instrument_day_clusters([obs], {_EURUSD: series})

        assert remapped.candidate_id == obs.candidate_id
        assert remapped.policy_id == obs.policy_id
        assert remapped.relation == obs.relation
        assert remapped.outcome_state == obs.outcome_state
        assert remapped.closed_outcome == obs.closed_outcome
        assert remapped.realized_r == obs.realized_r

    def test_empty_observations_returns_empty_tuple(self) -> None:
        series = _series(_EURUSD, _MON_09_00_UTC)
        result = remap_to_instrument_day_clusters([], {_EURUSD: series})
        assert result == ()


class TestDifferentDaysSeparateClusters:
    """Observations from different Helsinki calendar dates on the same
    instrument must land in different clusters."""

    def test_winter_midnight_boundary_splits_days(self) -> None:
        """UTC+2: 21:45Z = day N, 22:00Z = day N+1 in Helsinki."""
        series = _series(_EURUSD, _WINTER_DAY1_LAST_CANDLE, _WINTER_DAY2_FIRST_CANDLE)
        obs_a = _never_filled_obs(_EURUSD, retest_index=0, signal_id="sig_a")
        obs_b = _never_filled_obs(_EURUSD, retest_index=1, signal_id="sig_b")

        result = remap_to_instrument_day_clusters(
            [obs_a, obs_b], {_EURUSD: series}
        )

        assert result[0].context_cluster_id != result[1].context_cluster_id

    def test_different_days_ordinals_differ_by_one(self) -> None:
        series = _series(_EURUSD, _WINTER_DAY1_LAST_CANDLE, _WINTER_DAY2_FIRST_CANDLE)
        obs_a = _never_filled_obs(_EURUSD, retest_index=0, signal_id="sig_a")
        obs_b = _never_filled_obs(_EURUSD, retest_index=1, signal_id="sig_b")

        result = remap_to_instrument_day_clusters(
            [obs_a, obs_b], {_EURUSD: series}
        )

        _, ord_a, _, _ = result[0].context_cluster_id
        _, ord_b, _, _ = result[1].context_cluster_id
        assert ord_b - ord_a == 1


class TestDifferentInstrumentsSeparateClusters:
    """Same Helsinki date, different instruments → different clusters because
    the instrument string is the first element of the cluster id tuple."""

    def test_different_instruments_produce_different_cluster_ids(self) -> None:
        series_e = _series(_EURUSD, _MON_09_00_UTC)
        series_g = _series(_GBPUSD, _MON_09_00_UTC)
        obs_e = _never_filled_obs(_EURUSD, retest_index=0)
        obs_g = _never_filled_obs(_GBPUSD, retest_index=0)

        result = remap_to_instrument_day_clusters(
            [obs_e, obs_g], {_EURUSD: series_e, _GBPUSD: series_g}
        )

        assert result[0].context_cluster_id != result[1].context_cluster_id

    def test_same_day_different_instruments_share_ordinal_but_differ_on_instrument(self) -> None:
        series_e = _series(_EURUSD, _MON_09_00_UTC)
        series_g = _series(_GBPUSD, _MON_09_00_UTC)
        obs_e = _never_filled_obs(_EURUSD, retest_index=0)
        obs_g = _never_filled_obs(_GBPUSD, retest_index=0)

        result = remap_to_instrument_day_clusters(
            [obs_e, obs_g], {_EURUSD: series_e, _GBPUSD: series_g}
        )

        inst_e, ord_e, _, _ = result[0].context_cluster_id
        inst_g, ord_g, _, _ = result[1].context_cluster_id
        assert inst_e != inst_g  # instruments differ
        assert ord_e == ord_g    # same Helsinki date → same ordinal


# ---------------------------------------------------------------------------
# DST boundary behaviour in Europe/Helsinki
# ---------------------------------------------------------------------------

class TestDSTBoundaryHelsinki:
    """Europe/Helsinki is UTC+2 in winter (EET) and UTC+3 in summer (EEST).
    The UTC hour at which Helsinki midnight occurs shifts by one hour between
    seasons; remap_to_instrument_day_clusters must apply the correct offset."""

    def test_winter_utc22_is_helsinki_midnight_next_day(self) -> None:
        """2023-01-15T22:00Z → 2023-01-16T00:00 Helsinki (UTC+2, EET)."""
        from datetime import date

        series = _series(_EURUSD, _WINTER_DAY2_FIRST_CANDLE)
        obs = _never_filled_obs(_EURUSD, retest_index=0)

        (remapped,) = remap_to_instrument_day_clusters([obs], {_EURUSD: series})

        expected_ordinal = date(2023, 1, 16).toordinal()
        assert remapped.context_cluster_id[1] == expected_ordinal

    def test_summer_utc21_is_helsinki_midnight_next_day(self) -> None:
        """2023-07-15T21:00Z → 2023-07-16T00:00 Helsinki (UTC+3, EEST)."""
        from datetime import date

        series = _series(_EURUSD, _SUMMER_DAY2_FIRST_CANDLE)
        obs = _never_filled_obs(_EURUSD, retest_index=0)

        (remapped,) = remap_to_instrument_day_clusters([obs], {_EURUSD: series})

        expected_ordinal = date(2023, 7, 16).toordinal()
        assert remapped.context_cluster_id[1] == expected_ordinal

    def test_winter_utc2145_is_still_same_helsinki_day(self) -> None:
        """2023-01-15T21:45Z → 2023-01-15T23:45 Helsinki (UTC+2) → same day."""
        from datetime import date

        series = _series(_EURUSD, _WINTER_DAY1_LAST_CANDLE)
        obs = _never_filled_obs(_EURUSD, retest_index=0)

        (remapped,) = remap_to_instrument_day_clusters([obs], {_EURUSD: series})

        expected_ordinal = date(2023, 1, 15).toordinal()
        assert remapped.context_cluster_id[1] == expected_ordinal

    def test_summer_utc2045_is_still_same_helsinki_day(self) -> None:
        """2023-07-15T20:45Z → 2023-07-15T23:45 Helsinki (UTC+3) → same day."""
        from datetime import date

        series = _series(_EURUSD, _SUMMER_DAY1_LAST_CANDLE)
        obs = _never_filled_obs(_EURUSD, retest_index=0)

        (remapped,) = remap_to_instrument_day_clusters([obs], {_EURUSD: series})

        expected_ordinal = date(2023, 7, 15).toordinal()
        assert remapped.context_cluster_id[1] == expected_ordinal

    def test_dst_offset_difference_produces_different_midnight_boundaries(self) -> None:
        """Same naive-UTC hour-of-day crosses Helsinki midnight in one season
        but not the other — the two candles must map to different relative dates."""
        from datetime import date

        # 21:45Z is last candle of the Helsinki day in summer (UTC+3),
        # but still 23:45 (NOT midnight) in winter (UTC+2).
        # 22:00Z is midnight-of-next-day in winter, but 01:00 next-day in summer.
        # Build one series mixing a winter and summer "same UTC time" scenario
        # by verifying the ordinals directly rather than comparing against each
        # other (different years would be noise).

        summer_before = _SUMMER_DAY1_LAST_CANDLE   # 20:45Z → Helsinki 23:45 Jul 15
        summer_after = _SUMMER_DAY2_FIRST_CANDLE    # 21:00Z → Helsinki 00:00 Jul 16

        winter_before = _WINTER_DAY1_LAST_CANDLE    # 21:45Z → Helsinki 23:45 Jan 15
        winter_after = _WINTER_DAY2_FIRST_CANDLE    # 22:00Z → Helsinki 00:00 Jan 16

        for before_ts, after_ts, before_date, after_date in [
            (summer_before, summer_after, date(2023, 7, 15), date(2023, 7, 16)),
            (winter_before, winter_after, date(2023, 1, 15), date(2023, 1, 16)),
        ]:
            series = _series(_EURUSD, before_ts, after_ts)
            obs_before = _never_filled_obs(_EURUSD, retest_index=0, signal_id="sig_before")
            obs_after = _never_filled_obs(_EURUSD, retest_index=1, signal_id="sig_after")

            result = remap_to_instrument_day_clusters(
                [obs_before, obs_after], {_EURUSD: series}
            )

            assert result[0].context_cluster_id[1] == before_date.toordinal()
            assert result[1].context_cluster_id[1] == after_date.toordinal()

    def test_spring_dst_transition_date_is_correct(self) -> None:
        """2023-03-26: clocks spring forward at 03:00 EET (01:00 UTC) → 04:00 EEST.
        A candle at 00:45Z falls under EET (UTC+2), giving Helsinki 02:45, still Mar 26."""
        from datetime import date

        spring_forward_pre = datetime(2023, 3, 26, 0, 45)  # 00:45Z → 02:45 Helsinki EET
        series = _series(_EURUSD, spring_forward_pre)
        obs = _never_filled_obs(_EURUSD, retest_index=0)

        (remapped,) = remap_to_instrument_day_clusters([obs], {_EURUSD: series})

        assert remapped.context_cluster_id[1] == date(2023, 3, 26).toordinal()

    def test_autumn_dst_transition_date_is_correct(self) -> None:
        """2023-10-29: clocks fall back at 04:00 EEST (01:00 UTC) → 03:00 EET.
        A candle at 21:45Z falls under EET (UTC+2) after fallback, giving Helsinki 23:45 Oct 29."""
        from datetime import date

        autumn_fallback = datetime(2023, 10, 29, 21, 45)  # 21:45Z → 23:45 Helsinki EET (+2)
        series = _series(_EURUSD, autumn_fallback)
        obs = _never_filled_obs(_EURUSD, retest_index=0)

        (remapped,) = remap_to_instrument_day_clusters([obs], {_EURUSD: series})

        assert remapped.context_cluster_id[1] == date(2023, 10, 29).toordinal()


# ---------------------------------------------------------------------------
# Invalid inputs — fail-closed
# ---------------------------------------------------------------------------

class TestInvalidInputs:
    def test_unknown_instrument_raises(self) -> None:
        series = _series(_EURUSD, _MON_09_00_UTC)
        obs = _never_filled_obs("UNKNOWN_PAIR", retest_index=0)

        with pytest.raises(ClusterRemapError, match="UNKNOWN_PAIR"):
            remap_to_instrument_day_clusters([obs], {_EURUSD: series})

    def test_retest_index_out_of_range_raises(self) -> None:
        series = _series(_EURUSD, _MON_09_00_UTC)  # only 1 candle → valid index: 0
        obs = _never_filled_obs(_EURUSD, retest_index=5)

        with pytest.raises(ClusterRemapError, match="retest_index 5 out of range"):
            remap_to_instrument_day_clusters([obs], {_EURUSD: series})

    def test_negative_retest_index_raises(self) -> None:
        series = _series(_EURUSD, _MON_09_00_UTC)
        obs = _never_filled_obs(_EURUSD, retest_index=-1)

        with pytest.raises(ClusterRemapError, match="retest_index -1 out of range"):
            remap_to_instrument_day_clusters([obs], {_EURUSD: series})

    def test_non_m15_series_raises(self) -> None:
        h4_series = OHLCSeries(
            candles=(_candle(_MON_09_00_UTC),),
            instrument=_EURUSD,
            timeframe="H4",
        )

        with pytest.raises(ClusterRemapError, match="H4"):
            remap_to_instrument_day_clusters(
                [_never_filled_obs(_EURUSD, retest_index=0)],
                {_EURUSD: h4_series},
            )

    def test_aware_candle_timestamp_raises(self) -> None:
        aware_ts = datetime(2023, 3, 6, 9, 0, tzinfo=timezone.utc)
        aware_series = OHLCSeries(
            candles=(Candle(
                timestamp=aware_ts,
                open=_FLAT_PRICE, high=_FLAT_PRICE,
                low=_FLAT_PRICE, close=_FLAT_PRICE,
            ),),
            instrument=_EURUSD,
            timeframe="15M",
        )

        with pytest.raises(ClusterRemapError, match="not naive"):
            remap_to_instrument_day_clusters(
                [_never_filled_obs(_EURUSD, retest_index=0)],
                {_EURUSD: aware_series},
            )

    def test_error_message_includes_available_instruments(self) -> None:
        series_g = _series(_GBPUSD, _MON_09_00_UTC)
        obs = _never_filled_obs(_EURUSD, retest_index=0)

        with pytest.raises(ClusterRemapError, match=_GBPUSD):
            remap_to_instrument_day_clusters([obs], {_GBPUSD: series_g})

    def test_series_validation_fires_before_observation_loop(self) -> None:
        """Non-M15 series must be rejected even when observations list is empty."""
        bad_series = OHLCSeries(
            candles=(_candle(_MON_09_00_UTC),),
            instrument=_EURUSD,
            timeframe="D1",
        )

        with pytest.raises(ClusterRemapError, match="D1"):
            remap_to_instrument_day_clusters([], {_EURUSD: bad_series})


def test_statistics_wrapper_remaps_before_delegating(monkeypatch: pytest.MonkeyPatch) -> None:
    from research.dukascopy_eurusd_gbpusd import cluster

    series = _series(_EURUSD, _MON_09_00_UTC)
    obs = _never_filled_obs(_EURUSD, retest_index=0)
    captured: dict[str, object] = {}

    def fake_run_statistics(remapped, instruments):
        captured["observations"] = remapped
        captured["instruments"] = instruments
        return "sentinel"

    monkeypatch.setattr(
        "research.dukascopy_eurusd_gbpusd.seam.run_statistics",
        fake_run_statistics,
    )

    result = cluster.run_statistics_with_instrument_day_clusters(
        [obs], ("DUKASCOPY_EURUSD", "DUKASCOPY_GBPUSD"), {_EURUSD: series}
    )

    assert result == "sentinel"
    assert captured["observations"][0].context_cluster_id != obs.context_cluster_id
    assert captured["instruments"] == ("DUKASCOPY_EURUSD", "DUKASCOPY_GBPUSD")


def test_statistics_wrapper_rejects_wrong_instrument_order() -> None:
    series = _series(_EURUSD, _MON_09_00_UTC)
    obs = _never_filled_obs(_EURUSD, retest_index=0)

    with pytest.raises(ClusterRemapError, match="exactly"):
        run_statistics_with_instrument_day_clusters(
            [obs], ("DUKASCOPY_GBPUSD", "DUKASCOPY_EURUSD"), {_EURUSD: series}
        )


def test_statistics_wrapper_rejects_single_instrument_tuple() -> None:
    series = _series(_EURUSD, _MON_09_00_UTC)
    obs = _never_filled_obs(_EURUSD, retest_index=0)

    with pytest.raises(ClusterRemapError, match="exactly"):
        run_statistics_with_instrument_day_clusters(
            [obs], (_EURUSD,), {_EURUSD: series}
        )


def test_statistics_wrapper_rejects_unknown_instrument_in_tuple() -> None:
    series = _series(_EURUSD, _MON_09_00_UTC)
    obs = _never_filled_obs(_EURUSD, retest_index=0)

    with pytest.raises(ClusterRemapError, match="exactly"):
        run_statistics_with_instrument_day_clusters(
            [obs],
            ("DUKASCOPY_EURUSD", "DUKASCOPY_UNKNOWN"),
            {_EURUSD: series},
        )


def test_statistics_wrapper_rejects_observation_with_unapproved_instrument() -> None:
    series_e = _series(_EURUSD, _MON_09_00_UTC)
    obs_bad = _never_filled_obs("DUKASCOPY_XAUUSD", retest_index=0)

    with pytest.raises(ClusterRemapError, match="unapproved instrument"):
        run_statistics_with_instrument_day_clusters(
            [obs_bad],
            ("DUKASCOPY_EURUSD", "DUKASCOPY_GBPUSD"),
            {_EURUSD: series_e},
        )
