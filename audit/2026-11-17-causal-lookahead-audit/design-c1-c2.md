# Design — Intrabar causal detector (Arms C1/C2), REVISED (round 2)

Status: **design only, not implemented**. Round 1 revised the version reviewed at commit `07fc24c` (4 blocking issues). This round 2 closes the two pending decisions from round 1's §10 (Key-Level source causality; USDCAD/AUDUSD completeness) and fixes one more critical issue a further review found in round 1's own `fill_pass_c` fix. Nothing under `detector/`/`scanner/` touched; nothing in `/docs` touched; A/B1/B2 outputs untouched; no commits made from this revision.

## 0. What changed since round 1, and why

Round 1 fixed `fill_pass_c` to floor fill-eligibility at `confirmation_index` instead of `retest_index` — an improvement, but **still not causally sound by itself**: the confirming M15 bar's own high/low (its *full* 15-minute range) was still being used to check for a fill, even though the order is only placed once that bar's *close* occurs. §1 below fixes this precisely: the first fillable bar is the one *after* confirmation, located by real timestamp (not a blind `+1`), with two new required test cases. §2 now carries a full, independent causal trace of `primitives/fvg.py` and `composite/ict_order_block.py` (swings → MSS → displacement → anchor), closing round 1's open blocker on Key-Level-source causality. §4 adds the same completeness measurement for USDCAD and AUDUSD that round 1 only had for EURUSD, including one real, non-trivial anomaly (AUDUSD, concentrated in 2007-2009).

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

Under the round-1-reviewed (broken) design, `eligible_at = retest_index = 103` would let `_fill_pass`'s sweep credit the touch at `j=104` as a valid fill — one bar *before* the signal was even confirmed.

### 1.2b Round-2 finding: round 1's fix (`eligible_at = confirmation_index`) was still incomplete

A further review caught this: bar `j=105` (the confirmation bar) itself has a full 15-minute range (say it opens `09:30`, closes `09:45`). Its `low`/`high` reflect price action across that *entire* 15 minutes — but the order is only placed once that bar's **close** occurs, i.e., at `09:45`. If `eligible_at = confirmation_index = 105` is used directly, `_fill_sides`' sweep checks bar `105`'s *own* `low`/`high` against `entry_price` — using price movement from `09:30`-`09:44`, before the order existed. That is the same class of bug §1.1 fixed, one bar later.

**Corrected fix**: the first fillable bar is the first one whose *own open* is at or after `order_placed_ts` (`confirmation_index`'s close) — not `confirmation_index` itself:

```python
first_fillable_index = bisect.bisect_left(m15_timestamps, order_placed_ts)
# order_placed_ts = available_at(m15.candles[confirmation_index], M15_DURATION)
#                  = m15.candles[confirmation_index].timestamp + M15_DURATION
```

On a gapless grid this equals `confirmation_index + 1` exactly (verified: `m15.candles[confirmation_index + 1].timestamp == m15.candles[confirmation_index].timestamp + M15_DURATION` whenever no gap follows). The `bisect` form is used anyway, per the review's explicit instruction, because §4 confirms real gaps exist (holidays, DST) where a blind `+1` would land on a bar that does not actually open at `order_placed_ts` — `bisect_left` on real timestamps always finds the correct next *actually existing* bar.

If price touched `entry_price` only inside the confirmation bar (`j=105`, `09:30`-`09:45`) and never again at or after `first_fillable_index` (`09:45` onward), the trade is `never_filled` — not filled at `j=105`. If price touches `entry_price` again at or after `first_fillable_index`, *that* later touch is the credited fill.

### 1.3 Separating the five moments explicitly (per the review's ask), corrected

| Moment | Definition | Field |
|---|---|---|
| Retest observed | `m15.candles[signal.retest_index]` wicks back into the anchor body | `retest_observed_index` |
| Confirmation available | `m15.candles[signal.confirmation_index]`'s own bar has closed (§3) — the signal's final state (`CONFIRMED`/`PENDING`/`INVALIDATED`) is now knowable | `model1_available_ts = available_at(confirmation_index)` |
| Order constructible | Same instant as confirmation available, for a `CONFIRMED` signal only — `entry_price`/`stop_loss`/`take_profit`/`partial_price` are already fixed values (from `_build_candidate`, unmodified) | `order_constructed_ts = model1_available_ts` |
| Order placed | Same instant (no separate scanner-discovery delay here, unlike B1) | `order_placed_ts = model1_available_ts` |
| **First executable instant** | The first M15 bar whose own **open** is `>= order_placed_ts` — i.e. the bar *after* the confirmation bar, never the confirmation bar itself | `first_fillable_index = bisect_left(m15_timestamps, order_placed_ts)` **(corrected from round 1, which wrongly used `confirmation_index` itself)** |

Only `CONFIRMED` signals are carried forward into C1/C2's candidate stream at all (an explicit, new filter — stricter than production's existing `retest_index is not None` check, a deliberate divergence unchanged from round 1).

### 1.4 `fill_pass_c` — corrected design

```python
# causal_intrabar.py — reuses _fill_sides, two_heap_sweep, _resolve_exits
# from backtest.simulate UNMODIFIED, imported. eligible_at and the
# max_fill_wait anchor both use first_fillable_index (the bar AFTER
# confirmation, located by real timestamp) -- never confirmation_index
# itself, and never retest_index.

def fill_pass_c(candidates, candles, m15_timestamps, max_fill_wait,
                 order_placed_ts_by_signal_id, confirmation_index_by_signal_id):
    first_fillable = {
        sid: bisect.bisect_left(m15_timestamps, ts)
        for sid, ts in order_placed_ts_by_signal_id.items()
    }
    # Round-3 guard: the timestamp-based lookup must never land ON the
    # confirmation bar itself, regardless of what the timestamps say --
    # first_fillable_ts >= model1_available_ts is the real invariant
    # (equality is fine on a gapless grid), but the INDEX must still move
    # forward by at least one bar every time.
    for sid, idx in first_fillable.items():
        assert idx > confirmation_index_by_signal_id[sid], (
            f"{sid}: first_fillable_index {idx} must be strictly after confirmation_index "
            f"{confirmation_index_by_signal_id[sid]}"
        )
    eligible = [c for c in candidates if first_fillable.get(c.signal_id, len(candles)) < len(candles)]
    fill_order = sorted(eligible, key=lambda c: first_fillable[c.signal_id])
    fill_results = two_heap_sweep(
        candles, fill_order,
        eligible_at=lambda c: first_fillable[c.signal_id],
        sides=_fill_sides(), default=None,
    )
    filled = [
        (candidate, fill_index) for candidate, fill_index in zip(fill_order, fill_results)
        if fill_index is not None and fill_index - first_fillable[candidate.signal_id] <= max_fill_wait
    ]
    return filled, len(fill_order) - len(filled)
```

`_resolve_exits` (unmodified) is then called on `filled` exactly as production does — SL/TP/partial/breakeven resolution has no causality defect of its own (confirmed in Phase 1), reused as-is.

### 1.5 The two required test cases (both now specified precisely)

1. **`test_fill_pass_c_touch_only_during_confirmation_bar_never_fills`**: bullish candidate, `entry_price=1.10500`; confirmation bar (`confirmation_index`, opening `09:30`, closing `09:45`) has `low=1.10490` (touches); every bar from `first_fillable_index` (`09:45` onward) through `max_fill_wait` has `low > 1.10500` (never touches again). **Required result: `never_filled`.**
2. **`test_fill_pass_c_touch_after_activation_fills_at_that_later_touch`**: same setup, but one bar at or after `first_fillable_index` (say `10:15`) also has `low=1.10495` (touches). **Required result: filled at `10:15`'s index, never at the confirmation bar's index.**

## 2. CRITICAL — fixed: Key Levels compared by timestamp, never by raw index across grids

### 2.1 Evidence

`KeyLevel.origin_index`/`expiry_index` (`detector/core/key_level.py`) are indices into whichever H4-equivalent series built them:
- FVG levels (`primitives/fvg.py::to_key_levels`): `origin_index = fvg.end_index` — the THIRD candle of the 3-candle gap pattern, i.e., the index into the **broker H4 grid** (`detect_fvgs` is always called on `h4` = the broker-grid series in `build_key_levels`).
- Order-Block levels (`composite/ict_order_block.py::to_key_levels`): `origin_index = block.confirmation_index` — documented as "first provably-knowable index" — but this is an index into the **Daily** series, immediately reindexed into **broker-H4-index-space** by `alignment/htf_ltf.py::_reindex_daily_key_levels`, which (per its own code comment) uses `_daily_close` (conservative: the Daily candle's close, never knowable earlier) → `_ceiling_htf_index` against `htf_timestamps` — and `htf_timestamps` there is explicitly the **broker H4 grid's** timestamps (the only H4 series `build_key_levels` is ever called with).

So every `KeyLevel.origin_index`/`expiry_index` in this codebase is, and can only be, an index into the **broker H4 grid**. `_key_level_credit_map`'s check `level.origin_index < purge_index` (and the expiry check) is only meaningful when `purge_index` is *also* a broker-H4-grid index. **C2's "current candle" is a NY-anchored feeder candle — a different series, with a different count and different boundaries. Passing its position as `purge_index` into that comparison would compare two unrelated numbers.**

### 2.1b Full independent causal trace (round 2 — closes round 1's open blocker)

Round 1 only verified the documented *contract* on `to_key_levels`'s own comments. Per this round's instruction ("no aceptes comentarios del código como prueba suficiente"), every dependency was traced to its primitive source:

**FVG chain** (`primitives/fvg.py`):
- `detect_fvgs`: `_formed_gap(candles[i], candles[i+2])` compares candle `i`'s high/low against candle `i+2`'s low/high — needs candle `i+2`'s own high/low, i.e., needs candle `i+2` to have closed. The size filter uses `atr(candles, i+2)`.
- `core/atr.py::atr(candles, index)`: `start = max(0, index - period + 1); true_ranges = [true_range(candles, j) for j in range(start, index+1)]` — strictly backward-looking (never reads `candles[j]` for `j > index`), and `true_range` itself only reads `candles[index]` and `candles[index-1]`. No future dependency.
- `to_key_levels`: `origin_index = fvg.end_index = i+2`. **Verdict: `origin_index`'s true availability is `available_at(candles[i+2], H4_DURATION)` — that candle's own close — exactly what `key_level_credited` (§2.2) already uses. No bug.**

**Order-Block chain** (`composite/ict_order_block.py` + its three dependencies):
1. `primitives/swing.py::detect_swings`: a swing at index `i` requires `candles[i].high > candles[i-1].high and candles[i].high > candles[i+1].high` (symmetric for lows) — **needs candle `i+1` to exist and have closed**. A swing's own true availability is `available_at(candles[i+1])`, one candle later than its own index — confirmed, this is the exact mechanism `backtest/levels.py::stop_loss`'s own docstring already names ("`detect_swings` only confirms a swing at index `i` once candle `i+1` exists").
2. `composite/mss.py::detect_mss_events`: for each swing, `_sweep_decisive_breaks` only considers candles from `swing.index + 1` onward (`eligible_at = p[0].index + 1`) and resolves via `candle.close` at the break index — so `MSSEvent.index = break_index` always satisfies `break_index >= swing.index + 1`, and the event's own availability (`available_at(candles[break_index])`) is, by construction, never earlier than the swing's own availability (`available_at(candles[swing.index+1])`), whether or not they coincide on the same bar. **No violation.**
3. `composite/displacement.py::confirm_displacement`: accumulates `candle.close - candle.open` from `break_index` through at most 3 candles, returning the first index where the net crosses an ATR(14)-based threshold — that returned `index`'s own close is part of the sum, so **its true availability is `available_at(candles[index], H4_DURATION)`** — exactly what `origin_index = block.confirmation_index` represents, and exactly what `key_level_credited` already uses.
4. `composite/order_block_scan.py::scan_for_anchor`: a pure *backward* scan (`range(displacement_start - 1, floor - 1, -1)`) over candles strictly before `displacement_start` (which is itself before `confirmation_index`) — every candle it reads already closed before `confirmation_index`'s own close. **No future dependency.**
5. `_resolve_lifecycle` (mitigation/invalidation): forward scan from `confirmation_index + 1`, reading each candle's own `low`/`high`/`close` — same uniform bar-close convention as everywhere else.

**Daily-sourced reindexing** (`alignment/htf_ltf.py::_reindex_daily_key_levels`/`_daily_close`/`_ceiling_htf_index`, re-confirmed): `_daily_close` returns the *next* Daily candle's open as a conservative stand-in for "this Daily candle's own close" (explicitly documented, and conservative in the right direction — never earlier than the real close); `_ceiling_htf_index` finds the first broker-H4 index whose own timestamp is `>=` that conservative instant. Combined with the strict `origin_index < purge_index` check (and the broker H4 grid's own candles being contiguous, confirmed in Phase 1's M15-aggregation check), `purge_index`'s own open is guaranteed to be at or after the Daily level's real confirmation. **No violation.**

### 2.1c Verdict

**FVG and Order-Block Key Levels are both causally correct**, independently re-derived from their primitive detectors (swings, MSS, displacement, ATR, backward anchor scan) rather than taken on faith from a comment — answering this round's explicit question #1/#2: **yes, both are causally correct**, under one condition that was already true of the design: the credit check must use `available_at(origin_index)` (that candle's own **close**), never its open — which is exactly what `key_level_credited` (§2.2) implements. **Round 1's open blocker is closed.** Nothing in `detector/` needed to change to reach this conclusion; this was investigation only.

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
    def available_at(idx: int) -> datetime | None:
        # _ceiling_htf_index (alignment/htf_ltf.py:228-237) can return
        # len(htf_timestamps) as an explicit "not yet knowable within this
        # series" sentinel -- indexing h4_broker.candles[idx] at that value
        # raises IndexError. None here means "never available/never
        # expires within the data we have", handled by the caller below.
        if idx >= len(h4_broker.candles):
            return None
        return h4_broker.candles[idx].timestamp + H4_DURATION   # bar-close contract, see §3

    def credited(level: KeyLevel) -> bool:
        origin_at = available_at(level.origin_index)
        if origin_at is None or origin_at >= purge_observed_at:
            return False   # not yet knowable, or knowable only at/after this purge -- never credits
        if level.expiry_index is not None:
            expiry_at = available_at(level.expiry_index)
            if expiry_at is not None and purge_observed_at > expiry_at:
                return False   # expired before this purge
            # expiry_at is None (sentinel): the expiry condition was never
            # found within the available series -- treat as not-yet-expired.
        return True

    qualifying = [
        level for extreme in purge_extremes for level in key_levels
        if credited(level) and level.bottom <= extreme <= level.top
    ]
    return max(qualifying, key=lambda lv: lv.origin_index) if qualifying else None
```

**Round-3 fix**: `available_at` now returns `None` (never `IndexError`) for a sentinel/out-of-range index, and `credited()` treats `origin_at is None` as "not yet knowable -- never credits" (fail closed) while `expiry_at is None` is treated as "never found expiring within the data we have -- not yet expired" (fail open, matching `_key_level_credit_map`'s own `expiry_index is None` branch, which already treats a level with no registered expiry as perpetually valid).

This reproduces `_key_level_credit_map`'s exact rule (origin strictly before the purge, not yet expired, extreme inside the zone, highest-origin-index tiebreak) — restated so the only quantity ever compared against another is a `datetime`, which is valid regardless of which series (broker-grid for C1, NY-feeder for C2) supplied `purge_observed_at`. `_purge_wick_extremes` is still reused unmodified to compute `purge_extremes` from the provisional candle.

**This is the one place the design knowingly does NOT reuse an existing function's comparison logic verbatim** (`_key_level_credit_map` itself) — documented here as a deliberate, narrow divergence with a stated reason (cross-grid index incomparability), not a silent reimplementation, and not touching `detector/`.

### 2.3 Blocker status: CLOSED (see §2.1c)

Round 1 left this open. §2.1c's independent trace through `primitives/fvg.py` and `composite/ict_order_block.py` (down to swings/MSS/displacement/ATR) closes it: both Key-Level sources are causally correct under the `available_at(origin_index)` convention already used by `key_level_credited`.

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

### 4.2 Empirical measurement — all three pairs, full 2003-2026 history (round 2 adds USDCAD/AUDUSD)

| Pair | Construction | Buckets with ≥1 bar | Incomplete (≠16 bars) | Misaligned despite 16 bars |
|---|---|---|---|---|
| EURUSD | NY-anchored 9AM | 6,118 | 11 (0.18%) | 0 |
| EURUSD | NY-anchored 1AM | 6,128 | 12 (0.20%) | 0 |
| EURUSD | Broker-grid | 6,128 | 4 (0.07%) | 0 |
| USDCAD | NY-anchored 9AM | 6,050 | 12 (0.20%) | 0 |
| USDCAD | NY-anchored 1AM | 6,061 | 15 (0.25%) | 0 |
| USDCAD | Broker-grid | 6,061 | 7 (0.12%) | 0 |
| AUDUSD | NY-anchored 9AM | 6,041 | **127 (2.10%)** | 0 |
| AUDUSD | NY-anchored 1AM | 6,056 | 18 (0.30%) | 0 |
| AUDUSD | Broker-grid | 6,056 | 6 (0.10%) | 0 |

**Zero cases of 16 bars present but misaligned/non-consecutive, across all three pairs, all three constructions** — when this dataset has a full bucket, it is always a clean, contiguous 4-hour span; incompleteness is always an outright missing-bar count, never a hidden ordering problem. Duplicate timestamps are structurally impossible in this dataset (`ingestion/loader.py::_validate_timestamp_order` rejects them at CSV-load time), so no separate duplicate check was needed beyond consecutiveness.

**Real examples**: EURUSD `2013-12-25` (Christmas, 8/16), `2004-03-30`/`2005-06-10` (DST-adjacent gaps); USDCAD `2003-12-25`, `2004-01-01` (1/16 — nearly the whole session missing), `2004-03-30`/`2005-06-10`; AUDUSD `2003-12-25`, `2004-01-01`, `2004-03-30`/`2005-06-10`, and (see below) a large 2007-2009 cluster.

**AUDUSD anomaly, investigated rather than assumed**: AUDUSD's NY-anchored 9AM incompleteness (2.10%) is **4-7x every other row in this table**. Characterized its 127 incomplete dates by year rather than guessing: `{2007: 47, 2008: 35, 2009: 25, 2003: 8, 2005: 4, 2010: 3, 2004: 2, 2012: 1, 2014: 1, 2015: 1}` — **84% of the incompleteness (107/127) is concentrated in 2007-2009**, not early-history thin liquidity (which would show up in 2003 and taper off — it does not). This is a genuine, AUDUSD-specific, 2007-2009-concentrated broker-data-export gap pattern affecting the NY 13:00-17:00 UTC window specifically (the 9AM-NY slot) more than the 1AM-NY slot (0.30%) or the broker's own native grid (0.10%) for the same pair/period — consistent with a gap that happens to fall disproportionately inside that particular UTC window during those years, not a general AUDUSD data-quality problem (AUDUSD's OTHER two constructions are in line with EURUSD/USDCAD). **Not yet root-caused further** (e.g., not checked against MT5/broker history of AUDUSD trading-hours changes in 2007-2009) — flagged as a known, quantified, non-uniform gap rather than averaged away.

## 5. Revised state machine

| State | Entered when | Timestamp (always an `available_at` value) |
|---|---|---|
| `WAITING_FOR_FEEDER` | Previous (reference) feeder candle still forming, or not yet validated complete (§4) | — |
| `WAITING_FOR_SWEEP_AND_KEY_LEVEL` | Reference candle passed §4's completeness check; its own `available_at` has been reached | `feeder_ref_available_ts` |
| `HTF_CONDITIONS_OBSERVED` *(renamed/split from the old `WAITING_FOR_MODEL1`, per review §5)* | First M15 bar whose `available_at` makes the provisional current-candle's running high/low both sweep the reference range AND credit a Key Level (§2.2) | `activation_instant_ts` |
| `WAITING_FOR_MODEL1` | Immediately follows `HTF_CONDITIONS_OBSERVED` — `confirm_in_ltf_window` is now searching `[max(window_start, activation_instant), window_end)` | (no new timestamp; a search interval, not an instant) |
| `MODEL1_CONFIRMED_AND_AVAILABLE` *(renamed, per review §5 — no longer conflated with "retest")* | `confirm_in_ltf_window` returns `status=CONFIRMED`; `model1_available_ts = available_at(m15.candles[signal.confirmation_index], M15_DURATION)` | `model1_available_ts` |
| `ORDER_CONSTRUCTED_AND_PLACED` | Same instant as above (§1.3 — nothing new to wait for; nothing here uses `retest_ts` as if it were later confirmation) | `order_placed_ts = model1_available_ts` |
| `ORDER_ACTIVE` | `fill_pass_c` has pushed the candidate into its sweep -- eligible from `first_fillable_index` onward, **the bar AFTER the one whose close produced `order_placed_ts`, never that bar itself** (round-2 fix, §1.2b) | `first_fillable_ts = m15.candles[first_fillable_index].timestamp` (an open, not a close -- this is when the bar the sweep reads FROM begins, not when anything new becomes known) |
| `FILLED` / `EXPIRED` / `INVALIDATED` | `fill_pass_c` + unmodified `_resolve_exits` outcome | `entry_ts`/`exit_ts` |

Explicit invariant (tested, §6): for every signal, `feeder_ref_available_ts <= activation_instant_ts <= model1_available_ts <= entry_ts (if filled) <= exit_ts`. **`retest_ts` is never used as an activation timestamp anywhere** — it is retained only as a diagnostic field (when the retest was *observed*, for the reconciliation file), never as a decision boundary.

## 6. Automated tests needed (additions to the existing suite, not a rewrite)

1. `test_fill_pass_c_never_fills_between_retest_and_confirmation` — §1.2's example: a touch strictly between `retest_index` and `confirmation_index` is never credited.
2. **`test_fill_pass_c_touch_only_during_confirmation_bar_never_fills`** (new, round 2, §1.5.1) — a touch occurring only inside the confirmation bar itself (`confirmation_index`, before `first_fillable_index`) must resolve `never_filled`, not filled.
3. **`test_fill_pass_c_touch_after_activation_fills_at_that_later_touch`** (new, round 2, §1.5.2) — the same setup, with an additional touch at or after `first_fillable_index`, must fill there, never at the confirmation bar.
4. `test_fill_pass_c_first_fillable_index_uses_real_timestamps_across_a_gap` (new, round 2) — construct an M15 series with a gap immediately after `confirmation_index` (next bar opens later than `+15min`); assert `first_fillable_index` resolves to the actual next bar via `bisect`, not a blind `confirmation_index + 1`.
5. `test_key_level_credited_rejects_cross_grid_index_reuse` — construct a `KeyLevel` with `origin_index=5` on a 10-candle broker H4 series and a *different*, shorter NY-feeder series; assert `key_level_credited` only ever compares via `available_at(...)` timestamps, never raw indices.
6. `test_key_level_credited_matches_fvg_and_order_block_origin_semantics` (new, round 2) — two cases, one FVG-sourced (`origin_index = fvg.end_index`) and one Order-Block-sourced (`origin_index = block.confirmation_index`, reindexed), both asserting the credit only fires at-or-after that candle's **close**, never its open — pins §2.1b/§2.1c's trace as a regression test, not just a one-time manual audit.
6b. **`test_key_level_credited_handles_sentinel_origin_and_expiry_without_indexerror`** (new, round 3) — a `KeyLevel` with `origin_index == len(h4_broker.candles)` (the `_ceiling_htf_index` sentinel) must never credit and must never raise `IndexError`; a `KeyLevel` with `expiry_index == len(h4_broker.candles)` (expiry never found within the series) must still credit a purge that is otherwise valid, treated as not-yet-expired.
7. `test_bar_available_at_is_open_plus_duration` — pins §3.2's contract for both M15 (15 min) and H4-feeder (4h) durations, including the two DST-transition days found in §4.2.
8. `test_validate_complete_feeder_bucket_rejects_partial_and_misaligned` — table-driven: 16 consecutive bars (pass), 15 bars (fail), 16 bars with a duplicate/gap (fail), bars starting one step late (fail).
9. `test_state_machine_timestamps_are_monotonic` — run C1 (cheap, synthetic) and assert the §5 invariant chain holds for every produced signal: **`first_fillable_ts >= model1_available_ts`** (not strict — a bar can legitimately open exactly when the previous bar closes, on a gapless grid) **and, separately, `first_fillable_index > confirmation_index` strictly** (the bar-index floor must always move forward by at least one bar, regardless of what the timestamps happen to read). Two sub-cases, both required: (a) consecutive M15 bars with no gap (`first_fillable_index == confirmation_index + 1`, `first_fillable_ts == model1_available_ts` exactly); (b) a data gap right after `confirmation_index` (`first_fillable_index` lands on whatever bar actually exists next, `first_fillable_ts > model1_available_ts` strictly, found via `bisect`, never assumed `+1`).
10. `test_c1_c2_share_everything_except_candle_source` — a structural test: both call the same `detect_triggers(feeder_source, ...)` entry point; assert via introspection or a shared-code-path marker that no C1-only or C2-only branch exists outside the swapped `feeder_source` argument.
11. Re-affirm from the existing suite: Arm A still reproduces the audited baseline exactly (already covered, unaffected by this revision).

## 7. B1-realistic caveat (review §7 — documentation only, B1 not rerun)

`trades_b1_realistic.csv`'s `-145.86R` approximates the price available at order placement using the M15 bar's **close** price, and models scanner discovery delay as a flat `+120s` (`POLL_SECONDS`) added to the H4 close. Two compounding approximations, both stated plainly here (not re-run): (a) real MT5 execution would use a live bid/ask tick at the actual moment of placement, not a 15-minute bar's close — intra-bar price movement between the true placement instant and that bar's close is invisible to this approximation in either direction; (b) the real discovery delay is uniformly distributed over `[0, 120s]` depending on poll phase relative to the H4 close, not a fixed `120s` — B1-realistic used the conservative worst-case end of that range, not an average. **B1-realistic's number is a directional, order-of-magnitude diagnostic of what realistic discovery latency does to the strategy — not a claim of reproducing actual historical MT5 fills.**

## 8. C1 vs. C2 isolation, reconfirmed under the fixes

Both arms now share: §1's `fill_pass_c`, §2's `key_level_credited` (same `KeyLevel` objects, sourced identically), §3's bar contract, §5's state machine, and `build_stage6_population`/`_resolve_exits` (unmodified). The **only** swapped dependency remains which function supplies the reference/current `ProvisionalFeederCandle`/`CompleteFeederCandle` pair (§4's broker-grid builder for C1, NY-anchored builder for C2) — enforced by both arms calling one shared `causal_intrabar.detect_triggers(feeder_source, h4_broker_for_key_levels, ...)`, where `h4_broker_for_key_levels` is **always** the broker grid (Key-Level source held constant per §2.2, independent of which grid supplies the sweep side).

## 9. Risks, ambiguities, pending decisions (updated, round 2)

1. ~~Key-Level source causality not independently re-derived~~ — **CLOSED, §2.1c.**
2. ~~USDCAD/AUDUSD completeness not measured~~ — **CLOSED, §4.2**, with one new, real finding: the AUDUSD 2007-2009 9AM-NY gap concentration, not root-caused further (not checked against broker trading-hours-change history for that pair/period) — carried forward as a known, quantified, non-uniform data limitation specific to AUDUSD's 9AM arm, not averaged away.
3. DOL-gated reversal/continuation profile selection — still out of scope (charter defers to unreleased material).
4. 9AM sweeping the 1AM range (i-2) instead of 5AM's (i-1) — still out of scope per user restriction.
5. Non-Model-1 (TSQ/breaker-block) entries — still out of scope, no detector scaffolding.
6. Intrabar same-M15-bar ambiguity — unchanged conservative policy (resolve at that bar's `available_at`), correctly defined per §3.
7. DST-transition-day 4-hours convention — unchanged policy; §4.2 confirms 2004-03-30/2005-06-10 appear as incomplete-bucket examples in all three pairs, consistent and small.

## 10. Full causal-chain verification

Re-checked explicitly against the chain the review specified, stage by stage, under the round-2 fixes:

| Stage | Instant used | Never uses information known later than... |
|---|---|---|
| Key Level available | `available_at(level.origin_index)` — that candle's own close (§2.1b/§2.1c, independently traced to swings/MSS/displacement/ATR or the 3-candle FVG gap) | ...its own origin candle's close. |
| Previous feeder candle confirmed | Passes §4's `validate_complete_feeder_bucket`; its `available_at` is its own close | ...its own close. A bucket failing validation is never promoted to a reference range at all. |
| Sweep + Key Level observed | `activation_instant_ts = available_at(the M15 bar whose running high/low first satisfies both)` (§5, `HTF_CONDITIONS_OBSERVED`) | ...that M15 bar's own close. The Key-Level side of this check already only credits levels with `available_at(origin_index) < activation_instant_ts` (§2.2). |
| Model-1 search | Window `[max(window_start, activation_instant), window_end)` (§5's `WAITING_FOR_MODEL1`), unmodified `confirm_in_ltf_window` | ...nothing new — a search interval, not a decision; everything it can find is already bounded to start at-or-after `activation_instant_ts`. |
| Model-1 confirmed and available | `model1_available_ts = available_at(confirmation_index)` (§1.3) | ...the confirmation bar's own close. |
| Order constructed and placed | Same instant as above (§1.3) | ...nothing new; all price levels were already fixed earlier and are not time-sensitive data. |
| First negotiable instant | `first_fillable_index`, the bar strictly **after** the confirmation bar, located via `bisect` on real timestamps (§1.2b, the round-2 fix) | ...`order_placed_ts`; critically, **not** the confirmation bar's own high/low range. |
| Fill | `fill_pass_c` (§1.4), `_fill_sides`/`two_heap_sweep` unmodified, swept from `first_fillable_index` | ...each swept bar's own close, exactly as production's fill mechanics already assume uniformly. |
| SL/TP/partial/breakeven | `_resolve_exits` unmodified | ...each resolving bar's own close — no causality defect of its own (Phase 1 finding, unchanged). |

No stage in this chain reads a value from a candle later than the one that stage's own `available_at` instant corresponds to.

## 11. Explicit answers (per the review's 6 questions)

1. **¿Son causalmente correctos los FVG?** Sí — trazado hasta `core/atr.py`, sin dependencia futura, confirmado en §2.1b.
2. **¿Son causalmente correctos los Order Blocks?** Sí — trazado hasta swings (`primitives/swing.py`, que SÍ necesita la vela `i+1` para confirmar un swing — una capa adicional de retraso causal que resultó estar ya correctamente absorbida por el diseño existente), MSS, displacement y el escaneo hacia atrás del anchor, confirmado en §2.1b.
3. **¿Qué porcentaje de velas feeder está incompleto en cada par?** EURUSD 0.07-0.20%, USDCAD 0.12-0.25%, AUDUSD 0.10-0.30% salvo su 9AM-NY específico en 2.10% (concentrado 84% en 2007-2009, no en historial temprano) — tabla completa en §4.2.
4. **¿Está corregida la elegibilidad temporal de `fill_pass_c`?** Sí, en esta ronda — el piso ahora es `first_fillable_index` (la vela DESPUÉS de la de confirmación, localizada por timestamp real vía `bisect`), no `confirmation_index` como en la ronda anterior, que todavía permitía usar el rango completo de la vela de confirmación misma.
5. **¿Queda algún problema que impida considerar C1/C2 experimentalmente ejecutables?** No, a nivel de diseño. Los dos bloqueos pendientes de la ronda anterior quedaron cerrados (§2.1c, §4.2). La anomalía de AUDUSD 2007-2009 (§9.2) es una limitación de datos conocida y cuantificada, no un bloqueo de diseño — debe reportarse junto a los resultados de esa pata, no impide implementar.
6. **¿Recomiendas autorizar la implementación?** Sí. El diseño (máquina de estados, contrato de timestamps, `fill_pass_c` corregido, puente de Key Levels, validación de integridad de velas) no tiene ninguna pregunta abierta que yo pueda identificar. La única salvedad que dejo explícita: la anomalía de AUDUSD 2007-2009 debería leerse como "los resultados del brazo 9AM de AUDUSD en ese período tienen una cobertura de datos más débil que el resto" en el informe final, no como un defecto a corregir antes de implementar.
