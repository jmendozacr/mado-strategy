# Design — Intrabar causal detector (Arms C1/C2)

Status: **design only, not implemented**. Stop point per user instruction. Nothing under `detector/`/`scanner/` touched; nothing in `/docs` touched; A/B1/B2 outputs untouched.

## 0. Scope lock (what this design does NOT cover)

Charter-11 names considerably more structure than this experiment implements. Documented explicitly so no variant is silently assumed equivalent:

| Charter-11 concept | In scope for C1/C2? | Why |
|---|---|---|
| "Core model": 1AM+5AM range → 9AM sweep(of 5AM, i.e. i-1)+Model-1 | **Yes** — this is the user's worked example | Explicitly requested |
| 9AM sweeping the **1AM** range instead of 5AM's (line 42: "needs that soup from EITHER the 1:00 a.m. OR the 5:00 a.m. range") | **No** | Current production code only ever checks `prev = htf_candles[i-1]`; charter allows i-2 too. User restricted scope to "la variante de dos velas consecutivas". Flagged as a known gap (§8.3), not built. |
| Reversal vs. Continuation profile selection, each with 2 sub-variants (v1.1/v1.2) | **No** | Charter-11:86-91 says the gatekeeper is **Daily Draw-on-Liquidity status**, and Mado explicitly defers DOL mechanics to unreleased "C3" material — there is no documented, implementable rule available today. Building a DOL gate would require a **new, unapproved** decision. Flagged (§8.2). |
| Non-Model-1 entries (Turtle-Soup/breaker-block inside the TSQ) — charter-11's own Example 1 says its reversal trade is explicitly "not a valid Model 1" | **No** | User's rule explicitly says "la entrada se ejecuta según las reglas del Modelo #1". The detector has zero scaffolding for breaker-block/TSQ entries (confirmed gap, matches prior Engram finding). Flagged (§8.4). |
| 1AM model's own analogous sweep (vs. the 9PM candle) | **Yes, mirrored** | User: "La misma lógica causal debe analizarse para el modelo 1AM, utilizando su vela feeder anterior correspondiente." Same state machine, `prev` = 9PM candle, `current` = 1AM candle, same window policy (NY 02:00-04:00 per `MODEL_1AM`). |

C1 and C2 both implement **only** the core-model, two-consecutive-feeder-candle, Model-1-only variant, for both the 1AM and 9AM models. Nothing else.

## 1. Architecture

Three new modules under `audit/2026-11-17-causal-lookahead-audit/`, none touching `detector/`:

```
feeder_ny.py        -- NY-local-anchored feeder candle construction (complete + provisional)
causal_intrabar.py  -- the state machine; C1/C2 signal detection (replaces arm_b2_signals' role)
run_c1_c2.py         -- orchestrator (mirrors run_experiment.py's shape)
```

Everything else is **imported, unmodified**, from `detector/`: `alignment.htf_ltf._purge_wick_extremes`, `_key_level_credit_map` (Key Level crediting — already high/low-only, already causal); `causal.htf_trigger.confirmation_window_utc`, `ltf_window_indices`, `confirm_in_ltf_window`, `MODEL_1AM`, `MODEL_9AM` (window bounds + the UNCHANGED Model-1 search); `backtest.population.build_stage6_population`; `backtest.simulate.simulate`; `core.config.DetectorConfig`; the same `SYMBOL_CONFIG` from `experimental.htf_trigger_1am_9am_backtest` used by A/B1/B2.

**Key simplification, discovered while designing**: because the new trigger condition (sweep + Key Level, both wick-only) can only fire at-or-after `activation_instant`, and the Model-1 search window is floored at `max(window_start, activation_instant)`, the resulting `retest_index` is *causally valid by construction* — exactly the same situation as Arm B2. **C1 and C2 need no custom fill pass.** Both feed their signals into the production `build_stage6_population`/`simulate`, unmodified — identical reuse pattern to B2, not B1. This directly satisfies §7's "no second Model-1 implementation": only the *trigger* (sweep+Key-Level detection) is new; confirmation, retest, fill, SL/TP/partial/breakeven are 100% the existing functions.

## 2. State machine

| State | Entered when | Timestamp recorded |
|---|---|---|
| `WAITING_FOR_FEEDER` | Reference (previous) feeder candle not yet fully closed | — (not yet a real event) |
| `WAITING_FOR_SWEEP_AND_KEY_LEVEL` | Reference candle's final OHLC known (its own close has occurred) | `feeder_ref_close_ts` |
| `WAITING_FOR_MODEL1` | First M15 close at which the running high/low of the *current* forming candle both (a) breaches the reference candle's extreme and (b) credits a registered Key Level (`_purge_wick_extremes`/`_key_level_credit_map`, evaluated on the provisional candle) | `activation_instant_ts` (= that M15 candle's own close, see §8.5 on intrabar resolution) |
| `MODEL1_CONFIRMED` | `confirm_in_ltf_window` (unmodified) returns a `CONFIRMED` `Model1Signal` inside `[max(window_start, activation_instant), window_end)` | `confirmation_ts` = `m15.candles[signal.confirmation_index].timestamp` |
| `ORDER_ACTIVE` | Same instant as `MODEL1_CONFIRMED` (Model-1's own retest IS the order-construction trigger — no separate discovery delay, unlike B1, because this path never used pre-activation information to find it) | `retest_ts` = `m15.candles[signal.retest_index].timestamp` |
| `FILLED` / `EXPIRED` / `INVALIDATED` | Production `simulate()`'s own unmodified fill/resolve outcome | `entry_ts`/`exit_ts` from the resulting `Trade` |

Invariant checked in tests (§9 of the prior conversation's test suite will be extended, not rewritten): every state's timestamp is `>=` the previous state's timestamp, for every signal, in both C1 and C2 output.

**Important distinction from B1/B2**: B2 floored the window at the H4 candle's *close* (one instant per trigger). C1/C2 floor it at `activation_instant` — the sweep+Key-Level moment, which can fall *anywhere* inside the forming candle, usually well before its close. This is the whole point: it recovers trades B2 destroyed by being needlessly strict (waiting for the close when the charter never asked for that), while still never using information before it was real.

## 3. Feeder candle construction (`feeder_ny.py`)

Two candle shapes, deliberately different types so a "final value of an open candle" cannot type-check as available:

```python
@dataclass(frozen=True)
class CompleteFeederCandle:        # only ever built from a FULLY elapsed window
    open: float; high: float; low: float; close: float
    open_ts: datetime; close_ts: datetime

@dataclass(frozen=True)
class ProvisionalFeederCandle:     # built from "M15 bars closed so far" only
    open: float; running_high: float; running_low: float
    open_ts: datetime; as_of_ts: datetime   # NO close field -- cannot exist
```

- `complete_feeder_candles(m15_series, feeder_hour_ny)`: for each calendar day, true NY-local open via `zoneinfo` (the exact technique already validated empirically: `America/New_York` localize → `.astimezone(UTC)`), window `[open, open+4h)`, bucket M15 candles via `bisect`. **A day with zero M15 candles in the bucket produces NO candle (skipped, never synthesized)** — handles holidays/gaps per the "no inventar velas" constraint. The 2 DST-transition days/year use the same UTC-side `+timedelta(hours=4)` convention `confirmation_window_utc` already uses elsewhere in this codebase, for consistency — flagged explicitly in §8.6 as the one place "4 hours" means 4 *real* hours, not 4 *wall-clock-labelled* hours, on those 2 days only.
- `provisional_feeder_candle(m15_series, open_ts, as_of_index)`: aggregates only `m15_series.candles[start:as_of_index+1]` (bars with `timestamp <= as_of_ts`, i.e., **already closed** M15 bars) into a `ProvisionalFeederCandle`. Called once per M15 step while walking forward through the forming candle's span — this is the "watch the vela as it forms" loop.
- **C1's candle source**: same construction function, but with `feeder_hour_ny` replaced by the *existing* `trigger_utc_hour` from `causal.htf_trigger.FeederModel` and windows built directly on the fixed UTC grid (00/04/08/12/16/20) — i.e., C1 literally reuses today's production grid-selection logic for *which* candle is "current"/"previous", just observes it incrementally instead of only at the end.
- **C2's candle source**: `feeder_ny.py`'s NY-anchored construction, per the validated 84-86%-different geometry.

## 4. Key Level causal handling

No new logic: `_purge_wick_extremes(candle, crt_range)` and `_key_level_credit_map(...)` are **imported unmodified**. They are called with a tiny adapter object exposing only `.high`/`.low` (either a real `Candle` with `open`/`close` set to a placeholder — never read by these two functions, confirmed by reading their source — or a minimal duck-typed stand-in) carrying the `ProvisionalFeederCandle`'s `running_high`/`running_low`. Re-evaluated on every new M15 close until it first returns non-`None`/non-empty — that candle is `activation_instant`.

**Flagged risk, not resolved here (§8.1)**: the Key Levels themselves (FVGs on H4, Order Blocks on Daily) are built by `build_key_levels`/`detect_fvgs`/`detect_order_blocks` from the *existing* H4/Daily series — those detectors were never causality-audited in this investigation. `_key_level_credit_map`'s own `origin_index < purge_index` check already prevents crediting a level that didn't exist yet at the purge, which covers the *registration* side — but whether an individual FVG/Order-Block's own `origin_index` is itself causally knowable the instant it's dated (vs. needing its own formation candle's close) is **out of scope for this phase**, carried over unchanged from every other arm (A/B1/B2 inherit the same assumption).

## 5. Activation window (shared by C1 and C2)

```
eligible_start = max(window_start_utc, activation_instant_utc)   # window_start/end: confirmation_window_utc(reference_or_current_candle, model), UNCHANGED
eligible_end   = window_end_utc
if eligible_start >= eligible_end:
    # legitimate zero-signal outcome for this trigger -- recorded with a reason,
    # same convention as B2's zero_signal_reasons.csv
```

No unlimited window, no fixed duration-from-sweep, no "rest of the H4 bar" — exactly the policy the user specified. `ltf_window_indices` (unmodified) converts to M15 indices.

## 6. Model-1 integration

`confirm_in_ltf_window(ltf_series.candles, ltf_ranges, window, direction, model1_config)` — called **exactly as B2 already calls it**, unmodified, with the window from §5. Zero new Model-1 code.

## 7. C1 vs. C2 isolation

Both arms share: the state machine (§2), the Key-Level adapter (§4), the window policy (§5), `confirm_in_ltf_window`/`build_stage6_population`/`simulate` (all unmodified), and the exact same `SYMBOL_CONFIG` per pair. They differ in **exactly one swapped dependency**: which function builds "the reference candle" and "the provisional current candle" (§3's C1-grid vs. C2-NY constructors). This is enforced by having both arms call the *same* `causal_intrabar.detect_triggers(feeder_source, ...)` function, parameterized only by which `feeder_ny`-shaped source it's given — not two separate code paths that could silently drift.

## 8. Risks, ambiguities, pending decisions (not resolved by me)

1. **Key Level source causality** (FVG/Order-Block detection itself) — not audited this phase; inherited by every arm equally, so it does not bias a C1-vs-C2 comparison, but it is a limitation of the whole investigation's absolute numbers.
2. **DOL-gated reversal/continuation profile selection** — charter-11 itself says the mechanics aren't published yet ("C3"). Cannot be implemented faithfully without inventing a rule the source material doesn't give. Out of scope; flagged, not guessed at.
3. **9AM sweeping the 1AM range (i-2) instead of 5AM's (i-1)** — a second, charter-confirmed valid path the current code (and C1/C2) do not check. Out of scope per user's explicit restriction to the two-consecutive-candle variant; would roughly double the trigger search if added later.
4. **Non-Model-1 (TSQ/breaker-block) entries** — charter-11's own first worked example is explicitly not a Model-1 trade. Out of scope per user's rule (§1 point 7: "la entrada se ejecuta según las reglas del Modelo #1"); the detector has no scaffolding for this entry type at all.
5. **Intrabar same-M15-bar ambiguity**: if the sweep and the Key-Level credit both first become true within the *same* M15 candle (common — both conditions are evaluated off the same running high/low), or if both the high-side and low-side of the reference range breach on the same M15 bar (~14% of real purges, per `_purge_wick_extremes`'s own docstring), sub-15-minute ordering is unknowable from this data. **Conservative policy**: `activation_instant` = that M15 candle's own **close** timestamp, never its open or an interpolated instant. Resolving this more precisely would need M1 (1-minute) or tick data — explicitly flagged as a real resolution limit, not simulated around.
6. **DST transition days** (2/year): "4 hours" in the feeder-candle window is implemented as 4 real UTC hours (matching `confirmation_window_utc`'s own existing convention), not 4 wall-clock-labelled NY hours — on the spring-forward/fall-back day itself, this means the candle's wall-clock label and its real duration diverge by up to 1 hour. Affects roughly 2 candles/year per model, out of ~6,100 checked in §Phase-1's empirical comparison — not expected to be material, but reported per-pair in the C1/C2 results rather than assumed away.

## 9. Concrete chronological examples

**EDT example (1AM model, matches the Phase-1-finding dataset)**: reference candle = the true NY-anchored "9PM" candle, `open_ts=2003-05-05 01:00 UTC` (9pm NY EDT = UTC+4), `close_ts=2003-05-05 05:00 UTC`. Current candle ("1AM") opens `2003-05-05 05:00 UTC` (1am NY EDT). Suppose the running low first breaches the 9PM candle's low AND credits a registered Key Level at M15 bar closing `2003-05-05 06:30 UTC` → `activation_instant = 06:30 UTC`. Original window for `MODEL_1AM` on this trigger candle: NY 02:00-04:00 EDT = UTC 06:00-08:00. `eligible_start = max(06:00, 06:30) = 06:30`; `eligible_end = 08:00`. Model-1 search runs `confirm_in_ltf_window` over M15 bars in `[06:30, 08:00)` only — never over `[05:00, 06:30)`, even though that earlier span is where the *current* code's close-based trigger would have let a signal fire.

**EST example (9AM model)**: true NY-anchored "5AM" reference candle `open_ts=2026-01-15 10:00 UTC` (5am NY EST), close `14:00 UTC`. Current ("9AM") candle opens `14:00 UTC` (9am NY EST), true close `18:00 UTC`. Suppose sweep+Key-Level both resolve at M15 close `14:20 UTC`. Original window for `MODEL_9AM`: NY 09:00-10:30 EST = UTC 14:00-15:30. `eligible_start = max(14:00, 14:20) = 14:20`; `eligible_end = 15:30`. Note this window **never reaches 18:00** (the true close) — matching the Phase-1 finding that the whole 9AM window structurally precedes the close — but unlike B2, this arm does **not** require reaching the close at all, since the trigger here never needed it in the first place.

## 10. What happens next (not yet authorized)

Implementing `feeder_ny.py` + `causal_intrabar.py` + `run_c1_c2.py`, then running C1 and C2 across EURUSD/USDCAD/AUDUSD/2003-2026, writing `trades_c1.csv`/`trades_c2.csv`, extending the reconciliation file, and extending the automated-test suite with the invariants named in §2 and §8.5/8.6. Stopping here per instruction, awaiting review.
