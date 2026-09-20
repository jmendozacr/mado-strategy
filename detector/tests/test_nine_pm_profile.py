"""Tests for core.nine_pm_profile — REQ-76 and REQ-80."""

import pytest

from core.nine_pm_profile import NinePmMetrics, measure_nine_pm


# --- REQ-76.1: bullish body, extends prior high ---

def test_bullish_extends_prior_high():
    """open=1.10, high=1.12, low=1.09, close=1.115; prior high=1.11, prior low=1.08."""
    m = measure_nine_pm(
        nine_pm_open=1.10,
        nine_pm_high=1.12,
        nine_pm_low=1.09,
        nine_pm_close=1.115,
        prior_high=1.11,
        prior_low=1.08,
        prior_h4_index=3,
    )
    assert m.body_direction == "bullish"
    assert m.extends_prior_high is True
    assert m.extends_prior_low is False
    assert m.is_inside_bar is False
    assert m.prior_h4_index == 3
    # body = abs(1.115 - 1.10) = 0.015; range = 1.12 - 1.09 = 0.03; ratio = 0.5
    assert m.body_ratio == pytest.approx(0.5)


# --- REQ-76.2: inside bar ---

def test_inside_bar():
    """9PM range entirely within prior range."""
    m = measure_nine_pm(
        nine_pm_open=1.105,
        nine_pm_high=1.109,
        nine_pm_low=1.102,
        nine_pm_close=1.104,
        prior_high=1.12,
        prior_low=1.10,
        prior_h4_index=4,
    )
    assert m.is_inside_bar is True
    assert m.extends_prior_high is False
    assert m.extends_prior_low is False


# --- REQ-76.3: doji ---

def test_doji_body_direction():
    """open == close -> doji."""
    m = measure_nine_pm(
        nine_pm_open=1.1050,
        nine_pm_high=1.1080,
        nine_pm_low=1.1020,
        nine_pm_close=1.1050,
        prior_high=1.115,
        prior_low=1.095,
        prior_h4_index=2,
    )
    assert m.body_direction == "doji"


# --- REQ-76.4: zero-range candle -> body_ratio None, no exception ---

def test_zero_range_body_ratio_none():
    """high == low -> body_ratio is None; no ZeroDivisionError."""
    m = measure_nine_pm(
        nine_pm_open=1.10,
        nine_pm_high=1.10,
        nine_pm_low=1.10,
        nine_pm_close=1.10,
        prior_high=1.11,
        prior_low=1.09,
        prior_h4_index=1,
    )
    assert m.body_ratio is None


# --- REQ-76.5: extends both prior high and prior low ---

def test_extends_both():
    """9PM range exceeds prior on both sides."""
    m = measure_nine_pm(
        nine_pm_open=1.10,
        nine_pm_high=1.115,
        nine_pm_low=1.085,
        nine_pm_close=1.095,
        prior_high=1.11,
        prior_low=1.09,
        prior_h4_index=5,
    )
    assert m.extends_prior_high is True
    assert m.extends_prior_low is True
    assert m.is_inside_bar is False


# --- REQ-76 body_ratio arithmetic ---

def test_body_ratio_arithmetic():
    """body = abs(1.108 - 1.100) = 0.008; range = 1.112 - 1.096 = 0.016; ratio = 0.5."""
    m = measure_nine_pm(
        nine_pm_open=1.100,
        nine_pm_high=1.112,
        nine_pm_low=1.096,
        nine_pm_close=1.108,
        prior_high=1.115,
        prior_low=1.090,
        prior_h4_index=0,
    )
    assert m.body_ratio == pytest.approx(0.5)


# --- REQ-76 bearish body direction ---

def test_bearish_body_direction():
    """close < open -> bearish."""
    m = measure_nine_pm(
        nine_pm_open=1.110,
        nine_pm_high=1.112,
        nine_pm_low=1.096,
        nine_pm_close=1.098,
        prior_high=1.115,
        prior_low=1.090,
        prior_h4_index=0,
    )
    assert m.body_direction == "bearish"


# --- REQ-80.1: result is a frozen dataclass (no side effects, no external state) ---

def test_measure_nine_pm_returns_frozen_dataclass():
    """NinePmMetrics must be frozen — no assignment allowed."""
    m = measure_nine_pm(
        nine_pm_open=1.10,
        nine_pm_high=1.12,
        nine_pm_low=1.09,
        nine_pm_close=1.11,
        prior_high=1.11,
        prior_low=1.08,
        prior_h4_index=2,
    )
    assert isinstance(m, NinePmMetrics)
    with pytest.raises((AttributeError, TypeError)):
        m.body_direction = "bullish"  # type: ignore[misc]
