# North Star — CRT Backtest Simulation Engine (Foresight Checkpoint, post-design)

**Checkpoint**: foresight (forward-looking) | **Original verdict**: `outcome-gap`, `gap_category: scope`, blocking-with-override | **Resolution**: re-spec'd, then ratified — see Resolution below.

## What we set out to do

> The trader stops guessing whether the ~135 Model-1 signals/day his detector finds are worth
> anything, and starts reading a number: of the setups the methodology would actually have let
> him take — not the ones that happened to work out — how many won, and at what R.

The design's population-reconciliation discipline (survivorship-inclusive population, simulated fill gated on `confirmation_index` lag, deduplication, pessimistic tie-breaks, an exhaustive named-bucket accounting) was judged the strongest part of the plan — every mechanism exists to stop the headline number from lying.

## The defect this gate caught before a line of code was written

`entries/model1.py`'s `_select_entry` returns the anchor's own `protected_extreme` for wick entries — the SAME expression the original stop-loss design anchored to. Therefore, for the ~96% of signals that are wick entries, **risk collapsed to exactly `sl_buffer_price` (0.0002, 2 pips) — a config constant, not a property of the setup.** Three arithmetic consequences followed directly, none requiring a test run to see:

1. R-multiple would stop describing CRT and start describing `TP_distance / 0.0002` — every winner would report roughly 8R-25R, a rescaling of the divisor, not a methodology signal.
2. REQ-35's user-ratified R:R floor would become a no-op — clearing `2.0` requires only 4 pips of TP distance, smaller than any realistic HTF CRT range.
3. The reported verdict (profitable / not) would flip sign on an unexamined 2-pip default, dominated by noise at that scale.

A second, independent finding: trading costs (spread/slippage/commission) appeared nowhere in any artefact — not excluded, simply never named — on a 2-pip risk model, a ~1 pip round-trip spread would be 50% of risk. A third: the `signal_id` formula as designed omitted the originating `CRTRange`, so REQ-41.1's distinctness guarantee would fail on exactly the overlapping-range case the traceability requirement exists to solve.

## Escalated conscience questions (human-only, answered before any code was written)

1. Stop-loss rule — re-spec to anchor to what charter-2 actually names (purge/swing extreme with entry at the retest/open, so risk varies per setup), keep the current buffer-only model treating results as directional-only, or treat the run as an explicit sensitivity study?
2. Trading costs — disclose frictionless, or bring a configurable cost into scope now?
3. Significance — is win rate + average R over ~85 trades/9 days/one pair enough to change what the trader does next Monday, or does this need the deferred pieces (partials, drawdown, concurrency) first?

## Resolution (human-ratified)

1. **Re-spec** (option a): stop anchors to the purge-candle extreme OR the deepest qualifying swing extreme beyond it, entry at the retest boundary or candle open — risk now varies per setup. Routed to `sdd-spec` (REQ-31, REQ-35 revised) then `sdd-design` re-run (landed as design V6, ADR-05).
2. **Configurable trading cost added to scope now** — landed as REQ-48, `BacktestConfig.trading_cost_price`, `--trading-cost`.
3. **Significance ratified as-is** — win rate + average R over the estimated sample IS sufficient signal for the trader's next decision. This change stands as complete, not "phase 1 of N."

The `signal_id` formula defect was folded into the same design re-run: `origin_index` (the source `CRTRange`/`FVG.start_index`) added as a required field.

## Reckoning criteria left for the pre-archive gate

1. A trader-legible verdict from a real EURUSD run, not fixtures.
2. Reconciliation sums exactly; `excluded_rr_floor` specifically inspected (a near-zero count would prove the inert-filter prediction came true).
3. Risk is NOT a constant — `entry_price - stop_loss` shows meaningful variance across trades — or an explicit human override is recorded.
4. Trading-cost treatment stated in the metrics summary output itself.
5. Every `trades.csv` row joins to exactly one `detections.csv` row on real data.
6. Zero regressions in the v1 suite; byte-identical non-backtest output.
7. The §5 ratifications held through delivery, no drift.

**See `outcome-verdict.md` for how the reckoning gate scored delivery against these 7 criteria.**
