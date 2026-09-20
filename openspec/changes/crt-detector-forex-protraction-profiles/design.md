# Design: Forex Protraction Profile Classification

**Change**: `crt-detector-forex-protraction-profiles`
**Spec**: V1 draft (REQ-76–79, REQ-80)
**Triage**: M
**architecture_impact**: additive

---

## 0. Design decision: measurement-only, no classification

Charter 8 [00:03:43] distinguishes "consolidates" from "performs the manipulation" for the 9 PM candle but provides no numeric criterion. The design therefore separates two concerns that must NOT be merged:

1. **Measurement** (this change): compute and attach objective, threshold-free OHLC facts about the 9 PM candle — available AT the 01:00 H4 boundary, no discretion required
2. **Classification** (Phase 2, blocked on Q1 + Q4): apply human-ratified rules to those facts to produce `normal | delayed`

No `ProtractionProfile` type and no classification function are introduced in this version. Encoding a threshold or a stub-that-always-returns-indeterminate would silently diverge from the methodology without adding any present behaviour.

---

## 1. Architecture Overview

```
core → ingestion → primitives → composite/entries → alignment → backtest → viz/cli
```

New files:
```
core/nine_pm_profile.py    [NEW]  NinePmMetrics, measure_nine_pm()
                                  pure functions, no project imports
        │
alignment/forex_broker_clock.py  [MOD]  _build_forex_context() gains NinePmMetrics computation;
        │                                ForexCRTSignal gains nine_pm_metrics field via
        │                                core.forex_crt_context (which is also modified)
core/forex_crt_context.py  [MOD]  ForexCRTSignal.nine_pm_metrics: NinePmMetrics | None added
```

No other module changes. `alignment/htf_ltf.py`, `entries/model1.py`, `backtest/simulate.py`, `viz/table.py`, `cli.py` — all NO CHANGE.

**Why not add `NinePmMetrics` to `ForexCRTContext`?**
`ForexCRTContext` carries the Asia range reference (indices + OHLC bounds). The 9 PM metrics are derived from the Asia candle and its predecessor — they are a computed property of `ForexCRTSignal`, not a range boundary. Keeping them separate preserves the existing context contract and avoids widening `ForexCRTContext` with data that requires series access to compute (which `ForexCRTContext` currently avoids — it holds pre-extracted floats only).

---

## 2. File Changes Table

| Path | Action | Purpose |
|---|---|---|
| `detector/core/nine_pm_profile.py` | NEW | `NinePmMetrics`, `measure_nine_pm()` (REQ-76) |
| `detector/core/forex_crt_context.py` | MOD | `ForexCRTSignal.nine_pm_metrics: NinePmMetrics \| None` added (REQ-77) |
| `detector/alignment/forex_broker_clock.py` | MOD | `_build_forex_context()` gains prior-candle lookup + `measure_nine_pm()` call (REQ-77, REQ-80) |
| `detector/tests/test_nine_pm_profile.py` | NEW | Unit tests for REQ-76 |
| `detector/tests/test_forex_broker_clock.py` | MOD | Additional tests for REQ-77, REQ-79, REQ-80 |

No changes: `cli.py`, `backtest/`, `viz/`, `alignment/htf_ltf.py`, `primitives/`, `composite/`, `ingestion/`, `.importlinter`.

---

## 3. Data Model

```python
# detector/core/nine_pm_profile.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class NinePmMetrics:
    """Objective, threshold-free OHLC facts about the 9 PM H4 candle relative to its predecessor.

    All values are derived from the 9 PM candle and its immediate predecessor — both are
    finalised at the 01:00 H4 boundary after the 21:00 candle closes (REQ-80).

    Interpretation of each field is intentionally left to a downstream Phase 2 classification
    rule gated on Q1 + Q4. This struct is a measurement, not a verdict.
    """
    prior_h4_index: int

    # 9 PM candle body
    body_direction: Literal["bullish", "bearish", "doji"]
    body_ratio: float | None  # abs(close-open)/(high-low); None when high==low

    # 9 PM candle range relative to prior H4 candle range
    extends_prior_high: bool  # nine_pm.high > prior.high
    extends_prior_low: bool   # nine_pm.low < prior.low
    is_inside_bar: bool       # nine_pm.high <= prior.high AND nine_pm.low >= prior.low


def measure_nine_pm(
    nine_pm_open: float,
    nine_pm_high: float,
    nine_pm_low: float,
    nine_pm_close: float,
    prior_high: float,
    prior_low: float,
    prior_h4_index: int,
) -> NinePmMetrics:
    """Compute NinePmMetrics from raw OHLC values.

    No threshold logic here — pure structural arithmetic.
    """
    if nine_pm_close > nine_pm_open:
        body_direction: Literal["bullish", "bearish", "doji"] = "bullish"
    elif nine_pm_close < nine_pm_open:
        body_direction = "bearish"
    else:
        body_direction = "doji"

    candle_range = nine_pm_high - nine_pm_low
    body_ratio = abs(nine_pm_close - nine_pm_open) / candle_range if candle_range > 0 else None

    extends_prior_high = nine_pm_high > prior_high
    extends_prior_low = nine_pm_low < prior_low
    is_inside_bar = nine_pm_high <= prior_high and nine_pm_low >= prior_low

    return NinePmMetrics(
        prior_h4_index=prior_h4_index,
        body_direction=body_direction,
        body_ratio=body_ratio,
        extends_prior_high=extends_prior_high,
        extends_prior_low=extends_prior_low,
        is_inside_bar=is_inside_bar,
    )
```

```python
# detector/core/forex_crt_context.py — delta only

from core.nine_pm_profile import NinePmMetrics  # NEW import

@dataclass(frozen=True)
class ForexCRTSignal:
    aligned_signal: object
    forex_context: ForexCRTContext
    priority: bool
    nine_pm_metrics: NinePmMetrics | None  # NEW — None when 9 PM or prior H4 absent (REQ-77)
```

```python
# detector/alignment/forex_broker_clock.py — _build_forex_context delta only

from core.nine_pm_profile import NinePmMetrics, measure_nine_pm  # NEW

def _build_forex_context(
    enclosing_h4_idx: int,
    htf_series: OHLCSeries,
) -> tuple[ForexCRTContext, NinePmMetrics | None]:  # return type widens
    ...
    # After asia_idx lookup:
    if asia_idx is None:
        return ForexCRTContext(...), None  # no 9 PM candle → no metrics

    asia_candle = htf_series.candles[asia_idx]
    # Compute NinePmMetrics if predecessor exists
    nine_pm_metrics: NinePmMetrics | None
    if asia_idx == 0:
        nine_pm_metrics = None  # no prior candle (REQ-77.3)
    else:
        prior = htf_series.candles[asia_idx - 1]
        nine_pm_metrics = measure_nine_pm(
            nine_pm_open=asia_candle.open,
            nine_pm_high=asia_candle.high,
            nine_pm_low=asia_candle.low,
            nine_pm_close=asia_candle.close,
            prior_high=prior.high,
            prior_low=prior.low,
            prior_h4_index=asia_idx - 1,
        )

    context = ForexCRTContext(
        enclosing_h4_index=enclosing_h4_idx,
        asia_range_h4_index=asia_idx,
        asia_range_high=asia_candle.high,
        asia_range_low=asia_candle.low,
        asia_range_midpoint=(asia_candle.high + asia_candle.low) / 2,
    )
    return context, nine_pm_metrics

# In detect_forex_crt_signals, the call site becomes:
#   context, nine_pm_metrics = _build_forex_context(enclosing_h4_idx, htf_series)
#   result.append(ForexCRTSignal(
#       aligned_signal=signal,
#       forex_context=context,
#       priority=in_priority_subwindow(m15_anchor_ts),
#       nine_pm_metrics=nine_pm_metrics,
#   ))
```

**Note on `_build_forex_context` return type change**: the function is private (prefixed `_`), used only inside `forex_broker_clock.py`. No public API changes. The `ForexCRTContext` dataclass is unchanged.

---

## 4. No-Lookahead Guarantee

The 21:00 H4 candle closes exactly when the 01:00 H4 candle opens. `NinePmMetrics` uses only `h4_series.candles[asia_idx]` and `h4_series.candles[asia_idx - 1]`. Both candles have their OHLC finalised AT the 01:00 H4 boundary. No 01:00 candle fields, no M15 fields, no post-Asia data.

`REQ-80.1` maps directly: the charter's own timing rule [00:04:45] — "must not be predicted before the 9 PM candle has revealed its behavior" — is satisfied because the 9 PM candle is complete AT that boundary, not after it.

---

## 5. Test Derivation Table

| REQ | Scenario | Test file | Scenario description |
|---|---|---|---|
| REQ-76.1 | Bullish, extends-high | `test_nine_pm_profile.py` | 9PM high > prior high, close > open → `bullish`, `extends_prior_high=True`, `is_inside_bar=False` |
| REQ-76.2 | Inside bar | `test_nine_pm_profile.py` | 9PM range contained within prior → `is_inside_bar=True`, both extends=False |
| REQ-76.3 | Doji | `test_nine_pm_profile.py` | `open == close` → `body_direction="doji"` |
| REQ-76.4 | Zero-range | `test_nine_pm_profile.py` | `high == low` → `body_ratio=None`, no exception |
| REQ-76.5 | Extends both | `test_nine_pm_profile.py` | 9PM high > prior high AND low < prior low → both extends=True, `is_inside_bar=False` |
| REQ-76 body_ratio | Arithmetic | `test_nine_pm_profile.py` | `abs(close-open)/(high-low)` computed correctly for a known example |
| REQ-77.1 | nine_pm_metrics populated | `test_forex_broker_clock.py` | Signal with 9PM at idx≥1 → `nine_pm_metrics` is not None |
| REQ-77.2 | None when 9PM absent | `test_forex_broker_clock.py` | `asia_range_h4_index=None` → `nine_pm_metrics=None` |
| REQ-77.3 | None when no prior | `test_forex_broker_clock.py` | 9PM at index 0 → `nine_pm_metrics=None` |
| REQ-79.1 | No regression | `test_forex_broker_clock.py` | All REQ-73 scenarios from prior change still pass; `nine_pm_metrics` is the only addition |
| REQ-79.2 | CSV byte-identical | `test_cli.py` | `--forex-policy` run output unchanged (new field is in-memory only) |
| REQ-80.1 | No lookahead | `test_nine_pm_profile.py` | `measure_nine_pm` called with only the 9 PM and prior candle values — no series index beyond `asia_idx` |

---

## 6. Implementation Slice

**S-000 — Walking skeleton: NinePmMetrics attached to ForexCRTSignal**

Scope: all files listed in §2. No new CLI flag, no CSV change.

Observable outcome: `ForexCRTSignal.nine_pm_metrics` is populated when both the 9 PM candle and its predecessor are in the H4 series. All existing `--forex-policy` behavior is byte-identical.

**TDD sequence**:
1. Write `test_nine_pm_profile.py` (REQ-76) → red
2. Implement `core/nine_pm_profile.py` → green
3. Write additional `test_forex_broker_clock.py` cases (REQ-77) → red
4. Modify `core/forex_crt_context.py` + `alignment/forex_broker_clock.py` → green
5. Confirm REQ-79/80 via existing test suite + new no-lookahead test → green
6. `uv run lint-imports`

---

## 7. Phase 2 Extension Point

When Q1 and Q4 are answered, Phase 2 adds a `classify_protraction(metrics: NinePmMetrics) -> ProtractionProfile` function to `core/nine_pm_profile.py` and a `ProtractionProfile` type alias. `ForexCRTSignal` gains a `protraction_profile` field at that point — an additive change, same pattern as `nine_pm_metrics`. No API surface exists today to break; Phase 2 is a pure addition.

Candidate Q1 answers and their implementability:

| Q1 candidate | Implementable from 9PM + prior H4 alone? | Notes |
|---|---|---|
| Wick extends beyond prior H4 range | YES | Already in `NinePmMetrics.extends_prior_high/low` |
| Body-ratio threshold (e.g., < 0.3 = consolidation) | YES | `NinePmMetrics.body_ratio` |
| Range relative to ATR(14) | YES — requires ATR over preceding 14 H4 candles | Not in `NinePmMetrics` today; would require Phase 2 to pass ATR context as a separate argument |

The `NinePmMetrics` struct as designed covers the first two candidates directly. If ATR is needed, Phase 2 passes it as a separate argument alongside the `NinePmMetrics` rather than changing the existing struct.
