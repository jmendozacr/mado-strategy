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
class DetectorConfig:
    swing: SwingConfig = field(default_factory=SwingConfig)
    fvg: FVGConfig = field(default_factory=FVGConfig)
    crt_range: CRTRangeConfig = field(default_factory=CRTRangeConfig)
