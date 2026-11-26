from stats.confirmation_path_distribution import summarize


def _entry(symbol, model, period, invalidations):
    return {
        "symbol": symbol, "model": model, "period": period,
        "internal_invalidation_count": invalidations,
        "confirmation_attempt_count": invalidations + 1,
    }


def test_summarize_splits_zero_vs_one_or_more_correctly():
    paths = {
        "a": _entry("EURUSD", "1am", "2015-2017", 0),
        "b": _entry("EURUSD", "1am", "2015-2017", 1),
        "c": _entry("USDCAD", "1am", "2018-2020", 2),
        "d": _entry("AUDUSD", "9am", "2015-2017", 0),
    }
    result = summarize(paths)
    model_1am = result["models"]["1am"]
    assert model_1am["n_total"] == 3
    assert model_1am["n_zero_invalidation"] == 1
    assert model_1am["n_one_or_more_invalidation"] == 2
    assert model_1am["share_zero_invalidation"] == 1 / 3
    assert model_1am["internal_invalidation_count_distribution"] == {0: 1, 1: 1, 2: 1}

    model_9am = result["models"]["9am"]
    assert model_9am["n_total"] == 1
    assert model_9am["share_zero_invalidation"] == 1.0


def test_summarize_never_cross_counts_instruments_or_periods():
    paths = {
        "a": _entry("EURUSD", "1am", "2015-2017", 0),
        "b": _entry("USDCAD", "1am", "2018-2020", 1),
    }
    result = summarize(paths)
    by_instrument = result["models"]["1am"]["by_instrument"]
    assert by_instrument["EURUSD"]["n"] == 1
    assert by_instrument["USDCAD"]["n"] == 1
    assert by_instrument["AUDUSD"]["n"] == 0
    by_period = result["models"]["1am"]["by_period"]
    assert by_period["2015-2017"]["n"] == 1
    assert by_period["2018-2020"]["n"] == 1
    assert by_period["2021-2023"]["n"] == 0


def test_summarize_handles_an_empty_model_without_crashing():
    result = summarize({"a": _entry("EURUSD", "1am", "2015-2017", 0)})
    assert result["models"]["9am"]["n_total"] == 0
    assert result["models"]["9am"]["share_zero_invalidation"] is None
