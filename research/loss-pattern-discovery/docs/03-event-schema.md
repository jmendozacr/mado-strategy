# Event Schema

Defined in `schema/events.py`. Five dataclasses, deliberately not merged into one flat record:

- `Identification` — stable id, source path/version, instrument, session, config id, original
  direction. Never re-derived from other fields.
- `OriginalOperation` — the trade's own entry/SL/TP, activation/order/entry/exit timestamps, outcome,
  R-multiple, and an explicitly-labeled `exit_reason` + `exit_reason_basis` (see below).
- `FeaturesPreEntry` — known strictly before `entry_ts`.
- `FeaturesAtStop` — known strictly at/by `exit_ts`.
- `PostStopOutcome` — anything depending on price *after* `exit_ts`; a list, populated only by an
  explicit later enrichment step (`extract/post_stop_trajectory.py`), never implicitly.

## Why the three-way split is structural, not just documented

`FeaturesPreEntry` has no field whose name contains "exit", "outcome" or "r_multiple" — enforced by a
test (`tests/test_schema_separation.py`). This means a future feature-engineering step that only
imports `FeaturesPreEntry` *cannot* accidentally receive a leaking field through that type, regardless
of what the function body does with it. `FeaturesAtStop` legitimately includes `exit_price`/`outcome`/
`r_multiple` because those describe the stop event itself, which **is** known at that stage; what it
must never carry is anything timestamped after `exit_ts` (checked at runtime by
`validate/integrity.py::check_temporal_ordering`, as defense in depth on top of the type-level split).

## Why `exit_reason` is inferred, not observed, and says so

The source ledger has no `exit_reason` column — `detector`'s own `backtest.Trade` dataclass has no
such field either (confirmed by inspecting `detector/backtest/simulate.py`). The only exit paths that
dataclass models are stop-loss and take-profit (no time-based exit). So `exit_reason` is derived from
`outcome` under that documented assumption, and every record's `exit_reason_basis` field says
`INFERRED_BINARY` — never silently presented as if the source had stated it directly. If a future
source does carry a real `exit_reason` column, that extractor should set `exit_reason_basis =
OBSERVED` and this inference path should not be reused for it.

## Right-censoring (`outcome = open`)

A trade still running when the source ledger was generated has `exit_ts = exit_price = r_multiple =
None` — never `0.0` or a fabricated value. `OriginalOperation.exit_price`/`r_multiple` and
`FeaturesAtStop.exit_price`/`r_multiple` are `Optional[float]` for exactly this reason. Validators and
the descriptive-summary script both explicitly skip `None` rather than letting a numeric comparison
silently coerce it.

## `PostStopOutcome` convention

MFE/MAE are computed relative to the **original trade's own direction** — i.e. as if the original
trade were still open past its exit. For a bullish original trade, MAE grows if price keeps falling
(continuing the move that caused the SL) and MFE grows if price reverses back up. This is *not* the
P&L of a hypothetical new post-SL trade; it only characterizes what price did, in the original
direction's frame. They accumulate across increasing horizons (the `1d` figure already includes
everything seen by `4h`). `censored=True` means the M15 data ran out before reaching that horizon —
the record is kept with that flag, never dropped or treated as "no movement."
