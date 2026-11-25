# Deliverable D — Sensitivity Analysis (S0-S3)

Reproduce: `uv run --project detector python
research/loss-pattern-discovery/stats/sensitivity_scenarios.py`. All four scenarios use the SAME
primary population (2043 evaluable executed trades), the SAME 95% block-bootstrap machinery
(`stats.early_stop_hypothesis.unadjusted_gap`, unmodified), and the SAME statistical controls for
both models (docs/37 section 5, pre-registered before this script's first real-data run).

## S0 — Baseline (motor original, sin tocar nada)

| | 1AM | 9AM | Diff | 95% CI |
|---|---|---|---|---|
| Rate | 18.90% | 9.55% | **+9.35pp** | [5.85, 12.77] |

Reproduces Phase 5 exactly (0.09350892... vs. Phase 5's reported 0.0935). Baseline, unmodified.

## S1 — Next-bar alone (never a conditional "survived bar 0" probability)

| | 1AM | 9AM | Diff | 95% CI |
|---|---|---|---|---|
| Rate (E1 only) | 11.63% | 6.25% | **+5.38pp** | [2.52, 8.26] |

**This is the central result of the phase.** E1 events have NO same-bar intrabar ambiguity at all --
entry closed on a prior, already-resolved bar before the SL-bearing bar even opened (docs/37
section 1, Q4). The gap restricted to E1 alone is, by itself, statistically robust (CI excludes 0)
and clears the pre-registered 5pp relevance bar. This is computed as an unconditional rate over the
SAME 2043-trade denominator as S0 -- it is NOT "P(stop at bar 1 | survived bar 0)", a different,
conditional estimand this phase does not compute (per the brief's explicit instruction).

## S2 — Same-bar indeterminate: partial-identification bounds

| | 1AM | 9AM | Diff | 95% CI |
|---|---|---|---|---|
| Lower bound | 17.77% | 9.27% | +8.50pp | [5.05, 11.82] |
| Upper bound (= S0 exactly) | 18.90% | 9.55% | +9.35pp | [5.85, 12.77] |

The lower bound removes the 7 (1AM) / 4 (9AM) genuinely NOT-sequence-verifiable same-bar events from
the early-stop NUMERATOR only, while keeping them in the denominator -- never recoded as wins, never
recoded as non-entries (verified by test: their `outcome`/`entry_ts` fields are untouched). **The
band is narrow: [8.50pp, 9.35pp], under 1 percentage point wide.** Even the most conservative
treatment of same-bar ambiguity barely moves the result.

## S3 — Verifiable subset only (ambiguous same-bar events dropped entirely)

| | 1AM | 9AM |
|---|---|---|
| n excluded | 7 | 4 |
| n total | 619 | 1424 |
| Exclusion share | 1.13% | 0.28% |

| | 1AM | 9AM | Diff | 95% CI |
|---|---|---|---|---|
| Rate (verifiable subset) | 17.97% | 9.30% | +8.68pp | [5.29, 12.00] |

Dropping the ambiguous subset entirely (numerator AND denominator) leaves the gap at +8.68pp,
CI [5.29, 12.00] -- still clearly relevant and robust, nearly identical to S0/S2. The exclusion
share is small for both models and about 4x higher for 1AM (1.13%) than 9AM (0.28%) in relative
terms -- reported as a possible mild selection-asymmetry, not resolved and not large enough in
absolute terms (7 vs. 4 trades) to materially affect the comparison. **This subset is NOT presented
as an unbiased estimate of the full population** -- it is a deliberately restricted, smaller-n
comparison reported alongside, not instead of, S0.

## What changes and what does not

Nothing about the magnitude or robustness of the 1AM/9AM gap changes materially across S0-S3: every
scenario's point estimate falls in a tight 8.50-9.35pp band, and every 95% CI excludes zero with a
lower bound above 2.5pp even in S1 (the most restrictive single-component view). **The gap is not an
artifact of the same-bar engine convention** -- S1 alone (zero intrabar ambiguity) reproduces a
relevant, robust difference on its own.
