# Deliverable B — Confirmation Path Diagnostic

Reproduce: `uv run --project detector python
research/loss-pattern-discovery/extract/confirmation_path_reconstruction.py <SYMBOL>` (one process
per symbol, per the OOM workaround documented in Phase 9's `docs/78`). Module:
`extract/confirmation_path_diagnostics.py`; orchestration: `extract/confirmation_path_reconstruction.py`.

## Design

`confirm_in_ltf_window_v2_traced` is a structural, line-by-line mirror of the real
`causal_anchor_v2.confirm_in_ltf_window_v2`'s own retry loop -- it calls the SAME, unmodified
`find_first_valid_anchor` and `entries.model1._track_anchor` functions, in the SAME order, with
the SAME arguments, adding only one thing: it records each attempt's own `(anchor_index, status,
confirmation_index)` before deciding whether to retry. It never reimplements `_track_anchor`'s own
engulf/retest/invalidate decisions.

`trace_confirmation_path_for_record` recomputes the exact same `window` tuple
`causal_anchor_v2.build_causal_signal_v2` computed internally for that record (same
`window_start_fn`/`window_end_fn`/`record.activation_instant_ts` inputs, all already-computed,
pure values) -- never a different derivation.

`run_d_c2_with_confirmation_paths` calls the real, unmodified `run_d1_d2_d3.run_d_c2` for the
authoritative `records_with_ids`/`counters`, and ADDS one path-trace call per CONFIRMED record.

## Equivalence (requirement 1/14, never just a count)

Two dedicated tests prove bit-for-bit equivalence against the real pipeline, not merely matching
lengths:

- `test_confirmation_path_diagnostics.py::test_trace_confirmation_path_for_record_reproduces_the_real_pipeline_exactly`
  -- a synthetic, hand-built 2-invalidation sequence: the traced path's own `terminal_signal`
  equals calling `causal_anchor_v2.confirm_in_ltf_window_v2` directly, field for field.
- `test_confirmation_path_diagnostics.py::test_run_d_c2_with_confirmation_paths_reproduces_the_real_pipeline_exactly`
  -- real EURUSD data (Jan-Mar 2015): the instrumented runner's `records_with_ids`/`counters` match
  the real `run_d_c2` exactly, AND every one of that range's CONFIRMED records receives a
  reconstructed path whose `terminal_signal` equals that record's own real `aligned.ltf_signal`.

## Synthetic cases covered (requirements: zero/one/multiple restarts, direct confirm, exhaustion)

| Case | Test |
|---|---|
| Direct confirmation, zero invalidations | `test_direct_confirmation_has_zero_invalidations_and_one_attempt` |
| One internal invalidation, then confirms | `test_confirmation_after_one_invalidation_records_its_real_trajectory` |
| Two internal invalidations, then confirms | `test_confirmation_after_multiple_invalidations_records_every_restart` |
| Engulfed, window exhausts before retest (PENDING) | `test_window_exhaustion_after_engulf_without_retest_is_pending_with_no_fictitious_restart` |
| Never engulfs at all (terminal NONE, anchor existed) | `test_window_exhaustion_without_ever_engulfing_is_none_with_no_fictitious_restart` |
| No anchor at all (bare `None`, not a degenerate path) | `test_no_anchor_at_all_returns_none_not_a_degenerate_path` |

## No-lookahead proof (requirement 10)

`test_never_reads_candles_beyond_the_window_end_even_when_poisoned` appends two extra candles
after the true window end that WOULD flip the result if read (a close that would breach the final
anchor's protected extreme) -- the traced result is byte-identical with or without them, because
`window=(0, 6)` truncates the array the same way the real function does. This is a direct,
falsifiable proof, not an assumption from the code's structure alone.

## Scope and limitations (stated, not hidden)

- Paths are reconstructed ONLY for signals that terminate `CONFIRMED` -- per the brief's own
  framing ("necesitamos registrar el recorrido de las señales que finalmente confirman"), since
  only confirmed, executed signals can ever have an E1 outcome. Rejected signals' taxonomy was
  already fully characterized in Phase 9 and is not re-derived here.
- `first_anchor_found_at`/`final_anchor_found_at` probe only the FULL retry chain this function
  itself walks (every attempt, not just the first) -- a strictly more complete reconstruction than
  Phase 9's own `probe_first_anchor` (which checked only the first search, for the REJECTED side).
- Reconstruction coverage over the full 2015+ population is reported, not assumed, in Deliverable
  D/E -- any confirmed signal whose path could not be reconstructed is listed explicitly.
