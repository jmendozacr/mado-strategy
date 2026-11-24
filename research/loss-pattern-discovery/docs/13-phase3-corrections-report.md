# Deliverable A — Phase 3 Corrections Report

Independent review of commit `4aadf261371ad1973ebbd397030930f46789f901` found three concrete defects.
All three are fixed in this phase; none of the original source files, D3/C2 experiments, or `detector/`
code were touched.

## Defect 1 — Control group never actually matched by comparable hour (`control/sampling.py`)

**Root cause**: `_candidate_pool()` built its candidate set from `instrument` + `period_bucket` alone.
`session_label` (the real event's origin model, 1AM or 9AM) was copied onto the resulting
`ControlEvent` for display, but was never used to filter which timestamps were eligible as a control.
A 9AM-model stop whose actual execution happened mid-afternoon NY time could be matched against a
control drawn from the middle of the Asian session.

**RED proof** (`tests/test_control_sampling.py::test_RED_naive_pool_would_assign_a_9am_event_a_non_comparable_ny_hour_control`):
reproduces the Phase-2 pool construction inline (instrument+period only, no hour filter) against a
4-week synthetic M15 series and shows its candidate set spans more than 10 distinct NY hours-of-day —
confirming nothing ever narrowed it.

**Fix**: `origin_model` (the generating model label) and `actual_stop_time_ny` (the real event's own
`exit_ts`, converted to NY wall-clock time via `common/ny_time.py`'s `zoneinfo`-backed, DST-correct
conversion — never a hand-rolled EST/EDT rule) are now tracked as separate fields. Candidates are
grouped into quarter-hour NY buckets per stratum and gathered only from within
`NY_HOUR_TOLERANCE_HOURS = 1.0` of each real event's own `actual_stop_time_ny`, pre-declared before
any Phase-3 result was inspected.

**GREEN proof**: `test_controls_are_within_the_ny_hour_tolerance_of_their_matched_event` (every control
in a 6-event, 8-week synthetic run is within the tolerance) and the real-data run's
`audit_match_quality()` report (Deliverable C) confirms `within_tolerance_pct` at scale.

**Match-quality tiers added**: `MATCHED` (fresh candidate), `MATCHED_WITH_REPLACEMENT` (stratum+hour
pool exhausted, reused), `UNMATCHED` (zero candidates at all — reported, never silently dropped or
given a worse match). Proven by `test_match_tier_reports_replacement_when_the_hour_window_pool_is_exhausted`
and `test_unmatched_events_are_reported_not_silently_dropped_or_relaxed`.

**Secondary fix found while fixing this one**: the per-stratum candidate pool had no shuffle, so an
exact ATR tie (common on synthetic data, not impossible on real data) always resolved to the same
index regardless of `seed` — `test_different_seeds_can_produce_different_controls` caught this.
Candidates are now shuffled (seeded) before capping at `pool_size`, per quarter-hour bucket.

**`target_distance` added**: a control's synthetic target now also carries `target_distance =
abs(entry_price - exit_price)` of its matched real event, separate from `risk_price` — the two can
differ under a gap fill (`test_target_distance_can_differ_from_risk_price_under_a_gap_fill`). The
general Atlas re-run (Deliverable B) still uses `risk_price` for comparability with Phase 2's own
convention; the recovery-specific analysis (Deliverable D) uses `target_distance`, since that
endpoint's question is specifically about the distance actually traveled to the real entry price.

## Defect 2 — Post-stop metric timing (`behavior/post_stop_metrics.py`)

**Defect A root cause**: `raw_max_price`/`raw_min_price` were seeded from the first post-exit candle
BEFORE checking whether that candle belonged to the horizon being measured. A weekend-gap candle
landing just past a short horizon's boundary could leak its high/low into that horizon's result even
though the `while` loop's own body never executed for it.
**Fix**: both start `None`, set only from a candle actually included in the loop.
**GREEN proof**: `test_first_bar_outside_a_short_horizon_does_not_contaminate_it`.

**Defect B root cause**: a candle's `timestamp` is its OPEN instant (confirmed MT5 convention, already
relied on by this repo's own causal-lookahead-audit fixes); its high/low/close are not fully known
until `timestamp + M15_DURATION`. The inclusion test was `candle.timestamp <= horizon_ts`, using a
candle's own not-yet-closed OHLC up to ~15 minutes before it was knowable. The identical leak existed
in `compute_atr_at_event`'s pre-event lookback (the exit bar's own close was used in its ATR, even
though that close isn't known until after the exit itself).
**Fix**: inclusion is now `candle.timestamp + M15_DURATION <= horizon_ts`; the ATR lookback excludes
any bar not fully closed strictly before the event instant.
**GREEN proof**: `test_horizon_boundary_falling_inside_an_open_bar_excludes_that_bar`,
`test_fully_observed_horizon_with_no_gaps` (only 3 of 4 bars count for a 1h horizon, the 4th not yet
closed by the boundary), `test_atr_excludes_the_event_bars_own_not_yet_closed_candle`.

**Defect C root cause**: `censored` was `last_bar_ts < horizon_ts` against the series' own last
timestamp — conflating genuine dataset exhaustion with an ordinary weekend/holiday closure that is
simply bridged by later, real data.
**Fix**: `censored` now means ONLY that the series itself ran out (`idx` reached the end AND the last
bar used closed before `horizon_ts`) — a weekend gap with more data afterward is fully observed, never
censored. `weekend_gap_spanned` (Friday-start, 40-60h gap) and `unexpected_gap_spanned` (anything else
longer than 20 minutes) are reported as separate, informational flags via `classify_gap()`.
**GREEN proof**: `test_censored_only_means_true_data_exhaustion_not_weekend_closure`,
`test_gap_classification_distinguishes_weekend_from_unexpected`,
`test_unexpected_midweek_gap_is_flagged_separately_from_weekend`.

**Consequence for Phase 2's own `p_recovered_to_entry`**: `stats/atlas.py`'s recovery indicator used
to count `recovered_to_entry_price=False` as a confirmed non-recovery unconditionally, even when the
underlying horizon was genuinely censored. Fixed (`_recovery_indicator`): a censored non-recovery is
now excluded (`None`), never counted as a confirmed absence. Given censoring affects <0.3% of events
(Phase 2's own data-quality doc), the numeric effect on the headline recovery percentages is expected
to be negligible — quantified in Deliverable B's before/after table.

**Executable-entry fields added** (Section 5's A/B/C/D distinction): `recovery_touch_bar_open`
(historical contact), `recovery_confirmed_at` (causal confirmation, `touch_bar_open + M15_DURATION`),
`recovery_first_actionable_at` (first actionable instant, coincides with `recovery_confirmed_at` at
M15 granularity), `recovery_gap` (the touch candle's own open was already past the level — a gap, not
a clean intrabar touch), `recovery_reference_price`. Proven by
`test_recovery_not_confirmed_while_touch_bar_still_open_for_that_horizon` and
`test_recovery_gap_flagged_when_price_jumps_through_entry_level`.

## Defect 3 — Reported-percentage denominator inconsistency

Phase 2's report used "99.4%" in sentences that named "1,265 losses" as the denominator. The actual
arithmetic:

- `1262 / 1265` (confirmed stops over losses alone) = **99.76%**.
- `1262 / 1269` (confirmed stops over losses + open-censored) = **99.45%**, which rounds to the
  "99.4%" that was printed — but 1269 was never named as the denominator in the surrounding prose.

**Fix**: every restated figure in this phase's docs uses an explicit denominator in the same sentence
(e.g. "1262 of 1265 losses (99.76%)"), and open-censored trades are never silently folded into a
"confirmed stop rate" statement. The real counts are unchanged by this fix — only the prose is
corrected.

## What did NOT change

No change in this phase touched `detector/`'s exit-resolution rules, the eligibility classifier's
category logic, or any original source file — confirmed by
`test_phase3_fixes_do_not_alter_original_execution_rules` (eligibility regression) and
`test_source_files_are_never_modified_by_the_pipeline` (Phase 2, still passing). The real eligibility
counts (1262 confirmed / 0 stop-after-partial / 0 other / 3 ambiguous / 4 open) are identical before
and after this phase, since no fix touched `eligibility/stop_eligibility.py`.
