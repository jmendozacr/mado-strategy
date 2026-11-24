# Source Inventory

Every historical trade source inspected for this lab, with provenance, what it actually contains,
and why it is or isn't trusted as Phase-1 evidence. Nothing here is copied or duplicated — this lab
reads these files in place, read-only.

## Raw price data

`data/*.csv` (repo root, **gitignored**, absent from this worktree — read via `config.resolve_data_dir()`
pointing at the main worktree's absolute path). 18 files: 6 instruments (EURUSD, USDCAD, AUDUSD,
GBPUSD, USDJPY, XAUUSD) × {D1, H4, M15}. MT5 export format, tab-separated:
`<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>` (no volume column). `<DATE>` is `YYYY.MM.DD`, `<TIME>`
is `HH:MM:SS`, timestamps are **naive** (no UTC offset stored in the file). The codebase's own
assumption is that these are a fixed-UTC grid with no DST — a separate, already-closed investigation
(`openspec/changes/archive/crt-detector-htf-timezone-anchor/triage.md`) specifically tested and
disproved a UTC+3 broker-offset hypothesis via independent blind verification; that result is a
different, resolved claim from the current causal-lookahead-audit's grid-mismatch finding below —
the two must not be conflated. EURUSD is 5-decimal precision. M15 files are the largest (~30MB each).

Loaded exclusively via `detector/ingestion/loader.py::load_mt5_csv` (reused read-only, not
reimplemented) — the same loader every other research module in this repo already uses.

## Candidate trade-ledger sources

### 1. `audit/2026-11-17-causal-lookahead-audit/trades_d3_c2_2015plus_run2.csv` — **PRIMARY source for Phase 1**

2047 trades, EURUSD/USDCAD/AUDUSD, 2015-01-06 to 2026-11-11, `d3_c2` arm only (D1/D2 arms exist in
sibling files but were never executed in that audit per an explicit user restriction at the time).

This is the output of a **causal-correctness audit** of a D1-D3 (feeder-candle source) × C1-C2
(candle-grid) experiment matrix, documented in `design-c1-c2.md` and `design-causal-anchor-source.md`
in the same directory. Across 3 rounds, that audit found and fixed, in its own standalone pipeline
(`causal_intrabar.py`, `causal_anchor_v2.py`, `run_d1_d2_d3.py` and friends — **not** `detector/`):

- A fill-eligibility bug: fills were credited using price touches that occurred *before* the Model-1
  signal was even confirmed.
- A second-round refinement: even the confirmation bar's own intrabar range predates the instant the
  order itself becomes knowable (its own close/`order_placed_ts`); fixed with
  `first_fillable_index = bisect.bisect_left(m15_timestamps, order_placed_ts)` — the first fill-eligible
  bar is the one *after* the confirmation bar, never the confirmation bar itself.
- A Key-Level cross-grid index bug: `KeyLevel.origin_index`/`expiry_index` are indices into the broker
  H4 grid, while C2 uses a separate NY-anchored feeder grid; comparing raw indices across the two was
  invalid. Fixed via an explicit timestamp bridge.
- A bar availability bug: code had filtered M15 bars by `timestamp <= as_of_ts` using a bar's *open* as
  if it were its availability instant; fixed to `available_at = timestamp + duration` everywhere.
- A retrospective-anchor-eligibility bug: CRT range High/Low anchors were only eligible once they
  resolved (true/false break) within a backward-looking `max_lookback=20`-bar window — i.e. anchor
  eligibility depended on the future. Redesigned to a fixed 16-bar age window, decided by timestamp,
  never by whether the future happened to resolve it.
- A documented, *not fixed* data limitation: AUDUSD's NY-anchored 9am feeder buckets are 2.10%
  incomplete (vs 0.07–0.30% for other symbols/sessions), 84% of that concentrated in 2007-2009.

**Why this is the Phase-1 primary source**: it is the only ledger in the repo whose generating pipeline
has these specific causal-correctness fixes applied, and it carries explicit per-trade provenance
timestamps (`feeder_ref_available_ts`, `activation_instant_ts`, `model1_available_ts`,
`order_placed_ts`) that make the `features_pre_entry` cutoff unambiguous rather than inferred.

**Caveat that does NOT disqualify it, but must travel with every row**: a *separate* statistical
robustness audit of this exact result (`results-d3-c2-robustness-2015plus.md`, prior session, mirrored
in Engram memory `causal-audit/d3-c2-robustness-audit`) found: no genuine out-of-sample period exists
(USDCAD/AUDUSD's own stop-floor calibration window overlaps the 2015-2026 evaluation window); the
combined edge is cost-fragile (EURUSD is already ≤0 expectancy at zero extra cost; combined flips
negative around +0.025–0.04R/trade extra cost); the entire combined edge is concentrated in 2021-2026
(2015-2020 was net **-16.7R** combined); EURUSD's sign flips removing 8 of 12 years (a coin-flip
signature) while USDCAD/AUDUSD are more robust to any single year's removal. **This is a property of
the strategy's statistical edge, not a causal-execution defect** — these rows remain causally valid as
behavioral observations of what price actually did, but must not be read as "this pair/period has a
proven edge." `stats/descriptive_summary.py` surfaces this caveat on every run so it can't be missed.

**Known partial-exit nuance**: 38.2% of these trades show a non-empty `partial_exit_index` (a scale-out
leg before the final exit). The current schema/extractor records `has_partial_exit` as a flag but does
not yet model the partial leg's own timing/price as a separate stage — a Phase-2 schema extension, not
yet needed for the SL/outcome-level Phase-1 questions.

**Right-censoring**: 4 of the 2047 rows have `outcome=open` (the trade was still running when the
ledger was generated, around 2026-09-22 to 2026-11-11). `exit_ts`, `exit_price` and `r_multiple` are
`None` for these, never fabricated as zero — the extractor and its tests specifically check this.

### 2. `audit/2026-11-17-eurusd-usdcad-audusd/trades.csv` — documented, **not used as Phase-1 evidence**

2067 trades, same 3 pairs, 2003-05-08 to 2026 (much longer history), both `1am` and `9am` sessions.
Generated by `export_audit.py` calling `detector/experimental/htf_trigger_1am_9am_backtest.py` +
`detector/backtest/simulate.py` **unmodified** — i.e. it reflects the actual production
backtest engine's current behavior, not an audit-corrected variant.

A repo-wide grep for the causal-correctness fix markers from source #1 above
(`first_fillable_index`, `available_at = timestamp`, `order_placed_ts`) inside `detector/entries/`,
`detector/backtest/` and `detector/causal/` returns **zero hits**. Cross-checked against
`git log --oneline --all -- detector/entries/model1.py detector/backtest/simulate.py detector/causal/`:
no commit message references these fixes either. **Conclusion: those causal-correctness fixes were
never merged into `detector/`'s production code**, so this ledger likely still carries the same
premature-fill / bar-availability issues the audit itself found and fixed only in its own copy.

This source also lacks source #1's explicit `*_available_ts` provenance columns (only
`entry_timestamp_broker` is present), and its own README documents (independently, not re-verified by
that audit) that no train/OOS split and no cross-pair exposure/overlap check exist for this recipe.

It is kept in this inventory, not deleted or ignored, because it covers 2003-2026 (12 extra years) and
is the actual production recipe — a legitimate secondary source for a *future* research unit, once
either the ledger is regenerated through a corrected pipeline or the causal-correctness risk is
otherwise bounded. It also has a companion `execution_events.csv` (6779 rows, per-lifecycle-event
detail: `entry_fill`, `partial_close`, etc.) that source #1 does not have an equivalent of.

### 3. Sibling arm files in `audit/2026-11-17-causal-lookahead-audit/`

`trades_c1.csv`, `trades_c2.csv`, `trades_arm_a.csv`, `trades_b1_ideal.csv`, `trades_b1_realistic.csv`,
`trades_b2.csv`, `trades_d1_c1.csv`, `trades_d1_c2.csv`, `trades_d2_c1.csv`, `trades_d2_c2.csv`,
`trades_d3_c1.csv`, plus `*_smoke_edt.csv`/`*_smoke_est.csv` variants — not inspected in detail this
round. Same generating pipeline family as source #1 (so likely share its causal-correctness fixes),
but D1/D2 arms were explicitly not pursued by the user at audit time. Flagged here for a future
research unit that wants a broader arm comparison, not opened further in Phase 1.

### 4. What does NOT exist in this repo

No independent trade-level ledger exists outside the two audit directories above (confirmed via
`git grep` for `trades.csv`/`ledger.csv`/`backtest_results` across tracked files). No funnel/candidate
data (signals that were detected but never filled — the "never_filled" comparison group S6 asks for)
was located as a standalone extractable table in this round; `results-d3-c2-robustness-2015plus.md`
references pair-level `candidates_built`/`never_filled` counts, but a per-signal version of that funnel
(needed to build a true "valid signal, no execution" comparison group) was not confirmed to exist as
a reusable file — this is an open gap, see `06-limitations-and-decisions-log.md`.

## Protected / excluded (read-only boundary, not inventoried further)

`audit/trader-algorithm-fidelity/` — the paused 30-case human-fidelity pilot. Confirmed to exist with a
`pilot_manifest.json`, `PILOT_PROTOCOL.md`, `CHECKPOINT.md`, `engine.py`, `selection.py`, `server.py`,
a `frontend/` app and `tests/` — filenames only, per the hard boundary in
`05-excluded-protected-artifacts.md`. Not opened, not used as evidence, not touched.
