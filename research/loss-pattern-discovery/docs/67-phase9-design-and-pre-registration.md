# Phase 9 — Design and Pre-Registration

Written after reading `run_d1_d2_d3.py`, `causal_anchor_v2.py`, `entries/model1.py`, and
`detector/backtest/population.py` in full (Unit B's required code audit), and after a EURUSD-only
pilot run of the extended `extract/funnel_reconstruction.py` adapter -- disclosed here, not hidden,
same honesty standard as Phase 7's own process note. The criteria below are fixed BEFORE running
USDCAD/AUDUSD or computing the full three-pair reconciliation.

## 1. Structural facts established by reading the code (Unit B, before any new computation)

1. **`entries/model1.py::_track_anchor`** tracks ONE anchor forward: a candle closing beyond the
   anchor's protected extreme (before the retest completes) returns `INVALIDATED`; a candle closing
   beyond the anchor's own body (`_closes_beyond`) marks "engulfed" (confirmed=True, entry
   type/price selected); once engulfed, the first candle wicking back into the anchor's body range
   sets `retest_index`; the first subsequent candle closing beyond THAT retest candle's own open
   returns `CONFIRMED`. If the loop's own `window_end` (`min(anchor_index + max_retest_lookback,
   len(candles)-1)`, `max_retest_lookback=20` for this config) is reached with no engulf, it returns
   `None`; if engulfed but never confirmed, it returns `PENDING`.
2. **`causal_anchor_v2.confirm_in_ltf_window_v2`** calls `find_first_valid_anchor` ONCE to get a
   starting anchor, then loops `_track_anchor`, retrying with `current_anchor =
   result.confirmation_index` whenever the result is `INVALIDATED` -- `while True: ...; if result is
   None or result.status != INVALIDATED: return result`. **`INVALIDATED` can therefore never be the
   function's own terminal return value** -- the only non-`None` statuses it can return to its
   caller are `CONFIRMED` or `PENDING`. Verified both by this code trace and by a deterministic
   regression test using the real, unmodified functions on a hand-built candle sequence that DOES
   invalidate internally at least once
   (`tests/test_model1_rejection_diagnostics.py::test_confirm_in_ltf_window_v2_never_returns_invalidated_as_terminal`).
   **Conclusion: `run_c1_c2._categorize_reason`'s `"model1_pending_or_invalidated"` label is a
   misnomer for D3 -- it is always PENDING, never a terminal INVALIDATED, in this pipeline.**
3. **`backtest/population.py::build_stage6_population`**'s five `_population_cuts` exclusion
   categories (`no_crt_range`, `unaligned`, `never_confirmed`, `no_key_level`,
   `confirmed_no_retest`) are each individually proven STRUCTURALLY IMPOSSIBLE for D3/C2 (cited in
   full in `extract/stage6_attrition_diagnostics.py`'s own module docstring) -- RULE AVAILABLE,
   NEVER ACTIVE. Verified empirically (EURUSD pilot): all five are exactly 0.
4. **`_kill_zone_cut`** is RULE AVAILABLE but NOT ACTIVE: `SYMBOL_CONFIG[...].kill_zone_gated ==
   False` for EURUSD/USDCAD/AUDUSD (`experimental/htf_trigger_1am_9am_backtest.py`). Verified
   empirically (EURUSD pilot): 0 exclusions.
5. **`_dedup` and `_rr_floor_cut`** (`min_risk_reward=2.0`) are the only two RULE ACTIVE AND RULE
   APPLIED mechanisms. EURUSD pilot: `_dedup` excluded 0; `_rr_floor_cut` excluded exactly
   `model1_confirmed - candidates_built` for BOTH models (507 for 1AM, 429 for 9AM) -- the ENTIRE
   Stage-6 gap, for this pair, is the RR floor alone.

## 2. Pre-registered taxonomy dimensions (Unit C)

Independent, never forced into one mutually-exclusive label:
- **Terminal category** (matches `run_c1_c2._categorize_reason` exactly, reused): `confirmed`,
  `no_model1_anchor_found`, `model1_pending_or_invalidated` (-> always PENDING per section 1.2),
  `window_empty_before_search`, `window_has_no_m15_data`.
- **Anchor probe** (only computed within `no_model1_anchor_found`, a genuinely NEW read-only probe
  of `find_first_valid_anchor`'s first call): `zero_anchors_ever` vs.
  `anchor_found_but_chain_exhausted`. Explicitly scoped: this probes only the FIRST anchor search,
  not every retry-chain restart -- a stated limitation, not a hidden one.
- **Stage-6 removal reason** (only for signals that reached `build_stage6_population`):
  `duplicate`, `kill_zone`, `rr_floor` -- attributed by the FIRST stage that removes a candidate in
  the pipeline's own fixed sequential order, never split across overlapping causes.

## 3. Pre-registered verdict criteria (Deliverable H), fixed before the full 3-pair run

### Integrity dimension

| Verdict | Criterion |
|---|---|
| `EVENT_LEVEL_RECONCILED` | `compare_identities(...)["fully_matched"]` is `True` for the pooled 3-pair identity set, AND zero duplicate `signal_id`s in either set, AND the Phase 8 funnel counts/E1 endpoint still reproduce exactly |
| `PARTIAL_IDENTITY_RECONCILIATION` | set differences or field mismatches exist but are fully explained (e.g. a documented, bounded data-quality artifact), never silently accepted |
| `UNRESOLVED_IDENTITY_MISMATCH` | an unexplained set difference or field mismatch remains after investigation |

### Selection dimension

| Verdict | Criterion |
|---|---|
| `CONFIRMATION_REJECTIONS_DOMINATE` | the Model-1-confirmation-stage gap (triggers -> confirmed) is larger, in absolute count removed, than the Stage-6 gap (confirmed -> candidates), for both models |
| `STAGE6_ATTRITION_MATERIAL` | Stage-6 removes >=20% of `model1_confirmed` for either model (a material, not necessarily dominant, share) |
| `MULTIPLE_SELECTION_MECHANISMS` | BOTH of the above hold simultaneously -- confirmation dominates in absolute terms AND Stage-6 attrition is independently material |
| `INSUFFICIENT_REJECTION_PROVENANCE` | the rejection taxonomy cannot be reconstructed reliably for a material share of events (e.g. the anchor probe or Stage-6 attribution disagrees with the pooled totals) |
| `NO_MAJOR_NEW_DIFFERENCE` | none of the above describes anything beyond what Phase 8 already established |

These two dimensions are independent and BOTH get reported -- never collapsed into one label, per
the brief's own instruction and Phase 8's precedent.

## 4. What this phase does not attempt

No contrafactual re-simulation of window duration (unchanged boundary from Phases 7-8). No
per-reason breakdown of WHY a specific never-engulfed retry chain failed beyond the one anchor
probe. No predictor, classifier, or threshold search over any rejection-stage covariate. The
confirmation-rate gap's link to window duration remains a NAMED, UNTESTED candidate mechanism, not
a demonstrated cause.
