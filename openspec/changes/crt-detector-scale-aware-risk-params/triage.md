# Triage: crt-detector-scale-aware-risk-params

**Classification**: S | **work_type**: bug | **root_cause_source**: description (bypass applied — user named exact cause) | **urgency**: normal
**Council**: architect + pm (triage-mandatory pair), both consulted in parallel, synthesized below — no L-scale full council needed
**Sensitivity override**: does not fire — this is a backtesting research tool over historical MT5 CSVs (no live trading, no real money, no auth/payment/PII/secrets/production-deploy/production-data-migration). Confirmed independently by both personas.

## Problem

A DXYm backtest trade showed `r_multiple ≈ 285` (`entry=99.028, stop=99.0282, risk=0.0002`). Root cause, user-identified and both-personas-confirmed: `core/config.py::BacktestConfig.sl_buffer_price` (default `0.0002`) is a raw price-unit constant sized for an FX pair (~1.05-1.20 scale). `backtest/levels.py::stop_loss()` applies this buffer to the returned stop-loss level unconditionally — not only in its no-qualifying-swing fallback branch — so on DXYm's much larger absolute price scale (~90-110) the same constant is proportionally ~180-220x smaller, collapsing the risk denominator toward zero and inflating R-multiple whenever that buffer dominates the stop distance.

**Consequence for scope**: because the buffer applies to every stop-loss regardless of source (real swing or fallback), the fix will shift R-multiples on EVERY instrument (EURUSDm, GBPUSDm, DXYm), not only DXYm's degenerate case. "Verify ordinary results don't change unexpectedly" must mean "shift is small and bounded, no distributional break" — not "byte-identical to before."

## Audit result (both personas read `core/config.py` independently — converges, does not expand)

| Field | Classification | Status |
|---|---|---|
| `FVGConfig.min_size_atr` (0.1) | ATR-normalized | Already correct — the pattern to reuse |
| `BacktestConfig.sl_buffer_price` (0.0002) | raw-price constant | **Live bug — fix now** |
| `BacktestConfig.trading_cost_price` (0.0) | raw-price constant | Same category, dormant (default 0.0 = no-op today). Defer — register as pending-change, do not fix now (no manifested problem; user's own scope discipline: fix only real problems found). |
| `Model1Config.respect_rule_tolerance` (0) | raw-price constant | Same category, dormant (default 0). Defer — same reasoning as above. Found by architect persona, missed by pm's first pass. |
| Everything else (ratios, candle-counts, time-of-day) | scale-independent | Clean, no action |

Audit is closed, not open-ended: exactly one live instance, two dormant same-shape fields logged as followups.

## Approach (architect-validated)

Promote `_atr`/`_true_range` from `primitives/fvg.py` (currently module-private) to a new `core/atr.py` — pure `Candle`-series arithmetic with no CRT/ICT domain semantics, belongs at the `core` layer per ADR-01's existing direction (both `primitives/fvg.py` and `backtest/levels.py` can then import downward from `core` legally, no boundary crossed). `primitives/fvg.py` switches to importing it. ATR-normalize `sl_buffer_price` the same way `min_size_atr` already normalizes FVG sizing — a new `sl_buffer_atr_multiple`-style field replaces the bare constant; `stop_loss()`'s signature gains the candle series it needs (one call site in `backtest/simulate.py::_build_candidate`, which already holds `ltf_series`).

**ADR** (ratifies at this S-inline close, no separate design-phase ceremony): *Promote ATR/true-range to `core`, rather than duplicating it into `backtest/levels.py`.* Rejected alternative: a second hand-rolled ATR implementation — rejected because two independent ATR implementations is exactly the silent-divergence risk this bug class already demonstrated. Second real consumer justifies promotion now (Rule-of-Three's own stated exception: "duplicates already diverging incorrectly").

## Explicitly out of scope

No changes to entry/exit/take-profit/trade-management logic — confirmed by both personas, `stop_loss()` is the only mechanism in play. No per-instrument config table (over-scoping, YAGNI). No fix to the two dormant fields now.

## Regression discipline (elevated per pm's finding)

Because every trade's stop distance shifts, the acceptance check is NOT "EURUSDm/GBPUSDm metrics stay identical" — it's "the shift is small, explained by the buffer-formula change, and no distributional property (win rate structure, trade count, bucket shape) breaks." Document exact before/after deltas for all 3 instruments, don't just eyeball it.

## Routing

S → inline path (orchestrator-executed, TDD-disciplined given strict-TDD project setting; execution delegated for the multi-file mechanical work, no separate spec/design/slice/verify-final/archive ceremony). Two followups registered to `project/pending-changes` (`trading_cost_price`, `respect_rule_tolerance` — same raw-price-constant category, dormant). Ablation study (separately scoped, already specified by the user) sequenced to start only after this fix is verified and base metrics are regenerated.
