"""Polling entrypoint: pulls fresh MT5 data, runs the 1AM+9AM HTF-first
detection pipeline (causal.htf_trigger.find_1am_9am_aligned_signals,
backtest.population.build_stage6_population -- never reimplemented here),
filters NEW signals (rules.filter_new_alerts -- dedup only, no session or
reaction filter, odd/tasks/scanner-1am-9am-diversified.md S4/S5), and
sends one Telegram message per new signal, across EURUSD/USDCAD/AUDUSD/
GBPUSD/USDJPY.

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
from execution import calculate_lot_size, pending_order_type  # noqa: E402
from rules import filter_new_alerts  # noqa: E402

# Replaced the old single-pair EURUSD recipe with the validated 1AM+9AM
# diversified account (odd/tasks/scanner-1am-9am-diversified.md S1/S2),
# then extended to 5 pairs (user decision, 2026-11-15, after the full
# 3-vs-4-vs-5-pair comparison: 5-pair wins on FTMO pass rate at the 1%
# risk this account trades, shortest stagnation, highest total R --
# Engram detector/1am-9am-diversified/final-5-pair-decision).
# MODEL_5AM was tested this session and explicitly declined by the user.
SYMBOLS = ("EURUSDm", "USDCADm", "AUDUSDm", "GBPUSDm", "USDJPYm")
POLL_SECONDS = 120
LOOKBACK = {"D1": 200, "H4": 500, "M15": 2000}

# Per-symbol BacktestConfig. EURUSDm/USDCADm/AUDUSDm validated against
# this broker's own real spread. GBPUSDm/USDJPYm's trading_cost_price is
# a WEB-RESEARCH ESTIMATE (FTMO Standard average spread, padded like
# EURUSDm's own margin), NOT independently verified against this broker's
# live spread the way the other three were -- confirm against the real
# MT5 terminal before trusting its P&L, especially USDJPYm (the weakest
# of the five pairs in every backtest this session, 45.6% win rate).
# min_stop_distance_price/trading_cost_price differ per instrument -- a
# flat EURUSD-pip-scale constant does NOT transfer across pairs, confirmed
# by sweep; USDJPYm's floor is scaled 100x for the yen's price scale
# (pip=0.01, not 0.0001). R:R=2.0 and kill_zone_gated=False for all five --
# each model's own confirmation window already bounds which candles can
# ever produce a signal, so no separate kill-zone cut is needed on top.
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
    "GBPUSDm": BacktestConfig(
        min_risk_reward=2.0, trading_cost_price=0.00014, kill_zone_gated=False, min_stop_distance_price=0.0006,
    ),
    "USDJPYm": BacktestConfig(
        min_risk_reward=2.0, trading_cost_price=0.0275, kill_zone_gated=False, min_stop_distance_price=0.06,
    ),
}
# Currencies whose high-impact news can affect each pair -- used only to
# ANNOTATE alerts (never to suppress them). FTMO's real 2-minute execution
# restriction applies only on Standard funded accounts, never during the
# Challenge/Verification evaluation (confirmed against ftmo.com/en/faq/can-i-trade-news/).
RELEVANT_CURRENCIES = {
    "EURUSDm": ("EUR", "USD"), "USDCADm": ("USD", "CAD"), "AUDUSDm": ("AUD", "USD"),
    "GBPUSDm": ("GBP", "USD"), "USDJPYm": ("USD", "JPY"),
}

# odd/tasks/scanner-auto-execution.md S1/S2/S7: real MT5 pending orders,
# not just Telegram alerts -- user's explicit decision, default True, since
# Sunday's activation is on a $10,000 DEMO account (no real-money risk).
# Flip to False to go back to alert-only, same behavior as before this task.
AUTO_EXECUTE = True
RISK_PCT = 1.0  # matches this session's own $10k/1%-risk USD-ledger convention
# Fixed, non-compounding -- NEVER the live/current account balance. Every
# rolling-window/FTMO result this session validated risk as 1% of a FIXED
# initial balance (research.eurusd_recipe_validation.sizing's own docstring:
# "non-compounding, because the limits this is measured against are
# themselves static from the initial balance" -- mirrors FTMO's own static-
# from-initial-capital rule). Sizing off the live balance instead would be
# compounding position sizing, a materially different, never-backtested
# scheme.
INITIAL_BALANCE = 10000.0
MAX_FILL_WAIT_CANDLES = 20  # M15 candles -- BacktestConfig's own default (S4/S5)
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


def _execute_alert(alert: dict, symbol: str) -> None:
    """odd/tasks/scanner-auto-execution.md S3/S4/S5/S6: sizes and places a
    real pending order for one new alert. Never called for a silent-seed
    poll (S5's own safety line -- backfilled history is never a live
    trade). Logs and returns on any skip/failure; never raises past this
    function, so one symbol's execution problem can never stop the poll
    loop or suppress the Telegram alert that already went out."""
    specs = mt5_feed.symbol_trade_specs(symbol)
    lot = calculate_lot_size(
        balance=INITIAL_BALANCE, risk_pct=RISK_PCT, entry_price=alert["entry_price"], stop_loss=alert["stop_loss"],
        **specs,
    )
    if lot is None:
        print(f"execution skipped for {alert['stable_id']}: target lot size below the symbol's volume_min", flush=True)
        return

    price = mt5_feed.current_price(symbol, alert["direction"])
    order_type = pending_order_type(alert["direction"], entry_price=alert["entry_price"], current_price=price)
    result = mt5_feed.send_pending_order(
        symbol, order_type, volume=lot, entry_price=alert["entry_price"], stop_loss=alert["stop_loss"],
        take_profit=alert["take_profit"], max_fill_wait_candles=MAX_FILL_WAIT_CANDLES,
    )
    if mt5_feed.order_succeeded(result):
        print(f"order placed for {alert['stable_id']}: {order_type} {lot} lots", flush=True)
    else:
        print(f"order REJECTED for {alert['stable_id']}: retcode={getattr(result, 'retcode', None)}", file=sys.stderr, flush=True)


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
            if AUTO_EXECUTE:
                try:
                    _execute_alert(alert, symbol)
                except Exception as error:  # noqa: BLE001 -- S6: one order failure must never stop the poll
                    print(f"execution error for {alert['stable_id']}: {error}", file=sys.stderr, flush=True)
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
