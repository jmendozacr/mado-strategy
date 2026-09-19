# Proposal: Forex Broker-Clock Policy for the 1 AM CRT

**Change**: `crt-detector-forex-broker-clock-policy`
**Triage**: M
**Source docs**: `docs/charter-8.md`, `docs/charter-9.md`

---

## Intent

Charters 8 and 9 introduce the 1 AM CRT as a time-first strategy: a specific pair of H4 candles (21:00 Asia reference range + 01:00 London CRT), a strict M15 execution window (02:00–04:00 broker clock), and a priority sub-window (03:00–04:00). The existing detector is time-agnostic — it detects CRT ranges and Model-1 signals purely from price structure and emits them without any notion of which H4 candle opens at 01:00.

This change adds a Forex broker-clock policy layer: a new, additive filter that tags an `AlignedSignal` as a `ForexCRTSignal` only when the enclosing H4 CRT range opens at 01:00 broker clock **and** the M15 anchor falls within 02:00–04:00 broker clock. A new `--forex-policy` CLI flag exposes the filter to the user.

The broker clock is the raw, unconverted timestamp embedded in the MT5 export — the same timestamp already loaded by `ingestion/loader.py`. No UTC conversion, no DST-aware tz arithmetic, no `zoneinfo` usage. This is a hard contract, not a default.

---

## Source Evidence Summary

| Fact | Charter citation |
|---|---|
| Forex 1 AM CRT = H4 candle opening at 01:00 | charter-8 [00:01:41] |
| 1 AM candle runs 01:00–05:00 (London Kill Zone) | charter-8 [00:02:30] |
| 21:00 H4 = Asia range, the reference for the 1 AM CRT | charter-8 [00:03:16] |
| Execution window: 02:00–04:00 broker clock | charter-8 [00:12:13] and [00:12:52] |
| Priority sub-window: 03:00–04:00 | charter-8 [00:12:13], charter-9 [00:05:18] |
| 01:00–02:00 and 04:00–05:00 are not recommended for beginners | charter-8 [00:12:25] |
| Execution TF is M15; sweep alone is not the entry | charter-8 [00:08:58] |
| The "3 AM" reference is the 03:00–04:00 window, not one minute | charter-9 [00:05:18] |
| Indices use 02:00 (out of scope for this change) | charter-8 [00:01:41] |

---

## Scope

```yaml
in_scope:
  - core/broker_clock.py: pure broker-clock predicates on datetime.hour with no TZ conversion
      is_london_crt_h4(ts)   → True when ts.hour == 1
      is_asia_range_h4(ts)   → True when ts.hour == 21
      in_execution_window(ts) → True when 2 <= ts.hour < 4
      in_priority_subwindow(ts) → True when ts.hour == 3
      asia_range_timestamp(london_crt_ts) → london_crt_ts - timedelta(hours=4)
  - core/forex_crt_context.py: ForexCRTContext dataclass linking the 01:00 and 21:00 H4 ranges
  - alignment/forex_broker_clock.py: detect_forex_crt_signals() that filters AlignedSignals
      to those whose H4 range is london_crt AND whose M15 anchor is in the execution window
  - cli.py: new --forex-policy flag; when present, post-filter aligned signals through
      detect_forex_crt_signals before writing detections.csv and running backtest

out_of_scope:
  - Indices (2 AM CRT) — explicitly deferred; not Forex
  - 01:00–02:00 execution window — deferred (charter-8 [00:12:25]: manipulation-heavy)
  - 04:00–05:00 execution window — deferred (charter-8 [00:12:25]: conditions-dependent)
  - Normal vs. delayed protraction profiles — require discretionary 9 PM candle read before the 1 AM open; cannot be automated without the profile classification sub-system
  - HTF order flow (bullish/bearish 4H structure), SMT divergence — deferred follow-up policy
  - Daily narrative (candle 1/2/3 sequence from charter-9 [00:01:31]) — deferred
  - CISD confirmation vs. plain Model-1 as alternative entries — deferred
  - Target policy: charter-8 [00:11:53] names "opposite side of the range"; charter-9 [00:08:11] names "3R mechanical" — these conflict and require a dedicated resolution; explicitly deferred
  - Modifying core/kill_zone.py or any NY Kill Zone behavior — the existing NY-converted kill zone is separate legacy behavior; this change adds an independent, parallel check
  - Adding new detections.csv row types or chart markers for the Asia range or the London CRT H4 candle
```

---

## Approach

All additions are net-new files plus a one-touch to `cli.py`. No existing files in `core/`, `primitives/`, `composite/`, `entries/`, or `alignment/htf_ltf.py` change.

**Layer placement**: `core/broker_clock.py` sits at the `core` layer (no imports from the detector stack). `alignment/forex_broker_clock.py` is a new sibling inside the existing `alignment` layer — it imports `core.broker_clock`, `core.candle.OHLCSeries`, `core.forex_crt_context`, and `alignment.htf_ltf.AlignedSignal`; nothing else.

**Raw-clock contract**: `is_london_crt_h4(ts)` reads `ts.hour` directly — the same `datetime` already deserialized by `load_mt5_csv`. No `replace(tzinfo=...)`, no `.astimezone(...)`. The existing `in_ny_kill_zone` function in `core/kill_zone.py` performs UTC→NY conversion (REQ-29 / REQ-36) — that behavior is UNCHANGED and fully independent. The two checks coexist on the same `AlignedSignal` without interaction.

**Enclosing H4 candle derivation**: `AlignedSignal.htf_context` is a `CRTRange` whose `start_index` is the origin of a generic sliding 2/3/multi-candle range — it is NOT the H4 candle that encloses the M15 anchor in time. The correct H4 candle to check is derived by `bisect_right(htf_timestamps, m15_anchor_ts) - 1` — the last H4 candle whose timestamp is ≤ the M15 anchor timestamp. This is the same lookup `tag_alignment._enclosing_htf_index` uses when building the `purge_index_to_range` map; `detect_forex_crt_signals` replicates it independently via `bisect` rather than importing the private function. Using `CRTRange.start_index` for the session-identity check would be semantically wrong.

**Asia reference pairing**: given the enclosing H4 candle timestamp `T` (hour == 1), the Asia range candle opens at `T - timedelta(hours=4)` (hour == 21, previous calendar day). `detect_forex_crt_signals` does a direct timestamp lookup in the H4 series. If the 21:00 candle is absent (series starts after it), `asia_range_h4_index` is `None` — the signal is still emitted with partial context, never silently dropped.

**Observable behavior**: with `--forex-policy`, `detections.csv` and the backtest output are filtered to Forex CRT signals only. Without the flag, existing behavior is byte-identical to today.

---

## Deferred Follow-Up Policies

The following are named follow-up items, not scope of this change:

1. **Profile classifier** — `normal_protraction` vs. `delayed_protraction` based on 9 PM candle behavior
2. **HTF order flow filter** — bullish/bearish 4H structure agrees with the sweep direction
3. **SMT divergence requirement** — as named in charter-8 [00:13:54]
4. **Daily narrative gate** — candle-3 confirmation from charter-9 [00:01:31]
5. **Target policy** — resolving the 3R (charter-9) vs. opposite-range (charter-8) conflict
6. **01:00–02:00 and 04:00–05:00 window activation** — once evidence is gathered

---

## Risks

1. **Broker-clock assumption is unverified at series level**: the MT5 export timestamps are assumed to be broker-local (unconverted), consistent with REQ-01's "broker-local timezone unconverted" statement. If a dataset is UTC-stamped, `ts.hour == 1` would mismatch silently. A future REQ should gate this on a `--instrument-type forex` flag or similar metadata; for now the `--forex-policy` flag itself is the opt-in.
2. **H4 series may not be 4-hour-aligned at 01:00/21:00**: some brokers use 00:00-aligned H4 partitions (00:00, 04:00, 08:00...) or non-standard ones. The predicates only fire when timestamps match exactly. The spec REQs explicitly require no fallback — partial match → no signal, never a wrong signal.
3. **Asia range absence at series start**: if the H4 series starts at or after 01:00 of day 1, the 21:00 candle is missing. `ForexCRTContext.asia_range_h4_index = None` is the designed outcome; it should not cause the signal to be dropped.

---

## Success Criteria

- REQ-70 through REQ-75 scenarios pass; `uv run lint-imports` passes; no existing test regresses.
- `--forex-policy` run on a real H4+M15 Forex pair produces a filtered `detections.csv` showing only rows whose `timestamp` falls in broker-clock 02:00–04:00 and whose H4 context opens at 01:00.
- `--forex-policy` absent: output is byte-identical to today's output on the same input.
