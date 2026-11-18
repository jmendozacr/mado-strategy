# Design — Intrabar causal detector (Arms C1/C2), REVISED

Status: **design only, not implemented**. This revises the version reviewed at commit `07fc24c` after an independent review found 4 blocking issues (§1-§4 below). Nothing under `detector/`/`scanner/` touched; nothing in `/docs` touched; A/B1/B2 outputs untouched; no commits made from this revision.

## 0. What changed since the last version, and why

The reviewed version claimed C1/C2 could reuse `simulate()` fully unmodified because "the trigger is causal, so `retest_index` is causal too." **That claim was wrong** — `retest_index` and `confirmation_index` are different indices, and nothing enforced that a fill could only happen after confirmation. §1 below fixes this with a real custom fill pass (`fill_pass_c`), not a reuse of unmodified `simulate()`. §2 replaces the direct reuse of `_key_level_credit_map`'s index comparison (broken across C1/C2's two different candle grids) with a timestamp-based bridge. §3 fixes every place the design confused a bar's open timestamp with its availability instant — including the EST/EDT examples, which contained an impossible M15 close time (`14:20`, not a real M15 boundary) as a direct symptom of this bug. §4 adds real completeness validation with real numbers, not just a "skip if empty" check.

## 1. CRITICAL — fixed: `retest_index` vs. `confirmation_index`, and the fill-pass redesign

### 1.1 Evidence

`detector/entries/model1.py::_track_anchor` (lines 101-166): scanning forward from `anchor_index+1`,
1. at some index `j1`, the body-engulf closes beyond `body_high`/`body_low` → `confirmed = True`, `entry_price` fixed (via `_select_entry`) — **this does not return a signal yet**.
2. at some LATER index `j2 >= j1+1`, price wicks back into the body (`_wick_overlaps`) → `retest_index = j2`.
3. at some index `j3 >= j2` (can equal `j2`, or be several bars later), `_closes_beyond_open(candle.close, retest_open, direction)` finally becomes true → `return signal(retest_index=j2, status=CONFIRMED, confirmation_index=j3)`.

So `j2` (`retest_index`) and `j3` (`confirmation_index`) are frequently different, and **the `Model1Signal` object itself does not exist as `CONFIRMED` until `j3`**. Before `j3`, there is no way to know the anchor will resolve `CONFIRMED` rather than `INVALIDATED` (price could still break the protected extreme between `j2` and `j3`) or `PENDING` (the lookback window could run out first).

Separately: `_population_cuts` (`detector/backtest/population.py:70-96`) only checks `signal.retest_index is None` to decide exclusion — it does **not** check `signal.status`. A `PENDING` signal (retest found, but the window ran out before any re-break close) and even an `INVALIDATED` signal that happened to have a `retest_index` set before the invalidating breach **both survive into the candidate population** exactly like a `CONFIRMED` one, as long as `retest_index is not None`. This is pre-existing production behavior, inherited unchanged by A/B1/B2, and I am not changing it — but it means "the signal has a `retest_index`" was never a safe proxy for "the signal is known to be valid" even in production's own terms. `confirmation_index` is the one field that is always set, for every outcome (`CONFIRMED`/`PENDING`/`INVALIDATED`), representing "the index the scan loop had reached when it finished" — i.e., the earliest instant the signal's *final, as-scanned* state is knowable at all.

`detector/backtest/simulate.py::_fill_pass` (lines 122-136): `eligible_at=lambda c: c.retest_index` — confirms the reviewer's point exactly: fills are sought starting at `retest_index`, with no floor at `confirmation_index` at all.

### 1.2 Concrete example (retest before confirmation, and how the fix stops an early fill)

Bullish anchor at M15 index 100, `entry_price = 1.10500` (fixed at the body-engulf index, say `j1=102`).
- `j=103`: price wicks back into the anchor's body → `retest_index = 103`, `retest_open = 1.10450`.
- `j=104`: price dips to `low=1.10490` — **this touches `entry_price`**. Price does not yet close back beyond `retest_open` this bar.
- `j=105`: price finally closes beyond `retest_open` → `confirmation_index = 105`. The `Model1Signal` is `CONFIRMED` only now.

Under the reviewed (broken) design, `eligible_at = retest_index = 103` would let `_fill_pass`'s sweep credit the touch at `j=104` as a valid fill — one bar *before* the signal was even confirmed. If price never returns to `1.10500` after `j=105`, production's `simulate()` would still show a filled, resolved trade that, causally, could not have existed: at `j=104` nothing yet distinguished this anchor from one about to `INVALIDATE`.

**Fix**: `eligible_at = confirmation_index = 105`, not `retest_index`. The candidate is not even pushed into the fill-sweep's heap until step `j=105` is reached, so the `j=104` touch is correctly invisible to it. If price does not come back to `1.10500` at or after `j=105` within `max_fill_wait`, the trade is correctly `never_filled` — not a phantom early fill.

### 1.3 Separating the five moments explicitly (per the review's ask)

| Moment | Definition | Field |
|---|---|---|
| Retest observed | `m15.candles[signal.retest_index]` wicks back into the anchor body | `retest_observed_index` |
| Confirmation available | `m15.candles[signal.confirmation_index]`'s own bar has closed (see §3) — the signal's final state (`CONFIRMED`/`PENDING`/`INVALIDATED`) is now knowable | `model1_available_index` / `model1_available_ts` |
| Order constructible | Same instant as confirmation available, for a `CONFIRMED` signal only — `entry_price`/`stop_loss`/`take_profit`/`partial_price` are already fixed values (from `_build_candidate`, unmodified), so nothing new needs computing | `order_constructed_ts` = `model1_available_ts` |
| Order placed | Same instant (no separate scanner-discovery delay here, unlike B1 — this whole path only ever used information real at the time) | `order_placed_ts` = `model1_available_ts` |
| First executable instant | The first M15 bar at or after `order_placed_ts` whose OWN close has occurred — i.e., `eligible_at = model1_available_index` itself, interpreted as "this bar's close is `model1_available_ts`" | `first_fillable_index` = `model1_available_index` |

Only `CONFIRMED` signals are carried forward into C1/C2's candidate stream at all (an explicit, new filter — stricter than production's existing `retest_index is not None` check, and documented as a deliberate divergence: production's looser behavior is a pre-existing question about A/B1/B2, not something this causal-correctness arm should reproduce).

### 1.4 `fill_pass_c` — the actual design (supersedes "no custom fill pass needed")

```python
# causal_intrabar.py — reuses _fill_sides, two_heap_sweep, _resolve_exits
# from backtest.simulate UNMODIFIED, imported. Only eligible_at changes,
# exactly the same shape as fill_b1.fill_pass_b1, floored at a DIFFERENT
# per-candidate index (model1_available_index, not a placement delay).

def fill_pass_c(candidates, candles, max_fill_wait, available_index_by_signal_id):
    eligible = [c for c in candidates if available_index_by_signal_id.get(c.signal_id) is not None]
    fill_order = sorted(eligible, key=lambda c: available_index_by_signal_id[c.signal_id])
    fill_results = two_heap_sweep(
        candles, fill_order,
        eligible_at=lambda c: available_index_by_signal_id[c.signal_id],
        sides=_fill_sides(), default=None,
    )
    filled = [
        (candidate, fill_index) for candidate, fill_index in zip(fill_order, fill_results)
        if fill_index is not None
        and fill_index - available_index_by_signal_id[candidate.signal_id] <= max_fill_wait
    ]
    return filled, len(fill_order) - len(filled)
```

`_resolve_exits` (unmodified) is then called on `filled` exactly as production does — SL/TP/partial/breakeven resolution has no causality defect of its own (confirmed in Phase 1), so it is reused as-is, satisfying "no reimplementes innecesariamente ... las funciones de salida que sean correctas."

This is architecturally identical in shape to `fill_b1.fill_pass_b1` (same reuse of `_fill_sides`/`two_heap_sweep`/`_resolve_exits`), but floored at a semantically different index. **Correction to the prior design: C1/C2 are NOT like B2 in this respect — they need the same kind of custom fill pass B1 needed, just with a different, correctly-causal floor.**

## 2. CRITICAL — fixed: Key Levels compared by timestamp, never by raw index across grids

### 2.1 Evidence

`KeyLevel.origin_index`/`expiry_index` (`detector/core/key_level.py`) are indices into whichever H4-equivalent series built them:
- FVG levels (`primitives/fvg.py::to_key_levels`): `origin_index = fvg.end_index` — the THIRD candle of the 3-candle gap pattern, i.e., the index into the **broker H4 grid** (`detect_fvgs` is always called on `h4` = the broker-grid series in `build_key_levels`).
- Order-Block levels (`composite/ict_order_block.py::to_key_levels`): `origin_index = block.confirmation_index` — documented as "first provably-knowable index" — but this is an index into the **Daily** series, immediately reindexed into **broker-H4-index-space** by `alignment/htf_ltf.py::_reindex_daily_key_levels`, which (per its own code comment) uses `_daily_close` (conservative: the Daily candle's close, never knowable earlier) → `_ceiling_htf_index` against `htf_timestamps` — and `htf_timestamps` there is explicitly the **broker H4 grid's** timestamps (the only H4 series `build_key_levels` is ever called with).

So every `KeyLevel.origin_index`/`expiry_index` in this codebase is, and can only be, an index into the **broker H4 grid**. `_key_level_credit_map`'s check `level.origin_index < purge_index` (and the expiry check) is only meaningful when `purge_index` is *also* a broker-H4-grid index. **C2's "current candle" is a NY-anchored feeder candle — a different series, with a different count and different boundaries. Passing its position as `purge_index` into that comparison would compare two unrelated numbers.**

I did not re-derive `detect_order_blocks`'s own internal `confirmation_index` causal correctness from scratch (out of scope for this phase, same inherited-trust boundary as §8.1) — I verified only the documented contract and the reindexing step, which are both explicitly causal by their own comments.

### 2.2 Fix: a timestamp bridge, Key-Level source held constant between C1 and C2

Per the review's point 6/7 ("mantener constante la fuente de Key Levels"), **both C1 and C2 use the exact same `KeyLevel` objects**, built once from the broker H4 + Daily series exactly as `build_key_levels` already does (unmodified call, same as A/B1/B2). What changes is *how the credit check is evaluated* — not reimplemented, but **translated from index-space to timestamp-space**, because that is the one thing that stays valid across two different candle grids:

```python
# causal_intrabar.py — a NEW function, replacing a direct call to
# _key_level_credit_map for the provisional/incremental case. Does not
# reimplement FVG/Order-Block detection or the credit RULE (origin before
# purge, inside the zone, unexpired) -- only restates that rule in
# timestamps instead of raw indices, since indices stop being comparable
# the moment two different grids are involved.

def key_level_credited(purge_extremes: tuple[float, ...], purge_observed_at: datetime,
                        key_levels: list[KeyLevel], h4_broker: OHLCSeries) -> KeyLevel | None:
    def available_at(idx: int) -> datetime:
        return h4_broker.candles[idx].timestamp + H4_DURATION   # bar-close contract, see §3
    qualifying = [
        level for extreme in purge_extremes for level in key_levels
        if available_at(level.origin_index) < purge_observed_at
        and (level.expiry_index is None or purge_observed_at <= available_at(level.expiry_index))
        and level.bottom <= extreme <= level.top
    ]
    return max(qualifying, key=lambda lv: lv.origin_index) if qualifying else None
```

This reproduces `_key_level_credit_map`'s exact rule (origin strictly before the purge, not yet expired, extreme inside the zone, highest-origin-index tiebreak) — restated so the only quantity ever compared against another is a `datetime`, which is valid regardless of which series (broker-grid for C1, NY-feeder for C2) supplied `purge_observed_at`. `_purge_wick_extremes` is still reused unmodified to compute `purge_extremes` from the provisional candle.

**This is the one place the design knowingly does NOT reuse an existing function's comparison logic verbatim** (`_key_level_credit_map` itself) — documented here as a deliberate, narrow divergence with a stated reason (cross-grid index incomparability), not a silent reimplementation, and not touching `detector/`.

### 2.3 Remaining explicit blocker

Per the review's own instruction: *"Si la causalidad de las fuentes de Key Level sigue sin poder demostrarse, debe tratarse como un bloqueo explícito."* I have verified the documented *contract* (origin = first provably-knowable index, conservative Daily-close reindexing) but have **not** independently re-derived `detect_fvgs`/`detect_order_blocks`'s own internal logic line-by-line the way I did for `_track_anchor`. **This stays an open blocker**, carried by every arm (A/B1/B2/C1/C2 alike) equally — it does not bias a C1-vs-C2 comparison against each other, but it does mean no arm's absolute numbers can yet be called fully, end-to-end causally proven from Key-Level origin through to position close. Resolving it would require the same depth of code-tracing §1 just got, applied to `primitives/fvg.py`'s 3-candle gap confirmation and `composite/ict_order_block.py`'s swing/MSS-based confirmation — not done in this revision; flagged for explicit decision on whether to do it before trusting C1/C2's own absolute R numbers, as opposed to trusting only the *qualitative, relative* C1-vs-C2 and C-vs-A comparison (which is unaffected, since the same unverified Key-Level pipeline feeds both C1 and C2 identically).

## 3. HIGH — fixed: bar open/close/availability contract

### 3.1 Evidence

The dataset's `Candle.timestamp` is the bar's **open**. A 15-minute bar opening `14:15` closes `14:30`; its own high/low/close are only real-world-knowable at `14:30`, not `14:15`. The reviewed design's `provisional_feeder_candle` filtered M15 bars by `timestamp <= as_of_ts` — using the OPEN timestamp as if it were the availability cutoff. That is the exact bug the review caught in the EST/EDT examples: I wrote "sweep+Key-Level resolve at M15 close `14:20`" — `14:20` is not a real M15 boundary (M15 closes only ever fall on `:00/:15/:30/:45`); I had silently conflated "the M15 bar containing roughly this moment" with a real close instant.

### 3.2 Fixed contract (used everywhere from here on)

```python
M15_DURATION = timedelta(minutes=15)
H4_DURATION  = timedelta(hours=4)

def bar_open_ts(candle) -> datetime: return candle.timestamp
def bar_close_ts(candle, duration) -> datetime: return candle.timestamp + duration
def available_at(candle, duration) -> datetime: return bar_close_ts(candle, duration)   # the ONLY field read for "is this known yet"
```

Every place the design (or its examples) used a bare `.timestamp` to mean "known as of," it must instead use `available_at`. Concretely: `provisional_feeder_candle(m15_series, open_ts, as_of_ts)` aggregates `m15_series.candles[i]` for every `i` with `available_at(m15_series.candles[i], M15_DURATION) <= as_of_ts` (equivalently: `m15.candles[i].timestamp + 15min <= as_of_ts`, i.e., `m15.candles[i].timestamp < as_of_ts - 15min + epsilon` — in practice this means "every bar up to and including the one whose open is `as_of_ts - 15min`", i.e., one bar *earlier* in open-time terms than a naive `timestamp <= as_of_ts` filter would include). `activation_instant`, `model1_available_ts`, `feeder_ref_close_ts` — all of §1's and the state machine's timestamps — are `available_at(...)` values, never bare `.timestamp`.

### 3.3 Corrected examples (replacing the broken ones)

**EDT, 1AM model**: reference "9PM" feeder candle opens `2003-05-05 01:00 UTC` (9pm NY EDT), its `available_at = 01:00 + 4h = 05:00 UTC` — this is also the "1AM" current candle's own open. Suppose the M15 bar opening `2003-05-05 06:15 UTC` (closing `06:30`) is the first whose accumulated high/low both sweeps the 9PM range AND credits a Key Level once `available_at` for that bar is reached: `activation_instant = available_at(m15[06:15], 15min) = 06:30 UTC` (**not** `06:20` — there is no M15 bar closing at `:20`). `MODEL_1AM` window for this trigger: NY 02:00-04:00 EDT = UTC 06:00-08:00. `eligible_start = max(06:00, 06:30) = 06:30`; `eligible_end = 08:00`.

**EST, 9AM model**: reference "5AM" feeder candle opens `2026-01-15 10:00 UTC` (5am NY EST), `available_at = 14:00 UTC` = the "9AM" current candle's own open. Suppose the M15 bar opening `14:15 UTC` is the first to sweep+credit: `activation_instant = available_at(m15[14:15], 15min) = 14:30 UTC`. `MODEL_9AM` window: NY 09:00-10:30 EST = UTC 14:00-15:30. `eligible_start = max(14:00, 14:30) = 14:30`; `eligible_end = 15:30`.

## 4. HIGH — fixed: feeder-candle completeness, with real numbers

### 4.1 Validation contract

```python
def validate_complete_feeder_bucket(bucket: tuple[Candle, ...], expected_open_ts: datetime, expected_count: int = 16) -> bool:
    if len(bucket) != expected_count:
        return False
    if bucket[0].timestamp != expected_open_ts:
        return False
    return all(bucket[i + 1].timestamp - bucket[i].timestamp == M15_DURATION for i in range(len(bucket) - 1))
```

A bucket that fails this check is **not** turned into a `CompleteFeederCandle` at all — it is marked `incomplete` (holiday/gap/DST), reported, and excluded from being used as a *reference range* (§2's "previous candle"). This is stricter than the reviewed design's "skip if zero M15 bars" — it now also catches a *partially* populated bucket.

### 4.2 Empirical measurement (EURUSD, run against real data, full 2003-2026 history)

| Construction | Buckets with ≥1 bar | Incomplete (≠16 bars) | Misaligned despite 16 bars |
|---|---|---|---|
| NY-anchored 9AM | 6,118 | 11 (0.18%) | 0 |
| NY-anchored 1AM | 6,128 | 12 (0.20%) | 0 |
| Broker-grid (today's code's "1AM" slot) | 6,128 | 4 (0.07%) | 0 |

Real examples of incomplete buckets: `2013-12-25` (Christmas, 8/16 bars), `2003-07-22`/`2003-08-15`/`2003-09-02` (early-history thin-liquidity gaps, 12-15/16 bars), `2004-03-30` and `2005-06-10` (DST-adjacent gaps, 9-14/16 bars). **Zero cases of 16 bars present but misaligned/non-consecutive** — when this dataset has a full bucket, it is always a clean, contiguous 4-hour span; incompleteness is always an outright missing-bar count, never a hidden ordering problem. Rate is low (~0.1-0.2%) but nonzero and must be handled explicitly, not assumed away — exactly the review's point. USDCAD/AUDUSD not yet re-measured for this specific check; expected to be similar in kind (same broker, same M15 grid) but not yet confirmed — flagged, not assumed.

## 5. Revised state machine

| State | Entered when | Timestamp (always an `available_at` value) |
|---|---|---|
| `WAITING_FOR_FEEDER` | Previous (reference) feeder candle still forming, or not yet validated complete (§4) | — |
| `WAITING_FOR_SWEEP_AND_KEY_LEVEL` | Reference candle passed §4's completeness check; its own `available_at` has been reached | `feeder_ref_available_ts` |
| `HTF_CONDITIONS_OBSERVED` *(renamed/split from the old `WAITING_FOR_MODEL1`, per review §5)* | First M15 bar whose `available_at` makes the provisional current-candle's running high/low both sweep the reference range AND credit a Key Level (§2.2) | `activation_instant_ts` |
| `WAITING_FOR_MODEL1` | Immediately follows `HTF_CONDITIONS_OBSERVED` — `confirm_in_ltf_window` is now searching `[max(window_start, activation_instant), window_end)` | (no new timestamp; a search interval, not an instant) |
| `MODEL1_CONFIRMED_AND_AVAILABLE` *(renamed, per review §5 — no longer conflated with "retest")* | `confirm_in_ltf_window` returns `status=CONFIRMED`; `model1_available_ts = available_at(m15.candles[signal.confirmation_index], M15_DURATION)` | `model1_available_ts` |
| `ORDER_CONSTRUCTED_AND_PLACED` | Same instant as above (§1.3 — nothing new to wait for; nothing here uses `retest_ts` as if it were later confirmation) | `order_placed_ts = model1_available_ts` |
| `ORDER_ACTIVE` | `fill_pass_c` has pushed the candidate into its sweep (eligible from `order_placed_ts`'s bar onward) | `order_placed_ts` (carried forward) |
| `FILLED` / `EXPIRED` / `INVALIDATED` | `fill_pass_c` + unmodified `_resolve_exits` outcome | `entry_ts`/`exit_ts` |

Explicit invariant (tested, §6): for every signal, `feeder_ref_available_ts <= activation_instant_ts <= model1_available_ts <= entry_ts (if filled) <= exit_ts`. **`retest_ts` is never used as an activation timestamp anywhere** — it is retained only as a diagnostic field (when the retest was *observed*, for the reconciliation file), never as a decision boundary.

## 6. Automated tests needed (additions to the existing suite, not a rewrite)

1. `test_fill_pass_c_never_fills_between_retest_and_confirmation` — the §1.2 example, made concrete: assert a touch strictly between `retest_index` and `confirmation_index` is never credited, and the SAME touch, moved to at-or-after `confirmation_index`, is credited.
2. `test_key_level_credited_rejects_cross_grid_index_reuse` — construct a `KeyLevel` with `origin_index=5` on a 10-candle broker H4 series and a *different*, shorter NY-feeder series; assert `key_level_credited` only ever compares via `available_at(...)` timestamps, never raw indices (i.e., changing the NY-series' bucket count must not change which levels credit).
3. `test_bar_available_at_is_open_plus_duration` — pins §3.2's contract for both M15 (15 min) and H4-feeder (4h) durations, including the two DST-transition days found in §4.2.
4. `test_validate_complete_feeder_bucket_rejects_partial_and_misaligned` — table-driven: 16 consecutive bars (pass), 15 bars (fail), 16 bars with a duplicate/gap (fail), bars starting one step late (fail).
5. `test_state_machine_timestamps_are_monotonic` — run C1 (cheap, synthetic) and assert the §5 invariant chain holds for every produced signal.
6. `test_c1_c2_share_everything_except_candle_source` — a structural test: both call the same `detect_triggers(feeder_source, ...)` entry point; assert via introspection or a shared-code-path marker that no C1-only or C2-only branch exists outside the swapped `feeder_source` argument.
7. Re-affirm from the existing suite: Arm A still reproduces the audited baseline exactly (already covered, unaffected by this revision).

## 7. B1-realistic caveat (review §7 — documentation only, B1 not rerun)

`trades_b1_realistic.csv`'s `-145.86R` approximates the price available at order placement using the M15 bar's **close** price, and models scanner discovery delay as a flat `+120s` (`POLL_SECONDS`) added to the H4 close. Two compounding approximations, both stated plainly here (not re-run): (a) real MT5 execution would use a live bid/ask tick at the actual moment of placement, not a 15-minute bar's close — intra-bar price movement between the true placement instant and that bar's close is invisible to this approximation in either direction; (b) the real discovery delay is uniformly distributed over `[0, 120s]` depending on poll phase relative to the H4 close, not a fixed `120s` — B1-realistic used the conservative worst-case end of that range, not an average. **B1-realistic's number is a directional, order-of-magnitude diagnostic of what realistic discovery latency does to the strategy — not a claim of reproducing actual historical MT5 fills.**

## 8. C1 vs. C2 isolation, reconfirmed under the fixes

Both arms now share: §1's `fill_pass_c`, §2's `key_level_credited` (same `KeyLevel` objects, sourced identically), §3's bar contract, §5's state machine, and `build_stage6_population`/`_resolve_exits` (unmodified). The **only** swapped dependency remains which function supplies the reference/current `ProvisionalFeederCandle`/`CompleteFeederCandle` pair (§4's broker-grid builder for C1, NY-anchored builder for C2) — enforced by both arms calling one shared `causal_intrabar.detect_triggers(feeder_source, h4_broker_for_key_levels, ...)`, where `h4_broker_for_key_levels` is **always** the broker grid (Key-Level source held constant per §2.2, independent of which grid supplies the sweep side).

## 9. Risks, ambiguities, pending decisions (updated)

1. **Key-Level source causality not independently re-derived** (§2.3) — now an explicit, named blocker on trusting C1/C2's *absolute* numbers, though not on the C1-vs-C2 *comparison* itself.
2. DOL-gated reversal/continuation profile selection — still out of scope (charter defers to unreleased material).
3. 9AM sweeping the 1AM range (i-2) instead of 5AM's (i-1) — still out of scope per user restriction.
4. Non-Model-1 (TSQ/breaker-block) entries — still out of scope, no detector scaffolding.
5. Intrabar same-M15-bar ambiguity — unchanged conservative policy (resolve at that bar's `available_at`), now correctly defined per §3.
6. DST-transition-day 4-hours convention — unchanged policy, now with real measured impact (§4.2: 2 of the ~23 incomplete-bucket examples found were DST-adjacent, out of ~6,100+6,100 buckets checked — small, not zero, reported per-pair rather than assumed away).
7. **New**: USDCAD/AUDUSD have not yet been run through §4's completeness check — only EURUSD has real numbers so far.

## 10. Explicit answer to "is this ready for implementation?"

**Not yet fully** — two things should be decided before implementation, not assumed by me:
- Whether §2.3's open Key-Level-source-causality question must be resolved (full trace of `primitives/fvg.py`/`composite/ict_order_block.py`) *before* trusting C1/C2's absolute R numbers, or whether it is acceptable to proceed now and treat it as a stated limitation on the final report (it does not bias C1 vs. C2 against each other either way).
- Whether to also run §4's completeness check against USDCAD/AUDUSD before implementation, or accept EURUSD's measured rate as representative.

Everything else in this revision (§1's fill-pass redesign, §2.2's timestamp bridge, §3's bar contract, §5's state machine) is a concrete, code-level design with no remaining open question I'm aware of — ready to implement once the two points above are answered.
