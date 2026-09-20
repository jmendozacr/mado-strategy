# Proposal: Forex Protraction Profile Classification

**Change**: `crt-detector-forex-protraction-profiles`
**Triage**: M (pending product-question resolution — see Open Questions)
**Source docs**: `docs/charter-8.md`, `docs/charter-9.md`
**Prerequisite**: `crt-detector-forex-broker-clock-policy` (archived 2026-09-20)

---

## Problem

The archived broker-clock policy (`ForexCRTSignal`) identifies a valid 1 AM CRT execution-window signal, but carries no information about the *pre-01:00 path* — whether the 9 PM Asia candle consolidated (normal protraction) or swept (delayed protraction). Charter 8 treats this classification as **required context** before taking the 1 AM trade [00:03:16]: "The 9:00 p.m. 4H candle represents the Asia range and must be profiled before building a narrative for the 1 AM candle."

Today, every `ForexCRTSignal` is indistinguishable by profile. A downstream filter, backtest slice, or preference rule (Mado's stated preference is normal-protraction only [00:07:58]) cannot act on that distinction.

---

## Source Evidence

### What charter-8 defines

| Concept | Description | Timestamp |
|---|---|---|
| Normal protraction | 9 PM candle consolidates; 1 AM performs both purge + expansion | [00:03:43–00:04:05] |
| Delayed protraction | 9 PM candle performs the manipulation; 1 AM is the expansion leg / candle three | [00:04:09–00:04:43] |
| Classification timing | Must NOT be predicted before the 9 PM candle reveals its behavior | [00:04:45–00:05:13] |
| Stated preference | Focus on the normal-protraction profile | [00:07:58–00:08:03] |
| Normal intraday signature | 1 AM candle or London shortly afterward prints the day high or low | [00:06:57–00:07:14] |
| Delayed intraday signature | 9 PM candle or Asia session often marks the day high or low; 1 AM launches expansion | [00:07:21–00:07:39] |
| Mado's personal avoidance rule | Personally avoids the 1 AM/London trade when Asia has already made the day high or low, preferring the 5 AM or 9 AM CRT | [00:16:57–00:17:45] |
| Avoidance rule status | Explicitly **not a universal rule** — "a valid setup need not be a setup that belongs in an individual trading plan" | [00:17:52–00:18:11] |
| Practical checklist | Mark 9 PM range high, low, and 50% midpoint; wait for sweep then M15 Model 1 | [00:11:33–00:11:53] |

### What charter-9 adds

| Concept | Description | Timestamp |
|---|---|---|
| 9 PM candle is the key reference range | Confirmed independently in a live execution walkthrough | [00:04:21–00:04:34] |
| Expected sequence in example (normal) | 1 AM open → purge of 9 PM high at key time → expansion | [00:04:36–00:04:58] |

### What the source does NOT provide

Charter 8 never gives:
- A numeric or structural threshold that separates "consolidates" from "performs the manipulation" for the 9 PM candle
- A definition of what "making the day high or low" means mechanically (calendar day? trading day? relative to prior close? absolute swing?)
- A body-ratio cutoff, range-size rule, or any quantitative criterion

The two profile descriptions are presented verbally and illustrated on charts — they are **conceptual categories**, not algorithmic rules.

---

## What IS Computable from the 9 PM H4 Candle at the 01:00 H4 Boundary

The following facts are fully derivable from the 9 PM candle's own OHLC data (available from `ForexCRTContext.asia_range_h4_index`) plus the H4 candle immediately preceding it. The 21:00 H4 candle closes exactly when the 01:00 H4 candle opens; all values below are final at that boundary:

| Metric | Computable | Source basis |
|---|---|---|
| 9 PM high, low, midpoint | YES — already in `ForexCRTContext` | charter-8 [00:11:33] |
| 9 PM body direction (bullish / bearish / doji) | YES — `close > open` / `close < open` / `close == open` | structural |
| 9 PM body-to-range ratio | YES — `abs(close-open) / (high-low)` | structural |
| Whether 9 PM wick extends beyond the prior H4 candle's range | YES — `nine_pm.high > prior.high` OR `nine_pm.low < prior.low` | structural (proxy for "reach") |
| Whether the 9 PM candle closed in the direction of the purge (e.g., closed below if it swept low) | YES | structural |
| Whether the 9 PM candle is an inside bar relative to the prior H4 | YES — `nine_pm.high <= prior.high AND nine_pm.low >= prior.low` | structural (proxy for "consolidation") |

**None of these map directly to "consolidates" or "performs manipulation" without a human-defined threshold.** They are objective measurements that a future policy rule could apply thresholds to.

---

## Scope

```yaml
in_scope:
  - core/nine_pm_profile.py: NinePmMetrics dataclass — computable, threshold-free facts about
      the 9 PM candle relative to its immediate predecessor (body_direction, body_ratio,
      extends_prior_high, extends_prior_low, is_inside_bar, prior_h4_index)
  - core/nine_pm_profile.py: measure_nine_pm(nine_pm, prior) -> NinePmMetrics — pure function,
      no thresholds
  - alignment/forex_broker_clock.py: ForexCRTSignal gains nine_pm_metrics: NinePmMetrics | None
      (None when asia_range_h4_index is None or prior H4 candle is unavailable)
  - core/forex_crt_context.py: no change — asia_range_* fields already present
  - The --forex-policy flag behavior: UNCHANGED. nine_pm_metrics is an additional field on
      ForexCRTSignal; no new CLI flag is introduced by this change.
  - Tests for NinePmMetrics computation (structural scenarios: inside bar, extends prior,
      body direction, doji)

out_of_scope:
  - ProtractionProfile type and any classification function — no classification rule is encoded
      until Q1 and Q4 are answered by a later signed change
  - A --profile flag or any new CLI filter — not until classification is defined
  - HTF order flow, SMT, daily narrative, CISD, targets — all remain deferred
  - Indices (2 AM CRT)
  - 01:00–02:00 and 04:00–05:00 execution windows
  - Changing the existing broker-clock temporal policy
  - Modifying core/broker_clock.py or alignment/htf_ltf.py
```

---

## Approach

**Phase 1 (this change)**: Expose objective 9 PM metrics on `ForexCRTSignal` with no thresholds — a pure measurement layer. No profile value, type, or classification function exists in Phase 1.

**Phase 2 (follow-on, gated on product-question answers)**: Apply human-ratified threshold rules to produce `normal` or `delayed` from the metrics. This is a separate, smaller change once Q1 and Q4 are answered.

**Why not do classification now?**
Charter 8 [00:04:45] explicitly rejects predicting the profile before observing the 9 PM candle's behavior — which means classification IS retrospective and possible. The problem is not timing; it is that the source never specifies the rule. Encoding an invented threshold would silently diverge from the methodology and produce unmeasurable errors.

**Layer placement**: `core/nine_pm_profile.py` — `core` layer, pure functions and frozen dataclass, no imports from the detector stack. `alignment/forex_broker_clock.py` gains the computation call when building `ForexCRTSignal`.

**Extension point**: `ForexCRTSignal.nine_pm_metrics: NinePmMetrics | None` is additive — no existing field changes.

---

## Open Questions (product-question gate for Phase 2)

These must be answered before any automated `normal` / `delayed` classification can be implemented. They are NOT answerable from the charter source material alone.

**Q1 — Manipulation threshold**: Charter 8 distinguishes a 9 PM candle that "consolidates" from one that "performs the manipulation." What structural criterion separates them? Candidates: (a) wick extends beyond the prior H4 candle's range on the manipulation side; (b) body-to-range ratio below a threshold (e.g., < 0.3 = doji = consolidation); (c) range size relative to ATR(14). The source names none of these.

**Q4 — Profile classification from 9 PM metrics alone**: Charter 8's practical checklist [00:11:33] says to "mark the 9 PM range high, low, and 50%." The profile descriptions use the 9 PM candle's structural behavior, not external reference levels (HTF order flow, prior swing highs). Can profile classification run on 9 PM OHLC + prior H4 OHLC alone, or does it require HTF context (which is a deferred dependency)?

---

## Deferred Follow-Up Policies

| Item | Source evidence | Planned change |
|---|---|---|
| ProtractionProfile classification rule | charter-8 [00:03:43], [00:04:09] — pending Q1 + Q4 answers | Phase 2 of this change or `crt-detector-forex-profile-classifier` |
| --profile CLI filter flag | requires classification first | same |
| Mado 1 AM avoidance rule ("Asia made the day high/low") + day-boundary definition | charter-8 [00:16:57–00:17:45] — personal preference, not a universal classification rule | `crt-detector-forex-1am-avoidance-policy` |
| HTF order flow agreement | charter-8 [00:05:32] | `crt-detector-forex-order-flow-gate` |
| SMT divergence | charter-8 [00:13:54] | `crt-detector-forex-order-flow-gate` |
| Daily narrative candle-3 gate | charter-9 [00:01:31] | `crt-detector-forex-daily-narrative` |
| Target policy (3R vs opposite-range) | charter-8 [00:11:53], charter-9 [00:08:11] | `crt-detector-forex-target-policy` |

---

## Risks

1. **Phase 1 without Phase 2 has limited user-visible utility**: `nine_pm_metrics` will be computed but not yet surfaced in `detections.csv` (requires a CSV schema change, same pattern as the `ForexCRTContext` limitation already logged). Phase 1's value is establishing the correct measurement foundation before thresholds are discussed.
2. **"Prior H4 candle" ambiguity at series start**: if the 9 PM candle is the first candle in the H4 series, `prior_h4_index` is None and all extends/inside-bar comparisons are unavailable. `NinePmMetrics` fields that require the prior candle are `None` in that case — never silently assumed.
3. **Body ratio edge case**: a zero-range candle (high == low, e.g. a synthetic fill) would produce a division-by-zero for `body_ratio`. The implementation must guard this: `body_ratio = None` when `high == low`.

---

## Success Criteria

- `NinePmMetrics` is computed for every `ForexCRTSignal` where the 9 PM candle and its predecessor are present in the H4 series.
- No `ProtractionProfile` type, no classification function, and no profile value of any kind exist in Phase 1 — classification belongs entirely to a later signed change gated on Q1 + Q4.
- All existing `ForexCRTSignal` tests continue to pass; `nine_pm_metrics` is an additive field.
- `--forex-policy` output behavior is byte-identical to the archived change — no new filter is introduced.
- `uv run lint-imports` passes.
