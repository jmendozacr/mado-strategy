"""TDD for the styled (HTML parse_mode) alert format."""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "detector"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402


def _bullish_alert():
    return {
        "signal_id": "x", "symbol": "EURUSDm", "direction": "bullish",
        "entry_price": 1.1, "stop_loss": 1.09, "take_profit": 1.12,
        "anchor_ts": datetime(2026, 10, 19, 12, 30, 0),
        "model": "9am", "key_level_reaction": "reject_close_inside", "key_level_kind": "fvg",
    }


def _bearish_alert():
    return {**_bullish_alert(), "direction": "bearish"}


def test_bullish_gets_green_marker():
    text = main._format_alert(_bullish_alert(), signal_number_today=1, near_news=False)
    assert "\U0001F7E2" in text  # green circle


def test_bearish_gets_red_marker():
    text = main._format_alert(_bearish_alert(), signal_number_today=1, near_news=False)
    assert "\U0001F534" in text  # red circle


def test_symbol_and_labels_are_bold_html():
    text = main._format_alert(_bullish_alert(), signal_number_today=1, near_news=False)
    assert "<b>" in text and "</b>" in text
    assert "EURUSDm" in text


def test_news_warning_uses_warning_emoji():
    text = main._format_alert(_bullish_alert(), signal_number_today=1, near_news=True)
    assert "\u26A0" in text  # warning sign
