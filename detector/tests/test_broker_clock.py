from datetime import datetime
import pytest

from core.broker_clock import (
    asia_range_timestamp,
    in_execution_window,
    in_priority_subwindow,
    is_asia_range_h4,
    is_london_crt_h4,
)


# REQ-70
def test_is_london_crt_h4_true():
    assert is_london_crt_h4(datetime(2026, 9, 16, 1, 0)) is True

def test_is_london_crt_h4_minute_irrelevant():
    assert is_london_crt_h4(datetime(2026, 9, 16, 1, 30)) is True

def test_is_london_crt_h4_false():
    assert is_london_crt_h4(datetime(2026, 9, 16, 5, 0)) is False

def test_is_asia_range_h4_true():
    assert is_asia_range_h4(datetime(2026, 9, 15, 21, 0)) is True

def test_is_asia_range_h4_false():
    assert is_asia_range_h4(datetime(2026, 9, 15, 5, 0)) is False

def test_classification_neither():
    assert is_london_crt_h4(datetime(2026, 9, 16, 9, 0)) is False
    assert is_asia_range_h4(datetime(2026, 9, 16, 9, 0)) is False

# REQ-71.1
def test_asia_range_timestamp():
    result = asia_range_timestamp(datetime(2026, 9, 16, 1, 0))
    assert result == datetime(2026, 9, 15, 21, 0)

# REQ-72
def test_in_execution_window_02_00():
    assert in_execution_window(datetime(2026, 9, 16, 2, 0)) is True

def test_in_execution_window_02_15():
    assert in_execution_window(datetime(2026, 9, 16, 2, 15)) is True

def test_in_execution_window_03_45():
    assert in_execution_window(datetime(2026, 9, 16, 3, 45)) is True

def test_in_execution_window_04_00_excluded():
    assert in_execution_window(datetime(2026, 9, 16, 4, 0)) is False

def test_in_execution_window_01_59_excluded():
    assert in_execution_window(datetime(2026, 9, 16, 1, 59)) is False

def test_in_priority_subwindow_03_15():
    assert in_priority_subwindow(datetime(2026, 9, 16, 3, 15)) is True

def test_in_priority_subwindow_03_00():
    assert in_priority_subwindow(datetime(2026, 9, 16, 3, 0)) is True

def test_in_priority_subwindow_02_45_excluded():
    assert in_priority_subwindow(datetime(2026, 9, 16, 2, 45)) is False

def test_in_priority_subwindow_04_00_excluded():
    assert in_priority_subwindow(datetime(2026, 9, 16, 4, 0)) is False

# REQ-75.2 structural — broker_clock must not import kill_zone
def test_broker_clock_does_not_import_kill_zone():
    import core.broker_clock as bc
    import inspect
    src = inspect.getsource(bc)
    assert "kill_zone" not in src
