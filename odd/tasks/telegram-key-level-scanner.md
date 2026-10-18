# Telegram Key-Level Scanner

**Objective**: a live scanner that pulls fresh EURUSDm/GBPUSDm candles from
the user's locally-running MT5 terminal, runs the already-validated signal
rules (natural CRT-opposite-extreme TP, `reject_close_inside` Key Level
confluence, confirmed Model-1, London+Lunch+NY session window), and sends a
Telegram message for each new qualifying signal. Human stays in the loop —
the message reports context (today's signal/loss count per pair) so the
user applies the daily-loss-stop/concurrency judgment themselves, rather
than the scanner silently suppressing alerts.

**Branch**: none yet (not started). **Delivery**: work-unit commits once
S-000 is verified end-to-end.

## Specs

- S1: Pull fresh Daily/H4/M15 candles for EURUSDm and GBPUSDm from the
  locally-running MT5 terminal via the `MetaTrader5` Python package.
- S2: Run the exact validated detection pipeline (reuse `cli._detect_all`,
  `backtest.population.build_stage6_population`'s real selection, natural
  `take_profit()`) — never reimplement detection logic.
- S3: Filter to signals that are CONFIRMED (status), `aligned`, and
  `key_level_reaction == "reject_close_inside"`, with anchor timestamp
  inside London(02-05)/London-Lunch(05-07)/New-York(07-11) NY-local.
- S4: Never alert the same signal twice across polls (persisted
  dedup state, keyed by `signal_id` + instrument).
- S5: Each Telegram message reports: instrument, direction, entry/stop/
  target prices, and today's running signal + loss count for that
  instrument (informational only — never auto-suppressed).
- S6: Credentials (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) read from
  `scanner/.env`, gitignored, never logged or echoed.

- S7: Annotate (never suppress) an alert when its anchor timestamp falls
  within +/-2 minutes of a High-impact EUR/USD/GBP news release, sourced
  from ForexFactory's free public weekly JSON feed (no API key). Matches
  FTMO's real rule (confirmed at ftmo.com/en/faq/can-i-trade-news/):
  applies only to Standard funded accounts, never during Challenge/
  Verification -- so this is informational context for the funded phase,
  not a Phase-1/2 requirement.

## Tasks

- [x] T1 (S1, S6): MT5 connection + candle pull, verified against real
  account data (live EURUSDm M15 candles pulled successfully).
- [x] T2 (S6): Telegram send, verified with one real test message
  (user confirmed receipt).
- [x] T3 (S2, S3): Rule engine (`rules.filter_new_alerts`) wired to the
  real pipeline (`build_stage6_population`, never reimplemented). 5 tests.
- [x] T4 (S4): Dedup state persistence (`state.py`). 4 tests.
- [x] T5 (S5): Message formatting with per-instrument daily context
  (`main._format_alert`).
- [x] T6: Polling loop main entrypoint (`main.py`), not yet started live.
- [x] T7 (S7): News-calendar annotation (`news_calendar.py`, ForexFactory
  free feed), wired into `_format_alert`. 6+2 tests. Best-effort fetch --
  a feed failure never blocks alerting, only skips the annotation.
- [x] T8: Styled message format (Telegram HTML parse_mode): bold labels,
  green/red direction marker, clock + warning emojis. 4+1 tests. User
  confirmed real rendering looks correct.

## Log

- L1 (verbatim): "listo revisa" — confirmed `scanner/.env` exists (93
  bytes, not inspected — read access to `.env` files is permission-denied
  by design). Walking skeleton (T1/T2) verified end-to-end: real MT5
  candles pulled, real Telegram message received by the user.
- L2 (incident, same turn): first `run_once()` call against real MT5 data
  sent **35 real Telegram messages** — every reject_close_inside candidate
  inside the ~3-week M15 lookback window was treated as "new" against an
  empty dedup state. Root cause: no distinction between "first-ever run,
  seed what already exists" and "live poll, alert only on genuinely new
  signals." Fixed: `run_once(..., silent=True)` seeds state without
  sending messages; `main()` auto-detects a fresh state file and runs the
  first pass silently. Pinned with `tests/test_main_silent_seed.py`
  (regression test, asserts zero Telegram sends during silent seeding).
  Also fixed in the same pass: a real `KeyError: 'H4'` from using MT5's
  own timeframe labels instead of `core.pairing_table.TIMEFRAME_DURATIONS`'
  labels ("4H"/"15M"/"D"); and daily signal counts were keyed by
  `date.today()` instead of each signal's own `anchor_ts` date (would have
  mislabeled every backfilled signal's "señal #N hoy" count).
  `state.json` already holds the 35 real signal_ids from the incident —
  left as-is, since that is exactly the correct seeded state the silent
  path would have produced; no cleanup needed.
- Live polling loop (`uv run python main.py`) NOT yet started — holding
  for explicit user go-ahead given the incident above.
