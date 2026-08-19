from dataclasses import dataclass, field


@dataclass(frozen=True)
class SwingConfig:
    pass


@dataclass(frozen=True)
class DetectorConfig:
    swing: SwingConfig = field(default_factory=SwingConfig)
