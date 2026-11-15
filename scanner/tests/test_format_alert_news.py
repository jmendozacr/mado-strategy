"""TDD test for _format_alert's news-proximity annotation (informational
only, per FTMO's real rule -- never suppresses, see news_calendar.py)."""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "detector"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402


def _alert():
    return {
        "signal_id": "x", "symbol": "EURUSDm", "direction": "bullish",
        "entry_price": 1.1, "stop_loss": 1.09, "take_profit": 1.12,
        "anchor_ts": datetime(2026, 10, 19, 12, 30, 0),
        "model": "9am", "key_level_reaction": "reject_close_inside", "key_level_kind": "fvg",
    }


def test_near_news_flag_true_adds_warning_line():
    text = main._format_alert(_alert(), signal_number_today=1, near_news=True)
    assert "noticia" in text.lower()


def test_near_news_flag_false_has_no_warning_line():
    text = main._format_alert(_alert(), signal_number_today=1, near_news=False)
    assert "noticia" not in text.lower()
