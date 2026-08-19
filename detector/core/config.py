from dataclasses import dataclass, field


@dataclass(frozen=True)
class SwingConfig:
    pass


@dataclass(frozen=True)
class FVGConfig:
    min_size_atr: float = 0.1


@dataclass(frozen=True)
class CRTRangeConfig:
    max_lookback: int = 20


@dataclass(frozen=True)
class MSSConfig:
    decisive_close_ratio: float = 0.25


@dataclass(frozen=True)
class Model1Config:
    body_ratio_tiebreak: float = 0.6
    respect_rule_tolerance: float = 0
    max_retest_lookback: int = 20


@dataclass(frozen=True)
class DetectorConfig:
    swing: SwingConfig = field(default_factory=SwingConfig)
    fvg: FVGConfig = field(default_factory=FVGConfig)
    crt_range: CRTRangeConfig = field(default_factory=CRTRangeConfig)
    mss: MSSConfig = field(default_factory=MSSConfig)
    model1: Model1Config = field(default_factory=Model1Config)
