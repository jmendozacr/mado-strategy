# Specs: CRT/ICT Pattern Detector

**Spec version**: V4 | **Status**: signed | **Domain**: detector

**Scope note**: Covers 5 of 7 originally-named setup types (Swing, FVG, CRT range, MSS, Model-1). Standalone Order Block + Breaker Block deliberately deferred (pending change `crt-detector-order-block-breaker`), ratified at the steward foresight gate.

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

## Domain: chart-overlay-viz

### REQ-23: Chart image overlay
6 distinct encodings (Swing=triangle, FVG=shaded rect, CRT range=bracket lines without per-instance text labels, MSS=small triangle marker at the broken swing's price level, Model-1=arrow+entry line, alignment=border color). Zero detections → still emits a valid chart, exit 0.
- **REQ-23.1**: multi-week series, all 6 types — each visually distinct.

### REQ-24: Companion CSV table
Columns `timestamp,type,direction,price_high,price_low,status` (+`aligned` for Model-1 rows). Zero detections → header-only CSV, exit 0.
- **REQ-24.1**: scannable for e.g. "any PENDING Model-1" without re-parsing the image.

---

## Sensitive Areas Coverage
None.
