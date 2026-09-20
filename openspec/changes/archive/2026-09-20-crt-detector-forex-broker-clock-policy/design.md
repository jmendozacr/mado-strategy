# Design: Forex Broker-Clock Policy for the 1 AM CRT

**Change**: `crt-detector-forex-broker-clock-policy`
**Spec**: V1 draft (REQ-70–75)
**Triage**: M
**architecture_impact**: additive

---

## 1. Architecture Overview

The existing layer stack is:

```
core → ingestion → primitives → composite/entries → alignment → backtest → viz/cli
```

This change adds two new files (`core/broker_clock.py`, `alignment/forex_broker_clock.py`) and touches `cli.py` only. No existing module in any layer changes.

```
core/broker_clock.py          [NEW]     Pure hour predicates — no TZ, no imports from detector stack
core/forex_crt_context.py     [NEW]     ForexCRTContext dataclass; imports core.candle only
        │
alignment/htf_ltf.py          [NO CHANGE]
alignment/forex_broker_clock.py [NEW]   detect_forex_crt_signals(); imports core.broker_clock,
        │                               core.forex_crt_context, alignment.htf_ltf.AlignedSignal
        │
backtest/simulate.py          [NO CHANGE]   receives pre-filtered signals; knows nothing about forex policy
viz/table.py                  [NO CHANGE]
cli.py                        [MOD]     --forex-policy flag; post-filter aligned_signals through
                                        detect_forex_crt_signals before table/backtest
```

**Why alignment layer, not a new `policy/` layer?**
`detect_forex_crt_signals` transforms a `list[AlignedSignal]` (already in scope at `alignment`) with timestamp predicates from `core`. Adding a `policy/` module above `alignment` would require an `.importlinter` rule change and introduce a layer for a single function. Two sibling files in `alignment/` avoid that overhead. Rule of Three: when a second forex-policy function arrives, the layer can be extracted.

**Why NOT modifying `alignment/htf_ltf.py`?**
`tag_alignment` is generic by design (REQ-05 notes "Session/Kill-Zone timing is explicitly NOT part of this check"). Adding Forex-specific time gating inside it would silently break the invariant for non-Forex use. The filter lives orthogonally.

---

## 2. File Changes Table

| Path | Action | Purpose |
|---|---|---|
| `detector/core/broker_clock.py` | NEW | `is_london_crt_h4`, `is_asia_range_h4`, `in_execution_window`, `in_priority_subwindow`, `asia_range_timestamp` (REQ-70, REQ-71.1, REQ-72) |
| `detector/core/forex_crt_context.py` | NEW | `ForexCRTContext`, `ForexCRTSignal` dataclasses (REQ-73) |
| `detector/alignment/forex_broker_clock.py` | NEW | `detect_forex_crt_signals`, `find_asia_range_index` (REQ-71.2/71.3, REQ-73) |
| `detector/cli.py` | MOD | `--forex-policy` flag; when set, post-filter via `detect_forex_crt_signals` before table write + backtest (REQ-74) |
| `detector/tests/test_broker_clock.py` | NEW | Unit tests for REQ-70, REQ-71.1, REQ-72, REQ-75.1/75.2 |
| `detector/tests/test_forex_broker_clock.py` | NEW | Integration tests for REQ-71.2/71.3, REQ-73 |
| `detector/tests/test_cli.py` | MOD | REQ-74.1/74.2/74.3: `--forex-policy` flag presence/absence |

No changes needed: `core/kill_zone.py`, `core/key_level.py`, `core/config.py`, `ingestion/`, `primitives/`, `composite/`, `entries/`, `alignment/htf_ltf.py`, `backtest/simulate.py`, `viz/table.py`, `.importlinter`.

---

## 3. Data Model

```python
# detector/core/broker_clock.py

from datetime import datetime, timedelta


def is_london_crt_h4(ts: datetime) -> bool:
    """H4 candle opening at 01:00 broker clock — the 1 AM CRT [charter-8, 00:01:41]."""
    return ts.hour == 1


def is_asia_range_h4(ts: datetime) -> bool:
    """H4 candle opening at 21:00 broker clock — Asia reference range [charter-8, 00:03:16]."""
    return ts.hour == 21


def in_execution_window(ts: datetime) -> bool:
    """02:00 <= broker hour < 04:00 [charter-8, 00:12:13, 00:12:52]."""
    return 2 <= ts.hour < 4


def in_priority_subwindow(ts: datetime) -> bool:
    """03:00 <= broker hour < 04:00 — highest-probability sub-window [charter-9, 00:05:18]."""
    return ts.hour == 3


def asia_range_timestamp(london_crt_ts: datetime) -> datetime:
    """The 21:00 Asia range candle is exactly 4 broker hours before the 01:00 London CRT candle."""
    return london_crt_ts - timedelta(hours=4)
```

```python
# detector/core/forex_crt_context.py

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ForexCRTContext:
    """Links the enclosing H4 candle (01:00 broker clock) with its 21:00 Asia reference range.

    enclosing_h4_index is the bisect-derived index of the H4 candle whose timestamp is
    the last H4 timestamp <= the M15 anchor timestamp.  It is NOT CRTRange.start_index,
    which is the origin of the generic sliding CRT range and carries no session identity.

    All indices are into the H4 OHLCSeries passed to detect_forex_crt_signals.
    asia_range_* fields are None when the 21:00 candle is absent from the series tail
    — partial context is reported, the signal is never silently dropped (REQ-71.3).
    """
    enclosing_h4_index: int           # bisect-derived H4 candle that encloses the M15 anchor; hour == 1 guaranteed
    asia_range_h4_index: int | None
    asia_range_high: float | None
    asia_range_low: float | None
    asia_range_midpoint: float | None  # (high + low) / 2 — the 50% level [charter-8, 00:11:33]


@dataclass(frozen=True)
class ForexCRTSignal:
    """An AlignedSignal that satisfies all Forex broker-clock policy conditions.

    Does NOT imply trade eligibility — HTF order flow, profiles, daily narrative,
    and target policy are all deferred (see spec deferred table).
    """
    aligned_signal: object          # alignment.htf_ltf.AlignedSignal (typed at usage site)
    forex_context: ForexCRTContext
    priority: bool                  # True when M15 anchor is in 03:00–04:00 [charter-9, 00:05:18]
```

```python
# detector/alignment/forex_broker_clock.py

from __future__ import annotations
import bisect
from datetime import datetime

from core.broker_clock import (
    asia_range_timestamp, in_execution_window, in_priority_subwindow, is_london_crt_h4,
)
from core.candle import OHLCSeries
from core.forex_crt_context import ForexCRTContext, ForexCRTSignal
from alignment.htf_ltf import AlignedSignal


def detect_forex_crt_signals(
    aligned_signals: list[AlignedSignal],
    htf_series: OHLCSeries,
    ltf_series: OHLCSeries,
) -> list[ForexCRTSignal]:
    """Filter AlignedSignals to those satisfying the Forex broker-clock policy.

    Conditions (all required, REQ-73):
      1. aligned == "aligned"
      2. The H4 candle enclosing the M15 anchor opens at 01:00 broker clock
      3. M15 anchor timestamp is in execution window 02:00–04:00

    The enclosing H4 candle is the last H4 candle whose own timestamp is <=
    the M15 anchor timestamp — derived via bisect_right.  This is intentionally
    NOT AlignedSignal.htf_context.start_index: CRTRange.start_index is the
    origin of the generic sliding range and carries no session identity.
    tag_alignment uses the identical lookup internally (_enclosing_htf_index);
    we replicate it with bisect rather than importing a private function (REQ-73.7).
    """
    htf_timestamps = [c.timestamp for c in htf_series.candles]
    result = []

    for signal in aligned_signals:
        if signal.aligned != "aligned":
            continue

        m15_anchor_ts = ltf_series.candles[signal.ltf_signal.anchor_index].timestamp

        # Derive the enclosing H4 candle from the M15 anchor timestamp.
        position = bisect.bisect_right(htf_timestamps, m15_anchor_ts)
        if position == 0:
            continue
        enclosing_h4_idx = position - 1

        if not is_london_crt_h4(htf_series.candles[enclosing_h4_idx].timestamp):
            continue
        if not in_execution_window(m15_anchor_ts):
            continue

        context = _build_forex_context(enclosing_h4_idx, htf_series)
        result.append(ForexCRTSignal(
            aligned_signal=signal,
            forex_context=context,
            priority=in_priority_subwindow(m15_anchor_ts),
        ))

    return result


def find_asia_range_index(
    london_crt_ts: datetime,
    htf_series: OHLCSeries,
) -> int | None:
    """Exact timestamp lookup for the 21:00 Asia range candle (REQ-71.2/71.3)."""
    target = asia_range_timestamp(london_crt_ts)
    for i, candle in enumerate(htf_series.candles):
        if candle.timestamp == target:
            return i
    return None


def _build_forex_context(
    enclosing_h4_idx: int,
    htf_series: OHLCSeries,
) -> ForexCRTContext:
    london_crt_ts = htf_series.candles[enclosing_h4_idx].timestamp
    asia_idx = find_asia_range_index(london_crt_ts, htf_series)
    if asia_idx is None:
        return ForexCRTContext(
            enclosing_h4_index=enclosing_h4_idx,
            asia_range_h4_index=None,
            asia_range_high=None,
            asia_range_low=None,
            asia_range_midpoint=None,
        )
    asia_candle = htf_series.candles[asia_idx]
    return ForexCRTContext(
        enclosing_h4_index=enclosing_h4_idx,
        asia_range_h4_index=asia_idx,
        asia_range_high=asia_candle.high,
        asia_range_low=asia_candle.low,
        asia_range_midpoint=(asia_candle.high + asia_candle.low) / 2,
    )
```

---

## 4. CLI Integration

```python
# cli.py — delta only

parser.add_argument("--forex-policy", action="store_true", default=False,
                    help="Filter output to 1 AM CRT Forex signals in the 02:00–04:00 broker-clock window.")

# After tag_alignment produces aligned_signals:
if args.forex_policy:
    forex_signals = detect_forex_crt_signals(aligned_signals, htf_series, ltf_series)
    aligned_signals = [fs.aligned_signal for fs in forex_signals]
    # forex_signals list kept locally if future REQ needs priority column
```

The filter runs AFTER `tag_alignment` and BEFORE the table writer and backtest. `backtest/simulate.py` and `viz/table.py` receive a plain `list[AlignedSignal]` — they need zero changes.

---

## 5. NY Kill Zone — Explicit Non-Interaction

`core/kill_zone.py` reads:
```python
local = timestamp.replace(tzinfo=_UTC).astimezone(_NY)
return config.ny_start_hour <= local.hour < config.ny_end_hour
```

This uses `zoneinfo.ZoneInfo("America/New_York")` for DST-aware conversion. The new `in_execution_window` reads `ts.hour` directly. The two predicates operate on different semantic layers (NY-converted time vs. raw broker time) and share no code paths. A signal at 02:00 broker clock may or may not be in the NY Kill Zone depending on DST and broker offset — that is correct, expected, and not a bug.

---

## 6. Test Derivation Table

| REQ | Test type | File | Scenario |
|---|---|---|---|
| REQ-70.1 | Unit | `test_broker_clock.py` | `is_london_crt_h4(datetime(2026,9,16,1,0))` → `True` |
| REQ-70.2 | Unit | `test_broker_clock.py` | `is_asia_range_h4(datetime(2026,9,15,21,0))` → `True` |
| REQ-70.3 | Unit | `test_broker_clock.py` | `is_london_crt_h4(datetime(2026,9,16,1,30))` → `True` (minute irrelevant, `.hour==1`) |
| REQ-70.4 | Unit | `test_broker_clock.py` | `is_london_crt_h4(datetime(2026,9,16,5,0))` → `False`; same for `is_asia_range_h4` |
| REQ-71.1 | Unit | `test_broker_clock.py` | `asia_range_timestamp(datetime(2026,9,16,1,0)) == datetime(2026,9,15,21,0)` |
| REQ-71.2 | Integration | `test_forex_broker_clock.py` | H4 series with 21:00 candle → `find_asia_range_index` returns its index |
| REQ-71.3 | Integration | `test_forex_broker_clock.py` | H4 series starting at 01:00 (no 21:00 prior) → `find_asia_range_index` returns `None` |
| REQ-72.1 | Unit | `test_broker_clock.py` | `in_execution_window(datetime(2026,9,16,2,0))` → `True` |
| REQ-72.3 | Unit | `test_broker_clock.py` | `in_execution_window(datetime(2026,9,16,4,0))` → `False` (boundary excluded) |
| REQ-72.4 | Unit | `test_broker_clock.py` | `in_execution_window(datetime(2026,9,16,1,45))` → `False` |
| REQ-72.5 | Unit | `test_broker_clock.py` | `in_priority_subwindow(datetime(2026,9,16,3,15))` → `True` |
| REQ-72.6 | Unit | `test_broker_clock.py` | `in_priority_subwindow(datetime(2026,9,16,2,45))` → `False` |
| REQ-73.1 | Integration | `test_forex_broker_clock.py` | H4 series: enclosing candle (last H4 ts ≤ M15 anchor 02:30) opens at 01:00 → ForexCRTSignal, `priority=False` |
| REQ-73.2 | Integration | `test_forex_broker_clock.py` | Enclosing H4 at 01:00, M15 anchor at 03:00 → `priority=True` |
| REQ-73.3 | Integration | `test_forex_broker_clock.py` | Enclosing H4 at 05:00 (not 01:00), M15 at 02:30 → excluded |
| REQ-73.4 | Integration | `test_forex_broker_clock.py` | Enclosing H4 at 01:00, M15 anchor at 06:00 → excluded |
| REQ-73.5 | Integration | `test_forex_broker_clock.py` | `aligned="unaligned"` → excluded |
| REQ-73.6 | Integration | `test_forex_broker_clock.py` | Qualifying signal, no 21:00 candle in series → emitted with `ForexCRTContext.asia_range_h4_index=None` |
| REQ-73.7 | Integration | `test_forex_broker_clock.py` | CRTRange with `start_index` pointing to a 17:00 candle but enclosing H4 candle (bisect) at 01:00, M15 at 02:30 → ForexCRTSignal emitted (start_index NOT used) |
| REQ-74.1 | CLI | `test_cli.py` | without `--forex-policy`, output identical to existing output |
| REQ-74.2 | CLI | `test_cli.py` | with `--forex-policy`, only 01:00-H4 + 02:00–04:00 rows in CSV |
| REQ-74.3 | CLI | `test_cli.py` | with `--forex-policy`, no qualifying signals → header-only CSV, exit 0 |
| REQ-75.1 | Unit | `test_broker_clock.py` | `in_execution_window` and `in_ny_kill_zone` called on same timestamp → independent booleans |
| REQ-75.2 | Structural | `test_broker_clock.py` | No import of `core.kill_zone` in `core.broker_clock`; no import of `core.broker_clock` in `core.kill_zone` |

---

## 7. Implementation Slice

**S-000 — Walking skeleton: broker-clock filter is fully wired and user-observable**

Scope:
- `core/broker_clock.py` (REQ-70, REQ-71.1, REQ-72)
- `core/forex_crt_context.py` (REQ-73 types)
- `alignment/forex_broker_clock.py` (REQ-71.2/71.3, REQ-73)
- `cli.py` `--forex-policy` flag (REQ-74)
- All test files above

Observable outcome: running `uv run --project detector python -m detector.cli --csv H4.csv --symbol EURUSD --htf-csv M15.csv --htf-symbol EURUSD --forex-policy` produces a `detections.csv` filtered to 1 AM CRT execution-window Model-1 signals. Running without `--forex-policy` is byte-identical to today.

This is the only planned slice. The full spec (REQ-70–75) fits in one coherent, independently-testable delivery: the predicate layer, the context type, the filter function, and the CLI entry point are all needed for any observable behavior, and none is useful without the others.

**TDD sequence**:
1. Write `test_broker_clock.py` first (REQ-70, REQ-71.1, REQ-72, REQ-75) → all red
2. Implement `core/broker_clock.py` → green
3. Write `test_forex_broker_clock.py` (REQ-71.2/71.3, REQ-73) → red
4. Implement `core/forex_crt_context.py` + `alignment/forex_broker_clock.py` → green
5. Write CLI tests (REQ-74) → red
6. Touch `cli.py` → green
7. `uv run lint-imports` — confirm no new layer violations

---

## 8. Reuse of Existing Foundations

The generic H4→M15 alignment (`tag_alignment` in `alignment/htf_ltf.py`) is reused unchanged. It produces `AlignedSignal`s that carry `htf_context: CRTRange | None`.

**Critical distinction**: `CRTRange.start_index` is the origin of the generic sliding 2/3/multi-candle range (e.g., candle[0] of a 3-candle window) — it has nothing to do with the H4 session candle. `tag_alignment` identifies the enclosing H4 candle via `_enclosing_htf_index(htf_timestamps, anchor_timestamp)` (a `bisect_right` lookup) and stores the `CRTRange` under that purge-candle key — but the key itself is NOT preserved in `AlignedSignal`. `detect_forex_crt_signals` recovers the same enclosing H4 candle index by re-running `bisect_right(htf_timestamps, m15_anchor_ts) - 1` independently. The session-identity check (`is_london_crt_h4`) is applied to that candle, never to `CRTRange.start_index`.

The generic `Model1Signal` detection (`entries/model1.py`) is also reused unchanged. It fires on any purge + engulf structure regardless of time. The Forex broker-clock filter runs AFTER these generic passes, filtering their output — not replacing or modifying them.

**Critical invariant preserved**: a generic `Model1Signal` is NEVER implicitly treated as a valid 1 AM CRT setup. The `ForexCRTSignal` wrapper is required explicitly. The `--forex-policy` flag is the only gate — the filtering is opt-in, not silent.

---

## 9. Deferred Architecture Notes

When the first follow-up policy (e.g., profile classifier or HTF order flow gate) arrives, the natural extension point is:

1. `ForexCRTSignal` gains additional optional fields (profile, order_flow_aligned, etc.) — additive, backward-compatible
2. `detect_forex_crt_signals` can accept an optional config dataclass for enabling/disabling sub-checks
3. If three or more such policies exist, `alignment/forex_broker_clock.py` can be promoted to a `policy/` sublayer

None of these are authorised by the current spec. They are noted so the next change doesn't re-litigate the design.
