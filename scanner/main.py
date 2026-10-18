"""Polling entrypoint: pulls fresh MT5 data, runs the real detection
pipeline (cli._detect_all, backtest.population.build_stage6_population --
never reimplemented here), filters new reject_close_inside signals inside
the London+Lunch+NY session (rules.filter_new_alerts), and sends one
Telegram message per new signal.
"""
import sys
import time

sys.path.insert(0, r"D:\Josué\Documents\proyectos\mado-strategy\detector")

from cli import _detect_all  # noqa: E402
from core.config import DetectorConfig  # noqa: E402
from backtest.population import build_stage6_population  # noqa: E402

import mt5_feed  # noqa: E402
import news_calendar  # noqa: E402
import state  # noqa: E402
import telegram_notify  # noqa: E402
from rules import filter_new_alerts  # noqa: E402

SYMBOLS = ("EURUSDm", "GBPUSDm")
POLL_SECONDS = 120
LOOKBACK = {"D1": 200, "H4": 500, "M15": 2000}
# Currencies whose high-impact news can affect each pair -- used only to
# ANNOTATE alerts (never to suppress them). FTMO's real 2-minute execution
# restriction applies only on Standard funded accounts, never during the
# Challenge/Verification evaluation (confirmed against ftmo.com/en/faq/can-i-trade-news/).
RELEVANT_CURRENCIES = {"EURUSDm": ("EUR", "USD"), "GBPUSDm": ("GBP", "USD")}


_DIRECTION_MARKER = {"bullish": "\U0001F7E2", "bearish": "\U0001F534"}  # green/red circle


def _format_alert(alert, signal_number_today: int, near_news: bool) -> str:
    """HTML parse_mode (Telegram Bot API) -- only <b>/</b> used, no escaping
    needed since every interpolated field is numeric or an ISO timestamp,
    never free text that could contain &lt;/&gt;/&amp;."""
    marker = _DIRECTION_MARKER[alert["direction"]]
    lines = [
        f"{marker} <b>{alert['symbol']} — {alert['direction'].upper()}</b>",
        f"reject_close_inside · señal #{signal_number_today} hoy",
        "",
        f"<b>Entry:</b>  {alert['entry_price']:.5f}",
        f"<b>Stop:</b>   {alert['stop_loss']:.5f}",
        f"<b>Target:</b> {alert['take_profit']:.5f}",
        "",
        f"\U0001F550 {alert['anchor_ts'].strftime('%Y-%m-%d %H:%M')} UTC",
    ]
    if near_news:
        lines += ["", "⚠️ <b>Cerca de noticia de alto impacto</b> (±2 min)"]
    return "\n".join(lines)


def run_once(current_state: dict, *, silent: bool = False) -> dict:
    """`silent=True` (REQ: first-ever run only) marks every currently-
    qualifying candidate as already-alerted WITHOUT sending Telegram
    messages -- backfill history inside the lookback window must never be
    blasted as if it were new. Only candidates that appear in a LATER
    poll, after this seeding, are genuinely new and get alerted."""
    config = DetectorConfig()
    try:
        news_events = news_calendar.fetch_this_week_events()
    except Exception as error:  # noqa: BLE001 -- news annotation is best-effort, never blocks alerting
        print(f"news calendar fetch failed, alerts will go out without news annotation: {error}", file=sys.stderr)
        news_events = []

    for symbol in SYMBOLS:
        m15 = mt5_feed.fetch_series(symbol, "M15", LOOKBACK["M15"])
        h4 = mt5_feed.fetch_series(symbol, "H4", LOOKBACK["H4"])
        d1 = mt5_feed.fetch_series(symbol, "D1", LOOKBACK["D1"])

        result = _detect_all(m15, h4, d1, config)
        aligned = result.aligned_signals or []
        reaction_by_id = {s.ltf_signal.signal_id: s.key_level_reaction for s in aligned if s.key_level is not None}
        population = build_stage6_population(aligned, m15, config)

        alerts = filter_new_alerts(
            symbol, population.candidates, reaction_by_id, m15, set(current_state["alerted_ids"])
        )
        for alert in alerts:
            signal_day = str(alert["anchor_ts"].date())
            if silent:
                current_state = state.record_alert(current_state, alert["signal_id"], symbol, signal_day)
                continue
            signal_number = current_state["daily_counts"].get(signal_day, {}).get(symbol, 0) + 1
            near_news = news_calendar.is_near_high_impact_news(
                alert["anchor_ts"], news_events, RELEVANT_CURRENCIES[symbol]
            )
            telegram_notify.send_message(_format_alert(alert, signal_number, near_news))
            current_state = state.record_alert(current_state, alert["signal_id"], symbol, signal_day)
            print(f"alerted {alert['signal_id']} ({symbol}){' [near news]' if near_news else ''}")
        if silent:
            print(f"seeded {len(alerts)} pre-existing candidates for {symbol} (no messages sent)")
    return current_state


def main() -> None:
    mt5_feed.connect()
    try:
        current_state = state.load_state()
        is_fresh_state = not current_state["alerted_ids"] and not current_state["daily_counts"]
        if is_fresh_state:
            print("fresh state -- seeding existing candidates silently (no Telegram messages)")
            current_state = run_once(current_state, silent=True)
            state.save_state(current_state)
        print(f"scanner started -- polling every {POLL_SECONDS}s for {SYMBOLS}")
        while True:
            try:
                current_state = run_once(current_state)
                state.save_state(current_state)
            except Exception as error:  # noqa: BLE001 -- keep polling, never crash the loop silently
                print(f"error during poll: {error}", file=sys.stderr)
            time.sleep(POLL_SECONDS)
    finally:
        mt5_feed.disconnect()


if __name__ == "__main__":
    main()
