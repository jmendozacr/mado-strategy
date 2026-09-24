"""Environment verification: uv.lock SHA-256, numpy version, Python version."""

import hashlib
import sys
from pathlib import Path

import numpy as np

from runner.errors import AuthorizationError


def _python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def environment_record(uv_lock_path: str) -> dict[str, str]:
    lock_path = Path(uv_lock_path)
    lock_sha256 = hashlib.sha256(lock_path.read_bytes()).hexdigest() if lock_path.is_file() else ""
    return {
        "python_version": _python_version(),
        "numpy_version": np.__version__,
        "uv_lock_sha256": lock_sha256,
    }


def verify_environment(
    expected_uv_lock_sha256: str,
    expected_numpy_version: str,
    uv_lock_path: str,
) -> dict[str, str]:
    """Abort on any environment mismatch."""
    record = environment_record(uv_lock_path)
    python_ver = record["python_version"]
    if not python_ver.startswith("3.12"):
        raise AuthorizationError(f"Python version must be 3.12.*, got {python_ver}")

    actual_numpy = record["numpy_version"]
    if actual_numpy != expected_numpy_version:
        raise AuthorizationError(
            f"numpy version must be {expected_numpy_version}, got {actual_numpy}"
        )

    lock_path = Path(uv_lock_path)
    if not lock_path.exists():
        raise AuthorizationError(f"uv.lock not found at {uv_lock_path}")
    actual_hash = record["uv_lock_sha256"]
    if actual_hash != expected_uv_lock_sha256:
        raise AuthorizationError(
            f"uv.lock SHA-256 mismatch: expected {expected_uv_lock_sha256}, got {actual_hash}"
        )
    return record
