from raza_stats.thirteen_oclock_report import (
    decomposition,
    funnel_by_arm,
    primary_metric,
    sweep_and_close_breakdown,
)


def _row(symbol, close_position, sweep_side, ny_date, b_outcome, b_r, v_outcome, v_r,
         b_candidate=True, b_filled=True, v_candidate=True, v_filled=True):
    return {
        "symbol": symbol, "direction": "bullish", "close_position": close_position,
        "sweep_side": sweep_side, "ny_date": ny_date,
        "baseline": {"is_candidate": b_candidate, "is_filled": b_filled, "outcome": b_outcome, "r_multiple": b_r},
        "variant": {"is_candidate": v_candidate, "is_filled": v_filled, "outcome": v_outcome, "r_multiple": v_r},
    }


def test_funnel_by_arm_counts_each_stage_independently():
    rows = {
        "a": _row("EURUSD", "INSIDE", "LOW_ONLY", "2020-01-01", "win", 1.5, "win", 1.5),
        "b": _row("EURUSD", "OUTSIDE", "HIGH_ONLY", "2020-01-02", "loss", -1.0, None, None,
                   v_candidate=False, v_filled=False),
    }
    funnel = funnel_by_arm(rows)
    assert funnel["baseline"]["confirmed"] == 2
    assert funnel["baseline"]["closed"] == 2
    assert funnel["variant"]["candidate"] == 1
    assert funnel["variant"]["closed"] == 1


def test_decomposition_classifies_loss_avoided_and_gain_forgone_and_unaffected():
    rows = {
        "unaffected": _row("EURUSD", "INSIDE", "LOW_ONLY", "2020-01-01", "win", 1.5, "win", 1.5),
        "loss_avoided": _row("EURUSD", "OUTSIDE", "HIGH_ONLY", "2020-01-02", "loss", -1.2, None, None,
                              v_candidate=False, v_filled=False),
        "gain_forgone": _row("EURUSD", "OUTSIDE", "LOW_ONLY", "2020-01-03", "win", 2.0, None, None,
                              v_candidate=False, v_filled=False),
        "both_zero": _row("EURUSD", "OUTSIDE", "HIGH_ONLY", "2020-01-04", None, None, None, None,
                           b_candidate=False, b_filled=False, v_candidate=False, v_filled=False),
    }
    result = decomposition(rows)
    assert result["UNAFFECTED"] == 1
    assert result["LOSS_AVOIDED"] == 1
    assert result["GAIN_FORGONE"] == 1
    assert result["BOTH_ZERO"] == 1


def test_primary_metric_excludes_open_trades_as_censored():
    rows = {
        "closed": _row("EURUSD", "INSIDE", "LOW_ONLY", "2020-01-01", "win", 2.0, "win", 2.0),
        "open_baseline": _row("EURUSD", "OUTSIDE", "HIGH_ONLY", "2020-01-02", "open", None, None, None,
                               v_candidate=False, v_filled=False),
    }
    result = primary_metric(rows)
    assert result["n"] == 1  # the open-censored row is excluded
    assert result["n_censored_baseline"] == 1
    assert result["mean_r_baseline"] == 2.0
    assert result["mean_r_variant"] == 2.0


def test_sweep_and_close_breakdown_separates_double_from_single_sided_inside():
    rows = {
        "a": _row("EURUSD", "INSIDE", "LOW_ONLY", "2020-01-01", "win", 1.0, "win", 1.0),
        "b": _row("EURUSD", "INSIDE", "BOTH", "2020-01-02", "win", 1.0, "win", 1.0),
    }
    result = sweep_and_close_breakdown(rows)
    assert result["inside_single_sided"] == 1
    assert result["inside_double_sweep"] == 1
