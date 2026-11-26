# Deliverable C — Event Identity & Causal Availability Audit

Reproduce: `uv run --project detector python -c "..."` calling
`extract.confirmation_path_identity_audit.reconcile_with_ledger` against
`extract.from_causal_lookahead_audit.extract`'s own real ledger records and
`load_all_symbol_paths()`'s merged, per-symbol reconstructed paths.

## Identity reconciliation (full, real data, all 3 pairs)

| | Count |
|---|---|
| Ledger (executed trades) | 2047 |
| Matched to a reconstructed confirmation path | **2047** |
| Missing a path | 0 |
| Cross-instrument mismatch | 0 |
| Duplicate `event_id` (`stable_id`) | 0 |
| Open (censored) trades, matched | 4 of 4 |

**Every one of the 2047 executed trades links to its own real confirmation path, by `stable_id` --
the lab's primary key since Phase 1, re-confirmed by Phase 9 as the only safe cross-instrument
identifier.** No global join was ever done on `signal_id` alone (Phase 9's own 3 harmless
cross-instrument `signal_id` collisions are irrelevant here, since `stable_id` already disambiguates
them). The 4 OPEN (censored) trades keep their own identity and matched status explicitly, never
silently excluded from this reconciliation (though they remain excluded from the E1 primary
population, per Phase 5's own convention, reused unmodified).

## Reconstruction coverage over the full confirmed population

| Symbol | Confirmed signals | Reconstructed | Unreconstructed |
|---|---|---|---|
| EURUSD | 1719 | 1719 | 0 |
| USDCAD | 1803 | 1803 | 0 |
| AUDUSD | 1594 | 1594 | 0 |
| **Total** | **5116** | **5116** | **0** |

5,116 matches Phase 9's own pooled confirmed total exactly (1,805 for 1AM + 3,311 for 9AM). 100%
reconstruction coverage -- no confirmed signal's path was silently dropped.

## Causal availability, verified (not merely asserted)

Every feature this phase computes (`internal_invalidation_count`, `confirmation_attempt_count`,
`first_anchor_found_at`, `final_anchor_found_at`) is a function of candles up to and including
`signal.confirmation_index` only:

- `trace_confirmation_path_for_record` never receives, and never reads, any field from the
  record's own OUTCOME (fill status, exit, P&L) -- its signature accepts only `record.direction`
  and `record.activation_instant_ts`, both already-existing PRE-ORDER fields the real pipeline
  itself produces for every record, confirmed or not.
- `test_never_reads_candles_beyond_the_window_end_even_when_poisoned`
  (`tests/test_confirmation_path_diagnostics.py`) proves this empirically: candles appended AFTER
  the true confirmation point, engineered to flip the result if read, change nothing.
- E1 itself (Deliverable E) is computed from `eligibility.stop_timing_decomposition.
  classify_all_timing`, which depends on `OriginalOperation`'s own exit/outcome fields --
  categorically separate inputs from the confirmation-path features, joined only by `stable_id`
  AFTER both are independently computed, never by sharing state.

**No variable observed after a rejection or after order placement is ever used to reconstruct, or
retroactively adjust, a confirmation path.** This mirrors Phase 9's own Layer 1-4 causal-
availability dictionary (`docs/73`): `internal_invalidation_count` is a Layer 2 (During
Confirmation) fact, never a Layer 4 (After Fill) one.
