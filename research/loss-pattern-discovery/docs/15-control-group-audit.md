# Deliverable C — Control Group Match-Quality Audit

Real-data run, 1262 eligible events, `uv run --project detector python research/loss-pattern-discovery/stats/atlas.py`
(`control/sampling.py::audit_match_quality`, seed `20261124`, `pool_size=400`).

## Match outcome

| | Count | % |
|---|---|---|
| Matched (fresh candidate) | 1262 | 100.0% |
| Matched with replacement | 0 | 0.0% |
| Unmatched | 0 | 0.0% |

Every eligible event found a fresh, never-reused control candidate within its NY-hour window for this
dataset's size -- the 400-candidate-per-quarter-hour-bucket pool was never exhausted. Unmatched events
(had there been any) would have been reported individually by instrument/period/reason -- the
mechanism exists (`UnmatchedEvent`) and is tested
(`tests/test_control_sampling.py::test_unmatched_events_are_reported_not_silently_dropped_or_relaxed`),
it simply had nothing to report this run.

## Do controls actually share the agreed characteristics?

| Characteristic | Result |
|---|---|
| NY-hour alignment | mean absolute difference **0.58h**, max **1.0h** (the declared tolerance boundary) -- **100% of controls within `NY_HOUR_TOLERANCE_HOURS=1.0`** |
| Volatility (ATR) | mean absolute difference **2.69e-7** (effectively exact -- nearest-ATR matching within the hour-filtered pool is working as designed) |
| Instrument | 0 mismatches (controls are always drawn from the SAME instrument's series as their matched event, by construction) |
| Period bucket | 0 mismatches (candidates are only drawn from the matched event's own period bucket, by construction) |
| Direction | 0 mismatches (direction is inherited from the matched event, by construction) |

**This is the direct evidence that Phase 2's claim did not hold and now does.** Phase 2's own
documentation (`docs/07-...`, commit `4aadf26`) asserted controls were matched by "instrumento, sesión,
dirección, período histórico, volatilidad" -- but `_candidate_pool()` never filtered by hour at all
(`docs/13-...`'s Defect 1 root-cause). Re-running that exact (unfiltered) logic
(`tests/test_control_sampling.py::test_RED_naive_pool_would_assign_a_9am_event_a_non_comparable_ny_hour_control`)
shows candidate hours spanning more than 10 distinct values with no restriction whatsoever. The fixed
version now demonstrably restricts every control to within 1 hour of its matched event's own actual
stop time, confirmed above at 100%.

## Episode overlap

`EXCLUSION_BUFFER = 4h` (unchanged from Phase 2) drops any candidate within 4 hours of ANY real SL
event of the same instrument before hour-filtering or ATR-matching -- so the same short-term market
episode cannot trivially appear in both the SL group and its own control. This is a deliberate,
pre-declared choice, not re-tuned this phase.

## Known residual limitations (carried from Phase 2's L8/L9, still true)

- The control borrows direction/risk/target_distance from its matched real event rather than deriving
  an independent "what would a typical trade look like here" rule -- it tests "is post-SL behavior
  different from an ordinary, matched moment," not "every possible alternative trade design."
- The 400-candidate-per-bucket pool is a finite, seeded sample, not an exhaustive search --
  demonstrated sufficient this run (0 unmatched, 0 replacement) but not guaranteed to remain so if the
  eligible population or exclusion buffer changes materially in a future phase.
