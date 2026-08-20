"""Fitness function (ADR-02, §4.7, REQ-25.1): config-completeness — no bare
numeric literal (excluding index/loop counters) outside `core/config.py`.

Scope: every production module that imports `core.config` — the modules
positioned to make the config-vs-hardcode choice for an ICT-qualitative
threshold (REQ-25's domain). Modules that never read `DetectorConfig`
(`viz/`, `ingestion/`) are out of REQ-25's concern by construction and are
not scanned, avoiding an unrelated allowlist for rendering geometry and
CSV/timeframe parsing constants.

A bare literal is "allowed" only if it is (a) a small index/loop-counter or
structural zero-guard value, or (b) the right-hand side of a module-level
named-constant assignment (`_UPPER_CASE = ...`, the codebase's existing
convention for non-discretionary constants like `_ATR_PERIOD`/`_DPI`).
Anything else is a threshold that should have been sourced from
`DetectorConfig` instead.
"""

import ast
from pathlib import Path

DETECTOR_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = DETECTOR_ROOT / "core" / "config.py"

# Candle-offset / window-bound / zero-guard values used throughout the
# detector algorithms (e.g. `high[i - 1]`, `range(i + 1, ...)`,
# `if candle_range <= 0`) — never a discretionary ICT threshold in this
# codebase; every real threshold (0.1, 0.25, 0.6, 20) lives in config.py.
_ALLOWED_BARE_VALUES = {-3, -2, -1, 0, 0.0, 1, 2, 3}


def _imports_core_config(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "core.config":
            return True
    return False


def _config_consuming_files() -> list[Path]:
    files = []
    for path in sorted(DETECTOR_ROOT.rglob("*.py")):
        if path == CONFIG_FILE or path.name == "__init__.py":
            continue
        if "tests" in path.relative_to(DETECTOR_ROOT).parts:
            continue
        if ".venv" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if _imports_core_config(tree):
            files.append(path)
    return files


class _BareLiteralVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.found: list[tuple[int, object]] = []
        self._suppressed: set[int] = set()

    def visit_Assign(self, node: ast.Assign) -> None:
        is_named_constant = (
            len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id.lstrip("_").isupper()
        )
        if is_named_constant:
            self._suppressed.update(id(child) for child in ast.walk(node.value))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        is_named_constant = isinstance(node.target, ast.Name) and node.target.id.lstrip("_").isupper()
        if is_named_constant and node.value is not None:
            self._suppressed.update(id(child) for child in ast.walk(node.value))
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if id(node) in self._suppressed:
            return
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            return
        if node.value in _ALLOWED_BARE_VALUES:
            return
        self.found.append((node.lineno, node.value))


def test_config_consuming_modules_have_no_bare_numeric_literals():
    violations = []
    for path in _config_consuming_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = _BareLiteralVisitor()
        visitor.visit(tree)
        for lineno, value in visitor.found:
            violations.append(f"{path.relative_to(DETECTOR_ROOT)}:{lineno}: {value!r}")

    assert not violations, (
        "Bare numeric literal(s) found outside core/config.py in a module "
        "that reads DetectorConfig — should be sourced from config instead "
        "(REQ-25.1):\n" + "\n".join(violations)
    )
