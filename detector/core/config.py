from dataclasses import dataclass, field


@dataclass(frozen=True)
class SwingConfig:
    pass


@dataclass(frozen=True)
class FVGConfig:
    min_size_atr: float = 0.1


@dataclass(frozen=True)
class MSNRConfig:
    # A-shape/V-shape levels are a single close PRICE, not a wick-to-wick
    # zone -- a real wick would (almost) never land on an exact price, so
    # KeyLevel needs a nonzero width. ATR-relative, never a raw price
    # constant (REQ-31 precedent, BacktestConfig.sl_buffer_atr_multiple).
    # 0.1 is a first-pass value, not yet tuned against real data.
    zone_atr_multiple: float = 0.1


@dataclass(frozen=True)
class CRTRangeConfig:
    max_lookback: int = 20


@dataclass(frozen=True)
class MSSConfig:
    decisive_close_ratio: float = 0.25


@dataclass(frozen=True)
class OrderFlowConfig:
    pass  # rejection/break are hard geometric tests (wick-cross + close-back / close-beyond) — no discretionary threshold is justified at v1 (spec REQ-OF-01/02/03)


@dataclass(frozen=True)
class ICTOrderBlockConfig:
    pass  # base rule is fully structural — engulfment and touch-invalidation are hard geometric tests, no discretionary threshold


@dataclass(frozen=True)
class Model1Config:
    body_ratio_tiebreak: float = 0.6
    respect_rule_tolerance: float = 0
    max_retest_lookback: int = 20


@dataclass(frozen=True)
class KillZoneConfig:
    """charter-3 [00:07:52]: New York Kill Zone, 7:00-10:00/11:00am
    NY-local. Upper bound is ambiguous in the source ("10:00/11:00 a.m.")
    — defaults to the wider 11:00 to avoid silently dropping real signals.
    """
    ny_start_hour: int = 7
    ny_end_hour: int = 11


@dataclass(frozen=True)
class BacktestConfig:
    sl_buffer_atr_multiple: float = 0.3  # ATR(14)-relative offset, never a raw price constant (REQ-31) --
    # 0.3 reproduces ~the same absolute buffer as the former 0.0002 on EURUSDm/GBPUSDm-scale M15 series
    # (mean ATR(14) ~0.00067/~0.00088) while scaling correctly for a high-absolute-price instrument like DXYm
    min_stop_distance_price: float = 0.0006  # REQ-NEW: 6-pip EURUSDm floor -- beat every ATR-relative
    # alternative tested on the 1AM/5AM/9AM HTF-first population (odd/tasks/realistic-cost-prop-firm-validation.md
    # T8); operator-tunable per instrument like sl_buffer_atr_multiple, not hardcoded pips
    min_risk_reward: float = 2.0  # REQ-35
    trading_cost_price: float = 0.0  # total per-trade cost, price units (REQ-48)
    kill_zone_gated: bool = True  # REQ-36
    max_fill_wait: int = 20  # candles (REQ-50)
    partial_fraction: float = 0.5  # position-size fraction closing at the equilibrium level (REQ-68/51)
    breakeven_after_partial: bool = False  # EXPERIMENTAL: once the partial leg fires, move leg 2's
    # stop to entry price (breakeven) instead of letting it keep riding the original stop_loss --
    # default False preserves the original REQ-68/69 behavior exactly


@dataclass(frozen=True)
class DetectorConfig:
    swing: SwingConfig = field(default_factory=SwingConfig)
    fvg: FVGConfig = field(default_factory=FVGConfig)
    msnr: MSNRConfig = field(default_factory=MSNRConfig)
    crt_range: CRTRangeConfig = field(default_factory=CRTRangeConfig)
    mss: MSSConfig = field(default_factory=MSSConfig)
    ict_order_block: ICTOrderBlockConfig = field(default_factory=ICTOrderBlockConfig)
    model1: Model1Config = field(default_factory=Model1Config)
    kill_zone: KillZoneConfig = field(default_factory=KillZoneConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
