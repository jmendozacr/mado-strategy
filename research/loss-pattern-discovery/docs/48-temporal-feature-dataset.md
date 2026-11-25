# Deliverable C — Temporal Feature Dataset

Reproduce: `uv run --project detector python
research/loss-pattern-discovery/stats/temporal_feature_dataset.py`. Primary population: same 2043
evaluable executed trades as every prior phase (778 win, 1265 loss, 4 `OPEN_CENSORED` excluded).

## Field integrity

| Field | Source | Formula | Available at | Unit | Missing treatment | Causality test |
|---|---|---|---|---|---|---|
| `confirmation_elapsed_minutes` | derived | `confirmation_bar_open - window_start_at` | at `confirmation_bar_open` (the event itself) | minutes | `None` if `model1_available_ts` missing or model unknown | `tests/test_confirmation_window_features.py::test_elapsed_and_relative_position_respect_window_duration` + real-data invariant test |
| `confirmation_remaining_minutes` | derived | `window_duration_minutes - elapsed` | same as above | minutes | same | same |
| `confirmation_relative_position` | derived | `elapsed / window_duration_minutes` | same as above | ratio, [0,1] | same | same |
| `confirmation_bar_position` | derived | `elapsed / 15` | same as above | M15 bars | same | same |
| `window_duration_minutes` | `causal_anchor_v2.old_window_fns`/`new_9am_window_fns` | model-specific, corrected (docs/47) | fixed per model, not per-event | minutes | never missing once model is known | `test_1am_window_boundaries_are_02_to_04_ny`, `test_9am_window_boundaries_are_09_to_13_ny_not_09_to_1030` |
| `order_to_fill_minutes` | derived | `entry_filled_at - order_placed_at` | at `entry_filled_at` (fill, strictly AFTER order placement -- never used as a pre-entry PREDICTOR of E1, only described) | minutes | `None` if either timestamp missing | `test_fill_never_precedes_order_placement_in_well_formed_data` + real-data invariant (`>= 0` for all 2043) |
| `risk_atr` | `features/pre_entry_features.py` (Phase 4, unchanged) | `risk_price / atr_m15_at_entry` | strictly before `entry_ts` | ATR multiples | `None` if ATR history insufficient | Phase 4's own causality tests, unchanged |
| `atr_m15_at_entry` | `features/pre_entry_features.py` (unchanged) | 14-bar ATR strictly before `entry_ts` | strictly before `entry_ts` | price | same | same |
| `risk_price` | `OriginalOperation.risk_price` (ledger) | `abs(entry_price - stop_loss)` | at order placement (planned, never changes) | price | never missing for executed trades | n/a (ledger field) |
| `planned_rr` | `features_pre_entry.planned_rr` (ledger) | `reward_price / risk_price` | at order placement | ratio | `None` if `risk_price==0` (never observed) | n/a (ledger field) |

**Only `confirmation_elapsed_minutes` (or `confirmation_relative_position`) is used as a predictor of
E1 in Deliverable E (Model 2/3).** `order_to_fill_minutes` is reported descriptively (Unit C,
Deliverable D) but deliberately NOT used as a pre-entry predictor, since it is only fully known at
`entry_filled_at` -- strictly AFTER the information this phase's endpoint (E1) concerns. This mirrors
the brief's own caution in section 5 ("No incorpores variables calculadas después de la entrada como
predictores de E1") applied literally: `order_to_fill_minutes` resolves at fill time, which is
causally simultaneous with or after the event this phase studies, so it is description, not a
predictor candidate.

## Missing data

0 of 2043 events have any `missing_reasons` entry (verified by `stats/temporal_feature_dataset.py`'s
own summary output and by the real-data invariant test) -- every executed trade in this ledger has
a reconstructible confirmation window and a known `risk_atr`/`atr_m15_at_entry` (Phase 4 already
established 100% ATR-history coverage on this same population).

## Causality boundary, restated

Every field above is knowable strictly before or at `entry_filled_at`, except `order_to_fill_minutes`
itself (known only at fill) -- which is exactly why it is excluded from the predictor set. No field
in this dataset is computed from anything timestamped after entry.
