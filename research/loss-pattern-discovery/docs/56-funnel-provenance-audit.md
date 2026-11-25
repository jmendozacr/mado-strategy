# Deliverable A — Funnel Provenance Audit

Read-only inspection of `audit/2026-11-17-causal-lookahead-audit/run_d1_d2_d3.py`,
`run_c1_c2.py`, `causal_intrabar.py`, `causal_anchor_v2.py`, and `detector/backtest/simulate.py`.
No file is modified; checksums below prove it.

## Confirmed scope: D3 + C2 only

`trades_d3_c2_2015plus_run2.csv` / `funnel_2015plus_run2.csv` come from `run_d1_d2_d3.py`'s
`CONFIGS["d3"] = ("new", "new", "agreed 9AM operative design")` (`anchor_source="new"`,
`windows_9am="new"`, confirmed in Phase 7's `docs/47`) run over `RUN_FN_BY_GRID["c2"] = run_d_c2`
(the NY-anchored feeder grid). D1/D2/C1 counts are never read or mixed into this phase's analysis.

## The root cause: `candidates_built`/`filled`/`never_filled`/`skipped_no_placement` are
## pooled-arm aggregates, not per-model counts

Traced exactly, line by line:

```python
# run_c1_c2.py::process_arm -- called ONCE per (symbol, arm), given records_with_ids
# that already pool BOTH models' (record, stable_id) pairs together.
aligned_signals = [rec.aligned for rec, _sid in aligned_records]   # BOTH models pooled
population = build_stage6_population(aligned_signals, m15, config, swings=swings)
filled, never_filled, skipped_no_placement = ci.fill_pass_c(population.candidates, ...)
...
return trades, rows, {
    "candidates_built": len(population.candidates),    # POOLED over 1am+9am
    "filled": len(filled), "never_filled": never_filled, "skipped_no_placement": skipped_no_placement,
}
```

```python
# run_d1_d2_d3.py::main -- the SAME pop_stats dict is merged into EVERY model's own funnel row:
trades, rows, pop_stats = base.process_arm(...)
for model_name, c in counters.items():
    funnel_rows.append({"pair": symbol, "arm": arm_name, "model": model_name,
                         **c.to_dict(), **pop_stats})
```

`**pop_stats` is literally the same dict object's contents spread into BOTH the `1am` and `9am`
rows for a given (symbol, arm) -- there is no model-level disaggregation anywhere in this code
path. This is EXACTLY what the real CSV shows: EURUSD's 1am and 9am rows both read
`candidates_built=783, filled=636` -- not a coincidence, a structural duplication, confirmed from
source, not inferred from the data alone.

## Field-by-field provenance

| Field | Producer | Aggregation level | Unique per window/trigger? | Model-specific? |
|---|---|---|---|---|
| `windows_considered` | `FunnelCounters` (one instance per model, per symbol/arm loop iteration) | one NY-day window | 1 per window (incremented once, after the reference check passes) | **Yes** |
| `reference_incomplete_skipped` | `FunnelCounters` | one NY-day window | 1 per window (disjoint from `windows_considered` -- incremented instead, via `continue`) | **Yes** |
| `swept_bearish_only`/`swept_bullish_only`/`swept_both`/`swept_neither` | `FunnelCounters.record_sweep` | one NY-day window | exactly 1 of these 4 per window counted in `windows_considered` | **Yes** |
| `triggers_with_key_level` | `FunnelCounters` | one (window, direction) pair | 0, 1, or 2 per window (one per direction with a credited trigger) | **Yes** |
| `model1_confirmed` | `FunnelCounters` | one (window, direction) pair | subset of `triggers_with_key_level` | **Yes** |
| `zero_signal_reason_categories` | `FunnelCounters.zero_signal_reasons` (a `Counter`) | one (window, direction) pair | `model1_confirmed + sum(categories) == triggers_with_key_level` | **Yes** |
| `candidates_built` | `process_arm`'s own `pop_stats`, from `len(population.candidates)` | **the whole (symbol, arm) call, BOTH models pooled** | one per `Candidate` surviving `build_stage6_population`'s own exclusions | **No -- duplicated verbatim onto both model rows** |
| `filled` | same `pop_stats` | pooled | one per candidate that received a fill | **No -- duplicated** |
| `never_filled` | same `pop_stats` | pooled | one per eligible-but-unfilled candidate | **No -- duplicated** |
| `skipped_no_placement` | same `pop_stats` | pooled | one per candidate whose order-placement timestamp never maps to an M15 bar | **No -- duplicated** |

## Possible duplication, confirmed in the real CSV

EURUSD d3_c2: both the `1am` and `9am` rows show `candidates_built=783, filled=636` identically.
Verified for all three pairs (USDCAD: both rows `854, 696`; AUDUSD: both rows `887, 715`) -- the
duplication is total and consistent with the code trace above, not a one-off CSV artifact.

## Reconstruction limitations

No candidate-level, order-level, or fill-level file is persisted by the original pipeline -- only
the final EXECUTED-trade rows (`trades_d3_c2_...csv`, one row per `Trade`, WITH a reliable
per-model `model` column, since each `Trade` traces back to exactly one `signal_id` via
`model_by_sig`) and the aggregate funnel counters above. Recovering the per-model split of
`candidates_built`/`filled`/`never_filled`/`skipped_no_placement` therefore requires re-deriving
`population.candidates` and `fill_pass_c`'s internal partition -- Deliverable B's diagnostic
adapter (`extract/funnel_reconstruction.py`), not a re-read of any existing file.

## Checksums (proving the sources are untouched)

| File | SHA-256 |
|---|---|
| `run_d1_d2_d3.py` | `a184925f3b5379a5f04cb5d5466b91c3d623686a7ea52ce48fb19066df8edfac` |
| `run_c1_c2.py` | `f8ad3e3738c26c10f1c8d6e672aa082a00a9034c9470410927b6bcdd13e43ead` |
| `causal_intrabar.py` | `3886554bfa41e8cbc69cbec31920ff6f295248a6e7f4b24b832b4a3f64d2c26a` |
| `causal_anchor_v2.py` | `fd31db1b1b51e6c312241e40be01874215c078c45d182abac7ec9f8b442ede25` |
| `trades_d3_c2_2015plus_run2.csv` | `72bbfbf48e982483fe436c029e6a5672942114b6181520368fa948152d145392` |
| `funnel_2015plus_run2.csv` | `9e8d2e9df3e8261b6a05f0afd79a0458c6430468841157848c1d4c38c5183c13` |

`tests/test_phase8_requirements.py` re-checks these exact hashes after this phase's full pipeline
runs, as the phase's own regression proof (not just a one-time manual check).
