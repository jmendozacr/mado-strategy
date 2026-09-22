"""Research-only instrument-day cluster remapping for the Dukascopy
EURUSD+GBPUSD experiment.

Re-encodes context_cluster_id so that observations sharing the same
instrument AND Europe/Helsinki calendar date fall in the same cluster.

Not imported by any production module.
"""
from __future__ import annotations

from datetime import timezone
from typing import Sequence
from zoneinfo import ZoneInfo

from core.candle import OHLCSeries
from selection.model import DirectionPolicyObservation

_HELSINKI = ZoneInfo("Europe/Helsinki")
_M15_TIMEFRAME = "15M"
_APPROVED_INSTRUMENT_ORDER = (
    "DUKASCOPY_EURUSD",
    "DUKASCOPY_GBPUSD",
)


class ClusterRemapError(Exception):
    """Raised when the instrument-day remap cannot proceed fail-closed.

    Covers: unknown instrument, non-M15 series, out-of-range retest_index,
    or candle timestamps that are not naive-UTC.
    """


def remap_to_instrument_day_clusters(
    observations: Sequence[DirectionPolicyObservation],
    series_by_instrument: dict[str, OHLCSeries],
) -> tuple[DirectionPolicyObservation, ...]:
    """Return new observations whose context_cluster_id is the instrument-day.

    For each observation the M15 candle at candidate_id.retest_index is
    located, its naive-UTC timestamp is converted to Europe/Helsinki, and the
    local calendar date is encoded as the cluster id:

        (instrument, date.toordinal(), date.toordinal(), date.toordinal())

    This satisfies the existing tuple[str,int,int,int] bootstrap type while
    grouping observations by the approved statistical unit.

    Every other field of the original observation is preserved exactly; new
    frozen DirectionPolicyObservation objects are constructed.

    Raises ClusterRemapError (fail-closed) for:
    - An observation whose instrument is absent from series_by_instrument.
    - A series whose timeframe is not "15M".
    - A series containing aware (tz-annotated) candle timestamps.
    - A retest_index that is out of range for the supplied series.
    """
    _validate_series(series_by_instrument)

    remapped: list[DirectionPolicyObservation] = []
    for obs in observations:
        instrument = obs.candidate_id.instrument
        if instrument not in series_by_instrument:
            raise ClusterRemapError(
                f"instrument {instrument!r} not found in series_by_instrument;"
                f" available: {sorted(series_by_instrument)}"
            )
        series = series_by_instrument[instrument]
        idx = obs.candidate_id.retest_index
        n = len(series.candles)
        if idx < 0 or idx >= n:
            raise ClusterRemapError(
                f"retest_index {idx} out of range for instrument {instrument!r}"
                f" (series has {n} candle(s))"
            )
        naive_utc = series.candles[idx].timestamp
        helsinki_dt = naive_utc.replace(tzinfo=timezone.utc).astimezone(_HELSINKI)
        local_date = helsinki_dt.date()
        ordinal = local_date.toordinal()
        cluster_id: tuple[str, int, int, int] = (instrument, ordinal, ordinal, ordinal)
        remapped.append(
            DirectionPolicyObservation(
                candidate_id=obs.candidate_id,
                context_cluster_id=cluster_id,
                policy_id=obs.policy_id,
                relation=obs.relation,
                outcome_state=obs.outcome_state,
                closed_outcome=obs.closed_outcome,
                realized_r=obs.realized_r,
            )
        )
    return tuple(remapped)


def _validate_series(series_by_instrument: dict[str, OHLCSeries]) -> None:
    """Pre-flight: validate every series before touching any observation."""
    for instrument, series in series_by_instrument.items():
        if series.timeframe != _M15_TIMEFRAME:
            raise ClusterRemapError(
                f"series for {instrument!r} has timeframe {series.timeframe!r};"
                f" expected {_M15_TIMEFRAME!r}"
            )
        for i, candle in enumerate(series.candles):
            if candle.timestamp.tzinfo is not None:
                raise ClusterRemapError(
                    f"series for {instrument!r}: candle[{i}].timestamp is not"
                    f" naive (tzinfo={candle.timestamp.tzinfo!r});"
                    f" all M15 candles must be naive-UTC"
                )


def run_statistics_with_instrument_day_clusters(
    observations: Sequence[DirectionPolicyObservation],
    instruments: tuple[str, ...],
    series_by_instrument: dict[str, OHLCSeries],
):
    """Remap research observations before invoking the canonical statistics path."""
    if tuple(instruments) != _APPROVED_INSTRUMENT_ORDER:
        raise ClusterRemapError(
            "instruments must be exactly "
            f"{_APPROVED_INSTRUMENT_ORDER!r}, got {tuple(instruments)!r}"
        )
    invalid = sorted({obs.candidate_id.instrument for obs in observations} - set(_APPROVED_INSTRUMENT_ORDER))
    if invalid:
        raise ClusterRemapError(
            f"observations contain unapproved instrument(s): {invalid!r}"
        )

    remapped = remap_to_instrument_day_clusters(observations, series_by_instrument)
    from research.dukascopy_eurusd_gbpusd.seam import run_statistics

    return run_statistics(remapped, _APPROVED_INSTRUMENT_ORDER)
