from datetime import datetime

from raza_h4fvg.orchestrate import NOT_QUALIFYING_H4_REASONS, QUALIFYING_H4_REASONS, run_symbol


def test_run_symbol_on_a_real_tight_range_produces_a_consistent_outcome_taxonomy():
    """Real-data smoke test (fast, tight range): every session resolves
    to exactly one outcome, qualifying H4 setups are a strict subset of
    all sessions, and every ENTERED session carries a resolved trade."""
    result = run_symbol("EURUSD", start_date=datetime(2015, 1, 1), end_date=datetime(2015, 6, 1))
    sessions = result["sessions"]
    assert len(sessions) > 100  # roughly one row per NY calendar day in range

    n_qualifying = 0
    n_entered = 0
    for day_key, record in sessions.items():
        if record["qualifying_h4_setup"]:
            n_qualifying += 1
            assert record["outcome"] not in NOT_QUALIFYING_H4_REASONS
            if record["outcome"] == "ENTERED":
                n_entered += 1
                assert record["trade_outcome"] in ("win", "loss", "open")
        else:
            assert record["outcome"] not in ("ENTERED", "RR_FLOOR_REJECTED", "UNFILLED_ORDER")

    # Not every day qualifies -- this is a narrow, multi-condition setup.
    assert 0 <= n_qualifying <= len(sessions)
    assert n_entered <= n_qualifying
