"""Paths this lab depends on.

`data/` is gitignored in the main repo and therefore absent from this
worktree -- `git worktree add` only materializes tracked files. The historical
OHLC CSVs are read directly from wherever they actually live on disk; they
are never copied into this worktree.
"""
from __future__ import annotations

import os
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent
REPO_ROOT = LAB_ROOT.parent.parent  # research/loss-pattern-discovery -> repo root
DETECTOR_ROOT = REPO_ROOT / "detector"

_DEFAULT_DATA_DIR_CANDIDATES = (
    REPO_ROOT / "data",  # in case this is ever run from a worktree that has it
    REPO_ROOT.parent / "mado-strategy" / "data",  # sibling main worktree, same machine
)


def resolve_data_dir() -> Path:
    """Resolve the historical OHLC data/ directory.

    Resolved lazily (never at import time) so importing this module never
    fails on a machine without the raw data present -- schema/extractor tests
    that only need the committed CSV ledgers under audit/ must still pass.
    """
    override = os.environ.get("MADO_DATA_DIR")
    if override:
        path = Path(override)
        if not path.is_dir():
            raise FileNotFoundError(f"MADO_DATA_DIR={override!r} is not a directory")
        return path
    for candidate in _DEFAULT_DATA_DIR_CANDIDATES:
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        "could not locate the historical data/ directory; set the MADO_DATA_DIR "
        "environment variable to its absolute path (it is gitignored and not "
        "copied into this worktree)"
    )
