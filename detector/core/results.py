from enum import Enum


class DetectionStatus(str, Enum):
    CONFIRMED = "confirmed"
    INVALIDATED = "invalidated"
    PENDING = "pending"
