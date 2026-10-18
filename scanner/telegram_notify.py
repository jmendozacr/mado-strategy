"""Sends messages to the configured Telegram chat. Credentials come from
scanner/.env (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) -- never hardcoded,
never logged."""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

_API_BASE = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramConfigError(Exception):
    pass


def send_message(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise TelegramConfigError("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID missing from scanner/.env")
    response = requests.post(
        _API_BASE.format(token=token),
        data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=10,
    )
    response.raise_for_status()
