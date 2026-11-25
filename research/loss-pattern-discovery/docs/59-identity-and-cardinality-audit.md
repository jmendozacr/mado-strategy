# Deliverable C — Identity & Cardinality Audit

## Identifiers, traced through every stage

| Stage | Identifier | Assigned by | Survives to later stages as |
|---|---|---|---|
| Trigger (window, direction) | `stable_trigger_id` = `f"{symbol}|{arm}|{model_name}|{window_open_ts.isoformat()}|{direction}"` | `run_d_c2` (`stable_trigger_id(...)`), ONE per (window, direction) pair, computed even for zero-signal outcomes | stored alongside EVERY `(CausalSignalRecord, sid)` tuple in `records_with_ids`, including unconfirmed ones |
| Confirmed signal | `signal_id` (from `Model1Signal`, assigned deep inside `entries/model1.py`'s own tracked-anchor logic, reused unmodified) | Model-1's own confirmation machinery | becomes the KEY of `model_by_sig`/`stable_by_sig`/`order_placed_by_sig`/`confirmation_idx_by_sig` (all built from `aligned_records`) |
| Candidate | same `signal_id` (`Candidate.signal_id`, carried through `build_stage6_population` unmodified) | `build_stage6_population` | used by this phase's adapter to look up `model_by_sig.get(c.signal_id)` |
| Filled/trade | same `signal_id` (`Trade.signal_id`) | `_resolve_exits` (carries the candidate's own `signal_id` onto the `Trade`) | the trades CSV's own `signal_id` AND `model` columns -- both already correct and reliable in the original ledger, confirmed by Deliverable B's reconciliation |
| Extracted event | `stable_id` (CSV's own `stable_trigger_id`, read verbatim) == `EventRecord.identification.event_id` | `extract/from_causal_lookahead_audit.py` (Phase 1, unchanged) | the lab's own primary key for every downstream module (Phases 2-7) |

**The identity chain is intact and traceable end-to-end**: `stable_trigger_id` (assigned even for
trades that never confirm) -> `signal_id` (assigned only once Model-1 confirms) -> same `signal_id`
on the `Candidate` -> same `signal_id` on the `Trade` -> `stable_id`/`event_id` in this lab's own
extracted ledger. No stage re-derives or guesses an identity; each either carries the prior stage's
ID forward unchanged or has none yet (never-confirmed triggers have a `stable_trigger_id` but no
`signal_id`, by construction -- they never reach Model-1's own ID-assignment step).

## Duplicates: legitimate vs. accidental

- **Legitimate**: `candidates_built`/`filled`/`never_filled`/`skipped_no_placement` appear IDENTICAL
  on both the `1am` and `9am` rows of the same (pair, arm) in the funnel CSV -- this is a genuine
  structural duplication (Deliverable A), not a data-entry error, caused by merging one pooled dict
  into two rows. Legitimate (explained, reproducible, now corrected in this lab's own derived
  reconstruction).
- **Searched for, not found**: duplicate `signal_id`s within a single symbol's trades CSV (would
  indicate the same confirmed signal producing two Trade rows) -- not observed; `_resolve_exits`
  produces exactly one `Trade` per filled candidate, and `process_arm`'s `trades.sort(key=lambda t:
  (t.entry_index, t.signal_id))` would not hide a true duplicate from a `Counter`-based check
  (implemented as a test, `test_funnel_reconciliation_detects_duplicate_event_ids`).
- **Searched for, not found**: an event whose `model` cannot be resolved (e.g. a `signal_id` absent
  from `model_by_sig`) -- every trade in the real ledger has a non-empty `model` field matching
  `{"1am", "9am"}` exactly (verified: `Deliverable B`'s per-model sums account for all 2047 rows
  with none left over as "unknown").

## Multi-signal / multi-direction windows, handled without inventing a 1:1 relationship

A single (model, NY-day) window can produce 0, 1, or 2 triggers (one per direction) --
`triggers_with_key_level` is NOT bounded by `windows_considered`, and indeed exceeds it for every
model/pair observed (e.g. EURUSD 1AM: 4199 triggers from 3085 windows -- more than one trigger per
window on average, confirming both directions regularly produce a credited trigger within the same
window). This phase never divides `model1_confirmed` or `triggers_with_key_level` by
`windows_considered` and calls the result "P(confirmed | window)" -- that would conflate a
direction-level numerator with a window-level denominator (docs/57 section 1's own rule). Where a
window-level rate IS reported (Deliverable D), it is explicitly framed as "average triggers per
window" (a rate that can exceed 1), never as a per-window probability.

## What remains unreconstructed (disclosed, not hidden)

`build_stage6_population`'s own internal exclusion reasons (duplicate signal dedup, kill-zone
filter, RR floor) are not broken out per-model or per-reason this phase -- only the NET effect
(`model1_confirmed` minus `candidates_built`, Deliverable B) is visible. A per-reason breakdown
would require instrumenting that function's internals (beyond a read-only call), out of this
phase's scope.
