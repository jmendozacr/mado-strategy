# Spec: Forex Protraction Profile Classification

**Change**: `crt-detector-forex-protraction-profiles`
**Spec version**: V1 | **Status**: signed
**Triage**: M
**Source docs**: `docs/charter-8.md`, `docs/charter-9.md`
**REQ range**: REQ-76 – REQ-79

---

## Scope note

This spec covers Phase 1 only: the objective measurement layer (`NinePmMetrics`) and its attachment to `ForexCRTSignal`. No `ProtractionProfile` type, classification function, or profile value of any kind is introduced here. Phase 2 (automated normal/delayed classification) requires answers to product questions Q1 + Q4 (see proposal.md) and is out of scope for this version.

---

## Domain: nine-pm-candle-metrics

### REQ-76: Compute objective metrics for the 9 PM H4 candle

The system MUST compute a `NinePmMetrics` record from the 9 PM H4 candle and its immediate predecessor whenever both are present in the H4 series. The following fields are required; all comparisons use raw OHLC prices with no normalisation:

- `body_direction: Literal["bullish", "bearish", "doji"]` — `"bullish"` when `close > open`; `"bearish"` when `close < open`; `"doji"` when `close == open`
- `body_ratio: float | None` — `abs(close - open) / (high - low)` when `high > low`; `None` when `high == low` (zero-range candle, avoids division by zero) [charter-8, 00:03:43: the 9 PM candle's internal structure is the basis for profile distinction]
- `extends_prior_high: bool` — `True` when `nine_pm.high > prior_h4.high` [structural proxy for "reach" on the high side]
- `extends_prior_low: bool` — `True` when `nine_pm.low < prior_h4.low` [structural proxy for "reach" on the low side]
- `is_inside_bar: bool` — `True` when `nine_pm.high <= prior_h4.high AND nine_pm.low >= prior_h4.low` [structural proxy for consolidation; charter-8 [00:03:43]: "the 9 PM candle consolidates"]
- `prior_h4_index: int` — H4 series index of the predecessor candle

**All fields that require the prior candle are `None` / `False` is NOT acceptable when the prior is absent — use `None` for the whole `NinePmMetrics` instead (REQ-77.3).**

- **REQ-76.1** (happy, bullish extends-high): GIVEN a 9 PM candle with `open=1.10, high=1.12, low=1.09, close=1.115` and a prior candle with `high=1.11`, WHEN metrics are computed, THEN `body_direction="bullish"`, `extends_prior_high=True`, `extends_prior_low=False`, `is_inside_bar=False`, `body_ratio` ≈ 0.5.
- **REQ-76.2** (happy, inside bar): GIVEN a 9 PM candle with `open=1.105, high=1.109, low=1.102, close=1.104` and a prior candle with `high=1.12, low=1.10`, WHEN metrics are computed, THEN `is_inside_bar=True`, `extends_prior_high=False`, `extends_prior_low=False`.
- **REQ-76.3** (edge, doji): GIVEN a 9 PM candle where `open == close`, WHEN metrics are computed, THEN `body_direction="doji"`.
- **REQ-76.4** (edge, zero-range): GIVEN a 9 PM candle where `high == low`, WHEN metrics are computed, THEN `body_ratio=None` — no division by zero, no error.
- **REQ-76.5** (edge, extends both): GIVEN a 9 PM candle that exceeds both the prior high and the prior low, WHEN metrics are computed, THEN `extends_prior_high=True`, `extends_prior_low=True`, `is_inside_bar=False`.

---

### REQ-77: NinePmMetrics attachment to ForexCRTSignal

`ForexCRTSignal` MUST gain a new field `nine_pm_metrics: NinePmMetrics | None`. The value is `None` in exactly two cases:

1. The 9 PM candle is absent from the H4 series (`ForexCRTContext.asia_range_h4_index is None`)
2. The 9 PM candle has no predecessor in the H4 series (it is the first candle, `asia_range_h4_index == 0`)

In all other cases the value MUST be a fully-populated `NinePmMetrics` instance. No error is raised for absent data — `None` signals "insufficient context."

- **REQ-77.1** (happy): GIVEN a `ForexCRTSignal` whose H4 series contains the 9 PM candle at index 5 and a prior candle at index 4, WHEN `nine_pm_metrics` is accessed, THEN a `NinePmMetrics` instance is returned (not None).
- **REQ-77.2** (absent 9 PM): GIVEN a `ForexCRTSignal` whose `ForexCRTContext.asia_range_h4_index is None`, WHEN `nine_pm_metrics` is accessed, THEN `None`.
- **REQ-77.3** (no prior): GIVEN a `ForexCRTSignal` whose 9 PM candle is at H4 index 0 (no predecessor), WHEN `nine_pm_metrics` is accessed, THEN `None` — the field is never partially populated.

---

## Domain: backward-compatibility

### REQ-79: Existing ForexCRTSignal behavior is unchanged

Adding `nine_pm_metrics` to `ForexCRTSignal` is additive. All existing REQ-70 through REQ-75 scenarios MUST continue to pass without modification.

- **REQ-79.1**: GIVEN the full test suite as of the `crt-detector-forex-broker-clock-policy` archive, WHEN this change is applied, THEN 0 previously-passing tests regress.
- **REQ-79.2**: GIVEN a run with `--forex-policy` after this change, WHEN `detections.csv` is inspected, THEN the output is byte-identical to the pre-change output (no new column, no new row — `nine_pm_metrics` is in-memory only until a CSV schema change is separately specced).

---

## Domain: no-lookahead

### REQ-80: NinePmMetrics uses only data available at the 01:00 H4 boundary

`NinePmMetrics` MUST be derived exclusively from the 9 PM H4 candle and its immediate predecessor. The 21:00 H4 candle closes exactly when the 01:00 H4 candle opens; its OHLC is final AT that boundary. No M15 data, no 01:00 candle data, and no later H4 candle data may be used.

- **REQ-80.1** (grounded, charter-8 [00:04:45]): Classification "must not be predicted before the 9 PM candle has revealed its behavior" — at the 01:00 H4 boundary the 9 PM candle is complete and all its OHLC values are final. GIVEN any `ForexCRTSignal`, WHEN `nine_pm_metrics` is inspected, THEN all field values derive only from `h4_series.candles[asia_range_h4_index]` and `h4_series.candles[asia_range_h4_index - 1]`.

---

## Deferred Requirements

| Deferred item | Source evidence | Condition for activation |
|---|---|---|
| `ProtractionProfile.normal` classification rule | charter-8 [00:03:43] | Q1 answered (manipulation threshold) |
| `ProtractionProfile.delayed` classification rule | charter-8 [00:04:09] | Q1 + Q4 answered |
| Mado 1 AM avoidance rule + "day high/low" boundary definition | charter-8 [00:16:57–00:17:45] | separate change `crt-detector-forex-1am-avoidance-policy` |
| `--profile` CLI filter flag | charter-8 [00:07:58] | classification REQs signed |
| `nine_pm_metrics` surfaced in `detections.csv` | — | separate CSV schema change |
