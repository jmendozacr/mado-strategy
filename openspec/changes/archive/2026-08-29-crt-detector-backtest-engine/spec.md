# Specs: CRT Backtest Simulation Engine

**Spec version**: V10 | **Status**: signed | **Change**: `crt-detector-backtest-engine`

23 REQ-IDs (REQ-30 through REQ-52), 67 sub-scenarios, all ADDED against the pre-existing main spec (v1's REQ-01..REQ-29) — no MODIFIED/REMOVED REQ-IDs. Two of the 23 (REQ-43, REQ-44) extend the pre-existing `model1-entry-detection` domain; two more (REQ-45, REQ-51) extend the pre-existing `cli-output-filtering` domain. The remaining 19 form three new domains: `backtest-simulation`, `backtest-metrics`, `signal-traceability`.

This spec went through 10 revisions across two Plan Verify gate cycles. Cycle 1 (4 iterations) found and closed problem-fit gaps in the tradeable population definition, the fill-simulation model, and the reconciliation-report semantics — plus a BLOCKING finding that early revisions had elided REQ text behind unretrievable "see revision history" pointers (fixed from V8 onward by reproducing every REQ-ID's full text on every revision, splitting into per-domain artefacts once the concatenated size risked the same truncation). Cycle 2 (2 iterations) closed a self-contradiction between REQ-41 (signal_id column) and REQ-45 (byte-for-byte guarantee) and added REQ-52 to back an authorized mechanical refactor that otherwise had no REQ-ID coverage.

---

## Domain: backtest-simulation (REQ-30 through REQ-38, REQ-40, REQ-46 through REQ-48, REQ-50, REQ-52)

### REQ-30: Tradeable candidate population selection
The system MUST select as a trade CANDIDATE (subject to fill simulation, REQ-50) every `AlignedSignal` whose `aligned == "aligned"` AND whose `ltf_signal` is eligible to be entered: `status == CONFIRMED`, `status == INVALIDATED` with `retest_index` not `None`, OR `status == PENDING` with `retest_index` not `None`. The system MUST NOT select any signal whose `retest_index is None` — regardless of status — nor `fvg_fill`-confirmed signals, nor `unaligned`/`insufficient_htf_data` signals.
- **REQ-30.1** through **REQ-30.6**: happy CONFIRMED path; INVALIDATED+retest path; `retest_index is None` exclusion; `fvg_fill` exclusion (no CRT range); unaligned exclusion; PENDING+retest admission (closes a survivorship-bias gap where these setups were silently dropped).

### REQ-31: Stop-loss placement
SL beyond a real structural level, computed relative to the REQ-47 entry price: the purge candle's `protected_extreme` offset by `sl_buffer_price` (default `0.0002`, a raw price-unit offset, never a pip count), or the DEEPEST qualifying swing extreme when one exists beyond it within `[anchor_index, retest_index - 2]` (the `-2` accounts for `detect_swings`' one-candle confirmation lag relative to when a candidate could actually fill).
- **REQ-31.1**–**31.4**: purge-extreme branch, single-swing branch, real risk-distance regression, deepest-of-multiple-swings tie-break.

### REQ-32: Take-profit sourcing and HTF pair-mode requirement
TP = HTF CRT range opposite extreme, sourced from `AlignedSignal.htf_context`, never recomputed. `--backtest` requires `--htf-csv`+`--htf-symbol`; fails fast naming both if missing.
- **REQ-32.1**–**32.2**: happy TP read; missing-flags fail-fast.

### REQ-33: Same-candle SL+TP tie-break
Pessimistic — SL wins whenever `sl_index <= tp_index`; counted as a distinct "same-candle SL+TP resolutions" disclosure. Level chosen BEFORE the REQ-34 gap check.
- **REQ-33.1**–**33.3**: happy tie-break; disclosure count; structural precedence over REQ-34.

### REQ-34: Gap-through-both-levels exit fill
Exit fills at the candle's actual open when it already lies beyond the chosen exit level — never at the SL/TP level itself. Exits only; REQ-47 governs entries independently.
- **REQ-34.1**: bearish gap-through-SL example.

### REQ-35: Risk:reward floor filter
Excludes, pre-simulation, any candidate whose signed R:R falls below `min_risk_reward` (default `2.0`). A structurally negative ratio (TP behind entry) falls in the SAME bucket.
- **REQ-35.1**–**35.3**: below-floor exclusion; floor-not-inert regression (1.43 R:R rejected); negative-ratio same-bucket.

### REQ-36: Kill-zone gating
Default-on NY Kill Zone gate on `anchor_index`; auto-disables when `--session` narrows the population; a third literal "disabled" rendering for `--kill-zone-gated false` without `--session`.
- **REQ-36.1**–**36.5**: default exclusion; session-narrowed zero count; anchor-time-only basis; auto-disabled disclosure; disabled disclosure.

### REQ-37: No-lookahead simulation entry point
Fill/SL/TP resolution uses only data existing at the evaluated index. The REQ-50 fill search may begin at `retest_index` for every candidate type; the SL/TP sweep begins at `fill_index + 1`, never earlier.
- **REQ-37.1**–**37.2**: CONFIRMED-path fill search from `retest_index` (not `confirmation_index+1`); same mechanism for INVALIDATED/PENDING+retest.

### REQ-38: Trade terminal states
Exactly one of `win`/`loss`/`open`. `open` has all exit fields `None`/`False`.
- **REQ-38.1**: open-trade field state.

### REQ-40: Population-reconciliation report
`signals_considered` measured strictly after the full CLI filter chain. Every signal lands in exactly one of `trades_opened` or 7 exclusion buckets, fixed precedence: `no_crt_range → unaligned → never_confirmed → duplicate → kill_zone → rr_floor → never_filled`.
- **REQ-40.1**–**40.4**: sum invariant; post-filter measurement point; unaligned-over-kill_zone precedence; PENDING+retest admission into the bucket accounting.

### REQ-46: Signal deduplication
Collapses `(anchor_index, direction, entry_price, entry_type)` collisions to one, lowest `origin_index` survives, run BEFORE kill-zone/R:R cuts (closes a measured 1.44x inflation).
- **REQ-46.1**–**46.2**: 3-way collapse; differing-entry-type both-survive.

### REQ-47: Entry price definition
Independent of `Model1Signal.entry_price`: `anchor.open` for body-type, retest-side body-zone boundary for wick-type — never `protected_extreme`. Doji anchors are the one documented equality exception. Fill candle gapping past entry fills AT the entry price (never the more favorable open).
- **REQ-47.1**–**47.5**: body entry; wick entry; non-degeneracy property; doji carve-out; entry-side gap asymmetry.

### REQ-48: Trading cost
`trading_cost_price` (default `0.0`), netted out of `r_multiple` once at closure. Always disclosed.
- **REQ-48.1**–**48.3**: net-R arithmetic; default-zero bit-identity; disclosure wording.

### REQ-50: Entry-fill simulation window
`max_fill_wait` (positive int) bounds the inclusive `[retest_index, retest_index+max_fill_wait]` touch search, uniformly across candidate types. Untouched → `excluded_never_filled`, never counted as a loss.
- **REQ-50.1**–**50.4**: wick same-candle fill; body later-candle fill; window boundary exclusivity; never-filled exclusion for INVALIDATED/PENDING types.

### REQ-52: Kill-zone gate relocation and dead-parameter removal preserve existing behavior
Relocating `in_ny_kill_zone` into `core/kill_zone.py` and removing `_detect_all`'s dead `types` parameter are both behavior-preserving.
- **REQ-52.1**–**52.2**: relocation identical classification; dead-param removal is a no-op.

## Domain: backtest-metrics (REQ-39, REQ-49)

### REQ-39: Win rate
`wins / (wins + losses)` over closed trades only. Zero closed → `None`/"n/a", never `0.0`.
- **REQ-39.1**–**39.2**: no-substitution; happy 0.6.

### REQ-49: Aggregate profitability disclosure
Average `r_multiple` + total R over closed trades, both "n/a" when none closed, always with an unlimited-capital note. Plus an explicit "open trades: N" line.
- **REQ-49.1**–**49.4**: happy average/total; no-substitution; disclosure wording; open-trades count line.

## Domain: signal-traceability (REQ-41, REQ-42)

### REQ-41: Signal/anchor identifier
`signal_id = f"{origin_index}-{anchor_index}-{direction}-{confirmation_type}-{entry_type}"`, `origin_index` = originating `CRTRange`/`FVG.start_index`. Injectivity inherited, not enforced (accepted risk, followup registered). `detections.csv` gains the column ONLY when `--backtest` is passed.
- **REQ-41.1**–**41.3**: cross-range distinctness; fvg_fill/purge_engulf non-collision; column absent without `--backtest`.

### REQ-42: Trade-to-detection traceability
Every `trades.csv` row's `signal_id` joins to exactly one `detections.csv` row. Divergent wick-type entry prices between the two are disclosed, not hidden.
- **REQ-42.1**–**42.2**: exact-one join; divergence disclosure note.

## Domain: model1-entry-detection (extended — REQ-43, REQ-44)

### REQ-43: `confirmation_index` field
Traceability/audit-only — records when a signal's fate became knowable, distinct from `retest_index`; NOT consumed by fill/SL/TP simulation.
- **REQ-43.1**: confirming-candle index example.

### REQ-44: HTF alignment requirement for take-profit sourcing
Only `aligned == "aligned"` signals become candidates; TP always read from that signal's own `htf_context`.
- **REQ-44.1**–**44.2**: happy sourcing; unaligned exclusion regardless of status.

## Domain: cli-output-filtering (extended — REQ-45, REQ-51)

### REQ-45: `--backtest` flag and trades.csv contract
13-column `trades.csv` contract; `detections.csv` gains `signal_id` only with `--backtest`; byte-for-byte output otherwise, no carve-out.
- **REQ-45.1**–**45.3**: regression; 13-column contract + fill-index timestamp; byte-for-byte without `--backtest`.

### REQ-51: BacktestConfig CLI overrides
5 flags, 1:1 field mapping, falling back to defaults when omitted; invalid values reject with exit 1 naming flag+value+constraint.
- **REQ-51.1**–**51.3**: override changes results; all-defaults byte-identity; invalid-value rejection.

---

## Sensitive Areas Coverage

None. Confirmed against `project/sensitive-areas`: no auth, no payments, no live order placement — read-only analysis tool over historical CSV data.

## Drift Check Results / Upstream Sync

N/A — `spec_source: internal`.
