# Phase 6 — Design, Execution Semantics Audit (Unit A), and Pre-Registration

Checkpoint: `8031cb2` (Phase 5). Read-only inspection of
`detector/backtest/simulate.py` and the actual pipeline that produced this lab's source ledger,
`audit/2026-11-17-causal-lookahead-audit/causal_intrabar.py` + `run_c1_c2.py`. No source file is
modified by this phase.

## 0. Correction to the brief's own premise, verified before anything else

The brief's Unit 2 names `detector/backtest/simulate.py` as "the" engine. That is only half true for
this lab's actual data. `extract/from_causal_lookahead_audit.py`'s own docstring (written in Phase 1,
re-verified here) states explicitly: the source CSV
(`audit/2026-11-17-causal-lookahead-audit/trades_d3_c2_2015plus_run2.csv`) was produced by the
audit's own **corrected** pipeline, not `detector/backtest/simulate.py`'s unmodified `simulate()`
entry point. Confirmed by reading `causal_intrabar.py` and `run_c1_c2.py` directly:

- **Entry fill timing is REPLACED.** `simulate.py`'s own `_fill_pass` makes a candidate eligible to
  fill starting at `candidate.retest_index` -- the retest/confirmation bar itself (same bar).
  `causal_intrabar.py::fill_pass_c` (what actually produced this ledger) instead floors eligibility at
  `first_fillable_index = bisect_left(m15_timestamps, order_placed_ts)`, where
  `order_placed_ts = model1_available_ts = candle[confirmation_index].timestamp + 15min` (the
  confirmation bar's own CLOSE). `fill_pass_c` asserts `first_fillable_index > confirmation_index`
  strictly. This is precisely the "premature-fill bug" fix the causal-lookahead audit exists to
  apply -- entries in this ledger can never fill on their own confirmation bar.
- **Exit/SL/TP resolution is REUSED UNMODIFIED.** `causal_intrabar.py`'s own docstring: "Reuses
  detector internals UNMODIFIED wherever already causally correct ... `_resolve_exits`."
  `run_c1_c2.py:269` calls `_resolve_exits` imported directly from `backtest.simulate`, byte-for-byte.
  **This means every fact established below about `_fill_candle_immediate_loss`, `_resolve_level_exit`,
  `_resolve_trade`, and `_resolve_single_leg` applies exactly, unmodified, to this lab's real ledger.**
  Only the FILL step differs from a raw `simulate()` call; the SL/TP/partial resolution step does not.
- `entry_timestamp_broker`/`exit_timestamp_broker` in the CSV are `m15.candles[t.entry_index].timestamp`
  / `m15.candles[t.exit_index].timestamp` (`run_c1_c2.py::fmt_idx_ts`) -- the bar's OPEN timestamp, the
  same convention already used throughout Phases 1-5 and reconfirmed here, not re-derived.

This correction does not change Phase 5's own numeric results (which never depended on where
`retest_index`-eligibility vs. `first_fillable_index`-eligibility placed the fill bar -- only on
`duration_bars` counted from whatever bar actually filled). It matters here because Unit A's
questions are about the SL/TP resolution step, which is confirmed unmodified.

## 1. The 10 required questions, answered from source, not assumed

**Q1 -- When is an order considered available?** A candidate becomes fill-eligible at
`first_fillable_index`, the first M15 bar whose own OPEN timestamp is `>= order_placed_ts`
(`order_placed_ts` = Model-1 confirmation bar's CLOSE, i.e. `available_at(confirmation_candle,
15min)` in `causal_intrabar.py`). Strictly after the confirmation bar -- never the same bar.

**Q2 -- When can its entry activate?** From `first_fillable_index` onward, the first bar (via
`two_heap_sweep` over `_fill_sides()`) whose own low (bullish) or high (bearish) reaches the
candidate's `entry_price`. No upper bound on how many bars this can take except
`config.backtest.max_fill_wait` (candidates waiting longer are excluded as `excluded_never_filled` --
not part of this phase's population, already excluded upstream of the ledger).

**Q3 -- Which OHLC field of the entry bar determines the fill?** `low` for bullish (price must fall
to or below `entry_price`), `high` for bearish (price must rise to or above `entry_price`) --
`_fill_sides()` in `simulate.py`. `open` and `close` play no role in the fill test itself.

**Q4 -- Can the SL be touched before the fill, within that same bar?** This is the engine's central
ambiguity. `_fill_candle_immediate_loss` is evaluated on the SAME bar the fill-sweep reports as
`fill_index`; it checks whether that SAME bar's low (bullish)/high (bearish) ALSO reaches
`stop_loss`. M15 OHLC (4 points per bar) cannot establish whether the entry-price touch or the
stop-loss touch happened first within that bar -- **this is a structural limit of the data, not a
limitation this lab can code around.** Section 2 below derives the one case where order IS
recoverable from OHLC without inventing intrabar order: when the bar's own `open` already lies on
the "far side" of `entry_price` from `stop_loss` (continuity then forces entry-before-stop).
Otherwise it is genuinely unknowable from M15 alone.

**Q5 -- What happens if entry, SL, and TP are all touched in the same bar?** `_fill_candle_immediate_loss`
sets `ambiguous_bar=True` whenever TP is ALSO touched on that fill bar (in addition to SL); the SL
still wins (pessimistic tie-break, same convention as every later-bar SL/TP tie in this codebase).
**Critically, this lab's own pre-existing eligibility taxonomy (`eligibility/stop_eligibility.py`,
Phase 2) already treats any `ambiguous_bar=True` loss as `AMBIGUOUS_STOP`, not `CONFIRMED_STOP`** --
so same-bar multi-level-ambiguity events are already excluded from every "confirmed stop" count used
in Phase 5 and in this phase's E0/E1/E2 decomposition. Verified by reading `classify()` directly
(`stop_eligibility.py` line 98-104).

**Q6 -- What exactly does `_fill_candle_immediate_loss()` do?** Given a filled candidate and its fill
bar: if the fill bar's low/high (per direction) does not reach `stop_loss`, returns `None` (no
same-bar loss; falls through to the normal post-fill sweep starting at `fill_index + 1`). If it does
reach `stop_loss` but the bar's `open` already gapped beyond `stop_loss` (Q7), also returns `None`
(exempted, deferred -- see Q7). Otherwise returns a `Trade` with `exit_index = entry_index =
fill_index` (duration 0 by construction), `exit_price = stop_loss` exactly (never the gap-open price
-- `gap_filled` is hardcoded `False` on this path, line 337), `outcome` always `"loss"` in practice
(exiting at exactly the nominal stop, net of cost, is never non-negative), and `ambiguous_bar` set per
Q5.

**Q7 -- What if price opens beyond the SL already?** `_exit_gap_beyond(fill_candle.open, stop_loss,
direction, chosen_is_stop=True)`: for bullish, `open < stop_loss`; for bearish, `open > stop_loss`. If
true, `_fill_candle_immediate_loss` returns `None` -- **exempted, not charged as a same-bar loss**.
Rationale in the function's own docstring: "we cannot know the position was live before that gap, so
no loss is inferred from it." This is an asymmetric convention worth stating plainly: the engine is
pessimistic about SL-vs-entry ordering in the ordinary same-bar case (Q4/Q5) but lenient in this one
specific gap sub-case. The candidate is NOT lost or dropped -- it falls through to the ordinary
post-fill sweep (`eligible_at = fill_index + 1`), so if the gap persists it resolves on a LATER bar
(becoming an E1+/E2+ event with `gap_filled=True` at that later bar, not an E0 event at all).

**Q8 -- What treatment does a gap receive generally?** `_exit_gap_beyond` + `_resolve_level_exit`:
whenever the bar that resolves SL or TP (in the post-fill sweep, i.e. for E1+/E2+ events, never E0)
has its own `open` already beyond the chosen level, the trade executes at that `open` price
(`gap_filled=True`), not at the nominal level -- a worse realized price, the standard conservative
gap-fill convention. This can ONLY happen for E1+/E2+ (never for E0, since `gap_filled` is hardcoded
`False` in `_fill_candle_immediate_loss`).

**Q9 -- How is a later-bar SL/TP tie resolved?** `_resolve_level_exit`: `sl_wins = tp_index is None or
(sl_index is not None and sl_index <= tp_index)` -- SL wins ties (same bar index) exactly as on the
fill bar. `ambiguous_bar = (sl_index == tp_index)`. Same downstream consequence as Q5: this lab's
`stop_eligibility.classify()` routes any `ambiguous_bar=True` loss to `AMBIGUOUS_STOP`, never
`CONFIRMED_STOP`, regardless of which bar the tie occurred on.

**Q10 -- When are these results considered available?** Only once `exit_index` is determined (SL or
TP swept successfully within the remaining series); a candidate for which neither level is ever
touched before the series ends is `outcome="open"` -- right-censored, carried in this lab as
`OPEN_CENSORED` (4 total, unchanged from Phase 5, excluded from every rate denominator in this
phase exactly as in Phase 5).

## 2. The one OHLC-based partial-identification criterion used in Unit C

For an E0 (same-bar, `_fill_candle_immediate_loss`-produced) event, direction-dependent:

- **Bullish** (`stop_loss < entry_price`): if `fill_candle.open >= entry_price`, then by price-path
  continuity within the bar, to reach a low `<= stop_loss < entry_price` the path must cross
  `entry_price` strictly before (or at) reaching `stop_loss` -- entry-before-stop is then
  **sequence-verifiable** from OHLC alone, no intrabar order invented. If `open < entry_price`
  (open already between or below the two levels), both temporal orderings are consistent with the
  same OHLC -- genuinely **not verifiable**.
- **Bearish** (`stop_loss > entry_price`), mirrored: sequence-verifiable iff `fill_candle.open <=
  entry_price`.

This is the ONLY assumption used: continuous intrabar price movement (no instantaneous jump mid-bar,
as distinct from the already-handled bar-boundary gap of Q7/Q8). It never assigns an order when the
open sits strictly between the two levels. See `eligibility/intrabar_ambiguity.py` for the
implementation and `tests/test_intrabar_ambiguity.py` for the proof this never invents an order.

## 3. Pre-registered taxonomy (Unit C) -- independent dimensions, not exclusive labels

| Dimension | Applies to | Source |
|---|---|---|
| `sequence_verifiable` | E0 only | Section 2 criterion on the fill/entry candle's `open` |
| `engine_conservative_same_bar` | E0 only (definitionally all of E0) | duration_bars == 0 |
| `same_bar_multi_level_ambiguity` | would apply to any duration | NEVER occurs within confirmed-stop populations -- already routed to `AMBIGUOUS_STOP` upstream (Q5/Q9); reported as a verification fact, not a new finding |
| `gap_affected` | E1/E2 only | ledger's own `gap_filled` field (always False for E0 by construction) |
| `insufficient_evidence` | any | fill/entry candle lookup fails (index out of range, missing series data) |

## 4. Pre-registered decomposition (Unit B)

Primary population unchanged from Phase 5: 2043 evaluable executed trades (778 win, 1265 loss, 4
`OPEN_CENSORED` excluded, reported separately). Within it, using the SAME `is_confirmed_stop`
definition and the SAME `compute_trade_timing` as Phase 5:

- E0: confirmed_stop AND `duration_bars == 0`
- E1: confirmed_stop AND `duration_bars == 1`
- E2: confirmed_stop AND `duration_bars >= 2`
- "Otras salidas": WIN outcomes + `AMBIGUOUS_STOP` losses (both are, by definition, not a
  confirmed early/late stop)
- `OPEN_CENSORED`: reported separately with its own denominator (`n_total`), never folded into the
  2043-based rates, exactly as in Phase 5.

Identity checked by test, not assumed: `rate(E0 ∪ E1) == rate(E0) + rate(E1)` per model (mutually
exclusive by construction), and `Gap_early == Gap_E0 + Gap_E1` where `Gap_X = rate_X(1am) -
rate_X(9am)`.

## 5. Pre-registered sensitivity scenarios (Unit D)

- **S0 (baseline):** exact reproduction of Phase 5's unadjusted gap (+9.35pp) from this same
  pipeline, no engine rule touched.
- **S1 (next-bar alone):** `Gap_E1` alone, same 2043 denominator, never framed as "P(fail at bar 1 |
  survived bar 0)" -- that would be a different (conditional) estimand this phase does not compute.
- **S2 (same-bar indeterminate, partial identification):** within E0, split into
  `sequence_verifiable` and not. For the NOT-verifiable subset only: report a **lower bound** (those
  events removed from the early-stop numerator but KEPT in the denominator -- "not established as an
  early stop," never recoded as a win or as a non-entry) and an **upper bound** (the engine's own
  convention, i.e. S0's number restricted to this subset). The verifiable E0 subset and E1/E2 are
  never bounded -- their status is not in question.
- **S3 (verifiable subset only):** drop the NOT-verifiable E0 subset entirely (numerator AND
  denominator) and recompute the gap on the remaining population; report the exact exclusion count,
  the reason, and whether the excluded share differs materially between 1AM and 9AM (a possible
  selection-bias signal in itself, reported, not resolved).

## 6. Verdict criteria (Deliverable F), declared before computing

| Verdict | Criterion |
|---|---|
| `NO_ROBUST_EARLY_STOP_DIFFERENCE` | S0's unadjusted 95% CI includes 0, or \|gap\| < 5pp |
| `MOSTLY_SAME_BAR_ENGINE_DEPENDENT` | S0 relevant; `Gap_E1` alone (S1) has a 95% CI including 0 or \|Gap_E1\| < 5pp -- i.e. the gap is concentrated in E0 and collapses once E0 is set aside |
| `NEXT_BAR_DIFFERENCE_PERSISTS` | S0 relevant; `Gap_E1` (S1) ALSO has a 95% CI excluding 0 AND \|Gap_E1\| >= 5pp -- i.e. a same-order-of-magnitude difference exists even restricted to E1 alone |
| `INSUFFICIENT_INTRABAR_INFORMATION` | the NOT-sequence-verifiable share of E0 exceeds 50% of E0 for either model, making S2's bounds too wide to distinguish the other verdicts |
| `MIXED_ENGINE_AND_MARKET_ASSOCIATION` | none of the above cleanly applies but S3's verifiable-only gap remains relevant and robust -- i.e. part of the effect is engine-dependent (S2's bound is wide) yet a real difference also survives on the cleanly verifiable subset |
| `INCONCLUSIVE` | none of the above cleanly applies |

This mirrors Phase 5's own discipline (`docs/29` section 4): criteria fixed before inspecting Unit B/D
results, one primary endpoint (S0, identical to Phase 5's), everything else secondary/explanatory.

## 7. What this phase does not do

No change to `detector/backtest/simulate.py`, `audit/2026-11-17-causal-lookahead-audit/` (any file),
or the source ledger. No re-simulation with an alternative engine rule presented as "the real market."
No RR/SL/TP/entry-parameter optimization. No ML. The 2015-2026 history remains previously-examined,
not genuine out-of-sample, regardless of this phase's findings.
