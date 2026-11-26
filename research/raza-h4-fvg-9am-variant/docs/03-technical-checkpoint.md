# Technical Checkpoint

## Checkpoint

- Starting SHA: `8e38a0e` (branch `research/loss-pattern-discovery`, clean at start).
- This experiment's own work is uncommitted as of this checkpoint -- pending review before commit.

## Files created

- `docs/00-checkpoint-and-scope.md`, `docs/01-protocol.md`, `docs/02-results.md`, this file.
- `raza_h4fvg/candles.py` -- generic candle-bucket reconstruction + sweep/close classification
  (shared by daily bias and H4 decision).
- `raza_h4fvg/daily_bias.py` -- Step 1 (17:00 NY daily candles, reconstructed fresh from M15).
- `raza_h4fvg/h4_setup.py` -- Steps 2/3 (reference candle, known-at-09:00 FVG, the 13:00 decision).
- `raza_h4fvg/m15_entry.py` -- Step 4 (13:00-15:00 window, `confirm_in_ltf_window_v2` reused
  unmodified, plus the independent invalidation scan).
- `raza_h4fvg/candidate_and_fill.py` -- Step 5 (entry/stop/target/RR floor, 15:00-cutoff fill,
  exit resolution -- every formula and primitive reused unmodified from `backtest.levels`/
  `backtest.simulate`/`core.sweep`).
- `raza_h4fvg/orchestrate.py`, `raza_h4fvg/build_and_save.py` -- per-symbol, per-session loop and
  full-history orchestration (one process per symbol, same OOM workaround used throughout this
  lab and its siblings).
- `raza_h4fvg_stats/report.py` -- funnel, net-R, and D3/C2 comparison.
- `tests/conftest.py` + 7 test files (26 tests total).

## Verified, not assumed

- The existing `daily` OHLCSeries (D1 CSV) is UTC-midnight-anchored, NOT 17:00-NY-anchored --
  checked directly against real timestamps (`00:00:00`) before deciding to reconstruct daily
  candles fresh from M15 data instead of reusing it.
- `known_fvgs_at`'s own availability check uses `H4_DURATION`, not `M15_DURATION` -- caught and
  fixed during development (an FVG's own origin candle is on the H4 series, available 4 hours
  after its own open, never 15 minutes).
- The one `ENTERED` trade with an R-multiple of +11.68 (EURUSD, 2015-10-28) was individually
  traced end to end and confirmed to be a genuine large intrabar gap, resolved by the real,
  unmodified, already-tested `_exit_gap_beyond`/gap-fill logic -- not a bug in this experiment's
  own new code.

## Counts (full 2015+ history, 3 pairs)

13,002 total sessions; 242 qualifying H4 setups (1.9%); 12 `ENTERED` trades (0.09%). Net R per
qualifying setup: +0.0276 pooled; total net R +6.67, but -5.01 excluding the single outlier trade.
Comparison with D3/C2: 3 sessions where both execute, 9 where only this variant does, 1,424 where
only D3/C2 does, 11,566 where neither does.

## Tests

26 tests, all passing: `test_candles.py` (5), `test_daily_bias.py` (5), `test_h4_setup.py` (5),
`test_m15_entry.py` (5, including the brief's own Enter/Wait/Discard worked examples),
`test_candidate_and_fill.py` (3), `test_orchestrate.py` (1, real-data smoke test), `test_report.py`
(2). `lint-imports` (run from the worktree's own `detector/`): 11/11 contracts kept, 0 broken.

## Reproduction commands

See `README.md`.

## Limitations (stated, not hidden)

- **n=12 is too small for any statistical conclusion** -- the report explicitly does not compute a
  confidence interval or significance test on this sample, per the protocol's own pre-declared stop
  condition.
- The pooled total net-R sign depends entirely on one large-gap outlier trade.
- The daily-bias/H4/gap/M15-window design choices are all stated research conventions (the brief's
  own words), not validated as "correct" in any sense beyond reproducibility.
- No RR/SL/TP parameter search was performed -- the 2.0 floor and every other baseline parameter
  are reused unchanged from the original D3/C2 config.
- 2015-2026 remains previously examined by the sibling lab's own phases; this is an exploratory
  historical comparison, not an out-of-sample validation.
- No detector/scanner change, no live order submission, no adoption recommendation.

## Commits

None yet -- this report stops here for review, consistent with this phase's own closing framing.

## Final recommendation

Given the extreme scarcity (12 trades), any further investment in this specific five-condition
sequence should first ask whether a less restrictive daily-bias or gap definition is worth testing
-- but that is a scope decision for review, not something this report recommends unilaterally.
