"""Environment checks and config fingerprint."""

import sys
from unittest.mock import patch

import pytest


def test_numpy_version_mismatch_aborts():
    from runner.environment import verify_environment

    with pytest.raises(Exception, match="numpy"):
        verify_environment(
            expected_uv_lock_sha256="abc123",
            expected_numpy_version="9.9.9",
            uv_lock_path="/nonexistent",
        )


def test_python_version_mismatch_aborts():
    from runner.environment import verify_environment

    with patch("runner.environment._python_version", return_value="2.7.18"):
        with pytest.raises(Exception, match="Python"):
            verify_environment(
                expected_uv_lock_sha256="abc123",
                expected_numpy_version="2.5.2",
                uv_lock_path="/nonexistent",
            )


def test_uv_lock_hash_mismatch_aborts(tmp_path):
    import numpy as np

    from runner.environment import verify_environment

    lock_file = tmp_path / "uv.lock"
    lock_file.write_text("some content")

    with pytest.raises(Exception, match="uv.lock"):
        verify_environment(
            expected_uv_lock_sha256="0000000000000000000000000000000000000000000000000000000000000000",
            expected_numpy_version=np.__version__,
            uv_lock_path=str(lock_file),
        )


def test_config_reconstruction_equality():
    from runner.config_fingerprint import reconstruct_and_fingerprint

    from core.config import DetectorConfig

    config_dict = {
        "swing": {},
        "fvg": {"min_size_atr": 0.1},
        "crt_range": {"max_lookback": 20},
        "mss": {"decisive_close_ratio": 0.25},
        "ict_order_block": {},
        "model1": {"body_ratio_tiebreak": 0.6, "respect_rule_tolerance": 0, "max_retest_lookback": 20},
        "kill_zone": {"ny_start_hour": 7, "ny_end_hour": 11},
        "backtest": {
            "sl_buffer_atr_multiple": 0.3,
            "min_risk_reward": 2.0,
            "trading_cost_price": 0.0,
            "kill_zone_gated": True,
            "max_fill_wait": 20,
            "partial_fraction": 0.5,
        },
    }
    config, fingerprint = reconstruct_and_fingerprint(config_dict)
    assert config == DetectorConfig()
    assert len(fingerprint) == 64


def test_config_drift_detected():
    from core.config import DetectorConfig
    from runner.config_fingerprint import reconstruct_and_fingerprint

    config_dict = {
        "swing": {},
        "fvg": {"min_size_atr": 0.999},
        "crt_range": {"max_lookback": 20},
        "mss": {"decisive_close_ratio": 0.25},
        "ict_order_block": {},
        "model1": {"body_ratio_tiebreak": 0.6, "respect_rule_tolerance": 0, "max_retest_lookback": 20},
        "kill_zone": {"ny_start_hour": 7, "ny_end_hour": 11},
        "backtest": {
            "sl_buffer_atr_multiple": 0.3,
            "min_risk_reward": 2.0,
            "trading_cost_price": 0.0,
            "kill_zone_gated": True,
            "max_fill_wait": 20,
            "partial_fraction": 0.5,
        },
    }
    config, _ = reconstruct_and_fingerprint(config_dict)
    assert config != DetectorConfig()


def test_config_fingerprint_deterministic():
    from runner.config_fingerprint import reconstruct_and_fingerprint

    config_dict = {
        "swing": {},
        "fvg": {"min_size_atr": 0.1},
        "crt_range": {"max_lookback": 20},
        "mss": {"decisive_close_ratio": 0.25},
        "ict_order_block": {},
        "model1": {"body_ratio_tiebreak": 0.6, "respect_rule_tolerance": 0, "max_retest_lookback": 20},
        "kill_zone": {"ny_start_hour": 7, "ny_end_hour": 11},
        "backtest": {
            "sl_buffer_atr_multiple": 0.3,
            "min_risk_reward": 2.0,
            "trading_cost_price": 0.0,
            "kill_zone_gated": True,
            "max_fill_wait": 20,
            "partial_fraction": 0.5,
        },
    }
    _, fp1 = reconstruct_and_fingerprint(config_dict)
    _, fp2 = reconstruct_and_fingerprint(config_dict)
    assert fp1 == fp2


def test_config_fingerprint_is_sensitive_to_min_stop_distance_price():
    """REQ-NEW (odd/tasks/realistic-cost-prop-firm-validation.md T8): two
    configs differing ONLY in the new min_stop_distance_price must get
    DIFFERENT fingerprints -- it is an economically-relevant backtest
    parameter, and a fingerprint that ignored it would let two materially
    different runs collide under one identity."""
    from runner.config_fingerprint import reconstruct_and_fingerprint

    base_backtest = {
        "sl_buffer_atr_multiple": 0.3,
        "min_risk_reward": 2.0,
        "trading_cost_price": 0.0,
        "kill_zone_gated": True,
        "max_fill_wait": 20,
        "partial_fraction": 0.5,
    }
    shared = {
        "swing": {}, "fvg": {"min_size_atr": 0.1}, "crt_range": {"max_lookback": 20},
        "mss": {"decisive_close_ratio": 0.25}, "ict_order_block": {},
        "model1": {"body_ratio_tiebreak": 0.6, "respect_rule_tolerance": 0, "max_retest_lookback": 20},
        "kill_zone": {"ny_start_hour": 7, "ny_end_hour": 11},
    }
    _, fp_default = reconstruct_and_fingerprint({**shared, "backtest": {**base_backtest, "min_stop_distance_price": 0.0006}})
    _, fp_disabled = reconstruct_and_fingerprint({**shared, "backtest": {**base_backtest, "min_stop_distance_price": 0.0}})
    assert fp_default != fp_disabled
