"""Polling entrypoint: pulls fresh MT5 data, runs the 1AM+9AM HTF-first
detection pipeline (causal.htf_trigger.find_1am_9am_aligned_signals,
backtest.population.build_stage6_population -- never reimplemented here),
filters NEW signals (rules.filter_new_alerts -- dedup only, no session or
reaction filter, odd/tasks/scanner-1am-9am-diversified.md S4/S5), and
sends one Telegram message per new signal, across EURUSD/USDCAD/AUDUSD.

Replaces the old EURUSD-only NY-kill-zone recipe entirely (user: "Reemplaza
todo por lo nuevo") -- see odd/tasks/scanner-1am-9am-diversified.md for the
full spec and the Engram diversification-arc memories for how each
instrument's own config (below) was validated.
"""
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, r"D:\Josué\Documents\proyectos\mado-strategy\detector")

from alignment.htf_ltf import _reindex_daily_key_levels  # noqa: E402
from causal.htf_trigger import find_1am_9am_aligned_signals  # noqa: E402
from composite.ict_order_block import detect_order_blocks, to_key_levels as ob_to_key_levels  # noqa: E402
from core.config import BacktestConfig, DetectorConfig  # noqa: E402
from core.key_level import KeyLevel  # noqa: E402
from primitives.fvg import detect_fvgs, to_key_levels as fvg_to_key_levels  # noqa: E402
from backtest.population import build_stage6_population  # noqa: E402

import mt5_feed  # noqa: E402
import news_calendar  # noqa: E402
import state  # noqa: E402
import telegram_notify  # noqa: E402
from rules import filter_new_alerts  # noqa: E402

# Replaced the old single-pair EURUSD recipe with the validated 1AM+9AM
# diversified account (odd/tasks/scanner-1am-9am-diversified.md S1/S2).
# MODEL_5AM was tested this session and explicitly declined by the user.
SYMBOLS = ("EURUSDm", "USDCADm", "AUDUSDm")
POLL_SECONDS = 120
LOOKBACK = {"D1": 200, "H4": 500, "M15": 2000}

# Per-symbol BacktestConfig, each already validated this session (R:R=2.0
# and kill_zone_gated=False for all three -- each model's own confirmation
# window already bounds which candles can ever produce a signal, so no
# separate kill-zone cut is needed on top). min_stop_distance_price/
# trading_cost_price differ per instrument -- a flat EURUSD-pip-scale
# constant does NOT transfer to USDCAD/AUDUSD, confirmed by sweep this
# session, never assumed.
BACKTEST_CONFIG = {
    "EURUSDm": BacktestConfig(
        min_risk_reward=2.0, trading_cost_price=0.00013, kill_zone_gated=False, min_stop_distance_price=0.0006,
    ),
    "USDCADm": BacktestConfig(
        min_risk_reward=2.0, trading_cost_price=0.000167, kill_zone_gated=False, min_stop_distance_price=0.0,
    ),
    "AUDUSDm": BacktestConfig(
        min_risk_reward=2.0, trading_cost_price=0.00013, kill_zone_gated=False, min_stop_distance_price=0.0,
    ),
}
# Currencies whose high-impact news can affect each pair -- used only to
# ANNOTATE alerts (never to suppress them). FTMO's real 2-minute execution
# restriction applies only on Standard funded accounts, never during the
# Challenge/Verification evaluation (confirmed against ftmo.com/en/faq/can-i-trade-news/).
RELEVANT_CURRENCIES = {
    "EURUSDm": ("EUR", "USD"), "USDCADm": ("USD", "CAD"), "AUDUSDm": ("AUD", "USD"),
}
# ForexFactory's free feed rate-limits aggressive polling (observed 429s
# when fetched every 2-minute poll) -- the calendar barely changes within
# an hour, so cache it instead of refetching every run_once().
NEWS_CACHE_MINUTES = 60
_news_cache = {"events": [], "fetched_at": None}


def _cached_news_events() -> list[dict]:
    now = datetime.now(timezone.utc)
    if _news_cache["fetched_at"] is None or now - _news_cache["fetched_at"] >= timedelta(minutes=NEWS_CACHE_MINUTES):
        try:
            _news_cache["events"] = news_calendar.fetch_this_week_events()
            _news_cache["fetched_at"] = now
        except Exception as error:  # noqa: BLE001 -- news annotation is best-effort, never blocks alerting
            print(f"news calendar fetch failed, keeping last cached events: {error}", file=sys.stderr)
            if _news_cache["fetched_at"] is None:
                _news_cache["fetched_at"] = now  # avoid retrying every single poll on a persistent outage
    return _news_cache["events"]


def _build_key_levels(htf_series, daily_series, fvg_config) -> list[KeyLevel]:
    """HTF FVGs + Daily-tier Order Blocks reindexed to HTF-index-space --
    the exact construction this session verified reproduces the backtested
    1AM+9AM population (mirrors causal.generate.generate_causal_aligned_
    signals' own division of labor: this module builds the raw KeyLevels,
    causal.htf_trigger only ever consumes an already-built list)."""
    htf_fvg_levels = fvg_to_key_levels(detect_fvgs(htf_series, fvg_config))
    daily_ob_levels = ob_to_key_levels(detect_order_blocks(daily_series))
    htf_timestamps = [c.timestamp for c in htf_series.candles]
    reindexed_daily = _reindex_daily_key_levels(
        daily_ob_levels, daily_series.candles, htf_series.candles, htf_timestamps
    )
    return htf_fvg_levels + reindexed_daily


_DIRECTION_MARKER = {"bullish": "\U0001F7E2", "bearish": "\U0001F534"}  # green/red circle
_MODEL_LABEL = {"1am": "1AM", "9am": "9AM"}


def _format_alert(alert, signal_number_today: int, near_news: bool) -> str:
    """HTML parse_mode (Telegram Bot API) -- only <b>/</b> used, no escaping
    needed since every interpolated field is numeric or an ISO timestamp,
    never free text that could contain &lt;/&gt;/&amp;."""
    marker = _DIRECTION_MARKER[alert["direction"]]
    model_label = _MODEL_LABEL.get(alert["model"], alert["model"])
    reaction_label = alert["key_level_reaction"] or "unknown"
    key_level_label = alert["key_level_kind"] or "unknown"
    lines = [
        f"{marker} <b>{alert['symbol']} — {alert['direction'].upper()}</b>",
        f"{model_label} · {reaction_label} · {key_level_label} · señal #{signal_number_today} hoy",
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
    news_events = _cached_news_events()

    for symbol in SYMBOLS:
        m15 = mt5_feed.fetch_series(symbol, "M15", LOOKBACK["M15"])
        h4 = mt5_feed.fetch_series(symbol, "H4", LOOKBACK["H4"])
        d1 = mt5_feed.fetch_series(symbol, "D1", LOOKBACK["D1"])

        config = DetectorConfig(backtest=BACKTEST_CONFIG[symbol])
        key_levels = _build_key_levels(h4, d1, config.fvg)
        results = find_1am_9am_aligned_signals(h4.candles, m15, key_levels, config.crt_range, config.model1)

        aligned_signals = [aligned for aligned, _model in results]
        reaction_by_id = {aligned.ltf_signal.signal_id: aligned.key_level_reaction for aligned, _model in results}
        model_by_id = {aligned.ltf_signal.signal_id: model for aligned, model in results}
        kind_by_id = {
            aligned.ltf_signal.signal_id: (aligned.key_level.kind if aligned.key_level else None)
            for aligned, _model in results
        }
        population = build_stage6_population(aligned_signals, m15, config)

        alerts = filter_new_alerts(
            symbol, population.candidates, reaction_by_id, m15, set(current_state["alerted_ids"])
        )
        for alert in alerts:
            alert["model"] = model_by_id.get(alert["signal_id"])
            alert["key_level_kind"] = kind_by_id.get(alert["signal_id"])
            signal_day = str(alert["anchor_ts"].date())
            if silent:
                current_state = state.record_alert(current_state, alert["stable_id"], symbol, signal_day)
                continue
            signal_number = current_state["daily_counts"].get(signal_day, {}).get(symbol, 0) + 1
            near_news = news_calendar.is_near_high_impact_news(
                alert["anchor_ts"], news_events, RELEVANT_CURRENCIES[symbol]
            )
            telegram_notify.send_message(_format_alert(alert, signal_number, near_news))
            current_state = state.record_alert(current_state, alert["stable_id"], symbol, signal_day)
            print(f"alerted {alert['stable_id']}{' [near news]' if near_news else ''}", flush=True)
        if silent:
            print(f"seeded {len(alerts)} pre-existing candidates for {symbol} (no messages sent)", flush=True)
    return current_state


def main() -> None:
    mt5_feed.connect()
    try:
        current_state = state.load_state()
        is_fresh_state = not current_state["alerted_ids"] and not current_state["daily_counts"]
        if is_fresh_state:
            print("fresh state -- seeding existing candidates silently (no Telegram messages)", flush=True)
            current_state = run_once(current_state, silent=True)
            state.save_state(current_state)
        print(f"scanner started -- polling every {POLL_SECONDS}s for {SYMBOLS}", flush=True)
        while True:
            try:
                current_state = run_once(current_state)
                state.save_state(current_state)
            except Exception as error:  # noqa: BLE001 -- keep polling, never crash the loop silently
                print(f"error during poll: {error}", file=sys.stderr, flush=True)
            time.sleep(POLL_SECONDS)
    finally:
        mt5_feed.disconnect()


if __name__ == "__main__":
    main()
