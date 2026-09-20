# Spec: Forex Broker-Clock Policy for the 1 AM CRT

**Change**: `crt-detector-forex-broker-clock-policy`
**Spec version**: V1 | **Status**: signed
**Triage**: M
**Source docs**: `docs/charter-8.md`, `docs/charter-9.md`
**REQ range**: REQ-70 – REQ-75 (gap from REQ-67 is intentional — buffer for in-flight changes)

---

## Domain: broker-clock-classification

### REQ-70: Raw broker-clock H4 candle classification

The system MUST classify H4 candle timestamps by their raw broker-clock hour with no UTC conversion, no DST-aware tz arithmetic, and no `zoneinfo` usage. Two classifications are defined for this change:

- `london_crt`: `timestamp.hour == 1` — the H4 candle running 01:00–05:00 broker clock [charter-8, 00:01:41]
- `asia_range`: `timestamp.hour == 21` — the H4 candle running 21:00–01:00 broker clock [charter-8, 00:03:16]

Classification is a pure predicate on `datetime.hour`. Any H4 candle whose hour is not 1 or 21 is neither; no error is raised.

- **REQ-70.1** (happy, london_crt): GIVEN an H4 candle with `timestamp.hour == 1`, WHEN classified, THEN `is_london_crt_h4` returns `True`.
- **REQ-70.2** (happy, asia_range): GIVEN an H4 candle with `timestamp.hour == 21`, WHEN classified, THEN `is_asia_range_h4` returns `True`.
- **REQ-70.3** (edge, no conversion): GIVEN a `datetime` with no `tzinfo`, WHEN `is_london_crt_h4` is called, THEN it reads `.hour` directly and performs no `astimezone` or `replace(tzinfo=...)` call.
- **REQ-70.4** (edge, non-matching hour): GIVEN an H4 candle with `timestamp.hour == 5`, WHEN classified, THEN both `is_london_crt_h4` and `is_asia_range_h4` return `False` — no error.

---

### REQ-71: Asia reference range pairing

For a `london_crt` candle timestamp `T` (hour == 1), the corresponding Asia reference range candle MUST open exactly 4 broker-clock hours earlier, at `T - timedelta(hours=4)` (hour == 21, previous calendar day). This arithmetic is the ONLY pairing mechanism — no day-of-week logic, no calendar-aware lookup [charter-8, 00:03:16].

- **REQ-71.1** (happy): GIVEN a `london_crt` candle with `timestamp = 2026-09-16 01:00:00`, WHEN the Asia reference timestamp is derived, THEN the result is `2026-09-15 21:00:00`.
- **REQ-71.2** (happy, found in series): GIVEN an H4 series that contains a candle at `2026-09-15 21:00:00`, WHEN `find_asia_range_index` is called for the `london_crt` candle at `2026-09-16 01:00:00`, THEN it returns the index of that candle.
- **REQ-71.3** (edge, absent): GIVEN an H4 series whose earliest candle is at `2026-09-16 01:00:00`, WHEN `find_asia_range_index` is called for that candle, THEN it returns `None` — no error, no default, no nearest-match fallback.

---

## Domain: execution-window-filter

### REQ-72: M15 execution window classification

An M15 candle timestamp MUST be classified as within the strict execution window when `2 <= timestamp.hour < 4` (broker clock) [charter-8, 00:12:13, 00:12:52]. The sub-window `3 <= timestamp.hour < 4` (03:00–04:00) is the highest-probability period and MUST be flagged separately [charter-8, 00:12:13; charter-9, 00:05:18].

The windows 01:00–02:00 and 04:00–05:00 are explicitly deferred [charter-8, 00:12:25] — candles in those hours MUST NOT be classified as in-scope by this version of the spec.

- **REQ-72.1** (happy, 02:00): GIVEN an M15 candle at `timestamp.hour == 2`, WHEN `in_execution_window` is called, THEN `True`.
- **REQ-72.2** (happy, 02:15): GIVEN an M15 candle at `timestamp.hour == 2`, WHEN `in_execution_window` is called, THEN `True` (the 02:15 candle has `hour == 2`).
- **REQ-72.3** (boundary, 04:00 excluded): GIVEN an M15 candle at `timestamp.hour == 4`, WHEN `in_execution_window` is called, THEN `False`.
- **REQ-72.4** (boundary, 01:59 excluded): GIVEN an M15 candle at `timestamp.hour == 1`, WHEN `in_execution_window` is called, THEN `False`.
- **REQ-72.5** (priority sub-window, 03:15): GIVEN an M15 candle at `timestamp.hour == 3`, WHEN `in_priority_subwindow` is called, THEN `True`.
- **REQ-72.6** (priority sub-window, 02:45 excluded): GIVEN an M15 candle at `timestamp.hour == 2`, WHEN `in_priority_subwindow` is called, THEN `False`.

---

## Domain: forex-crt-signal

### REQ-73: ForexCRTSignal qualification

An `AlignedSignal` MUST qualify as a `ForexCRTSignal` if and only if ALL of the following hold:

1. `aligned_signal.aligned == "aligned"` (an unaligned or insufficient signal is never a Forex CRT signal)
2. The H4 candle that encloses the M15 anchor timestamp — that is, the last H4 candle whose own timestamp is ≤ the M15 anchor timestamp — opens at 01:00 broker clock (`is_london_crt_h4`). This is derived via `bisect_right(htf_timestamps, m15_anchor_ts) - 1` and is NOT `AlignedSignal.htf_context.start_index`, which is the origin of the generic sliding CRT range, not the H4 session candle [charter-8, 00:01:41].
3. The M15 anchor candle's timestamp satisfies `in_execution_window` (`2 <= hour < 4`) [charter-8, 00:12:52]

A `ForexCRTSignal` carries:
- the original `AlignedSignal` unchanged
- a `ForexCRTContext` (linking `enclosing_h4_index` — the bisect-derived H4 candle index — `asia_range_h4_index | None`, Asia range OHLC bounds | None)
- `priority: bool` — `True` when the M15 anchor is also in the priority sub-window (`hour == 3`)

- **REQ-73.1** (happy): GIVEN an H4 series where the candle enclosing the M15 anchor (last H4 timestamp ≤ M15 anchor at 02:30) opens at 01:00, WHEN `detect_forex_crt_signals` is called, THEN a `ForexCRTSignal` is emitted with `priority=False`.
- **REQ-73.2** (happy, priority): GIVEN an H4 series where the enclosing H4 candle opens at 01:00 and the M15 anchor is at 03:00, WHEN `detect_forex_crt_signals` is called, THEN a `ForexCRTSignal` is emitted with `priority=True`.
- **REQ-73.3** (excluded, wrong H4 hour): GIVEN an H4 series where the candle enclosing the M15 anchor opens at 05:00 (not 01:00), even with an M15 anchor in the execution window, WHEN `detect_forex_crt_signals` is called, THEN no `ForexCRTSignal` is emitted.
- **REQ-73.4** (excluded, outside execution window): GIVEN an H4 series where the enclosing H4 candle opens at 01:00 but the M15 anchor is at 06:00, WHEN `detect_forex_crt_signals` is called, THEN no `ForexCRTSignal` is emitted.
- **REQ-73.5** (excluded, unaligned): GIVEN an `AlignedSignal` with `aligned="unaligned"`, WHEN `detect_forex_crt_signals` is called, THEN no `ForexCRTSignal` is emitted for it.
- **REQ-73.6** (Asia range absent): GIVEN a qualifying `AlignedSignal` whose H4 series has no 21:00 candle before the enclosing H4 candle at 01:00, WHEN `detect_forex_crt_signals` is called, THEN a `ForexCRTSignal` IS emitted with `ForexCRTContext.asia_range_h4_index=None` — partial context does not drop the signal.
- **REQ-73.7** (regression, start_index must not be used): GIVEN a `CRTRange` whose `start_index` points to an H4 candle that opens at 17:00 (not 01:00) but whose purge candle — and therefore the enclosing H4 candle for any M15 anchor within it — opens at 01:00, WHEN `detect_forex_crt_signals` is called with a qualifying M15 anchor at 02:30, THEN a `ForexCRTSignal` IS emitted — the 01:00 session identity comes from the bisect-derived enclosing H4 candle, never from `CRTRange.start_index`.

---

### REQ-74: CLI filter flag

The CLI MUST accept a `--forex-policy` boolean flag. When present, `detections.csv` output and backtest trades MUST be filtered to `ForexCRTSignal`s only (02:00–04:00 window, H4 range is `london_crt`). When absent, existing behavior is byte-identical to today's output [charter-8, 00:12:52].

- **REQ-74.1** (backward compatibility): GIVEN a run WITHOUT `--forex-policy`, WHEN output is produced, THEN `detections.csv` is identical to a run on the same data without this change applied at all.
- **REQ-74.2** (filtering): GIVEN a run WITH `--forex-policy` on data containing both 01:00 and 05:00 H4 CRT ranges, WHEN `detections.csv` is written, THEN only Model-1 rows whose H4 context is a `london_crt` range AND whose M15 anchor is in 02:00–04:00 broker clock are present.
- **REQ-74.3** (empty result): GIVEN a run WITH `--forex-policy` on data with no qualifying signals, WHEN `detections.csv` is written, THEN a header-only file is produced (matching REQ-24's existing zero-detection behavior).

---

## Domain: kill-zone-independence

### REQ-75: NY Kill Zone and broker-clock window are independent

The existing `in_ny_kill_zone` classification (REQ-29 / REQ-36, implemented in `core/kill_zone.py`) MUST remain byte-identical after this change. The new broker-clock execution window check is a SEPARATE, additive predicate. The two checks operate on the same `AlignedSignal` independently and MUST NOT interact.

- **REQ-75.1** (coexistence): GIVEN a signal tagged `in_ny_kill_zone=True` in the backtest with `timestamp.hour == 2` broker clock, WHEN both checks are applied, THEN `in_ny_kill_zone` retains its value and `in_execution_window` also returns `True` — neither overrides the other.
- **REQ-75.2** (no modification): GIVEN `core/kill_zone.py` after this change is applied, WHEN inspected, THEN its content is byte-identical to its pre-change state.

---

## Deferred Requirements (named, not scoped here)

The following requirements are acknowledged from the source material but explicitly deferred:

| Deferred item | Source evidence | Follow-up change |
|---|---|---|
| Normal vs. delayed protraction profile | charter-8 [00:04:09], [00:07:58] | `crt-detector-forex-1am-profiles` |
| HTF 4H order flow agreement | charter-8 [00:05:32] | `crt-detector-forex-order-flow-gate` |
| SMT divergence confirmation | charter-8 [00:13:54] | `crt-detector-forex-order-flow-gate` |
| Daily narrative candle-3 gate | charter-9 [00:01:31] | `crt-detector-forex-daily-narrative` |
| Target: opposite 9PM range | charter-8 [00:11:53] | `crt-detector-forex-target-policy` |
| Target: 3R mechanical | charter-9 [00:08:11] | `crt-detector-forex-target-policy` |
| 01:00–02:00 execution window | charter-8 [00:12:25] | pending evidence |
| 04:00–05:00 execution window | charter-8 [00:12:25] | pending evidence |
| Indices (2 AM CRT) | charter-8 [00:01:41] | out of Forex scope |
