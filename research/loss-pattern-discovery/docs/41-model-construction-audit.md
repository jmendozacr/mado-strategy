# Deliverable E — Model Construction Audit (Units E + F, read-only)

Read-only inspection of `detector/causal/htf_trigger.py` and
`audit/2026-11-17-causal-lookahead-audit/causal_intrabar.py`. No model rule is reimplemented,
modified, or re-tuned here -- facts cited directly from source, nothing speculative presented as
established.

## Unit E — Verified structural facts about 1AM vs. 9AM order generation

| | 1AM (`MODEL_1AM`) | 9AM (`MODEL_9AM`) |
|---|---|---|
| Feeder reference hour (NY) | 21:00 (previous calendar day) | 05:00 (same day) |
| Trigger hour (UTC) | 04:00 | 12:00 |
| Confirmation window start (NY) | 02:00 | 09:00 |
| Confirmation window duration | **2h00m** | **1h30m** |

(`causal/htf_trigger.py::MODEL_1AM`/`MODEL_9AM`, `REFERENCE_HOUR_NY` in `causal_intrabar.py`.)

**Everything downstream of the window -- the Model-1 entry search itself -- is byte-for-byte
shared, not model-specific.** `causal_intrabar.py::build_causal_signal` calls
`confirmation_window_utc`, `ltf_window_indices`, and `confirm_in_ltf_window` with the SAME
`model1_config` object for both models (verified: neither `confirm_in_ltf_window` nor
`ltf_window_indices` branches on model identity in their own signatures or bodies). This means:

- **Entry type/level, invalidation rule, and SL geometry are IDENTICAL between 1AM and 9AM** -- they
  come from the one shared Model-1 implementation, not a per-model variant.
- **The only verified structural difference is the confirmation window's timing: when it opens, and
  for how long (2h vs. 1h30m).** A longer confirmation window (1AM's) gives Model-1 more M15 bars in
  which to find its own anchor/confirmation/retest sequence before the window closes -- but this
  lab did not verify, and does NOT claim, that window length causally produces a different
  early-stop rate. That would require a dedicated causal design (e.g. varying window length while
  holding everything else fixed), out of scope here.

**Answer to the brief's concrete question:** yes, one verified structural difference exists (the
confirmation window's start hour and duration) -- no others were found in the entry/SL generation
path itself. Whether that difference explains the early-stop gap is NOT established by this audit;
it is named here only as a candidate for a future, explicitly causal unit (Phase 7 recommendation,
`docs/43`).

## Unit F — Alternative explanations evaluated, not invented

### A. Trading costs

`detector/backtest/simulate.py::_fill_candle_immediate_loss`'s `sl_touched` boolean (the fact that
determines whether an E0 same-bar stop occurs at all) reads only `fill_candle.low`/`.high` and
`candidate.stop_loss` -- **`trading_cost_price` never appears in that expression.** `trading_cost_price`
is used exactly once in that function, inside `_net_r_multiple(...)`, which computes the R-multiple
of an ALREADY-DETERMINED exit, strictly after `sl_touched` is known. Verified directly from the
function body (`simulate.py` lines 309-339): cost affects the NET R-MULTIPLE/outcome sign, never
whether or when the SL is touched. **Trading cost is not a candidate explanation for the early-stop
TIMING gap.** It remains relevant to profitability (a separate question this phase does not reopen)
-- `docs/30-...`'s finding that 1AM's `cost_to_risk_ratio` is markedly higher (0.178 vs. 0.109)
stays a real, documented fact, just not one that bears on *when* a stop triggers.

### B. Volatility / risk sizing

Already tested directly in Phase 5 (`docs/32-...`): standardizing on `risk_atr` does not shrink the
unadjusted gap (it is very slightly larger standardized: +9.93pp vs. +9.35pp unadjusted). This phase
adds no new volatility-adjustment test -- Phase 5's conclusion stands: `risk_atr` does not explain
the gap, at either the combined endpoint or (by extension, not separately re-tested) its E0/E1
parts.

### C. Instruments

Kept separate throughout (`docs/38`'s by-model-and-instrument table): AUDUSD shows both the smallest
E0 and E1 rate gap between models among the three pairs, consistent with Phase 5's own finding that
AUDUSD's combined early-stop association was the weakest and not statistically significant. No
structural reason for this was identified in `causal/htf_trigger.py` (feeder/window rules do not
vary by instrument) -- reported as unexplained heterogeneity, not resolved, exactly as Phase 5 left
it.
