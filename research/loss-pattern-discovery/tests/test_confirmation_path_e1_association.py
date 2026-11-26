from datetime import datetime
from types import SimpleNamespace

from stats.confirmation_path_e1_association import (
    path_complexity_population,
    standardize_model_gap_by_path_complexity,
    two_group_gap,
    within_model_contrast,
)


def _record(event_id, instrument, session_label, entry_ts):
    return SimpleNamespace(
        identification=SimpleNamespace(event_id=event_id, instrument=instrument, session_label=session_label),
        operation=SimpleNamespace(entry_ts=entry_ts, outcome=SimpleNamespace(name="LOSS")),
    )


def _path(symbol, model, invalidations):
    return {"symbol": symbol, "model": model, "internal_invalidation_count": invalidations}


def test_path_complexity_population_reports_coverage_and_missing_ids_explicitly():
    primary = [
        _record("a", "EURUSD", "1am", datetime(2020, 1, 1)),
        _record("b", "EURUSD", "1am", datetime(2020, 1, 2)),
    ]
    paths = {"a": _path("EURUSD", "1am", 0)}
    covered, coverage, missing = path_complexity_population(primary, paths)
    assert [r.identification.event_id for r in covered] == ["a"]
    assert coverage == 0.5
    assert missing == ["b"]


def test_two_group_gap_computes_rate_difference_and_a_ci():
    group_a = [_record(f"a{i}", "EURUSD", "1am", datetime(2020, 1, i + 1)) for i in range(25)]
    group_b = [_record(f"b{i}", "EURUSD", "1am", datetime(2020, 2, i + 1)) for i in range(25)]
    flags = {r.identification.event_id: (i < 10) for i, r in enumerate(group_a)}
    flags.update({r.identification.event_id: (i < 2) for i, r in enumerate(group_b)})
    result = two_group_gap(group_a, group_b, flags, "zero", "has")
    assert result["n_zero"] == 25
    assert result["n_has"] == 25
    assert abs(result["rate_zero"] - 10 / 25) < 1e-9
    assert abs(result["rate_has"] - 2 / 25) < 1e-9
    assert result["diff"] > 0
    assert result["ci_low"] is not None and result["ci_high"] is not None


def test_within_model_contrast_flags_insufficient_support():
    recs = [_record(f"a{i}", "EURUSD", "1am", datetime(2020, 1, i + 1)) for i in range(5)]
    paths = {r.identification.event_id: _path("EURUSD", "1am", 0) for r in recs}
    flags = {r.identification.event_id: False for r in recs}
    result = within_model_contrast({"1am": recs, "9am": []}, flags, paths)
    assert result["1am"]["sufficient_support"] is False  # only 5 events, all in the same bucket


def test_standardize_model_gap_by_path_complexity_matches_pooled_weights():
    recs_1am = [_record(f"x{i}", "EURUSD", "1am", datetime(2020, 1, i + 1)) for i in range(4)]
    recs_9am = [_record(f"y{i}", "EURUSD", "9am", datetime(2020, 1, i + 1)) for i in range(4)]
    paths = {}
    for i, r in enumerate(recs_1am):
        paths[r.identification.event_id] = _path("EURUSD", "1am", 0 if i % 2 == 0 else 1)
    for i, r in enumerate(recs_9am):
        paths[r.identification.event_id] = _path("EURUSD", "9am", 0 if i % 2 == 0 else 1)
    flags = {r.identification.event_id: False for r in recs_1am + recs_9am}
    result = standardize_model_gap_by_path_complexity({"1am": recs_1am, "9am": recs_9am}, flags, paths)
    assert set(result["pooled_weights"].keys()) == {0, 1}
    assert abs(sum(result["pooled_weights"].values()) - 1.0) < 1e-9
    assert result["standardized_rate_1am"] == 0.0
    assert result["standardized_rate_9am"] == 0.0
