# Deliverable G — Recommendation for Phase 7 (not executed this phase)

One recommendation, per the brief's instruction to propose a single next investigation rather than
a menu.

## Recommended: investigate the confirmation-window-timing structural difference directly

`docs/41` verified exactly one structural difference between 1AM and 9AM's order-generation path:
the confirmation window's start hour and duration (1AM: 2h00m from 02:00 NY; 9AM: 1h30m from 09:00
NY) -- everything downstream (Model-1's entry/invalidation/SL-geometry rules) is shared, unmodified
code. This phase explicitly did NOT test whether window length or timing explains the persistent
E1 difference (`docs/42`) -- it only established that this is the one verified candidate mechanism
left standing after risk_atr (Phase 5), trading cost, and instrument (this phase) were each checked
and found not to explain it.

**A concrete, falsifiable Phase 7 design**: for each confirmed E1 (next-bar) stop, reconstruct how
far into its own model's confirmation window the Model-1 confirmation bar actually fell (e.g. as a
fraction of the window's total duration, or as a raw bar-count from window open), and the elapsed
time from `activation_instant_ts` to `order_placed_ts` (already available as
`time_from_activation_to_order_s` in `features/pre_entry_features.py`, used descriptively but never
tested as an adjustment variable in Phase 5 or this phase). Standardize the E1 gap on this variable
the same way Phase 5 standardized on `risk_atr` (common-support check first, direct standardization,
pre-declared thresholds before inspecting the result). If the gap shrinks substantially and
common support holds, that would be the first candidate mechanism with actual explanatory power;
if it does not shrink, say so plainly and close this particular mechanism as a candidate too.

## Why not the other options named in the brief

- **Obtaining lower-timeframe data to resolve the remaining ambiguity**: not justified by the
  evidence -- only 11 of 2043 events (0.54%) are genuinely indeterminate, and the sensitivity bounds
  are already under 1pp wide (`docs/40`). The marginal value of resolving those 11 cases is small
  compared to the open question of WHY the (already well-established) E1 difference exists.
- **Pre-entry features anticipating early invalidation**: a reasonable future direction but broader
  and less falsifiable than the window-timing test above; better attempted only after the window
  hypothesis is tested and either confirmed or ruled out, to avoid stacking untested candidate
  explanations.
- **Closing this research line**: not justified -- the evidence (NEXT_BAR_DIFFERENCE_PERSISTS,
  robust across 6 phases of adjustment attempts) is strong enough to warrant one more
  specific, falsifiable test before concluding the line is exhausted.

This is a recommendation only. Per the brief, Phase 7 does not start without separate, explicit
authorization.
