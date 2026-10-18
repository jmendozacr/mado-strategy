"""TDD: send_message must request HTML parse_mode so <b> tags render."""
import sys

sys.path.insert(0, r"D:\Josué\Documents\proyectos\mado-strategy\scanner")

import telegram_notify  # noqa: E402


def test_send_message_requests_html_parse_mode(monkeypatch):
    captured = {}

    class _FakeResponse:
        def raise_for_status(self):
            pass

    def _fake_post(url, data, timeout):
        captured.update(data)
        return _FakeResponse()

    monkeypatch.setattr(telegram_notify.requests, "post", _fake_post)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "dummy")

    telegram_notify.send_message("<b>hi</b>")

    assert captured["parse_mode"] == "HTML"
    assert captured["text"] == "<b>hi</b>"
