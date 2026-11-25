# Deliverable F — Causal Availability Dictionary

**Governing rule**: a variable observed after a rejection can never be used as a predictor of
that rejection. This dictionary assigns every variable this phase (and Phases 5-8) touches to the
earliest layer at which it exists, so later analysis cannot accidentally condition a rejection's
explanation on information that only exists for survivors.

## Layer 1 -- At Trigger (exists for every trigger, rejected or not)

- Trigger/activation timestamp (`activation_instant_ts`), confirmation window open/close
  (`window_open_ts`/derived `window_end`).
- Direction (`record.direction`).
- Credited key level (`CausalTrigger.credited_level`) -- always non-`None` by construction
  (Deliverable C).
- Instrument, model label (`1am`/`9am`), period bucket.
- `stable_trigger_id` (the phase's own primary key, exists for every trigger unconditionally).

## Layer 2 -- During Confirmation (exists for every trigger; VALUE depends on what the
## Model-1 state machine reaches, but the ATTEMPT itself is universal)

- Anchor-probe result (`zero_anchors_ever` / `chain_exhausted`) -- Deliverable B's first-anchor
  probe, defined for every trigger regardless of outcome.
- Rejection category (`no_model1_anchor_found` / `model1_pending_or_invalidated` /
  `window_empty_before_search`) OR confirmed.
- `signal_id`, `confirmation_type`, `entry_type`, `retest_index` -- these exist ONLY for triggers
  that reach at least the engulf stage; a `window_empty_before_search` or `zero_anchors_ever`
  rejection never produces any of these fields. **Using their presence/absence to explain a
  rejection would be circular** -- their absence IS part of the rejection, not an independent
  predictor of it.

## Layer 3 -- At Order Placement (exists ONLY for CONFIRMED signals that survive Stage 6's
## `_population_cuts` -> `_build_candidate` -> `_dedup` -> `_kill_zone_cut` sequence, up to the
## point `_rr_floor_cut` evaluates them)

- Planned risk-reward ratio (the `_rr_floor_cut` input) -- **does not exist for any rejected
  trigger** (no anchor, pending, or window-empty never reach `_build_candidate`). It is Layer-3
  information computed from Layer-2 survivors' own swing structure.
- `atr_at_order_placement`, `planned_risk_atr_at_order_placement` (Phase 5/8 covariates) --
  likewise exist only for Stage-6 candidates.
- Candidate's own `signal_id`-keyed dedup status.

**Consequence for this phase's own findings**: Deliverable C's "100% of Stage-6 attrition is
`_rr_floor_cut`" is a Layer-3 fact about CONFIRMED signals only. It says nothing about, and cannot
be used to explain, why a trigger was rejected at Layer 2 in the first place -- the RR ratio of a
trigger that never confirmed is not a defined quantity.

## Layer 4 -- After Fill (exists ONLY for Stage-6 candidates that are additionally fill-eligible
## and actually fill)

- Entry index, entry price, actual fill timing.
- E0-E4 timing decomposition (Phase 6), intrabar ambiguity classification (Phase 6).
- Confirmation-window-position features (Phase 7): `ConfirmationWindowFeatures`.
- Trade outcome, exit reason, E1 endpoint (loss-after-early-favorable-move).

**Consequence**: every quantity Phases 5-7 analyzed (timing position, E0-E4, intrabar ambiguity)
is Layer-4-or-later information. None of it can explain, or be checked against, why a trigger
was rejected at Layer 2 (confirmation) or Layer 3 (Stage 6) -- those triggers never reach Layer 4
at all, so no Layer-4 variable is even defined for them.

## Why this dictionary matters for this phase's own claims

Every rejection-taxonomy count in Deliverable B is built entirely from Layer 1 and Layer 2
variables (trigger identity, anchor-probe result, rejection category) -- never from Layer 3 or 4.
Every Stage-6 attribution in Deliverable C is built entirely from Layer 3 variables, applied only
to the Layer-2 survivors for whom Layer 3 is defined. No rejection category in this phase is ever
explained using a variable that only exists for later-stage survivors.
