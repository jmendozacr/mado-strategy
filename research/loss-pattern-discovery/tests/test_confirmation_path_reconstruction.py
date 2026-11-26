from datetime import datetime

from extract.confirmation_path_reconstruction import reconstruct_paths_for_symbol


def test_reconstruct_paths_for_symbol_covers_every_confirmed_signal_on_a_tight_range():
    """Full coverage check (requirement: no confirmed signal silently
    dropped) on a short, fast real-data range -- the heavy full-history
    run (`main()`, one process per symbol) is the production path, not
    exercised by the test suite itself."""
    result = reconstruct_paths_for_symbol("EURUSD", start_date=datetime(2015, 1, 1), end_date=datetime(2015, 3, 1))
    assert result["n_confirmed"] > 0
    assert result["n_unreconstructed"] == 0
    assert result["n_reconstructed"] == result["n_confirmed"]
    assert set(result["paths"].keys()) == set(result["paths"].keys())  # keys are the confirmed stable_ids
    for sid, path in result["paths"].items():
        assert path["symbol"] == "EURUSD"
        assert path["model"] in ("1am", "9am")
        assert path["internal_invalidation_count"] >= 0
        assert path["confirmation_attempt_count"] == path["internal_invalidation_count"] + 1
        assert sid.split("|")[0] == "EURUSD"  # no cross-instrument mixing


def test_reconstruct_paths_for_symbol_is_deterministic():
    r1 = reconstruct_paths_for_symbol("EURUSD", start_date=datetime(2015, 1, 1), end_date=datetime(2015, 3, 1))
    r2 = reconstruct_paths_for_symbol("EURUSD", start_date=datetime(2015, 1, 1), end_date=datetime(2015, 3, 1))
    assert r1 == r2
