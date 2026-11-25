# Deliverable B — Confirmation Window Reconstruction (Unit A)

Read-only inspection of `detector/causal/htf_trigger.py`,
`audit/2026-11-17-causal-lookahead-audit/causal_intrabar.py`, and
`audit/2026-11-17-causal-lookahead-audit/causal_anchor_v2.py` -- and, critically, of
`audit/2026-11-17-causal-lookahead-audit/run_d1_d2_d3.py`, the actual script that produced this
lab's source ledger. No source file is modified.

## 0. Major correction to Phase 6's own Model Construction Audit (docs/41), found before anything else

Phase 6's `docs/41-model-construction-audit.md` stated the 9AM confirmation window is
"09:00 NY, 1h30m duration" -- taken from `detector/causal/htf_trigger.py::MODEL_9AM`'s static
config. **That is not the window that generated this lab's ledger.**

Tracing the actual provenance: `extract/from_causal_lookahead_audit.py`'s own docstring names the
source as `trades_d3_c2_2015plus_run2.csv`. Reading `run_d1_d2_d3.py` directly:

```python
CONFIGS = {
    "d1": ("new", "old", "causal diagnostic -- anchor-source effect alone"),
    "d2": ("old", "new", "DIAGNOSTIC NON-CAUSAL -- do not use its R as profitability evidence"),
    "d3": ("new", "new", "agreed 9AM operative design"),
}
```

`arm_name = f"{cfg_name}_{grid}"`, written to `trades_{arm_name}_{output_label}.csv` -- so
`trades_d3_c2_...csv` is unambiguously `cfg_name="d3"`, `grid="c2"`. **D3 uses `anchor_source="new"`
and `windows_9am="new"` for BOTH models.** `windows_9am="new"` routes 9AM through
`causal_anchor_v2.py::new_9am_window_fns()`:

```python
def new_9am_window_fns():
    """Design S19 S1, corrected: the Model-1 search window is
    [true 09:00 NY, true 13:00 NY] ..."""
```

**The real 9AM confirmation window is 09:00-13:00 NY -- 240 minutes, not 90.** A separate, narrower
09:00-11:00 NY "activation window" (`activation_window_open_ts`/`activation_window_close_ts`) gates
only when the HTF sweep+Key-Level TRIGGER itself may fire, not the Model-1 confirmation deadline --
never confuse the two (brief section 4's own warning, now doubly relevant).

1AM is unaffected: `causal_anchor_v2.py`'s own comment confirms "1AM's windows are never touched,
design S19 S5" -- `old_window_fns(MODEL_1AM)` is used regardless of `windows_9am`, reproducing
`confirmation_window_utc`'s original 02:00-04:00 NY, 120-minute window exactly, as Phase 6 already
documented correctly for 1AM specifically.

**This reverses the premise both Phase 6 and this very phase's own brief stated as background: 1AM
does NOT have the longer window.** 9AM's real window (240min) is DOUBLE 1AM's (120min).

| | 1AM | 9AM (corrected) | 9AM (Phase 6's stale claim) |
|---|---|---|---|
| Window start (NY) | 02:00 | 09:00 | 09:00 |
| Window duration | 120 min | **240 min** | 90 min (wrong) |
| Window end (NY) | 04:00 | **13:00** | 10:30 (wrong) |
| Separate activation sub-window | none | 09:00-11:00 NY (120min, gates the HTF trigger only) | n/a |

Anchor-source mechanism: D3's `anchor_source="new"` means BOTH models use
`causal_anchor_v2.py::find_first_valid_anchor` (age-gated, gap-safe) for the anchor step, not the
original `detect_crt_ranges`-based search Phase 6 implicitly assumed. This is still SHARED between
models (applied uniformly, not model-specific) -- Phase 6's "entry/SL rules are shared Model-1 code"
claim survives, just via a different (also-shared) mechanism than documented. The engulf+retest
tracking (`_track_anchor`) and everything downstream (entry fill, SL/TP resolution) is unchanged
and still exactly as audited in Phase 6.

**Phase 6's `docs/41` is preserved unchanged as historical reference (its 1AM content, verdict, and
every other finding are unaffected); a correction banner now points here.**

## 1. The 11 required reconstruction facts, verified from source

1. **Feeder reference hour (NY)**: 1AM = 21:00 previous day; 9AM = 05:00 same day
   (`REFERENCE_HOUR_NY`/`REFERENCE_IS_PREVIOUS_DAY`, unchanged by D3 -- `causal_anchor_v2.py` never
   touches the reference feeder candle, only the search window and anchor source).
2. **Window start**: 1AM 02:00 NY; 9AM 09:00 NY (unchanged hour, only the END moved).
3. **Window end**: 1AM 04:00 NY; 9AM **13:00 NY** (corrected -- see section 0).
4. **Effective duration**: 1AM 120min; 9AM **240min**.
5. **UTC/NY conversion**: `causal_intrabar.py::ny_anchored_open_utc`, DST-aware via stdlib
   `zoneinfo("America/New_York")` -- reused directly in `features/confirmation_window_features.py`,
   never reimplemented.
6. **EST/EDT**: handled by the same `zoneinfo` conversion automatically; no hand-rolled DST rule
   anywhere in this reconstruction (consistent with Phase 3's own established discipline).
7. **Model-1 confirmation instant**: `confirmation_bar_open` -- the M15 bar whose own OPEN is where
   `_track_anchor`'s anchor/engulf/retest sequence resolved (`signal.confirmation_index`).
8. **Confirmation availability instant**: `confirmation_available_at` = `confirmation_bar_open +
   15min` (`causal_intrabar.py::available_at`'s own definition -- the bar's CLOSE). Equals the
   ledger's own `model1_available_ts` field exactly, verified against real data (0 of 2043 events
   recompute a different value from it, since this IS the field, not a re-derivation).
9. **Order placement instant**: `order_placed_at` -- verified EQUAL to `confirmation_available_at`
   in this pipeline (`causal_anchor_v2.py::build_causal_signal_v2` line `order_placed_ts =
   model1_available_ts`, confirmed; 0 of 2043 real events show any deviation).
10. **First M15 bar eligible for fill**: not separately recomputed this phase (unchanged from
    Phase 6's own citation of `fill_pass_c`'s `first_fillable_index = bisect_left(m15_timestamps,
    order_placed_ts)`, asserted strictly after `confirmation_index`).
11. **Effective entry instant**: `entry_filled_at` = `EventRecord.operation.entry_ts` -- the actual
    fill bar the engine's sweep found, which can be ANY bar from the first eligible one onward
    (never assumed equal to the order-placement or confirmation instant).

## 2. Self-consistency verification against real data

Reconstructing `window_start_at`/`window_end_at` purely from each event's own `confirmation_bar_open`
(= `model1_available_ts - 15min`) and NY calendar date, fed back into the ACTUAL window-boundary
function for that model (`causal_anchor_v2.old_window_fns`/`new_9am_window_fns`, never a hand-rolled
constant), checked against all 2043 executed trades:

| Check | Violations (using the STALE 90min 9AM duration) | Violations (after correction) |
|---|---|---|
| `window_start_at <= confirmation_bar_open <= window_end_at` | 1080 / 2043 (52.9%) | **0 / 2043** |
| `confirmation_elapsed_minutes` within `[0, window_duration_minutes]` | 1080 / 2043 | **0 / 2043** |
| `order_placed_at == confirmation_available_at` | 0 / 2043 | 0 / 2043 |
| `order_to_fill_minutes >= 0` (fill never precedes order placement) | 0 / 2043 | 0 / 2043 |
| Missing/unreconstructible records | 0 / 2043 | 0 / 2043 |

The 1080-violation run (before noticing the D3 window correction) is the clearest possible evidence
the stale 90-minute assumption was wrong -- every single one of those 1080 events showed
`confirmation_bar_open` falling AFTER the (wrongly narrow) computed window close, by up to ~2.5
hours, entirely consistent with the TRUE 240-minute window. After the correction, zero violations
remain, across the full population, not a sample.

## 3. What this does and does not establish

This is a reconstruction, not a re-simulation. No order, fill, or SL/TP rule is modified; nothing
here changes which trades exist or their outcomes -- only how this phase LABELS each trade's own
confirmation timing. The 1AM/9AM window-duration asymmetry itself is a verified STRUCTURAL fact, not
yet a causal or even associational claim about E1 -- that is Unit E / Deliverable E (`docs/51`).
