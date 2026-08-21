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
class KillZoneConfig:
    """charter-3 [00:07:52]: New York Kill Zone, 7:00-10:00/11:00am
    NY-local. Upper bound is ambiguous in the source ("10:00/11:00 a.m.")
    — defaults to the wider 11:00 to avoid silently dropping real signals.
    """
    ny_start_hour: int = 7
    ny_end_hour: int = 11


@dataclass(frozen=True)
class DetectorConfig:
    swing: SwingConfig = field(default_factory=SwingConfig)
    fvg: FVGConfig = field(default_factory=FVGConfig)
    crt_range: CRTRangeConfig = field(default_factory=CRTRangeConfig)
    mss: MSSConfig = field(default_factory=MSSConfig)
    model1: Model1Config = field(default_factory=Model1Config)
    kill_zone: KillZoneConfig = field(default_factory=KillZoneConfig)
