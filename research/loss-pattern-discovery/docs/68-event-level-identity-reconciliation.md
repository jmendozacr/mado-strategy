# Deliverable A — Event-Level Identity Reconciliation

Reproduce: `uv run --project detector python
research/loss-pattern-discovery/stats/event_identity_reconciliation_report.py` (after
`extract/funnel_reconstruction.py` has produced the artifact). Compares this phase's own
reconstructed `Trade` identities (via the SAME, unmodified `_resolve_exits`) against
`trades_d3_c2_2015plus_run2.csv`'s own `signal_id`/`entry_index`/`entry_price` columns, read by a
dedicated, isolated reader (`extract/event_identity_reconciliation.py`) that never touches the
shared Phase-1 extractor.

## Primary identity (`stable_id`): fully reconciled

| | Count |
|---|---|
| In reconstruction | 2047 |
| In ledger | 2047 |
| In both | **2047** |
| Only in ledger | 0 |
| Only in reconstruction | 0 |
| Field mismatches (model, instrument, direction, entry_index, entry_price) | 0 |

**Every single executed trade's `stable_id` (the lab's own `event_id` since Phase 1) reconciles
exactly between this phase's reconstruction and the real ledger -- identical model, instrument,
direction, entry bar index, and entry price, for all 2047 rows.** This IS event-by-event validation
in the sense the brief asks for: the primary key that actually guarantees uniqueness
(`stable_trigger_id` embeds symbol+arm+model+window_open_ts+direction) matches perfectly.

## A separate, real discovery: `signal_id` is not a safe cross-instrument key

3 `signal_id` values are shared by TWO DIFFERENT trades each (6 rows total), found by
`detect_duplicate_signal_ids` and investigated before accepting anything:

| `signal_id` | Row 1 | Row 2 |
|---|---|---|
| `298390-298391-bearish-purge_engulf-body` | USDCAD 9am 2015-07-10 | AUDUSD 9am 2015-09-02 |
| `389704-389705-bullish-purge_engulf-wick` | USDCAD 9am 2019-03-11 | AUDUSD 9am 2019-05-02 |
| `453973-453975-bullish-purge_engulf-wick` | USDCAD 1am 2021-10-07 | AUDUSD 1am 2021-11-30 |

**Root cause, verified from source**: `entries/model1.py::Model1Signal.signal_id` is built as
`f"{origin_index}-{anchor_index}-{direction}-{confirmation_type}-{entry_type}"` -- a formula using
ONLY M15 bar INDICES, which are local to each INSTRUMENT's own independently-loaded M15 series.
`signal_id` carries no instrument, no model, no date. The three collisions above are all between
TWO DIFFERENT INSTRUMENTS (USDCAD/AUDUSD) whose own M15 series happen to reach the same numeric bar
index at an unrelated calendar date -- a coincidence of two separately-indexed arrays, not a data
error.

**This is a genuine, documented limitation of the production ID scheme, not a reconciliation
failure of this phase's own work**: every single one of these 6 rows is ALSO present, correctly,
individually, under its own unique `stable_id` -- the collision never caused any row to be lost,
merged, or misattributed in this lab's own identity chain (which has always used `stable_id`, never
`signal_id`, as its primary key -- Phase 1's own extractor design). `signal_id` remains useful WITHIN
one instrument's own fill/candidate pipeline (where `fill_pass_c`/`build_stage6_population` use it
as a dict key, always scoped to a single symbol's own candidate list, never crossing instruments) --
it is simply never safe as a GLOBAL cross-instrument identifier, a fact this phase's own
investigation establishes for the first time.

## What "validated event by event" means here, precisely

`compare_identities(...)["fully_matched"] == True`: the TRUE primary key (`stable_id`) reconciles
perfectly. `detect_duplicate_signal_ids(...)` finding 3 EXPLAINED, harmless collisions is reported
as its own fact, never silently folded into, or hidden by, the primary reconciliation result.
