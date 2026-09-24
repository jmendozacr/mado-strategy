"""Fitness function (ADR-01, §4.7): the .importlinter layers contract must
hold. Extend `.importlinter`'s root_packages/layers as composite, entries,
and alignment are introduced in later slices.
"""

import subprocess
import sys

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _lint_imports_command() -> list[str]:
    return [
        sys.executable,
        "-c",
        "from importlinter.cli import lint_imports_command; lint_imports_command()",
    ]


def test_import_linter_uses_the_current_interpreter_module_path():
    assert _lint_imports_command() == [
        sys.executable,
        "-c",
        "from importlinter.cli import lint_imports_command; lint_imports_command()",
    ]


def test_import_linter_layers_contract_holds():
    result = subprocess.run(
        _lint_imports_command(),
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
