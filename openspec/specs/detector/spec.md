# Specs: CRT/ICT Pattern Detector

**Spec version**: V6 | **Status**: signed | **Domain**: detector

**Scope note**: Covers 5 of 7 originally-named setup types (Swing, FVG, CRT range, MSS, Model-1), plus a candle-by-candle trade backtest simulator over Model-1 signals (single take-profit level; partial exits/equity curve/drawdown deferred to `crt-detector-backtest-partial-exits`), plus a classical ICT Order Block detector wired as a second Key Level confluence source (Daily-tier, `crt-detector-ict-order-block`) — HTF-only, computed-not-rendered, mirroring FVG's own Key Level treatment: no standalone `detections.csv` row/type, no `overlay.png` marker. Breaker Block remains deferred (pending change `crt-detector-order-block-breaker`, superseded in sequencing by the `crt-detector-key-level-confluence` program's sub-change #3), ratified at the steward foresight gate.

---

## Domain: ohlc-ingestion

### REQ-01: Load MetaTrader 5 CSV export with explicit instrument identity
The system MUST parse an MT5-exported OHLC CSV (tab-delimited, header row, columns `<DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE> <TICKVOL> <VOL> <SPREAD>`, broker-local timezone unconverted) into `OHLCSeries`, with `instrument` populated from a required `--symbol` CLI flag (the file itself carries no symbol column — see design ADR-06).
- **REQ-01.1** (happy): GIVEN a valid MT5 CSV + `--symbol EURUSD`, WHEN loaded, THEN an OHLCSeries with ascending-timestamp Candles and `instrument="EURUSD"` is returned.
- **REQ-01.2** (edge): GIVEN a CSV with a duplicate timestamp, WHEN loaded, THEN a named error is raised — no silent dedup.

### REQ-02: Reject malformed input
The system MUST reject a CSV missing required columns or with non-monotonic timestamps, naming the row/problem.
- **REQ-02.1**: GIVEN a CSV missing `<HIGH>`, WHEN loaded, THEN fails naming the column — no partial series.

## Domain: htf-ltf-alignment

### REQ-03: Load paired HTF+LTF series
The system MUST accept two OHLCSeries for the SAME instrument (validated via REQ-27) and align by timestamp.
- **REQ-03.1**: GIVEN Daily HTF + 1H LTF for EURUSD, WHEN aligned, THEN each LTF candle resolves to exactly one enclosing HTF candle.

### REQ-04: Timeframe pairing table
The system MUST validate the HTF/LTF pair against charter-2's 5-row table (Monthly→Daily, Weekly→4H, Daily→1H, 4H→15M, 1H→5M — authoritative over charter-4's subset) and reject unlisted pairings.
- **REQ-04.1**: GIVEN Daily+1H, WHEN validated, THEN passes.
- **REQ-04.2**: GIVEN Daily+5M, WHEN validated, THEN rejected, citing expected 1H.

### REQ-05: Tag Model-1 signals with HTF alignment
The system MUST tag each LTF Model-1 detection `aligned` (within an HTF CRT purge window), `unaligned` (no HTF purge window active), or `insufficient_htf_data` (partial-tail-coverage case, ADR-05) — three distinct states, none silently dropped. Session/Kill-Zone timing is explicitly NOT part of this check.
- **REQ-05.1** (grounded, charter-2 [00:12:34]-[00:13:55]): GIVEN an HTF CRT purge and an LTF Model-1 signal inside its price/time window, WHEN tagged, THEN `aligned`.
- **REQ-05.2**: GIVEN an LTF signal with no HTF purge window active, WHEN tagged, THEN `unaligned`.
- **REQ-05.3**: GIVEN an LTF signal near the series tail where the HTF candle isn't fully covered by available LTF data, WHEN tagged, THEN `insufficient_htf_data`.

### REQ-27: Reject mismatched-instrument pairing
The system MUST reject an HTF+LTF pair whose `--htf-symbol`/`--ltf-symbol` flags differ.
- **REQ-27.1**: GIVEN `--htf-symbol EURUSD --ltf-symbol GBPUSD`, WHEN loaded, THEN rejected, naming both instruments.

## Domain: swing-detection

### REQ-06: Strict 3-candle fractal Swing High/Low
`high[i] > high[i-1] AND high[i] > high[i+1]` (mirror for Low). Ties are NOT swings.
- **REQ-06.1** (grounded, charter-2 [00:05:28]): pre-purge high flagged before the purge candle appears.
- **REQ-06.2** (edge): two candles with identical highs — neither flagged.
- **REQ-06.3** (edge): series < 3 candles — no result, not an error.

### REQ-07: No-lookahead (Swing)
`detect(series.up_to(n))` matches full-series output up to index `n-1` (k=1), for all n. Property test.

## Domain: fvg-detection

### REQ-08: Detect Fair Value Gap
Bullish FVG = `candle[i+2].low > candle[i].high` (mirror bearish); top/bottom = those extremes.
- **REQ-08.1** (grounded, charter-2 [00:13:19] DXY daily): FVG top/bottom match candle-1/candle-3 extremes.

### REQ-09: Exclude zero/negative-width gaps
Gaps < `FVGConfig.min_size_atr` (default 0.1 × ATR(14) at formation) excluded.
- **REQ-09.1**: gap width < threshold — not flagged.

### REQ-10: Track fill/mitigation status
`filled` once cumulative price action after formation reaches the far edge of the gap; else `open`.
- **REQ-10.1** (grounded, charter-3 [00:14:47]-[00:15:23]): partial re-entry only — remains `open`.

## Domain: crt-range-detection

### REQ-11: 3-Candle CRT (sliding window)
Every 3 consecutive candles evaluated as a candidate, independent of calendar alignment.
- **REQ-11.1** (grounded, charter-1 [00:16:11]): correct High/Low + `true_break` resolution.

### REQ-12: 2-Candle CRT
Vela2 purges + resolves within itself.
- **REQ-12.1** (grounded, charter-1 [00:16:53]): flagged 2-Candle, not 3.

### REQ-13: Multiple-Candle CRT (Inside/Outside Bar)
`CRTRangeConfig.max_lookback=20` candle cap.
- **REQ-13.1** (grounded, charter-1 [00:18:12]): one Inside-Bar detection, not N false ranges.

### REQ-14: Only surface resolved ranges
Unresolved by series end → not emitted at all (prevents sliding-window noise flood).
- **REQ-14.1**: price stays inside range to series end — no range flagged.

## Domain: mss-detection

### REQ-15: Detect Market Structure Shift
Close beyond a counter-trend swing by ≥ `MSSConfig.decisive_close_ratio` (default 0.25) of the swing-to-opposite-extreme distance.
- **REQ-15.1** (grounded, charter-3 [00:10:32]): bullish MSS flagged at the break candle.

### REQ-16: Exclude plain continuation
MUST be preceded by rejection of the opposite extreme.
- **REQ-16.1**: break with no prior rejection — no MSS.

## Domain: model1-entry-detection

### REQ-17: Purge-and-anchor candle
Internal Model-1 logic, absorbs charter-2's "Order Block" — no separate detector.
- **REQ-17.1** (grounded, charter-2 [00:04:15],[00:15:16]): purge candle marked as anchor.

### REQ-18: Engulf confirmation
Respect Rule at ZERO tolerance (any close beyond the anchor's protected extreme before confirmation invalidates immediately).
- **REQ-18.1** (grounded, charter-2 [00:06:35]-[00:07:02]): delayed engulf, no intervening breach — anchor stays valid, confirms on close.

### REQ-19: FVG-fill confirmation
Anchor candle also satisfies REQ-10.
- **REQ-19.1** (grounded, charter-2 [00:07:27]-[00:07:56]): dual-condition, flagged high-probability.

### REQ-20: Wick-vs-Body entry selection
Wick if confirming close beyond anchor's wick extreme; else Body; tie-break via `body_ratio_tiebreak=0.6`.
- **REQ-20.1**: close beyond wick extreme — Wick used regardless of body size.

### REQ-21: Three-state status
CONFIRMED (retest + respect), INVALIDATED (Respect Rule breach OR retest-then-close-through), PENDING (`max_retest_lookback=20` candles or series end, anchor still unbreached, no retest yet).
- **REQ-21.1** (grounded, charter-2 [00:08:29]-[00:08:57]): no retest by series end — PENDING, never dropped.

### REQ-22: No-lookahead (Model-1)
k=`max_retest_lookback`.

### REQ-43: `confirmation_index` field
`Model1Signal` MUST carry a `confirmation_index: int` field — the index of the candle at which the signal's terminal `status` (CONFIRMED, INVALIDATED, or the `PENDING` window-close fallback) first became determinable, distinct from `retest_index` (the earlier index at which the retest touch itself occurred). This field is a TRACEABILITY/AUDIT field only — it records when a signal's fate became knowable, for reporting and kill-zone-timing evidence, but is NOT consumed by the backtest fill, stop-loss, or take-profit mechanism (REQ-50's unified fill-window search begins at `retest_index` for every candidate type, never at `confirmation_index + 1`).
- **REQ-43.1** (happy): GIVEN a signal whose engulfing close confirms 6 candles after its retest touch, WHEN `confirmation_index` is set, THEN it equals the index of that confirming candle.

### REQ-44: HTF alignment requirement for take-profit sourcing
A trade candidate MUST be sourced ONLY from an `AlignedSignal` whose `aligned == "aligned"` — take-profit is read directly from that `AlignedSignal.htf_context` (REQ-32), never independently recomputed or re-derived from the LTF series. A signal tagged `unaligned` or `insufficient_htf_data` MUST NOT become a candidate, regardless of its `Model1Signal.status`.
- **REQ-44.1** (happy): GIVEN an aligned CONFIRMED signal, WHEN take-profit is sourced, THEN it is read from that signal's own `AlignedSignal.htf_context`'s opposite extreme — never a freshly recomputed value.
- **REQ-44.2** (edge): GIVEN a signal tagged `aligned="unaligned"`, WHEN the candidate population is built, THEN it is excluded, regardless of its underlying `Model1Signal.status`.

## Domain: configurable-parameters

### REQ-25: Discretionary thresholds are configurable, never hardcoded
Every ICT-qualitative threshold sourced from `DetectorConfig`, defaults documented in `design.md` §4.4. Python-level defaults only — no CLI/file config parsing in v1.
- **REQ-25.1**: config-completeness AST scan finds no bare numeric literal outside `config.py` (excluding index/loop counters).

## Domain: no-lookahead-completeness

### REQ-26: No-lookahead applies uniformly
FVG, CRT range, MSS, and HTF/LTF alignment satisfy the same property as Swing/Model-1, each with its own `k`.
- **REQ-26.1**: property test per detector, prefix-consistency.
- **REQ-26.2**: partial HTF+LTF tail — alignment tags stable up to the truncation point.

## Domain: cli-output-filtering

### REQ-28: Date-range and detector-type filters
`--from-date/--to-date/--types` filter RESULTS after detection, never the input series (preserves no-lookahead correctness). Omitted = full unfiltered output.
- **REQ-28.1**: `--types fvg,model1` — only those markers/rows appear; CRT range still computed internally (Model-1 dependency) but not shown.
- **REQ-28.2**: no filters — full unfiltered output.

### REQ-29: Kill Zone session filter
`--session ny-killzone` filters RESULTS (same post-detection pattern as REQ-28, never the input series) to detections anchored inside the New York Kill Zone (charter-3 [00:07:52]: 7:00-10:00/11:00am NY-local; `KillZoneConfig` defaults to the wider 11:00 upper bound). Converted via real `America/New_York` tz rules against UTC candle timestamps — not a fixed UTC offset, since the boundary shifts with US DST.
- **REQ-29.1**: a candle at a UTC hour that maps to 07:00-10:59 NY-local, WHEN filtered, THEN kept.
- **REQ-29.2**: the same UTC hour maps to inside the kill zone during EDT but outside during EST (11:00 UTC → 07:00 EDT vs. 06:00 EST) — the filter follows the DST-correct local hour, not a fixed UTC window.
- **REQ-29.3**: `--session bogus` — rejected, naming the unknown token.

### REQ-45: `--backtest` flag and trades.csv contract
The system MUST accept a `--backtest` boolean flag, composable with the existing `--from-date`/`--to-date`/`--session`/`--types` filter chain. WHEN `--backtest` is supplied, the system MUST write `trades.csv` with exactly these 17 columns in this order: `signal_id, anchor_timestamp, entry_timestamp, direction, entry_price, stop_loss, take_profit, exit_timestamp, exit_price, outcome, r_multiple, ambiguous_bar, gap_filled, partial_exit_timestamp, partial_exit_price, partial_r_multiple, partial_gap_filled` (the 4 trailing columns append-only, mirroring `detections.csv`'s own `key_level_source` trailing-column precedent, REQ-24; blank/`False` for a trade with no partial leg, REQ-38.3). WHEN `--backtest` is supplied, `detections.csv` gains a trailing `signal_id` column (REQ-41) and no other change; `overlay.png` is unaffected. WHEN `--backtest` is NOT supplied, the system MUST reproduce today's exact byte-for-byte output for both `detections.csv` and `overlay.png` — no carve-out applies.
- **REQ-45.1** (happy, regression): GIVEN `--session ny-killzone --backtest`, WHEN the run completes, THEN trades are filtered accordingly AND `overlay.png` is byte-identical to an equivalent non-backtest run.
- **REQ-45.2** (edge, contract): GIVEN any `--backtest` run producing at least one trade, WHEN `trades.csv` is inspected, THEN its header is exactly the 17 columns above in that order, and `entry_timestamp` is the timestamp of the candle at `fill_index` (REQ-50).
- **REQ-45.3** (edge, byte-for-byte without carve-out): GIVEN a detector run WITHOUT `--backtest`, WHEN `detections.csv` and `overlay.png` are inspected, THEN both are byte-for-byte identical to the equivalent pre-backtest-feature output, with no `signal_id` column present in `detections.csv`.
- **REQ-45.4** (edge, contract): GIVEN any `--backtest` run, WHEN `trades.csv` is inspected, THEN its header is exactly the 17 columns above, in that order.
- **REQ-45.5** (edge, disclosure): GIVEN a trade whose partial leg fired, WHEN its `trades.csv` row is inspected, THEN its 4 trailing cells are populated; GIVEN a trade with no partial leg, THEN those same 4 cells are blank/`False`.

### REQ-51: BacktestConfig CLI overrides
The system MUST accept 6 CLI flags, each overriding exactly one `BacktestConfig` field when `--backtest` is used, falling back to that field's default when the flag is omitted: `--sl-buffer` (REQ-31's `sl_buffer_price`, default `0.0002`, a raw price-unit offset, never a pip count), `--min-rr` (REQ-35's `min_risk_reward`), `--trading-cost` (REQ-48's `trading_cost_price`), `--kill-zone-gated` (REQ-36's gate, boolean), `--max-fill-wait` (REQ-50's `max_fill_wait`), `--partial-fraction` (REQ-68's `partial_fraction`, default `0.5`, valid range `[0.0, 1.0)` — `1.0` is rejected as degenerate since no remainder leg would exist). 1:1 flag-to-field mapping — no new configuration abstraction beyond it.
- **REQ-51.1** (happy): GIVEN `--backtest --min-rr 3.0`, WHEN a run executes, THEN `excluded_rr_floor` is computed against `3.0`, not the `2.0` default, and downstream trade counts differ measurably from an equivalent run using the `2.0` default on the same input.
- **REQ-51.2** (edge): GIVEN `--backtest` with none of the 6 override flags supplied, WHEN a run executes, THEN all 6 fields use `BacktestConfig`'s defaults, producing output identical to a run with all 6 flags set explicitly to those same default values.
- **REQ-51.3** (edge): GIVEN `--backtest` invoked with an override flag value that violates that flag's constraint — `--max-fill-wait` set to zero or negative, or `--sl-buffer`, `--min-rr`, or `--trading-cost` set to a negative value — WHEN the run starts, THEN the system MUST reject with exit 1, naming the offending flag and the constraint it violates.
- **REQ-51.4** (happy, comparability escape hatch): GIVEN `--backtest --partial-fraction 0.0`, WHEN a run executes, THEN it reproduces, trade-for-trade, the exact single-TP outcomes and r_multiples this codebase produced before the partial-exit feature (REQ-68.5).
- **REQ-51.5** (edge, validation): GIVEN `--partial-fraction` supplied with a negative value or a value `>= 1.0`, WHEN the run starts, THEN the system MUST reject with exit 1, naming the flag and the constraint violated.

## Domain: backtest-simulation

### REQ-30: Tradeable candidate population selection
The system MUST select as a trade CANDIDATE (subject to fill simulation, REQ-50) every `AlignedSignal` whose `aligned == "aligned"` AND whose `ltf_signal` is eligible to be entered: `status == CONFIRMED`, `status == INVALIDATED` with `retest_index` not `None`, OR `status == PENDING` with `retest_index` not `None`. The system MUST NOT select any signal whose `retest_index is None` — regardless of status — nor `fvg_fill`-confirmed signals (no CRT range at all), nor `unaligned`/`insufficient_htf_data` signals, as candidates. All three eligible candidate types share the same fill-timing mechanism (REQ-50): the fill-window search is `[retest_index, retest_index + max_fill_wait]` for all of them.
- **REQ-30.1** (happy): GIVEN an `aligned` CONFIRMED signal, WHEN the candidate population is built, THEN it becomes a trade candidate, subject to REQ-50's unified fill-window search starting at `retest_index`.
- **REQ-30.2** (edge): GIVEN an `aligned` INVALIDATED signal with `retest_index` set, WHEN the candidate population is built, THEN it becomes a trade candidate subject to REQ-50's SAME unified fill-window search starting at `retest_index`. Some INVALIDATED+retest candidates correctly fail to fill within the window and land in `excluded_never_filled` instead of being forced into a loss (see REQ-50.4).
- **REQ-30.3** (edge): GIVEN a signal with `retest_index is None`, regardless of status, WHEN the candidate population is built, THEN no candidate is created; counted under `excluded_never_confirmed` (REQ-40, stage 3).
- **REQ-30.4** (edge): GIVEN a CONFIRMED `fvg_fill` signal, WHEN the candidate population is built, THEN no candidate is created; counted under "no CRT range" (REQ-40).
- **REQ-30.5** (edge): GIVEN a CONFIRMED signal tagged `unaligned` or `insufficient_htf_data`, WHEN the candidate population is built, THEN no candidate is created; counted under "unaligned" (REQ-40).
- **REQ-30.6** (edge): GIVEN an `aligned` PENDING signal with `retest_index` set (entry touched, confirmation never resolved within `max_retest_lookback`), WHEN the candidate population is built, THEN it becomes a trade candidate subject to REQ-50's same unified fill-window search starting at `retest_index` — mirroring REQ-30.2. Closes a survivorship-bias gap: excluding these entirely would silently drop exactly the setups most likely to resolve as losses or opens.

### REQ-31: Stop-loss placement
The system MUST place SL beyond a real structural level, computed relative to the REQ-47 entry price (never equal to it, subject to REQ-47.4's documented exception): the purge (anchor) candle's own swept extreme (`protected_extreme`) by default, offset further by `BacktestConfig.sl_buffer_price` away from entry; OR, when one or more swing highs/lows exist beyond `protected_extreme` between the CRT purge and the entry (`retest_index`, never `fill_index` — using `fill_index` would introduce lookahead), the DEEPEST such qualifying swing, offset the same way. `BacktestConfig.sl_buffer_price` defaults to `0.0002` — a raw PRICE-UNIT offset (2 pips on a 5-digit EURUSD quote), never a pip count.
- **REQ-31.1** (grounded, charter-2 [00:18:46], happy — purge-extreme branch): GIVEN bullish signal, `protected_extreme=1.0990`, no swing low beyond it, `sl_buffer_price=0.0002`, WHEN SL computed, THEN `stop_loss=1.0988`.
- **REQ-31.2** (grounded, single-swing branch): GIVEN the same signal, but a swing low at `1.0975` exists beyond `protected_extreme=1.0990`, WHEN SL computed, THEN `stop_loss` anchors to the swing low: `1.0975 - 0.0002 = 1.0973`.
- **REQ-31.3** (edge, regression): GIVEN a wick-type signal whose entry price is the REQ-47.2 anchor wick extreme (`1.1005`), WHEN entry and SL are both computed (`stop_loss=1.0988`), THEN `risk = 0.0017` — 17 pips.
- **REQ-31.4** (edge): GIVEN two swing lows beyond `protected_extreme=1.0990` — `1.0975` and `1.0960` — WHEN SL computed with `sl_buffer_price=0.0002`, THEN `stop_loss` anchors to the deeper swing: `1.0960 - 0.0002 = 1.0958`.

### REQ-32: Take-profit sourcing and HTF pair-mode requirement
The system MUST compute a trade candidate's take-profit price as the HTF CRT range's opposite extreme, sourced from `AlignedSignal.htf_context` (REQ-44) — never independently recomputed from the LTF series. The system MUST require HTF pair mode (`--htf-csv` and `--htf-symbol` both supplied) whenever `--backtest` is used; WHEN either flag is missing, THEN the system MUST fail fast at start, exiting 1 and naming both missing flags, before any candidate is evaluated.
- **REQ-32.1** (happy): GIVEN an aligned CONFIRMED signal whose `htf_context` is a CRTRange with `high=1.1050`/`low=1.0900` (bullish direction), WHEN take-profit is computed, THEN `take_profit=1.1050`.
- **REQ-32.2** (edge): GIVEN `--backtest` invoked without `--htf-csv`, WHEN the run starts, THEN the system exits 1, naming both `--htf-csv` and `--htf-symbol` as required.

### REQ-33: Same-candle SL+TP tie-break
WHEN a single candle's range touches both a trade's stop-loss and take-profit levels, the system MUST resolve the trade as a loss at the stop-loss price (pessimistic tie-break). Every such resolution MUST be counted and disclosed in `metrics_summary` as a distinct count of "same-candle SL+TP resolutions". Resolution order: (1) an unresolved-by-series-end trade is `open`, no gap check runs; (2) the resolving level is chosen first — SL wins whenever `sl_index <= tp_index`; (3) only after the level is chosen does the system check whether that candle's open already lies beyond the CHOSEN level (REQ-34).
- **REQ-33.1** (happy): GIVEN a candle whose range touches both SL and TP, WHEN resolved, THEN `outcome="loss"` at the SL price, and `ambiguous_bar=True`.
- **REQ-33.2** (edge, disclosure): GIVEN a backtest run in which 4 trades resolve via this tie-break, WHEN `metrics_summary` is written, THEN it states "same-candle SL+TP resolutions: 4".
- **REQ-33.3** (edge, structural precedence over REQ-34): GIVEN a bullish candle whose open lies above take-profit AND whose low also reaches stop-loss, WHEN resolved, THEN `outcome="loss"` at `stop_loss`, `gap_filled=False`.

### REQ-34: Gap-through-both-levels exit fill
WHEN the resolving exit candle's open price already lies beyond the chosen exit level, the system MUST fill the exit at the candle's actual open price, NOT at the SL/TP level itself. This rule applies to EXITS only; REQ-47 governs entry fills independently.
- **REQ-34.1** (happy): GIVEN a bearish trade whose stop-loss is `1.0970`, and the resolving exit candle opens beyond SL with take-profit untouched that candle, WHEN the exit is resolved, THEN `exit_price` is the actual gap-open price, `gap_filled=True`.

### REQ-35: Risk:reward floor filter
The system MUST exclude, before fill simulation, any candidate whose risk:reward ratio (signed distances, entry to stop-loss vs. entry to take-profit) falls below `BacktestConfig.min_risk_reward` (default `2.0`). A structurally negative ratio (take-profit behind entry) MUST be excluded under this SAME rule.
- **REQ-35.1** (happy): GIVEN a candidate whose computed R:R is `1.4` and `min_risk_reward=2.0`, WHEN the floor filter runs, THEN the candidate is excluded under `rr_floor`.
- **REQ-35.2** (edge, floor not inert): GIVEN a candidate with 14-pip risk and a 20-pip reward (R:R=`1.43`), WHEN the floor filter runs against the `2.0` default, THEN excluded.
- **REQ-35.3** (edge, negative ratio, no separate bucket): GIVEN a candidate whose take-profit sits behind its entry (signed R:R = `-0.5`), WHEN the floor filter runs, THEN excluded under the SAME `rr_floor` bucket as REQ-35.1.

### REQ-36: Kill-zone gating
The system MUST, by default, exclude signals anchored outside the NY Kill Zone (REQ-29's predicate), evaluated against `anchor_index` timestamp. Counted under "outside kill zone" (REQ-40). WHEN `--session` has already narrowed the population, this internal gate MUST auto-disable — `excluded_kill_zone` MUST be `0` by construction. `metrics_summary` MUST additionally state the gate's own state as one of three literal lines: (a) enabled (default, gate active); (b) auto-disabled (because `--session` already narrowed the population); (c) disabled (because `--kill-zone-gated false` was supplied WITHOUT `--session`).
- **REQ-36.1** (grounded, charter-3 [00:13:17]): GIVEN a signal anchored 5:30am NY-local, no `--session` filter applied, WHEN the default gate is applied, THEN excluded.
- **REQ-36.2** (edge): GIVEN `--backtest --session ny-killzone`, WHEN the reconciliation report is generated, THEN `excluded_kill_zone = 0`.
- **REQ-36.3** (edge): GIVEN a signal anchored inside the kill zone whose confirmation lands later outside it, WHEN the default gate is applied, THEN NOT excluded under `kill_zone` — anchor time is the only basis evaluated.
- **REQ-36.4** (edge): GIVEN `--backtest --session ny-killzone`, WHEN `metrics_summary` is written, THEN it includes an explicit line stating the gate auto-disabled for this run.
- **REQ-36.5** (edge): GIVEN `--backtest --kill-zone-gated false` supplied WITHOUT `--session`, WHEN `metrics_summary` is written, THEN it includes the third literal rendering, distinct from both "enabled" and "auto-disabled".

### REQ-37: No-lookahead simulation entry point
The system's fill/SL/TP resolution MUST use ONLY price data that genuinely exists in the candle series at the index being evaluated. Once a candidate is in the population, checking whether price touched its REQ-47 entry price at any index from `retest_index` onward is reading historical price data, not simulating a decision that could not have known the future. The REQ-50 fill-window search MAY begin at `retest_index` for all candidate types uniformly. The SL/TP resolution sweep MUST begin at `fill_index + 1`, never earlier.
- **REQ-37.1** (grounded): GIVEN a CONFIRMED-path candidate whose true confirmation lags `retest_index` by up to 6 candles, WHEN simulated, THEN the REQ-50 fill-window search begins at `retest_index`, not `confirmation_index + 1`.
- **REQ-37.2** (edge): GIVEN an INVALIDATED+retest or PENDING+retest candidate, WHEN simulated, THEN its fill is searched via REQ-50's window starting at `retest_index`, and the SL/TP sweep begins at `fill_index + 1`, never earlier.

### REQ-38: Trade terminal states gain partial-leg disclosure fields
Every simulated trade MUST resolve to EXACTLY one of three terminal states: `win`, `loss`, or `open` (neither SL, TP, nor the partial level touched by series end) — a two-leg trade still resolves to `win` or `loss` based on the SIGN of its `r_multiple` (REQ-69's blended figure when a partial fired, REQ-48's unmodified figure otherwise). An `open` trade MUST have `exit_index=None`, `exit_price=None`, `r_multiple=None`, `ambiguous_bar=False`, `gap_filled=False`. `Trade` additionally exposes four partial-leg disclosure fields: `partial_exit_index: int | None`, `partial_exit_price: float | None`, `partial_r_multiple: float | None`, `partial_gap_filled: bool` — ALL `None`/`False` when no partial fired, including every `open` trade and every single-leg `win`/`loss` trade.
- **REQ-38.1** (edge, open trade): GIVEN a trade whose SL, TP, and partial level are never touched, WHEN simulation ends, THEN `outcome="open"`, all exit fields (including the 4 partial fields) are `None`/`False`, and the trade is excluded from win-rate computation (REQ-39) but still counted as `trades_opened` (REQ-40).
- **REQ-38.2** (happy, blended sign determines outcome): GIVEN a two-leg trade whose blended `r_multiple` (REQ-69) is `+0.25`, WHEN resolved, THEN `outcome="win"` — the same sign rule applies to the blended figure.
- **REQ-38.3** (edge, no-partial fields stay empty): GIVEN a single-leg trade (REQ-68.3's SL-wins-tie case, or `partial_fraction=0.0`), WHEN resolved, THEN all four partial-leg fields are `None`/`False`.

### REQ-40: Population-reconciliation report
The system MUST report, for every `--backtest` run, a `ReconciliationReport` whose `signals_considered` count is measured strictly AFTER the full CLI filter chain has already run. Every signal admitted to `signals_considered` MUST land in EXACTLY ONE of `trades_opened` or seven exclusion buckets — `excluded_no_crt_range`, `excluded_unaligned`, `excluded_never_confirmed`, `excluded_duplicate`, `excluded_kill_zone`, `excluded_rr_floor`, `excluded_never_filled` — evaluated in that fixed precedence order.
- **REQ-40.1** (edge, invariant): GIVEN any `--backtest` run, WHEN the reconciliation report is generated, THEN `trades_opened + sum(all 7 exclusion buckets) == signals_considered`, exactly.
- **REQ-40.2** (grounded, e2e): GIVEN a session filter narrows the population, WHEN `--backtest` runs, THEN `signals_considered` reflects the post-CLI-filter count, not the raw detected count.
- **REQ-40.3** (edge, precedence): GIVEN a signal that is BOTH unaligned AND anchored outside the kill zone, WHEN reconciled, THEN it lands in `excluded_unaligned`, never `excluded_kill_zone`.
- **REQ-40.4** (edge): GIVEN a `PENDING` signal whose `retest_index` is set, WHEN the candidate population is built, THEN it is admitted as a REQ-30.6 candidate — never silently dropped — and resolves through stages 4-7, landing in `trades_opened` or one of the stage 4-7 buckets.

### REQ-46: Signal deduplication
Before simulation, the system MUST collapse candidates sharing an identical `(anchor_index, direction, entry_price, entry_type)` tuple into ONE trade candidate — the one with the LOWEST `origin_index` survives; the rest are counted under `excluded_duplicate` (REQ-40, stage 4). Deduplication MUST run BEFORE the kill-zone and R:R-floor cuts.
- **REQ-46.1** (happy): GIVEN 3 candidates sharing an identical identity tuple, WHEN deduplicated, THEN exactly 1 trade candidate survives (lowest `origin_index`) and 2 are counted under `excluded_duplicate`.
- **REQ-46.2** (edge): GIVEN two candidates sharing the same `anchor_index`/`entry_price` but with DIFFERENT `entry_type`, WHEN deduplicated, THEN both survive as distinct candidates.

### REQ-47: Entry price definition
The system MUST compute a candidate's entry price independently of `Model1Signal.entry_price`/`detections.csv`: for `entry_type="body"`, `anchor.open`; for `entry_type="wick"`, the retest-side body-zone boundary (`max(anchor.open, anchor.close)` bullish, `min(...)` bearish) — never `protected_extreme`. For a non-degenerate anchor candle, entry price MUST NOT equal `protected_extreme`. A doji anchor is the one documented exception, but `risk >= sl_buffer_price > 0` MUST still hold. WHEN the fill candle's open already lies beyond the entry price, the system MUST fill at the entry price itself — never at the candle's open.
- **REQ-47.1** (happy, body): GIVEN a body-type signal, WHEN entry price is computed, THEN it equals `anchor.open`.
- **REQ-47.2** (happy, wick — corrected 2026-11-10b): GIVEN a wick-type signal whose anchor spans body `[1.0998, 1.1002]` and full range `[1.0990, 1.1005]` (bullish), WHEN entry price is computed, THEN it equals `1.1005` — the anchor's own wick extreme (`anchor.high`), never `1.1002` (the body boundary this formula previously, incorrectly, returned) and never `1.0990` (`protected_extreme`, the swept side). Two real executed Model-1 trades (GBPUSD buy, EURUSD sell, both 2026-11-10) confirmed entry sits at the anchor's own opposite-side wick tip.
- **REQ-47.3** (edge, non-degeneracy, property-tested): GIVEN a non-degenerate wick anchor (`anchor.high != anchor.low`), WHEN entry price and `protected_extreme` are compared, THEN they are never equal — automatically true for any anchor with a real range, since entry and `protected_extreme` now sit on opposite sides of the candle by construction.
- **REQ-47.4** (edge, zero-range carve-out — corrected 2026-11-10b): GIVEN a zero-range anchor (`anchor.high == anchor.low`, not merely `open == close`), WHEN entry price is computed, THEN equality between entry price and `protected_extreme` is permitted, but risk still holds because ATR's `true_range` also measures the gap against the PREVIOUS candle's close (`core/atr.py`), never collapsing to zero from this one degenerate candle alone.
- **REQ-47.5** (edge, entry-side gap): GIVEN a fill candle that opens above a bullish candidate's entry price, WHEN the fill is resolved, THEN the trade fills at the entry price itself.

### REQ-48: Trading cost
`BacktestConfig` MUST expose `trading_cost_price: float` (default `0.0`, TOTAL per-trade cost covering spread+slippage+commission). The system MUST net this cost out of every closed trade's `r_multiple` exactly once, at closure: `r_multiple = (signed_move - trading_cost_price) / risk`. `metrics_summary` MUST always disclose the configured trading cost.
- **REQ-48.1** (happy): GIVEN `trading_cost_price=0.00007`, risk=`0.0014`, a gross R of `3.0`, WHEN net R is computed, THEN it equals `2.95`.
- **REQ-48.2** (edge, default neutrality): GIVEN the default `trading_cost_price=0.0`, WHEN metrics are computed, THEN they are bit-identical to a cost-free computation.
- **REQ-48.3** (edge, disclosure): GIVEN any `--backtest` run, WHEN `metrics_summary` is written, THEN it states either "trading cost: 0.0 (frictionless)" or "trading cost: {price} per trade".

### REQ-50: Entry-fill simulation window
`BacktestConfig` MUST expose `max_fill_wait` (positive integer, candles) — the window after `retest_index` within which a candidate's REQ-47 entry price MUST be touched for the trade to open, applying uniformly to ALL candidate types. The system MUST check the inclusive window `[retest_index, retest_index + max_fill_wait]`. The first touching index becomes `fill_index`. A candidate never touched within the window MUST be excluded under `excluded_never_filled` and MUST NOT be counted as win/loss/open.
- **REQ-50.1** (happy, wick-type): GIVEN a wick-type candidate whose retest candle itself touches the entry price, WHEN fill is simulated, THEN `fill_index = retest_index`.
- **REQ-50.2** (happy, body-type): GIVEN a body-type candidate whose entry touches 3 candles after `retest_index`, `max_fill_wait=10`, WHEN fill is simulated, THEN `fill_index` is that later index.
- **REQ-50.3** (edge, boundary): GIVEN `retest_index=95`, `max_fill_wait=10`, WHEN the fill window is evaluated, THEN candle index 106 is NOT considered — the window closes at index 105 inclusive.
- **REQ-50.4** (edge): GIVEN an INVALIDATED+retest or PENDING+retest candidate whose entry is never touched within its fill window, WHEN fill is simulated, THEN the candidate IS excluded under `excluded_never_filled` — NOT counted as a loss.

### REQ-52: Kill-zone gate relocation and dead-parameter removal preserve existing behavior
The system SHALL preserve `in_ny_kill_zone`'s existing behavior when relocated from `cli.py` into `core/kill_zone.py`: for any given input, the relocated function MUST produce the same output as the original `cli.py` implementation. The system SHALL remove the dead `types` parameter from `_detect_all` with no change to its observable output for any input.
- **REQ-52.1** (happy, relocation preserves behavior): GIVEN a timestamp classified by the original `in_ny_kill_zone`, WHEN evaluated via the relocated `core/kill_zone.py` version, THEN the classification is identical.
- **REQ-52.2** (edge, dead-param removal is a no-op): GIVEN any valid `_detect_all` invocation, WHEN its returned detections are compared before and after the unused `types` parameter is removed, THEN the result is identical.

### REQ-68: Two-stage (partial) exit detection and resolution
For every trade candidate reaching the exit-resolution stage (REQ-37), the system MUST additionally compute `partial_price = (entry_price + take_profit) / 2` — the midpoint between the trade's OWN entry price and its OWN take-profit target (REQ-32/44), not any HTF-range-level derivation. Because `entry_price` and `take_profit` are already correctly ordered for every candidate reaching this stage (REQ-35's R:R floor requires a positive-reward configuration), this formula guarantees `entry_price` strictly between `stop_loss` and `partial_price`, and `partial_price` strictly between `entry_price` and `take_profit` (direction-adjusted) BY CONSTRUCTION — REQ-70's ordering invariant holds structurally rather than incidentally. Starting the sweep at `fill_index + 1` (unchanged), the system searches for the first index touching `partial_price` alongside the existing SL and TP searches. WHEN the stop-loss level would resolve at or before the partial level (SL wins ties, extending REQ-33's existing pessimistic precedent to this third level), the trade resolves as a SINGLE-LEG outcome exactly as it did before this feature — no partial leg is recorded. OTHERWISE (the partial level resolves strictly before the stop-loss), leg 1 closes at `partial_price` (or the gap-open price per REQ-34's existing rule, applied identically to this level) at that index, and a second leg resolves the SAME, UNCHANGED original stop-loss and take-profit — never moved or re-based — starting at the partial's resolving index + 1, using REQ-33's existing SL-vs-TP pessimistic tie-break unmodified for leg 2's own resolution. `BacktestConfig.partial_fraction` (REQ-51) sets the position-size fraction closing at leg 1; `partial_fraction=0.0` MUST make leg 1 never eligible to fire, collapsing every trade to the exact single-leg resolution this codebase produced before this feature.
- **REQ-68.1** (happy, two-leg win-then-win): GIVEN a candidate whose partial level resolves at index 50 (before SL) and whose remainder then resolves at the original take-profit at index 80, WHEN resolved, THEN leg 1 closes at `partial_price` (index 50), leg 2 closes at `take_profit` (index 80), and both leg exits are recorded.
- **REQ-68.2** (happy, two-leg win-then-loss): GIVEN the same partial firing at index 50, but the remainder then resolves at the ORIGINAL stop-loss at index 90 (not moved), WHEN resolved, THEN leg 2 closes at `stop_loss` — the stop was never re-based after the partial fired.
- **REQ-68.3** (edge, SL wins the tie — no partial): GIVEN a candle in which stop-loss and the partial level would resolve at the same index, or stop-loss resolves at an earlier index than the partial, WHEN resolved, THEN the trade resolves as a single-leg loss at the stop-loss price — no partial leg is recorded, matching this codebase's exact pre-feature behavior for that candidate.
- **REQ-68.4** (edge, gap-through partial): GIVEN the resolving candle's open price already lies beyond `partial_price`, WHEN leg 1 is resolved, THEN it fills at the candle's actual open price, not at `partial_price` itself (REQ-34, applied identically).
- **REQ-68.5** (edge, `partial_fraction=0.0` regression): GIVEN `BacktestConfig.partial_fraction=0.0`, WHEN any candidate is resolved, THEN the resulting `Trade` (outcome, exit_index, exit_price, r_multiple) is byte-identical to resolving the SAME candidate with this feature entirely absent.
- **REQ-68.6** (edge, never touched): GIVEN neither SL, TP, nor the partial level is ever touched by series end, WHEN resolved, THEN the trade remains `outcome="open"` with no partial leg recorded (mirrors REQ-38.1).

### REQ-69: Blended R-multiple and proportional cost allocation
WHEN a trade resolves with a partial leg (REQ-68), the system MUST compute the trade's `r_multiple` as `partial_fraction * R_leg1 + (1 - partial_fraction) * R_leg2`, where `R_leg1` and `R_leg2` are each computed via the existing `net_r_multiple` formula (REQ-48), BOTH measured against the trade's ORIGINAL, unchanged `entry_price` and `stop_loss` — leg 2's risk is never re-based to a moved or breakeven stop, consistent with trailing-stops/breakeven-after-partial being out of scope. `trading_cost_price` (REQ-48) MUST be allocated proportionally across the two legs — `partial_fraction * trading_cost_price` netted from leg 1, the remainder from leg 2 — so the TOTAL cost netted across both legs equals exactly `trading_cost_price`, never double-counted and never dropped.
- **REQ-69.1** (happy): GIVEN `partial_fraction=0.5`, `R_leg1=+1.5` (partial always profitable when it fires, since it only fires after price has moved favorably), `R_leg2=-1.0`, WHEN blended, THEN `r_multiple = 0.5*1.5 + 0.5*(-1.0) = 0.25`.
- **REQ-69.2** (edge, cost-default neutrality): GIVEN the default `trading_cost_price=0.0`, WHEN a two-leg trade's blended `r_multiple` is computed, THEN it is bit-identical to a zero-cost computation, regardless of `partial_fraction`.
- **REQ-69.3** (edge, single-leg trade unaffected): GIVEN a trade that resolves single-leg (REQ-68.3, SL wins the tie, or no partial ever configured), WHEN `r_multiple` is computed, THEN it uses the existing REQ-48 formula EXACTLY as before this feature — no blending, full `trading_cost_price` applied once.

### REQ-70: Partial-price ordering guarantee
For every trade candidate that survives the R:R floor filter (REQ-35), the system MUST guarantee `partial_price` (REQ-68) lies strictly between `entry_price` and `take_profit` on the favorable side of the trade, and strictly on the favorable side of `stop_loss` — i.e., a partial exit is never priced worse than holding to the stop, and never behind entry. This MUST be verified by an explicit property test run against the real 3-instrument corpus (EURUSDm, GBPUSDm, DXYm), not assumed. If the property is ever falsified for a real candidate, the test MUST fail explicitly, naming the offending candidate — the resolution logic MUST NOT silently emit a nonsensical partial.
- **REQ-70.1** (property test): GIVEN every real trade candidate surviving REQ-35's floor across the 3-instrument corpus, WHEN direction-adjusted ordering is checked, THEN `stop_loss` is strictly worse than `entry_price`, which is strictly worse than `partial_price`, which is strictly worse than `take_profit`, for every single candidate.
- **REQ-70.2** (edge, loud failure): GIVEN a hypothetical candidate constructed to violate this ordering, WHEN the property test runs against it, THEN it fails explicitly identifying that candidate — never silently excluded or skipped.

## Domain: backtest-metrics

### REQ-39: Win rate
The system MUST compute win rate as `wins / (wins + losses)` over CLOSED trades only (`open` trades excluded from both numerator and denominator). WHEN zero trades have closed, win rate MUST be `None`/"n/a" — never `0.0`.
- **REQ-39.1** (edge, no substitution): GIVEN zero closed trades, WHEN win rate is computed, THEN `win_rate` is `None`/"n/a", never `0.0`.
- **REQ-39.2** (happy): GIVEN 3 wins and 2 losses (5 closed trades), WHEN win rate is computed, THEN it equals `0.6`.

### REQ-49: Aggregate profitability disclosure gains partial-exit count
`metrics_summary` MUST report an aggregate profitability figure alongside per-trade metrics: the AVERAGE `r_multiple` across all CLOSED trades, AND the TOTAL R (sum) — both `None`/"n/a" when zero trades have closed. Both figures MUST be accompanied by an explicit note that they assume unlimited capital with no cap on concurrently open positions. `metrics_summary` MUST also disclose the count of trades still `open` at series end as its own explicit line, and the count of trades whose partial leg fired (REQ-68) as its own explicit line, distinct from the open-trades count.
- **REQ-49.1** (happy): GIVEN 3 closed trades with r_multiples `+2, +2, -1`, WHEN aggregate profitability is computed, THEN `average_r_multiple=1.0` and `total_r=3.0`.
- **REQ-49.2** (edge, no substitution): GIVEN zero closed trades, WHEN aggregate profitability is computed, THEN both figures are "n/a" — never `0.0`.
- **REQ-49.3** (edge, disclosure wording): GIVEN 5 closed trades averaging `1.0`, WHEN `metrics_summary` is written, THEN it states the average "over 5 closed trades" plus the unlimited-capital note.
- **REQ-49.4** (edge): GIVEN a run in which 7 trades remain `open` at series end, WHEN `metrics_summary` is written, THEN it includes an explicit "open trades: 7" line.
- **REQ-49.5** (edge, partial-exit disclosure): GIVEN a run in which 4 trades fired a partial exit, WHEN `metrics_summary` is written, THEN it includes an explicit "partial exits: 4" line.

## Domain: signal-traceability

### REQ-41: Signal/anchor identifier
The system MUST assign every `Model1Signal` a stable `signal_id: str`, computed as `f"{origin_index}-{anchor_index}-{direction}-{confirmation_type}-{entry_type}"`, where `origin_index` is the originating `CRTRange.start_index` or `FVG.start_index`. Injectivity is INHERITED from `detect_crt_ranges`/`detect_fvgs` emitting at most one structure per `start_index` — not independently enforced (accepted risk, followup registered for hardening). WHEN `--backtest` is passed, `detections.csv` MUST gain a trailing `signal_id` column; non-model1 rows write `""`. WHEN `--backtest` is NOT passed, `detections.csv` MUST NOT include this column.
- **REQ-41.1** (happy): GIVEN two signals sharing the same `anchor_index` but originating from different `CRTRange`s, WHEN `signal_id` is computed, THEN the two ids are distinct.
- **REQ-41.2** (edge): GIVEN an `fvg_fill`-confirmed signal, WHEN `signal_id` is computed, THEN it is stable and does not collide with a `purge_engulf`-confirmed signal at the same `origin_index`.
- **REQ-41.3** (edge): GIVEN a detector run WITHOUT `--backtest`, WHEN `detections.csv` is written, THEN it has no `signal_id` column and matches the 8-column header exactly (the 7 prior columns plus `key_level_source`, REQ-24).

### REQ-42: Trade-to-detection traceability
Every row in `trades.csv` MUST carry the `signal_id` (REQ-41) of the `Model1Signal` it originated from, joining to EXACTLY ONE row in `detections.csv`. Because the backtest computes its own entry price independently of `detections.csv`'s `entry_price` (REQ-47), a joined pair's `entry_price` values MAY legitimately differ for wick-type signals — `metrics_summary` MUST disclose this as an explicit note.
- **REQ-42.1** (happy): GIVEN any `trades.csv` row, WHEN its `signal_id` is looked up in `detections.csv`, THEN exactly one row matches.
- **REQ-42.2** (edge, disclosure): GIVEN a joined pair of a wick-type trade row and its detection row with differing `entry_price` values, WHEN `metrics_summary` is written, THEN it includes a note that the two are independently computed and may differ for wick-type signals.

## Domain: chart-overlay-viz

### REQ-23: Chart image overlay
6 distinct encodings (Swing=triangle, FVG=shaded rect, CRT range=bracket lines without per-instance text labels, MSS=small triangle marker at the broken swing's price level, Model-1=arrow+entry line, alignment=border color). Zero detections → still emits a valid chart, exit 0.
- **REQ-23.1**: multi-week series, all 6 types — each visually distinct.

### REQ-24: Companion CSV table
Columns `timestamp,type,direction,price_high,price_low,status,aligned,key_level_source` (8 columns; `aligned` and `key_level_source` populated for Model-1 rows only). `key_level_source` is populated ONLY for Model-1 rows tagged `aligned` with a Key Level recorded, carrying that Key Level's `kind` (`fvg` or `ict_order_block`); empty for every other row. Zero detections → header-only CSV, exit 0.
- **REQ-24.1**: scannable for e.g. "any PENDING Model-1" without re-parsing the image.
- **REQ-24.2** (happy): GIVEN an `aligned` Model-1 signal credited to an ICTOrderBlock-sourced Key Level, WHEN `detections.csv` is written, THEN its `key_level_source` cell is exactly `"ict_order_block"`.
- **REQ-24.3** (edge): GIVEN a non-Model-1 row (swing/fvg/crt_range/mss), WHEN `detections.csv` is written, THEN its `key_level_source` cell is empty.

## Domain: ict-order-block-detection

### REQ-61: Detect ICT Order Block (immediate-engulfing rule)
The system MUST detect an `ICTOrderBlock` for every pair of consecutive candles `(i, i+1)` in the source series, checked unconditionally in BOTH directions — no external bias input, no structure-break/MSS dependency:
- **Bullish Order Block**: candle `i` closes bearish (`i.close < i.open`) AND candle `i+1` fully engulfs `i`'s range (`i+1.high >= i.high` AND `i+1.low <= i.low`) AND candle `i+1` closes bullish (`i+1.close > i+1.open`).
- **Bearish Order Block**: mirror — `i` closes bullish, `i+1` fully engulfs `i`, `i+1` closes bearish.
- The zone is candle `i`'s own BODY — `top = max(i.open, i.close)`, `bottom = min(i.open, i.close)`.
- A pair that does not satisfy all three conditions for either direction yields no Order Block for that pair — never an error.
- **REQ-61.1** (happy, bullish): GIVEN candle `i` closes bearish and candle `i+1` fully engulfs `i`'s range and closes bullish, WHEN detected, THEN a bullish `ICTOrderBlock` is emitted anchored at `i`, zone = candle `i`'s body, confirmed at `i+1`.
- **REQ-61.2** (happy, bearish): mirror of REQ-61.1 — candle `i` closes bullish, candle `i+1` fully engulfs `i` and closes bearish.
- **REQ-61.3** (edge, partial engulf — no OB): GIVEN candle `i` closes bearish and candle `i+1` closes bullish but `i+1` does NOT fully engulf `i`'s range (e.g. `i+1.high < i.high`), WHEN evaluated, THEN no `ICTOrderBlock` is emitted for that pair.
- **REQ-61.4** (edge, wrong confirmation close — no OB): GIVEN candle `i` closes bearish and candle `i+1` fully engulfs `i`'s range but `i+1` itself closes bearish (not bullish), WHEN evaluated, THEN no `ICTOrderBlock` is emitted for that pair.
- **REQ-61.5** (edge, doji excluded): GIVEN candle `i` has `open == close` (doji), WHEN evaluated as a potential anchor, THEN it never qualifies for either direction — the strict `close < open` / `close > open` inequalities a doji can satisfy neither.
- **REQ-61.6** (edge, adjacent pairs are independent): GIVEN candle `B` is simultaneously the confirmation of a bullish Order Block anchored at `A` (pair `A,B`) AND itself closes bullish so that `B` also satisfies the bearish-OB anchor condition for the adjacent pair `(B, C)`, and `C` fully engulfs `B` and closes bearish, WHEN detected, THEN BOTH Order Blocks are emitted independently — no exclusivity constraint between overlapping matches.

### REQ-62: Invalidation by first touch
The system MUST mark an `ICTOrderBlock` `invalidated` at the FIRST candle strictly after its confirmation candle (`i+1`) — i.e. starting the scan at `i+2` — whose range overlaps the zone AT ALL: `candle.high >= bottom AND candle.low <= top`, for either direction. This is a touch test (wick or body, any overlap), not a close-through test. An Order Block never invalidated by series end remains `status="open"`, `invalidation_index=None`.
- **REQ-62.1** (happy): GIVEN a bullish Order Block with `bottom=1.0950, top=1.0980`, confirmed at `i+1`, and the candle at index `i+2` has `low=1.0955` (inside the zone), WHEN evaluated, THEN `status="invalidated"` at index `i+2`.
- **REQ-62.2** (edge, wick-only touch invalidates): GIVEN a later candle's wick merely dips to the zone boundary while its CLOSE remains entirely outside the zone, WHEN evaluated, THEN the Order Block IS invalidated at that candle — a mere touch mitigates it.
- **REQ-62.3** (edge, boundary-inclusive): GIVEN a later candle's `high` exactly equals `bottom` (or `low` exactly equals `top`), WHEN evaluated, THEN it counts as an overlap and invalidates.
- **REQ-62.4** (edge, confirmation candle excluded from the scan): GIVEN the confirmation candle `i+1` — which by definition already overlaps the zone, since full engulfment implies `i+1.high >= i.high` and `i+1.low <= i.low` — WHEN evaluated, THEN it is NEVER treated as the invalidating candle; the invalidation scan begins strictly at `i+2`, never at `i+1`.
- **REQ-62.5** (edge, never invalidated): GIVEN no candle from `i+2` onward ever overlaps the zone, WHEN evaluated at series end, THEN `status="open"`, `invalidation_index=None`.

### REQ-63: Registration as a Key Level source (Daily-tier source, H4-native invalidation, most-recent tie-break)
`core.key_level.KeyLevel.kind` includes `"ict_order_block"` alongside `"fvg"`. The system MUST expose `to_key_levels(blocks: list[ICTOrderBlock]) -> list[KeyLevel]` producing, for every `ICTOrderBlock`, a `KeyLevel` with `kind="ict_order_block"`, `top`/`bottom` = the Order Block's own zone, `origin_index` = the CONFIRMATION candle's index (`i+1`), and `expiry_index` = `invalidation_index` when invalidated, absent when open.

`detect_ict_order_blocks` runs against the Daily series, not the HTF (H4) series — Order Block Key Levels are Daily-tier, matching the 3-tier hierarchy (Daily Key Level → H4 CRT signal/purge → M15 execution). `origin_index` is an index into the Daily series, reindexed to H4-index-space (the confirming day's CLOSE).

**Invalidation granularity**: for a Daily-sourced Order Block, whether and when it becomes invalidated is determined by scanning the H4 series candle-by-candle — starting at the reindexed `origin_index` (inclusive) — for the first H4 candle whose range overlaps the zone `[bottom, top]`, NOT by asking whether some Daily candle's full-day range touched it. The Order Block's own Daily-native `invalidation_index`/`status` (from `detect_ict_order_blocks`'s generic same-series scan) are NOT used for the Daily-tier flow — they are computed but discarded, replaced entirely by the H4-native scan's result.

**Confluence matching**: `alignment/htf_ltf.py`'s `_key_level_credit_map` selects the MOST RECENT qualifying Key Level (by `origin_index`) among candidates for a given purge, not the oldest. A Daily Key Level qualifies for an H4 purge when the purge candle's own wick extreme (`_purge_wick_extremes`) falls inside the Key Level's zone `[bottom, top]` inclusive of both edges, with NO tolerance — exact overlap only.

- **REQ-63.1** (happy, origin is the confirmation candle, not the anchor): GIVEN a bullish `ICTOrderBlock` anchored at Daily candle `i=13`, confirmed at candle `i+1=14`, WHEN presented as a `KeyLevel`, THEN `origin_index=14`, not `13`.
- **REQ-63.2** (alternate, expiry is H4-native): GIVEN a Daily-sourced Order Block whose zone is first touched by the H4 candle at H4 index `102` (not by asking which Daily candle touched it), WHEN the Key Level is credited, THEN `expiry_index=102`, an H4 index, derived from the H4-native scan (REQ-63.7).
- **REQ-63.3** (structural, regression): GIVEN `alignment/htf_ltf.py`'s own import statements, WHEN inspected, THEN they import only `core.key_level`.
- **REQ-63.4** (most-recent tie-break): GIVEN two Daily Key Levels both qualify for the same H4 purge (both overlap the purge candle's wick extreme), WHEN credited, THEN the one with the GREATER `origin_index` (more recent) is selected, not the lesser.
- **REQ-63.5** (Daily-tier source): GIVEN a Daily series is provided (REQ-67), WHEN Order Blocks are detected for Key Level registration, THEN they are computed from the Daily series' own candles — never from the H4 series.
- **REQ-63.6** (exact overlap): GIVEN a purge candle's wick extreme lies outside a Daily Key Level's zone by any margin, however small, WHEN credited, THEN NO confluence is recorded for that Key Level — no tolerance is applied, regardless of how close the miss.
- **REQ-63.7** (H4-native invalidation scan): GIVEN a Daily-sourced Order Block confirmed on Daily candle `D`, reindexed to H4 origin index `X`, WHEN checking for invalidation, THEN the system scans H4 candles starting at index `X` (inclusive) and marks the Order Block invalidated at the FIRST H4 candle whose range overlaps `[bottom, top]` — never at a Daily candle, and never by translating the Daily-native `invalidation_index`. If no H4 candle ever overlaps, the Order Block has no `expiry_index` (open indefinitely, same as an un-invalidated H4-native Order Block).

### REQ-64: No-lookahead (ICT Order Block)
`detect_ict_order_blocks(series.up_to(n))` MUST match the full-series output for every `ICTOrderBlock` whose confirmation candle (`i+1`) has index `< n` — a fixed `k=1` boundary-equality property. Invalidation status for an already-knowable Order Block MUST be re-derivable from any prefix that includes the invalidating candle, and MUST remain `open` in any shorter prefix.
- **REQ-64.1** (property test): prefix-consistency at fixed `k=1`, mirroring the existing per-detector property tests in `tests/property/test_no_lookahead.py`.

### REQ-66: ICTOrderBlock's own discrimination number (real-data comparison)
The system's real-data validation runs on the SAME 3 instruments (EURUSDm, GBPUSDm, DXYm) as the FVG confluence gate, WITH `--daily-csv`/`--daily-symbol` provided (REQ-67), gating confluence SOLELY on ICTOrderBlock-sourced Key Levels detected on the Daily series with H4-native invalidation (REQ-63.7), and the run's evidence records, per instrument: the count of `aligned`, non-`fvg_fill` Model-1 signals; how many were credited an ICTOrderBlock Key Level; how many were not; the resulting `excluded_no_key_level` count; and `trades_opened`. This REQ does NOT gate pass/fail on any specific threshold — the number itself is the deliverable.
- **REQ-66.1** (happy): GIVEN the real EURUSDm H4/M15/Daily triple with `--backtest`, WHEN run gating on ICTOrderBlock alone, THEN the evidence records all counts above.
- **REQ-66.2** (edge, no threshold gate): GIVEN any resulting discrimination percentage, WHEN evidence is recorded, THEN the run does NOT fail or halt based on that percentage's value alone.
- **REQ-66.3** (edge, full coverage): GIVEN all 3 instruments run, WHEN evidence is compiled, THEN a complete count set exists for each of EURUSDm, GBPUSDm, and DXYm — not a subset.

### REQ-67: Daily series CLI input
The system MUST accept an optional Daily-timeframe series input via `--daily-csv`/`--daily-symbol`, mirroring the existing optional `--htf-csv`/`--htf-symbol` pair-mode precedent: both flags MUST be provided together (error if only one is given), and omitting both is valid — the run proceeds without Daily-tier ICTOrderBlock Key Levels rather than failing.
- **REQ-67.1** (happy): GIVEN `--daily-csv` and `--daily-symbol` are both provided, WHEN the detector runs, THEN Order Block Key Levels are computed from the Daily series per REQ-63.
- **REQ-67.2** (edge, omitted): GIVEN both `--daily-csv` and `--daily-symbol` are omitted, WHEN the detector runs, THEN no ICTOrderBlock Key Levels are registered (FVG-only confluence) and the run does NOT fail.
- **REQ-67.3** (edge, partial pair rejected): GIVEN only ONE of `--daily-csv`/`--daily-symbol` is provided, WHEN the CLI parses arguments, THEN it exits with an error before any detection runs — mirroring `--htf-csv`/`--htf-symbol`'s existing validation.

---

## Sensitive Areas Coverage
None.
