# Deliverable C — Phase 2 vs. Phase 3 vs. Phase 3.1

Same 1262 eligible events, same 0.25R threshold, same horizons, same statistical criteria, same seed
(`20261124`) for the headline run in every phase -- only the control's price-causality was fixed this
round. Phase 2 numbers from `docs/09-11` (commit `4aadf26`); Phase 3 numbers from `docs/14-16`
(commit `f040a47`); Phase 3.1 from this phase's real-data run. **None of the earlier documents were
edited or overwritten.**

## Eligible population ("overall") -- unaffected by this fix, as expected

Real events' own `exit_price` was never close-referenced (confirmed in `docs/18-...`), so Phase 3.1
changes nothing about the eligible population's own numbers. 1h MAE 0.43R, P(continuation) 54.8-55.9%
across horizons, P(recovered) 22.4%/47.2%/75.3%/85.5% -- identical to Phase 3, not restated here.

## Continuation vs. control -- **the Phase 3 "correction" itself does not fully survive**

| Horizon | Phase 2 (4aadf26) | Phase 3 (f040a47) | Phase 3.1 (this phase) |
|---|---|---|---|
| 1h | +1.1pp [-2.0,+4.3] | -1.4pp [-4.5,+1.9] | -0.6pp [-3.8,+2.6] |
| 4h | -0.4pp [-3.6,+2.8] | **-4.4pp [-7.5,-1.4]** | -2.5pp [-5.8,+0.7] |
| 1d | -0.4pp [-3.6,+2.8] | **-4.4pp [-7.5,-1.4]** | -2.6pp [-5.8,+0.6] |
| 3d | -0.3pp [-3.5,+2.9] | **-4.4pp [-7.6,-1.3]** | -2.6pp [-5.8,+0.6] |

**Phase 3's statistically significant (CI-excluding-zero) continuation finding shrinks by roughly
40% and loses significance once the control's own price-causality defect is fixed.** The sign stays
negative at every horizon in every phase from Phase 3 onward, but Phase 3.1's 90% CI now includes
zero at all four horizons. This is reported exactly as found: Phase 3's "material correction" to
Phase 2 was itself partly an artifact of using the control bar's CLOSE (a price reached only after a
further 15 minutes of intrabar movement past the declared reference instant) rather than its OPEN --
inflating the apparent gap between SL events and their controls.

## Recovery to entry, 24h primary endpoint (95% CI) -- conclusion unchanged

| | Phase 2 | Phase 3 | Phase 3.1 |
|---|---|---|---|
| Diff (SL - control) | not computed this way in Phase 2 | +1.66pp [-1.67,+5.06] | **+1.11pp [-2.34,+4.53]** |
| Relevant (CI excl. 0 AND \|diff\|>=5pp)? | -- | No | **No** |

The primary, pre-registered endpoint's conclusion is unchanged: still not relevant, now with an even
smaller point estimate. **`NO_DIFFERENTIAL_RECOVERY_EVIDENCE` is confirmed, not reversed, by this
fix.**

## Recovery, secondary 1h/4h horizons -- direction and significance survive, magnitude shrinks

| Horizon | Phase 3 (90% CI) | Phase 3.1 (90% CI) |
|---|---|---|
| 1h | +5.47pp [+2.90,+8.00] | +3.72pp [+1.14,+6.21] |
| 4h | +5.39pp [+2.25,+8.45] | +3.88pp [+0.79,+7.10] |
| 1d | +1.66pp [-1.17,+4.58] | +1.11pp [-1.81,+4.01] |
| 3d | +1.11pp [-1.04,+3.47] | +1.67pp [-0.56,+3.97] |

Unlike continuation, the short-horizon recovery advantage (1h/4h) keeps its sign and keeps excluding
zero after the fix -- smaller, but not gone. Per the brief's own instruction, this is NOT promoted to
a new primary endpoint; the pre-registered 1d endpoint governs the verdict, and it stays
not-relevant.

## MAE vs. control -- Phase 3's one significant cell also disappears

| Horizon | Phase 3 | Phase 3.1 |
|---|---|---|
| 1h | **+0.056R [0.010,0.093]** | +0.015R [-0.034,+0.061] |
| 4h/1d/3d | not significant in either phase | not significant |

Phase 3's only significant MAE-vs-control cell (1h) also loses significance under the corrected
control -- the same pattern as continuation: Phase 3's apparent corrections were partly inflated by
the price-causality defect this phase fixed.
