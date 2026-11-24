"""End-to-end smoke test joining a real SL event against real M15 data.

Skipped automatically when the historical data/ directory isn't available on
this machine (it is gitignored and lives outside this worktree) -- the unit
tests in test_post_stop_trajectory.py already cover the logic with synthetic
bars and do not depend on this.
"""
from pathlib import Path

import pytest

import config
from extract.from_causal_lookahead_audit import extract
from extract.post_stop_trajectory import compute_post_stop_outcomes, load_m15_series
from schema.events import Outcome

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _data_dir_or_skip() -> Path:
    try:
        return config.resolve_data_dir()
    except FileNotFoundError:
        pytest.skip("historical data/ directory not available on this machine")


def test_real_sl_event_trajectory_is_measurable():
    data_dir = _data_dir_or_skip()
    records = extract(REPO_ROOT)
    loss_records = [r for r in records if r.operation.outcome is Outcome.LOSS]
    sample = loss_records[0]

    series = load_m15_series(sample.identification.instrument, data_dir)
    assert len(series.candles) > 100_000  # sanity: this is the full M15 history, not a stub

    outcomes = compute_post_stop_outcomes(sample, series)
    assert [o.horizon_label for o in outcomes] == ["4h", "1d", "3d"]
    for outcome in outcomes:
        assert outcome.bars_available > 0
        assert outcome.censored is False  # 2015 event, plenty of M15 history after it
        assert outcome.mfe_price is not None
        assert outcome.mae_price is not None
        assert outcome.mfe_price >= 0.0
        assert outcome.mae_price >= 0.0
    # MFE/MAE must accumulate monotonically across increasing horizons.
    assert outcomes[0].mfe_price <= outcomes[1].mfe_price <= outcomes[2].mfe_price
    assert outcomes[0].mae_price <= outcomes[1].mae_price <= outcomes[2].mae_price
