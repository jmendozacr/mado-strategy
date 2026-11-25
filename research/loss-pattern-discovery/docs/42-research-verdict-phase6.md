# Deliverable F — Research Verdict (Phase 6)

## Verdict: `NEXT_BAR_DIFFERENCE_PERSISTS`

Per the criteria pre-declared in `docs/37-phase6-design-and-pre-registration.md` section 6, decided
BEFORE Units B-D were run:

| Criterion | Pre-declared condition | Observed | Met? |
|---|---|---|---|
| `NO_ROBUST_EARLY_STOP_DIFFERENCE` | S0 CI includes 0, or \|gap\| < 5pp | S0 = +9.35pp, CI [5.85, 12.77] | No |
| `MOSTLY_SAME_BAR_ENGINE_DEPENDENT` | S0 relevant; Gap_E1 (S1) CI includes 0 OR \|Gap_E1\| < 5pp | S1 = +5.38pp, CI [2.52, 8.26] -- CI excludes 0 AND \|gap\|>=5pp | No |
| **`NEXT_BAR_DIFFERENCE_PERSISTS`** | S0 relevant; Gap_E1 (S1) ALSO CI excludes 0 AND \|Gap_E1\| >= 5pp | **Exactly matches** | **Yes** |
| `INSUFFICIENT_INTRABAR_INFORMATION` | NOT-verifiable share of E0 > 50% for either model | 15.6% (1AM) / 8.5% (9AM) -- far below 50% | No |

`NEXT_BAR_DIFFERENCE_PERSISTS` is the first (and only) criterion in the pre-declared order that
cleanly applies.

## Justification, with numbers

1. **The gap is real and robust at the aggregate level (S0)**: +9.35pp unadjusted (reproducing
   Phase 5 exactly), CI [5.85, 12.77], far above the 5pp relevance bar.
2. **The gap is NOT concentrated in the same-bar (E0) component.** `Gap_E0` alone is +3.97pp, CI
   [1.79, 6.27] -- its CI excludes 0 but it falls BELOW the 5pp relevance bar on its own (`docs/38`).
   `Gap_E1` alone is +5.38pp, CI [2.52, 8.26] -- LARGER than `Gap_E0`, and it independently clears
   both the statistical and relevance bars.
3. **E1 has zero same-bar intrabar ambiguity by construction** (docs/37 section 1, Q4): entry closes
   on a bar strictly before the SL-bearing bar. The engine's conservative same-bar convention (the
   mechanism the brief asks this phase to audit) plays NO role in the E1 comparison at all. A
   relevant, CI-robust gap restricted to E1 alone is therefore evidence the association is not an
   artifact of that specific engine convention.
4. **The same-bar (E0) component is mostly NOT genuinely ambiguous either**: 91.5% (9AM) / 84.4%
   (1AM) of E0 events have their entry-before-stop order established by price-path continuity from
   the fill candle's own open (`docs/39`) -- not an invented order, a direct OHLC fact. Only 4 (9AM)
   / 7 (1AM) events, out of 2043 total, are genuinely indeterminate.
5. **Sensitivity bounds are narrow, not wide** (`docs/40`): even the most conservative treatment of
   those 11 indeterminate events (S2 lower bound, S3 exclusion) moves the point estimate only from
   9.35pp to 8.50-8.68pp -- a band under 1pp wide. `INSUFFICIENT_INTRABAR_INFORMATION` would require
   a band wide enough to blur the other verdicts; it does not.

## What this verdict does and does not claim

This verdict states that the 1AM/9AM early-stop association **survives the specific audit this
phase set out to run**: it is not materially dependent on the engine's same-bar SL-wins-ties
convention, because the component with zero same-bar ambiguity (E1) reproduces a relevant, robust
difference on its own, and the same-bar component itself is mostly independently verifiable rather
than genuinely ambiguous.

It does **not** claim:
- That `origin_model` causes the difference (unchanged from Phase 5's own caution -- `origin_model`
  is not randomly assigned).
- That any tradable edge exists. This remains a historical association on previously-examined data
  (2015-2026), never genuine out-of-sample validation.
- That the one verified structural difference between models (confirmation window timing,
  `docs/41`) is the mechanism -- that is named as a candidate for a future, explicitly causal unit,
  not established here.
- That trading cost, risk_atr, or instrument explain the gap -- all three were evaluated and, so
  far as this phase and Phase 5 tested them, do not (`docs/41` Unit F).
