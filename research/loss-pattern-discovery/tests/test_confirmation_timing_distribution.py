from stats.confirmation_timing_distribution import BIN_WIDTH_MINUTES, summarize_model
from stats.temporal_feature_dataset import TemporalFeatureRow


def _row(event_id, elapsed, remaining, relative, order_to_fill=5.0, instrument="EURUSD", period="2024-2026"):
    return TemporalFeatureRow(
        event_id=event_id, origin_model="1am", instrument=instrument, direction="bullish",
        period_bucket=period, outcome="loss",
        confirmation_elapsed_minutes=elapsed, confirmation_remaining_minutes=remaining,
        confirmation_relative_position=relative, confirmation_bar_position=elapsed / 15.0 if elapsed else None,
        window_duration_minutes=120.0, order_to_fill_minutes=order_to_fill,
        risk_atr=1.2, atr_m15_at_entry=0.0008, risk_price=0.001, planned_rr=2.5,
        missing_reasons=(),
    )


def test_summarize_model_reports_medians_and_quantiles():
    rows = [_row("a", 10.0, 110.0, 10 / 120), _row("b", 50.0, 70.0, 50 / 120), _row("c", 90.0, 30.0, 90 / 120)]
    summary = summarize_model(rows)
    assert summary["n"] == 3
    assert summary["confirmation_elapsed_minutes"]["median"] == 50.0
    assert summary["confirmation_remaining_minutes"]["median"] == 70.0


def test_histogram_uses_fixed_pre_declared_bin_width_not_tuned():
    rows = [_row("a", 5.0, 115.0, 5 / 120), _row("b", 35.0, 85.0, 35 / 120), _row("c", 65.0, 55.0, 65 / 120)]
    summary = summarize_model(rows)
    histogram = summary["elapsed_minutes_histogram_30min_bins"]
    assert BIN_WIDTH_MINUTES == 30.0
    # bin 0 = [0,30): "a"; bin 1 = [30,60): "b"; bin 2 = [60,90): "c"
    assert histogram == {0: 1, 1: 1, 2: 1}


def test_summarize_model_skips_none_values_without_crashing():
    rows = [_row("a", None, None, None), _row("b", 20.0, 100.0, 20 / 120)]
    summary = summarize_model(rows)
    assert summary["confirmation_elapsed_minutes"]["n"] == 1
    assert summary["confirmation_elapsed_minutes"]["median"] == 20.0


def test_summarize_model_is_deterministic():
    rows = [_row("a", 10.0, 110.0, 10 / 120)]
    assert summarize_model(rows) == summarize_model(rows)
