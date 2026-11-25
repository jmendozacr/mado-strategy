# Phase 4 — Design and Pre-Registration: Failure Mode Taxonomy & Pre-Entry Feature Audit

Written and frozen before `stats/failure_mode_atlas.py` was run against real data for the first time.

## 1. What instant each stage represents, and the last M15 data known at it

Reusing, not re-deriving, what Phases 1-3 already established and tested:

| Stage | Field | Known instant | Last M15 data available |
|---|---|---|---|
| Signal activation | `features_pre_entry.activation_instant_ts` | the setup's own activation | bars closed strictly before it |
| Order placed | `features_pre_entry.order_placed_ts` | order placement | bars closed strictly before it |
| Entry execution | `operation.entry_ts` | the entry bar's OWN OPEN (MT5 convention, confirmed Phase 1-3) | bars closed strictly before `entry_ts` -- i.e. up to `entry_ts - M15_DURATION` (`behavior.post_stop_metrics.compute_atr_at_event`'s existing boundary, reused unchanged by calling it at `entry_ts`) |
| Trade open | -- | any instant between entry and exit | bars that have themselves closed by that instant |
| SL confirmed | `operation.exit_ts`, `features_at_stop.exit_ts` | the exit bar's OWN OPEN; `exit_price` is the pre-known level or that bar's own open under a gap (`detector/backtest/simulate.py:170`, confirmed Phase 3.1) -- never that bar's close | same causal rule |
| Post-SL | `post_stop_outcomes[*]` | strictly after the exit bar (`extract.post_stop_trajectory._bisect_after`) | N/A to this phase -- Layer C stays isolated (section 10 below) |

**The Phase-3.1 open-vs-close mistake is not reintroduced here.** Every new causal boundary in this
phase (`compute_pre_entry_features`, `compute_pre_stop_trajectory`) reuses `compute_atr_at_event`'s
existing `event_ts - M15_DURATION` bisect point, or excludes the entry/exit bar from the relevant
window entirely (see section 5 below) -- never a bar's close attributed to an earlier instant.

## 2. Pre-entry feature audit (Deliverable A implementation; full table in `docs/23-...`)

Kept deliberately small (per the brief's own "no catálogo enorme" instruction): volatility (ATR,
recent range), trade geometry (risk/reward/RR/cost, all already in `schema.events.FeaturesPreEntry`
or trivially derived), temporal context (NY hour via `common.ny_time`, day of week, signal-to-entry
time), and generic directional context (prior M15 return, position in recent range, prior-move
direction, distance to recent extremes) -- deliberately NOT CRT-Key-Level-dependent, to avoid
importing unverified structural assumptions this phase doesn't need.

`cost_to_risk_ratio` reuses the SAME per-symbol `trading_cost_price` from
`detector/experimental/htf_trigger_1am_9am_backtest.py::SYMBOL_CONFIG` that Phase 1's own source
inventory already confirmed the production scanner and the causal-lookahead-audit both use --
imported read-only, exactly as `research/diversified_1am_9am_rolling.py` already does elsewhere in
this repo.

## 3. Pre-SL trajectory reconstruction (Deliverable B implementation; full writeup in `docs/24-...`)

The PRIMARY MFE/MAE-pre-SL window is bars STRICTLY BETWEEN the entry bar and the exit (SL) bar --
both excluded, because each has an unresolvable intrabar order relative to the trade's own
fill/stop instant (the same class of ambiguity `ambiguous_bar` already names for SL-vs-TP ties,
applied here to entry-vs-SL). When zero such bars exist (entry and exit are the same or adjacent
bar), the path is `INSUFFICIENT` (same bar) or `AMBIGUOUS` (adjacent bars) and MFE/MAE-pre-SL are
`None` -- never fabricated as zero. Two labeled, separate sensitivity variants
(`mfe_including_entry_bar_r`, `mfe_including_exit_bar_r`) report the alternative without
contaminating the primary number.

## 4. Taxonomy threshold pre-registration (Deliverable C)

- **Favorable-excursion dimension**: `< 0.25R` = none, `0.25R-1.0R` = partial, `>= 1.0R` = material.
  `0.25R` reuses `behavior.post_stop_metrics.CONTINUATION_REVERSAL_THRESHOLD_R`, already pre-registered
  in Phase 2/3 for an unrelated purpose -- reused here for consistency with this lab's own prior
  convention, not re-tuned. `1.0R` is the position's own risk distance, a structural unit present in
  every trade by construction, not fit to any outcome.
- **Duration dimension**: reported as a CONTINUOUS distribution (median, quantiles) as the primary
  output. The only duration-related category used in any comparison is `n_observable_bars == 0`
  (zero bars exist between entry and exit) -- a data-integrity fact, not a chosen cut. Descriptive
  terciles (`failure_modes.taxonomy.duration_tercile_labels`) exist purely for the cross-tab's
  readability, are labeled explicitly as percentile bins of this specific sample, and are never used
  to threshold, select, or filter anything else.
- **Integrity dimension**: `RECONSTRUCTIBLE` / `AMBIGUOUS` / `INSUFFICIENT` -- purely structural
  (how many unambiguous bars exist), not a statistical choice at all.

No threshold in this document was chosen after inspecting a Phase-4 result.

## 5. Layer separation (section 10 of the brief)

`features/pre_entry_features.py` (Layer A) and `behavior/pre_stop_trajectory.py` +
`failure_modes/taxonomy.py` (Layer B) never read `EventRecord.post_stop_outcomes` or anything
timestamped after `exit_ts` -- confirmed by
`tests/test_pre_stop_trajectory.py::test_post_sl_changes_never_affect_the_trajectory_or_taxonomy`,
which mutates `post_stop_outcomes` and asserts the trajectory/classification are unchanged. Layer C
(post-stop behavior, Phase 2/3's own modules) is not imported by any Phase-4 module.

## 6. Selection-bias limitation carried forward (L1, unchanged)

This phase compares EXECUTED winners vs. EXECUTED losers only -- there is still no table of valid
signals that never executed (Phase 1's L1). Findings below describe executed trades, not "every
opportunity CRT produces." Noted again here per the brief's explicit instruction, not resolved this
phase.
