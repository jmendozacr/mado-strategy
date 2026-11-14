"""DetectorConfig reconstruction and fingerprint.

Reconstruct DetectorConfig from protocol JSON's population.config dict,
compute SHA-256 fingerprint of its canonical serialization."""

import hashlib
import json

from core.config import (
    BacktestConfig,
    CRTRangeConfig,
    DetectorConfig,
    FVGConfig,
    ICTOrderBlockConfig,
    KillZoneConfig,
    Model1Config,
    MSSConfig,
    SwingConfig,
)


def reconstruct_and_fingerprint(config_dict: dict) -> tuple[DetectorConfig, str]:
    """Reconstruct a DetectorConfig from a protocol JSON dict and compute
    its SHA-256 fingerprint. Returns (config, fingerprint_hex)."""
    config = DetectorConfig(
        swing=SwingConfig(**config_dict.get("swing", {})),
        fvg=FVGConfig(**config_dict.get("fvg", {})),
        crt_range=CRTRangeConfig(**config_dict.get("crt_range", {})),
        mss=MSSConfig(**config_dict.get("mss", {})),
        ict_order_block=ICTOrderBlockConfig(**config_dict.get("ict_order_block", {})),
        model1=Model1Config(**config_dict.get("model1", {})),
        kill_zone=KillZoneConfig(**config_dict.get("kill_zone", {})),
        backtest=BacktestConfig(**config_dict.get("backtest", {})),
    )

    canonical = json.dumps(
        {
            "swing": {},
            "fvg": {"min_size_atr": repr(config.fvg.min_size_atr)},
            "crt_range": {"max_lookback": config.crt_range.max_lookback},
            "mss": {"decisive_close_ratio": repr(config.mss.decisive_close_ratio)},
            "ict_order_block": {},
            "model1": {
                "body_ratio_tiebreak": repr(config.model1.body_ratio_tiebreak),
                "respect_rule_tolerance": repr(config.model1.respect_rule_tolerance),
                "max_retest_lookback": config.model1.max_retest_lookback,
            },
            "kill_zone": {
                "ny_start_hour": config.kill_zone.ny_start_hour,
                "ny_end_hour": config.kill_zone.ny_end_hour,
            },
            "backtest": {
                "sl_buffer_atr_multiple": repr(config.backtest.sl_buffer_atr_multiple),
                "min_stop_distance_price": repr(config.backtest.min_stop_distance_price),
                "min_risk_reward": repr(config.backtest.min_risk_reward),
                "trading_cost_price": repr(config.backtest.trading_cost_price),
                "kill_zone_gated": config.backtest.kill_zone_gated,
                "max_fill_wait": config.backtest.max_fill_wait,
                "partial_fraction": repr(config.backtest.partial_fraction),
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return config, fingerprint
