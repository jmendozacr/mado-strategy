# Deliverable C — Intrabar Uncertainty Report

Reproduce: `uv run --project detector python
research/loss-pattern-discovery/stats/intrabar_uncertainty_report.py`. Classifies every E0
(same-bar) confirmed-stop event's execution-order uncertainty per
`eligibility/intrabar_ambiguity.py` (criterion derived in
`docs/37-phase6-design-and-pre-registration.md` section 2).

## Within E0 (same-bar SL): sequence-verifiable vs. genuinely ambiguous

| | n (E0) | Sequence-verifiable | NOT verifiable | Multi-level ambiguity | Insufficient evidence |
|---|---|---|---|---|---|
| 9AM | 47 | 43 (91.49%) | 4 (8.51%) | 0 | 0 |
| 1AM | 45 | 38 (84.44%) | 7 (15.56%) | 0 | 0 |

**The large majority of same-bar stops are NOT genuinely ambiguous.** For 9AM, 91.5% of E0 events
have their entry-before-stop sequence established by price-path continuity from the fill candle's
own open (docs/37 section 2) -- no intrabar order invented, a direct OHLC fact. For 1AM, 84.4%. The
NOT-verifiable share is small for both models (8.5% / 15.6% of E0 respectively, i.e. 4/619 = 0.65% and
7/619 = 1.13% of each model's TOTAL evaluable population) -- small enough that Unit D's S2 bounds
stay narrow and S3's exclusion is minor (see `docs/40`).

## Category C (same-bar multi-level ambiguity) within confirmed stops: verified absent, not assumed

`same_bar_multi_level_ambiguity_violations_within_confirmed_stops = 0`. Confirms docs/37's own
prediction directly: `stop_eligibility.classify()` already routes every `ambiguous_bar=True` loss to
`AMBIGUOUS_STOP`, never `CONFIRMED_STOP` -- so this category, while real in principle, cannot
co-occur with any E0/E1/E2 event in this dataset. Not a new finding; a verification that the
pre-existing (Phase 2) eligibility taxonomy already handles it.

## Category D (gap-affected) within E1/E2

| | n (E1+E2) | Gap-affected | % |
|---|---|---|---|
| 9AM | 840 | 6 | 0.71% |
| 1AM | 330 | 0 | 0.00% |

Negligible for both models, and zero for 1AM specifically -- gap-through-the-level executions are not
a meaningful part of either model's early-stop story. (E0 is always `gap_affected=False` by
construction -- `_fill_candle_immediate_loss` never sets it, verified by test; see docs/37 Q7/Q8.)

## What this does and does not establish

This report answers "how much of E0 depends on the engine's same-bar convention vs. being
independently verifiable from OHLC" -- it does not, by itself, say whether the 1AM/9AM gap persists
once the genuinely-ambiguous subset is set aside. That is Unit D (`docs/40`).
