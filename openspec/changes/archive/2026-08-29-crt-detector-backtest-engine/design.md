# Design: CRT Backtest Simulation Engine

**Design version**: V6 | **Spec**: V8 (signed; V9/V10 landed as targeted unfreezes not requiring a design re-run) | **Triage**: L
**Architecture impact**: additive — the baseline gains a `backtest` root_package + layer tier and a `core.kill_zone` module; no boundary, dependency direction, or data-ownership line already in the baseline is changed.

## Architecture Overview

`backtest/` joins as a new pure-function layer above `alignment`, consuming `list[AlignedSignal]` — zero changes to `alignment/htf_ltf.py`. Internal direction is one-way: `levels.py` → `simulate.py` → `metrics.py`. SL/TP/entry-touch resolution reuses `core.sweep.two_heap_sweep` (already used by `fvg.py`/`mss.py`) — same O(n + m log m) shape, no new algorithm class. Output mirrors the existing `detections.csv` writer pattern, added to `viz/trades_table.py`. `--backtest` is opt-in at the CLI surface; omitting it reproduces today's byte-identical output.

Full pipeline: `core → primitives → composite/entries → alignment → backtest → viz/cli` (`ingestion` a leaf).

## File Changes (summary — 30 rows in the full design artefact)

| Area | Type | Notes |
|---|---|---|
| `detector/backtest/simulate.py` | Create | `Candidate`/`Trade`/`ReconciliationReport`, 7-stage population pipeline, unified fill from `retest_index`, SL/TP sweep from `fill_index+1` |
| `detector/backtest/levels.py` | Create | `entry_price`, `stop_loss` (purge/swing-extreme), `take_profit`, `risk_reward`, `net_r_multiple` |
| `detector/backtest/metrics.py` | Create | `BacktestMetrics` + `compute_metrics` |
| `detector/viz/trades_table.py` | Create | `trades.csv` + `metrics_summary.txt` writers |
| `detector/core/kill_zone.py` | Create | `in_ny_kill_zone` relocated verbatim from `cli.py` |
| `detector/core/config.py` | Modify | `BacktestConfig` (5 fields) |
| `detector/entries/model1.py` | Modify | `Model1Signal` +3 fields: `confirmation_index`, `origin_index`, `signal_id` (derived) |
| `detector/cli.py` | Modify | `--backtest` + 5 override flags, population binding, kill-zone delegation, dead `types` param removed |
| `detector/viz/table.py` | Modify | conditional `signal_id` column (runtime flag, not a static header change) |
| `detector/.importlinter` + `pyproject.toml` | Modify | new `backtest` layer/root_package/wheel entry |
| `detector/tests/property/test_no_lookahead.py` | Modify | new backtest monotonicity + swing-window-lookahead properties |
| `detector/tests/test_model1.py` | Modify | 12 existing tests updated for new fields |

## Data Model + Derivations

`Candidate` is a frozen dataclass with 9 fields, invariant "everything knowable AT `retest_index`" — `fill_index` is deliberately NOT a field; the fill pass yields `list[tuple[Candidate, int]]`. `take_profit`'s side selection is a total function of `direction` (`htf_context.high` bullish / `.low` bearish). `kill_zone_gate_state` is a 3-value string (`enabled`/`auto-disabled`/`disabled`). `signal_id` derivation: `f"{origin_index}-{anchor_index}-{direction}-{confirmation_type}-{entry_type}"`, where `origin_index` IS the originating `CRTRange`/`FVG.start_index` — closing a design defect an earlier revision had (a formula without `origin_index` would have collided on overlapping-range signals).

## Interface Contracts

`trades.csv`: 13 columns (`signal_id, anchor_timestamp, entry_timestamp, direction, entry_price, stop_loss, take_profit, exit_timestamp, exit_price, outcome, r_multiple, ambiguous_bar, gap_filled`). `metrics_summary.txt`: a literal, line-for-line template including win rate, average/total R with an unlimited-capital note, open-trades count, the 3-state kill-zone gate disclosure, and the trading-cost disclosure (frictionless or per-trade). CLI: `--backtest`, `--sl-buffer`, `--min-rr`, `--trading-cost`, `--kill-zone-gated`, `--max-fill-wait`.

## Architecture Decisions

Full text of all 5 ADRs, restored after an earlier revision cycle elided them to one-line summaries (a BLOCKING finding at Plan Verify iteration 4 — see Verify Plan history).

### ADR-01: `backtest` is a new lint-enforced layer above `alignment`, consuming `AlignedSignal`

**Decision**: Create a `backtest` package as a new `root_package` and a new layer slot between `alignment` and `viz : ingestion`. It consumes `list[AlignedSignal]` and makes zero changes to `alignment/htf_ltf.py`. Internally one-way: `levels.py` → `simulate.py` → `metrics.py`.

**Alternatives considered**: backtest logic inside `cli.py` (rejected — `cli` sits outside the layers contract entirely, so nothing would police selection-policy imports); extending `alignment/` (rejected — wrong single responsibility); a `backtest` module under `composite/` (rejected — inverts the contract's dependency direction).

**Consequences**: every future selection rule lands in a policed package; single-series backtesting becomes structurally impossible (matches REQ-32's HTF-pair-mode requirement); one more package to register in `.importlinter`+`pyproject.toml`, mitigated by an explicit fitness-function assertion (later found unimplemented — see Verify Report F-01).

### ADR-02: Three `two_heap_sweep` passes over explicitly sorted lists; every price ambiguity resolved pessimistically by ORDERING

**Decision**: Three direction-partitioned passes — fill, SL-touch, TP-touch. Exit resolution is `open-check → level-choice (SL wins on tie) → gap-check against the chosen level` (makes REQ-33's precedence over REQ-34 structural). The fill pass's eligibility is `retest_index` and the exit passes' is `fill_index + 1`, for every candidate type — `simulate` contains no `if candidate_type` anywhere. `two_heap_sweep`'s ascending-`eligible_at` ordering is a documented precondition each caller discharges by sorting immediately before the call.

**Alternatives considered**: per-trade forward scan (O(n·m), the regression class this codebase already paid to remove); an any-touch predicate (misses gapping fills); mirroring REQ-34's exit gap rule onto entries (rejected — REQ-47.5 requires the opposite, asymmetric treatment); making `two_heap_sweep` sort defensively (rejected — hides the requirement inside the primitive instead of naming it at the call site).

**Consequences**: O(n + m log m), no dependence on `max_fill_wait`. The sort precondition fails silently when violated — pinned by a sweep-order-invariance fitness function. Pessimism costs some understatement on genuinely favourable bars; intended direction of error.

### ADR-03: Every population cut is explicit, bounded, and bucketed — seven mutually exclusive buckets in a fixed precedence order

**Decision**: Every signal lands in exactly one of `trades_opened` or 7 exclusion buckets, evaluated in fixed order. `trades_opened + sum(buckets) == signals_considered` is an invariant asserted on every run. `metrics.py` embeds the report verbatim, never recomputing a bucket. Stage 3's criterion is `retest_index is None` regardless of status, admitting PENDING+retest candidates — closing the last hole where PENDING rows sat in `detections.csv`'s denominator but mapped to no bucket.

**Alternatives considered**: a single `excluded` count (answers "how many" but never "why" — the entire question a backtest report exists to answer); non-exclusive tags (kills the sum invariant); recomputing buckets in `metrics.py` (creates a second source of truth).

**Consequences**: a reader can always answer "where did the other N go" arithmetically. Precedence is observable and part of the contract. Constrains ADR-05's stop window — it cannot depend on `fill_index`, or stage 6 would depend on stage 7's output.

### ADR-04: Deduplicate candidates on `(anchor_index, direction, entry_price, entry_type)` BEFORE the kill-zone and R:R cuts

**Decision**: Collapse candidates sharing that tuple into one, lowest `origin_index` survives, cut runs at stage 4 (before kill-zone/R:R). Closes a measured 1.44x candidate inflation on real MT5 data.

**Alternatives considered**: dedup after the rule cuts (cheaper to reason about, but leaves both count buckets inflated 1.44x — optimizes implementation simplicity at the report's expense); include `origin_index` in the identity key (defines the problem away); include `confirmation_type` in the key (double-counts one real setup found two ways).

**Consequences**: `excluded_kill_zone`/`excluded_rr_floor` count economically distinct setups. `entry_type` in the key means a wick and a body candidate at the same anchor/price both survive (REQ-46.2) — different orders, different risk. Deterministic survivor independent of emission order (needed for REQ-51.2's byte-identity claim).

### ADR-05: Backtest-local price levels — entry at the retest boundary, stop at the deepest structural extreme, both fixed at `retest_index`

**Decision**: `backtest/levels.py` computes its OWN entry and stop, leaving `entries/model1.py`'s detection logic untouched. Entry is the retest-side body boundary for wick signals (charter-2) and `anchor.open` for body signals. Stop anchors to the deepest qualifying swing beyond `protected_extreme` within `[anchor_index, retest_index - 2]` (the `-2` accounts for `detect_swings`' one-candle confirmation lag — a swing at `retest_index - 1` would only be confirmable once candle `retest_index` closes, which is after a REQ-50.1 fill could already happen), or to `protected_extreme` itself when none qualifies, offset by `sl_buffer_price`.

**Context — why this exists**: an early version placed the stop just beyond `protected_extreme` while taking entry from `Model1Signal.entry_price`; for wick-type signals those are the SAME expression, collapsing risk to exactly `sl_buffer_price` for ~96% of trades, making R measure a config constant and REQ-35's R:R floor mathematically unreachable. This was the exact defect the post-design foresight gate (`north-star.md`) caught and routed back to spec.

**Alternatives considered**: changing `_select_entry` so detection and backtest agree (rejected — would alter REQ-19's tested detection output for a consumer that didn't exist when it was signed); entry at the wick extreme (rejected — reproduces the collapse); a larger `sl_buffer_price` (rejected — inflates risk uniformly rather than per-setup, R would still measure the config); `fill_index - 1` as the swing window's upper bound (rejected — reintroduces lookahead and inverts the fixed stage order).

**Consequences**: risk varies per setup (REQ-35.2 pins a real 1.43 R:R rejection). Backtest entry differs from `detections.csv`'s for wick signals — paid down by the `signal_id` join (REQ-42.1) and REQ-42.2's explicit divergence note.

**Amendment (2026-11-10b)**: "entry is the retest-side body boundary" above (and the "entry at the wick extreme (rejected — reproduces the collapse)" alternative) conflated two different points. Two real executed Model-1 trades confirmed entry actually sits at the anchor's own wick extreme (`anchor.high` bullish / `anchor.low` bearish) — a DIFFERENT value from the body boundary this ADR originally chose, and not the same value as the rejected alternative either: that alternative was the SWEPT-side wick tip (the same point as `protected_extreme`, which does collapse risk), while the wick extreme actually used sits on the OPPOSITE side of the candle from `protected_extreme`, so no collapse applies. `backtest/levels.py::entry_price`'s wick case now returns `anchor.high`/`anchor.low` directly — see REQ-47.2 (corrected) and `odd/tasks/model1-wick-entry-retest-side-fix.md`. The original Decision/Alternatives/Consequences text above is left unedited as the historical record of what was actually built and why, through 2026-11-10.

## Risks (numbered, as recorded in design V6)

1. The SL/TP sweep starts at `fill_index + 1`, so a trade stopped out on its own fill candle books no loss — a systematic optimistic bias, ratified by the human as acceptable, bounded to one candle per trade.
2. `signal_id` injectivity is inherited, not enforced — collision risk accepted as-is by the human; a uniqueness property test registered as a followup.
3. The surviving population may be very small — mitigated by the reconciliation block printing unconditionally.
4. C2 (`_filter_by_types`'s post-C2 body) is "output-preserving by construction" — mitigated by enumerating all `--types` combinations plus a regression row.
5. `two_heap_sweep`'s sort precondition fails silently, not loudly — mitigated by the sweep-order-invariance fitness function.
6. `metrics_summary.txt`'s wording is a test contract — e2e tests assert its lines as literal substrings.
7. Opinionated defaults (`min_risk_reward=2.0`, `kill_zone_gated=True`, `max_fill_wait=20`) shape headline numbers — mitigated by all 5 being REQ-51 CLI overrides, disclosed per run.
8. Performance is projected, not measured (a differential test was designed but never implemented — see Verify Report F-02).
9. `--types fvg --backtest` produces a silent empty, exit-0 backtest — ratified as-is by the human; `signals_considered: 0` is the disclosure.
10. Spec's `confirmation_index > retest_index` (strict) vs. the design's derived `>=` — harmless, nothing consumes the field for simulation.

## Fitness Functions

1. `.importlinter` layers contract extended for `backtest` (registered, though the dedicated assertion test was never implemented — see Verify Report F-01).
2. Config-completeness — automatic once `backtest/` imports `core.config`.
3. Backtest no-lookahead monotonicity property — a closed trade stays closed with identical fields under series truncation.
4. Exit-locality property — `simulate(series.up_to(exit_index+1))` reproduces every closed trade exactly.
5. Sweep-order-invariance — candidate order does not affect trades or buckets.

## Sensitive Areas Coverage

None. No auth, no payments, no PII, no secrets, no deploy surface, no production data — a read-only analysis tool over historical OHLC CSV.
