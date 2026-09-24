"""Canonical JSON serialization.

sort_keys=True, separators=(",",":"), ensure_ascii=False, allow_nan=False,
trailing newline, UTF-8 encoding. Floats via repr(), enums via .value."""

import hashlib
import json
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any


def _default_serializer(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, float):
        return obj
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def canonical_json(obj: Any) -> bytes:
    """Deterministic, byte-reproducible JSON serialization."""
    text = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=_default_serializer,
    )
    return (text + "\n").encode("utf-8")


def to_json_value(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {field.name: to_json_value(getattr(obj, field.name)) for field in fields(obj)}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, tuple):
        return [to_json_value(value) for value in obj]
    if isinstance(obj, list):
        return [to_json_value(value) for value in obj]
    if isinstance(obj, dict):
        return {str(key): to_json_value(value) for key, value in obj.items()}
    return obj


def manifest_sha256(manifest: Any) -> str:
    return hashlib.sha256(canonical_json(to_json_value(manifest))).hexdigest()
