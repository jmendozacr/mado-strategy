# Section 3/4 Results — 9AM Confirmations Resolving Exactly at 13:00 New York

Protocol: `docs/07` (committed before any number below was computed). Source:
`artifacts/raza_thirteen_oclock_report.json`, produced by `raza_stats/thirteen_oclock_report.py`
over the three per-symbol artifacts (`raza_extract/build_and_save_thirteen_oclock.py`).

## Reconciliation

232 confirmed signals pooled (EURUSD 72, USDCAD 81, AUDUSD 79 -- exactly matching the feasibility
count fixed in `docs/07` before this run). **Baseline-arm executed trades (119) reconcile 100%
against the real ledger by `stable_id` -- zero mismatches, zero missing.** Restricting the input
population to this 232-signal subset never changed an individual candidate's own resolution,
confirming the equivalence argument in `docs/07`.

## Funnel, both arms, same 232-signal denominator

| Stage | Baseline | Variant |
|---|---|---|
| Confirmed (population) | 232 | 232 |
| Candidate | 140 (60.3%) | 38 (16.4%) |
| Filled | 119 (85.0% of candidates) | 28 (73.7% of candidates) |
| Closed | 118 | 28 |
| Open (censored) | 1 | 0 |
| Skipped or unfilled | 113 | 204 |

The variant's gate removes 92 of 232 confirmations BEFORE the RR floor even runs (everything
`OUTSIDE` or `EXACT_BOUNDARY`) -- of the 112 that reach Stage 6 as `INSIDE`, only 38 (33.9%) clear
the UNCHANGED RR floor, a similar survival rate to baseline's own 140/232 (60.3%)... actually lower
(INSIDE signals pass the RR floor LESS often than the full population did) -- reported as a
descriptive fact, not explained further here (out of this unit's scope).

## Descriptive breakdown (never used as a filter)

`close_position`: OUTSIDE 119 (51.3%), INSIDE 112 (48.3%), EXACT_BOUNDARY 1 (0.4%). `sweep_side`:
LOW_ONLY 97, HIGH_ONLY 92, BOTH (double sweep) 43. Of the 112 INSIDE signals: **85 (75.9%)
single-sided, 27 (24.1%) double sweeps** -- both kept in the primary comparison, per protocol.

## Primary metric: net R per original 13:00 confirmation (n=231, one AUDUSD signal censored --
## still open in the baseline arm at the data's end, excluded from both arms' sums per protocol)

| | Baseline | Variant |
|---|---|---|
| Mean R per confirmation (n=231) | +0.0822 | +0.1002 |
| **Diff (variant - baseline)** | | **+0.0179** |
| Total R | +18.99 | +23.14 |
| Mean R per CLOSED trade | +0.161 (n=118) | +0.826 (n=28) |

**95% block-bootstrap CI on the paired difference** (2,000 resamples, blocks = whole NY trading
dates pooled across all three instruments, 218 blocks): **[-0.154, +0.171]** -- a range about 18x
the point estimate's own magnitude, and it crosses zero.

## By instrument (consistency check)

| | EURUSD | USDCAD | AUDUSD |
|---|---|---|---|
| n (population) | 72 | 81 | 79 (1 censored) |
| Diff (variant - baseline) | **+0.107** | **-0.032** | **-0.013** |
| n closed, baseline / variant | 33 / 12 | 45 / 11 | 40 / 5 |

**The sign is NOT consistent across instruments** -- EURUSD positive, USDCAD and AUDUSD both
slightly negative. This differs from the first experiment's own full-population INSIDE-vs-OUTSIDE
result (`docs/02`), which agreed in sign across all three pairs.

## Decomposition (how the difference is built)

| Category | n | Sum of baseline R | Mean |
|---|---|---|---|
| `BOTH_ZERO` (neither arm ever executes) | 113 | -- | -- |
| `UNAFFECTED` (variant executes identically to baseline -- the 28 variant-closed trades) | 28 | -- | -- |
| `LOSS_AVOIDED` (baseline closed at a loss; variant's gate skipped it) | **64** | **-71.93R** | -1.12R |
| `GAIN_FORGONE` (baseline closed at a win; variant's gate skipped it) | **26** | **+67.78R** | +2.61R |
| `NO_LONGER_CENSORED` (the one AUDUSD open-baseline signal; variant never built it as a candidate) | 1 | -- | -- |

**The entire +4.15R total-R advantage for the variant arm (23.14 - 18.99) is the net of 64 avoided
losses (-71.93R) against 26 forgone gains (+67.78R)** -- a thin margin (+4.15R) built from two much
larger, nearly-offsetting pools (~140R of gross swing). This is the concrete arithmetic behind the
wide, zero-crossing bootstrap CI above: a small historical edge riding on top of a near-cancellation,
not a clearly dominant effect.

## Stop condition applied (per `docs/07`'s own pre-declaration)

The bootstrap CI spans a range many times the point estimate's own magnitude, and the by-instrument
signs disagree. **Per the protocol's own pre-declared stop condition, this sample is reported as
too small for a useful conclusion about whether the close-gate changes the original opportunity
set's outcome, at the level of the primary (per-confirmation) metric.**

## Conclusion

**What the system could know at 13:00** (`docs/05`/`docs/06`): for every 9AM confirmation in this
population, the final H4 close becomes available at the EXACT same instant as the order-placement
decision -- never strictly before, by construction of the existing confirmation window. For 66 of
119 executed cases, the fill itself lands at that same instant too, an irreducible ordering
ambiguity at 15-minute resolution.

**Effect on the original opportunity set**: requiring the close to sit strictly inside the
reference range before submitting an order would have removed 92 of 232 confirmations before the
RR floor, retained a materially higher per-trade average among the 28 that remained (+0.826R vs.
+0.161R), and produced a small net positive total-R advantage (+4.15R) built from a near-cancellation
of 64 avoided ~-1.1R losses against 26 forgone ~+2.6R gains -- but the uncertainty on this paired
difference (block-bootstrapped by whole NY trading dates, pooled across instruments) comfortably
spans zero, and the per-instrument signs do not even agree.

**What the evidence supports about this SPECIFIC decision**: the close IS knowable at the exact
decision instant for this narrow population (not "cannot be known," `docs/06`'s own finding), so a
gate like this is at least representable without widening the window -- but this historical sample
does not support a conclusion about whether applying it would have helped or hurt, only that the
two arms differ by a margin smaller than this sample's own noise. Wider trading hours, detector or
scanner changes, and any adoption decision are explicitly left for review, per the brief's own
closing instruction.
