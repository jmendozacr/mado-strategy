"""Fitness function (ADR-01, §4.7): the .importlinter layers contract must
hold. Extend `.importlinter`'s root_packages/layers as composite, entries,
and alignment are introduced in later slices.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _lint_imports_executable() -> Path:
    script_name = "lint-imports.exe" if sys.platform == "win32" else "lint-imports"
    return Path(sys.executable).parent / script_name


def test_import_linter_layers_contract_holds():
    result = subprocess.run(
        [str(_lint_imports_executable())],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
