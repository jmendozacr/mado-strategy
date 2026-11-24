# Limitations, Assumptions and Decisions Log

Append-only. Each entry is dated and keeps its original reasoning even if later superseded — see
`04-methodology-safeguards.md`'s "hypotheses are registered before being evaluated" rule.

## 2026-11-24 — Phase 1

### Decisions

- **D1**: Primary Phase-1 evidence source is
  `audit/2026-11-17-causal-lookahead-audit/trades_d3_c2_2015plus_run2.csv` (2047 trades), not
  `audit/2026-11-17-eurusd-usdcad-audusd/trades.csv` (2067 trades, longer history). Reason: a repo-wide
  grep confirmed the first source's documented causal-correctness fixes (fill-eligibility,
  bar-availability, key-level cross-grid bridging) were never merged into `detector/`'s production
  code, which generated the second source unmodified. See `02-source-inventory.md`. This decision is
  reversible if either (a) those fixes get merged into `detector/` and the second ledger regenerated,
  or (b) a future unit specifically needs the longer 2003-2026 history and accepts the known risk.
- **D2**: `exit_reason` is inferred from `outcome` (loss→stop_loss, win→take_profit), not observed,
  because no source ledger has this column and `detector.backtest.Trade` only models SL/TP exits. Every
  record's `exit_reason_basis` says `INFERRED_BINARY`. If this assumption is ever wrong (e.g. a future
  source adds a time-based exit), it will silently mislabel exit cause — flagged here so it's checked
  first if that ever becomes relevant.
- **D3**: Right-censored (`outcome=open`) rows are kept with `exit_ts=exit_price=r_multiple=None`,
  never fabricated. 4 of 2047 rows in the primary source are censored this way (trades opened
  2026-09-22 to ~2026-11, still running when the ledger was generated).
- **D4**: Partial-exit trades (38.2% of the primary source) are flagged (`has_partial_exit`) but not
  yet modeled as a separate stage. Acceptable for Phase-1 (SL/outcome-level) questions; a Phase-2
  schema extension if partial-exit timing itself becomes a feature of interest.

### Known limitations / open gaps

- **L1 — No "valid signal, never executed" comparison group yet (S6).** Neither candidate source is a
  funnel table of detected-but-unfilled signals. `results-d3-c2-robustness-2015plus.md` references
  pair-level `candidates_built`/`never_filled` counts, but a per-signal version was not confirmed to
  exist as a reusable file this round. Without it, this lab can compare winners vs. losers, but not
  yet "executed vs. a setup that was valid but never triggered" — a real selection-bias risk for Line A
  specifically. Needs follow-up before Line A (failure prediction) can be trusted.
- **L2 — Pre-entry structural/volatility features are not yet joined.** The ledger has price levels
  and timestamps but no ATR, swing-structure, or session-range features computed at decision time.
  Building these requires joining `features_pre_entry` timestamps against the raw M15/H4 `data/` CSVs
  — mechanically possible (see `extract/post_stop_trajectory.py` for the same kind of join, applied
  post-exit instead of pre-entry) but not implemented this round; this is squarely a Line A input.
- **L3 — M15 resolution cannot resolve true intrabar SL/TP order** when a single M15 bar's range
  touches both levels. The primary source carries this as its own `ambiguous_bar` flag (0.29% of
  trades) rather than silently picking a side — kept as a flag here too, never resolved by assumption.
- **L4 — EURUSD's statistical evidence is weak** (documented in `02-source-inventory.md`): treat
  EURUSD rows as valid *behavioral* observations (what price did) but not as proof that pair has a real
  edge. Any cross-pair pooling in a later research unit must either stratify by pair or explicitly
  justify pooling despite this.
- **L5 — No genuine out-of-sample period exists yet anywhere in this data.** 2015-2026 has already
  been used by this repo's own prior research (robustness audit, stop-floor calibration). Any future
  discovery/validation/test split drawn from these years is "previously-seen, reserved," never virgin
  OOS — per `04-methodology-safeguards.md`.
- **L6 — Broker-UTC assumption for `data/*.csv`'s H4 anchors is a resolved-elsewhere claim, not
  re-verified by this lab.** `openspec/changes/archive/crt-detector-htf-timezone-anchor/triage.md`
  independently disproved a UTC+3 hypothesis (broker confirmed UTC+0, no DST). This lab relies on that
  prior result rather than re-deriving it; if that archived finding is ever revisited, this lab's
  timestamp assumptions should be re-checked too.
- **L7 — Post-SL trajectory reconstruction (`extract/post_stop_trajectory.py`) is implemented and unit-
  tested against synthetic bars, and smoke-tested against real M15 data for individual events, but has
  not been run over the full 2047-event dataset.** Running it at scale is deliberately deferred — it
  starts to shade into Line B's actual analysis, which is explicitly out of scope for this round.
  (Superseded by Phase 2: this run now happens at scale, over the eligible 1262-event population, in
  `behavior/post_stop_metrics.py` via `stats/atlas.py`. L7 is kept here as history, not deleted.)

## 2026-11-24 — Phase 2

### Decisions

- **D5**: `breakeven_after_partial=True` for EURUSD/USDCAD/AUDUSD in `SYMBOL_CONFIG`
  (`detector/experimental/htf_trigger_1am_9am_backtest.py`), reused unmodified by
  `audit/2026-11-17-causal-lookahead-audit/run_d1_d2_d3.py:239`, is a dataset-level constant for the
  primary source — every partial-exit trade's leg-2 adverse level is `entry_price`, never the original
  `stop_loss` column. `eligibility/stop_eligibility.py` hardcodes this (with the evidence cited in its
  module docstring) rather than re-deriving it per row, since the CSV itself carries no such column.
- **D6**: The eligible population for the Atlas is `confirmed_stop_event` + `stop_after_partial_exit`
  (1262 of 1265 losses). `ambiguous_stop_event` (3) and `open_censored` (4) are excluded from the main
  Atlas and reported only as a separate sensitivity check / their own category, per S18/S22.
- **D7**: Horizons are measured in **calendar time** (wall-clock), not market-effective time; weekend/
  holiday gaps are flagged (`weekend_gap_spanned`), never interpolated or silently absorbed. Chosen for
  consistency with Phase 1's existing MFE/MAE convention rather than introducing a second time system.
- **D8**: The continuation/reversal first-move threshold (0.25R) and the 4 period buckets
  (2015-2017/2018-2020/2021-2023/2024-2026) were fixed in `docs/07-phase2-stop-eligibility-and-atlas.md`
  before `stats/atlas.py` was ever run — see that file for the full pre-registration.
- **D9**: `stop_after_partial_exit` turned out to be empirically ~0 (0 of 1262 eligible events). This
  is a real finding (the breakeven-after-partial reward structure makes a net-loss outcome on a
  partial-exit trade arithmetically near-impossible, not a classifier defect) — confirmed by the
  `has_partial_exit` win-rate cross-check in `docs/07-phase2-stop-eligibility-and-atlas.md`. Recorded
  here, not silently dropped, per the "no corrijas silenciosamente" instruction.

### Known limitations / open gaps (Phase 2)

- **L8 — The control group borrows direction/risk from its matched real event rather than deriving an
  independent "what would a trade have looked like here" rule.** This avoids inventing a new,
  unvalidated direction-detection algorithm, but means the control group is NOT a fully independent
  simulation of "a typical trade at this moment" — it is "the same hypothetical trade parameters,
  dropped at an otherwise-ordinary moment." Good enough to test "is post-SL behavior different from
  ordinary market behavior at a matched moment," not strong enough to claim the control represents
  every alternative trade design.
- **L9 — ATR-based volatility matching uses a 400-candidate random pool per stratum, not an exhaustive
  search.** With only 12 strata (3 instruments x 4 period buckets) this pool is large relative to most
  strata's eligible-event count, but is still a finite, seeded sample — a different seed would produce
  a slightly different control set (by design, for reproducibility under one fixed seed, not because
  the matching is exact).
- **L10 — One-way stratification (never the full cross-product) by design (S22).** A reader asking
  "what about EURUSD 9am sell trades in 2021-2023 specifically" will not find that exact cell in this
  phase's output — deliberately, to avoid the combinatorial subgroup search the brief warned against.
  A future phase could examine a specific, pre-justified cell if one of this phase's one-way findings
  motivates it.
- **L11 — `has_partial_exit` trades are still not modeled as a separate stage** (L4 from Phase 1,
  unchanged): the Atlas treats a partial-exit loss's post-stop trajectory starting from its FINAL
  exit only, not from the partial leg's own exit instant. Revisit if partial-leg-specific behavior
  becomes a question of interest.
